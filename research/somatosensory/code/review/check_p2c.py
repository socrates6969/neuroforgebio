"""Reviewer check for P2c (cycle 3). Does NOT modify any project file.
1. Independent A0 refit (own continuous-time train-mean gain, own optimiser) under two train-time pairings.
2. Independent gain-session integrator (Euler, 10 substeps per 10-ms bin) vs the coder's gain_session.
3. Arm construction: own FV/HS noise sd from the adapted r vs p2b.noise_sd; gain applied to the signal.
4. Gain-scaling control decomposition: constant gain g_ss (no within-episode dynamics) vs session gain vs g = 1, D1-only
   and max(D1, D2), plus an independent rank AUC for D1. Episodes/encoders/detectors come from the coder's modules (read-only)."""
import csv
import math
import os
import sys
import time

import numpy as np
from scipy.optimize import minimize
from scipy.stats import norm, rankdata

CODE = r"C:\Users\mariu\neuro-company\research\somatosensory\code"
DATA = r"C:\Users\mariu\neuro-company\research\somatosensory\notes\published-derived"
t0 = time.time()

# ------------------------------------------------------------------ 1. A0 refit, own implementation
t_d, y_d = [], []
for r in csv.reader(open(os.path.join(DATA, "hughes2022_fig3b_intermittent_DIGITISED.csv"))):
    if r and not r[0].startswith("#") and not r[0].startswith("t_s") and not r[0].startswith('"'):
        t_d.append(float(r[0])); y_d.append(float(r[1]))
t_d, y_d = np.array(t_d), np.array(y_d)
print("1. digitised points:", t_d.size, "| last adaptation", y_d[36], "(quoted 43.5%) | last recovery", y_d[-1], "(quoted 72.6%)")


def train_means(ta, tr, order):
    """exact continuous-time mean of g over each 1-s train; order 'rest_first' or 'on_first'"""
    k = 1 / ta + 1 / tr
    ginf = (1 / tr) / k
    g, starts, vals, t = 1.0, [], [], 0.0
    rests = [5.0] * 50 + [61.0] * 5
    for rst in rests:
        if order == "rest_first":
            g = 1 - (1 - g) * math.exp(-rst / tr); t += rst
        vals.append(ginf + (g - ginf) * (1 - math.exp(-k)) / k)
        g = ginf + (g - ginf) * math.exp(-k); t += 1.0
        starts.append(t)                       # train end time
        if order == "on_first":
            g = 1 - (1 - g) * math.exp(-rst / tr); t += rst
    v = np.array(vals)
    return v / v[0], np.array(starts)


def fit(order):
    _, ends = train_means(10, 100, order)
    idx = np.argmin(np.abs(ends[None] - t_d[:, None]), 1)
    f = lambda th: np.sum((train_means(math.exp(th[0]), math.exp(th[1]), order)[0][idx] - y_d) ** 2)
    best = min((minimize(f, [math.log(a), math.log(b)], method="Nelder-Mead", options=dict(xatol=1e-8, fatol=1e-12, maxiter=4000))
                for a in (5, 15, 40) for b in (50, 150, 500)), key=lambda r: r.fun)
    ta, tr = map(math.exp, best.x)
    v, _ = train_means(ta, tr, order)
    rm = math.sqrt(best.fun / t_d.size)
    # profile-free approx CI via numerical Hessian of SSE in log space
    h = 1e-4
    H = np.zeros((2, 2))
    for i in range(2):
        for j in range(2):
            e_i, e_j = np.eye(2)[i] * h, np.eye(2)[j] * h
            H[i, j] = (f(best.x + e_i + e_j) - f(best.x + e_i - e_j) - f(best.x - e_i + e_j) + f(best.x - e_i - e_j)) / (4 * h * h)
    s2 = best.fun / (t_d.size - 2)
    se = np.sqrt(np.diag(np.linalg.inv(H / 2) * s2))
    rm_pre = math.sqrt(np.mean((train_means(14.6, 120, order)[0][idx] - y_d) ** 2))
    print(f"   [{order}] tau_a {ta:.2f} s (CI {math.exp(best.x[0]-1.96*se[0]):.1f}-{math.exp(best.x[0]+1.96*se[0]):.1f}), "
          f"tau_r {tr:.1f} s (CI {math.exp(best.x[1]-1.96*se[1]):.0f}-{math.exp(best.x[1]+1.96*se[1]):.0f}), RMSE {rm:.4f}, "
          f"end-adapt {v[49]:.3f}, end-recov {v[54]:.3f}; A0 {'PASS' if rm <= 0.06 and abs(v[49]-0.435) <= 0.10 else 'FAIL'}; "
          f"prereg 14.6/120 RMSE here {rm_pre:.4f}")
    return ta, tr


ta_rf, tr_rf = fit("rest_first")
fit("on_first")
ta_c, tr_c = 13.16547856223222, 108.0226777377244
print(f"   coder: tau_a {ta_c:.2f}, tau_r {tr_c:.1f}")
k = 1 / ta_c + 1 / tr_c
print(f"   steady state for duty ~1/3 contact, a/60=1 (prereg arithmetic): 1/(1+(tau_r/tau_a)/3) = {1/(1+tr_c/ta_c/3):.3f}")

# ------------------------------------------------------------------ 2-4. sessions and arms (coder modules read-only)
sys.path.insert(0, CODE)
import p2c_biomimetic_adaptation as c  # noqa: E402
from p2b_biomimetic_ddprime import Scored, noise_sd  # noqa: E402
from p2_biomimetic_info import DEF, DT, NT, calibrate_w, scores  # noqa: E402
from p2b_biomimetic_ddprime import sigma_h  # noqa: E402

P = dict(DEF)
W = c.World(P)
prm = dict(p=1.0, G=3.0, tau_a=ta_c, tau_r=tr_c)
print(f"\n   world built {time.time()-t0:.0f}s; charge ratio {W.info['charge_ratio_charge']:.4f}")


def my_session(a, aw, prm, S_len=250, sub=10):
    """Euler with sub-steps; percept uses g at bin start; rest gaps by Euler too (1 ms steps)"""
    ta, tr, p, G = prm["tau_a"], prm["tau_r"], prm["p"], prm["G"]
    N = a.shape[0]; S = N // S_len
    nw = int(math.ceil(600 / (3 + G)))
    A = a.reshape(S, S_len, NT); Wm = aw[:S * nw].reshape(S, nw, NT)
    g = np.ones(S); h = DT / sub
    def step_ep(g, ep, rec=None):
        for t in range(NT):
            if rec is not None:
                rec[:, t] = g
            drive = (np.maximum(ep[:, t], 0) / 60.0) ** p / ta * (ep[:, t] > 0)
            for _ in range(sub):
                g = g + h * (-g * drive + (1 - g) / tr)
        for _ in range(int(round(G / 0.001))):
            g = g + 0.001 * (1 - g) / tr
        return g
    for e in range(nw):
        g = step_ep(g, Wm[:, e])
    out = np.empty((S, S_len, NT))
    for e in range(S_len):
        g = step_ep(g, A[:, e], out[:, e])
    return out.reshape(N, NT)


gb, sb = W.g("charge", prm)
gl, sl = W.g("lin", prm)
t1 = time.time()
my_gb = my_session(W.enc["charge"], W.warm["charge"], prm)
my_gl = my_session(W.enc["lin"], W.warm["lin"], prm)
print(f"2. own Euler gain session vs coder exact: max|dg| bio {np.abs(my_gb-gb).max():.2e}, lin {np.abs(my_gl-gl).max():.2e} "
      f"({time.time()-t1:.0f}s)")
cb, cl = W.enc["charge"] > 0, W.enc["lin"] > 0
print(f"   g_ss contact: own bio {my_gb[cb].mean():.4f} lin {my_gl[cl].mean():.4f} | coder {sb['g_ss_contact']:.4f} {sl['g_ss_contact']:.4f}")
print(f"   charge per episode after gain (sum g*a): bio/lin = {(gb*W.enc['charge']).sum()/(gl*W.enc['lin']).sum():.4f} "
      f"(unadapted charge ratio {W.info['charge_ratio_charge']:.4f})")

# 3. arm construction
w, sh = calibrate_w(np.inf, P), sigma_h(np.inf, P)
nT = P["T_train"] / DT
for nm, a, g in (("bio", W.enc["charge"], gb), ("lin", W.enc["lin"], gl)):
    r = g * a
    con = a > 0
    rbar = (r * con).sum(1) / np.maximum(con.sum(1), 1)
    fv_own = np.where(con, (np.sqrt(nT) * (w * rbar + P["sigma0"]))[:, None], np.sqrt(nT) * (w * r + P["sigma0"]))
    print(f"3. {nm}: FV sd own vs noise_sd max diff {np.abs(fv_own - noise_sd(a, r, 'fv', w, sh, P)).max():.1e}; "
          f"HS sd const {np.unique(noise_sd(a, r, 'hs', w, sh, P)).round(3)} (= sqrt(100) x {sh:.3f}); "
          f"mean FV contact sd adapted {fv_own[con].mean():.1f} vs unadapted "
          f"{np.where(con, np.sqrt(nT)*(w*((a*con).sum(1)/np.maximum(con.sum(1),1))[:, None]+1), 0)[con].mean():.1f}")
y_b = c.observe_r(W.enc["charge"], gb * W.enc["charge"], "hs", w, sh, P, W.E["Z"])
print("   observe_r(bio, HS) - g*a is pure noise with sd", round(float((y_b - gb * W.enc["charge"]).std()), 3),
      "-> gain acts on the signal only (HS) as prereg 2.1")

# 4. decomposition of the gain-scaling control
E = W.E
ab, al = W.enc["charge"], W.enc["lin"]
gss = 0.5 * (sb["g_ss_contact"] + sl["g_ss_contact"])
dp = lambda A: math.sqrt(2) * norm.ppf(A)


def evalD(rb, rl, arm):
    yb, yl = c.observe_r(ab, rb, arm, w, sh, P, E["Z"]), c.observe_r(al, rl, arm, w, sh, P, E["Z"])
    Sb, Sl = Scored(yb, E, P).evalw(), Scored(yl, E, P).evalw()
    # independent rank AUC for D1
    d1p, _ = scores(yb, E["ev_ep"], E["ev_idx"], P); d1n, _ = scores(yb, E["nu_ep"], E["nu_idx"], P)
    rk = rankdata(np.r_[d1p, d1n])[:d1p.size]
    auc_own = (rk.sum() - d1p.size * (d1p.size + 1) / 2) / (d1p.size * d1n.size)
    return dict(D=Sb["dprime"] - Sl["dprime"], D1=dp(Sb["AUC_D1"]) - dp(Sl["AUC_D1"]), best=(Sb["best"], Sl["best"]),
                auc=(round(Sb["AUC_D1"], 4), round(Sb["AUC_D2"], 4), round(Sl["AUC_D1"], 4), round(Sl["AUC_D2"], 4)),
                auc_own_bio_D1=round(auc_own, 4))


print(f"\n4. gain-scaling decomposition (g_ss = {gss:.4f}, g_ss^2 = {gss**2:.4f})")
res = {}
for arm in ("hs", "fv"):
    for tag, rb, rl in (("g=1", ab, al), ("const g_ss", gss * ab, gss * al),
                        ("const own g_ss", sb["g_ss_contact"] * ab, sl["g_ss_contact"] * al), ("session g", gb * ab, gl * al)):
        o = evalD(rb, rl, arm)
        res[(arm, tag)] = o
        print(f"   {arm.upper()} {tag:15s} Delta(max D1,D2) {o['D']:+.4f}  Delta_D1only {o['D1']:+.4f}  best {o['best']}  "
              f"AUC bioD1,bioD2,linD1,linD2 {o['auc']}  own-rank AUC bioD1 {o['auc_own_bio_D1']}")
h1, hc, hs_ = res[("hs", "g=1")], res[("hs", "const g_ss")], res[("hs", "session g")]
print(f"   HS: D1-only ratio const/g=1 = {hc['D1']/h1['D1']:.3f}, session/g=1 = {hs_['D1']/h1['D1']:.3f} "
      f"(g_ss = {gss:.3f}, g_ss^2 = {gss**2:.3f}); session vs const D1-only differ by {hs_['D1']-hc['D1']:+.4f}")
# where d1 is linear or quadratic: sweep constant g on HS D1 only
print("   HS D1-only Delta vs constant g:", {g: round(evalD(g * ab, g * al, "hs")["D1"], 4) for g in (1.0, 0.75, 0.5, 0.273)})
print(f"total {time.time()-t0:.0f}s")
