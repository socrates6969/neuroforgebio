r"""M1b §7 power check on synthetic + OLD M1 data (run BEFORE any fresh download).

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. Computational decoding of recorded activity only.
  power_m1b.py --stage checks     P1-P6 -> results\POWER_M1b_checks.json
  run_m1b.py --dry                P7 dry run of the real pipeline (old files stand in for fresh ones)
  power_m1b.py --stage finalize   P7 projection + A4 decision + gate -> results\POWER_M1b.json
Specs: code\DEVIATIONS_M1b.md B.17-B.20.
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"

import argparse  # noqa: E402
import csv  # noqa: E402
import glob  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import m1b  # noqa: E402
from m1b import (K_NL1, K_PLANT, K_SHUF, LINK, MEDIUM, OLD_LARGE, OLD_LINK0, OLD_LINK1, OLD_SMALL, POWER_LOCK,  # noqa: E402
                 POWER_LOCK_SHA, PREREG, PREREG_SHA, RES, RUO, link_rel, raw_path)
from m1b import core as CO  # noqa: E402
from m1b import d3 as D3  # noqa: E402
from m1b import pipeline as PL  # noqa: E402
from m1b import synth as SY  # noqa: E402
from m1lib import data as D  # noqa: E402
from m1lib import metrics as MET  # noqa: E402
from m1lib import synthetic as M1SYN  # noqa: E402
from m1lib.decoders import reg_cov  # noqa: E402
from m1lib.guards import assert_file_hash, assert_input_lock, chrono_split, sha256_file  # noqa: E402
from nfharness.config import rng  # noqa: E402
from nfharness.provenance import card_hash, dumps, peak_rss_mb  # noqa: E402

J0, W, H = PL.J0, PL.W1, PL.H1
T0 = time.time()
LOG = []


def log(msg):
    line = "%s +%7.1fs %s" % (time.strftime("%Y-%m-%dT%H:%M:%S"), time.time() - T0, msg)
    print(line, flush=True)
    LOG.append(line)


def fresh_absent():
    paths = [raw_path(MEDIUM["rel"])] + [raw_path(link_rel(r[3])) for r in LINK]
    present = [p for p in paths if os.path.exists(p)]
    if present:
        raise SystemExit("fresh file(s) on disk during the power check: %s" % present)
    return True


def manifest():
    with open(m1b.MANIFEST, newline="") as f:
        return {r["path"]: r for r in csv.DictReader(f)}


# =====================================================================================================================
def load_d1_real(rel):
    path = raw_path(rel)
    t = CO.d1_trial_table(path)
    src = D.D1Source(path)
    C = src.counts(t["onset"], 20)
    V = src.velocity(t["onset"], 20)
    return dict(C=C, V=V, cond=t["cond"], id=t["id"], start=t["start"], stop=t["stop"], n_units=src.n_units)


def prep_d1(ds):
    ids = np.asarray(ds["id"])
    p = chrono_split(list(ids.tolist()), ds["start"], ds["stop"])
    ix = {int(i): k for k, i in enumerate(ids)}
    iTR, iVA, iTE = (np.array([ix[i] for i in p[k]]) for k in ("train", "val", "test"))
    _, Z = PL.d1_zscore(ds["C"], ids, iTR)
    Vw = ds["V"][:, J0:J0 + W]
    return dict(Z=Z, Vw=Vw, iTR=iTR, iVA=iVA, iTE=iTE, cond_tr=[ds["cond"][i] for i in iTR],
                cond_va=[ds["cond"][i] for i in iVA], B0=Vw[iTR].mean(0), n=len(ids))


def score_d1(P, yh, key):
    y = P["Vw"][P["iTE"]].reshape(-1, 2)
    units = [(k * W, (k + 1) * W) for k in range(len(P["iTE"]))]
    return PL.cont_score(y, np.asarray(yh).reshape(-1, 2), units, 20, W, key)[0]


def honest_d1(P, which, dsk):
    pr, hs, inf = PL.fit_d1(P["Z"], P["Vw"][P["iTR"]], P["Vw"][P["iVA"]], P["iTR"], P["iVA"], P["iTE"], which,
                            m1b.GRU_SEED1)
    sc = {k: score_d1(P, pr[k], (90, dsk, i)) for i, k in enumerate(pr)}
    sc["B0"] = score_d1(P, np.repeat(P["B0"][None], len(P["iTE"]), axis=0), (90, dsk, 9))
    return pr, sc, inf


def p1_d1(P, inf, honest_r2, dsk, n_seeds=20):
    m = inf["_ridge_model"]
    vpred = PL.predict_ridge_d1(m, P["Z"], P["iVA"])
    s2, E, r, w = CO.pl1_sigma2_and_E(P["Vw"][P["iVA"]].reshape(-1, 2), vpred.reshape(-1, 2))
    yte = P["Vw"][P["iTE"]].reshape(-1, 2)
    out = []
    for sd in range(n_seeds):
        res = PL.pl1_fit_d1(P["Z"], P["Vw"][P["iTR"]], P["Vw"][P["iVA"]], P["iTR"], P["iVA"], vpred, s2,
                            (90, dsk, sd), (90, dsk, sd))
        Xte = res["design_test"](P["Vw"][P["iTE"]], P["iTE"])
        rise = MET.r2_vw(yte, res["model"].predict(Xte)) - honest_r2
        valid = 0.5 * E >= 3 * res["s"]
        out.append(dict(seed=sd, rise=float(rise), s=res["s"], valid=bool(valid), lambda_=res["lambda_"],
                        hit=bool(valid and rise >= 0.5 * E), hit_literal=bool(rise >= 0.5 * E),
                        val_rise=float(res["val_rise"])))
    rises = np.array([o["rise"] for o in out])
    return dict(sigma2=s2, E=E, r=r, w=w, bar=0.5 * E, n_hit=int(sum(o["hit"] for o in out)),
                n_hit_literal=int(sum(o["hit_literal"] for o in out)), n_valid=int(sum(o["valid"] for o in out)),
                mean_rise=float(rises.mean()), mean_rise_over_E=float(rises.mean() / E), seeds=out)


def nc1_d1(P, honest_ridge_imse, b0_r2, dsk, mode, n_rep=20, n_gru=5):
    """mode 'clean' (constrained derangement) or 'nl1' (25 % true pairs). Returns per-decoder pass/fail counts."""
    res = {k: [] for k in ("ridge", "kf0", "kfl", "gru")}
    methods = []
    for rep in range(n_rep):
        if mode == "clean":
            pc, ic = CO.constrained_derangement(P["cond_tr"], rng(K_SHUF, 90, dsk, rep, 1))
            pv, iv = CO.constrained_derangement(P["cond_va"], rng(K_SHUF, 90, dsk, rep, 3))
        else:
            pc, _, ic = CO.nl1_permutation(P["cond_tr"], rng(K_NL1, 90, dsk, rep, 1), rng(K_SHUF, 91, dsk, rep, 1))
            pv, _, iv = CO.nl1_permutation(P["cond_va"], rng(K_NL1, 90, dsk, rep, 3), rng(K_SHUF, 91, dsk, rep, 3))
        methods.append((ic["method"], iv["method"]))
        which = ("ridge", "kf0", "kfl") + (("gru",) if rep < n_gru else ())
        Vtr = P["Vw"][P["iTR"]][pc]
        Vva = P["Vw"][P["iVA"]][pv]
        pr, _, inf = PL.fit_d1(P["Z"], Vtr, Vva, P["iTR"], P["iVA"], P["iTE"], which, m1b.GRU_SEED1)
        for i, k in enumerate(pr):
            sc = score_d1(P, pr[k], (91, dsk, rep, i, 0 if mode == "clean" else 1))
            ok_r2 = sc["r2"] <= b0_r2 + 0.03
            ok_mse = sc["bits"]["I_mse_net"] <= 0.10 * honest_ridge_imse
            res[k].append(dict(r2=sc["r2"], I_mse_net=sc["bits"]["I_mse_net"], I_coh_net=sc["bits"]["I_coh_net"],
                               pass_=bool(ok_r2 and ok_mse), kfl_LB=(inf["kfl"]["L"], inf["kfl"]["B"]) if k == "kfl" else None))
    summ = {}
    for k, v in res.items():
        a = np.array([x["I_mse_net"] for x in v])
        summ[k] = dict(n=len(v), n_pass=int(sum(x["pass_"] for x in v)), n_fail=int(sum(not x["pass_"] for x in v)),
                       r2_mean=float(np.mean([x["r2"] for x in v])), r2_max=float(np.max([x["r2"] for x in v])),
                       r2_min=float(np.min([x["r2"] for x in v])),
                       I_mse_net_mean=float(a.mean()), I_mse_net_sd=float(a.std(ddof=1)) if len(a) > 1 else 0.0,
                       I_mse_net_max=float(a.max()),
                       I_coh_net_mean=float(np.mean([x["I_coh_net"] for x in v])), reps=v)
    return dict(bar_r2=b0_r2 + 0.03, bar_Imse=0.10 * honest_ridge_imse, sampler_methods=sorted(set(map(str, methods))),
                decoders=summ)


def p4_d1(sc, P, pr, dsk):
    """Metric properties: I_mse <= I_coh (every decoder), negated ridge, B0 zero, frequency counts."""
    le = {k: bool(v["bits"]["I_mse"] <= v["bits"]["I_coh"] + 1e-9) for k, v in sc.items()}
    neg = score_d1(P, -pr["ridge"], (90, dsk, 8))
    b0 = sc["B0"]["bits"]
    return dict(imse_le_icoh=le, all_le=all(le.values()),
                neg_ridge=dict(I_mse_net=neg["bits"]["I_mse_net"], I_coh=neg["bits"]["I_coh"],
                               I_coh_honest=sc["ridge"]["bits"]["I_coh"],
                               ok=bool(neg["bits"]["I_mse_net"] < 0 and abs(neg["bits"]["I_coh"] - sc["ridge"]["bits"]["I_coh"]) < 1e-9)),
                b0=dict(I_mse_net=b0["I_mse_net"], I_coh_net=b0["I_coh_net"],
                        ok=bool(abs(b0["I_mse_net"]) < 1e-9 and abs(b0["I_coh_net"]) < 1e-9)),
                n_freqs=b0["n_freqs"], n_freqs_ok=b0["n_freqs"] == 7)


def calibrate_noise(target, dsk):
    """Bisection on log s (14 steps) for honest ridge test R^2 = target on a calibration draw (own sub-key)."""
    lo, hi = np.log(0.2), np.log(40.0)
    hist = []
    for _ in range(14):
        mid = 0.5 * (lo + hi)
        ds = SY.synth_d1((100, dsk), float(np.exp(mid)))
        P = prep_d1(ds)
        pr, _, _ = PL.fit_d1(P["Z"], P["Vw"][P["iTR"]], P["Vw"][P["iVA"]], P["iTR"], P["iVA"], P["iTE"], ("ridge",), ())
        r2 = MET.r2_vw(P["Vw"][P["iTE"]].reshape(-1, 2), pr["ridge"].reshape(-1, 2))
        hist.append((float(np.exp(mid)), float(r2)))
        if r2 > target:
            lo = mid
        else:
            hi = mid
    s = float(np.exp(0.5 * (lo + hi)))
    return s, hist


# =====================================================================================================================
def d2_old_session(loader, path, date, lag):
    t = loader.trials(path)
    pp = chrono_split(list(t["id"].tolist()), t["start"], t["stop"])
    return PL.d2_session(loader, path, date, lag, pp, vault=None)


def d2_anchor_block(S, dsk):
    """Honest anchor ridge + FA-ridge, B0, P1 (PL-1 D2), P2/P3 (NC1 ridge gated, FA-ridge descriptive), P4 (D2)."""
    out = {}
    M0 = PL.d2_fit_day(S, ("ridge",))
    y = S["beh_test"]
    units = PL.d2_units(len(y))
    pr = PL.d2_apply(M0, "ridge", S)
    sc_r = PL.cont_score(y, pr, units, 32, 64, (92, dsk, 0))[0]
    FA0 = PL.fa_anchor(S)
    fr, _ = PL.fa_ridge_fit(S, FA0)
    pfa, _ = PL.fa_ridge_apply(fr, FA0, S, True)
    sc_fa = PL.cont_score(y, pfa, units, 32, 64, (92, dsk, 1))[0]
    _, b0 = PL.d2_b0(S)
    sc_b0 = PL.cont_score(y, b0, units, 32, 64, (92, dsk, 2))[0]
    flat = np.repeat(np.nanmean(S["beh"][S["part"] == "calib"], axis=0)[None], len(y), axis=0)
    sc_flat = PL.cont_score(y, flat, units, 32, 64, (92, dsk, 3))[0]
    neg = PL.cont_score(y, -pr, units, 32, 64, (92, dsk, 4))[0]
    out["honest"] = dict(ridge_val_r2=M0["info"]["ridge"]["val_r2"], lambda_=M0["lam"],
                         ridge=_pub(sc_r), fa_ridge=_pub(sc_fa), B0_start_aligned=_pub(sc_b0), flat_mean=_pub(sc_flat))
    out["P4"] = dict(imse_le_icoh={k: bool(v["bits"]["I_mse"] <= v["bits"]["I_coh"] + 1e-9)
                                   for k, v in (("ridge", sc_r), ("fa_ridge", sc_fa), ("B0", sc_b0), ("flat", sc_flat))},
                     neg_ridge_ok=bool(neg["bits"]["I_mse_net"] < 0 and abs(neg["bits"]["I_coh"] - sc_r["bits"]["I_coh"]) < 1e-9),
                     neg_ridge_I_mse_net=neg["bits"]["I_mse_net"],
                     flat_zero_ok=bool(abs(sc_flat["bits"]["I_mse_net"]) < 1e-9 and abs(sc_flat["bits"]["I_coh_net"]) < 1e-9),
                     n_freqs=sc_r["bits"]["n_freqs"], n_freqs_ok=sc_r["bits"]["n_freqs"] == 20)
    # P1
    s2, E, r, w = CO.pl1_sigma2_and_E(S["beh"][S["part"] == "val"], M0["ridge_val_pred"])
    seeds = []
    for sd in range(20):
        res = PL.pl1_d2_fit(S, M0, s2, (92, dsk, sd), (92, dsk, sd))
        rise = MET.r2_vw(y, res["model"].predict(res["design_test"](y))) - sc_r["r2"]
        valid = 0.5 * E >= 3 * res["s"]
        seeds.append(dict(seed=sd, rise=float(rise), s=res["s"], valid=bool(valid), hit=bool(valid and rise >= 0.5 * E),
                          hit_literal=bool(rise >= 0.5 * E), lambda_=res["lambda_"]))
    out["P1"] = dict(sigma2=s2, E=E, r=r, w=w, bar=0.5 * E, n_hit=int(sum(x["hit"] for x in seeds)),
                     n_hit_literal=int(sum(x["hit_literal"] for x in seeds)), n_valid=int(sum(x["valid"] for x in seeds)),
                     mean_rise=float(np.mean([x["rise"] for x in seeds])), seeds=seeds)
    # P2 / P3
    Z0 = M0["zs"].transform(S["sbp"])
    b0r2 = sc_b0["r2"]
    for mode in ("clean", "nl1"):
        reps, meth = [], []
        for rep in range(20):
            if mode == "clean":
                pc, ic = CO.constrained_derangement(S["cond_calib"], rng(K_SHUF, 92, dsk, rep, 1))
                pv, iv = CO.constrained_derangement(S["cond_val"], rng(K_SHUF, 92, dsk, rep, 3))
            else:
                pc, _, ic = CO.nl1_permutation(S["cond_calib"], rng(K_NL1, 92, dsk, rep, 1), rng(K_SHUF, 93, dsk, rep, 1))
                pv, _, iv = CO.nl1_permutation(S["cond_val"], rng(K_NL1, 92, dsk, rep, 3), rng(K_SHUF, 93, dsk, rep, 3))
            meth.append((ic["method"], iv["method"], ic["flag"], iv["flag"]))
            tr, va = PL.d2_nc1_design(S, Z0, pc, pv)
            Mn = PL.d2_fit_day(S, ("ridge",), train=tr, val=va)
            prn = PL.d2_apply(Mn, "ridge", S)
            frn, _ = PL.fa_ridge_fit(S, FA0, train=tr, val=va)
            pfn, _ = PL.fa_ridge_apply(frn, FA0, S, True)
            e = {}
            for k, p_ in (("ridge", prn), ("fa_ridge", pfn)):
                sc = PL.cont_score(y, p_, units, 32, 64, (93, dsk, rep, 0 if k == "ridge" else 1, 0 if mode == "clean" else 1))[0]
                e[k] = dict(r2=sc["r2"], I_mse_net=sc["bits"]["I_mse_net"], I_coh_net=sc["bits"]["I_coh_net"],
                            pass_=bool(sc["r2"] <= b0r2 + 0.03 and sc["bits"]["I_mse_net"] <= 0.10 * sc_r["bits"]["I_mse_net"]))
            reps.append(e)
        summ = {}
        for k in ("ridge", "fa_ridge"):
            a = np.array([x[k]["I_mse_net"] for x in reps])
            summ[k] = dict(n=20, n_pass=int(sum(x[k]["pass_"] for x in reps)), n_fail=int(sum(not x[k]["pass_"] for x in reps)),
                           r2_mean=float(np.mean([x[k]["r2"] for x in reps])), r2_max=float(np.max([x[k]["r2"] for x in reps])),
                           I_mse_net_mean=float(a.mean()), I_mse_net_sd=float(a.std(ddof=1)), I_mse_net_max=float(a.max()),
                           I_coh_net_mean=float(np.mean([x[k]["I_coh_net"] for x in reps])))
        out["NC1_" + mode] = dict(bar_r2=b0r2 + 0.03, bar_Imse=0.10 * sc_r["bits"]["I_mse_net"],
                                  sampler_methods=sorted(set(map(str, meth))), decoders=summ, reps=reps)
    return out, M0


def _pub(sc):
    b = sc["bits"]
    return dict(r2=sc["r2"], rho2=sc["rho2"], I_coh=b["I_coh"], I_coh_net=b["I_coh_net"], I_coh_dc_net=b["I_coh_dc_net"],
                I_mse=b["I_mse"], I_mse_net=b["I_mse_net"], n_segments=b["n_segments"])


def p5_pair(loader, p0, pk, lag_k, dsk):
    S0 = d2_old_session(loader, p0, "anchor", 0)
    Sk = d2_old_session(loader, pk, "k", lag_k)
    M0 = PL.d2_fit_day(S0, ("ridge",))
    Mk = PL.d2_fit_day(Sk, ("ridge",))
    y = Sk["beh_test"]
    fixed = MET.r2_vw(y, PL.d2_apply(M0, "ridge", Sk))
    within = MET.r2_vw(y, PL.d2_apply(Mk, "ridge", Sk))
    pred, raised, _ = PL.pl2_fit(S0, M0, Sk)
    leak = MET.r2_vw(y, pred)
    loss = within - fixed
    return dict(fixed=fixed, within=within, leak=leak, loss=loss, recovered=leak - fixed, bar=0.5 * loss,
                informative=bool(loss >= 0.05), undeclared_raised=raised,
                pass_=bool(loss >= 0.05 and leak - fixed >= 0.5 * loss and raised == "SessionOrderError"))


# =====================================================================================================================
def p6_synthetic_eeg():
    base = os.path.join("synthetic_eeg")
    subj = {}
    for s in range(1, 21):
        R = {}
        for r in ("R04", "R08", "R12"):
            p = os.path.join(base, "S%03d" % s, "S%03d%s.edf" % (s, r))
            x, fs, _, ann, dur = M1SYN.d3_run(p)
            ev = D3.task_events(ann)
            xf = D3.bandpass(x, fs)
            ep, y, _ = D3.epochs(xf, fs, ev)
            R[r] = dict(X=np.log(ep.var(axis=2)), C=np.array([reg_cov(e) for e in ep]), y=y, ev=ev, n=x.shape[1], fs=fs,
                        t2=[(on, d) for on, d, t in ev if t == "T2"])
        subj[s] = R
    raised = D3.pl4_whitelist()
    honest, nc1 = [], {"LDA": [], "TS": []}
    for s, R in subj.items():
        Xr = {r: R[r]["X"] for r in ("R04", "R08")}
        Cr = {r: R[r]["C"] for r in ("R04", "R08")}
        yr = {r: R[r]["y"] for r in ("R04", "R08")}
        pr, _, _ = D3.fit_subject(Xr, Cr, yr, R["R12"]["X"], R["R12"]["C"], with_ts=False)
        honest.append(float((pr["LDA"] == R["R12"]["y"]).mean()))
        ytr = np.concatenate([yr["R04"], yr["R08"]])
        n4 = len(yr["R04"])
        for pix in range(5):
            yp = rng(m1b.K_D3PERM, 90, s, pix).permutation(ytr)
            pp, _, _ = D3.fit_subject(Xr, Cr, {"R04": yp[:n4], "R08": yp[n4:]}, R["R12"]["X"], R["R12"]["C"])
            for k in pp:
                nc1[k].append(float((pp[k] == R["R12"]["y"]).mean()))
    seeds = []
    for sd in range(20):
        accs = []
        for s, R in subj.items():
            Xp = {}
            for ri, r in enumerate(("R04", "R08", "R12")):
                ch = D3.pl4_channel(R[r]["n"], R[r]["fs"], R[r]["t2"], rng(K_PLANT, 94, sd, s, ri))
                Xp[r] = np.column_stack([R[r]["X"], D3.pl4_features(ch, R[r]["fs"], R[r]["ev"])])
            pr, _, _ = D3.lda_fit_predict({r: Xp[r] for r in ("R04", "R08")},
                                          {r: R[r]["y"] for r in ("R04", "R08")}, Xp["R12"])
            accs.append(float((pr == R["R12"]["y"]).mean()))
        seeds.append(float(np.mean(accs)))
    hon = float(np.mean(honest))
    m = {k: float(np.mean(v)) for k, v in nc1.items()}
    return dict(honest_lda_mean_acc=hon, pl4_mean_acc_by_seed=seeds, n_seeds_ge_090=int(sum(a >= 0.90 for a in seeds)),
                n_seeds_ge_honest_plus_015_descriptive=int(sum(a >= hon + 0.15 for a in seeds)),
                undeclared_raised=raised, nc1_d3_mean_acc=m, nc1_ok=all(0.40 <= v <= 0.60 for v in m.values()),
                pass_=bool(sum(a >= 0.90 for a in seeds) >= 19 and all(0.40 <= v <= 0.60 for v in m.values())
                           and raised == "FeatureWhitelistError"))


# =====================================================================================================================
def stage_checks():
    ph = sha256_file(PREREG)
    if ph != PREREG_SHA:
        raise SystemExit("prereg SHA mismatch %s" % ph)
    lock = assert_input_lock(POWER_LOCK, POWER_LOCK_SHA)
    fresh_absent()
    man = manifest()
    ins = {rel: assert_file_hash(raw_path(rel), man[rel]["expected_sha256"]) for rel in (OLD_LARGE, OLD_SMALL, OLD_LINK0, OLD_LINK1)}
    log("prereg + power lock + %d old input hashes OK; no fresh file on disk" % len(ins))
    out = dict(ruo=RUO, prereg_sha256=ph, power_lock_sha256=lock, inputs=ins, seed=m1b.SEED,
               streams=dict(bootstrap=1, nc1=2, null=3, planted=6, synthetic=7, nl1=8), P1={}, P2={}, P3={}, P4={}, P5={})
    # ---------------- synthetic D1 calibration
    cal = {}
    for lvl, tgt in (("syn040", 0.4), ("syn060", 0.6), ("syn080", 0.8)):
        s, hist = calibrate_noise(tgt, int(tgt * 100))
        cal[lvl] = dict(target=tgt, s=s, history=hist)
        log("synthetic noise for R2 %.1f: s = %.4f" % (tgt, s))
    out["synthetic_calibration"] = cal
    # ---------------- D1 datasets
    dsets = [("syn040", 1), ("syn060", 2), ("syn080", 3), ("large", 4), ("small", 5)]
    for name, dsk in dsets:
        if name.startswith("syn"):
            ds = SY.synth_d1((200, dsk), cal[name]["s"])
        else:
            ds = load_d1_real(OLD_LARGE if name == "large" else OLD_SMALL)
        P = prep_d1(ds)
        del ds
        full = name in ("syn060", "large", "small")
        which = ("ridge", "kf0", "kfl", "gru") if full else ("ridge",)
        pr, sc, inf = honest_d1(P, which, dsk)
        hr = sc["ridge"]["r2"]
        log("%s: n=%d honest ridge R2 %.3f %s" % (name, P["n"], hr, " ".join("%s %.3f" % (k, v["r2"]) for k, v in sc.items())))
        out["P1"][name] = p1_d1(P, inf, hr, dsk)
        log("  P1 E %.3f bar %.3f mean rise %.3f hits %d/20 (valid %d)" % (
            out["P1"][name]["E"], out["P1"][name]["bar"], out["P1"][name]["mean_rise"], out["P1"][name]["n_hit"],
            out["P1"][name]["n_valid"]))
        if full:
            out.setdefault("honest", {})[name] = {k: _pub(v) for k, v in sc.items()}
            out["honest"][name]["kfl_LB"] = (inf["kfl"]["L"], inf["kfl"]["B"])
            out["P4"][name] = p4_d1(sc, P, pr, dsk)
            imse = sc["ridge"]["bits"]["I_mse_net"]
            b0 = sc["B0"]["r2"]
            out["P2"][name] = nc1_d1(P, imse, b0, dsk, "clean")
            log("  P2 clean: " + " ".join("%s %d/%d" % (k, v["n_pass"], v["n"]) for k, v in out["P2"][name]["decoders"].items())
                + " methods %s" % out["P2"][name]["sampler_methods"])
            out["P3"][name] = nc1_d1(P, imse, b0, dsk, "nl1")
            log("  P3 NL-1 fails: " + " ".join("%s %d/%d" % (k, v["n_fail"], v["n"]) for k, v in out["P3"][name]["decoders"].items()))
            if name == "large":
                # M1's unconstrained shuffle (stream 2 sub 1 / 3), ridge: reproduce the coherence failure
                pi = rng(K_SHUF, 1).permutation(len(P["iTR"]))
                piv = rng(K_SHUF, 3).permutation(len(P["iVA"]))
                prm, _, _ = PL.fit_d1(P["Z"], P["Vw"][P["iTR"]][pi], P["Vw"][P["iVA"]][piv], P["iTR"], P["iVA"], P["iTE"],
                                      ("ridge",), ())
                scm = score_d1(P, prm["ridge"], (90, dsk, 20))
                out["P2"]["large_M1_unconstrained_ridge"] = dict(
                    r2=scm["r2"], I_coh_net=scm["bits"]["I_coh_net"], I_coh_dc_net=scm["bits"]["I_coh_dc_net"],
                    I_mse_net=scm["bits"]["I_mse_net"], coherence_failure_reproduced=bool(scm["bits"]["I_coh_dc_net"] > 0.15))
                log("  M1 unconstrained shuffle ridge: R2 %.3f I_coh_net(DC) %.2f I_mse_net %.2f" % (
                    scm["r2"], scm["bits"]["I_coh_dc_net"], scm["bits"]["I_mse_net"]))
        del P
    # ---------------- D2 LINK 20200127 anchor
    S = d2_old_session(PL.RealD2, raw_path(OLD_LINK0), "20200127", 0)
    blk, _ = d2_anchor_block(S, 6)
    del S
    out["D2_link20200127"] = {k: v for k, v in blk.items() if not k.startswith("NC1")}
    out["P1"]["link20200127"] = blk["P1"]
    out["P4"]["link20200127"] = blk["P4"]
    out["P2"]["link20200127"] = blk["NC1_clean"]
    out["P3"]["link20200127"] = blk["NC1_nl1"]
    log("LINK 20200127: ridge R2 %.3f; P1 E %.3f hits %d/20; P2 ridge %d/20 (FA %d/20); P3 ridge fails %d/20 (FA %d/20)" % (
        blk["honest"]["ridge"]["r2"], blk["P1"]["E"], blk["P1"]["n_hit"], blk["NC1_clean"]["decoders"]["ridge"]["n_pass"],
        blk["NC1_clean"]["decoders"]["fa_ridge"]["n_pass"], blk["NC1_nl1"]["decoders"]["ridge"]["n_fail"],
        blk["NC1_nl1"]["decoders"]["fa_ridge"]["n_fail"]))
    # ---------------- P5
    out["P5"]["link_20200127_to_20200626"] = p5_pair(PL.RealD2, raw_path(OLD_LINK0), raw_path(OLD_LINK1), 151, 7)
    sy = SY.SynthD2()
    out["P5"]["synthetic_0_to_120"] = p5_pair(sy, "synth:1:0", "synth:1:120", 120, 8)
    log("P5: " + json.dumps({k: [round(v["loss"], 3), round(v["recovered"], 3), v["pass_"]] for k, v in out["P5"].items()}))
    # ---------------- P6
    out["P6"] = p6_synthetic_eeg()
    log("P6: PL-4 >= 0.90 in %d/20 seeds; honest LDA %.3f; NC1-D3 %s; raised %s" % (
        out["P6"]["n_seeds_ge_090"], out["P6"]["honest_lda_mean_acc"], out["P6"]["nc1_d3_mean_acc"], out["P6"]["undeclared_raised"]))
    # ---------------- gates P1-P6
    g = {}
    g["P1a"] = all(v["n_hit"] >= 19 for v in out["P1"].values())
    g["P1b"] = all(abs(out["P1"][k]["mean_rise"] / out["P1"][k]["E"] - 1) <= 0.25 for k in ("syn040", "syn060", "syn080"))
    g["P2"] = all(all(d["n_pass"] >= (5 if k == "gru" else 19) for k, d in out["P2"][n]["decoders"].items()
                      if not (n == "link20200127" and k == "fa_ridge"))
                  for n in ("syn060", "large", "small", "link20200127"))
    g["P3"] = all(all(d["n_fail"] >= (5 if k == "gru" else 19) for k, d in out["P3"][n]["decoders"].items()
                      if not (n == "link20200127" and k == "fa_ridge"))
                  for n in ("syn060", "large", "small", "link20200127"))
    g["P4"] = all(v["all_le"] and v["neg_ridge"]["ok"] and v["b0"]["ok"] and v["n_freqs_ok"]
                  for k, v in out["P4"].items() if k != "link20200127") and \
        all(out["P4"]["link20200127"]["imse_le_icoh"].values()) and out["P4"]["link20200127"]["neg_ridge_ok"] and \
        out["P4"]["link20200127"]["flat_zero_ok"] and out["P4"]["link20200127"]["n_freqs_ok"]
    g["P5"] = all(v["pass_"] for v in out["P5"].values())
    g["P6"] = out["P6"]["pass_"]
    out["gates_P1_P6"] = g
    out["descriptive_FA_ridge_link"] = dict(P2_n_pass=out["P2"]["link20200127"]["decoders"]["fa_ridge"]["n_pass"],
                                            P3_n_fail=out["P3"]["link20200127"]["decoders"]["fa_ridge"]["n_fail"])
    out["pass_P1_P6"] = all(g.values())
    out["code_sha256"] = code_hashes()
    out["runtime"] = dict(wall_s=time.time() - T0, peak_rss_mb=peak_rss_mb())
    out["log"] = LOG
    p = os.path.join(RES, "POWER_M1b_checks.json")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(dumps(out))
    log("gates %s -> %s" % (g, "PASS" if out["pass_P1_P6"] else "FAIL"))


def code_hashes():
    files = sorted(glob.glob(os.path.join(HERE, "m1b", "*.py"))) + sorted(glob.glob(os.path.join(HERE, "m1lib", "*.py"))) + \
        [os.path.join(HERE, f) for f in ("power_m1b.py", "run_m1b.py")] + sorted(glob.glob(os.path.join(HERE, "tests_m1b", "*.py")))
    return {os.path.relpath(f, HERE).replace("\\", "/"): sha256_file(f) for f in files if os.path.exists(f)}


def stage_finalize():
    chk = json.load(open(os.path.join(RES, "POWER_M1b_checks.json"), encoding="utf-8"))
    dry = json.load(open(os.path.join(RES, "M1b_card_dry.json"), encoding="utf-8"))
    tm = dry["runtime"]["timing"]
    d1, d2, d3 = tm["D1_s"], tm["D2_s"], tm.get("D3_s", 0.0)
    other = dry["runtime"]["wall_s"] - d1 - d2 - d3
    proj = dict(D1_s=2.5 * d1, D2_s=d2, D3_s=d3, other_s=other)
    proj["total_s"] = sum(proj.values())
    proj["peak_rss_mb_dry"] = dry["runtime"]["peak_rss_mb"]
    # A4 rule (DEVIATIONS_M1b B.20): cut in prereg order while 1.25 * projected wall >= 1200 s or RSS >= 1536 MB
    comp = dict(dry["runtime"]["timing"].get("components", {}))
    cuts, total = [], proj["total_s"]
    order = [("A4 cut (1): D3 / H6 NOT TESTED", comp.get("D3", d3)),
             ("A4 cut (2): D2 GRU and KF descriptive drift curves and their NC1", comp.get("D2_gru_kf", 0.0)),
             ("A4 cut (3): NC2b and the bin sweep", 2.5 * comp.get("D1_nc2b_binsweep", 0.0)),
             ("A4 cut (4): honest GRU ensemble 3 -> 1 seed", 2.5 * comp.get("D1_gru_ens_extra", 0.0))]
    rss_ok = (proj["peak_rss_mb_dry"] or 0) < 1536
    for name, saves in order:
        if 1.25 * total < 1200 and rss_ok:
            break
        cuts.append(name)
        total -= saves
    a4 = dict(rule="cut in prereg order while 1.25 x projected wall >= 1200 s or projected peak RSS >= 1536 MB",
              projection=proj, component_s=comp, cuts=cuts, projected_after_cuts_s=total,
              gru_arm_not_tested=bool(1.25 * total >= 1200))
    p7 = dict(dry_card_sha256=dry.get("card_sha256_excl_runtime"), dry_wall_s=dry["runtime"]["wall_s"],
              dry_peak_rss_mb=dry["runtime"]["peak_rss_mb"], A4=a4,
              pass_=bool(rss_ok and dry.get("stopped") is None))
    res = dict(ruo=RUO, prereg_sha256=chk["prereg_sha256"], power_lock_sha256=chk["power_lock_sha256"], inputs=chk["inputs"],
               gates=dict(chk["gates_P1_P6"], P7=p7["pass_"]), P7=p7, checks_file_sha256=sha256_file(os.path.join(RES, "POWER_M1b_checks.json")),
               summary=summarise(chk), code_sha256=chk["code_sha256"])
    res["verdict"] = "PASS" if all(res["gates"].values()) else "FAIL"
    res["card_sha256"] = card_hash(res)
    with open(m1b.POWER_JSON, "w", encoding="utf-8", newline="\n") as f:
        f.write(dumps(res))
    print("POWER_M1b.json verdict %s sha %s" % (res["verdict"], sha256_file(m1b.POWER_JSON)))
    print(json.dumps(a4, indent=1))


def summarise(chk):
    s = {}
    for k, v in chk["P1"].items():
        s["P1_" + k] = "E %.3f bar %.3f mean rise %.3f hits %d/20 valid %d" % (v["E"], v["bar"], v["mean_rise"], v["n_hit"], v["n_valid"])
    for p in ("P2", "P3"):
        for k, v in chk[p].items():
            if "decoders" in v:
                s[p + "_" + k] = {d: "%d pass / %d; R2 mean %.3f max %.3f (bar %.3f); I_mse_net mean %.2f sd %.2f max %.2f (bar %.2f)" % (
                    x["n_pass"], x["n"], x["r2_mean"], x["r2_max"], v["bar_r2"], x["I_mse_net_mean"], x["I_mse_net_sd"],
                    x["I_mse_net_max"], v["bar_Imse"]) for d, x in v["decoders"].items()}
    return s


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["checks", "finalize"], required=True)
    a = ap.parse_args()
    stage_checks() if a.stage == "checks" else stage_finalize()
