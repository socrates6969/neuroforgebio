"""N3 power analysis for the harness negative controls (SYNTHETIC score surrogate only; no EEG is read).

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims.
Author: mathematician/methodologist, hive cycle 3, 2026-09-26. Seed 20261001. numpy/scipy only.

What this does
--------------
N1b's NC-P event arm (per-replicate exact conditional p-values of event F1, Fisher-combined over non-degenerate
replicates, N_ref = 4 phantoms per subject) did not trip planted leaks PL-A (Fisher 0.012) or PL-B (0.51). This script
asks, on a calibrated synthetic score surrogate, how the probability that each planted leak trips each control depends
on the phantom count per replicate (K, = N_ref per subject in N1b), the allowed test hours per subject (H), the
number of subjects (S), the replicates (R fits, G phantom draws per fit), and on the combination statistic.

The surrogate replaces the fitted pipeline (features -> z-score -> LR) by a window-score process with the properties
that matter for the controls: autocorrelation, artifact bursts, train/test mismatch (which produces the NEVER-ALARM and
over-alarm replicates seen in N1b), and a planted leak = a latent shift of the phantom windows (PL-A). Everything
downstream of the scores is the N1b/N2 logic: locked tau grid, 4-of-5 causal smoothing (checked bit-for-bit against
nfharness.postprocess.hypothesis_mask), the 90-s merge / 300-s split event rule and the SzCORE any-overlap TP rule with
-30/+60 s tolerance (checked against nfharness.scoring.reimpl_event_score), the label-free rate-matched tau t_rm
(1.323 events/h of training time, checked against n1b.ncp.rate_matched_tau logic), rank AUROC, and exact conditional
randomisation nulls. The phantom sampler is the joint-uniform rejection sampler S_J (defined in prereg N3 §3.2); it is
used for both the observed and the null placements, so every p-value is exact by construction, as in N1b.

Imports from code\\nfharness and code\\n1b are READ-ONLY (nothing there is modified).

Outputs: results\\power\\n3_power.json and a printed summary. Runtime target < 10 min, < 1 GB (6 worker processes).
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

import numpy as np
from scipy.signal import lfilter
from scipy.special import expit
from scipy.stats import chi2, kstest, rankdata

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.dirname(HERE)
ROOT = os.path.dirname(CODE)
sys.path.insert(0, CODE)

from nfharness.config import TAU_GRID                                   # noqa: E402  (read-only reuse)
from nfharness.postprocess import hypothesis_mask                       # noqa: E402
from nfharness.scoring import reimpl_event_score                        # noqa: E402
from n1b.ncp import RATE_TARGET, n_events as n1b_n_events, fisher      # noqa: E402

SEED = 20261001
TAUS = np.asarray(TAU_GRID, dtype=np.float64)
PRE, POST, MINGAP, MERGE, SPLIT = 30, 60, 300, 90, 300
SEP = 200                      # separator (s) between concatenated pseudo-records; > MERGE so events never merge across
ALPHA = 0.0025
M_NULL = 1999
DUR_CYCLE = [52, 65, 90, 47, 76, 101, 58, 40, 64, 53, 89, 54, 93, 70, 35, 69]   # CHB-MIT-like durations (N1b tables)
SEGMENT_S = 3000              # allowed pseudo-record length used to tile H hours (real allowed segments: 415-3600 s)
TRAIN_H = 4.0                 # allowed training hours (only feeds the label-free t_rm)


def rng(*key):
    return np.random.default_rng(np.random.SeedSequence(SEED, spawn_key=(30,) + tuple(int(k) for k in key)))


# ============================================================================ layout
class Layout:
    """Concatenated seconds axis (segments separated by SEP seconds of 'no data') and windows axis (n = L-1 per seg)."""

    def __init__(self, seg_lengths):
        self.L = np.asarray(seg_lengths, dtype=np.int64)
        self.soff = np.concatenate([[0], np.cumsum(self.L + SEP)])[:-1]
        self.T = int(self.soff[-1] + self.L[-1])
        nw = self.L - 1
        self.woff = np.concatenate([[0], np.cumsum(nw)])[:-1]
        self.N = int(nw.sum())
        self.hours = float(self.L.sum()) / 3600.0


def tile(hours, seg=SEGMENT_S):
    tot = int(round(hours * 3600))
    out = []
    while tot > 0:
        s = min(seg, tot)
        out.append(s)
        tot -= s
    if len(out) > 1 and out[-1] < 600:          # fold a short tail into the previous segment
        out[-2] += out.pop()
    return out


# ============================================================================ score surrogate
def ar1(g, n, rho):
    e = g.standard_normal(n)
    z0 = g.standard_normal()
    y, _ = lfilter([math.sqrt(1 - rho * rho)], [1.0, -rho], e, zi=[rho * z0])
    return y


def latent(g, lay, P, shift=0.0):
    """Honest latent per window, concatenated over segments (windows axis)."""
    z = np.empty(lay.N)
    for j, L in enumerate(lay.L):
        n = int(L) - 1
        x = math.sqrt(1 - P["slow_w"]) * ar1(g, n, P["rho"]) + math.sqrt(P["slow_w"]) * ar1(g, n, P["rho_slow"])
        nb = g.poisson(P["burst_rate_h"] * L / 3600.0)
        for _ in range(nb):
            d = int(g.integers(P["burst_dur"][0], P["burst_dur"][1] + 1))
            a = int(g.integers(0, max(1, n - d)))
            x[a:a + d] += g.uniform(*P["burst_amp"])
        z[lay.woff[j]:lay.woff[j] + n] = x
    return z + shift


def to_scores(z, mu, sig):
    return expit(mu + sig * z)


def qm_series(p, lay):
    """Seconds-axis series qm with (qm >= tau) == nfharness hypothesis_mask(p_seg, tau, L) per segment; -inf elsewhere."""
    out = np.full(lay.T, -np.inf)
    for j, L in enumerate(lay.L):
        n = int(L) - 1
        ps = p[lay.woff[j]:lay.woff[j] + n]
        q = np.full(n, -np.inf)
        if n >= 4:
            q[3] = ps[:4].min()
        if n >= 5:
            w = np.lib.stride_tricks.sliding_window_view(ps, 5)
            q[4:] = np.partition(w, 1, axis=1)[:, 1]          # >= 4 of 5 above tau  <=>  2nd smallest >= tau
        s0 = int(lay.soff[j])
        out[s0 + 1:s0 + 1 + min(n, int(L) - 1)] = q[:int(L) - 1]
    return out


def _runs_2d(B):
    """Row-wise runs of True in a 2-D bool array -> (row, start, end) sorted row-major."""
    Z = np.zeros((B.shape[0], 1), dtype=np.int8)
    D = np.diff(np.concatenate([Z, B.astype(np.int8), Z], axis=1), axis=1)
    r1, c1 = np.nonzero(D == 1)
    _, c2 = np.nonzero(D == -1)
    return r1, c1, c2


def _merge_split(r, st, en):
    """90-s merge then 300-s split, per row. Returns merged (row, st, en) and split pieces (row, st, en)."""
    if st.size == 0:
        e = np.zeros(0, dtype=np.int64)
        return (e, e, e), (e, e, e)
    new = np.ones(st.size, dtype=bool)
    new[1:] = (r[1:] != r[:-1]) | ((st[1:] - en[:-1]) >= MERGE)
    first = np.flatnonzero(new)
    last = np.concatenate([first[1:] - 1, [st.size - 1]])
    mr, ms, me = r[first], st[first], en[last]
    npc = -(-(me - ms) // SPLIT)
    pr = np.repeat(mr, npc)
    base = np.repeat(ms, npc)
    k = np.arange(npc.sum()) - np.repeat(np.cumsum(npc) - npc, npc)
    ps = base + SPLIT * k
    pe = np.minimum(ps + SPLIT, np.repeat(me, npc))
    return (mr, ms, me), (pr, ps, pe)


def events_counts_all_taus(qm, hours):
    """Scored (merged+split) event count per grid tau / hours -> rate array (len 95)."""
    B = qm[None, :] >= TAUS[:, None]
    r, s, e = _runs_2d(B)
    _, (pr, _, _) = _merge_split(r, s, e)
    return np.bincount(pr, minlength=TAUS.size) / hours


def rate_matched_tau(qm_train, hours):
    rate = events_counts_all_taus(qm_train, hours)
    ok = np.flatnonzero(rate <= RATE_TARGET)
    if ok.size:
        return float(TAUS[ok[0]]), False
    return 0.99, True


class Hyp:
    """A fixed hypothesis on the seconds axis: merged coverage cumsum + split pieces (for TP / FP of any placement)."""

    def __init__(self, qm, tau):
        B = (qm >= tau)[None, :]
        r, s, e = _runs_2d(B)
        (_, ms, me), (_, ps, pe) = _merge_split(r, s, e)
        cov = np.zeros(qm.size + 1, dtype=np.int64)
        np.add.at(cov, ms, 1)
        np.add.at(cov, me, -1)
        self.cc = np.concatenate([[0], np.cumsum(np.cumsum(cov)[:-1] > 0)])
        self.ps, self.pe = ps, pe
        self.n_pieces = int(ps.size)
        self.coverage_s = int(self.cc[-1])


def event_stats(h, lay, J, O, D):
    """TP, FP, F1 for placements J, O (M x K), durations D (K)."""
    a = lay.soff[J] + O - PRE
    b = lay.soff[J] + O + D[None, :] + POST
    tp = ((h.cc[b] - h.cc[a]) > 0).sum(axis=1)
    if h.n_pieces:
        i0 = np.searchsorted(h.pe, a, side="right")
        i1 = np.searchsorted(h.ps, b, side="left")
        i1 = np.maximum(i1, i0)
        order = np.argsort(i0, axis=1, kind="stable")
        i0s = np.take_along_axis(i0, order, 1)
        i1s = np.take_along_axis(i1, order, 1)
        run = np.maximum.accumulate(i1s, axis=1)
        prev = np.concatenate([np.zeros((i0s.shape[0], 1), dtype=np.int64), run[:, :-1]], axis=1)
        cover = np.maximum(0, i1s - np.maximum(i0s, prev)).sum(axis=1)
        fp = h.n_pieces - cover
    else:
        fp = np.zeros(J.shape[0], dtype=np.int64)
    K = J.shape[1]
    den = 2 * tp + fp + (K - tp)
    f1 = np.where(den > 0, 2 * tp / np.maximum(den, 1), 0.0)
    return tp, fp, f1


class Ranks:
    def __init__(self, p):
        self.cr = np.concatenate([[0.0], np.cumsum(rankdata(p))])
        self.N = p.size

    def auroc(self, lay, J, O, D):
        w0 = lay.woff[J] + O
        R1 = (self.cr[w0 + D[None, :] - 1] - self.cr[w0]).sum(axis=1)
        n1 = float((D - 1).sum())
        n0 = self.N - n1
        return (R1 - n1 * (n1 + 1) / 2.0) / (n1 * n0)


# ============================================================================ sampler S_J (joint-uniform, rejection)
def sample_SJ(g, lay, D, M):
    """M independent placements of K phantoms (durations D): each phantom uniform on its own valid set
    {(j, o): PRE <= o <= L_j - d - POST}; the whole configuration is redrawn until every same-segment pair has a gap
    >= MINGAP. Returns (J, O) as (M, K) int arrays."""
    K = D.size
    cnt = np.maximum(0, lay.L[None, :] - D[:, None] - POST - PRE + 1)          # K x nseg
    cum = np.cumsum(cnt, axis=1)
    tot = cum[:, -1]
    if np.any(tot <= 0):
        raise ValueError("a phantom does not fit in any segment")
    J = np.empty((M, K), dtype=np.int64)
    O = np.empty((M, K), dtype=np.int64)
    todo = np.arange(M)
    tries = 0
    while todo.size:
        tries += 1
        if tries > 10000:
            raise RuntimeError("sampler S_J: acceptance too low (layout too dense)")
        m = todo.size
        u = (g.random((m, K)) * tot[None, :]).astype(np.int64)
        j = np.empty((m, K), dtype=np.int64)
        o = np.empty((m, K), dtype=np.int64)
        for k in range(K):
            jj = np.searchsorted(cum[k], u[:, k], side="right")
            start = cum[k][jj] - cnt[k][jj]
            j[:, k] = jj
            o[:, k] = PRE + u[:, k] - start
        ok = np.ones(m, dtype=bool)
        for k in range(K):
            for l in range(k + 1, K):
                same = j[:, k] == j[:, l]
                sep = (o[:, k] + D[k] + MINGAP <= o[:, l]) | (o[:, l] + D[l] + MINGAP <= o[:, k])
                ok &= ~same | sep
        J[todo[ok]] = j[ok]
        O[todo[ok]] = o[ok]
        todo = todo[~ok]
    return J, O


def phantom_window_mask(lay, J, O, D):
    m = np.zeros(lay.N, dtype=bool)
    for j, o, d in zip(J, O, D):
        w0 = int(lay.woff[j] + o)
        m[w0:w0 + int(d) - 1] = True
    return m


# ============================================================================ self-tests against the harness code
def self_test():
    g = rng(99)
    P = SURROGATES["calibrated"]
    lay = Layout([900, 1500, 700])
    p = to_scores(latent(g, lay, P), -0.4, 1.0)
    qm = qm_series(p, lay)
    n_checked = 0
    for tau in (0.3, 0.5, 0.7, 0.9):
        h = Hyp(qm, tau)
        for j, L in enumerate(lay.L):
            ps = p[lay.woff[j]:lay.woff[j] + L - 1]
            ref = hypothesis_mask(ps, tau, int(L))
            mine = (qm[lay.soff[j]:lay.soff[j] + L] >= tau).astype(np.int8)
            assert np.array_equal(ref, mine), "k-of-n mismatch"
        D = np.array([52, 90, 47])
        J, O = sample_SJ(g, lay, D, 200)
        tp, fp, f1 = event_stats(h, lay, J, O, D)
        for m in range(200):
            TP = FP = NR = 0
            for j, L in enumerate(lay.L):
                ref = np.zeros(int(L), dtype=np.int8)
                for k in range(3):
                    if J[m, k] == j:
                        ref[O[m, k]:O[m, k] + D[k]] = 1
                hm = (qm[lay.soff[j]:lay.soff[j] + L] >= tau).astype(np.int8)
                e = reimpl_event_score(ref, hm)
                TP, FP, NR = TP + e["tp"], FP + e["fp"], NR + e["n_ref"]
            assert (TP, FP, NR) == (tp[m], fp[m], 3), ("event mismatch", tau, m, TP, FP, tp[m], fp[m])
            n_checked += 1
        n_ev = sum(n1b_n_events((qm[lay.soff[j]:lay.soff[j] + L] >= tau).astype(np.int8)) for j, L in enumerate(lay.L))
        assert n_ev == h.n_pieces, "event count mismatch"
        rk = Ranks(p)
        au = rk.auroc(lay, J[:5], O[:5], D)
        from nfharness import stats
        for m in range(5):
            y = phantom_window_mask(lay, J[m], O[m], D).astype(np.int8)
            assert abs(stats.auroc(y, p) - au[m]) < 1e-12, "auroc mismatch"
    # rate-matched tau vs a direct per-tau loop with the n1b event counter
    H = lay.hours
    t, _ = rate_matched_tau(qm, H)
    direct = 0.99
    for tau in TAUS:
        n = sum(n1b_n_events((qm[lay.soff[j]:lay.soff[j] + L] >= tau).astype(np.int8)) for j, L in enumerate(lay.L))
        if n / H <= RATE_TARGET:
            direct = float(tau)
            break
    assert t == direct, "t_rm mismatch"
    # S_J on a tiny fixture: joint-uniform over the enumerated valid configurations (chi-square)
    small = Layout([700, 500])
    D2 = np.array([60, 40])
    J, O = sample_SJ(g, small, D2, 60000)
    # exact enumeration of the valid joint configurations, bucketed as (j1, j2, o1 // 50, o2 // 50)
    expc, nvalid = {}, 0
    for j1 in range(2):
        for o1 in range(PRE, int(small.L[j1]) - 60 - POST + 1):
            for j2 in range(2):
                for o2 in range(PRE, int(small.L[j2]) - 40 - POST + 1):
                    if j1 == j2 and not (o1 + 60 + MINGAP <= o2 or o2 + 40 + MINGAP <= o1):
                        continue
                    b = (j1, j2, o1 // 50, o2 // 50)
                    expc[b] = expc.get(b, 0) + 1
                    nvalid += 1
    obsc = {b: 0 for b in expc}
    for a, b_, c, d in zip(J[:, 0], O[:, 0], J[:, 1], O[:, 1]):
        obsc[(int(a), int(c), int(b_) // 50, int(d) // 50)] += 1     # KeyError here = an invalid configuration
    e = np.array([expc[b] for b in expc], dtype=float) / nvalid * J.shape[0]
    o_ = np.array([obsc[b] for b in expc], dtype=float)
    X = ((o_ - e) ** 2 / e).sum()
    p_chi = float(chi2.sf(X, e.size - 1))
    assert p_chi > 1e-4, "S_J not uniform (p=%g)" % p_chi
    return {"event_placements_checked_vs_reimpl": n_checked, "kofn_bitwise": True, "t_rm_match": True,
            "auroc_vs_nfharness_stats": True, "S_J_bucketed_chi2_p": p_chi, "S_J_buckets": int(e.size),
            "S_J_min_expected": float(e.min()), "S_J_valid_configs": nvalid}


# ============================================================================ surrogates
# Nuisance parameters of the honest score process. "calibrated" is chosen (by the calibrate stage below, from this
# fixed candidate list) as the one closest to the N1b NC-P / PL-A replicate summaries; "harsh" is a deliberately
# burstier, more mismatched process used as a robustness check.
SURROGATES = {
    "calibrated": {"rho": 0.90, "rho_slow": 0.999, "slow_w": 0.5, "burst_rate_h": 2.0, "burst_dur": (5, 60),
                   "burst_amp": (1.5, 3.5), "mis_sd": 1.2, "mu": -0.4, "sig_lo": 0.4, "sig_hi": 1.6},
}
CANDIDATES = []
for rho in (0.90, 0.97):
    for cp in (0.15, 0.30):
        for cs in (-4.0, -6.0):
            CANDIDATES.append({"rho": rho, "rho_slow": 0.999, "slow_w": 0.3, "burst_rate_h": 2.0, "burst_dur": (5, 60),
                               "burst_amp": (1.5, 3.5), "mis_sd": 1.0, "mu": -0.4, "sig_lo": 0.4, "sig_hi": 1.6,
                               "collapse_p": cp, "collapse_shift": cs})


def durations(K):
    return np.array([DUR_CYCLE[k % len(DUR_CYCLE)] for k in range(K)], dtype=np.int64)


# ============================================================================ one fit (one replicate of the harness)
def one_fit(key, P, H, K, delta, G, M, plb=True):
    """key: rng key; P: surrogate; H: allowed test hours; K: phantoms per draw; delta: PL-A latent shift (0 = honest);
    G: PL-B phantom draws on this (honest) fit. Returns a dict of observed stats and null arrays."""
    g = rng(*key)
    te = Layout(tile(H))
    tr = Layout(tile(TRAIN_H))
    D = durations(K)
    sig = g.uniform(P["sig_lo"], P["sig_hi"])
    mis = g.normal(0.0, P["mis_sd"])
    if g.random() < P.get("collapse_p", 0.0):          # null model collapses on the test period (scores pinned low)
        mis = g.normal(P["collapse_shift"], 1.0) / sig
    ztr = latent(g, tr, P)
    t_rm, flag = rate_matched_tau(qm_series(to_scores(ztr, P["mu"], sig), tr), tr.hours)
    J0, O0 = sample_SJ(g, te, D, 1)                              # the "test phantoms" of this replicate
    zte = latent(g, te, P, shift=mis)
    if delta:
        zte = zte + delta * phantom_window_mask(te, J0[0], O0[0], D)
    p = to_scores(zte, P["mu"], sig)
    qm = qm_series(p, te)
    h = Hyp(qm, t_rm)
    rk = Ranks(p)
    Jn, On = sample_SJ(g, te, D, M)                              # null placements (stream-12 analogue)
    ta_obs = float(rk.auroc(te, J0, O0, D)[0])
    ta_null = rk.auroc(te, Jn, On, D)
    tp0, fp0, f10 = event_stats(h, te, J0, O0, D)
    tpn, fpn, f1n = event_stats(h, te, Jn, On, D)
    never = h.n_pieces == 0
    always = h.coverage_s >= 0.5 * te.L.sum()
    mu0, sd0 = tp_mu_sd(g, h, te, D)
    out = {"t_rm": t_rm, "t_rm_flag": flag, "n_events": h.n_pieces, "events_per_h": h.n_pieces / te.hours,
           "coverage": h.coverage_s / float(te.L.sum()), "degenerate": bool(never or always), "never": bool(never),
           "TA": ta_obs, "pA_up": (1 + int((ta_null >= ta_obs).sum())) / (M + 1),
           "pA_lo": (1 + int((ta_null <= ta_obs).sum())) / (M + 1),
           "TP": int(tp0[0]), "FP": int(fp0[0]), "F1": float(f10[0]),
           "pE_up": (1 + int((f1n >= f10[0]).sum())) / (M + 1),
           "TPn": tpn.astype(np.int16), "F1n": f1n.astype(np.float32), "K": K,
           "zTP": float(zsc(tp0[0], mu0, sd0)), "zTPn": zsc(tpn, mu0, sd0).astype(np.float32)}
    if plb and G > 0:
        # PL-B: G independent test-phantom draws on this honest fit; for each, tau = argmax over the grid of event F1
        # against THAT draw (ties -> smallest tau), then the same pooled conditional test at the chosen h.
        hs = [Hyp(qm, float(t)) for t in TAUS]
        Jg, Og = sample_SJ(g, te, D, G)
        f1_tau = np.stack([event_stats(hh, te, Jg, Og, D)[2] for hh in hs], axis=1)    # G x 95
        best = np.argmax(f1_tau, axis=1)
        b_tp, b_f1, b_TPn, b_F1n, b_p, b_tau, b_deg = [], [], [], [], [], [], []
        h_tp, h_f1, h_TPn, h_F1n = [], [], [], []
        for gi in range(G):
            hb = hs[best[gi]]
            tp, fp, f1 = event_stats(hb, te, Jg[gi:gi + 1], Og[gi:gi + 1], D)
            Jb, Ob = sample_SJ(g, te, D, M)
            tpn2, _, f1n2 = event_stats(hb, te, Jb, Ob, D)
            b_tp.append(int(tp[0]))
            b_f1.append(float(f1[0]))
            b_TPn.append(tpn2.astype(np.int16))
            b_F1n.append(float(f1n2.mean()))
            b_p.append((1 + int((f1n2 >= f1[0]).sum())) / (M + 1))
            b_tau.append(float(TAUS[best[gi]]))
            b_deg.append(bool(hb.n_pieces == 0 or hb.coverage_s >= 0.5 * te.L.sum()))
            tph, _, f1h = event_stats(h, te, Jg[gi:gi + 1], Og[gi:gi + 1], D)       # same draw, honest t_rm
            tpnh, _, f1nh = event_stats(h, te, Jb, Ob, D)
            h_tp.append(int(tph[0]))
            h_f1.append(float(f1h[0]))
            h_TPn.append(tpnh.astype(np.int16))
            h_F1n.append(float(f1nh.mean()))
        out["PLB"] = {"TP": np.array(b_tp), "F1": np.array(b_f1), "TPn": np.stack(b_TPn), "F1n_mean": np.array(b_F1n),
                      "p": np.array(b_p), "tau": np.array(b_tau), "deg": np.array(b_deg),
                      "hTP": np.array(h_tp), "hF1": np.array(h_f1), "hTPn": np.stack(h_TPn), "hF1n_mean": np.array(h_F1n)}
    return out


M_STD = 500     # separate null draws used only to standardise TP (keeps the pooled z-statistic exact)


def tp_mu_sd(g, h, te, D):
    J, O = sample_SJ(g, te, D, M_STD)
    tp = event_stats(h, te, J, O, D)[0].astype(np.float64)
    return float(tp.mean()), float(tp.std())


def zsc(x, mu, sd):
    return (np.asarray(x, dtype=np.float64) - mu) / sd if sd > 0 else np.zeros_like(np.asarray(x, dtype=np.float64))

# ============================================================================ C3' / PL-C (random-alarm null, real refs)
PLC_PROB = 0.25


def c3_layout(g, n_ref, n_free, lam_h, T=3600):
    """Seizure files (one reference each, CHB-MIT-like duration, onset in [600, T-600)) + seizure-free files; the
    'model hypothesis' per file = Poisson(lam_h) raw alarm runs of 10-60 s, circularly >= 300 s apart."""
    files = []
    for i in range(n_ref + n_free):
        refs = []
        if i < n_ref:
            d = DUR_CYCLE[i % len(DUR_CYCLE)]
            on = int(g.integers(600, T - 600 - d))
            refs = [(on, on + d)]
        n = int(g.poisson(lam_h * T / 3600.0))
        ev = []
        for _ in range(200):
            if len(ev) == n:
                break
            s = int(g.integers(0, T))
            L = int(g.integers(10, 61))
            if all(min((s - s2) % T, (s2 - s) % T) >= 300 + 60 for s2, _ in ev):
                ev.append((s, L))
        ev.sort()
        files.append((T, ev, refs))
    return files


def offset_counts(T, ev, refs):
    """TP_f(o), FP_f(o) for every circular offset o of the file's alarm runs (runs >= 360 s apart circularly, so the
    90-s merge never acts; runs <= 60 s, so the 300-s split never acts; a run crossing the end wraps into 2 pieces)."""
    o = np.arange(T)
    if not ev:
        return np.zeros(T, dtype=np.int64), np.zeros(T, dtype=np.int64)
    S = (np.array([s for s, _ in ev])[None, :] + o[:, None]) % T          # T x E
    Ln = np.array([L for _, L in ev])[None, :]
    E1 = np.minimum(S + Ln, T)
    wrap = (S + Ln) > T
    P2e = np.where(wrap, S + Ln - T, 0)                                   # second piece [0, P2e) if wrap
    tp = np.zeros(T, dtype=np.int64)
    hit_piece1 = np.zeros(S.shape, dtype=bool)
    hit_piece2 = np.zeros(S.shape, dtype=bool)
    for a, b in refs:
        xa, xb = max(0, a - PRE), min(T, b + POST)
        h1 = (S < xb) & (E1 > xa)
        h2 = wrap & (0 < xb) & (P2e > xa)
        tp += (h1 | h2).any(axis=1)
        hit_piece1 |= h1
        hit_piece2 |= h2
    fp = (~hit_piece1).sum(axis=1) + (wrap & ~hit_piece2).sum(axis=1)
    return tp, fp


def c3_power_one(g, n_ref, n_free, lam_h, M_C=1000):
    files = c3_layout(g, n_ref, n_free, lam_h)
    joint = np.ones((1, 1))
    per = []
    for T, ev, refs in files:
        tp, fp = offset_counts(T, ev, refs)
        per.append((tp, fp, T, ev, refs))
        H = np.zeros((tp.max() + 1, fp.max() + 1))
        np.add.at(H, (tp, fp), 1.0 / T)
        from scipy.signal import convolve2d
        joint = convolve2d(joint, H)
    TPg, FPg = np.meshgrid(np.arange(joint.shape[0]), np.arange(joint.shape[1]), indexing="ij")
    den = 2 * TPg + FPg + (n_ref - TPg)
    F1g = np.where(den > 0, 2 * TPg / np.maximum(den, 1), 0.0)
    f = F1g.ravel()
    w = joint.ravel()
    order = np.argsort(f, kind="stable")
    fv, wv = f[order], w[order]
    cum = np.cumsum(wv)
    q95 = float(fv[np.searchsorted(cum, 0.95 - 1e-12)])
    a_star = float(w[f > q95 + 1e-12].sum())
    mu = float((f * w).sum())
    TP = np.zeros(M_C, dtype=np.int64)
    FP = np.zeros(M_C, dtype=np.int64)
    TPh = np.zeros(M_C, dtype=np.int64)
    FPh = np.zeros(M_C, dtype=np.int64)
    for tp, fp, T, ev, refs in per:
        o = g.integers(0, T, M_C)
        TPh += tp[o]
        FPh += fp[o]
        if refs and ev:
            force = g.random(M_C) < PLC_PROB
            o2 = np.where(force, (refs[0][0] - ev[0][0]) % T, o)
        else:
            o2 = o
        TP += tp[o2]
        FP += fp[o2]
    def f1(tp, fp):
        d = 2 * tp + fp + (n_ref - tp)
        return np.where(d > 0, 2 * tp / np.maximum(d, 1), 0.0)
    bound = a_star + 3 * math.sqrt(a_star * (1 - a_star) / M_C)
    frac_plc = float((f1(TP, FP) > q95 + 1e-12).mean())
    frac_h = float((f1(TPh, FPh) > q95 + 1e-12).mean())
    return {"trip": frac_plc > bound, "honest_ii_fail": frac_h > bound, "a_star": a_star, "q95": q95, "mu": mu,
            "frac_plc": frac_plc}


def c3_power(tag, n_ref, n_free, lam_h, n_lay=100):
    g = rng(hash_tag(tag))
    rs = [c3_power_one(g, n_ref, n_free, lam_h) for _ in range(n_lay)]
    return {"N_ref": n_ref, "n_free_files": n_free, "alarm_rate_h": lam_h, "n_layouts": n_lay,
            "P_trip_PLC": float(np.mean([r["trip"] for r in rs])),
            "P_honest_fails_ii": float(np.mean([r["honest_ii_fail"] for r in rs])),
            "a_star_median": float(np.median([r["a_star"] for r in rs])),
            "frac_plc_median": float(np.median([r["frac_plc"] for r in rs]))}


def _worker(args):
    return [one_fit(*a) for a in args]


# ============================================================================ experiment-level tests
def pooled_p(obs_sum, null_sum):
    M = null_sum.size
    return (1 + int((null_sum >= obs_sum - 1e-9).sum())) / (M + 1)


def experiment_pvalues(fits, arm="NCP", G=1):
    """fits: list of fit dicts forming one experiment (S subjects x R fits).
    Returns p-values of: window Fisher (up), event N1b-style Fisher (non-degenerate), pooled sum TP, pooled sum F1."""
    if arm in ("PLB", "PLBhalf"):
        # PLBhalf: only every 2nd draw is leaked (the others keep the honest t_rm) -> about half the selection gain,
        # a conservative stand-in for the real N1b PL-B gain (see calibration)
        def pick(f, a, b):
            x, y = f["PLB"][a][:G], f["PLB"][b][:G]
            if arm == "PLB":
                return x
            sel = (np.arange(x.shape[0]) % 2 == 0)
            return np.where(sel.reshape((-1,) + (1,) * (x.ndim - 1)), x, y)
        TP = np.concatenate([pick(f, "TP", "hTP") for f in fits])
        TPn = np.concatenate([pick(f, "TPn", "hTPn") for f in fits]).astype(np.int64).sum(axis=0)
        ps = np.concatenate([f["PLB"]["p"][:G][~f["PLB"]["deg"][:G]] for f in fits]) if arm == "PLB" else np.zeros(0)
        return {"E_fisher": fisher(list(ps))[0] if ps.size else 1.0,
                "E_sumTP": pooled_p(TP.sum(), TPn), "n_draws": int(TP.size)}
    pa = [f["pA_up"] for f in fits]
    pe = [f["pE_up"] for f in fits if not f["degenerate"]]
    TP = sum(f["TP"] for f in fits)
    F1 = sum(f["F1"] for f in fits)
    TPn = np.sum([f["TPn"].astype(np.int64) for f in fits], axis=0)
    F1n = np.sum([f["F1n"].astype(np.float64) for f in fits], axis=0)
    Z = sum(f["zTP"] for f in fits)
    Zn = np.sum([f["zTPn"].astype(np.float64) for f in fits], axis=0)
    return {"E_zTP": pooled_p(Z, Zn), "A_fisher": fisher(pa)[0], "A_fisher_lo": fisher([f["pA_lo"] for f in fits])[0],
            "E_fisher": fisher(pe)[0] if pe else 1.0,
            "E_sumTP": pooled_p(TP, TPn), "E_sumF1": pooled_p(F1, F1n), "n_deg": sum(f["degenerate"] for f in fits)}


def size_disjoint(pool, n_fits, g):
    """Honest-harness rejection rate from DISJOINT experiments only (resampled experiments share fits and are
    correlated, so they cannot estimate a 0.25% size). Low resolution: n_pool / n_fits experiments."""
    idx = g.permutation(len(pool))
    n = len(pool) // n_fits
    keys = ["A_fisher", "A_fisher_lo", "E_fisher", "E_sumTP", "E_zTP"]
    rej = {k: 0 for k in keys}
    for e in range(n):
        r = experiment_pvalues([pool[i] for i in idx[e * n_fits:(e + 1) * n_fits]])
        for k in keys:
            rej[k] += int(r[k] < ALPHA)
    return {"n_experiments": n, **{k: rej[k] / max(n, 1) for k in keys}}


def power(pool, n_fits, n_exp, g, arm="NCP", G=1):
    keys = {"NCP": ["A_fisher", "E_fisher", "E_sumTP", "E_sumF1", "E_zTP"],
            "PLB": ["E_fisher", "E_sumTP"], "PLBhalf": ["E_sumTP"]}[arm]
    hits = {k: 0 for k in keys}
    for _ in range(n_exp):
        idx = g.choice(len(pool), size=n_fits, replace=n_fits > len(pool))
        r = experiment_pvalues([pool[i] for i in idx], arm, G)
        for k in keys:
            hits[k] += int(r[k] < ALPHA)
    return {k: hits[k] / n_exp for k in keys}


# ============================================================================ calibration against N1b summaries
N1B_TARGETS = {   # from results\N1b_card.json (real data, NC-P 30 replicates, PL-A 15 replicates)
    "ncp_never_frac": 7 / 30, "ncp_hit_rate": 17 / 120, "ncp_events_per_h_median": 0.96,
    "ncp_tA_sd": 0.118, "pla_auroc_mean": 0.775, "pla_hit_rate": 19 / 60, "pla_never_frac": 4 / 15,
    "plb_F1_mean": 0.136, "plb_gain_mean": 0.042, "plb_F1_zero_frac": 5 / 30,
}


def summarise(fits):
    ev = np.array([f["events_per_h"] for f in fits])
    extra = {}
    if "PLB" in fits[0]:
        F = np.array([f["PLB"]["F1"][0] for f in fits])
        extra = {"plb_F1_mean": float(F.mean()), "plb_F1_zero_frac": float((F == 0).mean()),
                 "plb_gain_mean": float(np.mean([f["PLB"]["F1"][0] - f["PLB"]["F1n_mean"][0] for f in fits])),
                 "plb_p_median": float(np.median([f["PLB"]["p"][0] for f in fits]))}
    return {**extra, "never_frac": float(np.mean([f["never"] for f in fits])),
            "hit_rate": float(sum(f["TP"] for f in fits) / sum(f["K"] for f in fits)),
            "events_per_h_median": float(np.median(ev)), "events_per_h_q90": float(np.quantile(ev, 0.9)),
            "t_rm_flag_frac": float(np.mean([f["t_rm_flag"] for f in fits])),
            "TA_mean": float(np.mean([f["TA"] for f in fits])), "TA_sd": float(np.std([f["TA"] for f in fits], ddof=1))}


def run_pool(pool_exec, P, H, K, delta, G, n, tag, M=M_NULL, plb=True):
    args = [((hash_tag(tag), i), P, H, K, delta, G, M, plb) for i in range(n)]
    chunks = [args[i::pool_exec._processes] for i in range(pool_exec._processes)] if pool_exec else [args]
    if pool_exec:
        res = pool_exec.map(_worker, chunks)
        out = [x for c in res for x in c]
    else:
        out = _worker(args)
    return out


def hash_tag(tag):
    return int(hashlib.sha256(tag.encode()).hexdigest()[:8], 16)


def calibrate_delta(pool_exec, P, target_auc, H=6.0, K=4, n=48):
    lo, hi = 0.0, 3.0
    for _ in range(9):
        mid = (lo + hi) / 2
        fits = run_pool(pool_exec, P, H, K, mid, 0, n, "cal-delta-%g-%g" % (target_auc, mid), M=199, plb=False)
        if np.mean([f["TA"] for f in fits]) < target_auc:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 3)

DESIGNS = [(1, 10), (1, 20), (2, 10), (2, 20), (3, 5), (3, 10), (3, 20), (4, 10), (6, 10)]
G_PLB = 10


def run_cell(job):
    sname, P, H, K, dl, n_pool, n_exp = job
    tag = "%s-H%g-K%d" % (sname, H, K)
    ncp = run_pool(None, P, H, K, 0.0, G_PLB, n_pool, tag + "-ncp")
    pla = run_pool(None, P, H, K, dl["PL-A"], 0, n_pool, tag + "-pla", plb=False)
    plw = run_pool(None, P, H, K, dl["PL-A-weak"], 0, n_pool, tag + "-plw", plb=False)
    gexp = rng(31, hash_tag(tag))
    cell = {"surrogate": sname, "H_test_allowed_h": H, "K_phantoms_per_draw": K, "n_pool": n_pool, "n_exp": n_exp,
            "ncp_summary": summarise(ncp), "pla_summary": summarise(pla), "plw_summary": summarise(plw),
            "plb_hit_rate": float(np.mean([f["PLB"]["TP"].mean() / K for f in ncp])),
            "plb_gain_mean_allG": float(np.mean([(f["PLB"]["F1"] - f["PLB"]["F1n_mean"]).mean() for f in ncp])),
            "ncp_pA_up_KS_p": float(kstest([f["pA_up"] for f in ncp], "uniform").pvalue),
            "ncp_pE_up_mean_nondeg": float(np.mean([f["pE_up"] for f in ncp if not f["degenerate"]])),
            "ncp_TP_minus_null_mean": float(np.mean([f["TP"] - f["TPn"].mean() for f in ncp])),
            "designs": []}
    for (S, Rr) in DESIGNS:
        nf = S * Rr
        row = {"S": S, "R": Rr, "fits": nf, "phantoms_event_arm": nf * K}
        row["NCP_size_disjoint"] = size_disjoint(ncp, nf, gexp)
        row["PL-A"] = power(pla, nf, n_exp, gexp)
        row["PL-A-weak"] = power(plw, nf, n_exp, gexp)
        for gg in (1, G_PLB):
            row["PL-B_G%d" % gg] = power(ncp, nf, n_exp, gexp, arm="PLB", G=gg)
            row["PL-B-half_G%d" % gg] = power(ncp, nf, n_exp, gexp, arm="PLBhalf", G=gg)
        cell["designs"].append(row)
    return cell


# ============================================================================ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    import multiprocessing as mp
    pool_exec = mp.Pool(args.workers) if args.workers > 1 else None
    R = {"status": "RESEARCH USE ONLY. NOT A MEDICAL DEVICE. Synthetic surrogate only; no EEG read.", "seed": SEED,
         "alpha": ALPHA, "M_null": M_NULL, "rate_target": RATE_TARGET}
    R["self_test"] = self_test()
    print("self-test", R["self_test"], flush=True)
    q = args.quick
    n_cal = 40 if q else 90

    # ---- 1. calibrate the nuisance surrogate to N1b (NC-P summaries) from the fixed candidate list
    cal = []
    for ci, P in enumerate(CANDIDATES):
        fits = run_pool(pool_exec, P, 5.0, 4, 0.0, 1, n_cal, "cal-%d" % ci, M=199)
        s = summarise(fits)
        T = N1B_TARGETS
        dist = (abs(s["never_frac"] - T["ncp_never_frac"]) / 0.08 + abs(s["hit_rate"] - T["ncp_hit_rate"]) / 0.04
                + abs(math.log((s["events_per_h_median"] + 0.1) / (T["ncp_events_per_h_median"] + 0.1))) / 0.5
                + abs(s["TA_sd"] - T["ncp_tA_sd"]) / 0.02
                + abs(s["plb_gain_mean"] - T["plb_gain_mean"]) / 0.02 + abs(s["plb_F1_zero_frac"] - T["plb_F1_zero_frac"]) / 0.08)
        cal.append({"candidate": ci, "params": P, "summary": s, "distance": dist})
        print("cal", ci, {k: round(v, 3) for k, v in s.items()}, round(dist, 2), flush=True)
    best = min(cal, key=lambda c: c["distance"])
    harsh = max(cal, key=lambda c: c["summary"]["never_frac"])       # most degenerate candidate = hardest event arm
    SURR = {"calibrated": best["params"], "harsh": harsh["params"]}
    R["calibration"] = {"targets": N1B_TARGETS, "candidates": cal, "chosen": best["candidate"],
                        "harsh": harsh["candidate"]}

    # ---- 2. leak strengths: PL-A strong (= N1b real AUROC 0.775) and realistic (AUROC 0.62, ~Brookshire-size gap)
    deltas = {}
    for name, P in SURR.items():
        deltas[name] = {"PL-A": calibrate_delta(pool_exec, P, 0.775), "PL-A-weak": calibrate_delta(pool_exec, P, 0.62)}
    R["deltas"] = deltas
    print("deltas", deltas, flush=True)
    # PL-A check vs N1b event numbers (calibrated surrogate, N1b-like layout H=5 h, K=4)
    chk = run_pool(pool_exec, SURR["calibrated"], 5.0, 4, deltas["calibrated"]["PL-A"], 0, n_cal, "chk-pla", M=199,
                   plb=False)
    R["calibration"]["PL-A_check"] = summarise(chk)
    print("PL-A check", R["calibration"]["PL-A_check"], flush=True)

    # ---- 2b. validity (size) of the combination rules under the honest calibrated surrogate, DISJOINT experiments
    nsz = 600 if q else 1800
    fits = run_pool(pool_exec, SURR["calibrated"], 6.0, 4, 0.0, 0, nsz, "size", plb=False)
    pa = np.array([f["pA_up"] for f in fits])
    pl = np.array([f["pA_lo"] for f in fits])
    R["size_check"] = {"n_fits": nsz, "KS_pA_up": float(kstest(pa, "uniform").pvalue),
                       "KS_pA_lo": float(kstest(pl, "uniform").pvalue),
                       "frac_pA_up_le_0.01": float((pa <= 0.01).mean()),
                       "fisher_A_up_reject_rate_10fits": float(np.mean([fisher(list(pa[i:i + 10]))[0] < ALPHA
                                                                         for i in range(0, nsz, 10)])),
                       "fisher_A_lo_reject_rate_10fits": float(np.mean([fisher(list(pl[i:i + 10]))[0] < ALPHA
                                                                         for i in range(0, nsz, 10)])),
                       "sumTP_reject_rate_30fits": float(np.mean([experiment_pvalues(fits[i:i + 30])["E_sumTP"] < ALPHA
                                                                   for i in range(0, nsz, 30)])),
                       "n_fisher_experiments": nsz // 10, "n_sumTP_experiments": nsz // 30}
    print("size", R["size_check"], flush=True)
    del fits

    # ---- 3a. C3' / PL-C power vs the number of REAL test references (pooled over subjects)
    R["C3prime_PLC"] = []
    for nr in ((2, 4, 8) if q else (1, 2, 3, 4, 6, 8, 12)):
        for lam in (0.5, 1.3, 3.0):
            r = c3_power("c3-%d-%g" % (nr, lam), nr, 4, lam, n_lay=40 if q else 150)
            R["C3prime_PLC"].append(r)
            print("C3prime", r, flush=True)

    # ---- 3b. NC-P pools per layout cell and power over designs (one cell per worker process)
    cells = [(2.0, 2), (2.0, 4), (4.0, 4), (4.0, 8), (4.0, 12), (6.0, 4), (6.0, 12), (8.0, 8), (8.0, 16)]
    harsh_cells = [(4.0, 8), (4.0, 12), (6.0, 12), (8.0, 16)]
    if q:
        cells, harsh_cells = [(6.0, 4)], []
    n_pool = 60 if q else 400
    n_exp = 200 if q else 300
    jobs = [("calibrated", SURR["calibrated"], H, K, deltas["calibrated"], n_pool, n_exp) for H, K in cells]
    jobs += [("harsh", SURR["harsh"], H, K, deltas["harsh"], n_pool, n_exp) for H, K in harsh_cells]
    R["power"] = pool_exec.map(run_cell, jobs, chunksize=1) if pool_exec else [run_cell(j) for j in jobs]
    for cell in R["power"]:
        print("cell %s H%g K%d  never %.2f hit %.3f | PL-A hit %.3f AUROC %.3f | weak AUROC %.3f | KS(pA) %.2f" % (
            cell["surrogate"], cell["H_test_allowed_h"], cell["K_phantoms_per_draw"],
            cell["ncp_summary"]["never_frac"], cell["ncp_summary"]["hit_rate"], cell["pla_summary"]["hit_rate"],
            cell["pla_summary"]["TA_mean"], cell["plw_summary"]["TA_mean"], cell["ncp_pA_up_KS_p"]))
        for row in cell["designs"]:
            print("   S%d R%d n_ph=%d  PL-A %s | weak %s | PL-B1 %s | half1 %s | PL-B10 %s | half10 %s | size %s" % (
                row["S"], row["R"], row["phantoms_event_arm"],
                _fmt(row["PL-A"]), _fmt(row["PL-A-weak"]), _fmt(row["PL-B_G1"]), _fmt(row["PL-B-half_G1"]),
                _fmt(row["PL-B_G10"]), _fmt(row["PL-B-half_G10"]), _fmt(row["NCP_size_disjoint"])), flush=True)
    if pool_exec:
        pool_exec.close()
    R["runtime_s"] = round(time.time() - t0, 1)
    R["env"] = {"python": platform.python_version(), "numpy": np.__version__,
                "scipy": __import__("scipy").__version__, "workers": args.workers}
    with open(__file__, "rb") as fh:
        R["script_sha256"] = hashlib.sha256(fh.read()).hexdigest()
    od = os.path.join(ROOT, "results", "power")
    os.makedirs(od, exist_ok=True)
    fn = os.path.join(od, "n3_power%s.json" % ("_quick" if q else ""))
    with open(fn, "w") as fh:
        json.dump(R, fh, indent=1, sort_keys=True, default=_js)
    print("wrote", fn, "runtime %.0fs" % R["runtime_s"])


def _fmt(d):
    return " ".join("%s=%.2f" % (k.replace("_fisher", "F").replace("E_sum", "S").replace("E_zTP", "Z"), v) for k, v in d.items())


def _js(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, tuple):
        return list(o)
    raise TypeError(type(o))


if __name__ == "__main__":
    main()
