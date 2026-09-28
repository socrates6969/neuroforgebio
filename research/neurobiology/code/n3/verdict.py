"""N3 gate logic (prereg §4, changes D1-D3) and the N2 §4 FP grid (§5).

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
"""
import math

from nfharness import stats

from . import ALPHA


def fp_grid(hours):
    """N2 §4: meets bar FP <= floor(H) (FA <= 24/24 h); FAIL if the Garwood lower 95% bound of FP > H (FA > 24/24 h).
    Returns (meets-bar max FP, inconclusive max FP)."""
    meet = int(math.floor(hours))
    inc = max(k for k in range(0, 500) if stats.garwood(k)[0] <= hours)
    return meet, inc


def window_gate(fisher_up, fisher_lo, n_window_flagged, n_replicates):
    """V1-A: both Fisher p (T_A) >= alpha. V2-A: <= 1 window-flagged replicate of 20 (scaled by n/20)."""
    v1 = bool(fisher_up == fisher_up and fisher_lo == fisher_lo and fisher_up >= ALPHA and fisher_lo >= ALPHA)
    v2 = bool(n_window_flagged <= 1 * n_replicates / 20.0)
    return v1, v2


def event_gate(p_up, p_lo):
    """V1-E: both pooled SigmaF1 p >= alpha (NaN = no retained replicate -> not met)."""
    return bool(p_up == p_up and p_lo == p_lo and p_up >= ALPHA and p_lo >= ALPHA)


def pla_trips(fisher_T_A_up):
    """D1: PL-A must trip the window arm: Fisher (T_A, up) p < alpha."""
    return bool(fisher_T_A_up == fisher_T_A_up and fisher_T_A_up < ALPHA)


def harness_verdict(c):
    """c: dict of booleans (the §4 PASS list). Returns (verdict, failed items, flags)."""
    keys = ["step2_pytest", "step3_dry_run", "step5_real_run_complete", "step6_rerun_identical", "V1-A", "V2-A", "V1-E",
            "C3prime_i", "C3prime_ii", "PL-A_trips_T_A", "PL-B-code_raises", "PL-C_trips", "PL-B_specificity"]
    failed = [k for k in keys if not c.get(k)]
    flags = []
    if not c.get("V1-A") or not c.get("V1-E"):
        flags.append("possible leak (V1-A or V1-E trip)")
    if not c.get("PL-A_trips_T_A"):
        flags.append("controls powerless (PL-A did not trip T_A)")
    return ("PASS" if not failed else "FAIL"), failed, flags


def model_overall(verdicts):
    """N2 rule for S = 2: PASS if both PASS, FAIL if both FAIL, else INCONCLUSIVE (= run_n2.overall for 2 subjects)."""
    n_pass = sum(v == "PASS" for v in verdicts)
    n_fail = sum(v == "FAIL" for v in verdicts)
    if n_pass >= 2 and n_fail == 0:
        return "PASS"
    if n_fail >= 2:
        return "FAIL"
    return "INCONCLUSIVE"
