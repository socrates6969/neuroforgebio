"""P3b: threshold-only Bayesian adaptive recalibration (1-D posterior over alpha, ASSUMED slope) vs 3-down-1-up staircase.

Implements prereg\\P3b_threshold_only_psi_recalibration.md (FIXED). Simulated observers only.
Everything not changed by P3b is identical to prereg\\P3 and is reused from code\\p3_psi_calibration.py (imported, not modified).
Interpretations/deviations: code\\DEVIATIONS.md, section P3b.

Run:  python p3b_psi_threshold_only.py            (self-tests + full run)
      python p3b_psi_threshold_only.py --selftest (self-tests only)
"""
import json
import os
import sys
import time

import numpy as np

BASE = r"C:\Users\mariu\neuro-company\research\somatosensory\code"
sys.path.insert(0, BASE)
import p3_psi_calibration as p3  # noqa: E402  (cycle-1 code, reused read-only)

RES, FIG = p3.RES, p3.FIG
SEED = p3.SEED
CELLS, BUDGETS, NRUNS, NMAX = p3.CELLS, p3.BUDGETS, p3.NRUNS, p3.NMAX
THR, BIAS_THR = p3.THR, p3.BIAS_THR
BETA_A = 3.0          # assumed slope (C1/C2)
LAM_A = 0.02
N_ALPHA = 200
P3_JSON = os.path.join(RES, "p3_psi_staircase.json")

# rng namespaces for the A arms (staircases reuse P3's exact keys so they are bit-identical to P3)
VID = dict(main=200, oracle=201, a_logistic=202, b_plus=203, b_minus=204, c_beta2=205, c_beta45=206)


def make_grid_1d(beta_a, lam=LAM_A):
    """1-D posterior: 200 log-spaced alpha in [2,200] uA, slope fixed at beta_a, lam fixed, gamma 0.5.
    Returns a dict with the same keys as p3.make_grid so p3.run_psi / p3.expected_entropy work unchanged."""
    A = np.geomspace(2, 200, N_ALPHA)
    B = np.full_like(A, float(beta_a))
    Lm = np.full_like(A, float(lam))
    cands = np.unique(np.round(np.geomspace(2, 100, 40)).astype(int)).astype(float)   # identical to P3
    L = np.clip(p3.weibull_p(cands[None, :], A[:, None], B[:, None], Lm[:, None]), 1e-12, 1 - 1e-12)
    g = dict(A=A, B=B, lam=Lm, cands=cands, L=L, logL=np.log(L), log1mL=np.log1p(-L),
             logtheta=np.log(p3.weibull_x_at(0.75, A, B, Lm)), beta_a=float(beta_a))
    g["LlogL"] = L * g["logL"]
    g["MlogM"] = (1 - L) * g["log1mL"]
    return g


_GRIDS = {}


def grid(beta_a):
    if beta_a not in _GRIDS:
        _GRIDS[beta_a] = make_grid_1d(beta_a)
    return _GRIDS[beta_a]


def sim_A(vid, beta_a=BETA_A, kind="weibull", drift=0.0, adaptive=True, key=0):
    """beta_a = float (assumed slope for all cells) or 'oracle' (true beta per cell)."""
    out = {}
    for ci, (th, be, la) in enumerate(CELLS):
        obs = p3.Observer(th, be, la, kind=kind, drift=drift)
        g = grid(be if beta_a == "oracle" else beta_a)
        est, xs = p3.run_psi(obs, p3.rng_for(vid, ci, key), g, adaptive=adaptive)
        out[ci] = dict(e_psi=np.log(est) - np.log(p3.target_series(obs, 0.75)),
                       frac_at_cap=float((xs >= 100).mean()))
    return out


def sim_stair(vid, kind="weibull", drift=0.0, down=3, start=80.0):
    return p3.simulate_variant(vid, kind=kind, drift=drift, stair_down=down, stair_start=start,
                               do_psi=False, do_stair=True, do_ctrl=False)


def nreq(e):
    return p3.n_req_from_rmse(np.sqrt((e ** 2).mean(0)))


def minutes(v):
    v = np.asarray(v, float)
    fin = v[np.isfinite(v)]
    k = p3.N_ELEC * p3.SEC_PER_TRIAL / 60
    return dict(median_min=float(np.median(np.where(np.isfinite(v), v, 150)) * k),
                min_min=float(fin.min() * k) if fin.size else None,
                max_finite_min=float(fin.max() * k) if fin.size else None,
                n_cells_over_150=int((~np.isfinite(v)).sum()), note="median uses 150 for '>150' cells (lower bound)")


# ----------------------------------------------------------------------------- self tests
def selftest():
    res = {}
    # 1. observer parameterisation (as in P3)
    worst = 0.0
    for th, be, la in CELLS:
        for kind in ("weibull", "logistic"):
            o = p3.Observer(th, be, la, kind=kind)
            worst = max(worst, abs(o.p(th, 0) - 0.75), abs(o.p(o.x_at(p3.P_3D1U), 0) - p3.P_3D1U))
    res["observer_param_max_err"] = worst
    assert worst < 1e-9
    # 2. closed-form expected entropy vs brute force on the 1-D posterior
    g = grid(BETA_A)
    rng = np.random.default_rng(1)
    post = rng.random((3, N_ALPHA)) ** 4
    post /= post.sum(1, keepdims=True)
    fast = p3.expected_entropy(post, g)
    brute = np.zeros_like(fast)
    H = lambda q: -(q[q > 0] * np.log(q[q > 0])).sum()
    for r in range(3):
        for c in range(g["cands"].size):
            L = g["L"][:, c]
            Z = post[r] @ L
            brute[r, c] = Z * H(post[r] * L / Z) + (1 - Z) * H(post[r] * (1 - L) / (1 - Z))
    res["entropy_1d_max_abs_err"] = float(np.abs(fast - brute).max())
    assert res["entropy_1d_max_abs_err"] < 1e-9
    # 3. estimator: exp(E log theta75) == exp(E log alpha) * u^(1/beta_a)  (prereg C1 wording)
    u = -np.log(1 - p3.weib_q(0.75, LAM_A))
    e1 = np.exp(post @ g["logtheta"])
    e2 = np.exp(post @ np.log(g["A"])) * u ** (1 / BETA_A)
    res["estimator_identity_max_rel_err"] = float(np.abs(e1 / e2 - 1).max())
    assert res["estimator_identity_max_rel_err"] < 1e-12
    # 4. grid spec
    assert g["A"].size == 200 and abs(g["A"][0] - 2) < 1e-12 and abs(g["A"][-1] - 200) < 1e-9
    assert np.all(g["B"] == 3.0) and np.all(g["lam"] == 0.02)
    res["n_candidates"] = int(g["cands"].size)
    # 5. model-matched recovery (beta 3, lam 0.02) with 600 trials
    obs = p3.Observer(20.0, 3.0, 0.02)
    est, _ = p3.run_psi(obs, p3.rng_for(7777, 10), g, nruns=100, ntrials=600, budgets=[600])
    e = np.log(est[:, 0] / 20.0)
    res["recovery_600trials"] = dict(ratio=float(np.exp(e.mean())), rmse_log=float(np.sqrt((e ** 2).mean())))
    assert abs(e.mean()) < 0.03 and np.sqrt((e ** 2).mean()) < 0.06, res["recovery_600trials"]
    # 6. misspecified-slope bias sign check: true beta 1.5 with assumed 3 -> finite, recorded (no assertion on sign)
    obs = p3.Observer(20.0, 1.5, 0.02)
    est, _ = p3.run_psi(obs, p3.rng_for(7777, 11), g, nruns=100, ntrials=600, budgets=[600])
    res["misspecified_beta1p5_600trials_mean_log_err"] = float(np.log(est[:, 0] / 20.0).mean())
    # 7. oracle grid uses the true slope
    assert grid(1.5)["B"][0] == 1.5 and grid(6.0)["B"][0] == 6.0
    res["all_passed"] = True
    return res


def stair_reproduces_p3(st_main):
    """the staircase arm must be bit-identical to P3's (same code, same rng keys)"""
    with open(P3_JSON) as f:
        d = json.load(f)
    ref = [c["N_req_stair"] for c in d["main"]["cells"]]
    mine = [nreq(st_main[ci]["e_st"]) for ci in range(len(CELLS))]
    diffs = []
    for a, b in zip(mine, ref):
        if b == ">150":
            diffs.append(0.0 if not np.isfinite(a) else np.inf)
        else:
            diffs.append(abs(a - b))
    return dict(max_abs_diff=float(max(diffs)), ok=bool(max(diffs) < 1e-9))


# ----------------------------------------------------------------------------- figures
def fig_savings(ev_main, ev_oracle):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 2, figsize=(13, 11))
    for ax, ev, ttl in ((axs[0], ev_main, "A (assumed beta_a = 3)"), (axs[1], ev_oracle, "A-oracle (beta_a = true beta; no verdict)")):
        M = np.full((16, 3), np.nan)
        for r in ev["cells"]:
            i = p3.LAMS.index(r["lam"]) * 4 + p3.THETAS.index(r["theta75"])
            j = p3.BETAS.index(r["beta"])
            s = r["savings"]
            if s is None:
                sp, txt = (1.0, "st>150") if r["savings_ok"] else (-1.0, "A>150")
            else:
                sp, txt = max(s, -1.0), f"{s:.2f}"
            M[i, j] = sp
            ax.text(j, i, f"{txt}\n{p3.fmt_n(r['N_req_psi'])}/{p3.fmt_n(r['N_req_stair'])}", ha="center", va="center", fontsize=7)
            if sp >= 0.30:
                ax.add_patch(plt.Rectangle((j - .5, i - .5), 1, 1, fill=False, ec="k", lw=1.5))
        im = ax.imshow(M, cmap="RdBu", vmin=-1, vmax=1, aspect="auto", zorder=0)
        ax.set_xticks(range(3)); ax.set_xticklabels([f"beta={b:g}" for b in p3.BETAS])
        ax.set_yticks(range(16)); ax.set_yticklabels([f"lam={la:.2f} th75={th:g}" for la in p3.LAMS for th in p3.THETAS], fontsize=8)
        ax.set_xlabel("true Weibull slope beta")
        ax.set_ylabel("true lapse lam, true threshold theta75 (uA)")
        ax.set_title(f"{ttl}\n{ev['n_savings_cells']}/48 cells savings >= 0.30 (CI {ev['n_savings_ci95'][0]}-{ev['n_savings_ci95'][1]})"
                     f"\ntext: savings, N_req(A)/N_req(stair)", fontsize=9)
        fig.colorbar(im, ax=ax, label="savings = 1 - N_req(A)/N_req(3d1u staircase) (clipped at -1)", shrink=0.6)
    fig.suptitle(f"P3b threshold-only Bayesian adaptive vs staircase: verdict {ev_main['verdict']}")
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(os.path.join(FIG, f"p3b_savings_map.{ext}"), dpi=150)
    plt.close(fig)


def fig_rmse(A, O, C, S):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ex = [(20.0, 3.0, 0.02), (20.0, 1.5, 0.02), (20.0, 6.0, 0.02), (50.0, 1.5, 0.05)]
    fig, axs = plt.subplots(2, 2, figsize=(10, 7.5), sharex=True)
    for ax, (th, be, la) in zip(axs.ravel(), ex):
        ci = CELLS.index((th, be, la))
        for d, key, lab, col in ((A, "e_psi", "A (beta_a=3)", "C0"), (O, "e_psi", "A-oracle", "C1"),
                                 (C, "e_psi", "control (random placement)", "C2"), (S, "e_st", "3d1u staircase (vs x79.4)", "C3")):
            ax.plot(BUDGETS, np.sqrt((d[ci][key] ** 2).mean(0)), "o-", color=col, ms=3, label=lab)
        ax.axhline(THR, color="k", ls="--", lw=1, label="target RMSE ln 1.2")
        ax.set_ylim(0, 1.0)
        ax.set_title(f"theta75={th:g} uA, beta={be:g}, lam={la:g}", fontsize=9)
        ax.set_ylabel("RMSE of ln(estimate/target)")
    for ax in axs[1]:
        ax.set_xlabel("trials N")
    axs[0, 0].legend(fontsize=7)
    fig.suptitle("P3b: RMSE vs trial budget (300 simulated runs per curve)")
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(os.path.join(FIG, f"p3b_rmse_curves.{ext}"), dpi=150)
    plt.close(fig)


# ----------------------------------------------------------------------------- main
def main():
    t0 = time.time()
    st = selftest()
    print("self-tests passed:", json.dumps(st), flush=True)
    if "--selftest" in sys.argv:
        return
    timing = {}
    t = time.time()
    S = sim_stair(0)                                   # identical keys to P3 main staircase
    A = sim_A(VID["main"], BETA_A)
    C = sim_A(VID["main"], BETA_A, adaptive=False, key=2)
    O = sim_A(VID["oracle"], "oracle")
    timing["main"] = time.time() - t
    st["staircase_reproduces_P3"] = stair_reproduces_p3(S)
    assert st["staircase_reproduces_P3"]["ok"], st["staircase_reproduces_P3"]
    print("main done", timing["main"], flush=True)

    ev = p3.evaluate(A, S, nboot=1000, boot_seed=20)
    ev_or = p3.evaluate(O, S, nboot=1000, boot_seed=21)
    # control / abandonment 1
    n_within = 0
    for ci, r in enumerate(ev["cells"]):
        nc, na = nreq(C[ci]["e_psi"]), r["N_req_psi"]
        within = bool(np.isfinite(nc) and nc <= 1.10 * na) if np.isfinite(na) else (not np.isfinite(nc))
        n_within += within
        r.update(N_req_ctrl=nc, ctrl_within_10pct=within, N_req_oracle=ev_or["cells"][ci]["N_req_psi"],
                 bias60_oracle=ev_or["cells"][ci]["bias60_psi"], A_frac_trials_at_cap=A[ci]["frac_at_cap"],
                 rmse_ctrl=np.sqrt((C[ci]["e_psi"] ** 2).mean(0)).tolist(),
                 rmse_oracle=np.sqrt((O[ci]["e_psi"] ** 2).mean(0)).tolist())
    abandon = dict(ctrl_within_10pct_cells=int(n_within), ctrl_rule_triggered=bool(n_within >= 36),
                   oracle_savings_cells=ev_or["n_savings_cells"], oracle_savings_ci95=ev_or["n_savings_ci95"],
                   oracle_rule_triggered_stop_line=bool(ev_or["n_savings_cells"] < 24))
    # per-beta breakdown (prediction check)
    by_beta = {}
    for be in p3.BETAS:
        rows = [r for r in ev["cells"] if r["beta"] == be]
        rows_o = [r for r in ev_or["cells"] if r["beta"] == be]
        by_beta[str(be)] = dict(A_savings_cells=int(sum(r["savings_ok"] for r in rows)),
                                oracle_savings_cells=int(sum(r["savings_ok"] for r in rows_o)),
                                A_median_Nreq=float(np.median([min(r["N_req_psi"], 150) for r in rows])),
                                oracle_median_Nreq=float(np.median([min(r["N_req_psi"], 150) for r in rows_o])),
                                stair_median_Nreq=float(np.median([min(r["N_req_stair"], 150) for r in rows])),
                                A_max_abs_bias60_lam_le_0p05=float(max(abs(r["bias60_psi"]) for r in rows if r["lam"] <= 0.05)))
    mins = dict(A=minutes([r["N_req_psi"] for r in ev["cells"]]), stair_3d1u=minutes([r["N_req_stair"] for r in ev["cells"]]),
                control=minutes([r["N_req_ctrl"] for r in ev["cells"]]), oracle=minutes([r["N_req_psi"] for r in ev_or["cells"]]))
    max_bias = max(abs(r["bias60_psi"]) for r in ev["cells"] if r["lam"] <= 0.05)

    # sensitivity
    var = {}
    t = time.time()
    Sa = sim_stair(1, kind="logistic")
    var["a_logistic_observer"] = p3.evaluate(sim_A(VID["a_logistic"], BETA_A, kind="logistic"), Sa, nboot=300, boot_seed=22)
    for k, d, vs in (("b_drift_plus20", 0.2, 2), ("b_drift_minus20", -0.2, 3)):
        Sb = sim_stair(vs, drift=d)
        var[k] = p3.evaluate(sim_A(VID["b_plus" if d > 0 else "b_minus"], BETA_A, drift=d), Sb, nboot=300, boot_seed=23 if d > 0 else 24)
    var["c_beta_a_2"] = p3.evaluate(sim_A(VID["c_beta2"], 2.0), S, nboot=300, boot_seed=25)
    var["c_beta_a_4p5"] = p3.evaluate(sim_A(VID["c_beta45"], 4.5), S, nboot=300, boot_seed=26)
    var["d_stair_2down1up"] = p3.evaluate(A, sim_stair(5, down=2), nboot=300, boot_seed=27)
    var["e_stair_start_40uA"] = p3.evaluate(A, sim_stair(6, start=40.0), nboot=300, boot_seed=28)
    timing["sensitivity"] = time.time() - t

    # P3 lapse follow-up rule is replaced by P3b section 3; count reported only
    out = dict(prereg="prereg/P3b_threshold_only_psi_recalibration.md", seed=SEED, nruns=NRUNS, budgets=BUDGETS,
               beta_assumed=BETA_A, lam_assumed=LAM_A, n_alpha=N_ALPHA, selftest=st, main=ev,
               max_abs_bias60_lam_le_0p05=max_bias, oracle=ev_or, abandonment=abandon, by_beta=by_beta,
               minutes_per_64_electrode_array_at_4s_per_trial=mins,
               sensitivity={k: {kk: v[kk] for kk in v if kk != "cells"} | {"max_abs_bias60_lam_le_0p05": max(
                   abs(r["bias60_psi"]) for r in v["cells"] if r["lam"] <= 0.05), "cells_compact": [
                   dict(theta75=r["theta75"], beta=r["beta"], lam=r["lam"], N_req_A=r["N_req_psi"], N_req_stair=r["N_req_stair"],
                        savings=r["savings"], bias60_A=r["bias60_psi"]) for r in v["cells"]]} for k, v in var.items()},
               timing_s=timing, runtime_s=time.time() - t0)
    with open(os.path.join(RES, "p3b_threshold_psi.json"), "w") as f:
        json.dump(p3.jsonable(out), f, indent=1)
    fig_savings(ev, ev_or)
    fig_rmse(A, O, C, S)
    print(json.dumps(p3.jsonable(dict(
        verdict=ev["verdict"], n_sav=ev["n_savings_cells"], ci=ev["n_savings_ci95"], bias_ok=ev["bias_ok_all_lam_le_0p05"],
        n_bias_fail=ev["n_bias_fail_lam_le_0p05"], max_bias=max_bias, bias_fail_lam10=ev["n_bias_fail_lam_0p10"],
        oracle=(ev_or["verdict"], ev_or["n_savings_cells"], ev_or["n_savings_ci95"], ev_or["n_bias_fail_lam_le_0p05"]),
        abandon=abandon, by_beta=by_beta, minutes=mins,
        variants={k: (v["verdict"], v["n_savings_cells"], v["n_savings_ci95"], v["n_bias_fail_lam_le_0p05"]) for k, v in var.items()},
        runtime=out["runtime_s"])), indent=1))


if __name__ == "__main__":
    main()
