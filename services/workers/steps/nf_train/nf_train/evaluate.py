"""Measure SISA against full retraining on the toy dataset (BUILD-GUIDE 6.4 acceptance: accuracy
relative to full retraining is measured and reported, not claimed in advance).

For each seed: train SISA (S shards x R slices) on ``n_train`` synthetic subjects, withdraw one
subject, retrain only its shard, and compare on ``n_test`` held-out subjects with

- the same SISA configuration trained from scratch without the subject (must be identical), and
- the monolithic decoder (one model, no shards) trained from scratch without the subject
  ("full retraining").

    python -m nf_train evaluate --seeds 0 1 2 3 4     (tools/synth on PYTHONPATH)
"""

from __future__ import annotations

from typing import Any

import numpy as np

from nf_train import decoder, sisa, toydata


def _xy(data: sisa.SubjectData) -> tuple[np.ndarray, np.ndarray]:
    hids = sorted(data)
    return (
        np.concatenate([data[h][0] for h in hids]),
        np.concatenate([data[h][1] for h in hids]),
    )


def run(
    seed: int,
    *,
    n_train: int = 48,
    n_test: int = 24,
    shards: int = 4,
    slices: int = 3,
    fit: decoder.FitParams | None = None,
) -> dict[str, Any]:
    fit = fit or decoder.FitParams()
    train = toydata.dataset(seed, n_train)
    test = toydata.dataset(seed, n_test, offset=n_train)
    xt, yt = _xy(test)
    cfg = sisa.SisaConfig(shards=shards, slices=slices, seed=seed, fit=fit)
    store = sisa.MemoryStore()
    full = sisa.train(cfg, train, store)
    gone = sorted(train)[seed % n_train]
    loads: list[list[str]] = []

    def load(hids: list[str]) -> sisa.SubjectData:
        loads.append(list(hids))
        return {h: train[h] for h in hids}

    audited = sisa.AuditedStore(store)
    after = sisa.retrain_without(full.manifest, [gone], load, audited, full.model)
    rest = {h: v for h, v in train.items() if h != gone}
    scratch = sisa.train(cfg, rest, sisa.MemoryStore())
    mono = sisa.train_monolithic(fit, rest)
    mono_before = sisa.train_monolithic(fit, train)
    k, r = full.manifest["assignment"][gone]
    return {
        "seed": seed,
        "config": cfg.doc(),
        "n_train_subjects": n_train,
        "n_test_subjects": n_test,
        "n_test_epochs": int(yt.size),
        "withdrawn": {"subject": gone, "shard": k, "slice": r},
        "accuracy": {
            "sisa_before": decoder.accuracy(full.model.predict(xt), yt),
            "sisa_after_shard_retrain": decoder.accuracy(after.model.predict(xt), yt),
            "sisa_full_retrain": decoder.accuracy(scratch.model.predict(xt), yt),
            "monolithic_before": decoder.accuracy((mono_before.proba(xt) >= 0.5).astype(int), yt),
            "monolithic_full_retrain": decoder.accuracy((mono.proba(xt) >= 0.5).astype(int), yt),
        },
        "sisa_retrain_equals_scratch": after.model.to_bytes() == scratch.model.to_bytes(),
        "checkpoint_audit": {
            "read": sorted({(e.shard, e.slice) for e in audited.log if e.op == "read"}),
            "written": sorted({(e.shard, e.slice) for e in audited.log if e.op == "write"}),
            "discarded": sorted({(e.shard, e.slice) for e in audited.log if e.op == "discard"}),
            "shards_touched": sorted(
                audited.shards("read") | audited.shards("write") | audited.shards("discard")
            ),
        },
        "subjects_loaded_for_retrain": len({h for batch in loads for h in batch}),
        "subjects_in_full_retrain": len(rest),
    }


def summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    keys = results[0]["accuracy"].keys()
    return {
        k: {
            "mean": round(float(np.mean([r["accuracy"][k] for r in results])), 4),
            "min": round(float(np.min([r["accuracy"][k] for r in results])), 4),
            "max": round(float(np.max([r["accuracy"][k] for r in results])), 4),
        }
        for k in keys
    }
