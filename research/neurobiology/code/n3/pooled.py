"""Exact pooled conditional-randomisation statistics for the event arm (prereg §4.2) + descriptive combinations.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
- null_draws_full mirrors n1b.ncp.null_draws draw for draw (same sampler calls on the same generator, same scorer) but
  keeps the integer (TP, FP, N_ref) of every null placement, which the pooled statistic needs. run_n3.py re-creates the
  stream-22 generator of each replicate and asserts that the T_A null array is bit-identical to the one n1b computed and
  that the float F1 null mean and p-values equal n1b's.
- Pooled SigmaF1: T = sum over retained replicates of the observed F1; null draw b = sum over the same replicates of
  F1(null draw b); p_up = (1 + #{T_null >= T}) / (M + 1), p_lo with <=. F1 values are exact fractions
  2TP / (TP + FP + N_ref), so sums and ties are exact (no float tolerance).
"""
import math
from fractions import Fraction

import numpy as np
from scipy.stats import chi2

from n1b.sampler import place_with_redraw


def null_draws_full(ts, arms, seg_lengths, dur_order, g, M):
    TA = np.empty(M)
    cnt = {a: np.empty((M, 3), dtype=np.int64) for a in arms}
    for m in range(M):
        pl, _ = place_with_redraw(seg_lengths, dur_order, g)
        TA[m] = ts.auroc(pl)
        for a, arm in arms.items():
            _, tp, fp, nr = arm.score(pl)
            cnt[a][m] = (tp, fp, nr)
    return TA, cnt


def f1_exact(tp, fp, nr):
    d = 2 * tp + fp + (nr - tp)
    return Fraction(2 * int(tp), int(d)) if d else Fraction(0)


def f1_float(tp, fp, nr):
    d = 2 * tp + fp + (nr - tp)
    return 2 * tp / d if d else 0.0


def pooled_test(obs, nulls, stat="F1"):
    """obs: [(tp, fp, nr)] of the retained replicates; nulls: [int array (M, 3)] in the same order.
    Returns dict with the exact T, p_up, p_lo (NaN p-values if no replicate is retained; DEVIATIONS N3-6)."""
    n = len(obs)
    if n == 0:
        return {"n_retained": 0, "T": None, "p_up": float("nan"), "p_lo": float("nan"), "null_mean": None}
    M = nulls[0].shape[0]
    if stat == "F1":
        T = sum((f1_exact(*o) for o in obs), Fraction(0))
        Tn = [Fraction(0)] * M
        for arr in nulls:
            for b in range(M):
                Tn[b] += f1_exact(*arr[b])
    elif stat == "TP":
        T = sum(int(o[0]) for o in obs)
        Tn = np.sum([arr[:, 0] for arr in nulls], axis=0).tolist()
    else:
        raise ValueError(stat)
    ge = sum(1 for x in Tn if x >= T)
    le = sum(1 for x in Tn if x <= T)
    return {"n_retained": n, "T": float(T), "T_exact": str(T), "p_up": (1 + ge) / (M + 1), "p_lo": (1 + le) / (M + 1),
            "null_mean": float(sum(Tn) / M) if stat == "TP" else float(sum(Tn, Fraction(0)) / M),
            "null_q95": float(sorted(Tn)[int(math.ceil(0.95 * M)) - 1])}


def mid_p(obs, arr):
    """Lancaster mid-p (upper) of one replicate, exact F1 comparison (as the power analysis: (gt + (eq + 1)/2)/(M + 1))."""
    o = f1_exact(*obs)
    f = [f1_exact(*r) for r in arr]
    gt = sum(1 for x in f if x > o)
    eq = sum(1 for x in f if x == o)
    return (gt + 0.5 * (eq + 1)) / (len(f) + 1)


def fisher(ps):
    ps = [float(p) for p in ps if p == p]
    if not ps:
        return float("nan"), 0
    return float(chi2.sf(-2.0 * sum(math.log(p) for p in ps), 2 * len(ps))), len(ps)
