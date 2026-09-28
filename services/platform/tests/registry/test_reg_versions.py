"""6.1 acceptance: Model/ModelVersion, model card, training-set manifest, lineage.

- registering a version without a training-set manifest fails;
- the lineage query from a model version returns every training subject's raw node;
- the manifest holds hashed subject IDs computed from the lineage (never the client's list);
- SEC-146: a subject without ``model_training`` consent -> 403, audited;
- SEC-061: weights only as safetensors/ONNX, structure-checked, never deserialised;
- SEC-145: the card requires robustness measurements; the committed JSON Schema matches the model.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import numpy as np
import pytest
from gov_helpers import ALL_SCOPES, make_recording, make_subject, principal
from nf_platform.db import models as m
from nf_platform.db.context import tenant_session
from nf_platform.governance import derived
from nf_platform.registry import card as card_mod
from nf_platform.registry import manifest as mf
from reg_helpers import (
    COMMIT,
    audit_rows,
    card,
    new_model,
    post,
    raw_chain,
    safetensors,
    version_body,
    weights_upload,
)
from sqlalchemy import select

pytestmark = pytest.mark.postgres
REPO = Path(__file__).resolve().parents[4]


@pytest.fixture
def two_subjects(client, as_role, tree, storage, engine, tenants):
    h = as_role("owner")
    out = {}
    for label in ("sub-x", "sub-y"):
        sub = make_subject(client, h, tree["dataset_id"], label)
        rid = make_recording(
            client,
            h,
            sub["session_id"],
            storage=storage,
            engine=engine,
            tenant_id=tenants.a,
            subject_id=sub["subject_id"],
        )
        out[label] = {**sub, "recording_id": rid, **raw_chain(engine, tenants.a, rid)}
    return out


def test_register_without_manifest_fails(client, as_role, two_subjects):
    h = as_role("scientist")
    model = new_model(client, h)
    url = f"/v1/models/{model['id']}/versions"
    body = version_body([two_subjects["sub-x"]["feature"]])
    del body["training_manifest"]
    r = client.post(url, json=body, headers=h)
    assert r.status_code == 422 and r.json()["code"] == "manifest_required", r.text
    body["training_manifest"] = {"input_node_ids": []}
    r = client.post(url, json=body, headers=h)
    assert r.status_code == 422 and r.json()["code"] == "manifest_required", r.text
    assert client.get(url, headers=h).json() == []


def test_version_manifest_and_lineage_reach_every_subject_raw_node(
    client, as_role, two_subjects, tenants, tree
):
    h = as_role("scientist")
    model = new_model(client, h)
    x, y = two_subjects["sub-x"], two_subjects["sub-y"]
    v = post(
        client,
        f"/v1/models/{model['id']}/versions",
        version_body(
            [x["feature"], y["feature"]],
            pipeline_version_ids=[tree["pipeline_ref"]],
            use_restrictions=["research_only"],
        ),
        h,
    )
    assert v["version"] == 1 and v["weights_format"] == "safetensors"
    assert v["pipeline_version_ids"][0].startswith("pv:sha256:")
    assert v["code_commit"] == COMMIT
    assert "Not intended for real-time or safety-critical control." in v["intended_use"]
    assert set(v["use_restrictions"]) == {"research_only", "no_realtime_control"}
    assert v["manifest_summary"]["n_subjects"] == 2 and v["retrain_required"] is False
    full = client.get(
        f"/v1/models/{model['id']}/versions/1", params={"include_manifest": True}, headers=h
    ).json()
    hashes = {mf.subject_hash(tenants.a, s["subject_id"]) for s in (x, y)}
    assert set(full["manifest"]["subjects"]) == hashes
    assert full["manifest"]["schema"] == mf.SCHEMA
    assert mf.digest(full["manifest"]) == v["manifest_sha256"]
    blob = json.dumps(full)
    assert x["subject_id"] not in blob and y["subject_id"] not in blob  # hashed only

    g = client.get(f"/v1/models/{model['id']}/versions/1/lineage", headers=h).json()
    assert "nodes" in g, g
    ids = {n["id"] for n in g["nodes"]}
    assert g["root"] == v["prov_node_id"] and g["n_training_subjects"] == 2
    for s in (x, y):
        assert str(s["raw"]) in ids and str(s["recording"]) in ids, "raw node missing"
    raw_refs = {n["ref_id"] for n in g["nodes"] if n["type"] == "raw_file"}
    assert raw_refs == {f"raw-{x['recording_id']}", f"raw-{y['recording_id']}"}
    detail = client.get(f"/v1/models/{model['id']}", headers=h).json()
    assert [v_["version"] for v_ in detail["versions"]] == [1]
    assert detail["latest_version"]["id"] == v["id"]


def test_subject_hashes_and_exclusions_are_checked(client, as_role, two_subjects, tenants):
    h = as_role("scientist")
    model = new_model(client, h)
    x, y = two_subjects["sub-x"], two_subjects["sub-y"]
    url = f"/v1/models/{model['id']}/versions"
    hx = mf.subject_hash(tenants.a, x["subject_id"])
    hy = mf.subject_hash(tenants.a, y["subject_id"])
    lie = version_body([x["feature"]])
    lie["training_manifest"]["subject_hashes"] = [hy]
    assert client.post(url, json=lie, headers=h).status_code == 422
    excl = version_body([x["feature"]])
    excl["training_manifest"]["excluded_subject_hashes"] = [hx]
    r = client.post(url, json=excl, headers=h)
    assert r.status_code == 422 and r.json()["code"] == "excluded_subject_present"
    shards = version_body([x["feature"], y["feature"]])
    shards["training_manifest"]["shards"] = {hx: 0}
    assert client.post(url, json=shards, headers=h).status_code == 422
    shards["training_manifest"]["shards"] = {hx: 0, hy: 1}
    v = post(client, url, shards, h)
    assert v["manifest_summary"]["n_shards"] == 2
    unknown = version_body([x["feature"]], use_restrictions=["no_such_restriction"])
    assert client.post(url, json=unknown, headers=h).status_code == 422
    missing = version_body([uuid.uuid4()])
    assert client.post(url, json=missing, headers=h).status_code == 422


def test_training_consent_is_required_and_denial_audited(
    client, as_role, tree, storage, engine, tenants
):
    h = as_role("owner")
    no_training = tuple(s for s in ALL_SCOPES if s != "model_training")
    sub = make_subject(client, h, tree["dataset_id"], "sub-nt", scopes=no_training)
    rid = make_recording(
        client,
        h,
        sub["session_id"],
        storage=storage,
        engine=engine,
        tenant_id=tenants.a,
        subject_id=sub["subject_id"],
    )
    chain = raw_chain(engine, tenants.a, rid)
    model = new_model(client, h)
    r = client.post(
        f"/v1/models/{model['id']}/versions", json=version_body([chain["feature"]]), headers=h
    )
    assert r.status_code == 403 and "model_training" in r.json()["detail"], r.text
    denied = [
        e
        for e in audit_rows(engine, type="authz.denied", action="model:train")
        if e["request_id"] == r.headers["x-request-id"]
    ]
    assert denied and denied[0]["outcome"] == "denied"
    with engine.connect() as c:  # nothing sealed or recorded
        assert c.exec_driver_sql("SELECT count(*) FROM model_version").scalar() == 0


@pytest.mark.parametrize(
    "weights",
    [
        weights_upload(b"\x80\x04\x95pickle"),  # not safetensors
        weights_upload(safetensors()[:-1]),  # truncated data section
        weights_upload(b"\x08\x07", fmt="onnx"),  # ir_version only, no graph
        {"format": "pt", "data_base64": "AA=="},  # a format outside SEC-061
        {"format": "safetensors", "data_base64": "not base64!"},
        {},  # neither an object nor data
    ],
)
def test_weights_are_structure_checked(client, as_role, two_subjects, weights):
    h = as_role("scientist")
    model = new_model(client, h)
    body = version_body([two_subjects["sub-x"]["feature"]], weights=weights)
    r = client.post(f"/v1/models/{model['id']}/versions", json=body, headers=h)
    assert r.status_code == 422, r.text


def test_onnx_upload_accepted(client, as_role, two_subjects):
    h = as_role("scientist")
    model = new_model(client, h)
    graph = b"\x3a\x02\x0a\x00"  # field 7 (graph), 2 bytes
    body = version_body(
        [two_subjects["sub-x"]["feature"]], weights=weights_upload(b"\x08\x07" + graph, "onnx")
    )
    v = post(client, f"/v1/models/{model['id']}/versions", body, h)
    assert v["weights_format"] == "onnx"


def test_platform_trained_weights(client, as_role, two_subjects, storage, engine, tenants):
    """A model derived object from a platform training job: the version's node IS its node, and
    the manifest inputs must be exactly the object's inputs."""
    h = as_role("scientist")
    owner = principal(tenants.a, "owner", pid="user-owner")
    x, y = two_subjects["sub-x"], two_subjects["sub-y"]
    with tenant_session(owner, engine=engine) as s:
        feats = []
        for sub in (x, y):  # a readable (.npy) single-subject input per subject
            obj = derived._record(
                s,
                owner,
                kind="group_average",
                activity_type="aggregate",
                entity_type="group_average",
                inputs=[sub["feature"]],
                data=derived._to_npy(np.arange(8, dtype=np.float64).reshape(2, 4)),
                bucket=derived.ARTIFACT_BUCKET,
                filename="data.npy",
                storage=storage,
                params={"method": "fixture"},
            )
            feats.append(obj.node_id)
        toy = derived.train_toy_model(s, storage, owner, feats)
        toy_id, toy_node = toy.id, toy.node_id
    model = new_model(client, h)
    url = f"/v1/models/{model['id']}/versions"
    body = version_body(feats[:1], weights={"derived_object_id": str(toy_id)})
    assert client.post(url, json=body, headers=h).status_code == 422  # inputs differ
    body = version_body(feats, weights={"derived_object_id": str(toy_id)})
    v = post(client, url, body, h)
    assert v["prov_node_id"] == str(toy_node) and v["derived_object_id"] == str(toy_id)
    assert v["weights_format"] == "platform/toy-mean-std"
    assert client.post(url, json=body, headers=h).status_code == 409  # one version per object
    with tenant_session(owner, engine=engine) as s:
        row = s.scalar(select(m.ModelVersion).where(m.ModelVersion.id == uuid.UUID(v["id"])))
        assert row.manifest["n_subjects"] == 2


def test_card_requires_robustness_and_schema_file_in_sync(client, as_role):
    h = as_role("scientist")
    doc = card()
    del doc["robustness"]
    r = client.post("/v1/models", json={"name": "no-robustness", "card": doc}, headers=h)
    assert r.status_code == 422
    bad = card()
    bad["robustness"]["noise"]["value"] = "NaN"
    r = client.post("/v1/models", json={"name": "nan", "card": bad}, headers=h)
    assert r.status_code == 422
    path = REPO / "docs" / "spec" / "model-card.schema.json"
    assert path.read_text(encoding="utf-8") == card_mod.json_schema_text(), (
        "regenerate docs/spec/model-card.schema.json from nf_platform.registry.card"
    )
    assert "robustness" in card_mod.json_schema()["required"]


def test_model_names_unique_and_other_tenant_404(client, as_role, tenants):
    h = as_role("scientist")
    model = new_model(client, h, name="dup-name")
    r = client.post("/v1/models", json={"name": "dup-name", "card": card()}, headers=h)
    assert r.status_code == 409
    hb = as_role("owner", tenant=tenants.b)
    assert client.get(f"/v1/models/{model['id']}", headers=hb).status_code == 404
    assert client.get("/v1/models", headers=hb).json() == []
    assert client.get(f"/v1/models/{model['id']}/versions", headers=hb).status_code == 404
    post(client, "/v1/models", {"name": "dup-name", "card": card()}, hb)  # names are per tenant
