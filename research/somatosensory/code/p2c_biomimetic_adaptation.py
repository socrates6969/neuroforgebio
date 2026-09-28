"""P2c: biomimetic vs linear ICMS encoding under variance-controlled noise (FV, HS) with MEASURED adaptation
(prereg\\P2c_biomimetic_measured_adaptation.md). Simulation only; amplitudes are MODEL units anchored to published
psychophysics, not stimulation settings. Imports code\\p2_biomimetic_info.py and code\\p2b_biomimetic_ddprime.py read-only.
Primary: perceptual divisive gain g fitted to the DIGITISED Hughes 2022 Fig 3B intermittent curve (gate A0), continuous
sessions with carried-over g. Secondary: P2's subtractive fast neuronal depression. Seed 20260926.
Usage: python p2c_biomimetic_adaptation.py test | main | sens | fig
Interpretations: code\\DEVIATIONS.md (section P2c).
"""
import csv
import json
import math
import os
import sys
import time

import numpy as np
from scipy.optimize import brentq, least_squares

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p2_biomimetic_info as p2  # noqa: E402
import p2b_biomimetic_ddprime as p2b  # noqa: E402
from p2_biomimetic_info import (DT, NT, SEED, RES, FIG, DEF, gen_episodes, a_lin, a_bio, dFdt, adapt, calibrate_w,  # noqa: E402
                                auc_w, rmse_eval, build, beta0_alpha, to_json)
from p2b_biomimetic_ddprime import Scored, noise_sd, sigma_h, ci95  # noqa: E402

DATA = r"C:\Users\mariu\neuro-company\research\somatosensory\notes\published-derived"
ARMS = ("fv", "hs")
DELTA_MIN = 0.30
A_REF = 60.0
SESSION_LEN = 250
WARM_S = 600.0
EP_S = NT * DT  # 3 s
NB_TRAIN = int(round(1.0 / DT))
PRIM = dict(p=1.0, G=3.0)  # tau_a, tau_r filled from the A0 refit
NEUR = dict(tau_n=0.04, k_ad=0.5)
TAU_N_GRID = (0.01, 0.04, 0.15)
K_GRID = (0.25, 0.5, 0.9)


# ------------------------------------------------------------------------------------------ gain model (exact per bin)
def gain_coeffs(a, tau_a, tau_r, p):
    """per-bin exact update g <- ginf + (g - ginf) q for piecewise-constant a."""
    ka = np.where(a > 0, (np.maximum(a, 0) / A_REF) ** p, 0.0) / tau_a
    kr = 1.0 / tau_r
    ktot = ka + kr
    return kr / ktot, np.exp(-ktot * DT)


def rest(g, dur, tau_r):
    return 1.0 - (1.0 - g) * math.exp(-dur / tau_r) if np.isscalar(g) else 1.0 - (1.0 - g) * np.exp(-dur / tau_r)


# ------------------------------------------------------------------------------------------ A0: Hughes 2022 intermittent
def load_fig3b():
    t, y = [], []
    with open(os.path.join(DATA, "hughes2022_fig3b_intermittent_DIGITISED.csv")) as f:
        for row in csv.reader(f):
            if not row or row[0].startswith("#") or row[0].startswith("t_s"):
                continue
            t.append(float(row[0])); y.append(float(row[1]))
    return np.array(t), np.array(y)


def load_fig2b():
    out = {}
    with open(os.path.join(DATA, "hughes2022_fig2b_burst_DIGITISED.csv")) as f:
        rows = [r for r in csv.reader(f) if r and not r[0].startswith("#")]
    hdr = rows[0]
    for r in rows[1:]:
        out[float(r[0])] = r[1:]
    return hdr, out


def intermittent_protocol():
    """(rest before train in s, train end time) for 50 adaptation + 5 recovery trains (rest-first, DEVIATIONS P2c item 2)."""
    rests = [5.0] * 50 + [61.0] * 5
    ends, t = [], 0.0
    for r in rests:
        t += r + 1.0
        ends.append(t)
    return np.array(rests), np.array(ends)


def intermittent_model(tau_a, tau_r, p=1.0):
    """train-mean g (normalised to train 0) for the 55 trains; a/60 = 1 during trains."""
    rests, ends = intermittent_protocol()
    ginf, q = gain_coeffs(np.array([A_REF]), tau_a, tau_r, p)
    ginf, q = float(ginf[0]), float(q[0])
    qn = q ** np.arange(NB_TRAIN)
    g = 1.0
    vals = []
    for i, r in enumerate(rests):
        g = rest(g, r, tau_r)
        vals.append(np.mean(ginf + (g - ginf) * qn))
        g = ginf + (g - ginf) * q ** NB_TRAIN
    vals = np.array(vals)
    return vals / vals[0], ends


def pair_index(t_dig):
    _, ends = intermittent_protocol()
    return np.argmin(np.abs(ends[None, :] - t_dig[:, None]), 1)


def fit_A0(t_dig=None, y_dig=None):
    if t_dig is None:
        t_dig, y_dig = load_fig3b()
    idx = pair_index(t_dig)

    def res(th):
        v, _ = intermittent_model(math.exp(th[0]), math.exp(th[1]))
        return v[idx] - y_dig

    best = None
    for ta0 in (5.0, 15.0, 40.0):
        for tr0 in (50.0, 150.0, 500.0):
            r = least_squares(res, [math.log(ta0), math.log(tr0)], bounds=([math.log(0.5), math.log(5)], [math.log(1e4), math.log(1e5)]),
                              x_scale=1.0, xtol=1e-12, ftol=1e-12)
            if best is None or r.cost < best.cost:
                best = r
    th = best.x
    rr = best.fun
    n, k = rr.size, 2
    s2 = (rr ** 2).sum() / (n - k)
    J = best.jac
    cov = s2 * np.linalg.inv(J.T @ J)
    se = np.sqrt(np.diag(cov))
    v, ends = intermittent_model(math.exp(th[0]), math.exp(th[1]))
    return dict(tau_a=float(math.exp(th[0])), tau_r=float(math.exp(th[1])),
                tau_a_CI95=[float(math.exp(th[0] - 1.96 * se[0])), float(math.exp(th[0] + 1.96 * se[0]))],
                tau_r_CI95=[float(math.exp(th[1] - 1.96 * se[1])), float(math.exp(th[1] + 1.96 * se[1]))],
                rmse=float(np.sqrt(np.mean(rr ** 2))), n_points=int(n), end_of_adaptation=float(v[49]),
                end_of_recovery=float(v[54]), model_train_values=v.tolist(), train_end_times=ends.tolist(),
                paired_train=idx.tolist())


def continuous_and_burst(tau_a, tau_r, p=1.0):
    ginf, q = gain_coeffs(np.array([A_REF]), tau_a, tau_r, p)
    ginf, q = float(ginf[0]), float(q[0])
    cont = {f"{s}s": float(ginf + (1 - ginf) * q ** int(round(s / DT))) for s in (5, 15)}
    burst = {}
    for bms in (100, 200, 500):
        nb = int(round(bms / 1000 / DT))
        g, gs = 1.0, []
        for t in range(int(round(30.0 / DT)) + 1):
            gs.append(g)
            on = (t // nb) % 2 == 0
            g = ginf + (g - ginf) * q if on else rest(g, DT, tau_r)
        burst[f"{bms}ms"] = {"20s": float(gs[int(round(20 / DT))]), "30s": float(gs[int(round(30 / DT))])}
    return cont, burst


# ------------------------------------------------------------------------------------------ sessions
def n_warm(G):
    return int(math.ceil(WARM_S / (EP_S + G)))


def gain_session(a, a_warm, prm, S_len=SESSION_LEN):
    """g (N, NT) for encoder amplitude a (N, NT) run as N/S_len continuous sessions with warm-up (discarded)."""
    tau_a, tau_r, p, G = prm["tau_a"], prm["tau_r"], prm["p"], prm["G"]
    N = a.shape[0]
    S = N // S_len
    assert S * S_len == N
    nw = n_warm(G)
    assert a_warm.shape[0] >= S * nw, "warm-up set too small"
    A = a.reshape(S, S_len, NT)
    W = a_warm[:S * nw].reshape(S, nw, NT)
    gi_A, q_A = gain_coeffs(A, tau_a, tau_r, p)
    gi_W, q_W = gain_coeffs(W, tau_a, tau_r, p)
    g = np.ones(S)
    out = np.empty((S, S_len, NT))
    tavg_sum = np.zeros(S)
    for e in range(nw):
        for t in range(NT):
            g = gi_W[:, e, t] + (g - gi_W[:, e, t]) * q_W[:, e, t]
        g = rest(g, G, tau_r)
    for e in range(S_len):
        ge = out[:, e]
        for t in range(NT):
            ge[:, t] = g
            g = gi_A[:, e, t] + (g - gi_A[:, e, t]) * q_A[:, e, t]
        tavg_sum += ge.sum(1) * DT + G - (1 - g) * tau_r * (1 - math.exp(-G / tau_r))
        g = rest(g, G, tau_r)
    gg = out.reshape(N, NT)
    contact = a > 0
    cm = np.array([out[s][A[s] > 0].mean() for s in range(S)])
    first = np.array([out[s, :50][A[s, :50] > 0].mean() for s in range(S)])
    last = np.array([out[s, -50:][A[s, -50:] > 0].mean() for s in range(S)])
    stats = dict(g_ss_contact=float(gg[contact].mean()), g_ss_contact_by_session=cm.tolist(),
                 g_time_avg=float((tavg_sum / (S_len * (EP_S + G))).mean()),
                 drift_last50_minus_first50=float((last - first).mean()), n_warm_episodes=nw, n_sessions=S)
    return gg, stats


# ------------------------------------------------------------------------------------------ evaluation
def observe_r(a, r, arm, w, sh, P, Z):
    return r + noise_sd(a, r, arm, w, sh, P) * Z


def eval_pair(E, yb, yl, P, boot=0, seed=SEED + 7, rmse=True):
    """Delta = d'_bio - d'_lin for given observation matrices (paired episode bootstrap, as p2b.arm_eval)."""
    sb, sl = Scored(yb, E, P), Scored(yl, E, P)
    b, l = sb.evalw(), sl.evalw()
    out = dict(dprime_bio=b["dprime"], dprime_lin=l["dprime"], Delta=b["dprime"] - l["dprime"],
               AUC_bio=[b["AUC_D1"], b["AUC_D2"]], AUC_lin=[l["AUC_D1"], l["AUC_D2"]], best_bio=b["best"], best_lin=l["best"])
    for sg, nm in ((1.0, "inc"), (-1.0, "dec")):
        bi, li = sb.evalw(sign=sg), sl.evalw(sign=sg)
        out[f"dprime_{nm}"] = dict(bio=bi["dprime"], lin=li["dprime"], Delta=bi["dprime"] - li["dprime"])
    if rmse:
        rb, rl = rmse_eval(yb, E, E["Fhold"]), rmse_eval(yl, E, E["Fhold"])
        out.update(rmse_bio=rb, rmse_lin=rl, rmse_ratio=rb / rl)
    if boot:
        rng = np.random.default_rng(seed)
        N = E["N"]
        DB, DL, RM = [], [], []
        for _ in range(boot):
            draw = rng.integers(0, N, N)
            mult = np.bincount(draw, minlength=N).astype(float)
            DB.append(sb.evalw(mult)["dprime"]); DL.append(sl.evalw(mult)["dprime"])
            if rmse:
                RM.append(rmse_eval(yb, E, E["Fhold"], order=draw) / rmse_eval(yl, E, E["Fhold"], order=draw))
        DB, DL = np.array(DB), np.array(DL)
        out.update(n_boot=boot, dprime_bio_CI95=ci95(DB), dprime_lin_CI95=ci95(DL), Delta_CI95=ci95(DB - DL))
        if rmse:
            out["rmse_ratio_CI95"] = ci95(RM)
    return out


def eval_arms(E, a_b, r_b, a_l, r_l, P, w, sh, boot=0, arms=ARMS, rmse=True):
    return {arm: eval_pair(E, observe_r(a_b, r_b, arm, w, sh, P, E["Z"]), observe_r(a_l, r_l, arm, w, sh, P, E["Z"]),
                           P, boot=boot, rmse=rmse) for arm in arms}


def arm_label(r):
    if r.get("rmse_ratio", 1.0) > 1.5:
        return "FAIL"
    lo, hi = r["Delta_CI95"]
    if r["Delta"] >= DELTA_MIN and lo > 0:
        return "PASS"
    if r["Delta"] < DELTA_MIN and hi < DELTA_MIN:
        return "FAIL"
    return "INCONCLUSIVE"


def decide(res):
    lab = {arm: arm_label(res[arm]) for arm in ARMS}
    rm_fail = any(res[arm].get("rmse_ratio", 1.0) > 1.5 for arm in ARMS)
    if rm_fail:
        v = "FAIL"
    elif all(x == "PASS" for x in lab.values()):
        v = "PASS"
    elif all(x == "FAIL" for x in lab.values()):
        v = "FAIL"
    elif lab["fv"] != lab["hs"]:
        v = "INCONCLUSIVE"
    else:
        v = "INCONCLUSIVE"
    return dict(labels=lab, verdict=v, variance_control_dependent=bool(lab["fv"] != lab["hs"]))


def floor_hit(res):
    return bool(all(max(res[arm]["AUC_bio"]) < 0.55 and max(res[arm]["AUC_lin"]) < 0.55 for arm in ARMS))


# ------------------------------------------------------------------------------------------ calibration
def jnd_gain(w, g, P):
    nT = P["T_train"] / DT
    s = P["std"]
    pg = lambda c: p2.p_greater(c, s, w, g, nT, P["sigma0"])
    if pg(0.0) >= 0.25 or pg(1e4) <= 0.75:
        return 1e6
    c25 = brentq(lambda c: pg(c) - 0.25, 0.0, s)
    c75 = brentq(lambda c: pg(c) - 0.75, s, 1e4)
    return 0.5 * (c75 - c25)


def calibrate_adapted(gss, P):
    g = np.full(NB_TRAIN, gss)
    w = brentq(lambda w: jnd_gain(w, g, P) - P["jnd"], 0.0, 10.0, xtol=1e-10)
    return w, gss * sigma_h(np.inf, P)


# ------------------------------------------------------------------------------------------ world
class World:
    """episodes, encoders, warm-up set for one step-size setting and N."""

    def __init__(self, P, n_sessions_max_warm=None):
        self.P = P
        self.E, self.dF, self.enc, self.info = build(P)
        F = self.E["F"]
        S = P["N"] // SESSION_LEN
        NW = S * n_warm(1.0)  # largest warm-up need (G = 1 s)
        Pw = dict(P, N=NW)
        Ew = gen_episodes(Pw, seed=SEED + 1000)
        self.Fw, self.dFw = Ew["F"], dFdt(Ew["F"])
        self.al0 = beta0_alpha(F, self.dF, P["D"])
        self.enc["beta0"] = a_bio(F, self.dF, self.al0, 0.0, P["D"])
        i = self.info
        self.warm = dict(lin=a_lin(self.Fw), charge=a_bio(self.Fw, self.dFw, i["alpha_charge"], i["beta_charge"], P["D"]),
                         peak=a_bio(self.Fw, self.dFw, i["alpha_peak"], i["beta_peak"], P["D"]),
                         beta0=a_bio(self.Fw, self.dFw, self.al0, 0.0, P["D"]))
        self._g = {}

    def g(self, key, prm):
        k = (key, prm["tau_a"], prm["tau_r"], prm["p"], prm["G"])
        if k not in self._g:
            self._g[k] = gain_session(self.enc[key], self.warm[key], prm)
        return self._g[k]


def perceptual(W, prm, w, sh, boot, bio="charge", calib_adapted=False):
    gb, sb = W.g(bio, prm)
    gl, sl = W.g("lin", prm)
    P = W.P
    info = {}
    if calib_adapted:
        w, sh = calibrate_adapted(sl["g_ss_contact"], P)
        info = dict(w_adapted=w, sigma_h_adapted=sh, g_ss_lin_used=sl["g_ss_contact"])
    ab, al_ = W.enc[bio], W.enc["lin"]
    res = eval_arms(W.E, ab, gb * ab, al_, gl * al_, P, w, sh, boot=boot)
    return dict(arms=res, g_bio=sb, g_lin=sl, decision=decide(res) if boot else None, floor=floor_hit(res), **info)


def neuronal(W, tau_n, k, boot, P=None):
    P = dict(W.P if P is None else P, k_ad=k)
    w = calibrate_w(tau_n, P)
    sh = sigma_h(tau_n, P)
    ab, al_ = W.enc["charge"], W.enc["lin"]
    res = eval_arms(W.E, ab, adapt(ab, tau_n, k), al_, adapt(al_, tau_n, k), P, w, sh, boot=boot)
    return dict(tau_n=tau_n, k_ad=k, w=w, sigma_h=sh, arms=res, decision=decide(res) if boot else None, floor=floor_hit(res))


# ------------------------------------------------------------------------------------------ self-test
def self_test():
    ok = {}
    r1 = p2b.self_test()
    ok["p2b_and_p2_helper_selftests_all"] = bool(all(r1.values()))
    # 1. exact integrator vs fine Euler (0.1 ms) over 60 s intermittent + amplitude variation, p = 2
    rng = np.random.default_rng(1)
    a = np.zeros(6000)
    for c in range(10):
        a[c * 600:c * 600 + 100] = rng.uniform(30, 90)
    ginf, q = gain_coeffs(a, 10.0, 80.0, 2.0)
    g, ge = 1.0, []
    for t in range(a.size):
        ge.append(g); g = ginf[t] + (g - ginf[t]) * q[t]
    gE, sub, gf = 1.0, 100, []
    for t in range(a.size):
        gf.append(gE)
        for _ in range(sub):
            gE += (DT / sub) * (-gE * (a[t] / 60) ** 2 / 10.0 + (1 - gE) / 80.0)
    ok["exact_integrator_vs_euler_0.1ms"] = bool(np.max(np.abs(np.array(ge) - np.array(gf))) < 1e-4)
    # 2. rest closed form equals stepping a = 0 bins
    gi0, q0 = gain_coeffs(np.zeros(300), 10.0, 80.0, 1.0)
    g = 0.3
    for t in range(300):
        g = gi0[t] + (g - gi0[t]) * q0[t]
    ok["rest_closed_form"] = bool(abs(g - rest(0.3, 3.0, 80.0)) < 1e-12)
    # 3. periodic steady state of 1 s on / 5 s off equals the analytic fixed point
    ta, tr = 14.6, 120.0
    gi, qq = gain_coeffs(np.array([60.0]), ta, tr, 1.0)
    Q, Rr = float(qq[0]) ** 100, math.exp(-5 / tr)
    gI = float(gi[0])
    # after on: g1 = gI + (g0 - gI) Q ; after rest: g0 = 1 - (1 - g1) Rr  -> linear fixed point
    g0 = (1 - Rr + Rr * gI * (1 - Q)) / (1 - Rr * Q)
    v, _ = intermittent_model(ta, tr)
    g = 1.0
    for _ in range(400):
        g = gI + (g - gI) * Q
        g = rest(g, 5.0, tr)
    ok["periodic_fixed_point"] = bool(abs(g - g0) < 1e-9)
    # 4. parameter recovery of the A0 fit on synthetic data at the digitised times
    t_dig, _ = load_fig3b()
    vs, _ = intermittent_model(10.0, 200.0)
    fr = fit_A0(t_dig, vs[pair_index(t_dig)])
    ok["A0_fit_parameter_recovery"] = bool(abs(fr["tau_a"] / 10 - 1) < 0.01 and abs(fr["tau_r"] / 200 - 1) < 0.01)
    # 5. tau_a -> inf gives g = 1 and the R0 path equals p2b.arm_eval bit for bit (FV and HS)
    Pt = dict(DEF, N=500)
    W = World(Pt)
    prm = dict(tau_a=1e300, tau_r=120.0, p=1.0, G=3.0)
    gb, _ = W.g("charge", prm)
    ok["g_equals_1_when_tau_a_inf"] = bool(np.all(gb == 1.0))
    w, sh = calibrate_w(np.inf, Pt), sigma_h(np.inf, Pt)
    same = True
    for arm in ARMS:
        mine = eval_pair(W.E, observe_r(W.enc["charge"], W.enc["charge"] * 1.0, arm, w, sh, Pt, W.E["Z"]),
                         observe_r(W.enc["lin"], W.enc["lin"] * 1.0, arm, w, sh, Pt, W.E["Z"]), Pt, boot=20)
        ref = p2b.arm_eval(W.E, W.enc, Pt, np.inf, arm, w, sh, boot=20)
        same &= all(abs(mine[k] - ref[k]) < 1e-12 for k in ("dprime_bio", "dprime_lin", "Delta", "rmse_ratio"))
        same &= bool(np.allclose(mine["Delta_CI95"], ref["Delta_CI95"], atol=1e-12, rtol=0))
    ok["R0_path_equals_p2b_arm_eval"] = bool(same)
    # 6. session carry-over: g at start of episode j+1 = rest(g at end of episode j after last bin update)
    prm = dict(tau_a=14.6, tau_r=120.0, p=1.0, G=3.0)
    gl, st = W.g("lin", prm)
    a0 = W.enc["lin"][0]
    gi_, q_ = gain_coeffs(a0, 14.6, 120.0, 1.0)
    gend = gi_[-1] + (gl[0, -1] - gi_[-1]) * q_[-1]
    ok["session_carry_over"] = bool(abs(gl[1, 0] - rest(gend, 3.0, 120.0)) < 1e-12)
    ok["gain_in_(0,1]"] = bool(gl.min() > 0 and gl.max() <= 1.0)
    # 7. identical encoders give Delta = 0 exactly with CI [0, 0]
    r = eval_pair(W.E, observe_r(W.enc["lin"], gl * W.enc["lin"], "fv", w, sh, Pt, W.E["Z"]),
                  observe_r(W.enc["lin"], gl * W.enc["lin"], "fv", w, sh, Pt, W.E["Z"]), Pt, boot=20)
    ok["identical_encoders_Delta_0"] = bool(r["Delta"] == 0 and r["Delta_CI95"] == [0.0, 0.0])
    # 8. adapted calibration: MC JND = 13.5 with flat gain 0.3 (Weber flat train) and HS
    P = dict(DEF)
    gss = 0.3
    wa, sha = calibrate_adapted(gss, P)
    r2 = np.random.default_rng(3)
    nT = P["T_train"] / DT
    cc = np.linspace(30, 90, 25)
    for nm in ("weber", "hs"):
        pr = []
        for c in cc:
            if nm == "weber":
                yc = (gss * c + np.sqrt(nT) * (wa * gss * c + P["sigma0"]) * r2.standard_normal((20000, 100))).sum(1)
                ys = (gss * 60 + np.sqrt(nT) * (wa * gss * 60 + P["sigma0"]) * r2.standard_normal((20000, 100))).sum(1)
            else:
                yc = (gss * c + np.sqrt(nT) * sha * r2.standard_normal((20000, 100))).sum(1)
                ys = (gss * 60 + np.sqrt(nT) * sha * r2.standard_normal((20000, 100))).sum(1)
            pr.append(np.mean(yc > ys))
        c25, c75 = np.interp(0.25, pr, cc), np.interp(0.75, pr, cc)
        ok[f"adapted_calibration_MC_JND_{nm}"] = bool(abs(0.5 * (c75 - c25) - 13.5) < 0.6)
    # 9. decision rule unit checks
    mk = lambda D, lo, hi, rm=1.0: dict(Delta=D, Delta_CI95=[lo, hi], rmse_ratio=rm)
    ok["decide_pass"] = decide(dict(fv=mk(.4, .1, .6), hs=mk(.35, .05, .6)))["verdict"] == "PASS"
    ok["decide_fail"] = decide(dict(fv=mk(.1, .0, .2), hs=mk(.05, -.02, .12)))["verdict"] == "FAIL"
    ok["decide_disagree_inconclusive"] = decide(dict(fv=mk(.4, .1, .6), hs=mk(.05, -.02, .12)))["verdict"] == "INCONCLUSIVE"
    ok["decide_rmse_fail"] = decide(dict(fv=mk(.4, .1, .6), hs=mk(.4, .1, .6, 1.6)))["verdict"] == "FAIL"
    ok["decide_ci_straddles_inconclusive"] = decide(dict(fv=mk(.2, .1, .35), hs=mk(.2, .1, .35)))["verdict"] == "INCONCLUSIVE"
    return ok


# ------------------------------------------------------------------------------------------ runs
def strip(o):
    return o


def run_main():
    t0 = time.time()
    P = dict(DEF)
    out = dict(prereg="P2c_biomimetic_measured_adaptation.md", seed=SEED, N=P["N"], note="model units, not stimulation settings")
    # ---- A0 gate
    A0 = fit_A0()
    A0["gate_rule"] = "RMSE <= 0.06 and end-of-adaptation in [0.335, 0.535]"
    A0["passed"] = bool(A0["rmse"] <= 0.06 and abs(A0["end_of_adaptation"] - 0.435) <= 0.10)
    cont, burst = continuous_and_burst(A0["tau_a"], A0["tau_r"])
    hdr, fb = load_fig2b()
    A0["descriptive_continuous_100Hz"] = dict(model=cont, quoted="5 s: median unchanged; 15 s: 64 +/- 36 %; drop onset 8.3 s (DIGITISED)")
    A0["descriptive_burst_out_of_sample"] = dict(model=burst, digitised={"20s": fb[20.0], "30s": fb[30.0]}, columns=hdr[1:])
    out["A0"] = A0
    print("A0", {k: A0[k] for k in ("tau_a", "tau_a_CI95", "tau_r", "tau_r_CI95", "rmse", "end_of_adaptation", "passed")},
          f"{time.time()-t0:.0f}s", flush=True)
    prm = dict(PRIM, tau_a=A0["tau_a"], tau_r=A0["tau_r"])
    out["primary_params"] = prm
    W = World(P)
    out["normalisation"] = W.info
    w, sh = calibrate_w(np.inf, P), sigma_h(np.inf, P)
    out["w"], out["sigma_h"] = w, sh
    # ---- R0 (g = 1)
    E = W.E
    r0 = eval_arms(E, W.enc["charge"], W.enc["charge"].copy(), W.enc["lin"], W.enc["lin"].copy(), P, w, sh, boot=0)
    with open(os.path.join(RES, "p2b_biomimetic_diff.json")) as f:
        pb = json.load(f)["primary"]
    dev = {arm: dict(dprime_bio=abs(r0[arm]["dprime_bio"] - pb[arm]["dprime_bio"]),
                     dprime_lin=abs(r0[arm]["dprime_lin"] - pb[arm]["dprime_lin"])) for arm in ARMS}
    R0ok = all(v <= 0.02 for d in dev.values() for v in d.values())
    out["R0"] = dict(results=r0, p2b_reference={a: {k: pb[a][k] for k in ("dprime_bio", "dprime_lin", "Delta")} for a in ARMS},
                     abs_dev=dev, passed=bool(R0ok))
    print("R0", {a: (round(r0[a]["dprime_bio"], 4), round(r0[a]["dprime_lin"], 4)) for a in ARMS}, R0ok, flush=True)
    if not R0ok:
        out["verdict"] = "NO VERDICT: R0 failed (code differs from P2b)"
        return _save(out, "p2c_biomimetic_adapt.json", t0)
    # ---- primary perceptual
    prim = perceptual(W, prm, w, sh, boot=1000)
    out["primary"] = prim
    print("primary", {a: (round(prim["arms"][a]["dprime_bio"], 4), round(prim["arms"][a]["dprime_lin"], 4),
                          round(prim["arms"][a]["Delta"], 4), [round(x, 4) for x in prim["arms"][a]["Delta_CI95"]]) for a in ARMS},
          prim["decision"], "g_ss", round(prim["g_bio"]["g_ss_contact"], 3), round(prim["g_lin"]["g_ss_contact"], 3),
          f"{time.time()-t0:.0f}s", flush=True)
    dec = prim["decision"]["verdict"]
    verdict = dict(decision_rule_primary=dec, A0_passed=A0["passed"], floor_primary=prim["floor"])
    if prim["floor"]:
        P2_ = dict(P, step_lo=0.3, step_hi=0.6)
        W2 = World(P2_)
        rr = perceptual(W2, prm, w, sh, boot=1000)
        out["rerun_steps_0.3_0.6"] = dict(normalisation=W2.info, result=rr)
        verdict.update(floor_rerun=rr["floor"], decision_rule_rerun=rr["decision"]["verdict"])
        print("rerun", {a: (round(rr["arms"][a]["Delta"], 4), max(rr["arms"][a]["AUC_bio"]), max(rr["arms"][a]["AUC_lin"])) for a in ARMS},
              rr["decision"], f"{time.time()-t0:.0f}s", flush=True)
        del W2
    if not A0["passed"]:
        verdict["formal"] = "NO PRIMARY VERDICT: A0 failed (tau grid reported descriptively)"
    elif prim["floor"] and verdict.get("floor_rerun"):
        verdict["formal"] = ("ABANDONED: 200-ms mean-change detection at the published JND is not measurable for either code "
                             "under variance-controlled noise (primary at AUC floor twice)")
    elif prim["floor"]:
        verdict["formal"] = verdict["decision_rule_rerun"] + " (rerun, steps U(0.3,0.6))"
    else:
        verdict["formal"] = dec
    out["verdict"] = verdict
    # ---- secondary neuronal (primary cell) and combined
    ne = neuronal(W, NEUR["tau_n"], NEUR["k_ad"], boot=1000)
    out["secondary_neuronal"] = ne
    print("neuronal", {a: (round(ne["arms"][a]["Delta"], 4), [round(x, 4) for x in ne["arms"][a]["Delta_CI95"]]) for a in ARMS},
          ne["decision"], f"{time.time()-t0:.0f}s", flush=True)
    Pk = dict(P, k_ad=NEUR["k_ad"])
    gb, _ = W.g("charge", prm)
    gl, _ = W.g("lin", prm)
    ab, al_ = W.enc["charge"], W.enc["lin"]
    comb = eval_arms(E, ab, gb * adapt(ab, NEUR["tau_n"], NEUR["k_ad"]), al_, gl * adapt(al_, NEUR["tau_n"], NEUR["k_ad"]),
                     Pk, ne["w"], ne["sigma_h"], boot=1000)
    out["combined_descriptive"] = dict(arms=comb, decision_descriptive=decide(comb))
    # ---- controls
    C = {}
    gl2, _ = gain_session(W.enc["lin"], W.warm["lin"], prm)  # linear code run through the bio slot as its own session
    nul = eval_arms(E, al_, gl2 * al_, al_, gl * al_, P, w, sh, boot=1000, rmse=False)
    C["identical_encoder_null"] = dict(Delta={a: nul[a]["Delta"] for a in ARMS}, CI={a: nul[a]["Delta_CI95"] for a in ARMS},
                                       pass_=bool(all(nul[a]["Delta_CI95"][0] <= 0 <= nul[a]["Delta_CI95"][1] for a in ARMS)))
    probe = {}
    for arm in ARMS:
        probe[arm] = dict(bio=Scored(noise_sd(ab, gb * ab, arm, w, sh, P) * E["Z"], E, P).evalw(),
                          lin=Scored(noise_sd(al_, gl * al_, arm, w, sh, P) * E["Z"], E, P).evalw())
    C["variance_only_probe"] = dict(probe=probe, pass_=bool(all(probe[a]["bio"]["dprime"] < 0.05 for a in ARMS)))
    gb0, sb0 = W.g("beta0", prm)
    b0 = eval_arms(E, W.enc["beta0"], gb0 * W.enc["beta0"], al_, gl * al_, P, w, sh, boot=0, rmse=False)
    C["beta0"] = dict(alpha=W.al0, Delta={a: b0[a]["Delta"] for a in ARMS}, pass_=bool(all(b0[a]["Delta"] < DELTA_MIN for a in ARMS)))
    Pn = dict(P, sigma0=0.0)
    nf = eval_arms(E, ab, gb * ab, al_, gl * al_, Pn, 0.0, 0.0, boot=0, rmse=False)
    C["noise_free"] = dict(AUC_bio={a: nf[a]["AUC_bio"] for a in ARMS}, AUC_lin={a: nf[a]["AUC_lin"] for a in ARMS},
                           pass_=bool(all(max(nf[a]["AUC_bio"]) > 0.99 and max(nf[a]["AUC_lin"]) > 0.99 for a in ARMS)))
    s = Scored(observe_r(ab, gb * ab, "fv", w, sh, P, E["Z"]), E, P)
    rng = np.random.default_rng(SEED + 3)
    allsc = np.concatenate([s.d1p, s.d1n])
    lab = rng.permutation(np.r_[np.ones(s.d1p.size, bool), np.zeros(s.d1n.size, bool)])
    auc_sh = auc_w(allsc[lab], np.ones(lab.sum()), allsc[~lab], np.ones((~lab).sum()))
    C["label_shuffle_fv_bio_D1"] = dict(AUC=float(auc_sh), pass_=bool(abs(auc_sh - 0.5) <= 0.02))
    pw = eval_arms(E, ab, ab.copy(), al_, al_.copy(), P, w, sh / 4, boot=200, arms=("hs",), rmse=False)["hs"]
    C["power_check_hs_sigma_h/4_g1"] = dict(dprime_bio=pw["dprime_bio"], dprime_lin=pw["dprime_lin"], Delta=pw["Delta"],
                                           Delta_CI95=pw["Delta_CI95"], reaches_030=bool(pw["Delta"] >= DELTA_MIN))
    gss = 0.5 * (prim["g_bio"]["g_ss_contact"] + prim["g_lin"]["g_ss_contact"])
    D1 = r0["hs"]["Delta"]
    ratio = prim["arms"]["hs"]["Delta"] / (gss * D1) if D1 != 0 else float("nan")
    C["gain_scaling_hs"] = dict(g_ss=gss, Delta_hs_g1=D1, predicted=gss * D1, observed=prim["arms"]["hs"]["Delta"], ratio=ratio,
                                pass_=bool(abs(ratio - 1) <= 0.25))
    out["controls"] = C
    print("controls", {k: v["pass_"] for k, v in C.items() if "pass_" in v}, f"{time.time()-t0:.0f}s", flush=True)
    pk = perceptual(W, prm, w, sh, boot=200, bio="peak")
    out["peak_matched_descriptive"] = dict(arms=pk["arms"], g_ss_peak=pk["g_bio"]["g_ss_contact"], g_ss_lin=pk["g_lin"]["g_ss_contact"],
                                           charge_ratio=W.info["charge_ratio_peak"])
    # example g traces for the figure
    np.savez_compressed(os.path.join(RES, "p2c_example.npz"), g_bio=gb[:6], g_lin=gl[:6], a_bio=ab[:6], a_lin=al_[:6])
    return _save(out, "p2c_biomimetic_adapt.json", t0)


def _save(out, name, t0):
    out["runtime_s"] = round(time.time() - t0, 1)
    with open(os.path.join(RES, name), "w") as f:
        json.dump(to_json(out), f, indent=1)
    return out


SENS_ROWS = [("tau_a 7 s", dict(tau_a=7.0)), ("tau_a 30 s", dict(tau_a=30.0)), ("tau_r 60 s", dict(tau_r=60.0)),
             ("tau_r 600 s", dict(tau_r=600.0)), ("p 0.5", dict(p=0.5)), ("p 2", dict(p=2.0)), ("G 1 s", dict(G=1.0)),
             ("G 10 s", dict(G=10.0)), ("JND calibrated adapted", dict(calib_adapted=True))]


def run_sens():
    t0 = time.time()
    with open(os.path.join(RES, "p2c_biomimetic_adapt.json")) as f:
        m = json.load(f)
    base = dict(m["primary_params"])
    prim_call = m["primary"]["decision"]["verdict"]
    P = dict(DEF, N=1000)
    W = World(P)
    w, sh = calibrate_w(np.inf, P), sigma_h(np.inf, P)
    rows = [dict(config="primary (N=4000)", call=prim_call, Delta={a: m["primary"]["arms"][a]["Delta"] for a in ARMS},
                 Delta_CI95={a: m["primary"]["arms"][a]["Delta_CI95"] for a in ARMS},
                 g_ss_bio=m["primary"]["g_bio"]["g_ss_contact"], g_ss_lin=m["primary"]["g_lin"]["g_ss_contact"])]
    for label, ch in SENS_ROWS:
        ca = ch.get("calib_adapted", False)
        prm = dict(base, **{k: v for k, v in ch.items() if k != "calib_adapted"})
        r = perceptual(W, prm, w, sh, boot=1000, calib_adapted=ca)
        row = dict(config=label, params=prm, call=r["decision"]["verdict"], labels=r["decision"]["labels"],
                   Delta={a: r["arms"][a]["Delta"] for a in ARMS}, Delta_CI95={a: r["arms"][a]["Delta_CI95"] for a in ARMS},
                   dprime_bio={a: r["arms"][a]["dprime_bio"] for a in ARMS}, dprime_lin={a: r["arms"][a]["dprime_lin"] for a in ARMS},
                   rmse_ratio={a: r["arms"][a]["rmse_ratio"] for a in ARMS}, floor=r["floor"],
                   g_ss_bio=r["g_bio"]["g_ss_contact"], g_ss_lin=r["g_lin"]["g_ss_contact"],
                   drift=[r["g_bio"]["drift_last50_minus_first50"], r["g_lin"]["drift_last50_minus_first50"]])
        if ca:
            row.update(w_adapted=r["w_adapted"], sigma_h_adapted=r["sigma_h_adapted"])
        rows.append(row)
        print(label, row["call"], {a: round(row["Delta"][a], 4) for a in ARMS}, round(row["g_ss_bio"], 3), round(row["g_ss_lin"], 3),
              f"{time.time()-t0:.0f}s", flush=True)
    n_same = sum(r["call"] == prim_call for r in rows)
    out = dict(N=1000, primary_call=prim_call, rows=rows, n_same_call=n_same, n_rows=len(rows),
               robust_VERIFIED=bool(n_same >= 7))
    # neuronal grid
    ne_call = m["secondary_neuronal"]["decision"]["verdict"]
    cells = []
    for tn in TAU_N_GRID:
        for k in K_GRID:
            if tn == NEUR["tau_n"] and k == NEUR["k_ad"]:
                ne = m["secondary_neuronal"]
                cells.append(dict(tau_n=tn, k_ad=k, N=4000, call=ne["decision"]["verdict"], Delta={a: ne["arms"][a]["Delta"] for a in ARMS},
                                  Delta_CI95={a: ne["arms"][a]["Delta_CI95"] for a in ARMS}))
                continue
            r = neuronal(W, tn, k, boot=1000)
            cells.append(dict(tau_n=tn, k_ad=k, N=1000, call=r["decision"]["verdict"], labels=r["decision"]["labels"],
                              Delta={a: r["arms"][a]["Delta"] for a in ARMS}, Delta_CI95={a: r["arms"][a]["Delta_CI95"] for a in ARMS},
                              dprime_bio={a: r["arms"][a]["dprime_bio"] for a in ARMS}, dprime_lin={a: r["arms"][a]["dprime_lin"] for a in ARMS},
                              rmse_ratio={a: r["arms"][a]["rmse_ratio"] for a in ARMS}, floor=r["floor"], w=r["w"], sigma_h=r["sigma_h"]))
            print("neur", tn, k, cells[-1]["call"], {a: round(cells[-1]["Delta"][a], 4) for a in ARMS}, f"{time.time()-t0:.0f}s", flush=True)
    n_same_n = sum(c["call"] == ne_call for c in cells)
    out["neuronal_grid"] = dict(primary_cell_call=ne_call, cells=cells, n_same_call=n_same_n, n_cells=len(cells),
                                robust_VERIFIED=bool(n_same_n >= 7))
    return _save(out, "p2c_biomimetic_adapt_sens.json", t0)


# ------------------------------------------------------------------------------------------ figures
def figures():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    with open(os.path.join(RES, "p2c_biomimetic_adapt.json")) as f:
        o = json.load(f)
    NOTE = "Model simulation in model units; NOT stimulation settings."
    # --- A0 fit figure
    A0 = o["A0"]
    t_dig, y_dig = load_fig3b()
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.6))
    a = ax[0]
    a.plot(t_dig, y_dig, "o", color="#1f5fa8", ms=4, label="Hughes 2022 Fig 3B (DIGITISED mean, 7 electrodes)")
    a.plot(A0["train_end_times"], A0["model_train_values"], "-", color="#c0392b", lw=1.2,
           label=f"gain model fit: τ_a {A0['tau_a']:.1f} s on-time, τ_r {A0['tau_r']:.0f} s (RMSE {A0['rmse']:.3f})")
    a.axhline(0.435, color="#999", ls=":", lw=1, label="quoted end of adaptation 43.5%")
    a.axhline(0.726, color="#999", ls="--", lw=1, label="quoted end of recovery 72.6%")
    a.set_xlabel("time from first train (s)"); a.set_ylabel("normalised percept intensity (train-mean gain g)")
    a.set_title(f"A0 gate: {'PASS' if A0['passed'] else 'FAIL'} (1 s on / 5 s off ×50, then 61 s rests ×5)", fontsize=9)
    a.legend(fontsize=7)
    b = ax[1]
    hdr, fb = load_fig2b()
    ts = sorted(fb)
    cols = ("#1f5fa8", "#2e7d32", "#b8860b")
    for j, (nm, c) in enumerate(zip(("100 ms", "200 ms", "500 ms"), cols)):
        xs, ys = [], []
        for t in ts:
            v = fb[t][j]
            try:
                ys.append(float(v)); xs.append(t)
            except ValueError:
                if v.startswith("1.0"):
                    ys.append(1.0); xs.append(t)
        b.plot(xs, ys, "-", color=c, lw=1, label=f"DIGITISED median, {nm} bursts")
    tau_a, tau_r = A0["tau_a"], A0["tau_r"]
    ginf, q = gain_coeffs(np.array([A_REF]), tau_a, tau_r, 1.0)
    for bms, c in zip((100, 200, 500), cols):
        nb = int(round(bms / 1000 / DT)); g = 1.0; gs = []
        for t in range(6001):
            gs.append(g)
            g = float(ginf[0] + (g - ginf[0]) * q[0]) if (t // nb) % 2 == 0 else rest(g, DT, tau_r)
        b.plot(np.arange(6001) * DT, gs, ":", color=c, lw=1.5, label=f"model g, {bms} ms bursts" if bms == 100 else None)
    b.set_xlabel("time from burst-train onset (s)"); b.set_ylabel("normalised percept intensity")
    b.set_title("out-of-sample (descriptive): 50%-duty bursts, 100 Hz 60 µA (Fig 2B)", fontsize=9)
    b.legend(fontsize=7)
    fig.suptitle("P2c perceptual adaptation model fitted to digitised human data. " + NOTE, fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    for ext in ("png", "svg"):
        fig.savefig(os.path.join(FIG, f"p2c_adaptation_fit.{ext}"), dpi=150)
    plt.close(fig)
    # --- Delta by arm
    sp = os.path.join(RES, "p2c_biomimetic_adapt_sens.json")
    s = json.load(open(sp)) if os.path.exists(sp) else None
    fig, ax = plt.subplots(1, 3 if s else 1, figsize=(18 if s else 7, 5.5))
    ax = np.atleast_1d(ax)
    a = ax[0]
    conds = [("g = 1 (R0)", o["R0"]["results"])]
    conds.append(("perceptual\n(PRIMARY)", o["primary"]["arms"]))
    if "rerun_steps_0.3_0.6" in o:
        conds.append(("perceptual rerun\nsteps 30-60%", o["rerun_steps_0.3_0.6"]["result"]["arms"]))
    conds.append(("neuronal\n(SECONDARY)", o["secondary_neuronal"]["arms"]))
    conds.append(("combined\n(descriptive)", o["combined_descriptive"]["arms"]))
    conds.append(("peak-matched\n(descriptive)", o["peak_matched_descriptive"]["arms"]))
    cc = dict(fv="#1f5fa8", hs="#2e7d32")
    for i, (nm, r) in enumerate(conds):
        for j, arm in enumerate(ARMS):
            d = r[arm]["Delta"]
            x = i + (j - 0.5) * 0.3
            if "Delta_CI95" in r[arm]:
                lo, hi = r[arm]["Delta_CI95"]
                a.errorbar(x, d, yerr=[[d - lo], [hi - d]], fmt="o", color=cc[arm], capsize=4, label=arm.upper() if i == 1 else None)
            else:
                a.plot(x, d, "o", mfc="none", color=cc[arm], label=None)
    a.axhline(DELTA_MIN, color="k", ls="--", lw=1, label="Δ_min = 0.30")
    a.axhline(0, color="#999", lw=0.8)
    a.set_xticks(range(len(conds))); a.set_xticklabels([c[0] for c in conds], fontsize=7)
    a.set_xlabel("adaptation model (charge-matched codes)")
    a.set_ylabel("Δ = d'_bio − d'_lin, 200-ms step detection (95% CI)")
    a.set_title(f"P2c primary verdict: {o['verdict']['formal'].split(':')[0]}; decision rule: {o['verdict']['decision_rule_primary']}", fontsize=9)
    a.legend(fontsize=7)
    if s:
        b = ax[1]
        rows = s["rows"]
        y = np.arange(len(rows))
        for arm, mk in zip(ARMS, ("o", "^")):
            b.errorbar([r["Delta"][arm] for r in rows], y + (0.15 if arm == "hs" else -0.15),
                       xerr=np.array([[r["Delta"][arm] - r["Delta_CI95"][arm][0], r["Delta_CI95"][arm][1] - r["Delta"][arm]] for r in rows]).T,
                       fmt=mk, color=cc[arm], capsize=2, label=arm.upper())
        b.axvline(DELTA_MIN, color="k", ls="--", lw=1); b.axvline(0, color="#999", lw=0.8)
        b.set_yticks(y); b.set_yticklabels([f"{r['config']} [{r['call']}]" for r in rows], fontsize=7); b.invert_yaxis()
        b.set_xlabel("Δ = d'_bio − d'_lin (95% CI)"); b.set_ylabel("perceptual-model robustness row (N = 1000)")
        b.set_title(f"robustness: same call {s['n_same_call']}/{s['n_rows']} (VERIFIED needs ≥ 7)", fontsize=9)
        b.legend(fontsize=7)
        c = ax[2]
        ng = s["neuronal_grid"]["cells"]
        M = np.zeros((3, 3, 2))
        for cell in ng:
            i, j = TAU_N_GRID.index(cell["tau_n"]), K_GRID.index(cell["k_ad"])
            M[i, j] = [cell["Delta"]["fv"], cell["Delta"]["hs"]]
        im = c.imshow(M[:, :, 1], cmap="viridis", origin="lower")
        for cell in ng:
            i, j = TAU_N_GRID.index(cell["tau_n"]), K_GRID.index(cell["k_ad"])
            c.text(j, i, f"FV {cell['Delta']['fv']:.2f}\nHS {cell['Delta']['hs']:.2f}\n{cell['call']}", ha="center", va="center",
                   fontsize=7, color="w")
        c.set_xticks(range(3)); c.set_xticklabels([str(k) for k in K_GRID]); c.set_yticks(range(3))
        c.set_yticklabels([f"{t*1000:.0f} ms" for t in TAU_N_GRID])
        c.set_xlabel("neuronal depression depth k_ad (model)"); c.set_ylabel("neuronal depression τ_n (model)")
        c.set_title(f"secondary neuronal grid: Δ (colour = HS), same call {s['neuronal_grid']['n_same_call']}/9", fontsize=9)
        fig.colorbar(im, ax=c, label="Δ_HS")
    fig.suptitle("P2c: biomimetic minus linear d' under variance-controlled noise with measured adaptation. " + NOTE, fontsize=9.5)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    for ext in ("png", "svg"):
        fig.savefig(os.path.join(FIG, f"p2c_delta_by_arm.{ext}"), dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "test"
    os.makedirs(RES, exist_ok=True)
    os.makedirs(FIG, exist_ok=True)
    if mode == "test":
        r = self_test()
        print("SELF-TEST", r, "ALL PASS" if all(r.values()) else "FAILURES")
        with open(os.path.join(RES, "p2c_selftest.json"), "w") as f:
            json.dump(r, f, indent=1)
        sys.exit(0 if all(r.values()) else 1)
    if mode == "main":
        o = run_main()
        print(json.dumps(to_json({k: o.get(k) for k in ("verdict", "controls", "runtime_s")}), indent=1))
    if mode == "sens":
        o = run_sens()
        print("robust", o["n_same_call"], "/", o["n_rows"], "neuronal", o["neuronal_grid"]["n_same_call"], "/ 9", o["runtime_s"])
    if mode in ("fig", "main", "sens"):
        figures()
