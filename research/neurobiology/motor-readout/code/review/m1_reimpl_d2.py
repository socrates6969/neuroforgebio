r"""Independent reviewer re-implementation of M1 D2 ridge drift (H4) and recalibration (H5: R-a, R-b).

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. Reviewer check; does not import m1lib or run_m1.
From the prereg text: 20 -> 32 ms re-binning (area-preserving, via a 4 ms common grid), per-session chronological
60/20/20 trial split with 1-trial gaps, z-score on calib, ridge with H = 6 lags (lambda by val R^2),
R^2_fixed / R^2_within / rho, R-a (day-k calib re-z-score), R-b (FA 10 factors EM 200 it, Procrustes to day 0,
day-0 latent ridge H = 6). Also: time-order checks and a mean-shift diagnostic for the negative R^2_fixed.
Output: review\m1_reimpl_d2_out.json
"""
import ctypes
import json
import os
import time
from ctypes import wintypes

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
import h5py  # noqa: E402
import numpy as np  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402

ROOT = r"C:\Users\mariu\neuro-company\research\neurobiology\motor-readout"
OUT = os.path.join(ROOT, "code", "review", "m1_reimpl_d2_out.json")
SES = [("20200127", 0), ("20200130", 3), ("20200204", 8), ("20200211", 15), ("20200228", 32), ("20200626", 151),
       ("20200924", 241), ("20210223", 393), ("20220126", 730)]
LAMS = np.logspace(-1, 5, 13)
T0 = time.time()


def peak_mb():
    class PMC(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t), ("a", ctypes.c_size_t), ("b", ctypes.c_size_t),
                    ("c", ctypes.c_size_t), ("d", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t)]
    p = PMC()
    p.cb = ctypes.sizeof(p)
    k32 = ctypes.WinDLL("kernel32")
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    k32.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
    k32.K32GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(p), p.cb)
    return p.PeakWorkingSetSize / 2 ** 20


def log(*a):
    print("%6.1fs" % (time.time() - T0), *a, flush=True)


def rebin(x):
    """20 ms -> 32 ms: each 20 ms sample spread over five 4 ms sub-bins, then 8 sub-bins averaged."""
    fine = np.repeat(x, 5, axis=0)
    n = fine.shape[0] // 8
    return fine[:n * 8].reshape(n, 8, *x.shape[1:]).mean(1)


def r2vw(y, p):
    return float(1 - ((y - p) ** 2).sum() / ((y - y.mean(0)) ** 2).sum())


def lag(Z, H=6):
    T, N = Z.shape
    out = np.zeros((T, N * H))
    for k in range(H):
        out[k:, k * N:(k + 1) * N] = Z[:T - k]
    return out


def ridge_select(Xtr, Ytr, Xva, Yva):
    xm, ym = Xtr.mean(0), Ytr.mean(0)
    Xc = Xtr - xm
    e, Q = np.linalg.eigh(Xc.T @ Xc)
    b = Q.T @ (Xc.T @ (Ytr - ym))
    best = None
    for lam in LAMS:
        W = Q @ (b / (e + lam)[:, None])
        s = r2vw(Yva, Xva @ W + (ym - xm @ W))
        if best is None or s > best[0]:
            best = (s, lam, W, ym - xm @ W)
    return best


def fa_em(X, k=10, iters=200):
    """Classic FA EM (Rubin & Thayer 1982). Returns mu, L, Psi."""
    mu = X.mean(0)
    Xc = X - mu
    S = Xc.T @ Xc / len(X)
    ev, V = np.linalg.eigh(S)
    ev, V = ev[::-1], V[:, ::-1]
    L = V[:, :k] * np.sqrt(np.maximum(ev[:k] - ev[k:].mean(), 1e-9))
    Psi = np.maximum(np.diag(S) - (L ** 2).sum(1), 1e-6 * np.diag(S).mean())
    for _ in range(iters):
        # E-step: beta = L'(LL' + Psi)^-1 via Woodbury
        LtPi = L.T / Psi
        G = np.linalg.inv(np.eye(k) + LtPi @ L)
        beta = G @ LtPi
        Ezz = np.eye(k) - beta @ L + beta @ S @ beta.T
        L = (S @ beta.T) @ np.linalg.inv(Ezz)
        Psi = np.maximum(np.diag(S - L @ beta @ S), 1e-6 * np.diag(S).mean())
    LtPi = L.T / Psi
    beta = np.linalg.inv(np.eye(k) + LtPi @ L) @ LtPi
    return mu, L, beta


def session(date):
    p = os.path.join(ROOT, "data", "raw", "001201", "sub-Monkey-N_ses-%s_ecephys.nwb" % date)
    with h5py.File(p, "r") as f:
        x = f["analysis/SpikingBandPower/data"][:]
        ts = f["analysis/SpikingBandPower/timestamps"][:]
        v = np.column_stack([f["analysis/index_velocity/data"][:, 0], f["analysis/mrs_velocity/data"][:, 0]])
        t = f["intervals/trials"]
        st, sp = t["start_time"][:], t["stop_time"][:]
        style = sorted(set(s.decode() if isinstance(s, bytes) else str(s) for s in t["target_style"][:]))
    X, Y = rebin(x), rebin(v)
    cen = ts[0] + (np.arange(len(X)) + 0.5) * 0.032
    o = np.argsort(st, kind="stable")
    n = len(o)
    c1, c2 = int(round(0.6 * n)), int(round(0.8 * n))
    blocks = dict(calib=o[:c1], val=o[c1 + 1:c2], test=o[c2 + 1:])
    assert sp[blocks["calib"]].max() < st[blocks["val"]].min() and sp[blocks["val"]].max() < st[blocks["test"]].min()
    lab = np.full(len(X), "", dtype="<U5")
    for name, idx in blocks.items():
        for i in idx:
            lab[(cen >= st[i]) & (cen < sp[i] + 0.020)] = name
    # time-order check on bins
    order_ok = bool(np.flatnonzero(lab == "calib").max() < np.flatnonzero(lab == "val").min() <
                    np.flatnonzero(lab == "val").max() < np.flatnonzero(lab == "test").min())
    return dict(X=X, Y=Y, lab=lab, style=style, order_ok=order_ok, n_trials=n,
                dt_med=float(np.median(np.diff(ts))))


res = dict(sessions={})
S = {}
for d, lg in SES:
    S[d] = session(d)
    log("loaded", d, S[d]["X"].shape, S[d]["style"], "order_ok", S[d]["order_ok"], "dt", S[d]["dt_med"])


def zfit(s):
    c = s["X"][s["lab"] == "calib"]
    return c.mean(0), np.maximum(c.std(0), 1e-8)


def fit_day(s, zs):
    L = lag((s["X"] - zs[0]) / zs[1])
    cal, val = s["lab"] == "calib", s["lab"] == "val"
    return ridge_select(L[cal], s["Y"][cal], L[val], s["Y"][val])


def predict(model, s, zs, rows):
    L = lag((s["X"] - zs[0]) / zs[1])
    return L[rows] @ model[2] + model[3]


d0 = SES[0][0]
zs0 = zfit(S[d0])
M0 = fit_day(S[d0], zs0)
res["day0"] = dict(lambda_=float(M0[1]), val_r2=float(M0[0]))
S0 = S[d0]
sd0 = np.maximum(S0["X"][S0["lab"] == "calib"].std(0), 1e-12)
mu0, L0, beta0 = fa_em(S0["X"][S0["lab"] == "calib"] / sd0)
lat0 = lag((S0["X"] / sd0 - mu0) @ beta0.T)
c0, v0 = S0["lab"] == "calib", S0["lab"] == "val"
FR = ridge_select(lat0[c0], S0["Y"][c0], lat0[v0], S0["Y"][v0])
log("day0", res["day0"], "FA ridge lam", FR[1])
for d, lg in SES:
    s = S[d]
    te = s["lab"] == "test"
    y = s["Y"][te]
    zk = zfit(s)
    Mk = M0 if d == d0 else fit_day(s, zk)
    fx = r2vw(y, predict(M0, s, zs0, te))
    wi = r2vw(y, predict(Mk, s, zk, te))
    ra = r2vw(y, predict(M0, s, zk, te))
    if d == d0:
        muk, Lk, betak = mu0, L0, beta0
    else:
        muk, Lk, betak = fa_em(s["X"][s["lab"] == "calib"] / sd0)
    U, _, Vt = np.linalg.svd(Lk.T @ L0)
    O = U @ Vt
    latk = lag(((s["X"] / sd0 - muk) @ betak.T) @ O)
    rb = r2vw(y, latk[te] @ FR[2] + FR[3])
    # mean-shift diagnostic: day-k calib mean of day-0-z-scored SBP (in day-0 SD units), averaged |.| over channels
    zshift = float(np.abs(((s["X"][s["lab"] == "calib"] - zs0[0]) / zs0[1]).mean(0)).mean())
    # bias part of the fixed decoder's error: squared mean error / total MSE
    pf = predict(M0, s, zs0, te)
    mse = ((y - pf) ** 2).mean(0).sum()
    bias2 = ((y - pf).mean(0) ** 2).sum()
    e = dict(lag=lg, style=s["style"], r2_within=wi, r2_fixed=fx, r2_Ra=ra, r2_Rb=rb,
             rho=fx / wi if wi >= 0.10 else None,
             phi_Rb=(rb - fx) / (wi - fx) if lg > 0 else None, phi_Ra=(ra - fx) / (wi - fx) if lg > 0 else None,
             mean_abs_z_shift_day0_units=zshift, fixed_bias2_fraction_of_mse=float(bias2 / mse),
             n_test_bins=int(te.sum()), order_ok=s["order_ok"])
    res["sessions"][d] = e
    log(d, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in e.items()})
late = [d for d, lg in SES if lg >= 30 and res["sessions"][d]["rho"] is not None]
later8 = [d for d, lg in SES if lg > 0]
res["H4"] = dict(median_rho=float(np.median([res["sessions"][d]["rho"] for d in late])),
                 spearman=float(spearmanr([res["sessions"][d]["lag"] for d in later8],
                                          [res["sessions"][d]["r2_fixed"] for d in later8])[0]), usable_late=late)
res["H5"] = dict(median_phi_Rb=float(np.median([res["sessions"][d]["phi_Rb"] for d in late])),
                 median_phi_Ra=float(np.median([res["sessions"][d]["phi_Ra"] for d in late])))
res["wall_s"] = time.time() - T0
res["peak_ws_mb"] = peak_mb()
json.dump(res, open(OUT, "w"), indent=1, default=float)
log("H4", res["H4"], "H5", res["H5"], "peak MB", res["peak_ws_mb"])
