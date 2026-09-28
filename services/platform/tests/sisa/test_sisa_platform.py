"""6.4 acceptance on the platform: SISA checkpoints are encrypted derived objects with provenance;
after a consent withdrawal (the M5 DeletionJob) the retrain touches only the withdrawn subject's
shard. Checkpoint audit: every checkpoint of the other shards is byte-identical in the object store,
keeps its row, key and provenance node, and no new checkpoint is written for those shards; the
superseded checkpoints of the affected shard are crypto-shredded and marked ``superseded``.

Synthetic data only (``nf_train.toydata``). Not certified unlearning (docs/features/sisa.md).
"""

from __future__ import annotations

import uuid

import numpy as np
import pytest
from gov_helpers import principal
from nf_platform.db import models as m
from nf_platform.db.context import tenant_session
from nf_platform.governance import deletion
from nf_platform.provenance import api as prov
from nf_platform.storage.keyring import SubjectKeyUnavailable
from nf_train import decoder, sisa, toydata
from nf_train import platform as sp
from sqlalchemy import select

pytestmark = pytest.mark.postgres

CFG = sisa.SisaConfig(shards=3, slices=2, seed=5, fit=decoder.FitParams(iterations=40))


def _checkpoints(s) -> list[m.DerivedObject]:
    rows = s.scalars(select(m.DerivedObject)).all()
    return [r for r in rows if r.params.get("role") == sp.CHECKPOINT_ROLE]


def test_sisa_platform_withdrawal_retrains_only_one_shard(
    client, as_role, world, storage, engine, worker
):
    tid, subs = world["tid"], world["subjects"]
    owner = principal(tid, "owner", pid="user-owner")
    nodes = [v["node"] for v in subs.values()]
    with tenant_session(owner, engine=engine) as s:
        model = sp.train_sisa(s, storage, owner, nodes, CFG)
        model_id, model_node = model.id, model.node_id
        man = model.params["sisa"]
        tm = sp.manifest_for(model)
        # the registry manifest: exactly the model's inputs, shard keys = registry subject hashes
        assert set(tm.input_node_ids) == set(nodes) and tm.recipe == "sisa"
        assert set(tm.shards) == set(subs) and set(man["assignment"]) == set(subs)
        # every (shard, slice) checkpoint is an encrypted derived object with a provenance node
        cps = _checkpoints(s)
        assert len(cps) == CFG.shards * CFG.slices
        for r in cps:
            assert r.key_state == "active" and r.node_id is not None and r.bucket == "models"
            assert storage.objects.get(r.bucket, r.object_key)[:4] == b"NFD1"
            assert prov.get_node(s, r.node_id).type == sp.CHECKPOINT_TYPE
        assert b"sisa-checkpoint" not in storage.objects.get(cps[0].bucket, cps[0].object_key)

    # the withdrawn subject: prefer one in the last slice of a shard (a checkpoint is then read)
    occupied = {int(kr[0]) for kr in man["assignment"].values()}
    assert len(occupied) >= 2, "the fixture must populate at least two shards"
    gone = sorted(man["assignment"], key=lambda h: (-man["assignment"][h][1], h))[0]
    k, r0 = man["assignment"][gone]

    with tenant_session(owner, engine=engine) as s:
        before = {
            (int(r.params["shard"]), int(r.params["slice"])): {
                "id": r.id,
                "sha256": r.sha256,
                "node": r.node_id,
                "blob": storage.objects.get(r.bucket, r.object_key),
            }
            for r in _checkpoints(s)
        }

    # withdraw (M5): the DeletionJob marks the subject's checkpoints stale and flags the model
    steward = as_role("data-steward")
    sid = subs[gone]["subject_id"]
    r = client.post(f"/v1/subjects/{sid}/withdrawals", json={}, headers=steward)
    assert r.status_code == 202, r.text
    job = worker.run_once()
    assert job is not None and job.kind == deletion.JOB_KIND
    with tenant_session(owner, engine=engine) as s:
        stale = {st.node_id for st in s.scalars(select(m.ArtifactStatus)) if st.status == "stale"}
        want_stale = {v["node"] for (kk, rr), v in before.items() if kk == k and rr >= r0}
        assert want_stale <= stale
        assert not ({v["node"] for (kk, _), v in before.items() if kk != k} & stale)
        assert not ({v["node"] for (kk, rr), v in before.items() if kk == k and rr < r0} & stale)
        flags = s.scalars(select(m.ModelFlag).where(m.ModelFlag.model_node_id == model_node))
        assert len(list(flags)) == 1

    # retrain without the subject (what the registry's "sisa" recipe runs)
    reads: list[uuid.UUID] = []
    orig = sp.derived.read_node

    def spy(session, st, node_id):
        reads.append(node_id)
        return orig(session, st, node_id)

    sp.derived.read_node = spy
    try:
        with tenant_session(owner, engine=engine) as s:
            parent = s.scalar(select(m.DerivedObject).where(m.DerivedObject.id == model_id))
            new, audit_doc = sp.retrain_without(s, storage, owner, parent, {gone})
            new_id, new_node = new.id, new.node_id
            new_man = new.params["sisa"]
            new_excluded = sp.manifest_for(new).excluded_subject_hashes
    finally:
        sp.derived.read_node = orig

    # checkpoint audit: only shard k was read / written / discarded
    assert audit_doc["shards_retrained"] == [k]
    touched = {e[0] for key in ("read", "written", "discarded") for e in audit_doc[key]}
    assert touched == {k}
    assert audit_doc["written"] == [[k, r] for r in range(r0, CFG.slices)]
    assert audit_doc["read"] == ([[k, r0 - 1]] if r0 > 0 else [])
    # the withdrawn subject's data was never loaded; only shard k's remaining subjects were
    shard_k = {h for h, kr in man["assignment"].items() if kr[0] == k and h != gone}
    assert subs[gone]["node"] not in reads
    assert set(reads) == {subs[h]["node"] for h in shard_k}

    with tenant_session(owner, engine=engine) as s:
        rows = _checkpoints(s)
        by_id = {r.id: r for r in rows}
        for (kk, rr), b in before.items():
            row = by_id[b["id"]]
            if kk != k or rr < r0:
                # unaffected: same row, same bytes in the object store, key intact, not superseded
                assert row.key_state == "active" and row.sha256 == b["sha256"]
                assert storage.objects.get(row.bucket, row.object_key) == b["blob"]
                assert s.get(m.ArtifactStatus, (uuid.UUID(tid), b["node"])) is None
            else:
                # superseded: data key destroyed, object deleted, status + replacement recorded
                assert row.key_state == "shredded" and row.wrapped_dek is None
                st = s.get(m.ArtifactStatus, (uuid.UUID(tid), b["node"]))
                assert st.status == "superseded" and st.replaced_by is not None
                assert storage.objects.get(
                    "audit", f"shred-ledger/{tid}/derived-{row.id}.json"
                ).startswith(b"{")
        # not rewritten: no new checkpoint rows for the unaffected shards
        new_rows = [r for r in rows if r.id not in {b["id"] for b in before.values()}]
        assert sorted((int(r.params["shard"]), int(r.params["slice"])) for r in new_rows) == [
            (k, r) for r in range(r0, CFG.slices)
        ]
        # the new manifest points at the kept checkpoints for the other shards
        for (kk, rr), b in before.items():
            if kk != k or rr < r0:
                assert new_man["checkpoints"][f"{kk}/{rr}"] == str(b["id"])
        assert gone not in new_man["assignment"] and new_man["withdrawn"] == [gone]
        assert new_excluded == (gone,)
        # provenance: the new model is not a descendant of the withdrawn subject's recording
        rec_node = prov.find_node(s, "entity", "recording", subs[gone]["recording_id"])
        down = {n.id for n in prov.lineage(s, rec_node, "down", None).nodes}
        assert model_node in down and new_node not in down
        new_row = s.scalar(select(m.DerivedObject).where(m.DerivedObject.id == new_id))
        got = sp.load_model(storage, new_row)
        # what the platform reads for the remaining subjects (the run output of each recording)
        rest = {}
        for h, v in subs.items():
            if h != gone:
                arr = sp._npy(orig(s, storage, v["node"]))
                assert arr.shape == (len(v["xy"][0][0]) + 1, len(v["xy"][1]))
                rest[h] = toydata.decode(arr, sp.DEFAULT_SCALE)
                assert np.array_equal(rest[h][1], v["xy"][1])  # labels survive the pipeline
                assert np.allclose(rest[h][0], v["xy"][0], atol=1e-3)

    # the platform retrain equals SISA trained from scratch without the subject (pure core)
    scratch = sisa.train(CFG, rest, sisa.MemoryStore())
    assert got.to_bytes() == scratch.model.to_bytes()


def test_sisa_platform_superseded_checkpoint_is_unreadable(world, storage, engine):
    tid, subs = world["tid"], world["subjects"]
    owner = principal(tid, "owner", pid="user-owner")
    with tenant_session(owner, engine=engine) as s:
        model = sp.train_sisa(s, storage, owner, [v["node"] for v in subs.values()], CFG)
        gone = sorted(model.params["sisa"]["assignment"])[0]
        k, r0 = model.params["sisa"]["assignment"][gone]
        old_ref = model.params["sisa"]["checkpoints"][f"{k}/{r0}"]
        sp.retrain_without(s, storage, owner, model, {gone})
        row = s.scalar(select(m.DerivedObject).where(m.DerivedObject.id == uuid.UUID(old_ref)))
        with pytest.raises(SubjectKeyUnavailable):
            sp.derived.open_blob(storage, row, b"NFD1" + b"\0" * 40)
        with pytest.raises(sp.SisaPlatformError):
            sp.retrain_without(s, storage, owner, model, {"not-a-subject"})


def test_sisa_platform_rejects_multi_subject_inputs(world, storage, engine):
    tid = world["tid"]
    owner = principal(tid, "owner", pid="user-owner")
    nodes = [v["node"] for v in world["subjects"].values()][:2]
    with tenant_session(owner, engine=engine) as s:
        avg = sp.derived.create_group_average(s, storage, owner, nodes)
        with pytest.raises(sp.SisaPlatformError, match="single-subject"):
            sp.train_sisa(s, storage, owner, [avg.node_id], CFG)


def test_sisa_platform_training_is_policy_checked(client, as_role, world, storage, engine):
    """SEC-146: a subject without model_training consent blocks SISA training."""
    from nf_platform.governance.policy import PolicyDenied

    tid, subs = world["tid"], world["subjects"]
    owner = principal(tid, "owner", pid="user-owner")
    hid, v = sorted(subs.items())[0]
    r = client.post(
        f"/v1/subjects/{v['subject_id']}/withdrawals", json={}, headers=as_role("data-steward")
    )
    assert r.status_code == 202
    with tenant_session(owner, engine=engine) as s, pytest.raises(PolicyDenied):
        sp.train_sisa(s, storage, owner, [x["node"] for x in subs.values()], CFG)
    assert np.isfinite(v["xy"][0]).all()
