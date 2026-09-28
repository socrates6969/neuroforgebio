"""P1b: latency budget for artificial slip feedback, friction-model repair (prereg\\P1b_grip_latency_budget_v2.md).

Simulation only. numpy (+ matplotlib for figures). Seed 20260926. Reuses code\\p1_grip_latency.py (read-only import).
Changes vs P1 (prereg C1-C4): per-trial memory friction prior mu_hat(0) = mu*exp(eps), eps ~ U(-hw, +hw), hw = ln 1.10;
two-sided ("replace") slip update; zero-perturbation hard gate G_Z first; reference config = cycle-1 friction model.
Usage:  python p1b_grip_latency_v2.py test | main | sens | fig
Interpretations: code\\DEVIATIONS.md (section P1b).
"""
import json
import os
import sys
import time
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p1_grip_latency as p1  # noqa: E402

from p1_grip_latency import (DT, NSTEP, SM_GRID, NS, NDET, DELTAS, PS, SEED, RES, FIG,  # noqa: E402
                             slip_update, cond_list_main, resolve, fstar, delta_star, fmt_delta, pct_ci,
                             boot_weights, boot_fstar, R_of, shuffled_preload, to_json)

HW10 = float(np.log(1.10))
DEFAULT = dict(p1.DEFAULT, prior="memory", mem_hw=HW10, update="replace")
REFERENCE = dict(p1.DEFAULT, prior="fixed", mem_hw=HW10, update="min")  # cycle-1 friction model


def make_trials(N, P, seed=SEED):
    """Cycle-1 trial generator (bit-identical draws) plus one extra uniform per trial for the memory prior, drawn from a
    separate stream so that all cycle-1 random numbers are unchanged (CRN with cycle 1 and across half-widths)."""
    tr = p1.make_trials(N, P, seed=seed)
    u = np.random.default_rng(seed + 1000).uniform(-1.0, 1.0, N)
    tr["u_mem"] = u
    tr["eps"] = u * P["mem_hw"]
    return tr


def simulate(tr, P, conds, record_name=None, preload=None, debug=False):
    """Copy of p1.simulate with (i) per-lane initial mu_hat (memory prior) and (ii) replace/min slip update.
    Returns fail codes [C,N,S] (0 ok, 1 drop, 2 crush)."""
    N = tr["N"]
    C = len(conds)
    nl = C * N * NS
    lane = np.arange(nl)
    ci = lane // (N * NS)
    ti = (lane // NS) % N
    si = lane % NS
    kind = np.array([c["kind"] for c in conds])
    is_fb = (kind == "FB")[ci]
    is_vis = (kind == "VIS")[ci]
    is_visev = (kind == "VISEV")[ci]
    pl = np.array([c["p"] for c in conds], dtype=float)[ci]
    taul = np.array([int(round(c["tau"] / DT)) for c in conds], dtype=np.int64)[ci]
    rec_c = [i for i, c in enumerate(conds) if c["name"] == record_name]
    rec_c = rec_c[0] if rec_c else -1
    replace = P["update"] == "replace"
    if P["prior"] == "memory":
        muh0 = tr["mu"][ti] * np.exp(tr["eps"][ti])
    else:
        muh0 = np.full(nl, P["mu_prior"])

    st = dict(idx=lane, ti=ti, sm=SM_GRID[si], m=tr["m"][ti], mu=tr["mu"][ti], mg=tr["mg"][ti], gc=tr["Gcrush"][ti],
              fb=is_fb, vis=is_vis, visev=is_visev, p=pl, tau=taul,
              G=np.zeros(nl), v=np.zeros(nl), s=np.zeros(nl), muh=muh0.astype(float), Lfb=np.zeros(nl),
              last=np.full(nl, -10**9, dtype=np.int64), noS=np.full(nl, 10**6, dtype=np.int64),
              evc=np.zeros(nl, dtype=np.int64), crossed=np.zeros(nl, bool), pany=np.zeros(nl, bool),
              pmu=np.full(nl, np.inf), pL=np.zeros(nl), sref=np.zeros(nl), ndel=np.zeros(nl, dtype=np.int64))
    if debug:
        st["first_ev"] = np.full(nl, -1, dtype=np.int64)
        st["first_del"] = np.full(nl, -1, dtype=np.int64)
    fail = np.zeros(nl, dtype=np.int8)
    fstep = np.full(nl, -1, dtype=np.int32)
    muh_end = np.full(nl, np.nan)
    ndel_end = np.zeros(nl, dtype=np.int64)
    pos = np.arange(nl)
    sched = defaultdict(list)
    if preload is not None:
        for step, ln, muc, Lc in preload:
            sched[int(step)].append((ln, muc, Lc))
    records = []
    decay = np.exp(-DT / 0.3)
    hold_steps = int(round(0.5 / DT))
    ev_gap = int(round(0.020 / DT))
    L_all, xi_all = tr["L"], tr["xi"]
    first_dbg = {}

    def push(step_arr, ln, muc, Lc):
        for sv in np.unique(step_arr):
            if sv >= NSTEP:
                continue
            k = step_arr == sv
            sched[int(sv)].append((ln[k], muc[k], Lc[k]))

    for n in range(NSTEP):
        t = n * DT
        a = st
        # (a) deliveries
        if n in sched:
            for ln, muc, Lc in sched.pop(n):
                p = pos[ln]
                ok = p >= 0
                if not ok.any():
                    continue
                p, muc, Lc = p[ok], muc[ok], Lc[ok]
                if replace:
                    a["muh"][p] = muc          # C2: two-sided update (measurement replaces the estimate)
                else:
                    np.minimum.at(a["muh"], p, muc)
                np.maximum.at(a["Lfb"], p, Lc)
                a["last"][p] = n
                a["ndel"][p] += 1
                if debug:
                    fd = a["first_del"]
                    fd[p] = np.where(fd[p] < 0, n, fd[p])
        # (b) reactive hold / decay
        dec = (n - a["last"]) > hold_steps
        a["Lfb"] = np.where(dec, a["Lfb"] * decay, a["Lfb"])
        # (c) grip command and dynamics
        ramp_lead = min(max((t + 0.2 - 0.5) / 0.3, 0.0), 1.0)
        Gcmd = (1 + a["sm"]) * np.maximum(a["mg"] * ramp_lead, a["Lfb"]) / (2 * a["muh"])
        a["G"] = a["G"] + DT * (Gcmd - a["G"]) / P["tau_m"]
        Geff = a["G"] * (1 + P["noise"] * xi_all[n][a["ti"]])
        L = L_all[n][a["ti"]]
        # (d) slip physics
        S = L > 2 * a["mu"] * Geff
        s_prev = a["s"]
        a["v"], a["s"] = slip_update(S, L, Geff, a["mu"], a["m"], a["v"], a["s"])
        # (e) failure
        drop = a["s"] > P["drop"]
        crush = Geff > a["gc"]
        # (f) events and feedback
        event = S & (a["noS"] >= ev_gap)
        a["noS"] = np.where(S, 0, a["noS"] + 1)
        if event.any():
            e = np.nonzero(event)[0]
            evi = np.minimum(a["evc"][e], NDET - 1)
            a["evc"][e] += 1
            if debug:
                fe = a["first_ev"]
                fe[e] = np.where(fe[e] < 0, n, fe[e])
            det = tr["udet"][a["ti"][e], evi] < a["p"][e]
            e, evi = e[det], evi[det]
            if e.size:
                muc = 0.9 * L[e] / (2 * np.maximum(Geff[e], 1e-12))
                if P["predictive"]:
                    fut = np.minimum(n + a["tau"][e], NSTEP - 1)
                    Lc = L_all[fut, a["ti"][e]]
                else:
                    Lc = L[e]
                fbm = a["fb"][e]
                if fbm.any():
                    push(n + a["tau"][e][fbm], a["idx"][e][fbm], muc[fbm], Lc[fbm])
                    if rec_c >= 0:
                        lanes = a["idx"][e][fbm]
                        r = (lanes // (N * NS)) == rec_c
                        if r.any():
                            records.append((lanes[r], evi[fbm][r], muc[fbm][r], Lc[fbm][r]))
                vm = a["vis"][e] | a["visev"][e]
                if vm.any():
                    ev_, muc_, Lc_ = e[vm], muc[vm], Lc[vm]
                    now = a["vis"][ev_] & a["crossed"][ev_]
                    if now.any():
                        push(n + a["tau"][ev_[now]], a["idx"][ev_[now]], muc_[now], Lc_[now])
                    pe, pm, pL_ = ev_[~now], muc_[~now], Lc_[~now]
                    newp = ~a["pany"][pe]
                    a["sref"][pe[newp]] = s_prev[pe[newp]]
                    # pooled (not yet visible) events: replace -> most recent measurement; min -> cycle-1 pooling
                    a["pmu"][pe] = pm if replace else np.minimum(a["pmu"][pe], pm)
                    a["pL"][pe] = np.maximum(a["pL"][pe], pL_)
                    a["pany"][pe] = True
        vis_any = a["vis"] | a["visev"]
        if vis_any.any():
            cross_cum = a["vis"] & ~a["crossed"] & (a["s"] > P["s_vis"])
            cross_ev = a["visev"] & a["pany"] & ((a["s"] - a["sref"]) > P["s_vis"])
            a["crossed"] = a["crossed"] | cross_cum
            fire = (cross_cum | cross_ev) & a["pany"]
            if fire.any():
                f = np.nonzero(fire)[0]
                push(n + a["tau"][f], a["idx"][f], a["pmu"][f], a["pL"][f])
                a["pany"][f] = False
                a["pmu"][f] = np.inf
                a["pL"][f] = 0.0
        ft = np.where(drop, 1, np.where(crush, 2, 0)).astype(np.int8)
        done = ft > 0
        if done.any():
            fail[a["idx"][done]] = ft[done]
            fstep[a["idx"][done]] = n
            muh_end[a["idx"][done]] = a["muh"][done]
            ndel_end[a["idx"][done]] = a["ndel"][done]
            keep = ~done
            pos[a["idx"][done]] = -1
            if debug:
                for k in ("first_ev", "first_del"):
                    first_dbg.setdefault(k, {}).update(dict(zip(a["idx"][done].tolist(), a[k][done].tolist())))
            st = {k: vv[keep] for k, vv in a.items()}
            pos[st["idx"]] = np.arange(st["idx"].size)
        if st["idx"].size == 0:
            break
    muh_end[st["idx"]] = st["muh"]
    ndel_end[st["idx"]] = st["ndel"]
    out = dict(fail=fail.reshape(C, N, NS), fstep=fstep.reshape(C, N, NS), records=records,
               muh_end=muh_end.reshape(C, N, NS), ndel=ndel_end.reshape(C, N, NS))
    if debug:
        fe = np.full(nl, -1, dtype=np.int64)
        fd = np.full(nl, -1, dtype=np.int64)
        fe[st["idx"]] = st["first_ev"]
        fd[st["idx"]] = st["first_del"]
        for k, arr in (("first_ev", fe), ("first_del", fd)):
            for ln, val in first_dbg.get(k, {}).items():
                arr[ln] = val
        out["first_ev"] = fe.reshape(C, N, NS)
        out["first_del"] = fd.reshape(C, N, NS)
    return out


def run_conditions(tr, P, conds, batch=8, record_name=None):
    res, recs = {}, []
    for b in range(0, len(conds), batch):
        cb = conds[b:b + batch]
        o = simulate(tr, P, cb, record_name=record_name)
        for i, c in enumerate(cb):
            res[c["name"]] = o["fail"][i]
        recs += o["records"]
    return res, recs


NAT_NOFB = [dict(name="NAT", kind="FB", tau=None, p=None), dict(name="NOFB", kind="NOFB", tau=0, p=0.0)]


def gate_Z(P, N, B=1000, boot_seed=SEED + 2):
    """G_Z: K = 0, NAT and NOFB, F* <= 0.01 (point estimates) with 95% bootstrap CI."""
    Pz = dict(P, K_zero=True)
    trz = make_trials(N, Pz)
    rz, _ = run_conditions(trz, Pz, resolve(NAT_NOFB, Pz))
    out = {k: fstar(v) for k, v in rz.items()}
    if B:
        W = boot_weights(N, B, boot_seed)
        for k, v in rz.items():
            bf = boot_fstar(W, v)
            out[k]["CI95"] = [float(np.percentile(bf, 2.5)), float(np.percentile(bf, 97.5))]
    return dict(F=out, passed=bool(all(v["F"] <= 0.01 for v in out.values())))


# ----------------------------------------------------------------------------------------------
def self_test():
    ok = {}
    # 0. cycle-1 unit tests still pass on the imported helpers
    r1 = p1.self_test()
    ok["cycle1_helper_selftests(10)"] = bool(all(r1.values()))
    # 1. cycle-1 friction model (fixed prior 0.75, min update) is bit-identical to p1.simulate
    P = dict(REFERENCE)
    tr = make_trials(150, P, seed=7)
    conds = resolve([dict(name="NAT", kind="FB", tau=None, p=None), dict(name="NOFB", kind="NOFB", tau=0, p=0.0),
                     dict(name="VIS200", kind="VIS", tau=0.2, p=1.0), dict(name="A", kind="FB", tau=0.124, p=0.75)], P)
    a1 = p1.simulate(tr, P, conds)["fail"]
    a2 = simulate(tr, P, conds)["fail"]
    ok["reference_config_bit_identical_to_cycle1"] = bool(np.array_equal(a1, a2))
    # 2. cycle-1 random numbers unchanged by the extra memory draw
    t1 = p1.make_trials(50, dict(p1.DEFAULT), seed=3)
    t2 = make_trials(50, dict(DEFAULT), seed=3)
    ok["trial_draws_unchanged"] = bool(np.array_equal(t1["L"], t2["L"]) and np.array_equal(t1["xi"], t2["xi"]) and
                                       np.array_equal(t1["mu"], t2["mu"]))
    # 3. memory prior range: mu_hat(0)/mu in [1/1.10, 1.10], roughly uniform in log
    tr = make_trials(20000, dict(DEFAULT), seed=4)
    rr = np.exp(tr["eps"])
    ok["memory_prior_range"] = bool(rr.min() >= 1 / 1.10 - 1e-12 and rr.max() <= 1.10 + 1e-12 and
                                    abs(np.mean(tr["eps"])) < 0.002 and abs(np.std(tr["eps"]) - HW10 / np.sqrt(3)) < 0.002)
    # 4. analytic G_Z case: no noise, K = 0, memory prior: SM = 0.2 cannot slip (1.2/1.1 > 1) nor crush (1.2*1.1 < 1.6)
    Pn = dict(DEFAULT, K_zero=True, noise=0.0)
    tr = make_trials(300, Pn, seed=9)
    o = simulate(tr, Pn, resolve(NAT_NOFB, Pn))
    j = int(np.where(SM_GRID == 0.2)[0][0])
    ok["noise_free_K0_SM0.2_zero_failures"] = bool((o["fail"][:, :, j] == 0).all())
    # and at SM = 0, open loop (NOFB): steady grip mg/(2 mu_hat) is below the slip limit mg/(2 mu) iff mu_hat > mu (eps > 0).
    # Expect: every trial with eps > 0.01 drops, no trial with eps < 0 fails.
    f0 = o["fail"][1, :, 0] > 0
    ok["noise_free_K0_SM0_fails_iff_overestimate"] = bool(np.all(f0[tr["eps"] > 0.01]) and not np.any(f0[tr["eps"] < 0]))
    # 5. two-sided update can RAISE mu_hat: start with mu_hat = 0.5 mu (under-estimate -> over-grip, no slip) is not a
    # test of raising; use over-estimate mu_hat = 1.5 mu (under-grip -> slip), p = 1 NAT; after the slip mu_hat should be
    # ~0.9 mu (i.e. lowered but NOT by min: equal to the measurement), then force an upward case with a fixed low prior.
    Pr = dict(DEFAULT, K_zero=True, noise=0.0, prior="fixed", mu_prior=0.2, update="replace", drop=1.0, c_lo=100, c_hi=101)
    tr = make_trials(40, Pr, seed=11)
    tr["mu"][:] = 0.6
    tr["Gcrush"] = tr["c"] * tr["mg"] / (2 * tr["mu"])
    o = simulate(tr, Pr, resolve([dict(name="NAT", kind="FB", tau=None, p=None)], Pr))
    # prior 0.2 < mu 0.6 -> over-grip, no slip, mu_hat stays 0.2 (nothing to measure): sanity of "no event, no update"
    ok["no_slip_no_update"] = bool(np.allclose(o["muh_end"][0], 0.2) and (o["ndel"][0] == 0).all())
    Pr2 = dict(Pr, mu_prior=1.5)
    o2 = simulate(tr, Pr2, resolve([dict(name="NAT", kind="FB", tau=None, p=1.0)], dict(Pr2, p_nat=1.0)))
    m0 = o2["ndel"][0][:, 0] >= 1
    ok["replace_sets_mu_hat_to_0.9mu"] = bool(m0.sum() > 20 and np.all(np.abs(o2["muh_end"][0][m0, 0] / 0.6 - 0.9) < 0.02))
    # min update would give the same here (lowering); the RAISING case: ART lane with measurement above current mu_hat.
    # Construct: replace vs min on the reference trials with noise: count lanes where final mu_hat > initial.
    Pm = dict(DEFAULT)
    tr = make_trials(200, Pm, seed=13)
    o3 = simulate(tr, Pm, resolve([dict(name="NAT", kind="FB", tau=None, p=None)], Pm))
    muh0 = (tr["mu"] * np.exp(tr["eps"]))[:, None]
    raised = (o3["muh_end"][0] > muh0 * 1.0001) & (o3["ndel"][0] > 0)
    o4 = simulate(tr, dict(Pm, update="min"), resolve([dict(name="NAT", kind="FB", tau=None, p=None)], Pm))
    raised_min = (o4["muh_end"][0] > muh0 * 1.0001)
    ok["replace_can_raise_min_cannot"] = bool(raised.sum() > 0 and raised_min.sum() == 0)
    # 6. CRN: ART p = 0 identical to NOFB under the new model
    o = simulate(tr, Pm, [dict(name="NOFB", kind="NOFB", tau=0, p=0.0), dict(name="A0", kind="FB", tau=0.1, p=0.0)])
    ok["crn_p0_equals_nofb"] = bool(np.array_equal(o["fail"][0], o["fail"][1]))
    # 7. delivery delay exact
    o = simulate(tr, Pm, [dict(name="A", kind="FB", tau=0.074, p=1.0)], debug=True)
    fe, fd = o["first_ev"][0], o["first_del"][0]
    mm = (fe >= 0) & (fd >= 0)
    ok["delay_exact_tau"] = bool(mm.sum() > 50 and np.all(fd[mm] - fe[mm] == 37))
    return ok


# ----------------------------------------------------------------------------------------------
def num(x):
    return np.inf if x == "> 300" else (-np.inf if x == "< -20" else float(x))


def h3_verdict(dstar, ci):
    lo, hi = num(ci[0]), num(ci[1])
    if 50 <= lo and hi <= 150 and np.isfinite(dstar) and 50 <= dstar <= 150:
        return "PASS"
    if lo <= 50 <= hi or lo <= 150 <= hi:
        return "INCONCLUSIVE"
    return "FAIL"


def full_analysis(res, N, B=1000):
    out = {}
    out["Fstar"] = {k: fstar(v) for k, v in res.items()}
    F = {k: v["F"] for k, v in out["Fstar"].items()}
    Rc = {str(p): [float(R_of(F["NOFB"], F["NAT"], F[f"ART_d{d}_p{p}"])) for d in DELTAS] for p in PS}
    out["R_curves"] = dict(deltas=DELTAS, **Rc)
    dstar = delta_star(Rc["0.95"])
    out["delta_star"] = fmt_delta(dstar)
    out["delta_star_p"] = {str(p): fmt_delta(delta_star(Rc[str(p)])) for p in PS}
    G0 = (F["NAT"] <= 0.5 * F["NOFB"]) and (F["NAT"] >= 0.005)
    out["G0"] = dict(holds=bool(G0), F_NAT=F["NAT"], F_NOFB=F["NOFB"], ratio=F["NAT"] / F["NOFB"] if F["NOFB"] > 0 else None)
    if "SHUF" in F:
        out["R_shuffled"] = float(R_of(F["NOFB"], F["NAT"], F["SHUF"]))
        out["shuffled_control_pass"] = bool(out["R_shuffled"] < 0.5)
    out["R_VIS"] = {k: float(R_of(F["NOFB"], F["NAT"], F[k])) for k in ("VIS150", "VIS200", "VIS250", "VISEV200") if k in F}
    W = boot_weights(N, B, SEED + 1)
    bF = {k: boot_fstar(W, v) for k, v in res.items()}
    out["Fstar_CI95"] = {k: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for k, v in bF.items()}
    Rb = np.stack([R_of(bF["NOFB"], bF["NAT"], bF[f"ART_d{d}_p0.95"]) for d in DELTAS], axis=1)
    out["R_CI95_p0.95"] = [[float(np.nanpercentile(Rb[:, j], 2.5)), float(np.nanpercentile(Rb[:, j], 97.5))]
                           for j in range(len(DELTAS))]
    ds = np.array([delta_star(Rb[b]) for b in range(200)])
    out["delta_star_boot"] = dict(n=200, CI95=pct_ci(ds), n_undefined=int(np.isnan(ds).sum()),
                                  n_gt300=int((ds == np.inf).sum()), n_lt_m20=int((ds == -np.inf).sum()),
                                  median=fmt_delta(np.nanmedian(ds)) if np.any(~np.isnan(ds)) else None)
    out["G0_boot_frac_holds"] = float(np.mean((bF["NAT"] <= 0.5 * bF["NOFB"]) & (bF["NAT"] >= 0.005)))
    if "VIS200" in F:
        ratio_b = bF["ART_d100_p0.95"] / np.where(bF["VIS200"] > 0, bF["VIS200"], np.nan)
        ratio = F["ART_d100_p0.95"] / F["VIS200"] if F["VIS200"] > 0 else np.nan
        out["H3b"] = dict(F_ART100=F["ART_d100_p0.95"], F_VIS200=F["VIS200"], ratio=ratio,
                          ratio_CI95=[float(np.nanpercentile(ratio_b, 2.5)), float(np.nanpercentile(ratio_b, 97.5))],
                          verdict="PASS" if ratio <= 0.8 else "FAIL")
        out["H3b"]["CI_straddles_0.8"] = bool(out["H3b"]["ratio_CI95"][0] <= 0.8 <= out["H3b"]["ratio_CI95"][1])
    out["_dstar"] = dstar
    out["_Rb"] = Rb
    out["_ds"] = ds
    return out


def run_main(N=4000):
    t0 = time.time()
    P = dict(DEFAULT)
    out = dict(prereg="P1b_grip_latency_budget_v2.md", seed=SEED, N=N, model=dict(prior="memory", mem_hw=HW10, update="replace"))
    # --- G_Z hard gate FIRST
    gz = gate_Z(P, N)
    out["G_Z"] = gz
    print("G_Z", json.dumps(to_json(gz)), f"{time.time()-t0:.0f}s", flush=True)
    # reference config regression (cycle-1 friction model): must give F*_NOFB(K=0) = 0.498 +/- 0.03
    ref = gate_Z(REFERENCE, N)
    out["reference_cycle1_G_Z"] = ref
    out["reference_regression_pass"] = bool(abs(ref["F"]["NOFB"]["F"] - 0.498) <= 0.03)
    print("REF", json.dumps(to_json(ref)), f"{time.time()-t0:.0f}s", flush=True)
    if not gz["passed"]:
        out["H3_verdict"] = "NO VERDICT: G_Z failed (model defect); stop per prereg section 4"
        out["H3b"] = dict(verdict="NO VERDICT (G_Z failed)")
        out["runtime_s"] = round(time.time() - t0, 1)
        with open(os.path.join(RES, "p1b_grip_latency.json"), "w") as f:
            json.dump(to_json(out), f, indent=1)
        return out
    # --- main conditions
    tr = make_trials(N, P)
    conds = resolve(cond_list_main(), P)
    res, recs = run_conditions(tr, P, conds, batch=8, record_name="ART_d0_p0.95")
    pre = shuffled_preload(tr, recs)
    o = simulate(tr, P, [dict(name="SHUF", kind="SHUF", tau=0, p=0.0)], preload=pre)
    res["SHUF"] = o["fail"][0]
    print("main conditions done", f"{time.time()-t0:.0f}s", flush=True)
    A = full_analysis(res, N)
    dstar, Rb, ds = A.pop("_dstar"), A.pop("_Rb"), A.pop("_ds")
    out.update(A)
    G0 = A["G0"]["holds"]
    if G0:
        out["H3_verdict"] = h3_verdict(dstar, A["delta_star_boot"]["CI95"])
    else:
        out["H3_verdict"] = "G0 FAILED (see redesign)"
        Pr = dict(P, amp_lo=0.4, amp_hi=1.0, c_lo=1.3, c_hi=2.0)
        gzr = gate_Z(Pr, N)
        trr = make_trials(N, Pr)
        names = ["NAT", "NOFB", "VIS200"] + [f"ART_d{d}_p0.95" for d in DELTAS]
        rr, _ = run_conditions(trr, Pr, resolve([c for c in cond_list_main() if c["name"] in names], Pr))
        Fr = {k: fstar(v)["F"] for k, v in rr.items()}
        G0r = (Fr["NAT"] <= 0.5 * Fr["NOFB"]) and (Fr["NAT"] >= 0.005)
        Rr = [float(R_of(Fr["NOFB"], Fr["NAT"], Fr[f"ART_d{d}_p0.95"])) for d in DELTAS]
        W = boot_weights(N, 1000, SEED + 1)
        bFr = {k: boot_fstar(W, v) for k, v in rr.items()}
        out["redesign"] = dict(G_Z=gzr, Fstar={k: fstar(v) for k, v in rr.items()},
                               Fstar_CI95={k: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for k, v in bFr.items()},
                               G0=bool(G0r), G0_ratio=Fr["NAT"] / Fr["NOFB"] if Fr["NOFB"] > 0 else None,
                               R=Rr, delta_star=fmt_delta(delta_star(Rr)))
        if (not G0r) or (not gzr["passed"]):
            why = []
            if not G0r:
                why.append("redesign G0 fails")
            if not gzr["passed"]:
                why.append("redesign G_Z fails")
            out["H3_verdict"] = ("ABANDONED (" + "; ".join(why) + "): open-loop margin with a memory prior suffices, or "
                                 "feedback cannot beat it; latency question not addressable with this task")
        else:
            Rbr = np.stack([R_of(bFr["NOFB"], bFr["NAT"], bFr[f"ART_d{d}_p0.95"]) for d in DELTAS], axis=1)
            dsr = np.array([delta_star(Rbr[b]) for b in range(200)])
            cir = pct_ci(dsr)
            out["redesign"]["delta_star_CI95"] = cir
            out["H3_verdict"] = h3_verdict(delta_star(Rr), cir) + " (redesign)"
    out["runtime_s"] = round(time.time() - t0, 1)
    with open(os.path.join(RES, "p1b_grip_latency.json"), "w") as f:
        json.dump(to_json(out), f, indent=1)
    np.savez_compressed(os.path.join(RES, "p1b_boot_R.npz"), Rb=Rb, ds=ds)
    return out


SENS = [("tau_m=20ms", dict(tau_m=0.020)), ("tau_m=80ms", dict(tau_m=0.080)),
        ("drop=5mm", dict(drop=0.005)), ("drop=20mm", dict(drop=0.020)),
        ("amp U(0.1,0.4)", dict(amp_lo=0.1, amp_hi=0.4)), ("amp U(0.4,1.0)", dict(amp_lo=0.4, amp_hi=1.0)),
        ("Poisson 1", dict(pois=1.0)), ("Poisson 4", dict(pois=4.0)),
        ("c U(1.3,2.0)", dict(c_lo=1.3, c_hi=2.0)), ("c U(2.0,4.0)", dict(c_lo=2.0, c_hi=4.0)),
        ("noise 0", dict(noise=0.0)), ("noise 0.1", dict(noise=0.1)),
        ("NAT tau 50ms", dict(nat_tau=0.050)), ("NAT tau 100ms", dict(nat_tau=0.100)),
        ("memory +/-5%", dict(mem_hw=float(np.log(1.05)))), ("memory +/-15%", dict(mem_hw=float(np.log(1.15)))),
        ("p_det_NAT 0.8", dict(p_nat=0.8)), ("p_det_NAT 1.0", dict(p_nat=1.0)),
        ("predictive (Smith)", dict(predictive=True))]


def run_sens(N=1000):
    t0 = time.time()
    rows = []
    names = ["NAT", "NOFB"] + [f"ART_d{d}_p0.95" for d in DELTAS]
    cfgs = [("baseline (N=1000)", DEFAULT, {})] + [(l, DEFAULT, c) for l, c in SENS] + \
           [("REFERENCE cycle-1 friction model (not counted)", REFERENCE, {})]
    for label, base, ch in cfgs:
        P = dict(base, **ch)
        tr = make_trials(N, P)
        conds = resolve([c for c in cond_list_main() if c["name"] in names], P)
        res, _ = run_conditions(tr, P, conds, batch=11)
        Fn, Fa = fstar(res["NOFB"])["F"], fstar(res["NAT"])["F"]
        R = [float(R_of(Fn, Fa, fstar(res[f"ART_d{d}_p0.95"])["F"])) for d in DELTAS]
        ds = delta_star(R)
        G0 = (Fa <= 0.5 * Fn) and (Fa >= 0.005)
        gz = gate_Z(P, N, B=0)
        rows.append(dict(config=label, F_NOFB=Fn, F_NAT=Fa, G0=bool(G0), G0_ratio=Fa / Fn if Fn > 0 else None,
                         G_Z=dict(F_NOFB=gz["F"]["NOFB"]["F"], F_NAT=gz["F"]["NAT"]["F"], passed=gz["passed"]),
                         R=R, delta_star=fmt_delta(ds),
                         in_50_150=bool(G0 and np.isfinite(ds) and 50 <= ds <= 150),
                         SM_opt_NOFB=fstar(res["NOFB"])["SM_opt"], SM_opt_NAT=fstar(res["NAT"])["SM_opt"]))
        print(label, rows[-1]["delta_star"], "G0", G0, "GZ", gz["passed"], f"{time.time()-t0:.0f}s", flush=True)
    cfg = [r for r in rows if not (r["config"].startswith("baseline") or r["config"].startswith("REFERENCE"))]
    frac = float(np.mean([r["in_50_150"] for r in cfg]))
    out = dict(N=N, rows=rows, frac_in_50_150=frac, n_in=int(sum(r["in_50_150"] for r in cfg)), n_configs=len(cfg),
               robust=bool(frac >= 0.7), runtime_s=round(time.time() - t0, 1))
    with open(os.path.join(RES, "p1b_grip_latency_sensitivity.json"), "w") as f:
        json.dump(to_json(out), f, indent=1)
    return out


def figures():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    with open(os.path.join(RES, "p1b_grip_latency.json")) as f:
        o = json.load(f)
    if "R_curves" not in o:
        return
    fig, ax = plt.subplots(1, 2, figsize=(14.5, 5.2))
    a = ax[0]
    # Plot F*_ART(delta) directly (R is undefined whenever F*NOFB <= F*NAT), with NOFB / NAT reference lines.
    a.axvspan(50, 150, color="#dfe8f5", label="H3 band for δ*: [50,150] ms")
    FN, FA = o["Fstar"]["NOFB"]["F"], o["Fstar"]["NAT"]["F"]
    a.axhline(FN, color="#7a7a7a", ls="--", lw=1.2, label=f"NOFB (open loop) F* = {FN:.3f}")
    a.axhline(FA, color="#2e7d32", ls="--", lw=1.2, label=f"NAT (74 ms) F* = {FA:.3f}")
    a.axhline(o["Fstar"]["VIS200"]["F"], color="#b8860b", ls=":", lw=1.2, label=f"VIS 200 ms F* = {o['Fstar']['VIS200']['F']:.3f}")
    ci = np.array([o["Fstar_CI95"][f"ART_d{d}_p0.95"] for d in DELTAS], dtype=float)
    a.fill_between(DELTAS, ci[:, 0], ci[:, 1], color="#1f5fa8", alpha=0.18, label="95% CI (p_det = 0.95)")
    for p, col in zip(PS, ["#bdbdbd", "#6b8fc2", "#1f5fa8"]):
        a.plot(DELTAS, [o["Fstar"][f"ART_d{d}_p{p}"]["F"] for d in DELTAS], "o-", color=col, label=f"ART, p_det = {p}")
    a.plot([0], [o["Fstar"]["SHUF"]["F"]], "x", color="#c0392b", ms=10, mew=2, label="shuffled-feedback control")
    a.set_xlabel("added feedback latency δ relative to natural 74 ms (model ms)")
    a.set_ylabel("failure rate F* at optimal safety margin (drop or crush)")
    ci_ = [x if (x is None or isinstance(x, str)) else round(float(x), 1) for x in o['delta_star_boot']['CI95']]
    gz = o["G_Z"]["F"]
    a.set_title(f"P1b grip model (model units): F* vs added latency; δ* = {o['delta_star']} (95% CI {ci_})\n"
                f"G_Z: F*NOFB(K=0) = {gz['NOFB']['F']:.4f}, F*NAT(K=0) = {gz['NAT']['F']:.4f} (PASS); "
                f"G0 {'holds' if o['G0']['holds'] else 'FAILS'}: F*NAT/F*NOFB = {o['G0']['ratio']:.2f} (needs ≤ 0.5)",
                fontsize=8.5)
    a.legend(fontsize=7, loc="best")
    b = ax[1]
    keys = ["NOFB", "NAT", "VIS150", "VIS200", "VIS250"] + [f"ART_d{d}_p0.95" for d in DELTAS] + ["SHUF"]
    Fv = [o["Fstar"][k]["F"] for k in keys]
    cl = np.array([o["Fstar_CI95"][k] for k in keys])
    b.bar(range(len(keys)), Fv, color=["#7a7a7a", "#2e7d32"] + ["#b8860b"] * 3 + ["#1f5fa8"] * len(DELTAS) + ["#c0392b"])
    b.errorbar(range(len(keys)), Fv, yerr=[np.array(Fv) - cl[:, 0], cl[:, 1] - np.array(Fv)], fmt="none", ecolor="k", lw=1)
    b.set_xticks(range(len(keys)))
    b.set_xticklabels([k.replace("_p0.95", "").replace("ART_d", "ART δ=") for k in keys], rotation=70, fontsize=7)
    b.set_xlabel("feedback condition (model)")
    b.set_ylabel("failure rate F* at the condition's optimal safety margin")
    b.set_title("P1b: F* per condition, 95% bootstrap CI (model units)", fontsize=9)
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(os.path.join(FIG, f"p1b_R_vs_delta.{ext}"), dpi=150)
    plt.close(fig)
    sp = os.path.join(RES, "p1b_grip_latency_sensitivity.json")
    if os.path.exists(sp):
        with open(sp) as f:
            s = json.load(f)
        fig, a = plt.subplots(figsize=(8.5, 6.5))
        rows = s["rows"]
        vals = []
        for r in rows:
            d = r["delta_star"]
            vals.append(320 if d == "> 300" else (-40 if d == "< -20" else (np.nan if d == "undefined" else float(d))))
        y = np.arange(len(rows))
        a.axvspan(50, 150, color="#dfe8f5", label="H3 band [50,150] ms")
        cols = ["#1f5fa8" if r["G0"] else "#c0392b" for r in rows]
        a.scatter(vals, y, c=cols, zorder=3)
        a.set_yticks(y)
        a.set_yticklabels([r["config"] for r in rows], fontsize=7.5)
        a.set_xlabel("δ* (model ms); plotted at 320 if > 300, at −40 if < −20")
        a.set_ylabel("sensitivity configuration (N = 1000 each)")
        a.set_title(f"P1b sensitivity (model units): δ* in [50,150] in {s['n_in']}/{s['n_configs']} configs "
                    f"(blue = G0 holds, red = G0 fails)", fontsize=9)
        a.invert_yaxis()
        a.legend(fontsize=8)
        fig.tight_layout()
        for ext in ("png", "svg"):
            fig.savefig(os.path.join(FIG, f"p1b_sensitivity.{ext}"), dpi=150)
        plt.close(fig)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "test"
    os.makedirs(RES, exist_ok=True)
    os.makedirs(FIG, exist_ok=True)
    if mode == "test":
        r = self_test()
        print("SELF-TEST", r, "ALL PASS" if all(r.values()) else "FAILURES")
        with open(os.path.join(RES, "p1b_selftest.json"), "w") as f:
            json.dump(r, f, indent=1)
        sys.exit(0 if all(r.values()) else 1)
    if mode == "main":
        o = run_main()
        print(json.dumps(to_json({k: o.get(k) for k in ("G_Z", "reference_regression_pass", "G0", "delta_star",
                                                         "delta_star_boot", "H3_verdict", "H3b", "R_shuffled", "runtime_s")}),
                         indent=1))
    if mode == "sens":
        s = run_sens()
        print("in [50,150]:", s["n_in"], "/", s["n_configs"], "runtime", s["runtime_s"])
    if mode in ("fig", "main", "sens"):
        figures()
