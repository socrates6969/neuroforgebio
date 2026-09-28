"""P2: biomimetic vs linear ICMS amplitude encoding, information about force changes per unit charge
(prereg\\P2_biomimetic_info_per_charge.md). Simulation only; amplitudes are model units, not stimulation settings.
numpy + scipy (+ matplotlib for figures). Seed 20260926.
Usage: python p2_biomimetic_info.py test | main | sens | all
Interpretations: code\\DEVIATIONS.md (section P2).
"""
import json
import os
import sys
import time

import numpy as np
from scipy.optimize import brentq
from scipy.special import ndtr, ndtri

BASE = r"C:\Users\mariu\neuro-company\research\somatosensory\code"
RES = os.path.join(BASE, "results")
FIG = os.path.join(BASE, "figures")
SEED = 20260926
DT = 0.01
NT = 300
A_CAP, A_THR, F_MAX = 100.0, 24.0, 2.5
TAUS = [0.1, 0.3, 1.0, 3.0, 10.0, 30.0, np.inf]
ALPHA_GRID = np.round(np.arange(0.25, 1.0001, 0.05), 2)

DEF = dict(N=4000, step_lo=0.1, step_hi=0.3, rise_lo=0.02, rise_hi=0.08, alpha0=0.25, D=20.0, T_train=1.0,
           sigma0=1.0, k_ad=0.9, deadline=0.2, w_scale=1.0, jnd=13.5, std=60.0)


# ------------------------------------------------------------------------------------------ episodes
def gen_episodes(P, seed=SEED):
    rng = np.random.default_rng(seed)
    N = P["N"]
    t = np.arange(NT) * DT
    F = np.zeros((N, NT))
    ev_ep, ev_idx, ev_sign, nu_ep, nu_idx = [], [], [], [], []
    Fhold = np.zeros(N)
    toff_a = np.zeros(N)
    hold_ok = np.zeros(N, bool)
    Fwin = np.zeros(N)
    win = np.zeros((N, 2), dtype=int)
    for i in range(N):
        t0 = rng.uniform(0.2, 0.5)
        ru = rng.uniform(0.05, 0.15)
        fh = rng.uniform(0.5, 2.0)
        toff = t0 + rng.uniform(1.5, 2.2)
        rd = rng.uniform(0.05, 0.15)
        hs = t0 + ru
        lo, hi = hs + 0.2, toff - 0.2
        steps = []
        tc = lo
        last = -np.inf
        while True:  # Poisson process rate 1/s with dead-time thinning (>= 300 ms apart)
            tc = tc + rng.exponential(1.0)
            if tc > hi:
                break
            if tc - last >= 0.3:
                steps.append(tc)
                last = tc
        bt, bv = [0.0, t0, hs], [0.0, 0.0, fh]
        lev = fh
        signs = []
        for te in steps:
            sgn = 1.0 if rng.uniform() < 0.5 else -1.0
            size = rng.uniform(P["step_lo"], P["step_hi"])
            rise = rng.uniform(P["rise_lo"], P["rise_hi"])
            new = lev * (1 + sgn * size)
            bt += [te, te + rise]
            bv += [lev, new]
            lev = new
            signs.append(sgn)
        bt += [toff, toff + rd, 3.0 + DT]
        bv += [lev, 0.0, 0.0]
        F[i] = np.interp(t, bt, bv)
        for te, sg in zip(steps, signs):
            ev_ep.append(i); ev_idx.append(int(np.ceil(te / DT - 1e-9))); ev_sign.append(sg)
        # null windows: tile 200 ms windows from hold start
        j = 1
        while True:
            tn = hs + 0.2 * j
            if tn + 0.2 > toff - 0.2 + 1e-12:
                break
            if all((te <= tn - 0.3) or (te >= tn + 0.2 + 0.3) for te in steps):
                nu_ep.append(i); nu_idx.append(int(np.ceil(tn / DT - 1e-9)))
            j += 1
        Fhold[i] = fh
        toff_a[i] = toff
        k0, k1 = int(np.ceil((toff - 0.5) / DT - 1e-9)), int(np.ceil(toff / DT - 1e-9))
        win[i] = (k0, k1)
        hold_ok[i] = not any(toff - 0.5 <= te < toff for te in steps)
        Fwin[i] = F[i, k0:k1].mean()
    return dict(F=F, ev_ep=np.array(ev_ep), ev_idx=np.array(ev_idx), ev_sign=np.array(ev_sign),
                nu_ep=np.array(nu_ep), nu_idx=np.array(nu_idx), Fhold=Fhold, hold_ok=hold_ok, Fwin=Fwin, win=win,
                Z=rng.standard_normal((N, NT)), N=N)


# ------------------------------------------------------------------------------------------ encoders
def a_lin(F):
    return np.where(F <= 0.02, 0.0, np.minimum(A_THR + (A_CAP - A_THR) * F / F_MAX, A_CAP))


def dFdt(F):
    d = np.zeros_like(F)
    d[:, 1:] = (F[:, 1:] - F[:, :-1]) / DT
    return d


def a_bio(F, dF, alpha, beta, D):
    x = np.clip((A_CAP - A_THR) * (alpha * F / F_MAX + beta * np.abs(dF) / D), 0, A_CAP - A_THR)
    return np.where(F <= 0.02, 0.0, A_THR + x)


def bisect(fun, lo, hi, it=80):
    flo = fun(lo)
    for _ in range(it):
        mid = 0.5 * (lo + hi)
        fm = fun(mid)
        if (fm > 0) == (flo > 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return 0.5 * (lo + hi)


def charge_match(F, dF, D, alpha0):
    target = a_lin(F).sum(1).mean()
    for al in [alpha0] + [a for a in ALPHA_GRID if a > alpha0 + 1e-9]:
        if a_bio(F, dF, al, 1000.0, D).sum(1).mean() >= target:
            if a_bio(F, dF, al, 0.0, D).sum(1).mean() >= target:
                return al, 0.0
            b = bisect(lambda b: a_bio(F, dF, al, b, D).sum(1).mean() - target, 0.0, 1000.0)
            return al, b
    raise RuntimeError("charge matching infeasible on alpha grid")


def charge_match_fixed_alpha(F, dF, D, al):
    target = a_lin(F).sum(1).mean()
    if a_bio(F, dF, al, 1000.0, D).sum(1).mean() < target:
        return None
    return bisect(lambda b: a_bio(F, dF, al, b, D).sum(1).mean() - target, 0.0, 1000.0)


def peak_match(F, dF, D, alpha):
    target = np.percentile(a_lin(F), 99)
    return bisect(lambda b: np.percentile(a_bio(F, dF, alpha, b, D), 99) - target, 0.0, 1000.0, it=60)


def beta0_alpha(F, dF, D):
    target = a_lin(F).sum(1).mean()
    return bisect(lambda al: a_bio(F, dF, al, 0.0, D).sum(1).mean() - target, 0.0, 5.0)


# ------------------------------------------------------------------------------------------ observer
def adapt(a, tau, k=0.9):
    if not np.isfinite(tau):
        return a.copy()
    e = np.exp(-DT / tau)
    z = np.zeros(a.shape[0])
    r = np.empty_like(a)
    for t in range(a.shape[1]):
        r[:, t] = np.maximum(a[:, t] - z, 0)
        z = k * a[:, t] + (z - k * a[:, t]) * e
    return r


def flat_gain(tau, n, k=0.9):
    """r_t / a for a flat train starting at rest (z0 = 0)."""
    r = adapt(np.ones((1, n)), tau, k)[0]
    return r


def p_greater(c, s, w, g, nT, sigma0):
    Mc, Ms = c * g.sum(), s * g.sum()
    Vc = nT * ((w * c * g + sigma0) ** 2).sum()
    Vs = nT * ((w * s * g + sigma0) ** 2).sum()
    sd = np.sqrt(Vc + Vs)
    if sd == 0:  # noise-free observer (sigma0 = 0, w = 0)
        return 0.5 if Mc == Ms else float(Mc > Ms)
    return ndtr((Mc - Ms) / sd)


def jnd_of(w, tau, P):
    n_cal = int(round(1.0 / DT))
    nT = P["T_train"] / DT
    g = flat_gain(tau, n_cal, P["k_ad"])
    s = P["std"]
    pg = lambda c: p_greater(c, s, w, g, nT, P["sigma0"])
    if pg(0.0) >= 0.25 or pg(1e4) <= 0.75:  # amplitudes are >= 0; JND not reachable -> effectively infinite
        return 1e6
    c25 = brentq(lambda c: pg(c) - 0.25, 0.0, s)
    c75 = brentq(lambda c: pg(c) - 0.75, s, 1e4)
    return 0.5 * (c75 - c25)


def calibrate_w(tau, P):
    f = lambda w: jnd_of(w, tau, P) - P["jnd"]
    if f(0.0) > 0:
        return np.nan
    return brentq(f, 0.0, 10.0, xtol=1e-10)


def observe(a, tau, w, P, Z):
    r = adapt(a, tau, P["k_ad"])
    nT = P["T_train"] / DT
    return r + np.sqrt(nT) * (w * r + P["sigma0"]) * Z


# ------------------------------------------------------------------------------------------ detection
def scores(y, idx_ep, idx_k, P):
    W = int(round(P["deadline"] / DT))
    cs = np.concatenate([np.zeros((y.shape[0], 1)), np.cumsum(y, 1)], 1)

    def wmean(ep, a, b):  # mean of y[ep, a..b] inclusive, indices clipped to the episode
        a = np.clip(a, 0, NT - 1); b = np.clip(b, 0, NT - 1)
        return (cs[ep, b + 1] - cs[ep, a]) / (b - a + 1)

    ks = idx_k[:, None] + np.arange(W + 1)[None, :]
    ep = np.repeat(idx_ep[:, None], W + 1, 1)
    d1 = np.abs(wmean(ep, ks - 4, ks) - wmean(ep, ks - 14, ks - 5)).max(1)
    d2 = np.abs(wmean(idx_ep, idx_k + W // 2, idx_k + W) - wmean(idx_ep, idx_k - 20, idx_k))
    return d1, d2


def auc_w(pos, pw, neg, nw):
    o = np.argsort(neg)
    ns, nws = neg[o], nw[o]
    cw = np.concatenate([[0.0], np.cumsum(nws)])
    l = np.searchsorted(ns, pos, "left")
    r = np.searchsorted(ns, pos, "right")
    num = (pw * (cw[l] + 0.5 * (cw[r] - cw[l]))).sum()
    return num / (pw.sum() * nws.sum())


def dprime(auc):
    return np.sqrt(2) * ndtri(np.clip(auc, 1e-12, 1 - 1e-12))


def encoder_eval(y, E, P, mult=None, sign=None):
    """best-detector d' and AUCs for one encoder output y."""
    ev_sel = np.ones(E["ev_ep"].size, bool) if sign is None else (E["ev_sign"] == sign)
    pe, pk = E["ev_ep"][ev_sel], E["ev_idx"][ev_sel]
    d1p, d2p = scores(y, pe, pk, P)
    d1n, d2n = scores(y, E["nu_ep"], E["nu_idx"], P)
    pw = np.ones(pe.size) if mult is None else mult[pe]
    nw = np.ones(E["nu_ep"].size) if mult is None else mult[E["nu_ep"]]
    a1, a2 = auc_w(d1p, pw, d1n, nw), auc_w(d2p, pw, d2n, nw)
    return dict(AUC_D1=a1, AUC_D2=a2, dprime=max(dprime(a1), dprime(a2)), best="D1" if a1 >= a2 else "D2")


def rmse_eval(y, E, target, order=None):
    k0, k1 = E["win"][:, 0], E["win"][:, 1]
    cs = np.concatenate([np.zeros((y.shape[0], 1)), np.cumsum(y, 1)], 1)
    ym = (cs[np.arange(y.shape[0]), k1] - cs[np.arange(y.shape[0]), k0]) / (k1 - k0)
    idx = np.arange(y.shape[0]) if order is None else order
    idx = idx[E["hold_ok"][idx]]
    h = idx.size // 2
    fit, test = idx[:h], idx[h:]
    X = np.stack([np.ones(fit.size), ym[fit]], 1)
    coef, *_ = np.linalg.lstsq(X, target[fit], rcond=None)
    pred = coef[0] + coef[1] * ym[test]
    return float(np.sqrt(np.mean((pred - target[test]) ** 2)))


# ------------------------------------------------------------------------------------------ pipeline
def build(P, E=None):
    E = E or gen_episodes(P)
    F = E["F"]
    dF = dFdt(F)
    al, bc = charge_match(F, dF, P["D"], P["alpha0"])
    bp = peak_match(F, dF, P["D"], P["alpha0"])
    enc = dict(lin=a_lin(F), charge=a_bio(F, dF, al, bc, P["D"]), peak=a_bio(F, dF, P["alpha0"], bp, P["D"]))
    Q = lambda a: a.sum(1).mean()
    info = dict(alpha_charge=al, beta_charge=bc, alpha_peak=P["alpha0"], beta_peak=bp,
                charge_ratio_charge=Q(enc["charge"]) / Q(enc["lin"]), charge_ratio_peak=Q(enc["peak"]) / Q(enc["lin"]),
                p99_lin=float(np.percentile(enc["lin"], 99)), p99_peak=float(np.percentile(enc["peak"], 99)),
                n_events=int(E["ev_ep"].size), n_null=int(E["nu_ep"].size), n_hold_usable=int(E["hold_ok"].sum()))
    return E, dF, enc, info


def evaluate(E, enc, P, tau, w, boot=0, seed=SEED + 7, variants=("charge", "peak")):
    ys = {k: observe(v, tau, w, P, E["Z"]) for k, v in enc.items() if k == "lin" or k in variants}
    out = {}
    base = {k: encoder_eval(y, E, P) for k, y in ys.items()}
    rm = {k: rmse_eval(y, E, E["Fhold"]) for k, y in ys.items()}
    rm2 = {k: rmse_eval(y, E, E["Fwin"]) for k, y in ys.items()}
    sg = {k: {s: encoder_eval(y, E, P, sign=s)["dprime"] for s in (1.0, -1.0)} for k, y in ys.items()}
    for v in variants:
        out[v] = dict(dprime_bio=base[v]["dprime"], dprime_lin=base["lin"]["dprime"],
                      dprime_ratio=base[v]["dprime"] / base["lin"]["dprime"],
                      AUC_bio=[base[v]["AUC_D1"], base[v]["AUC_D2"]], AUC_lin=[base["lin"]["AUC_D1"], base["lin"]["AUC_D2"]],
                      best_bio=base[v]["best"], best_lin=base["lin"]["best"],
                      rmse_bio=rm[v], rmse_lin=rm["lin"], rmse_ratio=rm[v] / rm["lin"],
                      rmse_ratio_trueforce=rm2[v] / rm2["lin"],
                      dprime_inc=[sg[v][1.0], sg["lin"][1.0]], dprime_dec=[sg[v][-1.0], sg["lin"][-1.0]],
                      dprime_ratio_inc=sg[v][1.0] / sg["lin"][1.0], dprime_ratio_dec=sg[v][-1.0] / sg["lin"][-1.0])
    if boot:
        rng = np.random.default_rng(seed)
        N = E["N"]
        R = {v: [] for v in variants}
        RM = {v: [] for v in variants}
        for b in range(boot):
            draw = rng.integers(0, N, N)
            mult = np.bincount(draw, minlength=N).astype(float)
            dl = encoder_eval(ys["lin"], E, P, mult)["dprime"]
            rl = rmse_eval(ys["lin"], E, E["Fhold"], order=draw)
            for v in variants:
                R[v].append(encoder_eval(ys[v], E, P, mult)["dprime"] / dl)
                RM[v].append(rmse_eval(ys[v], E, E["Fhold"], order=draw) / rl)
        for v in variants:
            out[v]["dprime_ratio_CI95"] = [float(np.percentile(R[v], 2.5)), float(np.percentile(R[v], 97.5))]
            out[v]["rmse_ratio_CI95"] = [float(np.percentile(RM[v], 2.5)), float(np.percentile(RM[v], 97.5))]
    return out


def verdict(r):
    lo, hi = r["dprime_ratio_CI95"]
    if lo <= 1.3 <= hi:
        return "INCONCLUSIVE"
    return "PASS" if (r["dprime_ratio"] >= 1.3 and r["rmse_ratio"] <= 1.5) else "FAIL"


# ------------------------------------------------------------------------------------------ self-test
def self_test():
    ok = {}
    rng = np.random.default_rng(11)
    pos, neg = rng.normal(1, 1, 40000), rng.normal(0, 1, 40000)
    d = dprime(auc_w(pos, np.ones(pos.size), neg, np.ones(neg.size)))
    ok["dprime_known_gaussians(d'=1)"] = bool(abs(d - 1) < 0.03)
    a, b = rng.integers(0, 5, 50).astype(float), rng.integers(0, 5, 60).astype(float)
    brute = np.mean((a[:, None] > b[None, :]) + 0.5 * (a[:, None] == b[None, :]))
    ok["auc_ties_vs_bruteforce"] = bool(abs(auc_w(a, np.ones(50), b, np.ones(60)) - brute) < 1e-12)
    wa = rng.integers(0, 3, 50).astype(float)
    brute_w = np.sum(wa[:, None] * ((a[:, None] > b[None, :]) + 0.5 * (a[:, None] == b[None, :]))) / (wa.sum() * 60)
    ok["auc_weighted_vs_bruteforce"] = bool(abs(auc_w(a, wa, b, np.ones(60)) - brute_w) < 1e-12)
    P = dict(DEF)
    for tau in (np.inf, 0.3):
        w = calibrate_w(tau, P)
        g = flat_gain(tau, 100)
        cs = np.array([P["std"] - 13.5, P["std"] + 13.5])
        r2 = np.random.default_rng(3)
        nT = P["T_train"] / DT
        pr = []
        for c in np.linspace(30, 90, 25):
            Zc, Zs = r2.standard_normal((20000, 100)), r2.standard_normal((20000, 100))
            yc = (c * g + np.sqrt(nT) * (w * c * g + P["sigma0"]) * Zc).sum(1)
            ys = (60 * g + np.sqrt(nT) * (w * 60 * g + P["sigma0"]) * Zs).sum(1)
            pr.append(np.mean(yc > ys))
        cc = np.linspace(30, 90, 25)
        c25, c75 = np.interp(0.25, pr, cc), np.interp(0.75, pr, cc)
        ok[f"calibration_MC_JND_tau={tau}"] = bool(abs(0.5 * (c75 - c25) - 13.5) < 0.6)
    aa = np.full((1, 400), 50.0)
    ok["adapt_inf_identity"] = bool(np.array_equal(adapt(aa, np.inf), aa))
    ok["adapt_steady_state_(1-k)a"] = bool(abs(adapt(aa, 0.1)[0, -1] - 5.0) < 1e-6)
    F = np.linspace(0, 2.4, 300)[None, :].repeat(3, 0)
    ok["bio_alpha1_beta0_equals_linear"] = bool(np.allclose(a_bio(F, dFdt(F), 1.0, 0.0, 20), a_lin(F)))
    Pt = dict(DEF, N=300)
    E = gen_episodes(Pt, seed=5)
    dF = dFdt(E["F"])
    al, bc = charge_match(E["F"], dF, 20.0, 0.25)
    ok["charge_match_exact"] = bool(abs(a_bio(E["F"], dF, al, bc, 20).sum(1).mean() / a_lin(E["F"]).sum(1).mean() - 1) < 1e-6)
    ok["events_>=300ms_apart"] = bool(all(np.all(np.diff(E["ev_idx"][E["ev_ep"] == i]) >= 29) for i in range(300)))
    ok["noise_free_null_scores_zero"] = bool(np.all(np.array(scores(a_lin(E["F"]), E["nu_ep"], E["nu_idx"], Pt)) < 1e-9))
    return ok


# ------------------------------------------------------------------------------------------ runs
def to_json(o):
    if isinstance(o, dict):
        return {str(k): to_json(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [to_json(v) for v in o]
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return f if np.isfinite(f) else str(f)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


def run_main():
    t0 = time.time()
    P = dict(DEF)
    E, dF, enc, info = build(P)
    out = dict(prereg="P2_biomimetic_info_per_charge.md", seed=SEED, N=P["N"], normalisation=info)
    info["realism_flag_unrealistic"] = bool(not (0.5 <= info["charge_ratio_peak"] <= 0.9))
    ws = {str(t): calibrate_w(t, P) for t in TAUS}
    out["w_calibrated"] = ws
    table = {}
    for tau in TAUS:
        table[str(tau)] = evaluate(E, enc, P, tau, ws[str(tau)], boot=1000 if tau == np.inf else 200)
        print("tau", tau, {v: round(table[str(tau)][v]["dprime_ratio"], 3) for v in ("charge", "peak")},
              f"{time.time()-t0:.0f}s", flush=True)
    out["table"] = table
    prim = table["inf"]["charge"]
    out["primary"] = prim
    # abandonment check
    aucs = [max(prim["AUC_bio"]), max(prim["AUC_lin"])]
    ceil_, floor_ = all(a > 0.99 for a in aucs), all(a < 0.55 for a in aucs)
    out["abandonment_check"] = dict(AUC_best_bio=aucs[0], AUC_best_lin=aucs[1], ceiling=ceil_, floor=floor_)
    out["verdict"] = verdict(prim)
    if ceil_ or floor_:
        P2 = dict(P, step_lo=0.05, step_hi=0.15) if ceil_ else dict(P, step_lo=0.3, step_hi=0.6)
        E2, _, enc2, info2 = build(P2)
        r2 = evaluate(E2, enc2, P2, np.inf, ws["inf"], boot=1000, variants=("charge",))["charge"]
        a2 = [max(r2["AUC_bio"]), max(r2["AUC_lin"])]
        out["rerun"] = dict(P=P2, normalisation=info2, result=r2)
        if all(a > 0.99 for a in a2) or all(a < 0.55 for a in a2):
            out["verdict"] = "ABANDONED: model cannot discriminate the encoders at the published noise level"
        else:
            out["verdict"] = verdict(r2) + " (rerun)"
    # controls
    F = E["F"]
    al0 = beta0_alpha(F, dF, P["D"])
    enc_b0 = dict(lin=enc["lin"], charge=a_bio(F, dF, al0, 0.0, P["D"]))
    rb0 = evaluate(E, enc_b0, P, np.inf, ws["inf"], variants=("charge",))["charge"]
    Pn = dict(P, sigma0=0.0)
    rnf = evaluate(E, enc, Pn, np.inf, 0.0, variants=("charge",))["charge"]
    y = observe(enc["charge"], np.inf, ws["inf"], P, E["Z"])
    d1p, d2p = scores(y, E["ev_ep"], E["ev_idx"], P)
    d1n, d2n = scores(y, E["nu_ep"], E["nu_idx"], P)
    rng = np.random.default_rng(SEED + 3)
    allsc = np.concatenate([d1p, d1n])
    lab = rng.permutation(np.r_[np.ones(d1p.size, bool), np.zeros(d1n.size, bool)])
    auc_sh = auc_w(allsc[lab], np.ones(lab.sum()), allsc[~lab], np.ones((~lab).sum()))
    out["controls"] = dict(
        beta0=dict(alpha=al0, dprime_ratio=rb0["dprime_ratio"], rmse_ratio=rb0["rmse_ratio"],
                   pass_=bool(rb0["dprime_ratio"] < 1.3)),
        noise_free=dict(AUC_bio=rnf["AUC_bio"], AUC_lin=rnf["AUC_lin"],
                        pass_=bool(max(rnf["AUC_bio"]) > 0.99 and max(rnf["AUC_lin"]) > 0.99)),
        label_shuffle=dict(AUC_D1_bio=auc_sh, pass_=bool(abs(auc_sh - 0.5) < 0.02)))
    # exploratory: next grid alpha' values (charge-matched)
    expl = []
    i0 = int(np.argmin(np.abs(ALPHA_GRID - info["alpha_charge"])))
    for al in ALPHA_GRID[i0 + 1:i0 + 3]:
        b = charge_match_fixed_alpha(F, dF, P["D"], al)
        if b is None:
            continue
        r = evaluate(E, dict(lin=enc["lin"], charge=a_bio(F, dF, al, b, P["D"])), P, np.inf, ws["inf"], variants=("charge",))
        expl.append(dict(alpha=float(al), beta=b, dprime_ratio=r["charge"]["dprime_ratio"], rmse_ratio=r["charge"]["rmse_ratio"]))
    out["exploratory_alpha_grid"] = expl
    out["runtime_s"] = round(time.time() - t0, 1)
    with open(os.path.join(RES, "p2_biomimetic.json"), "w") as f:
        json.dump(to_json(out), f, indent=1)
    np.savez_compressed(os.path.join(RES, "p2_example.npz"), F=E["F"][:3], lin=enc["lin"][:3], charge=enc["charge"][:3],
                        peak=enc["peak"][:3])
    return out


def run_posthoc(B=1000):
    """POST-HOC (added after seeing that d'_lin ~ 0 makes the ratio undefined): separate CIs for d'_bio, d'_lin and
    their difference at the primary condition. Not part of the prereg decision rule."""
    P = dict(DEF)
    E, dF, enc, info = build(P)
    w = calibrate_w(np.inf, P)
    yb, yl = observe(enc["charge"], np.inf, w, P, E["Z"]), observe(enc["lin"], np.inf, w, P, E["Z"])
    rng = np.random.default_rng(SEED + 7)
    db, dl = [], []
    for b in range(B):
        mult = np.bincount(rng.integers(0, E["N"], E["N"]), minlength=E["N"]).astype(float)
        db.append(encoder_eval(yb, E, P, mult)["dprime"]); dl.append(encoder_eval(yl, E, P, mult)["dprime"])
    db, dl = np.array(db), np.array(dl)
    ci = lambda x: [float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))]
    lin_d2 = scores(enc["lin"], E["ev_ep"], E["ev_idx"], P)[1]
    rr = enc["lin"][E["ev_ep"], E["ev_idx"]]
    out = dict(note="POST-HOC supplement, not a prereg criterion",
               dprime_bio=float(encoder_eval(yb, E, P)["dprime"]), dprime_bio_CI95=ci(db),
               dprime_lin=float(encoder_eval(yl, E, P)["dprime"]), dprime_lin_CI95=ci(dl),
               diff_CI95=ci(db - dl), frac_boot_lin_le_0=float(np.mean(dl <= 0)),
               lin_step_signal_D2_mean_uA=float(lin_d2.mean()),
               per_sample_noise_sd_at_lin_event_uA=float(np.mean(np.sqrt(P["T_train"] / DT) * (w * rr + P["sigma0"]))))
    with open(os.path.join(RES, "p2_biomimetic_posthoc.json"), "w") as f:
        json.dump(to_json(out), f, indent=1)
    return out


SENS = [("w x0.5", dict(w_scale=0.5)), ("w x1.5", dict(w_scale=1.5)), ("alpha' 0.1", dict(alpha0=0.1)),
        ("alpha' 0.5", dict(alpha0=0.5)), ("D 10", dict(D=10.0)), ("D 40", dict(D=40.0)),
        ("T_train 0.5 s", dict(T_train=0.5)), ("T_train 2 s", dict(T_train=2.0)),
        ("step U(0.05,0.15)", dict(step_lo=0.05, step_hi=0.15)), ("step U(0.3,0.6)", dict(step_lo=0.3, step_hi=0.6)),
        ("rise U(5,20) ms", dict(rise_lo=0.005, rise_hi=0.020)), ("rise U(80,200) ms", dict(rise_lo=0.08, rise_hi=0.2)),
        ("deadline 100 ms", dict(deadline=0.1)), ("deadline 400 ms", dict(deadline=0.4)),
        ("sigma0 0", dict(sigma0=0.0)), ("sigma0 5", dict(sigma0=5.0))]


def run_sens():
    t0 = time.time()
    rows = []
    for label, ch in [("baseline (N=2000)", {})] + SENS:
        P = dict(DEF, N=2000, **ch)
        E, dF, enc, info = build(P)
        w = calibrate_w(np.inf, P) * P["w_scale"]
        r = evaluate(E, enc, P, np.inf, w, variants=("charge",))["charge"]
        rows.append(dict(config=label, w=w, alpha=info["alpha_charge"], beta=info["beta_charge"],
                         dprime_ratio=r["dprime_ratio"], rmse_ratio=r["rmse_ratio"],
                         dprime_bio=r["dprime_bio"], dprime_lin=r["dprime_lin"]))
        print(label, round(r["dprime_ratio"], 3), round(r["rmse_ratio"], 3), f"{time.time()-t0:.0f}s", flush=True)
    out = dict(N=2000, rows=rows, runtime_s=round(time.time() - t0, 1))
    with open(os.path.join(RES, "p2_biomimetic_sensitivity.json"), "w") as f:
        json.dump(to_json(out), f, indent=1)
    return out


def figures():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    with open(os.path.join(RES, "p2_biomimetic.json")) as f:
        o = json.load(f)
    ex = np.load(os.path.join(RES, "p2_example.npz"))
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.6))
    xs = np.arange(len(TAUS))
    lab = [("∞" if t == np.inf else f"{t:g}") for t in TAUS]
    for v, col, off in (("charge", "#1f5fa8", -0.08), ("peak", "#b8860b", 0.08)):
        r = [o["table"][str(t)][v]["dprime_ratio"] for t in TAUS]
        ci = np.array([o["table"][str(t)][v].get("dprime_ratio_CI95", [np.nan, np.nan]) for t in TAUS], dtype=float)
        ax[0].errorbar(xs + off, r, yerr=[np.array(r) - ci[:, 0], ci[:, 1] - np.array(r)], fmt="o-", color=col,
                       capsize=3, label=f"{v}-matched")
    ax[0].axhline(1.3, color="k", ls="--", lw=1, label="PASS threshold 1.3")
    ax[0].axhline(1.0, color="#999", ls=":", lw=1)
    ax[0].set_yscale("symlog", linthresh=2)
    ax[0].set_xticks(xs); ax[0].set_xticklabels(lab)
    ax[0].set_xlabel("adaptation time constant τ_ad (s)")
    ax[0].set_ylabel("d'_bio / d'_lin (step detection, best detector)")
    ax[0].set_title(f"P2: d' ratio (symlog; undefined because d'_lin ≈ 0)\nverdict: {o['verdict']}", fontsize=10)
    ax[0].legend(fontsize=8)
    for v, col in (("lin", "#555"), ("charge", "#1f5fa8"), ("peak", "#b8860b")):
        key = "dprime_lin" if v == "lin" else "dprime_bio"
        src = "charge" if v == "lin" else v
        ax[1].plot(xs, [o["table"][str(t)][src][key] for t in TAUS], "o-", color=col,
                   label="linear" if v == "lin" else f"biomimetic ({v}-matched)")
    ax[1].set_xticks(xs); ax[1].set_xticklabels(lab)
    ax[1].set_xlabel("adaptation time constant τ_ad (s)")
    ax[1].set_ylabel("d' for ±10–30% force steps (200 ms)")
    ax[1].set_title("d' per encoder", fontsize=10)
    ax[1].legend(fontsize=8)
    t = np.arange(NT) * DT
    a2 = ax[2]
    a2.plot(t, ex["lin"][0], color="#555", label="linear a_lin")
    a2.plot(t, ex["charge"][0], color="#1f5fa8", label="biomimetic, charge-matched")
    a2.plot(t, ex["peak"][0], color="#b8860b", lw=0.9, label="biomimetic, peak-matched")
    a2.set_xlabel("time (s)"); a2.set_ylabel("amplitude (model µA units)")
    tw = a2.twinx(); tw.plot(t, ex["F"][0], color="#2e7d32", ls="--", lw=1); tw.set_ylabel("force F (N), dashed", color="#2e7d32")
    a2.set_title("example episode (model units, not stimulation settings)", fontsize=10)
    a2.legend(fontsize=7, loc="upper left")
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(os.path.join(FIG, f"p2_dprime_vs_tau.{ext}"), dpi=150)
    plt.close(fig)
    sp = os.path.join(RES, "p2_biomimetic_sensitivity.json")
    if os.path.exists(sp):
        with open(sp) as f:
            s = json.load(f)
        fig, a = plt.subplots(figsize=(8, 6))
        rows = s["rows"]
        y = np.arange(len(rows))
        a.scatter([r["dprime_bio"] for r in rows], y, color="#1f5fa8", label="d' biomimetic (charge-matched)", zorder=3)
        a.scatter([r["dprime_lin"] for r in rows], y, marker="s", color="#555", label="d' linear", zorder=3)
        a.scatter([r["rmse_ratio"] for r in rows], y, marker="x", color="#c0392b", label="hold-force RMSE ratio bio/lin", zorder=3)
        a.axvline(0, color="#999", lw=0.8); a.axvline(1.5, color="#c0392b", ls="--", lw=1)
        a.set_yticks(y); a.set_yticklabels([r["config"] for r in rows], fontsize=8); a.invert_yaxis()
        a.set_xlabel("d' (step detection, τ_ad = ∞) and RMSE ratio (dashed: RMSE limit 1.5)")
        a.set_title("P2 sensitivity (N = 2000): d' ratio undefined because d'_lin ≈ 0 in every configuration", fontsize=9)
        a.legend(fontsize=8)
        fig.tight_layout()
        for ext in ("png", "svg"):
            fig.savefig(os.path.join(FIG, f"p2_sensitivity.{ext}"), dpi=150)
        plt.close(fig)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    os.makedirs(RES, exist_ok=True)
    os.makedirs(FIG, exist_ok=True)
    if mode in ("test", "all"):
        r = self_test()
        print("SELF-TEST", r, "ALL PASS" if all(r.values()) else "FAILURES")
        with open(os.path.join(RES, "p2_selftest.json"), "w") as f:
            json.dump(r, f, indent=1)
        if not all(r.values()):
            sys.exit(1)
    if mode in ("main", "all"):
        o = run_main()
        print(json.dumps(to_json(dict(verdict=o["verdict"], primary=o["primary"], normalisation=o["normalisation"],
                                      controls=o["controls"], abandonment=o["abandonment_check"],
                                      exploratory=o["exploratory_alpha_grid"], runtime=o["runtime_s"])), indent=1))
    if mode in ("sens", "all"):
        run_sens()
    if mode in ("posthoc", "all"):
        print(json.dumps(run_posthoc(), indent=1))
    if mode in ("fig", "main", "sens", "all"):
        figures()
