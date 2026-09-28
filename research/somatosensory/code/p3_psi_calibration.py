"""P3: psi (Kontsevich & Tyler 1999) vs 3-down-1-up staircase for 2AFC threshold calibration.

Implements prereg\\P3_psi_vs_staircase_calibration.md (FIXED). Simulated observers only.
Interpretations/deviations are logged in code\\DEVIATIONS.md (section P3).

Run:  python p3_psi_calibration.py            (self-tests + full run)
      python p3_psi_calibration.py --selftest (self-tests only)
"""
import json
import os
import sys
import time

import numpy as np

BASE = r"C:\Users\mariu\neuro-company\research\somatosensory\code"
RES = os.path.join(BASE, "results")
FIG = os.path.join(BASE, "figures")
SEED = 20260926

THETAS = [10.0, 20.0, 31.5, 50.0]
BETAS = [1.5, 3.0, 6.0]
LAMS = [0.0, 0.02, 0.05, 0.10]
BUDGETS = [10, 15, 20, 30, 40, 50, 60, 80, 100, 120, 150]
NRUNS = 300
NMAX = 150
THR = np.log(1.2)       # RMSE target
BIAS_THR = np.log(1.10)  # |mean e| at N=60
SEC_PER_TRIAL = 4.0
N_ELEC = 64
P_3D1U = 0.5 ** (1 / 3)   # 0.7937
P_2D1U = 0.5 ** (1 / 2)   # 0.7071

CELLS = [(th, be, la) for th in THETAS for be in BETAS for la in LAMS]  # 48


# ----------------------------------------------------------------------------- observers
def weib_q(p, lam):
    """fraction of the (0.5-lam) range needed to reach p"""
    return (p - 0.5) / (0.5 - lam)


def weibull_p(x, alpha, beta, lam):
    return 0.5 + (0.5 - lam) * (1.0 - np.exp(-(x / alpha) ** beta))


def weibull_alpha_from_x(xp, beta, lam, p=0.75):
    u = -np.log(1.0 - weib_q(p, lam))
    return xp / u ** (1.0 / beta)


def weibull_x_at(p, alpha, beta, lam):
    u = -np.log(1.0 - weib_q(p, lam))
    return alpha * u ** (1.0 / beta)


class Observer:
    """True observer. kind 'weibull' or 'logistic' (logistic in ln x, same theta75 and matched slope dp/dx at theta75).
    drift: fractional linear change of the whole function's location over NMAX trials (scale factor 1+drift*t/(NMAX-1))."""

    def __init__(self, theta, beta, lam, kind="weibull", drift=0.0):
        self.theta, self.beta, self.lam, self.kind, self.drift = theta, beta, lam, kind, drift
        q = weib_q(0.75, lam)
        if not (0 < q < 1):
            raise ValueError("invalid cell: 0.75 unreachable")
        self.alpha = weibull_alpha_from_x(theta, beta, lam)
        u = -np.log(1 - q)
        # logistic F = 1/(1+exp(-s(ln x - ln m))); match F(theta)=q and dF/dlnx at theta: s q(1-q) = beta u (1-q)
        self.s = beta * u / q
        self.lnm = np.log(theta) - np.log(q / (1 - q)) / self.s

    def scale(self, t):
        return 1.0 + self.drift * t / (NMAX - 1)

    def p(self, x, t):
        f = self.scale(t)
        if self.kind == "weibull":
            return weibull_p(x, self.alpha * f, self.beta, self.lam)
        return 0.5 + (0.5 - self.lam) / (1.0 + np.exp(-self.s * (np.log(x) - self.lnm - np.log(f))))

    def x_at(self, p, t=0):
        f = self.scale(t)
        if self.kind == "weibull":
            return weibull_x_at(p, self.alpha, self.beta, self.lam) * f
        q = weib_q(p, self.lam)
        return np.exp(self.lnm + np.log(q / (1 - q)) / self.s) * f


# ----------------------------------------------------------------------------- psi
def make_grid(lam_values=(0.02,)):
    alphas = np.geomspace(2, 200, 40)
    betas = np.geomspace(0.7, 10, 10)
    lam_values = np.asarray(lam_values, float)
    A, B, Lm = np.meshgrid(alphas, betas, lam_values, indexing="ij")
    A, B, Lm = A.ravel(), B.ravel(), Lm.ravel()
    cands = np.unique(np.round(np.geomspace(2, 100, 40)).astype(int)).astype(float)
    L = weibull_p(cands[None, :], A[:, None], B[:, None], Lm[:, None])  # P(correct | params, stim)
    L = np.clip(L, 1e-12, 1 - 1e-12)
    g = dict(A=A, B=B, lam=Lm, cands=cands, L=L, logL=np.log(L), log1mL=np.log1p(-L),
             logtheta=np.log(weibull_x_at(0.75, A, B, Lm)))
    g["LlogL"] = L * g["logL"]
    g["MlogM"] = (1 - L) * g["log1mL"]
    return g


def expected_entropy(post, g):
    """expected posterior entropy for each candidate stimulus, vectorised over runs. post: (R,P) normalised"""
    L = g["L"]
    with np.errstate(divide="ignore", invalid="ignore"):
        plogp = np.where(post > 0, post * np.log(np.where(post > 0, post, 1.0)), 0.0)
    Z = post @ L
    Es = plogp @ L + post @ g["LlogL"]
    Ef = plogp @ (1 - L) + post @ g["MlogM"]
    return Z * np.log(Z) - Es + (1 - Z) * np.log(1 - Z) - Ef


def run_psi(obs, rng, g, adaptive=True, nruns=NRUNS, ntrials=NMAX, budgets=BUDGETS):
    P = g["A"].size
    C = g["cands"].size
    logpost = np.full((nruns, P), -np.log(P))
    est = np.zeros((nruns, len(budgets)))
    xs = np.zeros((nruns, ntrials))
    bset = {n: i for i, n in enumerate(budgets)}
    rr = np.arange(nruns)
    for t in range(ntrials):
        post = np.exp(logpost - logpost.max(1, keepdims=True))
        post /= post.sum(1, keepdims=True)
        if adaptive:
            idx = np.argmin(expected_entropy(post, g), axis=1)
        else:
            idx = rng.integers(0, C, size=nruns)
        x = g["cands"][idx]
        xs[:, t] = x
        resp = rng.random(nruns) < obs.p(x, t)
        logpost += np.where(resp[:, None], g["logL"][:, idx].T, g["log1mL"][:, idx].T)
        if (t + 1) in bset:
            post = np.exp(logpost - logpost.max(1, keepdims=True))
            post /= post.sum(1, keepdims=True)
            est[:, bset[t + 1]] = np.exp(post @ g["logtheta"])
    del rr
    return est, xs


# ----------------------------------------------------------------------------- staircase
def run_stair(obs, rng, down=3, start=80.0, nruns=NRUNS, ntrials=NMAX, budgets=BUDGETS):
    level = np.full(nruns, float(start))       # internal (unrounded) level
    ncorr = np.zeros(nruns, int)
    last_dir = np.zeros(nruns, int)
    nrev = np.zeros(nruns, int)
    pres = np.zeros((nruns, ntrials))
    revnum = np.zeros((nruns, ntrials), int)   # 0 = no reversal on this trial, k = k-th reversal
    for t in range(ntrials):
        x = np.round(np.clip(level, 1, 100))
        pres[:, t] = x
        resp = rng.random(nruns) < obs.p(x, t)
        ncorr = np.where(resp, ncorr + 1, 0)
        dn = resp & (ncorr >= down)
        up = ~resp
        ncorr[dn] = 0
        d = np.where(dn, -1, np.where(up, 1, 0))
        mv = d != 0
        rev = mv & (last_dir != 0) & (d != last_dir)
        nrev += rev
        revnum[rev, t] = nrev[rev]
        fac = np.where(nrev >= 2, 1.26, 1.585)
        level = np.where(mv, level * fac ** d, level)
        level = np.clip(level, 1, 100)
        last_dir = np.where(mv, d, last_dir)
    est = np.zeros((nruns, len(budgets)))
    lp = np.log(pres)
    for j, n in enumerate(budgets):
        use = revnum[:, :n] >= 3              # reversals after the 2nd reversal
        cnt = use.sum(1)
        gm = np.exp(np.where(use, lp[:, :n], 0).sum(1) / np.maximum(cnt, 1))
        est[:, j] = np.where(cnt >= 2, gm, pres[:, n - 1])
    return est, pres


# ----------------------------------------------------------------------------- metrics
def n_req_from_rmse(rmse, budgets=BUDGETS, thr=THR):
    b = np.asarray(budgets, float)
    ok = np.nonzero(rmse <= thr)[0]
    if ok.size == 0:
        return np.inf
    i = ok[0]
    if i == 0:
        return b[0]
    r0, r1 = rmse[i - 1], rmse[i]
    return b[i - 1] + (r0 - thr) / (r0 - r1) * (b[i] - b[i - 1])


def n_req_batch(e):
    """e: (..., R, nb) -> N_req (...)"""
    rmse = np.sqrt((e ** 2).mean(-2))
    flat = rmse.reshape(-1, rmse.shape[-1])
    return np.array([n_req_from_rmse(r) for r in flat]).reshape(rmse.shape[:-1])


def savings_ok(npsi, nst):
    if not np.isfinite(npsi):
        return False, None
    if not np.isfinite(nst):
        return True, None  # counts as >= 0.30
    s = 1 - npsi / nst
    return bool(s >= 0.30), float(s)


def target_series(obs, p, budgets=BUDGETS):
    return np.array([obs.x_at(p, n - 1) for n in budgets])


# ----------------------------------------------------------------------------- experiment driver
def rng_for(*key):
    return np.random.default_rng([SEED, *key])


def simulate_variant(vid, kind="weibull", drift=0.0, psi_lams=(0.02,), stair_down=3, stair_start=80.0,
                     do_psi=True, do_stair=True, do_ctrl=False, g=None):
    out = {}
    if g is None and (do_psi or do_ctrl):
        g = make_grid(psi_lams)
    p_st = P_3D1U if stair_down == 3 else P_2D1U
    for ci, (th, be, la) in enumerate(CELLS):
        obs = Observer(th, be, la, kind=kind, drift=drift)
        tgt75 = np.log(target_series(obs, 0.75))
        tgtst = np.log(target_series(obs, p_st))
        cell = {}
        if do_psi:
            est, xs = run_psi(obs, rng_for(vid, ci, 0), g, adaptive=True)
            cell["e_psi"] = np.log(est) - tgt75
            cell["psi_frac_at_cap"] = float((xs >= 100).mean())
        if do_ctrl:
            est, _ = run_psi(obs, rng_for(vid, ci, 2), g, adaptive=False)
            cell["e_ctrl"] = np.log(est) - tgt75
        if do_stair:
            est, _ = run_stair(obs, rng_for(vid, ci, 1), down=stair_down, start=stair_start)
            cell["e_st"] = np.log(est) - tgtst
            cell["e_st_vs75"] = np.log(est) - tgt75
        out[ci] = cell
    return out


def evaluate(psi_cells, st_cells, nboot=1000, boot_seed=0):
    """apply the decision rule; psi_cells/st_cells: dict ci -> dict with e_psi / e_st"""
    i60 = BUDGETS.index(60)
    rows = []
    n_sav = 0
    bias_ok_all = True
    for ci, (th, be, la) in enumerate(CELLS):
        ep, es = psi_cells[ci]["e_psi"], st_cells[ci]["e_st"]
        rp, rs = np.sqrt((ep ** 2).mean(0)), np.sqrt((es ** 2).mean(0))
        npsi, nst = n_req_from_rmse(rp), n_req_from_rmse(rs)
        ok, s = savings_ok(npsi, nst)
        n_sav += ok
        b60 = float(ep[:, i60].mean())
        se60 = float(ep[:, i60].std(ddof=1) / np.sqrt(ep.shape[0]))
        bias_ok = abs(b60) <= BIAS_THR
        if la <= 0.05 and not bias_ok:
            bias_ok_all = False
        rows.append(dict(cell=ci, theta75=th, beta=be, lam=la, N_req_psi=npsi, N_req_stair=nst, savings=s,
                         savings_ok=ok, bias60_psi=b60, bias60_ci95=[b60 - 1.96 * se60, b60 + 1.96 * se60],
                         bias60_ok=bool(bias_ok), rmse_psi=rp.tolist(), rmse_stair=rs.tolist(),
                         bias_psi=ep.mean(0).tolist(), bias_stair=es.mean(0).tolist()))
    # bootstrap CI on the number of cells with savings >= 0.30 (resample runs within cell/method)
    rng = np.random.default_rng([SEED, 999, boot_seed])
    counts = np.zeros(nboot, int)
    for ci in range(len(CELLS)):
        ep, es = psi_cells[ci]["e_psi"], st_cells[ci]["e_st"]
        R = ep.shape[0]
        ip = rng.integers(0, R, (nboot, R))
        is_ = rng.integers(0, R, (nboot, R))
        npb = n_req_batch(ep[ip])
        nsb = n_req_batch(es[is_])
        for b in range(nboot):
            counts[b] += savings_ok(npb[b], nsb[b])[0]
    verdict = "PASS" if (n_sav >= 36 and bias_ok_all) else "FAIL"
    return dict(verdict=verdict, n_savings_cells=int(n_sav), n_savings_ci95=[int(np.percentile(counts, 2.5)),
                int(np.percentile(counts, 97.5))], bias_ok_all_lam_le_0p05=bool(bias_ok_all),
                n_bias_fail_lam_le_0p05=int(sum((not r["bias60_ok"]) and r["lam"] <= 0.05 for r in rows)),
                n_bias_fail_lam_0p10=int(sum((not r["bias60_ok"]) and r["lam"] == 0.10 for r in rows)),
                cells=rows)


def fmt_n(n):
    return ">150" if not np.isfinite(n) else round(float(n), 1)


def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, (np.floating, float)):
        o = float(o)
        return ">150" if o == np.inf else (None if np.isnan(o) else o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


# ----------------------------------------------------------------------------- self tests
def selftest():
    res = {}
    # 1. observer parameterisation
    worst = 0.0
    for th, be, la in CELLS:
        for kind in ("weibull", "logistic"):
            o = Observer(th, be, la, kind=kind)
            worst = max(worst, abs(o.p(th, 0) - 0.75), abs(o.p(o.x_at(P_3D1U), 0) - P_3D1U))
        ow, ol = Observer(th, be, la), Observer(th, be, la, kind="logistic")
        h = 1e-4 * th
        sw = (ow.p(th + h, 0) - ow.p(th - h, 0)) / (2 * h)
        sl = (ol.p(th + h, 0) - ol.p(th - h, 0)) / (2 * h)
        res.setdefault("logistic_slope_max_rel_mismatch", 0.0)
        res["logistic_slope_max_rel_mismatch"] = max(res["logistic_slope_max_rel_mismatch"], abs(sw - sl) / sw)
    res["observer_param_max_err"] = worst
    assert worst < 1e-9, worst
    assert res["logistic_slope_max_rel_mismatch"] < 1e-5, res["logistic_slope_max_rel_mismatch"]
    # 2. entropy formula vs brute force
    g = make_grid()
    rng = np.random.default_rng(1)
    post = rng.random((3, g["A"].size)); post /= post.sum(1, keepdims=True)
    fast = expected_entropy(post, g)
    brute = np.zeros_like(fast)
    for r in range(3):
        for c in range(g["cands"].size):
            L = g["L"][:, c]
            Z = post[r] @ L
            ps, pf = post[r] * L / Z, post[r] * (1 - L) / (1 - Z)
            H = lambda q: -(q[q > 0] * np.log(q[q > 0])).sum()
            brute[r, c] = Z * H(ps) + (1 - Z) * H(pf)
    res["entropy_formula_max_abs_err"] = float(np.abs(fast - brute).max())
    assert res["entropy_formula_max_abs_err"] < 1e-9
    # 3. psi recovers a known threshold with many trials (model-matched observer lam=0.02)
    obs = Observer(20.0, 3.0, 0.02)
    est, _ = run_psi(obs, rng_for(7777, 0), g, nruns=100, ntrials=600, budgets=[600])
    e = np.log(est[:, 0] / 20.0)
    res["psi_recovery_600trials"] = dict(true=20.0, ratio_geo_mean_est_to_true=float(np.exp(e.mean())), rmse_log=float(np.sqrt((e ** 2).mean())))
    assert abs(e.mean()) < 0.03 and np.sqrt((e ** 2).mean()) < 0.08, res["psi_recovery_600trials"]
    # 4. staircase converges on x79.4
    obs = Observer(20.0, 3.0, 0.0)
    est, _ = run_stair(obs, rng_for(7777, 1), nruns=200, ntrials=1000, budgets=[1000])
    e = np.log(est[:, 0] / obs.x_at(P_3D1U))
    res["stair_convergence_1000trials"] = dict(x794_true=float(obs.x_at(P_3D1U)), geo_mean_est=float(np.exp(np.log(est[:, 0]).mean())),
                                               mean_log_err=float(e.mean()))
    assert abs(e.mean()) < np.log(1.1), res["stair_convergence_1000trials"]
    # 5. N_req interpolation
    assert n_req_from_rmse(np.array([0.3, 0.2, 0.1] + [0.05] * 8)) == 15 + (0.2 - THR) / (0.2 - 0.1) * 5
    res["all_passed"] = True
    return res


# ----------------------------------------------------------------------------- figures
def figures(main, cells_main, variants_eval):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = main["cells"]
    # savings map: rows = (lam, theta), cols = beta
    labels, M = [], np.full((16, 3), np.nan)
    ann = [["" for _ in range(3)] for _ in range(16)]
    for r in rows:
        i = LAMS.index(r["lam"]) * 4 + THETAS.index(r["theta75"])
        j = BETAS.index(r["beta"])
        s = r["savings"]
        if s is None:
            s_plot = 1.0 if r["savings_ok"] else -1.0
            txt = "st>150" if r["savings_ok"] else "psi>150"
        else:
            s_plot, txt = s, f"{s:.2f}"
        M[i, j] = s_plot
        ann[i][j] = f"{txt}\n{fmt_n(r['N_req_psi'])}/{fmt_n(r['N_req_stair'])}"
    for la in LAMS:
        for th in THETAS:
            labels.append(f"lam={la:.2f}  th75={th:g}")
    fig, ax = plt.subplots(figsize=(7.5, 11))
    im = ax.imshow(M, cmap="RdBu", vmin=-1, vmax=1, aspect="auto")
    for i in range(16):
        for j in range(3):
            ax.text(j, i, ann[i][j], ha="center", va="center", fontsize=7)
            if not np.isnan(M[i, j]) and M[i, j] >= 0.30:
                ax.add_patch(plt.Rectangle((j - .5, i - .5), 1, 1, fill=False, ec="k", lw=1.5))
    ax.set_xticks(range(3)); ax.set_xticklabels([f"beta={b:g}" for b in BETAS])
    ax.set_yticks(range(16)); ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("true Weibull slope beta")
    ax.set_ylabel("true lapse rate lam, true threshold theta75 (uA)")
    ax.set_title(f"P3 savings = 1 - N_req(psi)/N_req(3d1u staircase)\n(boxed: >= 0.30; text: savings, N_psi/N_stair)\n"
                 f"{main['n_savings_cells']}/48 cells >= 0.30 -> {main['verdict']}", fontsize=9)
    fig.colorbar(im, ax=ax, label="savings (fraction of trials saved)", shrink=0.6)
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(os.path.join(FIG, f"p3_savings_map.{ext}"), dpi=150)
    plt.close(fig)
    # RMSE curves for 4 example cells
    ex = [(20.0, 3.0, 0.02), (50.0, 1.5, 0.05), (10.0, 6.0, 0.0), (31.5, 3.0, 0.10)]
    fig, axs = plt.subplots(2, 2, figsize=(10, 7.5), sharex=True)
    for ax, (th, be, la) in zip(axs.ravel(), ex):
        ci = CELLS.index((th, be, la))
        c = cells_main[ci]
        for key, lab, col in (("e_psi", "psi", "C0"), ("e_ctrl", "control (random placement)", "C2"), ("e_st", "3d1u staircase (vs x79.4)", "C3")):
            if key in c:
                ax.plot(BUDGETS, np.sqrt((c[key] ** 2).mean(0)), "o-", color=col, label=lab, ms=3)
        ax.axhline(THR, color="k", ls="--", lw=1, label="target RMSE ln(1.2)")
        ax.set_title(f"theta75={th:g} uA, beta={be:g}, lam={la:g}", fontsize=9)
        ax.set_ylabel("RMSE of ln(estimate/target)")
        ax.set_ylim(0, 1.0)
    for ax in axs[1]:
        ax.set_xlabel("trials N")
    axs[0, 0].legend(fontsize=7)
    fig.suptitle("P3: threshold-estimate RMSE vs trial budget (300 simulated runs per curve)")
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(os.path.join(FIG, f"p3_rmse_curves.{ext}"), dpi=150)
    plt.close(fig)


# ----------------------------------------------------------------------------- main
def main():
    t0 = time.time()
    st = selftest()
    print("self-tests passed:", json.dumps(st))
    if "--selftest" in sys.argv:
        return
    timing = {}
    g02 = make_grid((0.02,))
    t = time.time()
    base = simulate_variant(0, do_psi=True, do_stair=True, do_ctrl=True, g=g02)
    timing["main"] = time.time() - t
    print(f"main done {timing['main']:.1f}s", flush=True)
    main_eval = evaluate(base, base)
    # control / abandonment check
    ctrl_rows, n_within = [], 0
    for ci, r in enumerate(main_eval["cells"]):
        nc = n_req_from_rmse(np.sqrt((base[ci]["e_ctrl"] ** 2).mean(0)))
        npsi = r["N_req_psi"]
        if np.isfinite(npsi):
            within = bool(np.isfinite(nc) and nc <= 1.10 * npsi)
        else:
            within = not np.isfinite(nc)
        n_within += within
        r["N_req_ctrl"] = nc
        r["ctrl_within_10pct"] = within
        r["rmse_ctrl"] = np.sqrt((base[ci]["e_ctrl"] ** 2).mean(0)).tolist()
        r["N_req_stair_vs_theta75"] = n_req_from_rmse(np.sqrt((base[ci]["e_st_vs75"] ** 2).mean(0)))
        r["stair_bias60_vs_theta75"] = float(base[ci]["e_st_vs75"][:, BUDGETS.index(60)].mean())
        r["psi_frac_trials_at_cap"] = base[ci]["psi_frac_at_cap"]
    abandon_ctrl = n_within >= 36
    # minutes per 64-electrode array
    def minutes(key):
        v = np.array([r[key] for r in main_eval["cells"]], float)
        fin = v[np.isfinite(v)]
        return dict(median_min=float(np.median(np.where(np.isfinite(v), v, 150)) * N_ELEC * SEC_PER_TRIAL / 60),
                    min_min=float(fin.min() * N_ELEC * SEC_PER_TRIAL / 60) if fin.size else None,
                    max_finite_min=float(fin.max() * N_ELEC * SEC_PER_TRIAL / 60) if fin.size else None,
                    n_cells_over_150=int((~np.isfinite(v)).sum()),
                    note="median uses 150 for '>150' cells (lower bound)")
    mins = {"psi": minutes("N_req_psi"), "stair_3d1u": minutes("N_req_stair"), "control": minutes("N_req_ctrl")}

    variants = {}
    # (a) logistic observer
    t = time.time(); va = simulate_variant(1, kind="logistic", g=g02); timing["a_logistic"] = time.time() - t
    variants["a_logistic_observer"] = evaluate(va, va, nboot=300, boot_seed=1)
    print("a done", flush=True)
    # (b) drift +20% / -20%
    for k, d in (("b_drift_plus20", 0.2), ("b_drift_minus20", -0.2)):
        t = time.time(); vb = simulate_variant(2 if d > 0 else 3, drift=d, g=g02); timing[k] = time.time() - t
        variants[k] = evaluate(vb, vb, nboot=300, boot_seed=2 if d > 0 else 3)
        print(k, "done", flush=True)
    # (c) psi lam fixed at 0.05 (staircase from main)
    t = time.time(); vc = simulate_variant(4, psi_lams=(0.05,), do_stair=False); timing["c_psi_lam05"] = time.time() - t
    variants["c_psi_lam_0p05"] = evaluate(vc, base, nboot=300, boot_seed=4)
    print("c done", flush=True)
    # (d) staircase 2-down-1-up vs x70.7 (psi from main)
    t = time.time(); vd = simulate_variant(5, stair_down=2, do_psi=False); timing["d_2d1u"] = time.time() - t
    variants["d_stair_2down1up"] = evaluate(base, vd, nboot=300, boot_seed=5)
    # (e) staircase start 40 uA
    t = time.time(); ve = simulate_variant(6, stair_start=40.0, do_psi=False); timing["e_start40"] = time.time() - t
    variants["e_stair_start_40uA"] = evaluate(base, ve, nboot=300, boot_seed=6)
    print("d,e done", flush=True)

    # abandonment (lapse): psi fails bias in > half of lam=0.10 cells -> one follow-up with free lapse
    followup = None
    if main_eval["n_bias_fail_lam_0p10"] > 6:
        t = time.time()
        gf = make_grid(np.linspace(0, 0.1, 4))
        vf = simulate_variant(7, psi_lams=np.linspace(0, 0.1, 4), do_stair=False, g=gf)
        timing["followup_free_lapse"] = time.time() - t
        followup = evaluate(vf, base, nboot=300, boot_seed=7)
        followup["note"] = "free lapse grid {0,0.033,0.067,0.1}; staircase from main run"
        print("follow-up done", flush=True)

    out = dict(prereg="prereg/P3_psi_vs_staircase_calibration.md", seed=SEED, nruns=NRUNS, budgets=BUDGETS,
               selftest=st, main=main_eval,
               control_check=dict(n_cells_ctrl_within_10pct_of_psi=int(n_within),
                                  abandonment_triggered=bool(abandon_ctrl),
                                  rule="N_req(ctrl) <= 1.10*N_req(psi); both >150 counts as within"),
               minutes_per_64_electrode_array_at_4s_per_trial=mins,
               sensitivity={k: {kk: v[kk] for kk in v if kk != "cells"} | {"cells_compact": [
                   dict(theta75=r["theta75"], beta=r["beta"], lam=r["lam"], N_req_psi=r["N_req_psi"],
                        N_req_stair=r["N_req_stair"], savings=r["savings"], bias60_psi=r["bias60_psi"])
                   for r in v["cells"]]} for k, v in variants.items()},
               lapse_followup=followup, timing_s=timing, runtime_s=time.time() - t0)
    with open(os.path.join(RES, "p3_psi_staircase.json"), "w") as f:
        json.dump(jsonable(out), f, indent=1)
    figures(main_eval, base, variants)
    print(json.dumps(jsonable(dict(verdict=main_eval["verdict"], n_sav=main_eval["n_savings_cells"],
                                   ci=main_eval["n_savings_ci95"], bias_ok=main_eval["bias_ok_all_lam_le_0p05"],
                                   bias_fail_lam10=main_eval["n_bias_fail_lam_0p10"],
                                   ctrl=out["control_check"], minutes=mins,
                                   variants={k: (v["verdict"], v["n_savings_cells"], v["n_bias_fail_lam_le_0p05"]) for k, v in variants.items()},
                                   followup=None if followup is None else (followup["verdict"], followup["n_savings_cells"], followup["n_bias_fail_lam_0p10"]),
                                   runtime=out["runtime_s"])), indent=1))


if __name__ == "__main__":
    main()
