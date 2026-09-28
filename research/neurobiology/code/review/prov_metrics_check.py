"""Reviewer checks: provenance (card hashes, code/prereg/input hashes, split hash, timing) + metric-function unit checks
+ NC1 tau-floor mechanism.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
Read-only with respect to the harness and results. Writes code\\review\\prov_metrics_out.json.
"""
import csv
import hashlib
import json
import os
import sys

import numpy as np
from scipy import stats as sst

ROOT = r"C:\Users\mariu\neuro-company\research\neurobiology"
CODE = os.path.join(ROOT, "code")
RES = os.path.join(ROOT, "results")
OUT = os.path.join(CODE, "review", "prov_metrics_out.json")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def card_hash_own(c):
    c = {k: v for k, v in c.items() if k not in ("runtime", "card_sha256_excl_runtime")}
    return hashlib.sha256(json.dumps(c, sort_keys=True, indent=1, allow_nan=False).encode()).hexdigest()


def provenance():
    out = {}
    cards = ["N2_run_card.json", "cards/chb01_card.json", "cards/chb03_card.json", "cards/chb10_card.json"]
    for tag, base in (("run1", RES), ("run2", os.path.join(RES, "rerun"))):
        out[tag] = {}
        for f in cards:
            c = json.load(open(os.path.join(base, *f.split("/"))))
            out[tag][f] = {"stored": c.get("card_sha256_excl_runtime"), "own_recomputed": card_hash_own(c)}
    out["rerun_identical"] = all(out["run1"][f]["own_recomputed"] == out["run2"][f]["own_recomputed"] for f in cards)
    out["stored_equals_recomputed"] = all(out[t][f]["stored"] == out[t][f]["own_recomputed"] for t in ("run1", "run2") for f in cards)
    rc = json.load(open(os.path.join(RES, "N2_run_card.json")))
    p = rc["provenance"]
    out["code_hash_mismatch_now_vs_run"] = {k: (v, sha(os.path.join(CODE, *k.split("/"))))
                                            for k, v in p["code_sha256"].items()
                                            if sha(os.path.join(CODE, *k.split("/"))) != v}
    out["prereg_hash_mismatch_now_vs_run"] = {k: v for k, v in p["prereg_sha256"].items()
                                              if sha(os.path.join(ROOT, "prereg", k)) != v}
    out["deviations_md_hash_run"] = p["deviations_sha256"]
    out["deviations_md_hash_now"] = sha(os.path.join(CODE, "DEVIATIONS.md"))
    # inputs: recompute all files vs manifest and PhysioNet SHA256SUMS
    ref = {}
    for line in open(os.path.join(ROOT, "data", "raw", "chbmit", "_meta", "SHA256SUMS.txt"), encoding="latin-1"):
        q = line.split()
        if len(q) == 2:
            ref[q[1]] = q[0]
    man = list(csv.DictReader(open(os.path.join(ROOT, "data", "manifests", "chbmit_manifest.csv"))))
    bad, n = [], 0
    for r in man:
        rel = r["file"]
        if rel.split("/")[0] not in ("chb01", "chb03", "chb10") or not rel.endswith((".edf", ".seizures", "-summary.txt")):
            continue
        n += 1
        h = sha(os.path.join(ROOT, "data", "raw", "chbmit", *rel.split("/")))
        if not (h == r["sha256"] == ref.get(rel) == p["input_sha256"].get(rel)):
            bad.append(rel)
    out["inputs_checked"] = n
    out["inputs_mismatch"] = bad
    rt = rc["runtime"]
    out["prereg_hashed_before_first_scorer_read_s"] = rt["first_test_label_read_unix"] - rt["prereg_hashed_at_unix"]
    out["split_hash_in_card"] = p["split_hash"]
    return out


def metric_units():
    g = np.random.default_rng(np.random.SeedSequence(20261001, spawn_key=(99, 11)))
    sys.path.insert(0, CODE)
    from nfharness import stats as H
    res = {"auroc_maxdiff": 0.0, "auprc_maxdiff": 0.0, "garwood_maxdiff": 0.0, "cp_maxdiff": 0.0}
    for _ in range(200):
        n = int(g.integers(20, 400))
        y = g.random(n) < g.uniform(0.02, 0.5)
        if y.sum() == 0 or y.sum() == n:
            continue
        s = np.round(g.standard_normal(n) + y * g.uniform(0, 2), 1)       # many ties
        u = sst.mannwhitneyu(s[y], s[~y]).statistic / (y.sum() * (~y).sum())
        res["auroc_maxdiff"] = max(res["auroc_maxdiff"], abs(u - H.auroc(y, s)))
        # brute-force AP: sum over distinct thresholds (desc) of (R_k - R_{k-1}) P_k
        ap, rprev = 0.0, 0.0
        for t in np.unique(s)[::-1]:
            sel = s >= t
            P, R = y[sel].mean(), y[sel].sum() / y.sum()
            ap += (R - rprev) * P
            rprev = R
        res["auprc_maxdiff"] = max(res["auprc_maxdiff"], abs(ap - H.auprc(y, s)))
    for k in range(0, 40):
        lo = 0.0 if k == 0 else sst.gamma.ppf(0.025, k)
        hi = sst.gamma.ppf(0.975, k + 1)
        a, b = H.garwood(k)
        res["garwood_maxdiff"] = max(res["garwood_maxdiff"], abs(a - lo), abs(b - hi))
    for n in range(1, 15):
        for k in range(0, n + 1):
            ci = sst.binomtest(k, n).proportion_ci(method="exact")
            a, b = H.clopper_pearson(k, n)
            res["cp_maxdiff"] = max(res["cp_maxdiff"], abs(a - ci.low), abs(b - ci.high))
    res["cp_4_of_4"] = H.clopper_pearson(4, 4)
    res["garwood_0_upper_per24h_chb01"] = 24 * H.garwood(0)[1] / 3.6458333
    # block bootstrap: exact-formula vs brute force on the same resample indices
    ys = [g.random(300) < 0.05 for _ in range(4)]
    ss = [g.standard_normal(300) + 1.5 * y for y in ys]
    B = 300
    g1 = np.random.default_rng(5)
    ci, _ = H.block_bootstrap_auroc(ys, ss, g1, B)
    g2 = np.random.default_rng(5)
    idx = g2.integers(0, 4, size=(B, 4))
    vals = []
    for row in idx:
        yy = np.concatenate([ys[i] for i in row]); sc = np.concatenate([ss[i] for i in row])
        if 0 < yy.sum() < yy.size:
            vals.append(H.auroc(yy, sc))
    res["block_boot_ci_formula"] = ci
    res["block_boot_ci_bruteforce"] = [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]
    return res


def nc1_tau_floor():
    """NC1 (D9): the training reference mask = permuted window labels -> scattered 1-s 'seizures'. Fraction of training
    time covered by merged (<90 s gap) reference events extended by [-30, +60): if ~1, every alarm is a TP on training,
    OOF FA = 0 for any tau, so tau* = 0.05 (grid floor) and the NC1 model alarms almost always on test."""
    g = np.random.default_rng(np.random.SeedSequence(20261001, spawn_key=(99, 12)))
    cfg = {"chb01": (25193, 104, 7), "chb03": (10797, 183, 3), "chb10": (21627, 167, 3)}   # windows, positives, files
    out = {}
    for s, (nw, npos, nf) in cfg.items():
        cov, allfp = [], []
        for _ in range(20):
            lab = np.zeros(nw, bool); lab[g.choice(nw, npos, replace=False)] = True
            T = nw // nf
            cfile = []
            fps = 0
            for f in range(nf):
                m = lab[f * T:(f + 1) * T]
                pos = np.flatnonzero(m)
                if pos.size == 0:
                    cfile.append(0.0); fps += 1; continue
                ev = [[pos[0], pos[0] + 1]]
                for p in pos[1:]:
                    if p - ev[-1][1] < 90:
                        ev[-1][1] = p + 1
                    else:
                        ev.append([p, p + 1])
                cover = np.zeros(T, bool)
                for a, b in ev:
                    cover[max(0, a - 30):b + 60] = True
                cfile.append(cover.mean())
                # always-alarm hypothesis split into 300-s events: FP = events not overlapping any extended ref
                for a in range(0, T, 300):
                    if not cover[a:min(T, a + 300)].any():
                        fps += 1
            cov.append(np.mean(cfile))
            allfp.append(24.0 * fps / (nw / 3600.0))
        out[s] = {"mean_fraction_of_training_time_inside_extended_ref": float(np.mean(cov)),
                  "always_alarm_train_FA_per_24h_mean": float(np.mean(allfp)),
                  "always_alarm_passes_FA<=12_fraction": float(np.mean(np.array(allfp) <= 12))}
    return out


if __name__ == "__main__":
    o = {"provenance": provenance(), "metric_units": metric_units(), "nc1_tau_floor": nc1_tau_floor()}
    with open(OUT, "w") as fh:
        json.dump(o, fh, indent=1, default=float)
    print(json.dumps(o, indent=1, default=float))
