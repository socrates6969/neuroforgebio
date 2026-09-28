"""5.5 acceptance (THE key M5 test) + SEC-034/034a/046/124.

subject A -> 3 recordings -> 2 pipeline runs -> 1 group average (with subject B) -> 1 toy model;
subject C is unrelated. Withdraw A, run the DeletionJob on the queue, then assert:

- A's objects are gone, and A's objects in the pre-withdrawal backup copy are unreadable
  (crypto-shred), including the old group average (its own key is destroyed);
- the group average is re-run without A (tenant policy ``rerun``) -- or tombstoned (``tombstone``);
- the model is flagged ``retrain_required``;
- the signed certificate lists every affected node and verifies offline; it names A only by the
  tenant's pseudonym (SEC-046);
- audit events exist for every phase;
- the unrelated subject C (and B's own data) is untouched;
- the job duration is measured against the 24 h target (BLUEPRINT §8.4).
"""

from __future__ import annotations

import io
import json
import shutil
import time
import uuid

import numpy as np
import pytest
from gov_helpers import (
    ALL_SCOPES,
    audit_rows,
    make_recording,
    make_subject,
    pass_pipeline,
    principal,
    publish,
    signal,
)
from nf_platform.db import models as m
from nf_platform.db.context import tenant_session
from nf_platform.governance import certificate, deletion, derived
from nf_platform.provenance import api as prov
from nf_platform.storage.keyring import SubjectKeyUnavailable
from nf_platform.storage.objects import LocalObjectStore
from nf_platform.storage.runtime import Storage
from sqlalchemy import select, text

pytestmark = pytest.mark.postgres


def _npy(b: bytes) -> np.ndarray:
    return np.lib.format.read_array(io.BytesIO(b), allow_pickle=False)


def _run(client, h, worker, ref: str, rid: str) -> str:
    r = client.post("/v1/runs", json={"pipeline": ref, "recording_id": rid}, headers=h)
    assert r.status_code == 202, r.text
    run_id = r.json()["id"]
    assert worker.run_once() is not None
    out = client.get(f"/v1/runs/{run_id}", headers=h).json()
    assert out["state"] == "succeeded", out["error"]
    return run_id


def _signal_node(engine, run_id: str) -> uuid.UUID:
    with engine.connect() as c:
        return c.execute(
            text(
                "SELECT prov_node_id FROM run_artifact WHERE run_id = :r AND name = 'signal.npy' "
                "AND visible_at IS NOT NULL"
            ),
            {"r": run_id},
        ).scalar_one()


@pytest.fixture
def world(client, as_role, tree, storage, engine, tenants, worker):
    """A (tree subject) with 3 recordings and 2 runs; B with 1 run; C unrelated with 1 run; a group
    average over A's two run outputs + B's; a toy model trained on the average; one export."""
    h = as_role("owner")
    tid = tenants.a
    # the tree's queued run would be claimed first: cancel it
    r = client.post(f"/v1/runs/{tree['run_id']}/cancel", headers=h)
    assert r.status_code == 202
    ref = publish(client, h, pass_pipeline())
    A = {"subject_id": tree["subject_id"], "session_id": tree["session_id"]}
    B = make_subject(client, h, tree["dataset_id"], "sub-B")
    C = make_subject(client, h, tree["dataset_id"], "sub-C")
    data = {}
    a_recs = []
    for i in range(3):
        data[f"A{i}"] = signal(10 + i)
        a_recs.append(
            make_recording(
                client,
                h,
                A["session_id"],
                storage=storage,
                engine=engine,
                tenant_id=tid,
                subject_id=A["subject_id"],
                data=data[f"A{i}"],
                label=f"A{i}",
            )
        )
    data["B"], data["C"] = signal(20), signal(30)
    b_rec = make_recording(
        client,
        h,
        B["session_id"],
        storage=storage,
        engine=engine,
        tenant_id=tid,
        subject_id=B["subject_id"],
        data=data["B"],
        label="B",
    )
    c_rec = make_recording(
        client,
        h,
        C["session_id"],
        storage=storage,
        engine=engine,
        tenant_id=tid,
        subject_id=C["subject_id"],
        data=data["C"],
        label="C",
    )
    runs = {
        "A0": _run(client, h, worker, ref, a_recs[0]),
        "A1": _run(client, h, worker, ref, a_recs[1]),
        "B": _run(client, h, worker, ref, b_rec),
        "C": _run(client, h, worker, ref, c_rec),
    }
    nodes = {k: _signal_node(engine, v) for k, v in runs.items()}
    owner = principal(tid, "owner", pid="user-owner")
    with tenant_session(owner, engine=engine) as s:
        avg = derived.create_group_average(
            s, storage, owner, [nodes["A0"], nodes["A1"], nodes["B"]]
        )
        model = derived.train_toy_model(s, storage, owner, [avg.node_id])
        # an export of A's first run output that already left the platform
        s.add(
            m.DataExport(
                tenant_id=uuid.UUID(tid),
                node_ids=[nodes["A0"]],
                subject_ids=[uuid.UUID(A["subject_id"])],
                destination="partner-lab",
                format="npy",
                exported_by="user-owner",
            )
        )
        avg_id, avg_node, model_node = avg.id, avg.node_id, model.node_id
    expected_avg = np.mean([data["A0"], data["A1"], data["B"]], axis=0)
    with tenant_session(owner, engine=engine) as s:
        row = s.scalar(select(m.DerivedObject).where(m.DerivedObject.id == avg_id))
        assert np.allclose(_npy(derived.read(storage, row)), expected_avg)
        # every node the withdrawal must reach (descendants of A's recordings)
        roots = [prov.find_node(s, "entity", "recording", r) for r in a_recs]
        affected = set()
        for rt in filter(None, roots):
            affected |= {n.id for n in prov.lineage(s, rt, "down", None).nodes}
    return {
        "h": h,
        "tid": tid,
        "A": A,
        "B": B,
        "C": C,
        "a_recs": a_recs,
        "b_rec": b_rec,
        "c_rec": c_rec,
        "runs": runs,
        "nodes": nodes,
        "avg_id": avg_id,
        "avg_node": avg_node,
        "model_node": model_node,
        "affected": affected,
        "data": data,
    }


def _backup(storage, tmp_path) -> Storage:
    """A copy of the object store taken BEFORE the withdrawal (e.g. a bucket replica/snapshot)."""
    src = storage.objects.root
    dst = tmp_path / "backup-objects"
    shutil.copytree(src, dst)
    return Storage(objects=LocalObjectStore(dst), keyring=storage.keyring)


def _subject_keys(storage, tid: str, sid: str) -> list[tuple[str, str]]:
    out = []
    for b in ("raw", "zarr"):
        out += [(b, k) for k in storage.objects.list(b, f"t/{tid}/s/{sid}/")]
    return out


def _artifact_keys(engine, run_ids) -> list[tuple[str, str]]:
    with engine.connect() as c:
        rows = c.execute(
            text("SELECT bucket, object_key FROM run_artifact WHERE run_id = ANY(:r)"),
            {"r": list(run_ids)},
        ).all()
    return [(r.bucket, r.object_key) for r in rows]


def test_withdrawal_propagates_shreds_and_certifies(
    client, as_role, world, storage, engine, worker, tmp_path, record_property
):
    w = world
    tid, a_sid = w["tid"], w["A"]["subject_id"]
    a_zarr = _subject_keys(storage, tid, a_sid)
    a_arts = _artifact_keys(engine, [w["runs"]["A0"], w["runs"]["A1"]])
    c_arts = _artifact_keys(engine, [w["runs"]["C"]])
    assert a_zarr and a_arts
    backup = _backup(storage, tmp_path)
    # the backup copy decrypts before the withdrawal
    b, k = a_zarr[0]
    storage.keyring.decrypt(tid, a_sid, f"{b}/{k}", 1, backup.objects.get(b, k))

    steward = as_role("data-steward")
    r = client.post(
        f"/v1/subjects/{a_sid}/withdrawals", json={"evidence_ref": "form-7"}, headers=steward
    )
    assert r.status_code == 202, r.text
    dj = r.json()
    assert dj["state"] == "queued" and dj["aggregate_policy"] == "rerun"
    # the policy denies A's data at once (consent withdrawn), before the job even ran
    url = f"/v1/recordings/{w['a_recs'][0]}/data?start=0&end=1"
    assert client.get(url, headers=w["h"]).status_code == 403
    again = client.post(f"/v1/subjects/{a_sid}/withdrawals", json={}, headers=steward)
    assert again.json()["id"] == dj["id"]  # one active job per subject

    t0 = time.perf_counter()
    job = worker.run_once()
    elapsed = time.perf_counter() - t0
    assert job is not None and job.kind == deletion.JOB_KIND
    out = client.get(f"/v1/deletion-jobs/{dj['id']}", headers=steward).json()
    assert out["state"] == "succeeded", out["error"]
    cert = out["certificate"]
    record_property("deletion_job_wall_s", round(elapsed, 3))
    record_property("deletion_job_certificate_duration_s", cert["duration_s"])
    print(
        f"\n[5.5 MEASUREMENT] DeletionJob: {elapsed:.3f} s wall (job body "
        f"{cert['duration_s']} s) for {len(cert['nodes'])} nodes; target {cert['target_s']} s"
    )
    assert elapsed < deletion.TARGET_S

    # 1. objects gone, backup copy unreadable (crypto-shred)
    assert _subject_keys(storage, tid, a_sid) == []
    for bucket, key in a_arts:
        assert not storage.objects.exists(bucket, key), key
    for bucket, key in a_zarr + a_arts:
        blob = backup.objects.get(bucket, key)
        with pytest.raises(SubjectKeyUnavailable):
            storage.keyring.decrypt(tid, a_sid, f"{bucket}/{key}", 1, blob)
    # SEC-034a: the shredded subject is tombstoned; nothing new is ever encrypted for it
    with pytest.raises(SubjectKeyUnavailable):
        storage.keyring.encrypt(tid, a_sid, "raw/t/x", 1, b"new data")
    assert client.get(url, headers=w["h"]).status_code in (403, 410)

    # 2. group average re-run without A (old object deleted, its key destroyed; backup unreadable)
    owner = principal(tid, "owner", pid="user-owner")
    with tenant_session(owner, engine=engine) as s:
        st = s.get(m.ArtifactStatus, (uuid.UUID(tid), w["avg_node"]))
        assert st.status == "superseded" and st.replaced_by is not None
        old = s.scalar(select(m.DerivedObject).where(m.DerivedObject.id == w["avg_id"]))
        assert old.key_state == "shredded" and old.wrapped_dek is None
        assert not storage.objects.exists(old.bucket, old.object_key)
        with pytest.raises(SubjectKeyUnavailable):
            derived.open_blob(storage, old, backup.objects.get(old.bucket, old.object_key))
        new = s.scalar(select(m.DerivedObject).where(m.DerivedObject.node_id == st.replaced_by))
        assert new.input_node_ids == [w["nodes"]["B"]]
        assert new.params["revision_of"] == str(w["avg_node"])
        assert np.allclose(_npy(derived.read(storage, new)), w["data"]["B"])
        # 3. model flagged
        flags = s.scalars(select(m.ModelFlag).where(m.ModelFlag.model_node_id == w["model_node"]))
        (flag,) = list(flags)
        assert flag.flag == "retrain_required" and flag.block_deployments
        assert str(flag.deletion_job_id) == dj["id"]

    # 4. certificate: every affected node, signed, verifiable offline, pseudonym only (SEC-046)
    listed = {uuid.UUID(n["node_id"]) for n in cert["nodes"]}
    assert w["affected"] <= listed
    assert {w["avg_node"], w["model_node"], w["nodes"]["A0"], w["nodes"]["A1"]} <= listed
    acts = {n["node_id"]: n["action"] for n in cert["nodes"]}
    assert "re-run without the subject" in acts[str(w["avg_node"])]
    assert acts[str(w["model_node"])].startswith("flagged retrain_required")
    assert cert["models_flagged"] == [str(w["model_node"])]
    assert [e["destination"] for e in cert["external_exports"]] == ["partner-lab"]
    assert cert["subject_pseudonym"] == "sub-01"
    assert cert["key_destruction"]["dek_versions_destroyed"] >= 1
    assert "unrecoverable_in_all_copies_after" in cert["key_destruction"]
    key = client.get("/v1/governance/certificate-key", headers=steward).json()
    assert certificate.verify(cert, key["public_key"])
    forged = json.loads(json.dumps(cert))
    forged["nodes"] = forged["nodes"][1:]
    assert not certificate.verify(forged, key["public_key"])
    blob = json.dumps(cert)
    for other in (a_sid, w["B"]["subject_id"], w["C"]["subject_id"], "sub-B", "sub-C"):
        assert other not in blob  # no subject identifiers beyond the pseudonym
    assert "not regulated" not in blob.lower()

    # 5. audit events for every phase
    phases = [
        e["details"].get("phase")
        for e in audit_rows(engine, type="governance.deletion", resource_id=a_sid)
    ]
    for p in (
        "requested",
        "started",
        "objects_deleted",
        "aggregates",
        "models_flagged",
        "key_shredded",
        "completed",
    ):
        assert p in phases, (p, phases)

    # 6. the unrelated subject C (and B's own data) untouched
    for sid, rec, arts in ((w["C"]["subject_id"], w["c_rec"], c_arts),):
        r = client.get(f"/v1/recordings/{rec}/data?start=0&end=1", headers=w["h"])
        assert r.status_code == 200, r.text
        for bucket, k in arts:
            storage.keyring.decrypt(tid, sid, f"{bucket}/{k}", 1, storage.objects.get(bucket, k))
    r = client.get(f"/v1/recordings/{w['b_rec']}/data?start=0&end=1", headers=w["h"])
    assert r.status_code == 200
    cons = client.get(f"/v1/subjects/{a_sid}/consents", headers=steward).json()
    assert cons["withdrawn"] and cons["current_scopes"] == []
    assert client.get(f"/v1/subjects/{w['C']['subject_id']}/consents", headers=steward).json()[
        "current_scopes"
    ] == sorted(ALL_SCOPES)


def test_tombstone_policy(client, as_role, world, storage, engine, worker):
    w = world
    r = client.put(
        "/v1/governance/tenant-policy",
        json={"aggregate_on_withdrawal": "tombstone"},
        headers=as_role("admin"),
    )
    assert r.status_code == 200, r.text
    r = client.post(
        f"/v1/subjects/{w['A']['subject_id']}/withdrawals", json={}, headers=as_role("data-steward")
    )
    assert r.status_code == 202 and r.json()["aggregate_policy"] == "tombstone"
    assert worker.run_once() is not None
    owner = principal(w["tid"], "owner", pid="user-owner")
    with tenant_session(owner, engine=engine) as s:
        st = s.get(m.ArtifactStatus, (uuid.UUID(w["tid"]), w["avg_node"]))
        assert st.status == "tombstoned" and st.replaced_by is None
        assert (
            s.scalar(select(m.DerivedObject).where(m.DerivedObject.id == w["avg_id"])).key_state
            == "shredded"
        )
        # nothing new was derived
        assert (
            s.scalar(
                select(m.DerivedObject).where(
                    m.DerivedObject.kind == "group_average", m.DerivedObject.key_state == "active"
                )
            )
            is None
        )


def test_restore_drill_reapplies_shreds(client, as_role, world, storage, engine, worker):
    """SEC-124: a DB restore from before the withdrawal brings the wrapped DEK rows back; the
    restore procedure re-applies the WORM shred ledger before serving."""
    w = world
    tid, sid = w["tid"], w["A"]["subject_id"]
    with engine.connect() as c:
        snap = [
            dict(r._mapping)
            for r in c.execute(text("SELECT * FROM subject_key WHERE subject_id = :s"), {"s": sid})
        ]
        dsnap = c.execute(
            text("SELECT id, wrapped_dek FROM derived_object WHERE id = :i"), {"i": w["avg_id"]}
        ).first()
    assert snap
    a_key = _artifact_keys(engine, [w["runs"]["A0"]])[0]
    blob = storage.objects.get(*a_key)  # the backup copy of one of A's artifacts
    client.post(f"/v1/subjects/{sid}/withdrawals", json={}, headers=as_role("data-steward"))
    assert worker.run_once() is not None
    # "restore": the old key rows come back (as a pre-shred DB backup would). A restore is a
    # physical/replica-mode load, so the SEC-034a tombstone trigger (0012m6_key_tombstone), which
    # refuses to un-shred a row in normal operation, does not fire (superuser-only setting).
    with engine.begin() as c:
        c.execute(text("SET LOCAL session_replication_role = replica"))
        for row in snap:
            c.execute(
                text(
                    "UPDATE subject_key SET wrapped_dek = :w, state = :st, shredded_at = NULL "
                    "WHERE tenant_id = :t AND subject_id = :s AND dek_version = :v"
                ),
                {
                    "w": row["wrapped_dek"],
                    "st": row["state"],
                    "t": tid,
                    "s": sid,
                    "v": row["dek_version"],
                },
            )
        c.execute(
            text(
                "UPDATE derived_object SET wrapped_dek = :w, key_state = 'active', "
                "shredded_at = NULL WHERE id = :i"
            ),
            {"w": dsnap.wrapped_dek, "i": w["avg_id"]},
        )
    assert storage.keyring._ks.get_wrapped(tid, sid) is not None  # the resurrection risk
    assert storage.keyring.decrypt(tid, sid, f"{a_key[0]}/{a_key[1]}", 1, blob)
    n = deletion.reapply_shreds(storage, engine, [tid])
    assert n >= 2
    assert storage.keyring._ks.get_wrapped(tid, sid) is None
    with pytest.raises(SubjectKeyUnavailable):
        storage.keyring.decrypt(tid, sid, f"{a_key[0]}/{a_key[1]}", 1, blob)
    with engine.connect() as c:
        assert (
            c.execute(
                text("SELECT key_state FROM derived_object WHERE id = :i"), {"i": w["avg_id"]}
            ).scalar_one()
            == "shredded"
        )
