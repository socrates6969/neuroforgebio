"""C3' random-alarm null with an EXACT reference (prereg §3) and the planted scorer/alarm leak PL-C (§4).

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
Generator (as D8): each test file's 1-Hz N2 hypothesis mask is circularly shifted by an independent offset uniform on
{0, ..., T_f - 1}. Exact distribution: all T_f offsets of every file scored with the validated re-implementation ->
integer counts of (TP_f, FP_f) -> exact integer convolution over files -> pooled F1 = 2TP/(2TP + FP + (N - TP)).
Harness Monte Carlo: M_C draws scored through nfharness Scorer.score_file (timescoring).
"""
import math
from collections import Counter
from fractions import Fraction

import numpy as np

from nfharness.scoring import mask_events, reimpl_event_score

from .vault import require_flag

PLC_PROB = 0.25


def file_counts(ref, hyp):
    """Counter {(TP_f, FP_f): number of offsets} over ALL T_f circular offsets."""
    hyp = np.asarray(hyp, dtype=np.int8)
    T = hyp.size
    if not hyp.any():
        e = reimpl_event_score(ref, hyp)
        return Counter({(e["tp"], e["fp"]): T})
    c = Counter()
    for o in range(T):
        e = reimpl_event_score(ref, np.roll(hyp, o))
        c[(e["tp"], e["fp"])] += 1
    return c


def convolve(counters):
    joint = Counter({(0, 0): 1})
    for c in counters:
        new = Counter()
        for (a, b), x in joint.items():
            for (u, v), y in c.items():
                new[(a + u, b + v)] += x * y
        joint = new
    return joint


def exact_distribution(counters, n_ref):
    """Exact pmf of the pooled F1 (integer arithmetic). Returns summary + the pmf as (F1 float, mass float) pairs."""
    joint = convolve(counters)
    W = math.prod(sum(c.values()) for c in counters)
    assert sum(joint.values()) == W
    mass = Counter()
    for (tp, fp), x in joint.items():
        d = 2 * tp + fp + (n_ref - tp)
        mass[Fraction(2 * tp, d) if d else Fraction(0)] += x
    vals = sorted(mass)
    mu = sum(v * mass[v] for v in vals) / W
    m2 = sum(v * v * mass[v] for v in vals) / W
    var = m2 - mu * mu

    def quant(num, den):
        cum = 0
        for v in vals:
            cum += mass[v]
            if cum * den >= num * W:
                return v, cum
    q95, c95 = quant(95, 100)
    q99, c99 = quant(99, 100)
    a_star = Fraction(W - c95, W)
    return {"mu_star": float(mu), "sigma_star": math.sqrt(float(var)), "q95": float(q95), "q99": float(q99),
            "a_star": float(a_star), "q95_exact": str(q95), "q99_exact": str(q99), "mu_star_exact_fraction": str(mu),
            "n_support_points": len(vals), "n_joint_states": len(joint), "total_weight_digits": len(str(W)),
            "P_F1_le_0.05": float(Fraction(sum(mass[v] for v in vals if v <= Fraction(1, 20)), W))}, \
        [(float(v), float(Fraction(mass[v], W))) for v in vals]


def first_alarm_start(hyp):
    st, _ = mask_events(hyp)
    return int(st[0]) if st.size else None


def harness_mc(files, scorers, g, M, plant=None, allow_planted_leak=False, seizure_onset=None):
    """files: [(subject, file, hyp_mask)] in the fixed order; scorers: {subject: nfharness Scorer}.
    Per draw and file: o = g.integers(0, T_f); for PL-C, then (seizure files only) u = g.random() and if u < 0.25 the
    offset is replaced by (first seizure onset - first raw alarm-run start) mod T_f. Returns (pooled F1 array, n_forced)."""
    if plant is not None:
        if plant != "PL-C":
            raise ValueError(plant)
        require_flag(allow_planted_leak, "PL-C harness_mc")
    fa = {f: first_alarm_start(h) for _, f, h in files}
    f1s = np.empty(M)
    n_forced = 0
    for m in range(M):
        TP = FP = NR = 0
        for s, f, h in files:
            T = h.size
            o = int(g.integers(0, T))
            if plant == "PL-C" and seizure_onset.get(f) is not None:
                u = float(g.random())
                if u < PLC_PROB and fa[f] is not None:
                    o = (seizure_onset[f] - fa[f]) % T
                    n_forced += 1
            e = scorers[s].score_file(f, np.roll(h, o))
            TP, FP, NR = TP + e["tp"], FP + e["fp"], NR + e["n_ref"]
        d = 2 * TP + FP + (NR - TP)
        f1s[m] = 2 * TP / d if d else 0.0
    return f1s, n_forced


def c3_criteria(f1s, ex):
    M = f1s.size
    mean = float(f1s.mean())
    frac = float(np.mean(f1s > ex["q95"]))
    tol_mean = 3 * ex["sigma_star"] / math.sqrt(M)
    bound = ex["a_star"] + 3 * math.sqrt(ex["a_star"] * (1 - ex["a_star"]) / M)
    return {"M": M, "mean_mc": mean, "sd_mc": float(f1s.std()), "abs_mean_diff": abs(mean - ex["mu_star"]),
            "tol_mean_3sigma_over_sqrtM": tol_mean, "crit_i": bool(abs(mean - ex["mu_star"]) <= tol_mean),
            "frac_above_q95": frac, "bound_ii": bound, "crit_ii": bool(frac <= bound),
            "p95_mc": float(np.percentile(f1s, 95))}
