"""P2b: biomimetic vs linear ICMS encoding, well-posed d' difference plus Weber-variance-cue controls
(prereg\\P2b_biomimetic_dprime_difference.md). Simulation only; amplitudes are MODEL units anchored to published
psychophysics, not stimulation settings. Reuses code\\p2_biomimetic_info.py (read-only import). Seed 20260926.
Noise arms: WEBER (cycle-1 noise, regression gate R0), FV (frozen variance: per-episode constant sd from mean r),
HS (homoscedastic sd calibrated to the same JND).
Usage: python p2b_biomimetic_ddprime.py test | main | sens | fig
Interpretations: code\\DEVIATIONS.md (section P2b).
"""
import json
import os
import sys
import time

import numpy as np
from scipy.special import ndtri

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p2_biomimetic_info as p2  # noqa: E402
from p2_biomimetic_info import (DT, NT, TAUS, SEED, RES, FIG, DEF, gen_episodes, a_lin, a_bio, dFdt, adapt,  # noqa: E402
                                flat_gain, calibrate_w, scores, auc_w, dprime, rmse_eval, build, beta0_alpha, to_json)

ARMS = ("weber", "fv", "hs")
DELTA_MIN = 0.30
Z75 = float(ndtri(0.75))


# ------------------------------------------------------------------------------------------ noise arms
def sigma_h(tau, P):
    """HS arm: constant per-train sd giving JND = P['jnd'] for two 1-s flat trains (Gaussian link), per tau_ad.
    For tau = inf: 13.5 / (Phi^-1(.75) sqrt 2) = 14.15 model-uA (prereg C4)."""
    n_cal = int(round(1.0 / DT))
    nT = P["T_train"] / DT
    G = flat_gain(tau, n_cal, P["k_ad"]).sum()
    # sum_t y over the train: mean c*G, var n_cal * nT * sh^2 ; difference of two trains: sd sqrt(2 n_cal nT) sh
    # JND = Z75 * sd / G  ->  sh = JND * G / (Z75 * sqrt(2 n_cal nT)); sh is expressed per train (per-sample sd = sqrt(nT) sh)
    return P["jnd"] * G / (Z75 * np.sqrt(2 * n_cal * nT))


def noise_sd(a, r, arm, w, sh, P):
    nT = P["T_train"] / DT
    if arm == "weber":
        return np.sqrt(nT) * (w * r + P["sigma0"])
    if arm == "hs":
        return np.full(r.shape, np.sqrt(nT) * sh)
    if arm == "fv":
        contact = a > 0
        n = contact.sum(1)
        rbar = np.where(n > 0, (r * contact).sum(1) / np.maximum(n, 1), 0.0)
        sd_c = np.sqrt(nT) * (w * rbar + P["sigma0"])
        return np.where(contact, sd_c[:, None], np.sqrt(nT) * (w * r + P["sigma0"]))
    raise ValueError(arm)


def observe_arm(a, tau, arm, w, sh, P, Z):
    r = adapt(a, tau, P["k_ad"])
    return r + noise_sd(a, r, arm, w, sh, P) * Z


# ------------------------------------------------------------------------------------------ detection with cached scores
class Scored:
    """Detector scores computed once for one observation matrix y; AUC / d' for any episode weighting."""

    def __init__(self, y, E, P):
        self.E = E
        self.d1p, self.d2p = scores(y, E["ev_ep"], E["ev_idx"], P)
        self.d1n, self.d2n = scores(y, E["nu_ep"], E["nu_idx"], P)
        self.y = y

    def evalw(self, mult=None, sign=None):
        E = self.E
        sel = np.ones(E["ev_ep"].size, bool) if sign is None else (E["ev_sign"] == sign)
        pe = E["ev_ep"][sel]
        pw = np.ones(pe.size) if mult is None else mult[pe]
        nw = np.ones(E["nu_ep"].size) if mult is None else mult[E["nu_ep"]]
        a1 = auc_w(self.d1p[sel], pw, self.d1n, nw)
        a2 = auc_w(self.d2p[sel], pw, self.d2n, nw)
        return dict(AUC_D1=float(a1), AUC_D2=float(a2), dprime=float(max(dprime(a1), dprime(a2))),
                    best="D1" if a1 >= a2 else "D2")


def ci95(x):
    x = np.asarray(x, float)
    return [float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))]


def arm_eval(E, enc, P, tau, arm, w, sh, boot=0, seed=SEED + 7, rmse=True):
    """Delta = d'_bio - d'_lin (charge-matched) for one noise arm. Paired bootstrap over episodes."""
    yb = observe_arm(enc["charge"], tau, arm, w, sh, P, E["Z"])
    yl = observe_arm(enc["lin"], tau, arm, w, sh, P, E["Z"])
    sb, sl = Scored(yb, E, P), Scored(yl, E, P)
    b, l = sb.evalw(), sl.evalw()
    out = dict(arm=arm, tau=tau, dprime_bio=b["dprime"], dprime_lin=l["dprime"], Delta=b["dprime"] - l["dprime"],
               dprime_ratio_descriptive=b["dprime"] / l["dprime"] if l["dprime"] != 0 else None,
               AUC_bio=[b["AUC_D1"], b["AUC_D2"]], AUC_lin=[l["AUC_D1"], l["AUC_D2"]], best_bio=b["best"], best_lin=l["best"])
    for sg, nm in ((1.0, "inc"), (-1.0, "dec")):
        bi, li = sb.evalw(sign=sg), sl.evalw(sign=sg)
        out[f"dprime_{nm}"] = dict(bio=bi["dprime"], lin=li["dprime"], Delta=bi["dprime"] - li["dprime"],
                                   best_bio=bi["best"], best_lin=li["best"])
    if rmse:
        rb, rl = rmse_eval(yb, E, E["Fhold"]), rmse_eval(yl, E, E["Fhold"])
        out.update(rmse_bio=rb, rmse_lin=rl, rmse_ratio=rb / rl,
                   rmse_ratio_trueforce=rmse_eval(yb, E, E["Fwin"]) / rmse_eval(yl, E, E["Fwin"]))
    if boot:
        rng = np.random.default_rng(seed)
        N = E["N"]
        DB, DL, RM = [], [], []
        for _ in range(boot):
            draw = rng.integers(0, N, N)
            mult = np.bincount(draw, minlength=N).astype(float)
            DB.append(sb.evalw(mult)["dprime"])
            DL.append(sl.evalw(mult)["dprime"])
            if rmse:
                RM.append(rmse_eval(yb, E, E["Fhold"], order=draw) / rmse_eval(yl, E, E["Fhold"], order=draw))
        DB, DL = np.array(DB), np.array(DL)
        out.update(n_boot=boot, dprime_bio_CI95=ci95(DB), dprime_lin_CI95=ci95(DL), Delta_CI95=ci95(DB - DL))
        if rmse:
            out["rmse_ratio_CI95"] = ci95(RM)
        out["_boot_Delta"] = DB - DL
    return out


def variance_only_probe(E, enc, P, tau, w, key="charge"):
    """Mean held constant during the hold (no mean step), noise sd time course of the WEBER arm of encoder `key`.
    Difference detectors cancel any constant mean inside the hold, so mean = 0 is used (see DEVIATIONS P2b)."""
    r = adapt(enc[key], tau, P["k_ad"])
    y = noise_sd(enc[key], r, "weber", w, None, P) * E["Z"]
    return Scored(y, E, P).evalw()


def decide(res_w, res_fv, res_hs=None):
    Dw, Df = res_w["Delta"], res_fv["Delta"]
    V = 1 - Df / Dw if Dw != 0 else np.nan
    rm = res_w["rmse_ratio"]

    def rule(Dw_lo, Dx, Dx_lo, Dx_hi, Vx):
        if Dw_lo >= DELTA_MIN and Dx_lo >= DELTA_MIN and Vx <= 0.5 and rm <= 1.5:
            return "PASS"
        if Dx_hi < DELTA_MIN or Vx > 0.5 or rm > 1.5:
            return "FAIL"
        return "INCONCLUSIVE"

    v_fv = rule(res_w["Delta_CI95"][0], Df, res_fv["Delta_CI95"][0], res_fv["Delta_CI95"][1], V)
    out = dict(V_fv=V, verdict_fv=v_fv, rmse_ratio=rm)
    verdict = v_fv
    if v_fv == "FAIL" and V > 0.5:
        verdict = "FAIL (biomimetic advantage is a Weber-variance artefact)"
    if res_hs is not None:
        Vh = 1 - res_hs["Delta"] / Dw if Dw != 0 else np.nan
        v_hs = rule(res_w["Delta_CI95"][0], res_hs["Delta"], res_hs["Delta_CI95"][0], res_hs["Delta_CI95"][1], Vh)
        out.update(V_hs=Vh, verdict_hs=v_hs)
        # disagreement = the two arms do not give the same PASS/FAIL/INCONCLUSIVE label; a PASS is downgraded whenever HS
        # is not also PASS (conservative reading, DEVIATIONS P2b item 7)
        out["variance_control_dependent"] = bool(v_fv != v_hs)
        if v_fv == "PASS" and v_hs != "PASS":
            verdict = f"INCONCLUSIVE (variance-control dependent: FV PASS, HS {v_hs})"
        elif v_fv != v_hs:
            verdict = verdict + f" (variance-control dependent: HS {v_hs})"
    out["verdict"] = verdict
    return out


# ------------------------------------------------------------------------------------------ self-test
def self_test():
    ok = {}
    r1 = p2.self_test()
    ok["cycle1_helper_selftests(11)"] = bool(all(r1.values()))
    P = dict(DEF)
    # 1. HS sigma_h at tau = inf equals the prereg value 14.15
    ok["sigma_h_inf_=14.15"] = bool(abs(sigma_h(np.inf, P) - 13.5 / (Z75 * np.sqrt(2))) < 1e-9 and
                                    abs(sigma_h(np.inf, P) - 14.15) < 0.01)
    # 2. HS calibration by Monte Carlo (tau = inf and 0.3): JND of two 1-s flat trains with constant noise = 13.5
    r2 = np.random.default_rng(3)
    nT = P["T_train"] / DT
    for tau in (np.inf, 0.3):
        g = flat_gain(tau, 100)
        sh = sigma_h(tau, P)
        cc = np.linspace(30, 90, 25)
        pr = []
        for c in cc:
            yc = (c * g + np.sqrt(nT) * sh * r2.standard_normal((20000, 100))).sum(1)
            ys = (60 * g + np.sqrt(nT) * sh * r2.standard_normal((20000, 100))).sum(1)
            pr.append(np.mean(yc > ys))
        c25, c75 = np.interp(0.25, pr, cc), np.interp(0.75, pr, cc)
        ok[f"hs_calibration_MC_JND_tau={tau}"] = bool(abs(0.5 * (c75 - c25) - 13.5) < 0.6)
    # 3. Weber arm reproduces p2.observe bit-for-bit
    Pt = dict(DEF, N=200)
    E, dF, enc, info = build(Pt, gen_episodes(Pt, seed=5))
    w = calibrate_w(np.inf, Pt)
    ok["weber_arm_equals_cycle1_observe"] = bool(np.array_equal(observe_arm(enc["charge"], np.inf, "weber", w, None, Pt, E["Z"]),
                                                                p2.observe(enc["charge"], np.inf, w, Pt, E["Z"])))
    # 4. FV arm: sd constant over contact samples of each episode, and equals sqrt(nT)(w rbar + sigma0)
    r = adapt(enc["charge"], np.inf)
    sd = noise_sd(enc["charge"], r, "fv", w, None, Pt)
    c = enc["charge"] > 0
    const = all(np.ptp(sd[i, c[i]]) < 1e-9 for i in range(Pt["N"]) if c[i].any())
    rb = np.array([r[i, c[i]].mean() for i in range(Pt["N"])])
    ok["fv_sd_constant_per_episode"] = bool(const)
    ok["fv_sd_value"] = bool(np.allclose([sd[i, c[i]][0] for i in range(Pt["N"])], np.sqrt(nT) * (w * rb + Pt["sigma0"])))
    # 5. FV average noise power roughly matched across encoders under charge matching (mean rbar within 5%)
    rl = adapt(enc["lin"], np.inf)
    cl = enc["lin"] > 0
    rbl = np.array([rl[i, cl[i]].mean() for i in range(Pt["N"])])
    ok["fv_mean_rbar_matched_5pct"] = bool(abs(rb.mean() / rbl.mean() - 1) < 0.05)
    # 6. variance cue exists by construction: pure variance step (sd x2 after onset, mean 0) is detected (AUC > 0.6);
    #    a pure mean step with constant noise has AUC ~ 0.5 in |.| detector only when the step is 0
    Z = np.random.default_rng(8).standard_normal((Pt["N"], NT))
    y = Z.copy()
    for ep, k in zip(E["ev_ep"], E["ev_idx"]):
        y[ep, k:k + 20] *= 3.0
    ok["variance_step_detectable_by_abs_detectors"] = bool(Scored(y, E, Pt).evalw()["AUC_D1"] > 0.6)
    ok["pure_noise_AUC_~0.5"] = bool(abs(Scored(Z, E, Pt).evalw()["AUC_D1"] - 0.5) < 0.05)
    # 7. Scored AUC equals p2.encoder_eval
    y = p2.observe(enc["charge"], np.inf, w, Pt, E["Z"])
    e1 = p2.encoder_eval(y, E, Pt)
    e2 = Scored(y, E, Pt).evalw()
    ok["scored_equals_encoder_eval"] = bool(abs(e1["AUC_D1"] - e2["AUC_D1"]) < 1e-12 and abs(e1["dprime"] - e2["dprime"]) < 1e-12)
    # 8. decision rule unit checks
    mk = lambda D, lo, hi: dict(Delta=D, Delta_CI95=[lo, hi], rmse_ratio=1.0)
    ok["decide_pass"] = decide(mk(.5, .45, .55), mk(.45, .35, .55))["verdict"] == "PASS"
    ok["decide_fail_V"] = decide(mk(.5, .45, .55), mk(.2, .1, .31))["verdict"].startswith("FAIL (biomimetic advantage is a Weber")
    ok["decide_inconclusive"] = decide(mk(.5, .45, .55), mk(.3, .25, .35))["verdict"] == "INCONCLUSIVE"
    ok["decide_hs_disagree_downgrade"] = decide(mk(.5, .45, .55), mk(.45, .35, .55), mk(.1, .0, .2))["verdict"].startswith("INCONCLUSIVE")
    return ok


# ------------------------------------------------------------------------------------------ runs
def strip(d):
    return {k: v for k, v in d.items() if not k.startswith("_")}


def run_main(tau_sweep=True):
    t0 = time.time()
    P = dict(DEF)
    E, dF, enc, info = build(P)
    w = calibrate_w(np.inf, P)
    sh = sigma_h(np.inf, P)
    out = dict(prereg="P2b_biomimetic_dprime_difference.md", seed=SEED, N=P["N"], normalisation=info,
               w_inf=w, sigma_h_inf=sh, Delta_min=DELTA_MIN)
    prim = {}
    for arm in ARMS:
        prim[arm] = arm_eval(E, enc, P, np.inf, arm, w, sh, boot=1000)
        print(arm, round(prim[arm]["dprime_bio"], 4), round(prim[arm]["dprime_lin"], 4), "Delta", round(prim[arm]["Delta"], 4),
              prim[arm]["Delta_CI95"], f"{time.time()-t0:.0f}s", flush=True)
    out["primary"] = {k: strip(v) for k, v in prim.items()}
    # R0 regression gate
    Dw, db = prim["weber"]["Delta"], prim["weber"]["dprime_bio"]
    R0 = abs(Dw - 0.52) <= 0.02 and abs(db - 0.542) <= 0.02
    out["R0"] = dict(Delta_weber=Dw, dprime_bio_weber=db, passed=bool(R0),
                     rule="|Delta - 0.52| <= 0.02 and |d'_bio - 0.542| <= 0.02")
    if not R0:
        out["verdict"] = "NO VERDICT: regression gate R0 failed (code differs from cycle 1)"
        _save(out, t0)
        return out
    # abandonment check on FV arm
    fv = prim["fv"]
    aucs = [max(fv["AUC_bio"]), max(fv["AUC_lin"])]
    floor_ = all(a < 0.55 for a in aucs)
    out["abandonment_check_fv"] = dict(AUC_best_bio=aucs[0], AUC_best_lin=aucs[1], floor=bool(floor_))
    dec = decide(prim["weber"], prim["fv"], prim["hs"])
    out["decision_primary"] = dec
    out["verdict"] = dec["verdict"]
    if floor_:
        P2_ = dict(P, step_lo=0.3, step_hi=0.6)
        E2, _, enc2, info2 = build(P2_)
        rr = {arm: arm_eval(E2, enc2, P2_, np.inf, arm, w, sh, boot=1000) for arm in ARMS}
        a2 = [max(rr["fv"]["AUC_bio"]), max(rr["fv"]["AUC_lin"])]
        out["rerun_fv_steps_0.3_0.6"] = dict(normalisation=info2, results={k: strip(v) for k, v in rr.items()},
                                             AUC_best_fv=a2, floor=bool(all(a < 0.55 for a in a2)))
        if all(a < 0.55 for a in a2):
            out["verdict"] = ("ABANDONED: at the published JND with per-bin noise, 200-ms step detection is not "
                              "measurable for either code (FV arm at floor twice)")
        else:
            d2 = decide(rr["weber"], rr["fv"], rr["hs"])
            out["decision_rerun"] = d2
            out["verdict"] = d2["verdict"] + " (rerun, steps U(0.3,0.6))"
    # variance-only probe
    out["variance_only_probe"] = dict(bio=variance_only_probe(E, enc, P, np.inf, w, "charge"),
                                      lin=variance_only_probe(E, enc, P, np.inf, w, "lin"))
    print("probe", out["variance_only_probe"], f"{time.time()-t0:.0f}s", flush=True)
    # controls
    F = E["F"]
    al0 = beta0_alpha(F, dF, P["D"])
    enc_b0 = dict(lin=enc["lin"], charge=a_bio(F, dF, al0, 0.0, P["D"]))
    b0 = {arm: arm_eval(E, enc_b0, P, np.inf, arm, w, sh, rmse=False) for arm in ARMS}
    Pn = dict(P, sigma0=0.0)
    nf = arm_eval(E, enc, Pn, np.inf, "weber", 0.0, 0.0, rmse=False)
    yb = observe_arm(enc["charge"], np.inf, "fv", w, sh, P, E["Z"])
    s = Scored(yb, E, P)
    rng = np.random.default_rng(SEED + 3)
    allsc = np.concatenate([s.d1p, s.d1n])
    lab = rng.permutation(np.r_[np.ones(s.d1p.size, bool), np.zeros(s.d1n.size, bool)])
    auc_sh = auc_w(allsc[lab], np.ones(lab.sum()), allsc[~lab], np.ones((~lab).sum()))
    out["controls"] = dict(
        beta0=dict(alpha=al0, Delta={k: v["Delta"] for k, v in b0.items()},
                   pass_=bool(all(v["Delta"] < DELTA_MIN for v in b0.values()))),
        noise_free=dict(AUC_bio=nf["AUC_bio"], AUC_lin=nf["AUC_lin"],
                        pass_=bool(max(nf["AUC_bio"]) > 0.99 and max(nf["AUC_lin"]) > 0.99)),
        label_shuffle_fv_bio_D1=dict(AUC=float(auc_sh), pass_=bool(abs(auc_sh - 0.5) < 0.02)))
    # peak-matched variant (descriptive)
    out["peak_matched_descriptive"] = {arm: strip(arm_eval(E, dict(lin=enc["lin"], charge=enc["peak"]), P, np.inf, arm, w, sh))
                                       for arm in ARMS}
    # exploratory tau_ad sweep, all arms (point estimates + 200-resample CI of Delta)
    if tau_sweep:
        sweep = {}
        for tau in TAUS:
            wt = calibrate_w(tau, P)
            sht = sigma_h(tau, P)
            sweep[str(tau)] = dict(w=wt, sigma_h=sht)
            for arm in ARMS:
                r = arm_eval(E, enc, P, tau, arm, wt, sht, boot=200 if np.isfinite(tau) else 0, rmse=True)
                sweep[str(tau)][arm] = strip(r)
            print("tau", tau, {a: round(sweep[str(tau)][a]["Delta"], 3) for a in ARMS}, f"{time.time()-t0:.0f}s", flush=True)
        out["tau_sweep_exploratory"] = sweep
    _save(out, t0)
    return out


def _save(out, t0):
    out["runtime_s"] = round(time.time() - t0, 1)
    with open(os.path.join(RES, "p2b_biomimetic_diff.json"), "w") as f:
        json.dump(to_json(out), f, indent=1)


SENS = p2.SENS


def run_sens():
    t0 = time.time()
    rows = []
    for label, ch in [("baseline (N=2000)", {})] + SENS:
        P = dict(DEF, N=2000, **ch)
        E, dF, enc, info = build(P)
        w = calibrate_w(np.inf, P) * P["w_scale"]
        sh = sigma_h(np.inf, P) * P["w_scale"]
        row = dict(config=label, w=w, sigma_h=sh, alpha=info["alpha_charge"], beta=info["beta_charge"])
        for arm in ARMS:
            r = arm_eval(E, enc, P, np.inf, arm, w, sh, rmse=(arm == "weber"))
            row[arm] = dict(dprime_bio=r["dprime_bio"], dprime_lin=r["dprime_lin"], Delta=r["Delta"])
            if arm == "weber":
                row["rmse_ratio"] = r["rmse_ratio"]
        row["V_fv"] = 1 - row["fv"]["Delta"] / row["weber"]["Delta"] if row["weber"]["Delta"] != 0 else None
        rows.append(row)
        print(label, {a: round(row[a]["Delta"], 3) for a in ARMS}, f"{time.time()-t0:.0f}s", flush=True)
    cfg = rows[1:]
    out = {"N": 2000, "rows": rows, "runtime_s": round(time.time() - t0, 1),
           "n_fv_Delta_ge_0.30": int(sum(r["fv"]["Delta"] >= DELTA_MIN for r in cfg)),
           "n_hs_Delta_ge_0.30": int(sum(r["hs"]["Delta"] >= DELTA_MIN for r in cfg)),
           "n_weber_Delta_ge_0.30": int(sum(r["weber"]["Delta"] >= DELTA_MIN for r in cfg)), "n_configs": len(cfg)}
    with open(os.path.join(RES, "p2b_biomimetic_diff_sensitivity.json"), "w") as f:
        json.dump(to_json(out), f, indent=1)
    return out


def figures():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    with open(os.path.join(RES, "p2b_biomimetic_diff.json")) as f:
        o = json.load(f)
    cols = dict(weber="#b8860b", fv="#1f5fa8", hs="#2e7d32")
    names = dict(weber="Weber (cycle-1 noise)", fv="frozen variance (FV)", hs="homoscedastic (HS)")
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.8))
    a = ax[0]
    x = np.arange(3)
    for i, arm in enumerate(ARMS):
        r = o["primary"][arm]
        a.bar(i - 0.2, r["dprime_bio"], 0.38, color=cols[arm], label="d'_bio" if i == 0 else None)
        a.bar(i + 0.2, r["dprime_lin"], 0.38, color=cols[arm], alpha=0.35, hatch="//", label="d'_lin" if i == 0 else None)
        lo, hi = r["dprime_bio_CI95"]
        a.errorbar(i - 0.2, r["dprime_bio"], yerr=[[r["dprime_bio"] - lo], [hi - r["dprime_bio"]]], color="k", capsize=3)
        lo, hi = r["dprime_lin_CI95"]
        a.errorbar(i + 0.2, r["dprime_lin"], yerr=[[r["dprime_lin"] - lo], [hi - r["dprime_lin"]]], color="k", capsize=3)
    pb = o["variance_only_probe"]["bio"]["dprime"]
    a.axhline(pb, color="#c0392b", ls=":", lw=1.2, label=f"variance-only probe d' (bio) = {pb:.2f}")
    a.set_xticks(x); a.set_xticklabels([names[k] for k in ARMS], fontsize=8)
    a.set_xlabel("observation-noise arm (model)")
    a.set_ylabel("d' for ±10–30% force steps within 200 ms")
    a.set_title("d' per encoder (charge-matched, τ_ad = ∞)", fontsize=9)
    a.legend(fontsize=7)
    b = ax[1]
    for i, arm in enumerate(ARMS):
        r = o["primary"][arm]
        lo, hi = r["Delta_CI95"]
        b.errorbar(i, r["Delta"], yerr=[[r["Delta"] - lo], [hi - r["Delta"]]], fmt="o", color=cols[arm], capsize=5, ms=8)
    b.axhline(DELTA_MIN, color="k", ls="--", lw=1, label="Δ_min = 0.30")
    b.axhline(0, color="#999", lw=0.8)
    b.set_xticks(x); b.set_xticklabels([names[k] for k in ARMS], fontsize=8)
    b.set_xlabel("observation-noise arm (model)")
    b.set_ylabel("Δ = d'_bio − d'_lin (95% bootstrap CI)")
    d = o["decision_primary"]
    b.set_title(f"Δ per arm; V_FV = {d['V_fv']:.2f}, V_HS = {d['V_hs']:.2f} (FAIL if > 0.5)", fontsize=9)
    fig.suptitle(f"P2b (model units, not stimulation settings). Primary-run rule: {d['verdict']}. "
                 f"Final: {o['verdict'].split(':')[0]} (FV arm at AUC floor twice)", fontsize=9.5)
    b.legend(fontsize=8)
    c = ax[2]
    if "tau_sweep_exploratory" in o:
        xs = np.arange(len(TAUS))
        lab = [("∞" if t == np.inf else f"{t:g}") for t in TAUS]
        for arm in ARMS:
            c.plot(xs, [o["tau_sweep_exploratory"][str(t)][arm]["Delta"] for t in TAUS], "o-", color=cols[arm], label=names[arm])
        c.axhline(DELTA_MIN, color="k", ls="--", lw=1)
        c.axhline(0, color="#999", lw=0.8)
        c.set_xticks(xs); c.set_xticklabels(lab)
        c.set_xlabel("adaptation time constant τ_ad (s, model)")
        c.set_ylabel("Δ = d'_bio − d'_lin")
        c.set_title("exploratory τ_ad sweep (no verdict)", fontsize=9)
        c.legend(fontsize=7)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    for ext in ("png", "svg"):
        fig.savefig(os.path.join(FIG, f"p2b_delta_dprime.{ext}"), dpi=150)
    plt.close(fig)
    sp = os.path.join(RES, "p2b_biomimetic_diff_sensitivity.json")
    if os.path.exists(sp):
        with open(sp) as f:
            s = json.load(f)
        fig, a = plt.subplots(figsize=(8.5, 6.5))
        rows = s["rows"]
        y = np.arange(len(rows))
        for arm, mk in zip(ARMS, ("s", "o", "^")):
            a.scatter([r[arm]["Delta"] for r in rows], y, marker=mk, color=cols[arm], label=names[arm], zorder=3)
        a.axvline(DELTA_MIN, color="k", ls="--", lw=1, label="Δ_min = 0.30")
        a.axvline(0, color="#999", lw=0.8)
        a.set_yticks(y); a.set_yticklabels([r["config"] for r in rows], fontsize=8); a.invert_yaxis()
        a.set_xlabel("Δ = d'_bio − d'_lin (charge-matched, τ_ad = ∞)")
        a.set_ylabel("sensitivity configuration (N = 2000 each)")
        a.set_title(f"P2b sensitivity (model units): Δ ≥ 0.30 in FV {s['n_fv_Delta_ge_0.30']}/{s['n_configs']}, "
                    f"HS {s['n_hs_Delta_ge_0.30']}/{s['n_configs']}, Weber {s['n_weber_Delta_ge_0.30']}/{s['n_configs']}", fontsize=9)
        a.legend(fontsize=8)
        fig.tight_layout()
        for ext in ("png", "svg"):
            fig.savefig(os.path.join(FIG, f"p2b_sensitivity.{ext}"), dpi=150)
        plt.close(fig)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "test"
    os.makedirs(RES, exist_ok=True)
    os.makedirs(FIG, exist_ok=True)
    if mode == "test":
        r = self_test()
        print("SELF-TEST", r, "ALL PASS" if all(r.values()) else "FAILURES")
        with open(os.path.join(RES, "p2b_selftest.json"), "w") as f:
            json.dump(r, f, indent=1)
        sys.exit(0 if all(r.values()) else 1)
    if mode == "main":
        o = run_main()
        print(json.dumps(to_json({k: o.get(k) for k in ("R0", "decision_primary", "verdict", "abandonment_check_fv",
                                                         "controls", "runtime_s")}), indent=1))
    if mode == "sens":
        run_sens()
    if mode in ("fig", "main", "sens"):
        figures()
