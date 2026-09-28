"""6.4 + 6.5 end to end through the registry: a SISA ensemble registered as a model version, its
container SBOM attached, the SOUP export, a withdrawal, the registry's ``registry.retrain`` job
running recipe ``sisa`` (one shard retrained), and the SOUP export of both versions.

Synthetic data only. Not certified unlearning (docs/features/sisa.md).
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from gov_helpers import audit_rows, principal
from nf_platform.db import models as m
from nf_platform.db.context import tenant_session
from nf_platform.governance import deletion
from nf_platform.registry import retrain as rretrain
from nf_platform.registry import service as svc
from nf_platform.registry.card import ModelCard
from nf_train import decoder, sisa
from nf_train import platform as sp
from sqlalchemy import select

pytestmark = pytest.mark.postgres

CFG = sisa.SisaConfig(shards=3, slices=2, seed=5, fit=decoder.FitParams(iterations=40))
FIXTURE = Path(__file__).resolve().parents[1] / "soup" / "fixtures" / "model-container.cdx.json"
M = {"summary": "toy SISA decoder", "limitations": "synthetic data only", "modalities": ["EEG"]}


def _card() -> ModelCard:
    meas = {"method": "m", "metric": "accuracy", "value": 0.5}
    return ModelCard(
        **M,
        task="decoding",
        inferences=["motor_intent"],
        robustness={"noise": meas, "channel_dropout": meas, "adversarial": meas},
    )


def _components(bom: dict) -> set[tuple[str, str, str]]:
    out, stack = set(), list(bom["components"])
    while stack:
        c = stack.pop()
        out.add((c["name"], str(c.get("version") or "unknown"), str(c.get("purl") or "")))
        stack.extend(c.get("components") or [])
    return out


@pytest.fixture
def registered(world, storage, engine):
    tid, subs = world["tid"], world["subjects"]
    owner = principal(tid, "owner", pid="user-owner")
    with tenant_session(owner, engine=engine) as s:
        obj = sp.train_sisa(s, storage, owner, [v["node"] for v in subs.values()], CFG)
        model = svc.register_model(s, owner, name="toy-sisa", card=_card())
        v1 = svc.register_version(
            s,
            owner,
            model.id,
            weights_object=svc.ObjectRef(derived_object_id=obj.id),
            training_manifest=sp.manifest_for(obj),
            pipeline_version_ids=[],
            code_commit="75c5f39",
            intended_use="Research decoding of synthetic band-power features.",
            use_restrictions=["research_only"],
        )
        out = {
            "model_id": str(model.id),
            "version": v1.version,
            "version_id": v1.id,
            "obj_id": obj.id,
            "assignment": dict(obj.params["sisa"]["assignment"]),
            "checkpoints": dict(obj.params["sisa"]["checkpoints"]),
        }
        assert v1.recipe == "sisa" and v1.manifest["shards"] == {
            h: kr[0] for h, kr in out["assignment"].items()
        }
    return {**world, **out}


def test_sisa_registry_soup_export_and_one_shard_retrain(
    client, as_role, registered, storage, engine, worker, tenants
):
    w = registered
    h = w["h"]
    base = f"/v1/models/{w['model_id']}/versions/{w['version']}"
    bom = json.loads(FIXTURE.read_text("utf-8"))

    # 6.5: attach the container SBOM, export the SOUP document
    r = client.put(f"{base}/sbom", json=bom, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["component_count"] == len(_components(bom))
    r = client.get(f"{base}/soup", headers=as_role("viewer"))
    assert r.status_code == 200, r.text
    doc = r.json()
    got = {(d["name"], d["version"], d["purl"]) for d in doc["dependencies"]["components"]}
    assert _components(bom) <= got
    assert "not intended for real-time or safety-critical control" in doc["statement"].lower()
    assert doc["intended_use"].startswith("Research decoding")
    assert "research_only" in doc["use_restrictions"]
    assert doc["training"]["sisa"]["shards"] == CFG.shards
    assert "NOT certified unlearning" in doc["training"]["sisa"]["statement"]
    assert doc["retrain_required"] is False
    for hid in w["assignment"]:
        assert hid not in r.text  # no hashed subject ids in the export
    again = client.get(f"{base}/soup", headers=h)
    assert again.content == r.content  # byte-identical regeneration
    exports = [
        e for e in audit_rows(engine, type="data.export") if e["action"] == "model:soup-export"
    ]
    assert exports and exports[-1]["details"]["sha256"]
    # another tenant: 404 for both routes
    other = as_role("owner", tenant=tenants.b)
    assert client.get(f"{base}/soup", headers=other).status_code == 404
    assert client.put(f"{base}/sbom", json=bom, headers=other).status_code == 404
    # a malformed SBOM is refused
    assert client.put(f"{base}/sbom", json={"bomFormat": "x"}, headers=h).status_code == 422

    # withdraw one subject: the DeletionJob flags the version
    gone = sorted(w["assignment"], key=lambda x: (-w["assignment"][x][1], x))[0]
    k, r0 = w["assignment"][gone]
    sid = w["subjects"][gone]["subject_id"]
    r = client.post(f"/v1/subjects/{sid}/withdrawals", json={}, headers=as_role("data-steward"))
    assert r.status_code == 202, r.text
    job = worker.run_once()
    assert job is not None and job.kind == deletion.JOB_KIND
    doc = client.get(f"{base}/soup", headers=h).json()
    assert doc["retrain_required"] is True
    assert any(a["source"] == "registry" for a in doc["known_anomalies"])

    # 6.3 + 6.4: the registry retrain runs recipe "sisa"
    r = client.post(f"{base}/retrain", json={}, headers=h)
    assert r.status_code == 202, r.text
    job = worker.run_once()
    assert job is not None and job.kind == rretrain.JOB_KIND
    owner = principal(w["tid"], "owner", pid="user-owner")
    with tenant_session(owner, engine=engine) as s:
        rt = s.scalar(select(m.ModelRetrain).where(m.ModelRetrain.version_id == w["version_id"]))
        assert rt.state == "succeeded", rt.error
        v2 = s.scalar(select(m.ModelVersion).where(m.ModelVersion.id == rt.new_version_id))
        assert v2.parent_version_id == w["version_id"] and v2.recipe == "sisa"
        assert gone in v2.manifest["excluded_subjects"] and gone not in v2.manifest["subjects"]
        assert gone not in svc.lineage_subjects(s, v2)
        assert not svc.retrain_required(s, v2.id)
        new = s.scalar(select(m.DerivedObject).where(m.DerivedObject.id == v2.derived_object_id))
        audit_doc = new.params["checkpoint_audit"]
        assert audit_doc["shards_retrained"] == [k]
        touched = {e[0] for key in ("read", "written", "discarded") for e in audit_doc[key]}
        assert touched == {k}
        kept = new.params["sisa"]["checkpoints"]
        for key, ref in w["checkpoints"].items():
            kk, rr = (int(x) for x in key.split("/"))
            if kk != k or rr < r0:
                assert kept[key] == ref  # the same checkpoint object, not rewritten
            else:
                assert kept[key] != ref
                old = s.scalar(select(m.DerivedObject).where(m.DerivedObject.id == uuid.UUID(ref)))
                assert old.key_state == "shredded"
        v2_no = v2.version

    doc2 = client.get(f"/v1/models/{w['model_id']}/versions/{v2_no}/soup", headers=h).json()
    assert doc2["training"]["sisa"]["withdrawn_subjects"] == 1
    assert doc2["retrain_required"] is False
    # no SBOM attached to v2 yet: the export says so and falls back to the locked Python deps
    assert doc2["dependencies"]["source"]["kind"] == "python-lock"
