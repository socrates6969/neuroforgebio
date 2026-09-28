"""AppSec M3: versions registered from UPLOADED weights carry a self-declared training lineage.

The platform cannot verify offline training, so such versions are labelled and restricted:

- ``weights_source`` (``platform`` | ``upload``) is part of the training manifest (hashing spec v2
  amendment, §9.7) and of every version view;
- publication and deployment of an upload-sourced version need a governance approver other than
  the uploader (four-eyes, ``model:approve``);
- taint is conservative: ANY subject withdrawal in the tenant after the version was registered
  flags it ``retrain_required`` with deployments blocked, reason "unverifiable lineage (uploaded
  weights)"; platform-trained versions keep the exact-lineage behaviour.
"""

from __future__ import annotations

import pytest
from gov_helpers import make_subject
from nf_platform.db import models as m
from nf_platform.db.context import tenant_session
from nf_platform.registry import manifest as mf
from nf_platform.registry import service as svc
from nf_platform.registry import vocab
from reg_helpers import feature_of, new_model, post, version_body
from sqlalchemy import select

pytestmark = pytest.mark.postgres
REASON = "unverifiable lineage (uploaded weights)"


def _deploy(client, h, model_id, version=1):
    body = {
        "version": version,
        "context": {"jurisdiction": "US", "setting": "research", "purpose": "study"},
    }
    return client.post(f"/v1/models/{model_id}/deployments", json=body, headers=h)


def _withdraw(client, as_role, worker, subject_id: str) -> str:
    steward = as_role("data-steward")
    r = client.post(f"/v1/subjects/{subject_id}/withdrawals", json={}, headers=steward)
    assert r.status_code == 202, r.text
    worker.kinds = ("governance.deletion",)
    job = worker.run_once()
    assert job is not None and job.kind == "governance.deletion"
    dj = client.get(f"/v1/deletion-jobs/{r.json()['id']}", headers=steward).json()
    assert dj["state"] == "succeeded", dj
    return dj["id"]


def _approve(client, as_role, model_id, version, sub):
    url = f"/v1/models/{model_id}/versions/{version}/approvals"
    r = client.post(url, headers=as_role("data-steward", sub=sub))
    assert r.status_code == 201, r.text


def test_weights_source_is_in_the_manifest_and_the_views(client, as_role, tree, engine, tenants):
    h = as_role("owner")
    node = feature_of(engine, tenants.a, tree["node_id"])
    model = new_model(client, h)
    v = post(client, f"/v1/models/{model['id']}/versions", version_body([node]), h)
    assert v["weights_source"] == "upload"
    full = client.get(
        f"/v1/models/{model['id']}/versions/1?include_manifest=true", headers=h
    ).json()
    assert full["manifest"]["weights_source"] == "upload"
    assert mf.digest(full["manifest"]) == full["manifest_sha256"]  # it is hashed
    listed = client.get(f"/v1/models/{model['id']}/versions", headers=h).json()
    assert [x["weights_source"] for x in listed] == ["upload"]
    detail = client.get(f"/v1/models/{model['id']}", headers=h).json()
    assert detail["latest_version"]["weights_source"] == "upload"


def test_report_attack_upload_declares_only_a_then_b_withdraws(
    client, as_role, tree, engine, tenants, worker
):
    """Report M3: weights trained offline on A and B, uploaded declaring only A; B withdraws. The
    version must NOT stay deployable or publishable."""
    h = as_role("owner")
    node_a = feature_of(engine, tenants.a, tree["node_id"])  # subject A = the tree's subject
    b = make_subject(client, h, tree["dataset_id"], "sub-B")
    model = new_model(client, h, privacy=True)
    mid = model["id"]
    v = post(client, f"/v1/models/{mid}/versions", version_body([node_a]), h)
    hb = mf.subject_hash(tenants.a, b["subject_id"])
    full = client.get(f"/v1/models/{mid}/versions/1?include_manifest=true", headers=h).json()
    assert hb not in full["manifest"]["subjects"]  # B was never declared
    _approve(client, as_role, mid, 1, "approver-1")
    assert _deploy(client, h, mid).status_code == 201  # deployable before the withdrawal

    dj = _withdraw(client, as_role, worker, b["subject_id"])
    out = client.get(f"/v1/models/{mid}/versions/1", headers=h).json()
    assert out["retrain_required"] and out["deployments_blocked"]
    assert [(f["deletion_job_id"], f["reason"]) for f in out["taint"]] == [(dj, REASON)]
    deps = client.get(f"/v1/models/{mid}/deployments", headers=h).json()
    assert [d["effective_state"] for d in deps] == ["blocked"]
    r = _deploy(client, h, mid)
    assert r.status_code == 403 and r.json()["code"] == vocab.R_RETRAIN
    _approve(client, as_role, mid, 1, "approver-2")
    r = client.post(f"/v1/models/{mid}/versions/1/publish", headers=h)
    assert r.status_code == 409 and r.json()["code"] == vocab.R_RETRAIN
    # the deletion certificate lists the flagged upload version with the reason
    cert = client.get(f"/v1/deletion-jobs/{dj}", headers=as_role("data-steward")).json()[
        "certificate"
    ]
    assert v["prov_node_id"] in cert["models_flagged"]
    acts = {n["node_id"]: n["action"] for n in cert["nodes"]}
    assert REASON in acts[v["prov_node_id"]]


def test_withdrawal_before_registration_does_not_taint(
    client, as_role, tree, engine, tenants, worker
):
    """The rule looks forward from the version's registration: an earlier withdrawal (whose data
    was already deleted when the version was registered) does not flag it."""
    h = as_role("owner")
    node_a = feature_of(engine, tenants.a, tree["node_id"])
    b = make_subject(client, h, tree["dataset_id"], "sub-B")
    _withdraw(client, as_role, worker, b["subject_id"])
    model = new_model(client, h)
    post(client, f"/v1/models/{model['id']}/versions", version_body([node_a]), h)
    out = client.get(f"/v1/models/{model['id']}/versions/1", headers=h).json()
    assert not out["retrain_required"] and out["taint"] == []


def test_platform_trained_version_keeps_exact_lineage(client, as_role, world, engine, worker):
    """A platform-trained version is flagged only by its own training subjects; an upload version
    in the same tenant is flagged by the unrelated withdrawal."""
    w = world
    h, tid = w["h"], w["tid"]
    with tenant_session(_owner(tid), engine=engine) as s:
        toy_id = s.scalar(
            select(m.DerivedObject.id).where(m.DerivedObject.node_id == w["model_node"])
        )
    model = new_model(client, h)
    mid = model["id"]
    plat = post(
        client,
        f"/v1/models/{mid}/versions",
        version_body([w["avg_node"]], weights={"derived_object_id": str(toy_id)}),
        h,
    )
    assert plat["weights_source"] == "platform"
    up = post(client, f"/v1/models/{mid}/versions", version_body([w["nodes"]["A0"]]), h)
    assert up["weights_source"] == "upload"
    # C is in neither lineage (the average covers A0, A1 and B)
    _withdraw(client, as_role, worker, w["C"]["subject_id"])
    v1 = client.get(f"/v1/models/{mid}/versions/1", headers=h).json()
    assert not v1["retrain_required"] and v1["taint"] == []
    assert _deploy(client, h, mid, 1).status_code == 201
    v2 = client.get(f"/v1/models/{mid}/versions/2", headers=h).json()
    assert v2["retrain_required"] and v2["deployments_blocked"]
    assert [f["reason"] for f in v2["taint"]] == [REASON]


def _owner(tid):
    from gov_helpers import principal  # noqa: PLC0415

    return principal(tid, "owner", pid="user-owner")


# ---------------------------------------------------------------- four-eyes for uploads
def test_upload_deploy_needs_an_approver_other_than_the_uploader(
    client, as_role, tree, engine, tenants
):
    uploader = as_role("owner", sub="uploader")
    node = feature_of(engine, tenants.a, tree["node_id"])
    model = new_model(client, uploader)
    mid = model["id"]
    post(client, f"/v1/models/{mid}/versions", version_body([node]), uploader)
    r = _deploy(client, uploader, mid)
    assert r.status_code == 403, r.text
    assert r.json()["code"] == vocab.R_UPLOAD_APPROVAL
    assert vocab.R_UPLOAD_APPROVAL in r.json()["reasons"]
    # the uploader's own approval does not count
    url = f"/v1/models/{mid}/versions/1/approvals"
    assert client.post(url, headers=uploader).status_code == 201
    assert _deploy(client, uploader, mid).status_code == 403
    _approve(client, as_role, mid, 1, "second-approver")
    r = _deploy(client, uploader, mid)
    assert r.status_code == 201 and r.json()["state"] == "approved", r.text


def test_upload_publish_needs_approvers_other_than_the_uploader(
    client, as_role, tree, engine, tenants
):
    uploader = as_role("owner", sub="uploader")
    publisher = as_role("owner", sub="publisher")
    node = feature_of(engine, tenants.a, tree["node_id"])
    model = new_model(client, uploader, privacy=True)
    mid = model["id"]
    post(client, f"/v1/models/{mid}/versions", version_body([node]), uploader)
    # the uploader + one other approver: two approvers other than the publisher, but only one
    # other than the uploader -> refused for an upload-sourced version
    assert (
        client.post(f"/v1/models/{mid}/versions/1/approvals", headers=uploader).status_code == 201
    )
    _approve(client, as_role, mid, 1, "approver-1")
    r = client.post(f"/v1/models/{mid}/versions/1/publish", headers=publisher)
    assert r.status_code == 403 and r.json()["code"] == "four_eyes_required", r.text
    _approve(client, as_role, mid, 1, "approver-2")
    r = client.post(f"/v1/models/{mid}/versions/1/publish", headers=publisher)
    assert r.status_code == 200 and r.json()["visibility"] == "published", r.text


# ---------------------------------------------------------------- pre-amendment manifests
def test_weights_source_falls_back_to_the_weights_object_for_old_manifests(
    client, as_role, world, engine
):
    """A manifest written before the amendment has no ``weights_source``: the weights object's
    ``params["source"]`` decides ("upload" -> upload, anything else -> platform)."""
    w = world
    h, tid = w["h"], w["tid"]
    with tenant_session(_owner(tid), engine=engine) as s:
        toy_id = s.scalar(
            select(m.DerivedObject.id).where(m.DerivedObject.node_id == w["model_node"])
        )
    model = new_model(client, h)
    mid = model["id"]
    body = version_body([w["avg_node"]], weights={"derived_object_id": str(toy_id)})
    assert post(client, f"/v1/models/{mid}/versions", body, h)["weights_source"] == "platform"
    body = version_body([w["nodes"]["A0"]])
    assert post(client, f"/v1/models/{mid}/versions", body, h)["weights_source"] == "upload"
    with tenant_session(_owner(tid), engine=engine) as s:
        rows = {
            v.version: v
            for v in s.scalars(select(m.ModelVersion).where(m.ModelVersion.model_id == mid))
        }
        plat, up = rows[1], rows[2]
        params = {
            o.id: o.params
            for o in s.scalars(
                select(m.DerivedObject).where(
                    m.DerivedObject.id.in_([plat.derived_object_id, up.derived_object_id])
                )
            )
        }
        assert (params[up.derived_object_id] or {}).get("source") == "upload"
        assert (params[plat.derived_object_id] or {}).get("source") != "upload"
        for version, want in ((plat, "platform"), (up, "upload")):
            assert svc.weights_source(s, version) == want  # stamped manifest
            # the same row as written before the amendment (transient: nothing is flushed)
            for manifest in (
                {k: v for k, v in version.manifest.items() if k != "weights_source"},
                {**version.manifest, "weights_source": "bogus"},
                None,
            ):
                old = m.ModelVersion(manifest=manifest, derived_object_id=version.derived_object_id)
                assert svc.weights_source(s, old) == want, (want, manifest and sorted(manifest))
        # a stamped value wins over the weights object
        stamped = m.ModelVersion(
            manifest={**up.manifest, "weights_source": "platform"},
            derived_object_id=up.derived_object_id,
        )
        assert svc.weights_source(s, stamped) == "platform"
