"""Reviewer's INDEPENDENT recomputation of the N3 locked-N2-model numbers on chb23 / chb24 (+ an independent C3' exact null).

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
Imports NOTHING from nfharness, edf_reader, run_n2, n1b or n3. Uses the reviewer's own N2 re-implementation in
code\\review\\indep_n2.py (own EDF reader, features, z-score, Newton-IRLS logistic regression, tau scan, 4-of-5, AUROC via
Mann-Whitney, timescoring 0.0.7 directly AND an own any-overlap scorer, Garwood via gamma quantiles).
The split is written out here from prereg\\N3 §2.2 and checked against the prereg S7 hash.
C3': exact random-alarm null by enumerating EVERY circular offset of each test file's hypothesis mask (np.roll), own
scorer, joint (TP, FP) convolution over files, exact Fractions -> mu*, sigma*, q95, P(F1 > q95) = a*.
Writes code\\review\\n3_indep_n2_out.json.
"""
import hashlib
import json
import math
import os
import sys
import time
from fractions import Fraction

import numpy as np
from scipy import stats as sst

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import indep_n2 as I  # noqa: E402  (reviewer code only)

RAW = I.RAW
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "n3_indep_n2_out.json")
SPLIT_TXT = ("chb23;train=chb23_06.edf,chb23_08.edf;test=chb23_09.edf\n"
             "chb24;train=chb24_01.edf,chb24_03.edf;test=chb24_04.edf,chb24_06.edf")
assert hashlib.sha256(SPLIT_TXT.encode()).hexdigest() == "9320fa73c5e52ce449f7257f47dda5fce87a25b53d812f51dbf6b21bc0397a19"
SPLIT = {}
for line in SPLIT_TXT.split("\n"):
    s, tr, te = line.split(";")
    SPLIT[s] = (tr[6:].split(","), te[5:].split(","))


def garwood_count(k):
    lo = 0.0 if k == 0 else sst.chi2.ppf(0.025, 2 * k) / 2.0
    hi = sst.chi2.ppf(0.975, 2 * k + 2) / 2.0
    return lo, hi


def fp_grid(H):
    meet = int(math.floor(H))
    inc = max(k for k in range(200) if garwood_count(k)[0] <= H)
    return meet, inc


def rule(tp, fp, H):
    meet, inc = fp_grid(H)
    if tp <= 1 or fp > inc:
        return "FAIL"
    if tp >= 3 and fp <= meet:
        return "PASS"
    return "INCONCLUSIVE"


def offsets_dist(ref_ev, hyp_mask):
    """ref_ev = reference MASK; {(tp, fp): count} over all T circular offsets of the hypothesis mask."""
    T = hyp_mask.size
    d = {}
    for k in range(T):
        tp, fp, _ = I.own_score(ref_ev, np.roll(hyp_mask, k))
        d[(tp, fp)] = d.get((tp, fp), 0) + 1
    return d, T


def main():
    t0 = time.time()
    res = {}
    c3_files = []
    for s in ("chb23", "chb24"):
        tr, te = SPLIT[s]
        ann = I.parse_summary(os.path.join(RAW, s, "%s-summary.txt" % s))
        F, T, ST = {}, {}, {}
        for f in tr + te:
            ST[f], T[f], F[f] = I.features(os.path.join(RAW, s, f))
        t_first = min(ST.values())
        tabs = {f: (ST[f] - t_first).total_seconds() for f in F}
        order_by_header = sorted(F, key=lambda f: tabs[f])
        causal_ok = max(tabs[f] + T[f] for f in tr) <= min(tabs[f] for f in te)
        keep = {}
        for f in tr:
            ends = tabs[f] + np.arange(T[f] - 1) + 2
            k = np.ones(T[f] - 1, bool)
            for g in te:
                k &= ~((ends > tabs[g] - 10) & (tabs[f] + np.arange(T[f] - 1) < tabs[g] + T[g] + 10))
            keep[f] = np.flatnonzero(k)
        ytr = {f: I.win_labels(I.ref_mask(ann[f], T[f])) for f in tr}
        oof = {}
        for h in tr:
            others = [f for f in tr if f != h]
            X = np.vstack([F[f][keep[f]] for f in others]); y = np.concatenate([ytr[f][keep[f]] for f in others])
            oof[h] = I.fit_predict(X, y, [F[h]])[0]
        Htr = sum(T[f] for f in tr) / 3600.0
        tau, curve = 0.99, []
        for tt in I.TAUS:
            fp = sum(I.ts_score(I.ref_mask(ann[f], T[f]), I.hyp_mask(oof[f], tt, T[f]))[1] for f in tr)
            curve.append((tt, 24.0 * fp / Htr))
            if 24.0 * fp / Htr <= 12.0:
                tau = tt
                break
        X = np.vstack([F[f][keep[f]] for f in tr]); y = np.concatenate([ytr[f][keep[f]] for f in tr])
        P = dict(zip(te, I.fit_predict(X, y, [F[f] for f in te])))
        TP = FP = NR = TPo = FPo = 0
        hyps = {}
        for f in te:
            r = I.ref_mask(ann[f], T[f]); hm = I.hyp_mask(P[f], tau, T[f])
            a = I.ts_score(r, hm); b = I.own_score(r, hm)
            TP += a[0]; FP += a[1]; NR += a[2]; TPo += b[0]; FPo += b[1]
            hyps[f] = {"T": T[f], "hyp_events": I.events(hm), "ref_events": ann[f]}
            c3_files.append((f, r, hm))
        H = sum(T[f] for f in te) / 3600.0
        yw = np.concatenate([I.win_labels(I.ref_mask(ann[f], T[f])) for f in te])
        sc = np.concatenate([P[f] for f in te])
        U = sst.mannwhitneyu(sc[yw == 1], sc[yw == 0]).statistic
        auroc = float(U / ((yw == 1).sum() * (yw == 0).sum()))
        ci_cp = sst.binomtest(TP, NR).proportion_ci(method="exact")
        gl = 0.0 if FP == 0 else sst.gamma.ppf(0.025, FP)
        gu = sst.gamma.ppf(0.975, FP + 1)
        res[s] = {"order_by_edf_header": order_by_header, "causal_chronology_ok": bool(causal_ok),
                  "n_buffer_dropped": int(sum(T[f] - 1 - keep[f].size for f in tr)),
                  "n_train_windows": int(sum(keep[f].size for f in tr)), "n_train_pos": int(sum(ytr[f][keep[f]].sum() for f in tr)),
                  "tau": tau, "tau_curve_head": curve[:3], "tau_curve_last": curve[-1], "tp_timescoring": TP, "fp_timescoring": FP,
                  "n_ref": NR, "tp_own": TPo, "fp_own": FPo, "hours": H, "fa_per_24h": 24.0 * FP / H, "window_auroc": auroc,
                  "n_test_windows": int(yw.size), "n_pos_windows": int(yw.sum()), "cp95": [float(ci_cp.low), float(ci_cp.high)],
                  "garwood95_per_24h": [24 * gl / H, 24 * gu / H], "fp_grid_meet_inc": fp_grid(H),
                  "rule_verdict": rule(TP, FP, H), "hyp": hyps}
        del F, P, oof
        print(s, {k: v for k, v in res[s].items() if k != "hyp"}, round(time.time() - t0, 1), flush=True)
    v = [res[s]["rule_verdict"] for s in ("chb23", "chb24")]
    res["overall"] = ("PASS" if v.count("PASS") == 2 else "FAIL" if v.count("FAIL") == 2 else "INCONCLUSIVE")
    # ---- C3' exact random-alarm null (independent)
    joint = {(0, 0): 1}
    Ttot = 1
    nref = 0
    for f, ref_ev, hm in c3_files:
        d, T = offsets_dist(ref_ev, hm)
        nref += I.own_score(ref_ev, np.zeros(T, bool))[2]
        new = {}
        for (a, b), c in joint.items():
            for (x, y), c2 in d.items():
                new[(a + x, b + y)] = new.get((a + x, b + y), 0) + c * c2
        joint = new
        Ttot *= T
    pmf = {}
    for (tp, fp), c in joint.items():
        den = tp + fp + nref
        f1 = Fraction(2 * tp, den) if den else Fraction(0)
        pmf[f1] = pmf.get(f1, 0) + Fraction(c, Ttot)
    xs = sorted(pmf)
    mu = sum(x * p for x, p in pmf.items())
    var = sum((x - mu) ** 2 * p for x, p in pmf.items())
    cum, q95 = Fraction(0), None
    for x in xs:
        cum += pmf[x]
        if q95 is None and cum >= Fraction(95, 100):
            q95 = x
    a_star = sum(p for x, p in pmf.items() if x > q95)
    res["C3prime_exact_independent"] = {"N_ref": nref, "mu_star": float(mu), "mu_star_exact": str(mu), "sigma_star": math.sqrt(var),
                                        "q95": str(q95), "a_star": float(a_star), "n_support": len(xs),
                                        "bound_i": 3 * math.sqrt(var) / math.sqrt(1000),
                                        "bound_ii": float(a_star) + 3 * math.sqrt(float(a_star) * (1 - float(a_star)) / 1000)}
    print("C3'", res["C3prime_exact_independent"], flush=True)
    res["_wall_s"] = time.time() - t0
    with open(OUT, "w") as fh:
        json.dump(res, fh, indent=1, default=float)


if __name__ == "__main__":
    main()
