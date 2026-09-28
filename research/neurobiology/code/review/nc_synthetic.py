"""Reviewer check for N1 (b): do the NC1/NC2 negative controls behave as the prereg assumes on synthetic data?

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
Uses the harness's own run_split (read-only import, no modification) on synthetic FEATURE matrices (no EDFs):
  condition "nosignal": seizure windows have the same distribution as background (delta = 0)
  condition "signal":   seizure windows are shifted by +delta in every feature (like a power increase in all channels)
For each condition and for NC1 / NC2 it records the test window AUROC and the pooled event TP vs the circular-shift
chance null (N1 b criterion 2). A third arm "NC2-excl" is the reviewer's proposed corrected NC2: circular shift of the
labels AFTER removing the true ictal windows (+/- 60 s) from training (AUROC only; own fit with harness ZScore/LogRegL2).
Seeds: numpy SeedSequence(20261001, spawn_key=(99, ...)) -- reviewer streams, disjoint from the prereg streams.
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"
import json
import sys
import time

import numpy as np

sys.path.insert(0, r"C:\Users\mariu\neuro-company\research\neurobiology\code")
from nfharness.data import FileRecord  # noqa: E402
from nfharness.labels import LabelVault  # noqa: E402
from nfharness.model import LogRegL2, ZScore  # noqa: E402
from nfharness.pipeline import run_split  # noqa: E402
from nfharness.scoring import Scorer  # noqa: E402
from nfharness.splits import Split  # noqa: E402
from nfharness.stats import auroc  # noqa: E402

T, D, NTR, NTE = 1800, 24, 4, 4
OUT = r"C:\Users\mariu\neuro-company\research\neurobiology\code\review\nc_synthetic_out.json"


def rng(*k):
    return np.random.default_rng(np.random.SeedSequence(20261001, spawn_key=(99,) + k))


def make_dataset(seed, delta):
    g = rng(1, seed)
    recs, feats, ann = [], {}, {}
    for i in range(NTR + NTE):
        name = "syn%d_%02d.edf" % (seed, i)
        e = g.standard_normal((T - 1, D))
        x = np.empty_like(e)
        x[0] = e[0]
        for t in range(1, T - 1):                         # AR(1) background state, phi = 0.98
            x[t] = 0.98 * x[t - 1] + 0.2 * e[t]
        x += 0.5 * g.standard_normal((T - 1, D))
        ev = []
        if i >= 1:
            on = int(g.integers(200, T - 300)); ln = int(g.integers(40, 90))
            ev.append((on, on + ln))
            x[on:on + ln - 1] += delta                     # window i fully inside [on, on+ln) -> i in [on, on+ln-2]
        feats[name] = x.astype(np.float32)
        ann[name] = ev
        recs.append(FileRecord("syn%d" % seed, name, "", i * (T + 7.0), T))
    return recs, feats, ann


def nc2_excl_auroc(recs, feats, ann, g):
    """Corrected NC2: drop true ictal windows (+/- 60 s) from training, then circularly shift the remaining labels."""
    tr, te = recs[:NTR], recs[NTR:]
    Xs, ys = [], []
    for r in tr:
        m = np.zeros(T, np.int8)
        excl = np.zeros(T - 1, bool)
        for a, b in ann[r.name]:
            m[a:b] = 1
            excl[max(0, a - 60):b + 60] = True
        off = int(g.integers(600, T - 600 + 1))
        ms = np.roll(m, off)
        wl = (ms[:-1] & ms[1:]).astype(np.int8)
        keep = ~excl
        Xs.append(feats[r.name][keep]); ys.append(wl[keep])
    X, y = np.concatenate(Xs), np.concatenate(ys)
    if y.sum() == 0:
        return float("nan")
    z = ZScore().fit(X, {"x": np.arange(len(X))})
    lr = LogRegL2().fit(z.transform_training(X), y)
    yt, st = [], []
    for r in te:
        mt = np.zeros(T, np.int8)
        for a, b in ann[r.name]:
            mt[a:b] = 1
        yt.append(mt[:-1] & mt[1:])
        st.append(lr.predict_proba(z.transform_training(feats[r.name])))
    return auroc(np.concatenate(yt), np.concatenate(st))


def main():
    t0 = time.time()
    out = {}
    for cond, delta in (("nosignal", 0.0), ("signal", 3.0)):
        out[cond] = {}
        for mode in ("nc1_perm", "nc2_shift", "true"):
            aucs, obs, null = [], 0, np.zeros(1000, np.int64)
            gl = rng(2, 0 if mode == "nc1_perm" else 1 if mode == "nc2_shift" else 2, int(delta))
            gn = rng(3, int(delta))
            nrep = 1 if mode == "true" else 5
            for ds in range(3):
                recs, feats, ann = make_dataset(ds, delta)
                sp = Split("causal", recs[:NTR], recs[NTR:])
                vault = LabelVault(ann, {r.name: T for r in recs}, protected_files=sp.test_names, name="rev")
                for rep in range(nrep):
                    res = run_split(sp, feats, vault, [[r] for r in sp.train], label_mode=mode, rng=gl, purpose="review")
                    y = np.concatenate([res["ywin"][f] for f in sp.test_names])
                    s = np.concatenate([res["p"][f] for f in sp.test_names])
                    aucs.append(auroc(y, s))
                    obs += sum(v["tp"] for v in res["per_file"].values())
                    sc = Scorer(vault, "review-null")
                    for r in sp.test:
                        null += sc.shifted_tp(r.name, res["hyp"][r.name], gn.integers(0, T, 1000))
            out[cond][mode] = {"auroc_mean": float(np.nanmean(aucs)), "aurocs": [round(a, 3) for a in aucs],
                               "pooled_tp": int(obs), "n_ref": int(len(aucs) * NTE), "null_mean": float(null.mean()),
                               "null_p99": float(np.percentile(null, 99)), "crit2_pass": bool(obs <= np.percentile(null, 99))}
            print(cond, mode, out[cond][mode], flush=True)
        g = rng(4, int(delta))
        ex = []
        for ds in range(3):
            recs, feats, ann = make_dataset(ds, delta)
            ex += [nc2_excl_auroc(recs, feats, ann, g) for _ in range(5)]
        out[cond]["nc2_excl_ictal"] = {"auroc_mean": float(np.nanmean(ex)), "aurocs": [round(a, 3) for a in ex]}
        print(cond, "nc2_excl_ictal", out[cond]["nc2_excl_ictal"], flush=True)
    out["_wall_s"] = time.time() - t0
    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=1)


if __name__ == "__main__":
    main()
