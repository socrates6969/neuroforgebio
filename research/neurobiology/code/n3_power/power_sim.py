"""N3 power analysis for the NC-P negative controls: SYNTHETIC label timelines and SYNTHETIC scores only (no EEG).

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims.
Author: mathematician/methodologist, hive cycle 2, 2026-09-26. Seed 20261001 (stream 40). numpy/scipy only.

Question: how many phantom/test references per subject (K = N_ref) and how many subjects (S) does the NC-P event arm
need to trip planted leaks of the PL-A / PL-B type with power >= 0.8 while keeping the false-trip rate <= 0.05, and
which combination rule should be used (Fisher on p_up, Fisher on Lancaster mid-p, Fisher on random-tie-break p,
pooled conditional-randomisation sums of TP or F1 across replicates)?

Surrogate (one "fit" = one subject x replicate):
  * test layout = equal allowed segments of SEG s (H_test = max(2 h, 1.25 h x K)); training layout TRAIN_H hours.
  * honest window latent z = fast AR(1) + slow AR(1) + artifact bursts (subject-specific); train-OOF scores
    q = expit(mu + sig z_tr), test scores p = expit(mu + sig (z_te + c)), c = train->test mismatch.
  * everything downstream is the N1b/N2 logic: locked tau grid, 4-of-5 causal smoothing (checked bit-for-bit against
    nfharness.postprocess.hypothesis_mask), 90-s merge / 300-s split, any-overlap TP with -30/+60 s tolerance, FP =
    pieces overlapping no extended reference (checked against nfharness.scoring.reimpl_event_score), label-free
    rate-matched tau t_rm (1.323 events/h of training time), degeneracy flags, rank AUROC (checked against
    nfharness.stats.auroc).
  * phantoms: sampler with the N1b sampler-S law (longest first; each onset uniform on the valid (segment, onset) set
    given the phantoms already placed; [o-30, o+d+60) inside the segment; >= 300 s gaps), by vectorised rejection
    from the uniform superset (equal segment lengths make the superset uniform, so the law is exact). The observed
    and the M null placements use the same sampler, so every p-value is exact by construction, as in N1b.
  * PL-A (label leak): latent shift delta * lambda_subject * gamma_phantom on the observed phantom windows;
    delta calibrated so the mean window AUROC T_A = 0.775 (N1b real PL-A mean) at K = 4 ("PL-A"), and weaker
    leaks calibrated to T_A = 0.65 ("PL-A-65") and 0.60 ("PL-A-60").
  * PL-B (threshold leak): on the honest fits, tau = argmax over the grid of the test-phantom F1 (ties -> smallest
    tau), p-value from the conditional null at that fixed h, exactly as in N1b.

Calibration targets for the honest surrogate (N1b real NC-P, code\\RESULTS_N1b.md): NEVER-ALARM fraction 7/30, pooled
phantom hit rate TP/N_ref = 17/120, T_A replicate SD 0.118. Validation targets NOT used in calibration: N1b real PL-A
pooled hit rate 19/60 and Fisher(T_E up) 0.012, PL-B Fisher 0.51, dry-run PL-A Fisher 0.25.

Imports from code\\nfharness and code\\n1b are read-only. Output: results\\n3_power\\power_sim.json + stdout.
Run: .venv\\Scripts\\python.exe code\\n3_power\\power_sim.py [--quick]
"""
import argparse
import hashlib
import json
import math
import os
import platform
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import numpy as np                                                   # noqa: E402
import scipy                                                         # noqa: E402
from scipy.signal import lfilter                                     # noqa: E402
from scipy.special import expit                                      # noqa: E402
from scipy.stats import chi2, rankdata                               # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.dirname(HERE)
ROOT = os.path.dirname(CODE)
sys.path.insert(0, CODE)

from nfharness.config import TAU_GRID                                # noqa: E402  (read-only reuse)
from nfharness.labels import mask_from_events                        # noqa: E402
from nfharness.postprocess import hypothesis_mask                    # noqa: E402
from nfharness.scoring import reimpl_event_score                     # noqa: E402
from nfharness.stats import auroc as nf_auroc                        # noqa: E402
from n1b.ncp import RATE_TARGET                                      # noqa: E402

SEED = 20261001
STREAM = 40
TAUS = np.asarray(TAU_GRID, dtype=np.float64)
PRE, POST, GAP, MERGE, SPLIT = 30, 60, 300, 90, 300
SEG = 3000                 # allowed segment length (s); real allowed segments 415-3600 s
SEP = 1000                 # global-axis separator between segments (> MERGE, > tolerances)
TRAIN_H = 4.0
M = 999
ALPHAS = (0.0025, 0.0125)
# CHB-MIT-like durations (N1b tables: test + training seizure durations of chb01/03/10)
DUR_POOL = [101, 93, 90, 89, 76, 70, 69, 65, 65, 64, 58, 54, 53, 52, 52, 51, 47, 40, 40, 35, 27]

# Honest surrogate regimes. "smooth": graded scores (expit of a unit-scale latent). "saturated": over-confident scores
# (large logit scale, low intercept) as produced by an L2-LR fitted to phantom labels; calibrated to N1b real NC-P and
# PL-B behaviour (see --calibrate and notes/n3_power.md). Values fixed after calibration.
BASE = dict(rho_f=0.90, rho_s=0.998, w_slow=(0.4, 0.8), burst_rate_h=(0.5, 4.0), burst_dur=(10, 120),
            burst_amp=(1.5, 4.0), c_between=0.3, c_within=0.5, burst_ratio_sd=1.5,
            leak_subject_sd=0.35, leak_gamma_shape=1.0)
REGIMES = {"smooth": dict(BASE, mu=(-1.0, 0.7), sig=(0.7, 1.5)),
           "saturated": dict(BASE, mu=(-9.0, 1.5), sig=(2.5, 4.0))}
HONEST = REGIMES["smooth"]


def rng(*key):
    return np.random.default_rng(np.random.SeedSequence(SEED, spawn_key=(STREAM,) + tuple(int(k) for k in key)))


# ----------------------------------------------------------------------------------------------- surrogate scores
def ar1(g, shape, rho):
    e = g.standard_normal(shape)
    z0 = g.standard_normal(shape[:-1] + (1,))
    y, _ = lfilter([math.sqrt(1 - rho * rho)], [1.0, -rho], e, axis=-1, zi=rho * z0)
    return y


def subject_params(s, P=None):
    P = P or HONEST
    g = rng(1, s)
    return dict(P=P, w_slow=g.uniform(*P["w_slow"]), burst_rate_h=math.exp(g.uniform(*np.log(P["burst_rate_h"]))),
                c_mean=g.normal(0.0, P["c_between"]), leak_mult=math.exp(g.normal(0.0, P["leak_subject_sd"])))


def latent(g, n_seg, L, sp, rate_mult=1.0):
    """window latent (n_seg, L-1); rate_mult scales the artifact-burst rate (train->test non-stationarity)"""
    n = L - 1
    w = sp["w_slow"]
    P = sp["P"]
    z = math.sqrt(1 - w) * ar1(g, (n_seg, n), P["rho_f"]) + math.sqrt(w) * ar1(g, (n_seg, n), P["rho_s"])
    nb = g.poisson(sp["burst_rate_h"] * rate_mult * n_seg * L / 3600.0)
    for _ in range(int(nb)):
        r = int(g.integers(0, n_seg))
        d = int(g.integers(P["burst_dur"][0], P["burst_dur"][1] + 1))
        a = int(g.integers(0, max(1, n - d)))
        z[r, a:a + d] += g.uniform(*P["burst_amp"])
    return z


def hq_rows(p):
    """p (n_seg, L-1) window scores -> hq (n_seg, L): (hq >= tau) == nfharness hypothesis_mask(p_row, tau, L)."""
    n_seg, nw = p.shape
    qm = np.full((n_seg, nw), -np.inf)
    qm[:, 3] = p[:, :4].min(axis=1)
    w = np.lib.stride_tricks.sliding_window_view(p, 5, axis=1)          # (n_seg, nw-4, 5)
    qm[:, 4:] = np.partition(w, 1, axis=-1)[..., 1]                     # >= 4 of 5 above tau <=> 2nd smallest >= tau
    hq = np.full((n_seg, nw + 1), -np.inf)
    hq[:, 1:] = qm
    return hq


def pieces(B):
    """B bool (n_seg, L) -> global (ps, pe) of merged (gap < 90 merges) and split (<= 300 s) hypothesis pieces."""
    n_seg, L = B.shape
    Z = np.zeros((n_seg, 1), dtype=np.int8)
    D = np.diff(np.concatenate([Z, B.astype(np.int8), Z], axis=1), axis=1)
    r, st = np.nonzero(D == 1)
    _, en = np.nonzero(D == -1)
    if st.size == 0:
        e = np.zeros(0, dtype=np.int64)
        return e, e
    new = np.ones(st.size, dtype=bool)
    new[1:] = (r[1:] != r[:-1]) | ((st[1:] - en[:-1]) >= MERGE)
    first = np.flatnonzero(new)
    last = np.concatenate([first[1:] - 1, [st.size - 1]])
    mr, ms, me = r[first], st[first], en[last]
    npc = -(-(me - ms) // SPLIT)
    base = np.repeat(ms, npc)
    k = np.arange(npc.sum()) - np.repeat(np.cumsum(npc) - npc, npc)
    ps = base + SPLIT * k
    pe = np.minimum(ps + SPLIT, np.repeat(me, npc))
    off = np.repeat(mr, npc).astype(np.int64) * (L + SEP)
    return ps + off, pe + off


def n_pieces_rate(hq, tau, hours):
    ps, _ = pieces(hq >= tau)
    return ps.size / hours


def rate_matched_tau(hq_tr, hours):
    for tau in TAUS:
        if n_pieces_rate(hq_tr, tau, hours) <= RATE_TARGET:
            return float(tau), False
    return 0.99, True


# ----------------------------------------------------------------------------------------------- phantoms
def durations(K):
    return np.array(sorted([DUR_POOL[i % len(DUR_POOL)] for i in range(K)], reverse=True), dtype=np.int64)


def sample(g, n_seg, L, D, n):
    """n placements of phantoms with durations D (longest first) -> segment (n,K), local onset (n,K)."""
    K = D.size
    S = np.zeros((n, K), dtype=np.int64)
    O = np.zeros((n, K), dtype=np.int64)
    for k in range(K):
        d = int(D[k])
        lo, hi = PRE, L - d - POST
        todo = np.arange(n)
        for _ in range(100000):
            s = g.integers(0, n_seg, size=todo.size)
            o = g.integers(lo, hi + 1, size=todo.size)
            bad = np.zeros(todo.size, dtype=bool)
            for k2 in range(k):
                same = S[todo, k2] == s
                ok = (o + d + GAP <= O[todo, k2]) | (o >= O[todo, k2] + D[k2] + GAP)
                bad |= same & ~ok
            S[todo[~bad], k] = s[~bad]
            O[todo[~bad], k] = o[~bad]
            todo = todo[bad]
            if todo.size == 0:
                break
        else:
            raise RuntimeError("sampler: capacity too small")
    return S, O


class Hyp:
    def __init__(self, hq, tau, L):
        self.ps, self.pe = pieces(hq >= tau)
        self.n = int(self.ps.size)
        self.L = L
        self.coverage = float((hq >= tau).mean())

    def score(self, S, O, D):
        """TP, FP, F1 for placements (n,K)."""
        G = S * (self.L + SEP) + O
        xs = G - PRE
        xe = G + D[None, :] + POST
        a = np.searchsorted(self.pe, xs, side="right")
        b = np.searchsorted(self.ps, xe, side="left")
        hit = b > a
        TP = hit.sum(axis=1)
        idx = np.argsort(G, axis=1)
        a_s = np.take_along_axis(a, idx, 1)
        b_s = np.take_along_axis(b, idx, 1)
        prev = np.maximum.accumulate(b_s, axis=1)
        prev = np.concatenate([np.zeros((b_s.shape[0], 1), dtype=b_s.dtype), prev[:, :-1]], axis=1)
        distinct = np.maximum(0, b_s - np.maximum(a_s, prev)).sum(axis=1)
        FP = self.n - distinct
        K = D.size
        F1 = 2.0 * TP / (2.0 * TP + FP + (K - TP))
        return TP, FP, F1


class Ranks:
    def __init__(self, p):
        n_seg, nw = p.shape
        r = rankdata(p.ravel()).reshape(n_seg, nw)
        self.cum = np.concatenate([np.zeros((n_seg, 1)), np.cumsum(r, axis=1)], axis=1)
        self.N = p.size

    def auroc(self, S, O, D):
        s = (self.cum[S, O + D[None, :] - 1] - self.cum[S, O]).sum(axis=1)
        n1 = float((D - 1).sum())
        n0 = self.N - n1
        return (s - n1 * (n1 + 1) / 2.0) / (n1 * n0)


# ----------------------------------------------------------------------------------------------- one fit
def one_fit(job):
    """job = (kind, K, subject, rep, delta, do_plb, M, regime) ; kind in {'honest','pla'}"""
    kind, K, s, rep, delta, do_plb, Mn, regime = job
    P = REGIMES[regime] if isinstance(regime, str) else regime
    g = rng(2, K, s, rep, int(round(delta * 1000)), 0 if regime == "smooth" else 1)
    sp = subject_params(s, P)
    H = max(2.0, 1.25 * K)
    n_seg = int(round(H * 3600 / SEG))
    L = SEG
    D = durations(K)
    mu = g.normal(*P["mu"])
    sig = g.uniform(*P["sig"])
    c = sp["c_mean"] + g.normal(0.0, P["c_within"])
    n_tr = int(round(TRAIN_H * 3600 / SEG))
    z_tr = latent(g, n_tr, L, sp)
    t_rm, flag = rate_matched_tau(hq_rows(expit(mu + sig * z_tr)), n_tr * L / 3600.0)
    z_te = latent(g, n_seg, L, sp, math.exp(g.normal(0.0, P["burst_ratio_sd"])))
    S_obs, O_obs = sample(g, n_seg, L, D, 1)
    if kind == "pla":
        gam = g.gamma(P["leak_gamma_shape"], 1.0 / P["leak_gamma_shape"], size=K)
        for k in range(K):
            z_te[S_obs[0, k], O_obs[0, k]:O_obs[0, k] + D[k] - 1] += delta * sp["leak_mult"] * gam[k]
    p = expit(mu + sig * (z_te + c))
    hq = hq_rows(p)
    S_nu, O_nu = sample(g, n_seg, L, D, Mn)
    rk = Ranks(p)
    out = {"kind": kind, "K": K, "s": s, "rep": rep, "t_rm": t_rm, "t_rm_flag": flag, "H": H, "n_events": 0}
    ta_obs = float(rk.auroc(S_obs, O_obs, D)[0])
    out["TA_obs"] = ta_obs
    out["TA_null"] = rk.auroc(S_nu, O_nu, D).astype(np.float32)
    h = Hyp(hq, t_rm, L)
    out["never"] = h.n == 0
    out["n_events"] = h.n
    out["always"] = h.coverage >= 0.5
    tp, fp, f1 = h.score(S_obs, O_obs, D)
    out["TP_obs"], out["FP_obs"], out["F1_obs"] = int(tp[0]), int(fp[0]), float(f1[0])
    tpn, _, f1n = h.score(S_nu, O_nu, D)
    out["TP_null"], out["F1_null"] = tpn.astype(np.int16), f1n.astype(np.float32)
    if do_plb:
        best, bt = -1.0, None
        for tau in TAUS:
            hb = Hyp(hq, tau, L)
            f = float(hb.score(S_obs, O_obs, D)[2][0])
            if f > best + 1e-12:
                best, bt, hbest = f, float(tau), hb
        tpb, _, f1b = hbest.score(S_obs, O_obs, D)
        tpbn, _, f1bn = hbest.score(S_nu, O_nu, D)
        out.update({"B_tau": bt, "B_never": hbest.n == 0, "B_always": hbest.coverage >= 0.5,
                    "B_TP_obs": int(tpb[0]), "B_F1_obs": float(f1b[0]),
                    "B_TP_null": tpbn.astype(np.int16), "B_F1_null": f1bn.astype(np.float32)})
    return out


# ----------------------------------------------------------------------------------------------- combination rules
def p_up(obs, null):
    return (1 + np.sum(null >= obs - 1e-12)) / (null.size + 1)


def p_mid(obs, null):
    gt = np.sum(null > obs + 1e-12)
    eq = np.sum(np.abs(null - obs) <= 1e-12)
    return (gt + 0.5 * (eq + 1)) / (null.size + 1)


def p_rt(obs, null, u):
    gt = np.sum(null > obs + 1e-12)
    eq = np.sum(np.abs(null - obs) <= 1e-12)
    return (1 + gt + np.floor(u * (eq + 1))) / (null.size + 1)


def fisher(ps):
    ps = np.asarray(ps, dtype=np.float64)
    if ps.size == 0:
        return 1.0
    return float(chi2.sf(-2.0 * np.log(ps).sum(), 2 * ps.size))


def pooled(obs_sum, null_sum):
    return (1 + np.sum(null_sum >= obs_sum - 1e-9)) / (null_sum.size + 1)


RULES = ["fisher", "fisher_mid", "fisher_rt", "pooled_TP", "pooled_F1"]


def combine(fits, arm, g):
    """arm 'E' (t_rm event arm), 'B' (PL-B tau), 'A' (window AUROC, Fisher on p_up only)."""
    if arm == "A":
        ps = [p_up(f["TA_obs"], f["TA_null"]) for f in fits]
        return {"fisher": fisher(ps)}
    pre = "" if arm == "E" else "B_"
    if arm == "E":
        ret = [f for f in fits if not (f["never"] or f["always"])]
    else:
        ret = [f for f in fits if not (f["B_never"] or f["B_always"])]
    if not ret:
        return {r: 1.0 for r in RULES}
    o = np.array([f[pre + "F1_obs"] for f in ret])
    nulls = [f[pre + "F1_null"].astype(np.float64) for f in ret]
    u = g.random(len(ret))
    res = {"fisher": fisher([p_up(a, b) for a, b in zip(o, nulls)]),
           "fisher_mid": fisher([p_mid(a, b) for a, b in zip(o, nulls)]),
           "fisher_rt": fisher([p_rt(a, b, uu) for a, b, uu in zip(o, nulls, u)])}
    res["pooled_F1"] = pooled(o.sum(), np.sum(nulls, axis=0))
    tpo = sum(f[pre + "TP_obs"] for f in ret)
    res["pooled_TP"] = pooled(tpo, np.sum([f[pre + "TP_null"].astype(np.int64) for f in ret], axis=0))
    return res


def pseudo_null_combine(fits, arm, g):
    """Size check: replace each retained fit's observation by one of its own null draws (exchangeable under H0)."""
    pre = "" if arm == "E" else "B_"
    key_nev = "never" if arm == "E" else "B_never"
    key_alw = "always" if arm == "E" else "B_always"
    ret = [f for f in fits if not (f[key_nev] or f[key_alw])]
    if not ret:
        return {r: 1.0 for r in RULES}
    obs, refs, tpo, tpr = [], [], 0, []
    for f in ret:
        b = int(g.integers(0, M))
        nf = f[pre + "F1_null"].astype(np.float64)
        nt = f[pre + "TP_null"].astype(np.int64)
        obs.append(nf[b])
        refs.append(np.delete(nf, b))
        tpo += nt[b]
        tpr.append(np.delete(nt, b))
    u = g.random(len(ret))
    return {"fisher": fisher([p_up(a, r) for a, r in zip(obs, refs)]),
            "fisher_mid": fisher([p_mid(a, r) for a, r in zip(obs, refs)]),
            "fisher_rt": fisher([p_rt(a, r, uu) for a, r, uu in zip(obs, refs, u)]),
            "pooled_F1": pooled(float(np.sum(obs)), np.sum(refs, axis=0)),
            "pooled_TP": pooled(tpo, np.sum(tpr, axis=0))}


# ----------------------------------------------------------------------------------------------- self test
def self_test():
    g = rng(9)
    out = {}
    # 1) hq_rows vs nfharness.hypothesis_mask
    ok = True
    for _ in range(20):
        L = int(g.integers(50, 400))
        p = g.random((1, L - 1)) ** 0.3
        hq = hq_rows(p)
        for tau in (0.05, 0.3, 0.6, 0.8, 0.95):
            ok &= np.array_equal((hq[0] >= tau).astype(np.int8), hypothesis_mask(p[0], tau, L))
    out["kofn_bitwise"] = bool(ok)
    # 2) event TP/FP vs reimpl_event_score, several segments, random placements
    nchk, ok = 0, True
    for _ in range(40):
        L, n_seg = 3000, int(g.integers(1, 4))
        z = latent(g, n_seg, L, subject_params(0))
        hq = hq_rows(expit(-1 + z))
        tau = float(g.choice(TAUS))
        h = Hyp(hq, tau, L)
        K = int(g.integers(1, 3 * n_seg + 1))
        D = durations(K)
        S, O = sample(g, n_seg, L, D, 5)
        TP, FP, _ = h.score(S, O, D)
        for m in range(5):
            tp = fp = 0
            for j in range(n_seg):
                ev = [(int(O[m, k]), int(O[m, k] + D[k])) for k in range(K) if S[m, k] == j]
                e = reimpl_event_score(mask_from_events(ev, L), (hq[j] >= tau).astype(np.int8))
                tp += e["tp"]
                fp += e["fp"]
            ok &= (tp == TP[m]) and (fp == FP[m])
            nchk += 1
    out["event_vs_reimpl"] = {"n": nchk, "all_equal": bool(ok)}
    # 3) AUROC vs nfharness.stats.auroc
    n_seg, L = 2, 3000
    p = expit(latent(g, n_seg, L, subject_params(1)))
    D = durations(4)
    S, O = sample(g, n_seg, L, D, 3)
    rk = Ranks(p)
    a = rk.auroc(S, O, D)
    ok = True
    for m in range(3):
        y = np.zeros((n_seg, L - 1), dtype=bool)
        for k in range(4):
            y[S[m, k], O[m, k]:O[m, k] + D[k] - 1] = True
        ok &= abs(nf_auroc(y.ravel(), p.ravel()) - a[m]) < 1e-12
    out["auroc_vs_nfharness"] = bool(ok)
    # 4) sampler law: 1 segment, 2 phantoms -> compare the first phantom's onset histogram with the exact law
    L, D = 1000, np.array([100, 50])
    S, O = sample(g, 1, L, D, 40000)
    ok_gap = bool(np.all((O[:, 0] + 100 + GAP <= O[:, 1]) | (O[:, 1] >= O[:, 0] + 100 + GAP) |
                         (O[:, 1] + 50 + GAP <= O[:, 0])))
    lo, hi = PRE, L - 100 - POST
    h, _ = np.histogram(O[:, 0], bins=8, range=(lo, hi + 1))
    exp = 40000 / 8.0
    out["sampler"] = {"gap_ok": ok_gap, "chi2_first_uniform_p": float(chi2.sf(((h - exp) ** 2 / exp).sum(), 7))}
    return out


# ----------------------------------------------------------------------------------------------- driver
def run_pool(ex, jobs):
    return list(ex.map(one_fit, jobs, chunksize=4))


def summarise(fits, arm="E"):
    n = len(fits)
    nev = np.mean([f["never"] for f in fits])
    tp = sum(f["TP_obs"] for f in fits)
    nref = sum(f["K"] for f in fits)
    return {"n": n, "never_frac": round(float(nev), 3), "always_frac": round(float(np.mean([f["always"] for f in fits])), 3),
            "t_rm_flag_frac": round(float(np.mean([f["t_rm_flag"] for f in fits])), 3),
            "hit_rate": round(tp / nref, 3), "FP_per_h": round(float(np.mean([f["FP_obs"] / f["H"] for f in fits])), 2),
            "TA_mean": round(float(np.mean([f["TA_obs"] for f in fits])), 3),
            "TA_sd": round(float(np.std([f["TA_obs"] for f in fits], ddof=1)), 3)}


def calibrate_delta(ex, target, regime, n_subj=24, reps=4, K=4):
    lo, hi = 0.0, 6.0
    for _ in range(10):
        mid = 0.5 * (lo + hi)
        fits = run_pool(ex, [("pla", K, 1000 + s, r, mid, False, 99, regime) for s in range(n_subj) for r in range(reps)])
        ta = np.mean([f["TA_obs"] for f in fits])
        if ta < target:
            lo = mid
        else:
            hi = mid
    return round(0.5 * (lo + hi), 3)


def power_table(pool, Ks, Ss, R, arm, n_exp, g):
    """pool[K] = {subject: [fits]} -> {K: {S: {rule: power at each alpha}}}"""
    tab = {}
    for K in Ks:
        subs = sorted(pool[K])
        tab[K] = {}
        for S in Ss:
            if S > len(subs):
                continue
            ps = {r: [] for r in (["fisher"] if arm == "A" else RULES)}
            for _ in range(n_exp):
                chosen = g.choice(subs, size=S, replace=False)
                fits = []
                for s in chosen:
                    fl = pool[K][s]
                    idx = g.choice(len(fl), size=R, replace=False) if R < len(fl) else np.arange(len(fl))
                    fits += [fl[i] for i in idx]
                res = combine(fits, arm, g)
                for r in ps:
                    ps[r].append(res[r])
            tab[K][S] = {r: {str(a): round(float(np.mean(np.asarray(v) < a)), 3) for a in ALPHAS} | {"median_p": float(np.median(v))}
                         for r, v in ps.items()}
    return tab


def size_table(pool, Ks, Ss, R, arm, n_exp, g):
    tab = {}
    for K in Ks:
        subs = sorted(pool[K])
        tab[K] = {}
        for S in Ss:
            if S > len(subs):
                continue
            ps = {r: [] for r in RULES}
            for _ in range(n_exp):
                chosen = g.choice(subs, size=S, replace=False)
                fits = []
                for s in chosen:
                    fits += pool[K][s][:R]
                res = pseudo_null_combine(fits, arm, g)
                for r in RULES:
                    ps[r].append(res[r])
            tab[K][S] = {r: {str(a): round(float(np.mean(np.asarray(v) < a)), 4) for a in ALPHAS + (0.05,)} for r, v in ps.items()}
    return tab


def by_subject(fits):
    d = {}
    for f in fits:
        d.setdefault(f["s"], []).append(f)
    return d


def n1b_like(fits_by_subj, g, arm, R, n_exp=300):
    """literal N1b Fisher over random 3-subject x R-fit sets at K = 4 (for validation against the real N1b card)."""
    ps = []
    subs = sorted(fits_by_subj)
    for _ in range(n_exp):
        chosen = g.choice(subs, size=3, replace=False)
        fits = sum([[fits_by_subj[s][i] for i in g.choice(len(fits_by_subj[s]), size=R, replace=False)] for s in chosen], [])
        ps.append(combine(fits, arm, g)["fisher"])
    ps = np.asarray(ps)
    return {"median": float(np.median(ps)), "q10": float(np.quantile(ps, 0.1)), "q90": float(np.quantile(ps, 0.9)),
            "P(p<0.0025)": float(np.mean(ps < 0.0025))}


def honest_diag(fits):
    d = summarise(fits)
    d["frac_events_ge20"] = round(float(np.mean([f["n_events"] >= 20 for f in fits])), 3)
    if "B_tau" in fits[0]:
        pb = [p_up(f["B_F1_obs"], f["B_F1_null"]) for f in fits]
        d.update({"PLB_tau_floor_frac": round(float(np.mean([f["B_tau"] <= 0.05 for f in fits])), 3),
                  "PLB_F1_mean": round(float(np.mean([f["B_F1_obs"] for f in fits])), 3),
                  "PLB_p_median": round(float(np.median(pb)), 3),
                  "PLB_zeroTP_frac": round(float(np.mean([f["B_TP_obs"] == 0 for f in fits])), 3)})
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--calibrate", default=None, help="JSON dict overriding the saturated regime (calibration scan)")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    from concurrent.futures import ProcessPoolExecutor
    t0 = time.time()
    st = self_test()
    print("self-test", st, flush=True)
    g = rng(3)
    with ProcessPoolExecutor(a.workers) as ex:
        if a.calibrate is not None:
            P = dict(REGIMES["saturated"], **{k: tuple(v) if isinstance(v, list) else v
                                              for k, v in json.loads(a.calibrate).items()})
            fits = run_pool(ex, [("honest", 4, 2000 + s, r, 0.0, True, 199, P) for s in range(24) for r in range(10)])
            print("honest K=4", honest_diag(fits), "PL-B N1b-like", n1b_like(by_subject(fits), g, "B", 10, 100),
                  round(time.time() - t0, 1), flush=True)
            return
        Ks = [4, 10] if a.quick else [2, 4, 7, 10, 13, 20]
        n_subj = 12 if a.quick else 24
        R_POOL = 10
        Ss = [1, 2, 3, 4, 6]
        n_exp = 150 if a.quick else 300
        n_size = 2000 if a.quick else 6000
        res = {"self_test": st, "regimes": REGIMES, "deltas": {}, "diagnostics": {}, "power": {}, "size_event_R10": {},
               "size_window_disjoint": {}, "n1b_design_validation": {}}
        for regime in ("saturated", "smooth"):
            leak_regime = {"PL-A": regime, "PL-A-65": regime, "PL-A-60": regime}
            if regime == "saturated":
                # harsher PL-A: same mean T_A, leak spread evenly over phantoms (gamma shape 20; a concentrated leak, shape 0.25,
                # raised the hit rate to 0.48 in a trial run), which lowers the event hit rate towards the N1b real 19/60 = 0.32
                leak_regime["PL-A-hom"] = dict(REGIMES["saturated"], leak_gamma_shape=20.0)
            deltas = {n: calibrate_delta(ex, {"PL-A": 0.775, "PL-A-65": 0.65, "PL-A-60": 0.60, "PL-A-hom": 0.775}[n], rg)
                      for n, rg in leak_regime.items()}
            res["deltas"][regime] = deltas
            print(regime, "deltas", deltas, round(time.time() - t0), flush=True)
            honest, leaks = {}, {k: {} for k in deltas}
            diag = {}
            for K in Ks:
                fits = run_pool(ex, [("honest", K, s, r, 0.0, True, M, regime) for s in range(n_subj) for r in range(R_POOL)])
                honest[K] = by_subject(fits)
                diag[K] = {"honest": honest_diag(fits)}
                for name, dl in deltas.items():
                    if name not in ("PL-A", "PL-A-hom") and K not in (4, 10, 20):
                        continue
                    lf = run_pool(ex, [("pla", K, s, r, dl, False, M, leak_regime[name])
                                       for s in range(n_subj) for r in range(R_POOL)])
                    leaks[name][K] = by_subject(lf)
                    diag[K][name] = summarise(lf)
                print(regime, "K", K, diag[K], round(time.time() - t0), flush=True)
            res["diagnostics"][regime] = diag
            pw = {"PL-A_event_R10": power_table(leaks["PL-A"], Ks, Ss, 10, "E", n_exp, g),
                  "PL-A_event_R5": power_table(leaks["PL-A"], Ks, Ss, 5, "E", n_exp, g),
                  "PL-A_window_R5": power_table(leaks["PL-A"], Ks, Ss, 5, "A", n_exp, g),
                  "PL-B_event_R10": power_table(honest, Ks, Ss, 10, "B", n_exp, g)}
            if "PL-A-hom" in leaks:
                pw["PL-A-hom_event_R10"] = power_table(leaks["PL-A-hom"], Ks, Ss, 10, "E", n_exp, g)
                pw["PL-A-hom_event_R5"] = power_table(leaks["PL-A-hom"], Ks, Ss, 5, "E", n_exp, g)
                pw["PL-A-hom_window_R5"] = power_table(leaks["PL-A-hom"], Ks, Ss, 5, "A", n_exp, g)
            for n in ("PL-A-65", "PL-A-60"):
                pw[n + "_event_R10"] = power_table(leaks[n], sorted(leaks[n]), Ss, 10, "E", n_exp, g)
                pw[n + "_window_R10"] = power_table(leaks[n], sorted(leaks[n]), Ss, 10, "A", n_exp, g)
            res["power"][regime] = pw
            if 4 in Ks:
                res["n1b_design_validation"][regime] = {"PL-A_E_R5": n1b_like(leaks["PL-A"][4], g, "E", 5),
                                                        "PL-B_R10": n1b_like(honest[4], g, "B", 10)}
                if "PL-A-hom" in leaks:
                    res["n1b_design_validation"][regime]["PL-A-hom_E_R5"] = n1b_like(leaks["PL-A-hom"][4], g, "E", 5)
            gs = rng(4, 0 if regime == "smooth" else 1)
            res["size_event_R10"][regime] = size_table(honest, [K for K in (4, 10) if K in Ks], [3], 10, "E", n_size, gs)
            res["size_PLBnull_R10"] = res.get("size_PLBnull_R10", {})
            res["size_PLBnull_R10"][regime] = size_table(honest, [4], [3], 10, "B", n_size, gs)
            wa = []
            for K in Ks:
                subs = sorted(honest[K])
                for i in range(0, len(subs) - 2, 3):
                    wa.append(combine(sum([honest[K][s] for s in subs[i:i + 3]], []), "A", gs)["fisher"])
            wa = np.asarray(wa)
            res["size_window_disjoint"][regime] = {"n_experiments": int(wa.size), "frac_p_lt_0.05": float(np.mean(wa < 0.05)),
                                                   "frac_p_lt_0.0125": float(np.mean(wa < 0.0125)),
                                                   "KS_uniform_p": float(__import__("scipy.stats", fromlist=["kstest"]).kstest(wa, "uniform").pvalue)}
    with open(__file__, "rb") as fh:
        script_hash = hashlib.sha256(fh.read()).hexdigest()
    res["provenance"] = {"script_sha256": script_hash, "seed": SEED, "stream": STREAM, "python": platform.python_version(),
                         "numpy": np.__version__, "scipy": scipy.__version__, "quick": a.quick,
                         "runtime_s": round(time.time() - t0, 1), "M": M, "n_subject_pool": n_subj, "R_pool": R_POOL,
                         "n_exp_power": n_exp, "n_exp_size": n_size, "alphas": ALPHAS}
    od = os.path.join(ROOT, "results", "n3_power")
    os.makedirs(od, exist_ok=True)
    fn = os.path.join(od, "power_sim_quick.json" if a.quick else "power_sim.json")
    with open(fn, "w") as fh:
        json.dump(res, fh, indent=1, sort_keys=True, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    print("wrote", fn, "runtime", round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
