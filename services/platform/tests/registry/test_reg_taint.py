"""6.3 acceptance: consent taint and the retrain flow, in the M5 5.5 end-to-end scenario.

subject A -> 3 recordings -> runs -> a group average (A0, A1, B) -> a toy model, registered as
version 1. A withdraws; the DeletionJob (5.5) re-runs the average without A and flags the model:

- version 1 becomes ``retrain_required``; its approved deployment is ``blocked`` and new deployments
  are refused (tenant policy ``block_deployments_on_retrain``, default true);
- ``POST .../versions/1/retrain`` queues ``registry.retrain``; the worker trains version 2
  without A;
- version 2's manifest excludes A (hashed), lists only B, names version 1 as parent, and its
  provenance lineage reaches no recording of A (the proof); version 2 deploys;
- version 1 stays flagged and blocked.
"""

from __future__ import annotations

import uuid

import pytest
from gov_helpers import principal
from nf_platform.db import models as m
from nf_platform.db.context import tenant_session
from nf_platform.registry import manifest as mf
from nf_platform.registry import retrain as rt_mod
from nf_platform.registry import vocab
from reg_helpers import audit_rows, feature_of, new_model, post, version_body
from sqlalchemy import select, text

pytestmark = pytest.mark.postgres


def _deploy(client, h, model_id, version, **ctx):
    body = {
        "version": version,
        "context": {"jurisdiction": "US", "setting": "research", "purpose": "study", **ctx},
    }
    return client.post(f"/v1/models/{model_id}/deployments", json=body, headers=h)


def test_withdrawal_taints_blocks_and_retrain_excludes_the_subject(
    client, as_role, world, engine, worker, tenants
):
    w = world
    h, tid = w["h"], w["tid"]
    a_sid, b_sid = w["A"]["subject_id"], w["B"]["subject_id"]
    ha, hb = mf.subject_hash(tid, a_sid), mf.subject_hash(tid, b_sid)
    owner = principal(tid, "owner", pid="user-owner")
    with tenant_session(owner, engine=engine) as s:
        toy_id = s.scalar(
            select(m.DerivedObject.id).where(m.DerivedObject.node_id == w["model_node"])
        )
    model = new_model(client, h)
    mid = model["id"]
    v1 = post(
        client,
        f"/v1/models/{mid}/versions",
        version_body([w["avg_node"]], weights={"derived_object_id": str(toy_id)}),
        h,
    )
    assert v1["prov_node_id"] == str(w["model_node"])
    full1 = client.get(f"/v1/models/{mid}/versions/1?include_manifest=true", headers=h).json()
    assert set(full1["manifest"]["subjects"]) == {ha, hb}  # which versions contained A
    dep = _deploy(client, h, mid, 1)
    assert dep.status_code == 201 and dep.json()["state"] == "approved"

    # ---- withdrawal of A (5.5): the DeletionJob flags the model
    steward = as_role("data-steward")
    dj = client.post(f"/v1/subjects/{a_sid}/withdrawals", json={}, headers=steward).json()
    job = worker.run_once()
    assert job is not None and job.kind == "governance.deletion"
    assert client.get(f"/v1/deletion-jobs/{dj['id']}", headers=steward).json()["state"] == (
        "succeeded"
    )
    v1 = client.get(f"/v1/models/{mid}/versions/1", headers=h).json()
    assert v1["retrain_required"] and v1["deployments_blocked"]
    assert [f["deletion_job_id"] for f in v1["taint"]] == [dj["id"]]
    deps = client.get(f"/v1/models/{mid}/deployments", headers=h).json()
    assert [d["effective_state"] for d in deps] == ["blocked"]
    r = _deploy(client, h, mid, 1)
    assert r.status_code == 403 and r.json()["code"] == vocab.R_RETRAIN
    assert client.get(f"/v1/models/{mid}", headers=h).json()["retrain_required"] is True

    # ---- retrain without A on the queue
    r = client.post(f"/v1/models/{mid}/versions/1/retrain", json={}, headers=h)
    assert r.status_code == 202, r.text
    req = r.json()
    assert req["state"] == "queued" and req["n_excluded_subjects"] == 1 and req["recipe"] == "toy"
    again = client.post(f"/v1/models/{mid}/versions/1/retrain", json={}, headers=h).json()
    assert again["id"] == req["id"]  # one active retrain per version
    job = worker.run_once()
    assert job is not None and job.kind == rt_mod.JOB_KIND
    done = client.get(f"/v1/models/{mid}/retrains/{req['id']}", headers=h).json()
    assert done["state"] == "succeeded", done["error"]

    v2 = client.get(f"/v1/models/{mid}/versions/2?include_manifest=true", headers=h).json()
    assert v2["id"] == done["new_version_id"] and v2["parent_version"] == 1
    assert v2["manifest"]["excluded_subjects"] == [ha]
    assert v2["manifest"]["subjects"] == [hb]
    assert v2["manifest"]["parent_version"] == v1["id"]
    assert v2["retrain_required"] is False and v2["recipe"] == "toy"
    # the provenance proof: v2's lineage reaches B's recording and no recording of A
    g = client.get(f"/v1/models/{mid}/versions/2/lineage", headers=h).json()
    recs = {n["ref_id"] for n in g["nodes"] if n["type"] == "recording"}
    assert recs == {w["b_rec"]} and not recs & set(w["a_recs"])
    assert g["n_training_subjects"] == 1
    with tenant_session(owner, engine=engine) as s:
        st = s.get(m.ArtifactStatus, (uuid.UUID(tid), w["avg_node"]))
        new_obj = s.scalar(
            select(m.DerivedObject).where(m.DerivedObject.id == uuid.UUID(v2["derived_object_id"]))
        )
        assert new_obj.input_node_ids == [st.replaced_by]  # trained on the re-run average
    assert _deploy(client, h, mid, 2).status_code == 201

    # ---- the old version stays flagged and blocked
    v1 = client.get(f"/v1/models/{mid}/versions/1", headers=h).json()
    assert v1["retrain_required"] and v1["deployments_blocked"]
    assert _deploy(client, h, mid, 1).status_code == 403
    evs = audit_rows(engine, type="data.create", resource_type="model_retrain")
    assert any(e["resource_id"] == req["id"] and e["actor_id"] == rt_mod.SERVICE_ID for e in evs)


def _flag(engine, tid: str, node_id: str, block: bool) -> None:
    with engine.begin() as c:  # superuser: what the DeletionJob writes
        c.execute(
            text(
                "INSERT INTO model_flag (tenant_id, model_node_id, deletion_job_id, "
                "block_deployments) VALUES (:t, :n, :d, :b)"
            ),
            {"t": tid, "n": node_id, "d": str(uuid.uuid4()), "b": block},
        )


def test_tenant_policy_may_leave_deployments_open(client, as_role, tree, engine, tenants):
    """``block_deployments_on_retrain = false``: the version is flagged but still deployable;
    publication of a flagged version is refused."""
    h = as_role("owner")
    node = feature_of(engine, tenants.a, tree["node_id"])
    model = new_model(client, h, privacy=True)
    v = post(client, f"/v1/models/{model['id']}/versions", version_body([node]), h)
    _flag(engine, tenants.a, v["prov_node_id"], block=False)
    # AppSec M3: an upload-sourced version needs a second approver before it is deployed
    r = client.post(
        f"/v1/models/{model['id']}/versions/1/approvals",
        headers=as_role("data-steward", sub="second-approver"),
    )
    assert r.status_code == 201, r.text
    out = client.get(f"/v1/models/{model['id']}/versions/1", headers=h).json()
    assert out["retrain_required"] and not out["deployments_blocked"]
    assert _deploy(client, h, model["id"], 1).status_code == 201
    r = client.post(f"/v1/models/{model['id']}/versions/1/publish", headers=h)
    assert r.status_code == 409 and r.json()["code"] == vocab.R_RETRAIN


def test_retrain_needs_a_remaining_subject_and_a_known_recipe(
    client, as_role, tree, engine, tenants
):
    h = as_role("owner")
    node = feature_of(engine, tenants.a, tree["node_id"])
    model = new_model(client, h)
    post(client, f"/v1/models/{model['id']}/versions", version_body([node]), h)
    r = client.post(
        f"/v1/models/{model['id']}/versions/1/retrain", json={"recipe": "nope"}, headers=h
    )
    assert r.status_code == 422
    assert rt_mod.known_recipe("sisa")  # 6.4 recipe, resolved lazily from nf_train.platform
    # the only subject withdraws its training consent: nothing remains to retrain on
    r = client.post(
        f"/v1/subjects/{tree['subject_id']}/consents",
        json={"kind": "withdraw", "scopes": ["model_training"]},
        headers=h,
    )
    assert r.status_code == 201, r.text
    r = client.post(f"/v1/models/{model['id']}/versions/1/retrain", json={}, headers=h)
    assert r.status_code == 403  # SEC-146: the remaining subject lacks model_training
