"""6.4 SISA core (pure NumPy, no database): determinism, subject-level assignment, the
one-shard retrain with its checkpoint audit, and retrain == training from scratch without the
subject. The accuracy comparison against full retraining is MEASURED here (and printed with
``-s``); the only assertion on it is that it was computed, not that it meets a number."""

from __future__ import annotations

import json

import numpy as np
import pytest
from nf_train import decoder, evaluate, sisa, toydata

FIT = decoder.FitParams(iterations=60)


@pytest.fixture(scope="module")
def data():
    return toydata.dataset(3, 24)


def test_sisa_toydata_is_deterministic_and_band_power_shaped():
    a = toydata.subject(1, 2)
    b = toydata.subject(1, 2)
    assert np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1])
    x, y = a
    n_ep = toydata.DURATION_S // toydata.EPOCH_S
    assert x.shape == (2 * n_ep, toydata.N_CHANNELS * len(toydata.BANDS))
    assert sorted(set(y.tolist())) == [0, 1]
    xs, ys = toydata.decode(toydata.encode(x, y))
    assert np.array_equal(ys, y) and np.allclose(xs, x, atol=1e-3)


def test_sisa_assignment_is_per_subject_and_independent_of_others():
    cfg = sisa.SisaConfig(shards=5, slices=4, seed=9)
    one = sisa.assign("abc", cfg)
    assert one == sisa.assign("abc", cfg)
    assert 0 <= one[0] < 5 and 0 <= one[1] < 4
    # a different seed reshuffles
    others = {sisa.assign(f"s{i}", sisa.SisaConfig(shards=5, slices=4, seed=10)) for i in range(40)}
    assert len(others) > 5
    with pytest.raises(sisa.SisaError):
        sisa.SisaConfig(shards=0)


def test_sisa_training_is_deterministic_by_seed(data):
    cfg = sisa.SisaConfig(shards=3, slices=2, seed=4, fit=FIT)
    a = sisa.train(cfg, data, sisa.MemoryStore())
    b = sisa.train(cfg, data, sisa.MemoryStore())
    assert a.model.to_bytes() == b.model.to_bytes()
    assert a.manifest == b.manifest
    c = sisa.train(sisa.SisaConfig(shards=3, slices=2, seed=5, fit=FIT), data, sisa.MemoryStore())
    assert c.manifest["assignment"] != a.manifest["assignment"]
    # manifest: every (hashed) subject -> [shard, slice]; one checkpoint per (shard, slice)
    assert set(a.manifest["assignment"]) == set(data)
    assert len(a.manifest["checkpoints"]) == 3 * 2
    assert sisa.SisaModel.from_doc(json.loads(a.model.to_bytes())).to_bytes() == a.model.to_bytes()


@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_sisa_withdrawal_retrains_only_one_shard_from_the_checkpoint_before(data, seed):
    cfg = sisa.SisaConfig(shards=4, slices=3, seed=seed, fit=FIT)
    store = sisa.MemoryStore()
    full = sisa.train(cfg, data, store)
    gone = sorted(data)[seed * 5 % len(data)]
    k, r0 = full.manifest["assignment"][gone]
    asked: list[str] = []

    def load(hids):
        asked.extend(hids)
        return {h: data[h] for h in hids}

    audited = sisa.AuditedStore(store)
    after = sisa.retrain_without(full.manifest, [gone], load, audited, full.model)

    # checkpoint audit: exactly one shard is touched ...
    reads = {(e.shard, e.slice) for e in audited.log if e.op == "read"}
    writes = {(e.shard, e.slice) for e in audited.log if e.op == "write"}
    discards = {(e.shard, e.slice) for e in audited.log if e.op == "discard"}
    assert audited.shards("read") | audited.shards("write") | audited.shards("discard") == {k}
    # ... it restarts from the last checkpoint BEFORE the subject's slice ...
    assert reads == ({(k, r0 - 1)} if r0 > 0 else set())
    # ... and rewrites (and destroys the old copies of) exactly the checkpoints that contained it
    assert writes == discards == {(k, r) for r in range(r0, cfg.slices)}
    assert after.retrained_shards == [k]
    # the withdrawn subject's data is never loaded; only its shard-mates are
    assert gone not in asked
    assert {full.manifest["assignment"][h][0] for h in asked} <= {k}
    # the other shards' constituents are the very same objects
    for j, (before_m, after_m) in enumerate(
        zip(full.model.members, after.model.members, strict=True)
    ):
        if j != k:
            assert after_m is before_m
    # the new manifest drops the subject and records the withdrawal
    assert gone not in after.manifest["assignment"] and after.manifest["withdrawn"] == [gone]
    for key, ref in after.manifest["checkpoints"].items():
        kk, rr = map(int, key.split("/"))
        if kk == k and rr >= r0:
            assert gone not in json.loads(store.get(ref))["subjects"]
        else:
            assert ref == full.manifest["checkpoints"][key]
    if r0 > 0:  # the checkpoint the retrain started from never contained the subject
        start = json.loads(store.get(full.manifest["checkpoints"][f"{k}/{r0 - 1}"]))
        assert gone not in start["subjects"]
    # superseded checkpoints are no longer readable
    with pytest.raises(sisa.SisaError):
        store.get(full.manifest["checkpoints"][f"{k}/{cfg.slices - 1}"])

    # retrain == SISA trained from scratch without the subject (bit-identical)
    rest = {h: v for h, v in data.items() if h != gone}
    scratch = sisa.train(cfg, rest, sisa.MemoryStore())
    assert after.model.to_bytes() == scratch.model.to_bytes()
    assert after.manifest["checkpoints"] == scratch.manifest["checkpoints"]


def test_sisa_two_withdrawals_in_one_shard_and_unknown_subject(data):
    cfg = sisa.SisaConfig(shards=2, slices=3, seed=1, fit=FIT)
    full = sisa.train(cfg, data, sisa.MemoryStore())
    by_shard: dict[int, list[str]] = {}
    for h, (k, _r) in full.manifest["assignment"].items():
        by_shard.setdefault(k, []).append(h)
    two = sorted(by_shard[0])[:2]
    store = sisa.MemoryStore()
    full = sisa.train(cfg, data, store)
    audited = sisa.AuditedStore(store)
    after = sisa.retrain_without(
        full.manifest, two, lambda hs: {h: data[h] for h in hs}, audited, full.model
    )
    assert after.retrained_shards == [0]
    r0 = min(full.manifest["assignment"][h][1] for h in two)
    assert {e.slice for e in audited.log if e.op == "write"} == set(range(r0, cfg.slices))
    with pytest.raises(sisa.SisaError, match="not in the training manifest"):
        sisa.retrain_without(full.manifest, ["nope"], lambda hs: {}, store, full.model)


def test_sisa_accuracy_vs_full_retraining_is_measured(capsys):
    """Measured, not claimed: the numbers are printed and go into the done-note / docs."""
    res = [evaluate.run(s, n_train=24, n_test=12, shards=3, slices=2, fit=FIT) for s in (0, 1)]
    for r in res:
        assert r["sisa_retrain_equals_scratch"] is True
        assert len(r["checkpoint_audit"]["shards_touched"]) == 1
        for v in r["accuracy"].values():
            assert 0.0 <= v <= 1.0
    with capsys.disabled():
        print("\nSISA measured:", json.dumps(evaluate.summary(res)))
