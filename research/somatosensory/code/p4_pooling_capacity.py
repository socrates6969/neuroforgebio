"""P4: channel capacity of amplitude-coded ICMS and the limit of multi-electrode pooling (H2).

Implements prereg\\P4_pooling_capacity.md (FIXED). Theory + simulation on published summary numbers
(Greenspon 2025, PMC12176618, as transcribed in the prereg). Interpretations logged in code\\DEVIATIONS.md (P4).

Run:  python p4_pooling_capacity.py            (self-tests + full run)
      python p4_pooling_capacity.py --selftest
"""
import json
import os
import sys
import time

import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm

BASE = r"C:\Users\mariu\neuro-company\research\somatosensory\code"
RES = os.path.join(BASE, "results")
FIG = os.path.join(BASE, "figures")
SEED = 20260926

N1 = 11.0            # biomimetic single-electrode levels (Greenspon Fig 7e)
N4_OBS = 19.5        # biomimetic quartet levels
N_NAT = 47.5         # natural touch levels (45-50)
W_LIST = [0.128, 0.162, 0.225, 0.268]
W0 = 0.162
KAPPAS = [0.0, 0.25, 0.5]
M_LIST = [1, 2, 4, 8, 16, 32, 64, 256, 1024]
T_SYM = [0.1, 0.2, 0.5, 1.0]
K_LIST = [1, 2, 4, 8, 16]
E_TOT = 64
QMAX_E = 100.0
QTHR_K = [20.0, 24.0, 35.0]
A_BAND = (0.8 * N4_OBS, 1.2 * N4_OBS)   # [15.6, 23.4]
Z75 = norm.ppf(0.75)                     # 0.6745


def s_of_w(w):
    return np.log1p(w) / (Z75 * np.sqrt(2))


def n_levels(M, w, kappa, n1=N1):
    return n1 + (1 - kappa) * np.log(M) / np.log1p(w)


def m_star(w, kappa, n1=N1):
    return np.exp((N_NAT - n1) * np.log1p(w) / (1 - kappa))


def kappa_hat(w, n1=N1, n4=N4_OBS):
    return 1 - (n4 - n1) * np.log1p(w) / np.log(4)


def model_k_n(M, qthr, n1=N1, qmax_e=QMAX_E, jnd_qmax_e=QMAX_E):
    """constant-absolute-JND pooling. JND_Q is fixed by N(1)=n1 at the baseline cap jnd_qmax_e."""
    jnd = (jnd_qmax_e - qthr) / n1
    return (qmax_e * M - qthr) / jnd


# ----------------------------------------------------------------------------- Blahut-Arimoto
def channel_matrix(xmin, xmax, s_fun, nx=400, ny=800):
    """input grid nx points on [xmin,xmax]; output grid ny points over [xmin-5s, xmax+5s];
    s_fun(x) -> noise sd (constant or x-dependent). Bin probabilities from CDF differences, open-ended edge bins."""
    x = np.linspace(xmin, xmax, nx)
    sx = np.broadcast_to(np.asarray(s_fun(x), float), x.shape)
    lo, hi = xmin - 5 * sx[0], xmax + 5 * sx[-1]
    y = np.linspace(lo, hi, ny)
    edges = np.concatenate([[-np.inf], 0.5 * (y[1:] + y[:-1]), [np.inf]])
    cdf = norm.cdf((edges[None, :] - x[:, None]) / sx[:, None])
    P = np.diff(cdf, axis=1)
    P /= P.sum(1, keepdims=True)
    return x, P


def blahut_arimoto(P, tol_bits=1e-6, stall_bits=1e-9, maxit=500_000):
    """Stops when the certified gap (upper - lower bound) < tol_bits, OR when the lower bound improves by
    < stall_bits per iteration (the gap then certifies the remaining error; see DEVIATIONS.md P4)."""
    nx = P.shape[0]
    r = np.full(nx, 1.0 / nx)
    with np.errstate(divide="ignore"):
        logP = np.where(P > 0, np.log(np.where(P > 0, P, 1.0)), 0.0)
    PlogP = (P * logP).sum(1)
    prev = -np.inf
    for it in range(maxit):
        q = r @ P
        with np.errstate(divide="ignore"):
            logq = np.log(np.where(q > 0, q, 1e-300))
        D = PlogP - P @ logq            # KL(P(.|x) || q) in nats
        c = np.exp(D - D.max())
        rc = r @ c
        IL = np.log(rc) + D.max()
        IU = D.max()
        if (IU - IL) / np.log(2) < tol_bits or (IL - prev) / np.log(2) < stall_bits:
            break
        prev = IL
        r = r * c / rc
    return dict(C=float(IL / np.log(2)), C_upper=float(IU / np.log(2)), iters=it + 1, r=r)


_cache = {}


def capacity_const(range_ln, s):
    """capacity (bits/symbol) of y = x + N(0,s^2), x in an interval of length range_ln (scale-invariant -> cache on ratio)"""
    key = round(range_ln / s, 10)
    if key not in _cache:
        _, P = channel_matrix(0.0, range_ln, lambda x: s)
        _cache[key] = blahut_arimoto(P)
    return _cache[key]


def capacity_M(M, w, kappa, n1=N1):
    n = n_levels(M, w, kappa, n1)
    if n <= 0:
        return dict(C=0.0, C_upper=0.0, iters=0)
    return capacity_const(n * np.log1p(w), s_of_w(w))


# ----------------------------------------------------------------------------- Weber-violation variant
def wq_fun(w0, expo):
    return lambda Q: w0 * (Q / 60.0) ** expo


def n_integral(qlo, qhi, wf, npts=4000):
    """continuous level count: integral of dlnQ / ln(1+w(Q))"""
    lq = np.linspace(np.log(qlo), np.log(qhi), npts)
    f = 1.0 / np.log1p(wf(np.exp(lq)))
    return float(np.trapezoid(f, lq)) if hasattr(np, "trapezoid") else float(np.trapz(f, lq))


def weber_violation(w0, expo, qmax_e=QMAX_E):
    wf = wq_fun(w0, expo)
    athr = brentq(lambda a: n_integral(a, qmax_e, wf) - N1, 1e-3, qmax_e * 0.999)
    NM = lambda M, k: n_integral(athr * M ** k, qmax_e * M, wf)
    n4_0, n4_1 = NM(4, 0.0), NM(4, 1.0)
    kh = brentq(lambda k: NM(4, k) - N4_OBS, -2, 1.0) if (NM(4, -2) - N4_OBS) * (NM(4, 1.0) - N4_OBS) < 0 else None
    try:
        ms = brentq(lambda lm: NM(np.exp(lm), 0.0) - N_NAT, 0.0, 60.0)
        ms = float(np.exp(ms))
    except ValueError:
        ms = None
    # heteroscedastic capacity for M=1, 64 (kappa=0); s depends on the input x = ln Q
    caps = {}
    for M in (1, 64):
        xlo, xhi = np.log(athr), np.log(qmax_e * M)
        _, P = channel_matrix(xlo, xhi, lambda x: s_of_w(wf(np.exp(x))))
        caps[M] = blahut_arimoto(P)["C"]
    return dict(w0=w0, exponent=expo, A_thr_uA=athr, N4_kappa0=n4_0, N4_kappa1=n4_1, kappa_hat=kh, M_star_kappa0=ms,
                C1=caps[1], C64=caps[64], dC_64_1=caps[64] - caps[1])


# ----------------------------------------------------------------------------- parts
def part_a(n1=N1, qmax_e=QMAX_E):
    rows = {}
    for w in W_LIST:
        athr = QMAX_E / (1 + w) ** N1           # threshold implied by N(1)=11 at the baseline 100 uA cap
        if qmax_e == QMAX_E:
            n1_eff = n1
        else:                                    # cap sensitivity: hold A_thr fixed, N(1) changes
            n1_eff = np.log(qmax_e / athr) / np.log1p(w)
        rows[w] = dict(kappa_hat=kappa_hat(w, n1_eff), N4_kappa0=n_levels(4, w, 0.0, n1_eff),
                       N4_kappa1=n_levels(4, w, 1.0, n1_eff), N1_eff=n1_eff, A_thr_implied_uA=athr)
    K = {q: model_k_n(4, q, n1=n1, qmax_e=qmax_e) for q in QTHR_K}
    r = rows[W0]
    inb = lambda v: A_BAND[0] <= v <= A_BAND[1]
    checks = dict(kappa0_in_band=inb(r["N4_kappa0"]), kappa1_outside=not inb(r["N4_kappa1"]),
                  kappa_hat_in_0_0p3=0 <= r["kappa_hat"] <= 0.3, modelK_all_outside=all(not inb(v) for v in K.values()))
    verdict = "PASS" if all(checks.values()) else "FAIL"
    k_fits = any(inb(v) for v in K.values())
    note = "pooling gain is linear (model K fits, Weber fails)" if (k_fits and not checks["kappa0_in_band"]) else ""
    return dict(verdict=verdict, checks=checks, per_w=rows, modelK_N4=K, band=A_BAND, note=note)


def part_b(n1=N1):
    tab = {}
    for kappa in KAPPAS:
        for w in W_LIST:
            for M in M_LIST:
                c = capacity_M(M, w, kappa, n1)
                n = n_levels(M, w, kappa, n1)
                tab[(kappa, w, M)] = dict(N=n, log2N=float(np.log2(n)) if n > 0 else None, C=c["C"], C_upper=c["C_upper"],
                                          BA_iters=c["iters"], bits_per_s={str(T): c["C"] / T for T in T_SYM})
    mstar = {(kappa, w): float(m_star(w, kappa, n1)) for kappa in KAPPAS for w in W_LIST}
    # K independent channels of 64/K electrodes
    split = {}
    for kappa in KAPPAS:
        for w in W_LIST:
            row = {}
            for K in K_LIST:
                m = E_TOT // K
                n = n_levels(m, w, kappa, n1)
                row[K] = K * tab[(kappa, w, m)]["C"] if n >= 2 else 0.0
            split[(kappa, w)] = row
    dC = tab[(0.0, W0, 64)]["C"] - tab[(0.0, W0, 1)]["C"]
    checks = dict(Mstar_gt_64_all_w_kappa0=all(mstar[(0.0, w)] > 64 for w in W_LIST), dC_64_1_lt_2bits=dC < 2.0)
    return dict(verdict="PASS" if all(checks.values()) else "FAIL", checks=checks, dC_64_minus_1_w0162_k0=dC,
                table=tab, M_star=mstar, split_64=split)


def part_c(rng, ntr=20000):
    w = W0
    s = s_of_w(w)
    athr = QMAX_E / (1 + w) ** N1
    out = {}
    for M in (1, 4, 16):
        qthr, qmax = athr, QMAX_E * M           # kappa = 0 (full summation), the model under test
        stds = np.exp(np.linspace(np.log(qthr), np.log(qmax), 5))
        deltas = np.log1p(w) * np.array([0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5])  # ln-intensity increments
        jnd_w, pcs = [], []
        for Q0 in stds:
            pc = []
            for d in deltas:
                Q1 = Q0 * np.exp(d)
                a0 = np.full((ntr, M), Q0 / M)            # equal split across the M pooled electrodes
                a1 = np.full((ntr, M), Q1 / M)
                y0 = np.log(a0.sum(1)) + s * rng.standard_normal(ntr)
                y1 = np.log(a1.sum(1)) + s * rng.standard_normal(ntr)
                corr = (y1 > y0) | ((y1 == y0) & (rng.random(ntr) < 0.5))
                pc.append(corr.mean())
            pc = np.array(pc)
            pcs.append(pc.tolist())
            # nonparametric: first crossing of 0.75, linear interpolation (0.5 at delta=0 prepended)
            dd = np.concatenate([[0.0], deltas]); pp = np.concatenate([[0.5], pc])
            i = np.nonzero(pp >= 0.75)[0][0]
            d75 = dd[i - 1] + (0.75 - pp[i - 1]) / (pp[i] - pp[i - 1]) * (dd[i] - dd[i - 1])
            jnd_w.append(np.expm1(d75))
        jnd_w = np.array(jnd_w)
        lstd = np.log(stds)
        wfun = lambda Q: np.interp(np.log(Q), lstd, jnd_w)
        Q, cnt = qthr, 0
        while Q * (1 + wfun(Q)) <= qmax:
            Q *= 1 + wfun(Q)
            cnt += 1
        frac = cnt + np.log(qmax / Q) / np.log1p(wfun(Q))
        an = n_levels(M, w, 0.0)
        out[M] = dict(standards_uA=stds.tolist(), measured_w=jnd_w.tolist(), pc_curves=pcs, count_int=cnt,
                      count_frac=float(frac), analytic=float(an), rel_err_int=(cnt - an) / an, rel_err_frac=(frac - an) / an)
    ok = all(abs(v["rel_err_int"]) <= 0.10 for v in out.values())
    return dict(verdict="PASS" if ok else "FAIL", per_M=out, criterion="integer step count within 10% of analytic N(M)")


def ba_sanity():
    s = 1.0
    res = []
    for rng_ in (30.0, 60.0):
        c = capacity_const(rng_, s)["C"]
        lo = np.log2(rng_ / (s * np.sqrt(2 * np.pi * np.e))) - 0.2
        hi = 0.5 * np.log2(1 + rng_ ** 2 / (4 * s ** 2))
        res.append(dict(range_over_s=rng_, C=c, lower=lo, upper=hi, ok=bool(lo <= c <= hi)))
    return res


def selftest():
    r = {}
    # worked numbers from prereg/theories
    r["N4_kappa0_w0162"] = n_levels(4, 0.162, 0.0)
    assert round(r["N4_kappa0_w0162"], 1) == 20.2
    r["M_star_range_kappa0"] = [m_star(0.128, 0), m_star(0.268, 0)]
    assert 78 <= r["M_star_range_kappa0"][0] <= 84 and 5000 <= r["M_star_range_kappa0"][1] <= 6500  # "81 to ~5800"
    r["w_from_JND"] = [9.7 / 60, 7.7 / 60, 16.1 / 60, 13.5 / 60]
    assert np.allclose(r["w_from_JND"], [0.162, 0.128, 0.268, 0.225], atol=6e-4)
    # s conversion: 2AFC P(correct) at delta = ln(1+w) must be 0.75
    r["pc_at_jnd"] = float(norm.cdf(np.log1p(0.162) / (s_of_w(0.162) * np.sqrt(2))))
    assert abs(r["pc_at_jnd"] - 0.75) < 1e-12
    # BA on a binary symmetric channel p=0.1: C = 1 - H(0.1) = 0.531
    P = np.array([[0.9, 0.1], [0.1, 0.9]])
    c = blahut_arimoto(P)["C"]
    r["BA_BSC_0p1"] = c
    assert abs(c - (1 + 0.1 * np.log2(0.1) + 0.9 * np.log2(0.9))) < 1e-5
    r["BA_gaussian_bounds"] = ba_sanity()
    assert all(x["ok"] for x in r["BA_gaussian_bounds"])
    r["all_passed"] = True
    return r


def jsonable(o):
    if isinstance(o, dict):
        return {(str(k) if not isinstance(k, tuple) else "|".join(f"{x:g}" if isinstance(x, float) else str(x) for x in k)): jsonable(v)
                for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, np.ndarray):
        return jsonable(o.tolist())
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def figures(A, B, extras):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 3, figsize=(16, 5))
    ax = axs[0]
    for kappa, ls in zip(KAPPAS, ["-", "--", ":"]):
        for w, col in zip(W_LIST, ["C0", "C1", "C2", "C3"]):
            Cs = [B["table"][(kappa, w, M)]["C"] for M in M_LIST]
            ax.plot(M_LIST, Cs, ls, color=col, marker="o", ms=3, label=f"w={w}, kappa={kappa}" if True else None)
    ax.plot(M_LIST, [B["table"][(0.0, W0, M)]["log2N"] for M in M_LIST], "k-.", lw=1, label="log2 N(M), w=0.162, kappa=0")
    ax.axhline(np.log2(N_NAT), color="gray", lw=0.8, label="log2 47.5 (natural levels)")
    ax.set_xscale("log", base=2)
    ax.set_xlabel("pooled electrodes M")
    ax.set_ylabel("capacity C(M) (bits/symbol, Blahut-Arimoto)")
    ax.set_title("Capacity of one pooled amplitude channel")
    ax.legend(fontsize=6, ncol=2)
    ax = axs[1]
    Ms = np.geomspace(1, 1e4, 200)
    for w, col in zip(W_LIST, ["C0", "C1", "C2", "C3"]):
        ax.plot(Ms, n_levels(Ms, w, 0.0), color=col, label=f"Weber pooling kappa=0, w={w}")
    ax.plot(Ms, n_levels(Ms, W0, 1.0), "k:", label="no summation kappa=1")
    for q in QTHR_K:
        ax.plot([1, 4, 16], [model_k_n(m, q) for m in (1, 4, 16)], "x--", color="gray", lw=0.8)
    ax.plot([], [], "x--", color="gray", label="constant-JND model K (Q_thr 20/24/35)")
    ax.plot([1, 4], [N1, N4_OBS], "r*", ms=12, label="Greenspon 2025 (11, 19.5)")
    ax.axhline(N_NAT, color="gray", lw=0.8)
    ax.axvline(64, color="gray", lw=0.8, ls="--")
    ax.text(70, 5, "64", fontsize=8)
    ax.set_xscale("log")
    ax.set_ylim(0, 80)
    ax.set_xlabel("pooled electrodes M")
    ax.set_ylabel("discriminable levels N(M)")
    ax.set_title(f"Part A: {A['verdict']}; natural levels 47.5 need M* > 64")
    ax.legend(fontsize=6)
    ax = axs[2]
    for kappa, ls in zip(KAPPAS, ["-", "--", ":"]):
        for w, col in zip(W_LIST, ["C0", "C1", "C2", "C3"]):
            ax.plot(K_LIST, [B["split_64"][(kappa, w)][K] for K in K_LIST], ls, color=col, marker="o", ms=3)
    ax.set_xscale("log", base=2)
    ax.set_xlabel("independent channels K (64/K electrodes each)")
    ax.set_ylabel("total capacity K*C(64/K) (bits/symbol)")
    ax.set_title("Pooling (K=1) vs independent spatial channels\n(independence ASSUMED; line styles as left panel)")
    fig.suptitle(f"P4 pooling capacity  |  A {A['verdict']}  B {B['verdict']}  C {extras['C']['verdict']}")
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(os.path.join(FIG, f"p4_capacity_vs_M.{ext}"), dpi=150)
    plt.close(fig)


def main():
    t0 = time.time()
    st = selftest()
    print("self-tests passed:", json.dumps(jsonable(st)))
    if "--selftest" in sys.argv:
        return
    rng = np.random.default_rng(SEED)
    A = part_a()
    B = part_b()
    print("B done", time.time() - t0, flush=True)
    C = part_c(rng)
    sens = {}
    for n1 in (7.0, 14.0):
        a, b = part_a(n1=n1), part_b(n1=n1)
        sens[f"N1={n1:g}"] = dict(A=a["verdict"], A_checks=a["checks"], A_per_w=a["per_w"], A_modelK=a["modelK_N4"],
                                  B=b["verdict"], B_checks=b["checks"], dC=b["dC_64_minus_1_w0162_k0"],
                                  M_star_k0={w: b["M_star"][(0.0, w)] for w in W_LIST})
    a80 = part_a(qmax_e=80.0)
    # B at 80 uA cap: A_thr held at the baseline-implied value -> N(1) drops
    n1_80 = {w: a80["per_w"][w]["N1_eff"] for w in W_LIST}
    mstar80 = {w: float(m_star(w, 0.0, n1_80[w])) for w in W_LIST}
    dC80 = capacity_M(64, W0, 0.0, n1_80[W0])["C"] - capacity_M(1, W0, 0.0, n1_80[W0])["C"]
    sens["Qmax=80uA"] = dict(A=a80["verdict"], A_checks=a80["checks"], A_per_w=a80["per_w"], A_modelK=a80["modelK_N4"],
                             M_star_k0=mstar80, dC=dC80,
                             B="PASS" if (all(v > 64 for v in mstar80.values()) and dC80 < 2) else "FAIL")
    wv = {}
    for expo in (-0.2, 0.2):
        rows = [weber_violation(w, expo) for w in W_LIST]
        r0 = rows[W_LIST.index(W0)]
        inb = lambda v: A_BAND[0] <= v <= A_BAND[1]
        a_ok = inb(r0["N4_kappa0"]) and not inb(r0["N4_kappa1"]) and r0["kappa_hat"] is not None and 0 <= r0["kappa_hat"] <= 0.3
        b_ok = all((r["M_star_kappa0"] is None) or r["M_star_kappa0"] > 64 for r in rows) and r0["dC_64_1"] < 2
        wv[f"w(Q)=w0*(Q/60)^{expo:+g}"] = dict(rows=rows, A=("PASS" if a_ok else "FAIL") + " (model K unchanged, outside band)",
                                              B="PASS" if b_ok else "FAIL")
    sens["weber_violation"] = wv
    # frequency as an extra independent channel: w = 0.15 over 20-50 Hz (log-frequency channel, same noise model)
    wf = 0.15
    cf = capacity_const(np.log(50 / 20), s_of_w(wf))["C"]
    sens["frequency_channel"] = dict(w=wf, range_Hz=[20, 50], levels=float(np.log(2.5) / np.log1p(wf)), added_bits=cf,
                                     C64_pooled_plus_freq=B["table"][(0.0, W0, 64)]["C"] + cf)
    out = dict(prereg="prereg/P4_pooling_capacity.md", seed=SEED, selftest=st, A=A, B=B, C=C,
               BA_sanity=st["BA_gaussian_bounds"], sensitivity=sens, runtime_s=time.time() - t0)
    with open(os.path.join(RES, "p4_pooling_capacity.json"), "w") as f:
        json.dump(jsonable(out), f, indent=1)
    figures(A, B, dict(C=C))
    summ = dict(A=A["verdict"], A_checks=A["checks"], kappa_hat={w: A["per_w"][w]["kappa_hat"] for w in W_LIST},
                N4_k0={w: A["per_w"][w]["N4_kappa0"] for w in W_LIST}, modelK=A["modelK_N4"],
                B=B["verdict"], dC=B["dC_64_minus_1_w0162_k0"], Mstar_k0={w: B["M_star"][(0.0, w)] for w in W_LIST},
                C1=B["table"][(0.0, W0, 1)]["C"], C64=B["table"][(0.0, W0, 64)]["C"],
                split_k0_w0162=B["split_64"][(0.0, W0)],
                C=C["verdict"], C_counts={M: (v["count_int"], round(v["count_frac"], 2), round(v["analytic"], 2)) for M, v in C["per_M"].items()},
                sens={k: (v.get("A"), v.get("B")) if isinstance(v, dict) and "A" in v else v for k, v in sens.items()},
                runtime=out["runtime_s"])
    print(json.dumps(jsonable(summ), indent=1))


if __name__ == "__main__":
    main()
