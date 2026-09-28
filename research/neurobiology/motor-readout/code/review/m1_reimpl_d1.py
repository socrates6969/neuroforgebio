r"""Independent reviewer re-implementation of M1 D1 (prereg M1_decoder_comparison.md, SHA 9eada9d7...).

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. Reviewer check; does not import m1lib or run_m1.
Re-implements from the prereg text: split, binning, z-scoring, ridge (H = 10, lambda by val R^2), velocity KF,
M-R2 (variance-weighted), rho^2, M-BITS (Hann, coherence, f <= 10 Hz, 200-derangement null, I_net).
Plus diagnostics: KF variants (lag, diagonal R, bin), memoryless ridge, sign-flip bits invariance, NC1 shuffled ridge
over several permutations, PL-1 analytic power and empirical rise over noise seeds.
Output: review\m1_reimpl_d1_out.json
"""
import json
import os
import sys
import time

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
import ctypes  # noqa: E402
from ctypes import wintypes  # noqa: E402
import h5py  # noqa: E402
import numpy as np  # noqa: E402

ROOT = r"C:\Users\mariu\neuro-company\research\neurobiology\motor-readout"
F = os.path.join(ROOT, "data", "raw", "000138", "sub-Jenkins_ses-large_desc-train_behavior+ecephys.nwb")
OUT = os.path.join(ROOT, "code", "review", "m1_reimpl_d1_out.json")
T0 = time.time()
R = np.random.default_rng(777)          # reviewer RNG (different from the run's streams)


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


# ------------------------------------------------------------------ load
with h5py.File(F, "r") as f:
    tr = f["intervals/trials"]
    start, stop = tr["start_time"][:], tr["stop_time"][:]
    onset = tr["move_onset_time"][:]
    maze = tr["maze_id"][:]
    ttype, tver = tr["trial_type"][:], tr["trial_version"][:]
    st = f["units/spike_times"][:]
    si = f["units/spike_times_index"][:].astype(np.int64)
    vts = f["processing/behavior/hand_vel/timestamps"][:]
    vel = f["processing/behavior/hand_vel/data"][:]
n_tr, n_u = len(start), len(si)
units = np.split(st, si[:-1])
log("trials", n_tr, "units", n_u, "mazes", len(np.unique(maze)), "type x version conditions",
    len(set(zip(ttype.tolist(), tver.tolist()))))

# ------------------------------------------------------------------ split (prereg §2: sort by start, 60/20/20, 1-trial gaps)
o = np.argsort(start, kind="stable")
c1, c2 = int(round(0.6 * n_tr)), int(round(0.8 * n_tr))
TR, VA, TE = o[:c1], o[c1 + 1:c2], o[c2 + 1:]
assert stop[TR].max() < start[VA].min() and stop[VA].max() < start[TE].min()
log("split", len(TR), len(VA), len(TE))


def grid(bin_ms, pre_ms, nb, shift_ms=0.0):
    e = onset[:, None] + (shift_ms + pre_ms + bin_ms * np.arange(nb + 1))[None, :] / 1000.0
    C = np.zeros((n_tr, nb, n_u))
    for u, s in enumerate(units):
        s = np.sort(s)
        C[:, :, u] = np.diff(np.searchsorted(s, e.ravel()).reshape(e.shape), axis=1)
    cs = np.vstack([np.zeros((1, 2)), np.cumsum(vel, 0)])
    k = np.searchsorted(vts, e.ravel()).reshape(e.shape)
    V = (cs[k[:, 1:]] - cs[k[:, :-1]]) / np.diff(k, axis=1)[..., None]
    return C, V


def r2vw(y, p):
    y, p = y.reshape(-1, y.shape[-1]), p.reshape(-1, p.shape[-1])
    return float(1 - ((y - p) ** 2).sum() / ((y - y.mean(0)) ** 2).sum())


def rho2(y, p):
    y, p = y.reshape(-1, 2), p.reshape(-1, 2)
    return float(np.mean([np.corrcoef(y[:, d], p[:, d])[0, 1] ** 2 for d in range(2)]))


# ------------------------------------------------------------------ bits (prereg §4 M-BITS, own implementation)
def bits(y, p, bin_ms, n_perm=200, dc=True, sym=True):
    """y, p [K, n, 2]. Returns I_raw, null median, I_net (bits/s, summed over dims)."""
    K, n, _ = y.shape
    w = np.hanning(n) if sym else 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(n) / n)
    X = np.fft.rfft(y * w[None, :, None], axis=1)
    Y = np.fft.rfft(p * w[None, :, None], axis=1)
    fr = np.fft.rfftfreq(n, bin_ms / 1000.0)
    keep = fr <= 10 + 1e-9
    if not dc:
        keep &= fr > 0
    df = fr[1]

    def info(Xp):
        sxy = (Xp * np.conj(Y)).sum(0)
        sxx = (np.abs(Xp) ** 2).sum(0)
        syy = (np.abs(Y) ** 2).sum(0)
        with np.errstate(invalid="ignore", divide="ignore"):
            g = np.where(sxx * syy > 0, np.abs(sxy) ** 2 / (sxx * syy), 0.0)
        g = np.clip(g[keep], 0, 1 - 1e-12)
        return float(-np.log2(1 - g).sum() * df)
    raw = info(X)
    nul = []
    while len(nul) < n_perm:
        pp = R.permutation(K)
        if np.all(pp != np.arange(K)):
            nul.append(info(X[pp]))
    m = float(np.median(nul))
    return dict(I_raw=raw, null_median=m, I_net=raw - m, n_freq=int(keep.sum()), df=float(df))


# ------------------------------------------------------------------ decoders
LAMS = np.logspace(-1, 5, 13)


def lagX(Z, H, lag0=0):
    """Z [S, T, N] -> [S, T, N*H]; block k = Z[:, t - k - lag0] (zero-padded)."""
    S, T, N = Z.shape
    out = np.zeros((S, T, N * H))
    for k in range(H):
        s = k + lag0
        out[:, s:, k * N:(k + 1) * N] = Z[:, :T - s] if s > 0 else Z
    return out


def ridge_fit(X, Y, lam):
    xm, ym = X.mean(0), Y.mean(0)
    Xc = X - xm
    W = np.linalg.solve(Xc.T @ Xc + lam * np.eye(X.shape[1]), Xc.T @ (Y - ym))
    return W, ym - xm @ W


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


class KF:
    """Velocity KF, state [v1, v2, 1]; LS fits; steady state by DARE-style iteration in the standard (innovation) form."""

    def __init__(self, Vs, Xs, diagR=False):
        Zs = [np.column_stack([v, np.ones(len(v))]) for v in Vs]
        Z0 = np.vstack([z[:-1] for z in Zs])
        Z1 = np.vstack([z[1:] for z in Zs])
        A = np.linalg.lstsq(Z0, Z1, rcond=None)[0].T
        A[2] = [0, 0, 1]
        E = Z1 - Z0 @ A.T
        Q = E.T @ E / len(E)
        Q[2] = 0
        Q[:, 2] = 0
        Z, X = np.vstack(Zs), np.vstack(Xs)
        C = np.linalg.lstsq(Z, X, rcond=None)[0].T
        Er = X - Z @ C.T
        Rm = Er.T @ Er / len(Er)
        if diagR:
            Rm = np.diag(np.diag(Rm))
        P = np.eye(3) * 0 + Q
        K = None
        for it in range(5000):
            Pp = A @ P @ A.T + Q
            S = C @ Pp @ C.T + Rm
            Kn = np.linalg.solve(S, C @ Pp).T           # Pp C' S^-1
            P = Pp - Kn @ C @ Pp
            if K is not None and np.abs(Kn - K).max() < 1e-12:
                K = Kn
                break
            K = Kn
        self.K, self.M, self.z0, self.iters = K, (np.eye(3) - K @ C) @ A, Z.mean(0), it + 1

    def run(self, X):
        z = self.z0.copy()
        out = np.empty((len(X), 2))
        for t in range(len(X)):
            z = self.M @ z + self.K @ X[t]
            out[t] = z[:2]
        return out


res = {}
# ------------------------------------------------------------------ 20 ms, H = 10, window 35 bins from -250 ms
H, W = 10, 35
C, V = grid(20, -450 - 100, H + W + 5)      # 5 extra bins in front for the lag-shift KF variant (-550 ms start)
C, V = C, V
off = 5                                     # C[:, off + H + j] is window bin j
mu = C[TR][:, off:off + H + W].reshape(-1, n_u).mean(0)
sd = np.maximum(C[TR][:, off:off + H + W].reshape(-1, n_u).std(0), 1e-8)
Z = (C - mu) / sd
Vw = V[:, off + H:off + H + W]
LX = lagX(Z, H)[:, off + H:off + H + W]      # features for window bins
b = ridge_select(LX[TR].reshape(-1, n_u * H), Vw[TR].reshape(-1, 2), LX[VA].reshape(-1, n_u * H), Vw[VA].reshape(-1, 2))
p_ridge = (LX[TE].reshape(-1, n_u * H) @ b[2] + b[3]).reshape(len(TE), W, 2)
res["ridge"] = dict(lambda_=float(b[1]), val_r2=float(b[0]), test_r2=r2vw(Vw[TE], p_ridge), rho2=rho2(Vw[TE], p_ridge),
                    bits=bits(Vw[TE], p_ridge, 20), bits_noDC=bits(Vw[TE], p_ridge, 20, dc=False),
                    bits_periodic_hann=bits(Vw[TE], p_ridge, 20, sym=False))
res["ridge"]["bits_signflipped_output"] = bits(Vw[TE], -p_ridge, 20)
res["ridge"]["r2_signflipped_output"] = r2vw(Vw[TE], -p_ridge)
log("ridge", res["ridge"]["lambda_"], res["ridge"]["test_r2"], res["ridge"]["bits"]["I_net"])

# memoryless ridge (current bin only, H = 1) = the information the prereg KF observation sees per bin
L1 = lagX(Z, 1)[:, off + H:off + H + W]
b1 = ridge_select(L1[TR].reshape(-1, n_u), Vw[TR].reshape(-1, 2), L1[VA].reshape(-1, n_u), Vw[VA].reshape(-1, 2))
p1 = (L1[TE].reshape(-1, n_u) @ b1[2] + b1[3]).reshape(len(TE), W, 2)
res["ridge_H1_current_bin_only"] = dict(lambda_=float(b1[1]), test_r2=r2vw(Vw[TE], p1))
# ridge H = 1 with 100 ms neural lead (x_{t-5}) as a check of the lag effect
L5 = lagX(Z, 1, lag0=5)[:, off + H:off + H + W]
b5 = ridge_select(L5[TR].reshape(-1, n_u), Vw[TR].reshape(-1, 2), L5[VA].reshape(-1, n_u), Vw[VA].reshape(-1, 2))
res["ridge_H1_x_t-5"] = dict(test_r2=r2vw(Vw[TE], (L5[TE].reshape(-1, n_u) @ b5[2] + b5[3]).reshape(len(TE), W, 2)))
log("ridge H1", res["ridge_H1_current_bin_only"], res["ridge_H1_x_t-5"])


def kf_eval(Xw_all, name, diagR=False, start=0):
    """Xw_all [S, T, N] observations aligned to window bins (window = last W rows); run from row `start`."""
    k = KF([Vw[s] for s in TR], [Xw_all[s, -W:] for s in TR], diagR=diagR)
    pr = np.stack([k.run(Xw_all[s, start:])[-W:] for s in TE])
    pv = np.stack([k.run(Xw_all[s, start:])[-W:] for s in VA])
    out = dict(test_r2=r2vw(Vw[TE], pr), val_r2=r2vw(Vw[VA], pv), rho2=rho2(Vw[TE], pr), iters=k.iters)
    if name == "kf_prereg":
        out["bits"] = bits(Vw[TE], pr, 20)
    res[name] = out
    log(name, out)
    return pr


Zw = Z[:, off + H:off + H + W]
kf_eval(Zw, "kf_prereg")                                           # prereg: current bin, window start, full R
kf_eval(Zw, "kf_diagR", diagR=True)
kf_eval(Z[:, off:off + H + W], "kf_start_at_history_-450ms", start=0)   # KF fitted on window, run from -450 ms
for L in (3, 5, 7):
    kf_eval(Z[:, off - L + H:off - L + H + W], "kf_obs_x_t-%d" % L)      # causal lagged observation (x_{t-L})
# KF on the ridge's smoothed/lagged information: observation = 200 ms boxcar mean of z (causal)
box = np.stack([Z[:, off + H - k:off + H - k + W] for k in range(10)]).mean(0)
kf_eval(box, "kf_obs_causal_200ms_boxcar")

# ------------------------------------------------------------------ NC1-like: ridge trained on shuffled trial pairing
nc1 = []
for rep in range(5):
    pi, pv = R.permutation(len(TR)), R.permutation(len(VA))
    bs = ridge_select(LX[TR].reshape(-1, n_u * H), Vw[TR][pi].reshape(-1, 2), LX[VA].reshape(-1, n_u * H),
                      Vw[VA][pv].reshape(-1, 2))
    ps = (LX[TE].reshape(-1, n_u * H) @ bs[2] + bs[3]).reshape(len(TE), W, 2)
    bb = bits(Vw[TE], ps, 20)
    nc1.append(dict(lambda_=float(bs[1]), r2=r2vw(Vw[TE], ps), I_net=bb["I_net"], I_raw=bb["I_raw"]))
res["NC1_ridge_5_reviewer_permutations"] = nc1
B0 = np.repeat(Vw[TR].mean(0)[None], len(TE), 0)
res["B0"] = dict(r2=r2vw(Vw[TE], B0), bits=bits(Vw[TE], B0, 20))
log("NC1", nc1, res["B0"]["r2"])

# ------------------------------------------------------------------ PL-1 analytic + empirical (10 noise seeds)
yt, pt = Vw[TE].reshape(-1, 2), p_ridge.reshape(-1, 2)
sst = ((yt - yt.mean(0)) ** 2).sum(0)
r = ((yt - pt) ** 2).sum(0)[0] / sst[0]
w1 = sst[0] / sst.sum()
res["PL1_analytic"] = dict(r_v1=float(r), w1=float(w1), expected_rise=float(w1 * r * r / (1 + r)))
# smallest r with w1 r^2/(1+r) >= 0.10
rr = np.linspace(0, 1, 100001)
ok = rr[w1 * rr ** 2 / (1 + rr) >= 0.10]
res["PL1_analytic"]["r_needed_for_0.10_at_this_w1"] = float(ok[0]) if ok.size else None
ok1 = rr[rr ** 2 / (1 + rr) >= 0.10]
res["PL1_analytic"]["r_needed_for_0.10_even_if_w1_eq_1"] = float(ok1[0])
v1m, v1s = Vw[TR][..., 0].mean(), Vw[TR][..., 0].std()
rises = []
for rep in range(10):
    def plant(idx):
        return np.column_stack([LX[idx].reshape(-1, n_u * H), (Vw[idx][..., 0].reshape(-1) - v1m) / v1s +
                                R.standard_normal(len(idx) * W)])
    bp = ridge_select(plant(TR), Vw[TR].reshape(-1, 2), plant(VA), Vw[VA].reshape(-1, 2))
    rises.append(r2vw(Vw[TE], (plant(TE) @ bp[2] + bp[3]).reshape(len(TE), W, 2)) - res["ridge"]["test_r2"])
res["PL1_empirical_rise_10_seeds"] = dict(values=[float(x) for x in rises], max=float(max(rises)),
                                          mean=float(np.mean(rises)))
log("PL1", res["PL1_analytic"], res["PL1_empirical_rise_10_seeds"])

# ------------------------------------------------------------------ KF bin sweep (window -250..+450, prereg bins)
sweep = {}
for bm in (10, 50, 100):
    nb = 700 // bm
    Cb, Vb = grid(bm, -250, nb)
    Cbt = Cb[TR].reshape(-1, n_u)
    Zb = (Cb - Cbt.mean(0)) / np.maximum(Cbt.std(0), 1e-8)
    k = KF([Vb[s] for s in TR], [Zb[s] for s in TR])
    sweep[bm] = r2vw(Vb[TE], np.stack([k.run(Zb[s]) for s in TE]))
    del Cb
res["kf_bin_sweep_window_only_z"] = sweep
log("sweep", sweep)
res["wall_s"] = time.time() - T0
res["peak_ws_mb"] = peak_mb()
json.dump(res, open(OUT, "w"), indent=1, default=float)
log("done")
