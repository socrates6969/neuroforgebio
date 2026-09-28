"""P5b: independent spatial channels per 2 x 32 S1 array pair, from MEASURED somatotopy (H7', cycle 3).

Implements prereg\\P5b_channels_measured_somatotopy.md (FIXED). Computational model only: stimulation values are QUOTED
facts used as model inputs, not settings for any person. Interpretations: code\\DEVIATIONS.md, section P5b.
Imports code\\p5_spatial_capacity.py and code\\p4_pooling_capacity.py read-only (unchanged).

Run:  python p5b_channels_measured.py --selftest
      python p5b_channels_measured.py --stage fit     (calibration, cached to results\\p5b_fits.json)
      python p5b_channels_measured.py --stage run     (configurations, gate, controls, verdict, figures)
"""
import csv
import json
import os
import sys
import time

import numpy as np
from scipy.optimize import minimize
from scipy.stats import norm

BASE = r"C:\Users\mariu\neuro-company\research\somatosensory\code"
ROOT = r"C:\Users\mariu\neuro-company\research\somatosensory"
DATA = os.path.join(ROOT, "notes", "published-derived")
RES = os.path.join(BASE, "results")
FIG = os.path.join(BASE, "figures")
sys.path.insert(0, BASE)
import p4_pooling_capacity as p4  # noqa: E402
import p5_spatial_capacity as p5  # noqa: E402

SEED = 20260926
# digitised Greenspon 2025 Fig 3e (notes\published-derived\greenspon2025_fig3e_cortical_vs_PF_distance_DIGITISED.csv)
EDGES = np.linspace(0.0, 4.0, 8)
CURVE_D = np.array([3.1, 6.0, 8.0, 11.8, 18.2, 24.1, 26.6])
CURVE_S = np.array([1, 1, 1, 1, 1, 1, 3.0])
R_T, R_SD = 0.69, 0.03
# PF area, two-piece log-normal (prereg section 2)
MU = np.log(2.5)
S_LO = np.log(2.5 / 0.3) / 1.645
S_HI = np.log(11.3 / 2.5) / 1.645
A_MIN, A_MAX = 0.05, 40.0   # cm2
PART_CODE = {"C1": "BCI02", "P2": "CRS02", "P3": "CRS07", "C2?": "BCI03", "P4?": "CRS08"}
F_PART = {"C1": 0.75, "P2": 0.75, "P3": 0.42, "C2?": 0.75, "P4?": 0.75}
U_MEAS = {"C1": 12.0, "P2": 33.0, "P3": 30.0}
PARTS = ["C1", "P2", "P3"]
MAPS = ["iso", "1d"]
W_LIST = [15.0, 20.0, 25.0]
SHAPES = ["disc", "ellipse"]
FMODES = ["part", "one"]
CURVES = [0.0, -1.0, 1.0]
K_MIN = 5.0
PALM_CM2 = 165.0
N_DISC, N_ELL, N_UNION = 500, 100, 100
N_CAL_PER = 80
H_RASTER = 0.25
AMP_CONDS = [(40, 0.77), (40, 1.43), (80, 0.77), (80, 1.43)]
D_SWEEP = [0.0, 2.0, 4.0, 8.0, 16.0]
B_CORR = [(0.5, 30.0), (0.0, 40.0), (0.1, 20.0), (0.0, 20.0)]
B_IND = [(0.5, 30.0), (0.0, 20.0)]
STARTS_CORR = [(5, 8, 1.5, 1.5), (3, 4, 0.5, 0.5), (8, 14, 3, 3), (12, 2, 6, 6), (2, 20, 1, 0.5)]
STARTS_IND = [(5, 1.5), (3, 0.5), (8, 3), (12, 6), (2, 8)]
NOTE = "Model output (simulation from published summary data); NOT stimulation settings for any person."


# ----------------------------------------------------------------------------- inputs
def load_geometry():
    g = {}
    with open(os.path.join(DATA, "greenspon2025_S1_array_channel_maps.csv")) as fh:
        for r in csv.DictReader(fh):
            if r["wired"] != "1":
                continue
            side = "M" if r["array_name"].startswith("Medial") else "L"
            g.setdefault((r["subject_code"], side), []).append((float(r["x_mm"]), float(r["y_mm"])))
    out = {}
    for k, v in g.items():
        X = np.array(v)
        out[k] = X - X.mean(0)
    return out


GEO = load_geometry()


def part_geo(p):
    c = PART_CODE[p]
    return GEO[(c, "M")], GEO[(c, "L")]


CAL_ARRAYS = [GEO[("BCI02", "M")], GEO[("BCI02", "L")], GEO[("CRS02", "M")], GEO[("CRS02", "L")], GEO[("CRS07", "M")]]


def downey_index():
    cov = {}
    with open(os.path.join(DATA, "downey2024_digit_coverage_by_array.csv")) as fh:
        lines = [l for l in fh if not l.startswith('"#') and not l.startswith("#")]
    for r in csv.DictReader(lines):
        cov.setdefault(r["participant"], {}).setdefault(r["array"], []).append(float(r["pct_electrodes_with_PF_on_digit"]))
    out = {}
    for p, d in cov.items():
        a, b = np.array(d["Medial"]), np.array(d["Lateral"])
        out[p] = float(a @ b / np.sqrt((a @ a) * (b @ b)))
    return out


# ----------------------------------------------------------------------------- model pieces
def area_cm2(u):
    """inverse CDF of the two-piece log-normal, truncated to [A_MIN, A_MAX]"""
    def cdf(a):
        z = np.log(a) - MU
        return norm.cdf(z / (S_LO if z < 0 else S_HI))
    flo, fhi = cdf(A_MIN), cdf(A_MAX)
    q = flo + np.asarray(u) * (fhi - flo)
    z = norm.ppf(q)
    return np.exp(MU + z * np.where(q < 0.5, S_LO, S_HI))


def ksqrt(X, l):
    d2 = ((X[:, None, :] - X[None, :, :]) ** 2).sum(-1)
    K = np.exp(-d2 / (2.0 * l * l))
    w, V = np.linalg.eigh(K)
    return (V * np.sqrt(np.clip(w, 0, None))) @ V.T


def linmap(X, ang, g, mapv):
    """X (m,2) or (n,m,2); ang (n,) -> (n,m,2) skin positions of the linear map"""
    c, s = np.cos(ang)[:, None], np.sin(ang)[:, None]
    x, y = (X[..., 0], X[..., 1])
    u0 = c * x - s * y
    v0 = s * x + c * y
    gv = g if mapv == "iso" else 0.0
    return np.stack([g * u0, gv * v0], -1)


def field(S, Z, sf):
    return sf * np.einsum("ij,njc->nic", S, Z)


class PairAcc:
    """accumulates same-digit pair statistics (bin sums, pooled Pearson sums, per-array r)"""

    def __init__(self):
        self.bs = np.zeros(7)
        self.bn = np.zeros(7)
        self.m = np.zeros(6)   # n, sx, sy, sxx, syy, sxy
        self.r_arr = []

    _geo = {}

    @classmethod
    def _pairs(cls, X):
        key = X.tobytes()
        if key not in cls._geo:
            iu = np.triu_indices(X.shape[0], 1)
            dc = np.sqrt(((X[iu[0]] - X[iu[1]]) ** 2).sum(-1))
            b = np.digitize(dc, EDGES) - 1
            b = np.where((b >= 0) & (b < 7), b, 7)   # 7 = out-of-range dump bin (not in the curve)
            cls._geo[key] = (iu, dc, b)
        return cls._geo[key]

    def add(self, X, cent, W, phase, per_array=True):
        iu, dc, b = self._pairs(X)
        u = cent[..., 0]
        strip = np.floor((u + phase[:, None]) / W)
        same = (strip[:, iu[0]] == strip[:, iu[1]]).astype(float)
        d = cent[:, iu[0]] - cent[:, iu[1]]
        ds = np.sqrt(d[..., 0] ** 2 + d[..., 1] ** 2)
        dsm = ds * same
        n = same.sum(1)
        sx, sy = same @ dc, dsm.sum(1)
        sxx, syy, sxy = same @ (dc * dc), (dsm * ds).sum(1), dsm @ dc
        nb = same.shape[0]
        self.bs += np.bincount(np.broadcast_to(b, ds.shape).ravel(), weights=dsm.ravel(), minlength=8)[:7]
        self.bn += np.bincount(b, weights=same.sum(0), minlength=8)[:7]
        self.m += [n.sum(), sx.sum(), sy.sum(), sxx.sum(), syy.sum(), sxy.sum()]
        if not per_array:
            return
        with np.errstate(invalid="ignore", divide="ignore"):
            r = (n * sxy - sx * sy) / np.sqrt((n * sxx - sx ** 2) * (n * syy - sy ** 2))
        self.r_arr.extend(r[np.isfinite(r) & (n >= 3)].tolist())
        del nb

    def merge(self, o):
        self.bs += o.bs; self.bn += o.bn; self.m += o.m; self.r_arr += o.r_arr
        return self

    def means(self):
        with np.errstate(invalid="ignore"):
            return self.bs / self.bn

    def r(self):
        n, sx, sy, sxx, syy, sxy = self.m
        return float((n * sxy - sx * sy) / np.sqrt((n * sxx - sx ** 2) * (n * syy - sy ** 2)))


# ----------------------------------------------------------------------------- calibration
def _uniq_cal():
    """group the 5 calibration arrays by identical geometry -> [(X, n_draws)]"""
    groups = []
    for X in CAL_ARRAYS:
        for gdef in groups:
            if gdef[0].shape == X.shape and np.allclose(gdef[0], X):
                gdef[1] += N_CAL_PER
                break
        else:
            groups.append([X, N_CAL_PER])
    return groups


CAL_GROUPS = _uniq_cal()


def cal_crn(tag):
    rng = np.random.default_rng([SEED, 51, tag])
    return [dict(X=X, ang=rng.uniform(0, 2 * np.pi, n), ph=rng.random(n), Zf=rng.standard_normal((n, 32, 2)),
                 Zn=rng.standard_normal((n, 32, 2))) for X, n in CAL_GROUPS]


def cal_stats(theta, model, mapv, W, crn, per_array=True):
    if model == "corr":
        g, sf, l, sn = theta
    else:
        (g, sn), sf, l = theta, 0.0, 1.0
    acc = PairAcc()
    for c in crn:
        X = c["X"]
        cent = linmap(X, c["ang"], g, mapv) + sn * c["Zn"]
        if sf > 0:
            cent = cent + field(ksqrt(X, l), c["Zf"], sf)
        acc.add(X, cent, W, c["ph"] * W, per_array=per_array)
    return acc


def objective(theta, model, mapv, W, target, crn):
    acc = cal_stats(theta, model, mapv, W, crn, per_array=False)
    m = acc.means()
    if not np.all(np.isfinite(m)):
        return 1e6
    r = acc.r()
    if not np.isfinite(r):
        return 1e6
    return float((((m - target) / CURVE_S) ** 2).sum() + ((r - R_T) / R_SD) ** 2)


def fit_one(model, mapv, W, shift, tag):
    crn = cal_crn(tag)
    target = CURVE_D + shift
    B, starts = (B_CORR, STARTS_CORR) if model == "corr" else (B_IND, STARTS_IND)
    best, runs = None, []
    for s in starts:
        res = minimize(objective, np.array(s, float), args=(model, mapv, W, target, crn), method="Nelder-Mead",
                       bounds=B, options=dict(maxfev=600, xatol=1e-3, fatol=1e-4))
        runs.append(dict(start=list(s), x=res.x.tolist(), fun=float(res.fun), nfev=int(res.nfev)))
        if best is None or res.fun < best.fun:
            best = res
    acc = cal_stats(best.x, model, mapv, W, crn)
    th = best.x.tolist()
    theta = dict(g=th[0], sigma_f=th[1], l=th[2], sigma_n=th[3]) if model == "corr" else \
        dict(g=th[0], sigma_f=0.0, l=1.0, sigma_n=th[1])
    return dict(model=model, map=mapv, W=W, shift=shift, theta=theta, obj=float(best.fun), runs=runs,
                fit_means=acc.means().tolist(), fit_r=acc.r(), fit_median_array_r=float(np.median(acc.r_arr)))


def fit_key(model, mapv, W, shift):
    return f"{model}|{mapv}|W{W:g}|c{shift:+g}"


def fit_settings():
    s = [(m, W, 0.0) for m in MAPS for W in W_LIST] + [(m, 20.0, c) for m in MAPS for c in (-1.0, 1.0)]
    return [(model, m, W, c) for model in ("corr", "ind") for (m, W, c) in s]


def stage_fit():
    t0 = time.time()
    out = {}
    for i, (model, m, W, c) in enumerate(fit_settings()):
        r = fit_one(model, m, W, c, 100 + i)
        out[fit_key(model, m, W, c)] = r
        print(f"fit {fit_key(model, m, W, c)} obj {r['obj']:.2f} theta {r['theta']} r {r['fit_r']:.3f} "
              f"t {time.time() - t0:.0f}s", flush=True)
    with open(os.path.join(RES, "p5b_fits.json"), "w") as f:
        json.dump(dict(prereg="prereg/P5b_channels_measured_somatotopy.md", seed=SEED, fits=out,
                       runtime_s=time.time() - t0), f, indent=1)


# ----------------------------------------------------------------------------- overlap / union
def C_of(cent, area_mm2, shape):
    if shape == "ellipse":
        cent = cent * np.array([1.0, 0.5])
        area_mm2 = area_mm2 * 0.5
    return p5.overlap_C(cent, area_mm2)


def S2(C):
    return (C ** 2).sum((-1, -2))


def union_mm2(cent, area_mm2, shape, h=H_RASTER):
    """0.25 mm raster union per draw; ellipses via the exact affine map (area x 2)"""
    fac = 1.0
    if shape == "ellipse":
        cent, area_mm2, fac = cent * np.array([1.0, 0.5]), area_mm2 * 0.5, 2.0
    r = np.sqrt(area_mm2 / np.pi)
    out = np.zeros(cent.shape[0])
    for k in range(cent.shape[0]):
        lo = (cent[k] - r[k, :, None]).min(0)
        hi = (cent[k] + r[k, :, None]).max(0)
        nx, ny = int(np.ceil((hi[0] - lo[0]) / h)) + 1, int(np.ceil((hi[1] - lo[1]) / h)) + 1
        xs = lo[0] + h / 2 + h * np.arange(nx)
        ys = lo[1] + h / 2 + h * np.arange(ny)
        cov = np.zeros((nx, ny), bool)
        for i in range(cent.shape[1]):
            cx, cy, ri = cent[k, i, 0], cent[k, i, 1], r[k, i]
            a0, a1 = max(0, int((cx - ri - lo[0]) / h) - 1), min(nx, int((cx + ri - lo[0]) / h) + 2)
            b0, b1 = max(0, int((cy - ri - lo[1]) / h) - 1), min(ny, int((cy + ri - lo[1]) / h) + 2)
            cov[a0:a1, b0:b1] |= ((xs[a0:a1, None] - cx) ** 2 + (ys[None, b0:b1] - cy) ** 2) <= ri * ri
        out[k] = cov.sum() * h * h * fac
    return out


def packing(C, area, thr=0.1):
    """greedy maximal set with pairwise C <= thr, smallest area first (vectorised over draws)"""
    n, m = area.shape
    order = np.argsort(area, 1, kind="stable")
    chosen = np.zeros((n, m), bool)
    ar = np.arange(n)
    for k in range(m):
        i = order[:, k]
        row = C[ar, i, :]
        ok = ~((row > thr) & chosen).any(1)
        chosen[ar, i] = ok
    return chosen.sum(1)


def gather(a, idx):
    if a.ndim == 3:
        return np.take_along_axis(a, idx[:, :, None], 1)
    return np.take_along_axis(a, idx, 1)


# ----------------------------------------------------------------------------- base draws
def base_draws(p, n):
    rng = np.random.default_rng([SEED, 52, PARTS.index(p) if p in PARTS else 10 + list(PART_CODE).index(p)])
    return dict(ang=rng.uniform(0, 2 * np.pi, n), ph=rng.random((n, 2)), Zj=rng.standard_normal((n, 64, 2)),
                Z2=rng.standard_normal((n, 32, 2)), Zn=rng.standard_normal((n, 64, 2)), uA=rng.random((n, 64)),
                key=rng.random((n, 64)), psi=rng.uniform(0, 2 * np.pi, n), perm=rng.random((n, 64)),
                nullr=rng.random((n, 64)), nullt=rng.random((n, 64)))


def keep_idx(key, nk):
    """nk kept electrodes per array (smallest keys; nested across f), returns (n, 2nk) indices into 0..63"""
    i1 = np.sort(np.argsort(key[:, :32], 1)[:, :nk], 1)
    i2 = np.sort(np.argsort(key[:, 32:], 1)[:, :nk], 1) + 32
    return np.concatenate([i1, i2], 1)


def centroids(p, bd, n, theta, mapv):
    X1, X2 = part_geo(p)
    Xj = np.vstack([X1, X2])
    g, sf, l, sn = theta["g"], theta["sigma_f"], theta["l"], theta["sigma_n"]
    lin = linmap(Xj, bd["ang"][:n], g, mapv)
    nug = sn * bd["Zn"][:n]
    fj = field(ksqrt(Xj, l), bd["Zj"][:n], sf) if sf > 0 else np.zeros_like(lin)
    f2 = field(ksqrt(X2, l), bd["Z2"][:n], sf) if sf > 0 else np.zeros_like(lin[:, 32:])
    low = lin + fj + nug
    high = low.copy()
    high[:, 32:] = lin[:, 32:] + f2 + nug[:, 32:]
    return dict(low=low, high=high, lin=lin, nug=nug, fj=fj, f2=f2, X1=X1, X2=X2, Xj=Xj)


def bounds_from(cl, ch, A, idx, nk, shape):
    """K_low, N_A1, N_A2, K_high, S sums and the low-frame C"""
    Cl = C_of(gather(cl, idx), gather(A, idx), shape)
    C1 = Cl[:, :nk, :nk]
    C2 = C_of(gather(ch, idx[:, nk:]), gather(A, idx[:, nk:]), shape)
    s1, s2 = S2(C1), S2(C2)
    K_low = p5.neff_from_C(Cl)
    NA1, NA2 = nk ** 2 / s1, nk ** 2 / s2
    K_high = (2 * nk) ** 2 / (s1 + s2)   # participation ratio of the block-diagonal C
    return dict(K_low=K_low, NA1=NA1, NA2=NA2, K_high=K_high, Cl=Cl)


def run_config(p, mapv, W, shape, fmode, fit, bd, amps=True, want_pack=True):
    n = N_DISC if shape == "disc" else N_ELL
    th = fit["theta"]
    cc = centroids(p, bd, n, th, mapv)
    nk = int(round((F_PART[p] if fmode == "part" else 1.0) * 32))
    idx = keep_idx(bd["key"][:n], nk)
    A = area_cm2(bd["uA"][:n]) * 100.0   # mm2
    b = bounds_from(cc["low"], cc["high"], A, idx, nk, shape)
    res = dict(part=p, map=mapv, W=W, shape=shape, fmode=fmode, n_keep=nk, n_draws=n, theta=th,
               K_low=b["K_low"], N_A=np.concatenate([b["NA1"], b["NA2"]]), K_high=b["K_high"],
               ident_err=float(np.abs(b["K_high"] - 4.0 / (1.0 / b["NA1"] + 1.0 / b["NA2"])).max()))
    if want_pack:
        res["pack_low"] = packing(b["Cl"], gather(A, idx))
    # gate V1/V2 on the independent single arrays (all 32 sites)
    acc = PairAcc()
    acc.add(cc["X1"], cc["high"][:, :32], W, bd["ph"][:n, 0] * W)
    acc.add(cc["X2"], cc["high"][:, 32:], W, bd["ph"][:n, 1] * W)
    res["acc"] = acc
    # unions (first N_UNION draws), cm2
    m = min(N_UNION, n)
    il = idx[:m]
    Ul = union_mm2(gather(cc["low"][:m], il), gather(A[:m], il), shape) / 100
    Ua1 = union_mm2(gather(cc["high"][:m], il[:, :nk]), gather(A[:m], il[:, :nk]), shape) / 100
    Ua2 = union_mm2(gather(cc["high"][:m], il[:, nk:]), gather(A[:m], il[:, nk:]), shape) / 100
    res["U_low"], res["U_high"] = Ul, Ua1 + Ua2
    if amps:
        res["amp"] = {}
        for I, gam in AMP_CONDS:
            ba = bounds_from(cc["low"], cc["high"], A * (I / 60.0) ** gam, idx, nk, shape)
            res["amp"][f"I{I}_g{gam}"] = dict(K_low=ba["K_low"], N_A=np.concatenate([ba["NA1"], ba["NA2"]]),
                                              K_high=ba["K_high"])
    res["_cc"], res["_idx"], res["_A"] = cc, idx, A
    return res


# ----------------------------------------------------------------------------- stats / gate
def q(v):
    v = np.asarray(v, float)
    return dict(p2_5=float(np.percentile(v, 2.5)), median=float(np.median(v)), p97_5=float(np.percentile(v, 97.5)),
                mean=float(v.mean()), n=int(v.size))


def boot_q(v, rng, nb=1000):
    v = np.asarray(v, float)
    b = rng.integers(0, v.size, (nb, v.size))
    vb = v[b]
    out = q(v)
    for name, f in (("p2_5", lambda x: np.percentile(x, 2.5, 1)), ("median", lambda x: np.median(x, 1)),
                    ("p97_5", lambda x: np.percentile(x, 97.5, 1))):
        e = f(vb)
        out[name + "_ci95"] = [float(np.percentile(e, 2.5)), float(np.percentile(e, 97.5))]
    return out


def gate(acc, U_low_by_p, U_high_by_p):
    m = acc.means()
    tol = np.array([max(2.0, 0.25 * d) for d in CURVE_D[:6]] + [0.40 * CURVE_D[6]])
    dev = np.abs(m - CURVE_D)
    V1 = bool(np.all(np.isfinite(m)) and np.all(dev <= tol))
    r = acc.r()
    rmed = float(np.median(acc.r_arr)) if acc.r_arr else float("nan")
    V2 = bool(0.59 <= r <= 0.79 and rmed > 0.40)
    v3 = {}
    for p in U_low_by_p:
        lo, hi = 0.7 * float(np.median(U_low_by_p[p])), 1.3 * float(np.median(U_high_by_p[p]))
        v3[p] = dict(U_meas=U_MEAS[p], lo=lo, hi=hi, ok=bool(lo <= U_MEAS[p] <= hi))
    V3 = bool(all(x["ok"] for x in v3.values()))
    return dict(V1=V1, V2=V2, V3=V3, passed=bool(V1 and V2 and V3), sim_means=m.tolist(), tol=tol.tolist(),
                r_pooled=r, r_array_median=rmed, V3_detail=v3)


def cfg_class(K_low, K_high):
    if np.percentile(K_low, 2.5) >= K_MIN:
        return "PASS"
    if np.percentile(K_high, 2.5) >= K_MIN:
        return "CONDITIONAL PASS"
    if np.percentile(K_high, 97.5) < K_MIN:
        return "FAIL"
    return "INCONCLUSIVE"


def pooled_p2_5_ci(lists, rng, nb=400):
    allv = np.concatenate(lists)
    est = float(np.percentile(allv, 2.5))
    bs = []
    for _ in range(nb):
        bs.append(np.percentile(np.concatenate([v[rng.integers(0, v.size, v.size)] for v in lists]), 2.5))
    return dict(value=est, ci95=[float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))], n_draws=int(allv.size),
                median=float(np.median(allv)), p97_5=float(np.percentile(allv, 97.5)))


def verdict_rule(rows):
    """rows: defensible configs with arrays K_low, K_high; prereg section 6"""
    rng = np.random.default_rng([SEED, 53, len(rows)])
    Kdl = pooled_p2_5_ci([r["K_low"] for r in rows], rng)
    Kdh = pooled_p2_5_ci([r["K_high"] for r in rows], rng)
    nd = len(rows)
    fr_low = float(np.mean([np.percentile(r["K_low"], 2.5) >= K_MIN for r in rows]))
    fr_high = float(np.mean([np.percentile(r["K_high"], 2.5) >= K_MIN for r in rows]))
    fr_fail = float(np.mean([np.percentile(r["K_high"], 97.5) < K_MIN for r in rows]))
    return dict(K_design_low=Kdl, K_design_high=Kdh, n_defensible=nd, frac_cfg_p2_5_Klow_ge5=fr_low,
                frac_cfg_p2_5_Khigh_ge5=fr_high, frac_cfg_p97_5_Khigh_lt5=fr_fail)


def decide(K_dl, K_dh, fr_low, fr_high, fr_fail):
    if K_dl >= K_MIN and fr_low >= 0.7:
        return "PASS"
    if K_dh >= K_MIN and fr_high >= 0.7:
        return "CONDITIONAL PASS"
    if fr_fail >= 0.7:
        return "FAIL"
    return "INCONCLUSIVE"


# ----------------------------------------------------------------------------- self tests
def selftest():
    res = {}
    # geometry
    for k, X in GEO.items():
        assert X.shape == (32, 2), k
        d = np.sqrt(((X[:, None] - X[None]) ** 2).sum(-1)) + np.eye(32) * 99
        assert d.min() >= 0.4 - 1e-9
    res["n_arrays"] = len(GEO)
    # area model quantiles (V4 implementation check)
    a = area_cm2(np.random.default_rng(1).random(400000))
    qs = [float(np.percentile(a, x)) for x in (50, 5, 95)]
    res["area_q50_q5_q95_cm2"] = qs
    res["V4_area_quantiles_within_5pct"] = bool(all(abs(x / t - 1) < 0.05 for x, t in zip(qs, (2.5, 0.3, 11.3))))
    assert res["V4_area_quantiles_within_5pct"]
    assert a.min() >= A_MIN - 1e-12 and a.max() <= A_MAX + 1e-9
    # N_eff bounds, block-diagonal identity
    assert abs(p5.neff_from_C(np.eye(24)[None])[0] - 24) < 1e-12
    assert abs(p5.neff_from_C(np.ones((1, 24, 24)))[0] - 1) < 1e-12
    rng = np.random.default_rng(2)
    cent = rng.normal(0, 20, (3, 48, 2)); A = area_cm2(rng.random((3, 48))) * 100
    C1 = p5.overlap_C(cent[:, :24], A[:, :24]); C2 = p5.overlap_C(cent[:, 24:], A[:, 24:])
    Cb = np.zeros((3, 48, 48)); Cb[:, :24, :24] = C1; Cb[:, 24:, 24:] = C2
    n1, n2 = p5.neff_from_C(C1), p5.neff_from_C(C2)
    res["block_identity_err"] = float(np.abs(p5.neff_from_C(Cb) - 4 / (1 / n1 + 1 / n2)).max())
    assert res["block_identity_err"] < 1e-9
    # ellipse affine closed form vs raster
    errs = []
    for k in range(6):
        Ae = rng.uniform(100, 600, 2); c2 = rng.normal(0, 8, 2)
        Ce = C_of(np.array([[[0, 0], c2]]), Ae[None], "ellipse")[0, 0, 1]
        a = np.sqrt(Ae / (2 * np.pi))
        h = 0.05
        xs = np.arange(-40, 40, h) + h / 2
        X, Y = np.meshgrid(xs, xs, indexing="ij")
        e1 = (X / a[0]) ** 2 + (Y / (2 * a[0])) ** 2 <= 1
        e2 = ((X - c2[0]) / a[1]) ** 2 + ((Y - c2[1]) / (2 * a[1])) ** 2 <= 1
        Cr = (e1 & e2).sum() * h * h / np.sqrt(Ae[0] * Ae[1])
        if Ce > 0.02:
            errs.append(abs(Cr / Ce - 1))
    res["ellipse_affine_vs_raster_max_rel_err"] = float(max(errs)) if errs else 0.0
    assert res["ellipse_affine_vs_raster_max_rel_err"] < 0.01
    # union raster
    u1 = union_mm2(np.zeros((1, 1, 2)), np.array([[250.0]]), "disc")[0]
    u2 = union_mm2(np.array([[[0, 0], [100, 0]]]), np.array([[250.0, 400.0]]), "disc")[0]
    ue = union_mm2(np.zeros((1, 1, 2)), np.array([[250.0]]), "ellipse")[0]
    res["union_rel_err_single_two_ellipse"] = [float(u1 / 250 - 1), float(u2 / 650 - 1), float(ue / 250 - 1)]
    assert max(abs(x) for x in res["union_rel_err_single_two_ellipse"]) < 0.01
    # field square root
    X = GEO[("BCI02", "M")]
    S = ksqrt(X, 1.5)
    K = np.exp(-((X[:, None] - X[None]) ** 2).sum(-1) / (2 * 1.5 ** 2))
    res["ksqrt_err"] = float(np.abs(S @ S - K).max())
    assert res["ksqrt_err"] < 1e-8
    # pair statistics: pure isotropic map, huge W -> every pair same digit, skin = g x cortex, r = 1
    acc = PairAcc()
    ang = rng.uniform(0, 6.3, 20)
    acc.add(X, linmap(X, ang, 5.0, "iso"), 1e9, np.full(20, 5e8))
    iu = np.triu_indices(32, 1)
    dc = np.sqrt(((X[iu[0]] - X[iu[1]]) ** 2).sum(-1))
    b = np.digitize(dc, EDGES) - 1
    exp_m = np.array([5 * dc[b == k].mean() for k in range(7)])
    res["pairstat_err"] = float(np.abs(acc.means() - exp_m).max())
    assert res["pairstat_err"] < 1e-9 and abs(acc.r() - 1) < 1e-9
    # 1-D map: v collapses
    assert np.abs(linmap(X, ang, 5.0, "1d")[..., 1]).max() == 0.0
    # strip test: two points 1 mm apart straddling a boundary are not same-digit
    acc2 = PairAcc()
    acc2.add(np.array([[0, 0], [1, 0.0]]), np.array([[[19.5, 0], [20.5, 0]]]), 20.0, np.zeros(1))
    assert acc2.m[0] == 0
    # pure linear map + tiny PFs -> N_A = n exactly
    cl = linmap(X, ang[:5], 5.0, "iso")
    res["tiny_linear_min_neff"] = float(p5.neff_from_C(p5.overlap_C(cl, np.full((5, 32), 0.1))).min())
    assert res["tiny_linear_min_neff"] == 32.0
    # packing: disjoint discs all chosen; identical discs -> 1
    Cd = np.eye(5)[None]; assert packing(Cd, np.ones((1, 5)))[0] == 5
    assert packing(np.ones((1, 5, 5)), np.ones((1, 5)))[0] == 1
    # decision rule logic
    assert decide(6, 8, 0.8, 0.9, 0) == "PASS" and decide(4, 6, 0.1, 0.8, 0) == "CONDITIONAL PASS"
    assert decide(2, 3, 0, 0, 0.9) == "FAIL" and decide(4, 6, 0.1, 0.5, 0.1) == "INCONCLUSIVE"
    res["all_passed"] = True
    return res


# ----------------------------------------------------------------------------- controls
def hand_clip_control(cc, idx, A, nk, ndr):
    """PFs clipped to a 165 cm2 disc around the mean centroid (array for N_A, pair for K_low); 0.25 mm raster"""
    Rh = np.sqrt(PALM_CM2 * 100 / np.pi)
    h = H_RASTER
    xs = np.arange(-Rh + h / 2, Rh, h)
    X, Y = np.meshgrid(xs, xs, indexing="ij")
    inside = (X ** 2 + Y ** 2 <= Rh ** 2)
    px, py = X[inside].astype(np.float32), Y[inside].astype(np.float32)
    rat_na, rat_kl = [], []
    for k in range(ndr):
        for which in ("NA", "KL"):
            ii = idx[k, :nk] if which == "NA" else idx[k]
            c = cc["low"][k, ii]
            a = A[k, ii]
            r = np.sqrt(a / np.pi)
            c = c - c.mean(0)
            M = ((px[None] - c[:, 0:1]) ** 2 + (py[None] - c[:, 1:2]) ** 2 <= (r[:, None] ** 2)).astype(np.float32)
            I = (M @ M.T) * h * h
            ac = np.diag(I).copy()
            ok = ac > 0
            I, ac = I[np.ix_(ok, ok)], ac[ok]
            Cc = I / np.sqrt(ac[:, None] * ac[None])
            np.fill_diagonal(Cc, 1.0)
            kc = Cc.shape[0] ** 2 / (Cc ** 2).sum()   # clipped PFs with zero area inside the hand are dropped
            ku = p5.neff_from_C(p5.overlap_C(c[None], a[None]))[0]
            (rat_na if which == "NA" else rat_kl).append(kc / ku)
    return rat_na, rat_kl


def controls(prim_rows, fits, bds):
    out = {}
    fitp = fits[fit_key("corr", "iso", 20.0, 0.0)]
    th = fitp["theta"]
    NA_m, NA_sh, NA_null, tiny = [], [], [], {"N_A": [], "K_low": [], "K_high": [], "nk": []}
    strict = []
    hn, hk = [], []
    for r in prim_rows:
        p, cc, idx, A, nk = r["part"], r["_cc"], r["_idx"], r["_A"], r["n_keep"]
        bd = bds[p]
        n = A.shape[0]
        NA_m.append(r["N_A"])
        # field shuffle within each array
        perm = np.argsort(bd["perm"][:n], 1)
        pj = np.concatenate([np.argsort(bd["perm"][:n, :32], 1), np.argsort(bd["perm"][:n, 32:], 1) + 32], 1)
        del perm
        fj_sh = gather(cc["fj"], pj)
        f2_sh = gather(cc["f2"], pj[:, 32:] - 32)
        low_sh = cc["lin"] + fj_sh + cc["nug"]
        high_sh = low_sh.copy(); high_sh[:, 32:] = cc["lin"][:, 32:] + f2_sh + cc["nug"][:, 32:]
        b = bounds_from(low_sh, high_sh, A, idx, nk, "disc")
        NA_sh.append(np.concatenate([b["NA1"], b["NA2"]]))
        # no-somatotopy null: uniform on a 165 cm2 disc
        Rh = np.sqrt(PALM_CM2 * 100 / np.pi)
        rr, tt = Rh * np.sqrt(bd["nullr"][:n]), 2 * np.pi * bd["nullt"][:n]
        nc = np.stack([rr * np.cos(tt), rr * np.sin(tt)], -1)
        b = bounds_from(nc, nc, A, idx, nk, "disc")
        NA_null.append(np.concatenate([b["NA1"], b["NA2"]]))
        # tiny PF
        b = bounds_from(cc["low"], cc["high"], np.full_like(A, 0.1), idx, nk, "disc")
        tiny["N_A"].append(np.concatenate([b["NA1"], b["NA2"]]) / nk)
        tiny["K_low"].append(b["K_low"] / (2 * nk)); tiny["K_high"].append(b["K_high"] / (2 * nk))
        b = bounds_from(cc["lin"], cc["lin"], np.full_like(A, 0.1), idx, nk, "disc")
        strict.append(np.concatenate([b["NA1"], b["NA2"]]) / nk)
        # hand boundary (10 draws per participant)
        a, k = hand_clip_control(cc, idx, A, nk, 10)
        hn += a; hk += k
    NA_m, NA_sh, NA_null = map(np.concatenate, (NA_m, NA_sh, NA_null))
    out["field_shuffle"] = dict(N_A_model=q(NA_m), N_A_shuffled=q(NA_sh), ratio_median=float(np.median(NA_sh) / np.median(NA_m)),
                                passed=bool(np.median(NA_sh) > np.median(NA_m)))
    out["no_somatotopy_null"] = dict(N_A_null=q(NA_null), passed=bool(np.median(NA_m) < np.median(NA_null)))
    tt = {k: np.concatenate(v) for k, v in tiny.items() if k != "nk"}
    st = np.concatenate(strict)
    out["tiny_pf"] = dict({k: dict(median_frac=float(np.median(v)), min_frac=float(v.min()), frac_draws_below_0_98=float((v < 0.98).mean()))
                           for k, v in tt.items()},
                          strict_linear_map_N_A_min_frac=float(st.min()),
                          passed=bool(all(np.median(v) >= 0.98 for v in tt.values()) and st.min() >= 0.98))
    cent0 = np.zeros((5, 48, 2))
    ne_id = p5.neff_from_C(p5.overlap_C(cent0, np.full((5, 48), 250.0)))
    out["identical_pf"] = dict(max_abs_dev=float(np.abs(ne_id - 1).max()), passed=bool(np.abs(ne_id - 1).max() < 1e-9))
    out["hand_boundary"] = dict(n_draws=len(hn), ratio_N_A=q(hn), ratio_K_low=q(hk),
                                frac_draws_ratio_gt_1_01=float(np.mean(np.array(hn + hk) > 1.01)),
                                passed=bool(np.median(hn) <= 1.01 and np.median(hk) <= 1.01))
    # lens closed form vs raster (radii from the P5b area model)
    rng = np.random.default_rng([SEED, 54])
    errs = []
    rs = np.sqrt(area_cm2(rng.random((100, 2))) * 100 / np.pi)
    for r1, r2 in rs:
        d = rng.uniform(abs(r1 - r2), r1 + r2)
        errs.append(abs(p5.raster_lens(d, r1, r2) / float(p5.lens_area(d, r1, r2)) - 1))
    out["lens_vs_raster"] = dict(max_rel_err=float(max(errs)), median_rel_err=float(np.median(errs)), passed=bool(max(errs) < 0.01))
    return out


def d_sweep(prim_rows, bds, fit):
    th = fit["theta"]
    g, sf, l, sn = th["g"], th["sigma_f"], th["l"], th["sigma_n"]
    res = {D: [] for D in D_SWEEP}
    exact0 = []
    for r in prim_rows:
        p, cc, idx, A, nk = r["part"], r["_cc"], r["_idx"], r["_A"], r["n_keep"]
        bd = bds[p]
        n = A.shape[0]
        X1, X2 = part_geo(p)
        for D in D_SWEEP:
            K = np.empty(n)
            for k in range(n):
                off = D * np.array([np.cos(bd["psi"][k]), np.sin(bd["psi"][k])])
                Xj = np.vstack([X1, X2 + off])
                lin = linmap(Xj, bd["ang"][k:k + 1], g, "iso")
                fj = field(ksqrt(Xj, l), bd["Zj"][k:k + 1], sf) if sf > 0 else 0.0
                cent = (lin + fj + sn * bd["Zn"][k:k + 1])[:, idx[k]]
                K[k] = p5.neff_from_C(p5.overlap_C(cent, A[k:k + 1, idx[k]]))[0]
            res[D].append(K)
        exact0.append(float(np.abs(res[0.0][-1] - r["K_low"]).max()))
    rng = np.random.default_rng([SEED, 55])
    out = {}
    for D in D_SWEEP:
        v = np.concatenate(res[D])
        bm = [np.median(v[rng.integers(0, v.size, v.size)]) for _ in range(300)]
        out[f"D{D:g}"] = dict(q(v), median_se=float(np.std(bm)))
    meds = [out[f"D{D:g}"]["median"] for D in D_SWEEP]
    ses = [out[f"D{D:g}"]["median_se"] for D in D_SWEEP]
    mono = all(meds[i + 1] >= meds[i] - 2 * max(ses[i], ses[i + 1]) for i in range(len(meds) - 1))
    Kh = np.median(np.concatenate([r["K_high"] for r in prim_rows]))
    return dict(by_D=out, K0_equals_K_low_maxdiff=float(max(exact0)), monotone=bool(mono),
                K16_over_K_high_median=float(meds[-1] / Kh), approach_ok=bool(abs(meds[-1] / Kh - 1) < 0.10))


# ----------------------------------------------------------------------------- figures
def figures(out, rows_def, prim, dsw, fits):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    BL, OR, AQ, TX, TX2, SURF = "#2a78d6", "#eb6834", "#1baf7a", "#0b0b0b", "#52514e", "#fcfcfb"
    plt.rcParams.update({"axes.edgecolor": TX2, "axes.labelcolor": TX, "xtick.color": TX2, "ytick.color": TX2,
                         "axes.spines.top": False, "axes.spines.right": False, "font.size": 9})
    # --- (1) K bounds per configuration + D-sweep
    fig, axs = plt.subplots(1, 2, figsize=(14, 5.4), gridspec_kw=dict(width_ratios=[2.6, 1]), facecolor=SURF)
    ax = axs[0]
    rs = sorted(rows_def, key=lambda r: np.median(r["K_high"]))
    x = np.arange(len(rs))
    for key, col, lab, dx in (("K_low", BL, "K_low (arrays on the same skin territory)", -0.22),
                              ("N_A", AQ, "N_A (one array)", 0.0), ("K_high", OR, "K_high (arrays on disjoint territories)", 0.22)):
        med = [np.median(r[key]) for r in rs]
        lo = [np.percentile(r[key], 2.5) for r in rs]
        hi = [np.percentile(r[key], 97.5) for r in rs]
        ax.vlines(x + dx, lo, hi, color=col, lw=1, alpha=0.6)
        ax.plot(x + dx, med, "o", ms=3, color=col, label=lab)
    ax.axhline(K_MIN, color=TX, ls="--", lw=1, label="K_min = 5 (pre-registered)")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{r['part']} {r['map']} W{r['W']:g} {r['shape'][:3]} f{'P' if r['fmode'] == 'part' else '1'}"
                        + ("" if r.get("shift", 0) == 0 else f" c{r['shift']:+g}") for r in rs], rotation=90, fontsize=5)
    ax.set_ylabel("effective independent channels (participation ratio)")
    ax.set_xlabel(f"configuration: {out['descriptive_basis']}; 60 uA mapping stimulus; median and 2.5-97.5% of draws", fontsize=7)
    ax.set_title(f"P5b: channels per 2 x 32 S1 array pair.  Verdict: {out['verdict']}", fontsize=10, loc="left")
    ax.legend(fontsize=7, frameon=False, loc="upper left")
    ax = axs[1]
    Ds = D_SWEEP
    med = [dsw["by_D"][f"D{D:g}"]["median"] for D in Ds]
    ax.fill_between(Ds, [dsw["by_D"][f"D{D:g}"]["p2_5"] for D in Ds], [dsw["by_D"][f"D{D:g}"]["p97_5"] for D in Ds],
                    color=BL, alpha=0.15, lw=0)
    ax.plot(Ds, med, "o-", color=BL, lw=2, ms=5, label="K(D), median, 2.5-97.5% band")
    ax.axhline(prim["K_high"]["median"], color=OR, lw=1.5, label="K_high median (disjoint)")
    ax.axhline(K_MIN, color=TX, ls="--", lw=1, label="K_min = 5")
    ax.set_xlabel("assumed inter-array distance D (mm of cortex)")
    ax.set_ylabel("K (both arrays, 60 uA)")
    ax.set_title("Descriptive D-sweep (primary; D is NOT reported)", fontsize=9, loc="left")
    ax.legend(fontsize=7, frameon=False, loc="center right")
    fig.text(0.01, 0.005, NOTE, fontsize=7, color=TX2)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    for e in ("png", "svg"):
        fig.savefig(os.path.join(FIG, f"p5b_K_bounds.{e}"), dpi=150, facecolor=SURF)
    plt.close(fig)
    # --- (2) calibration
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.4), sharey=True, facecolor=SURF)
    xc = 0.5 * (EDGES[1:] + EDGES[:-1])
    for ax, model, title in ((axs[0], "corr", "correlated field + nugget (primary)"), (axs[1], "ind", "independent scatter (artefact control)")):
        ax.fill_between(xc, CURVE_D - 1, CURVE_D + 1, color=TX2, alpha=0.15, lw=0, label="digitised Greenspon 2025 Fig 3e, +/-1 mm")
        ax.plot(xc, CURVE_D, "k-", lw=2)
        for (m, W), col in zip([(m, W) for m in MAPS for W in W_LIST], [BL, BL, BL, OR, OR, OR]):
            f = fits[fit_key(model, m, W, 0.0)]
            ls = {15.0: ":", 20.0: "-", 25.0: "--"}[W]
            ax.plot(xc, f["fit_means"], ls, color=col, lw=1.3, label=f"{m} map, W {W:g} mm (r {f['fit_r']:.2f})")
        ax.set_xlabel("cortical distance between electrodes (mm)")
        ax.set_title(title, fontsize=9, loc="left")
        ax.legend(fontsize=6, frameon=False)
    axs[0].set_ylabel("mean same-digit PF-centroid distance (mm of skin)")
    fig.text(0.01, 0.005, NOTE, fontsize=7, color=TX2)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    for e in ("png", "svg"):
        fig.savefig(os.path.join(FIG, f"p5b_calibration.{e}"), dpi=150, facecolor=SURF)
    plt.close(fig)
    # --- (3) web single panel: K vs amplitude (pooled over defensible configurations)
    fig, ax = plt.subplots(figsize=(7.6, 5.0), facecolor=SURF)
    amp = out["amplitude_conditions"]
    for key, col, lab, dx in (("K_high", OR, "Arrays on separate skin territories (K_high)", 1.2),
                              ("K_low", BL, "Arrays on the same skin territory (K_low)", -1.2)):
        for gam, mk, ls in ((1.43, "o", "-"), (0.77, "s", ":")):
            xs_, meds, los, his = [], [], [], []
            for I in (40, 60, 80):
                s = out["pooled_60uA"][key] if I == 60 else amp[f"I{I}_g{gam}"][key]
                xs_.append(I + dx); meds.append(s["median"]); los.append(s["p2_5"]); his.append(s["p97_5"])
            ax.vlines(xs_, los, his, color=col, lw=1.2, alpha=0.5)
            ax.plot(xs_, meds, ls, marker=mk, color=col, ms=7, lw=2,
                    label=f"{lab}, PF growth exponent {gam}" if True else None)
    ax.axhline(K_MIN, color=TX, ls="--", lw=1.2)
    ax.text(81.5, K_MIN + 0.2, "K_min = 5 (one channel per digit)", fontsize=8, color=TX, ha="right", va="bottom")
    ax.set_xticks([40, 60, 80])
    ax.set_xlabel("modelled mapping amplitude (uA); 60 uA = published PF-mapping stimulus")
    ax.set_ylabel("independent location channels, K")
    ttl = "Independent spatial channels per two 32-electrode S1 arrays (model)"
    if out["abandoned"]:
        ttl += "\nDescriptive only: the model failed its pre-registered validation gate (P5b ABANDONED)"
    ax.set_title(ttl, fontsize=9.5, loc="left")
    ax.set_ylim(0, None)
    ax.legend(fontsize=7, frameon=False, loc="upper right")
    fig.text(0.01, 0.01, "Median and 2.5-97.5% of model draws, pooled over configurations.\n" + NOTE, fontsize=7, color=TX2)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    for e in ("png", "svg"):
        fig.savefig(os.path.join(FIG, f"p5b_K_vs_amplitude_web.{e}"), dpi=150, facecolor=SURF)
    plt.close(fig)


# ----------------------------------------------------------------------------- run stage
def config_list():
    rows = [dict(part=p, map=m, W=W, shape=s, fmode=f, shift=0.0) for p in PARTS for m in MAPS for W in W_LIST
            for s in SHAPES for f in FMODES]
    rows += [dict(part=p, map=m, W=20.0, shape="disc", fmode="part", shift=c) for c in (-1.0, 1.0) for p in PARTS for m in MAPS]
    return rows


def cfg_name(c):
    return f"{c['part']}|{c['map']}|W{c['W']:g}|{c['shape']}|f{c['fmode']}|c{c['shift']:+g}"


def summarize(r):
    s = dict(K_low=q(r["K_low"]), N_A=q(r["N_A"]), K_high=q(r["K_high"]), U_low_cm2=q(r["U_low"]), U_high_cm2=q(r["U_high"]),
             ident_err=r["ident_err"], theta=r["theta"], n_keep=r["n_keep"], n_draws=r["n_draws"], gate=r["gate"],
             cls=cfg_class(r["K_low"], r["K_high"]))
    if "pack_low" in r:
        s["packing_low"] = q(r["pack_low"])
    return s


def stage_run():
    t0 = time.time()
    st = selftest()
    with open(os.path.join(RES, "p5b_fits.json")) as f:
        FJ = json.load(f)
    fits = FJ["fits"]
    bds = {p: base_draws(p, N_DISC) for p in PARTS}
    out = dict(prereg="prereg/P5b_channels_measured_somatotopy.md", seed=SEED, note=NOTE, selftest=st,
               fits={k: dict(theta=v["theta"], obj=v["obj"], fit_r=v["fit_r"], fit_means=v["fit_means"],
                             fit_median_array_r=v["fit_median_array_r"]) for k, v in fits.items()})
    models = {}
    keep_prim = None
    for model in ("corr", "ind"):
        rows = []
        for c in config_list():
            fit = fits[fit_key(model, c["map"], c["W"], c["shift"])]
            r = run_config(c["part"], c["map"], c["W"], c["shape"], c["fmode"], fit, bds[c["part"]], amps=(model == "corr"))
            r["shift"] = c["shift"]
            r["gate"] = gate(r["acc"], {c["part"]: r["U_low"]}, {c["part"]: r["U_high"]})
            if not (model == "corr" and c["map"] == "iso" and c["W"] == 20 and c["shape"] == "disc" and c["fmode"] == "part"
                    and c["shift"] == 0):
                for k in ("_cc", "_idx", "_A"):
                    r.pop(k)
            rows.append(r)
        print(f"{model}: {len(rows)} configs done t {time.time() - t0:.0f}s", flush=True)
        prim = [r for r in rows if r["map"] == "iso" and r["W"] == 20 and r["shape"] == "disc" and r["fmode"] == "part"
                and r["shift"] == 0]
        acc = PairAcc()
        for r in prim:
            acc.merge(PairAcc().merge(r["acc"]))
        pg = gate(acc, {r["part"]: r["U_low"] for r in prim}, {r["part"]: r["U_high"] for r in prim})
        dfn = [r for r in rows if r["gate"]["passed"]]
        rng = np.random.default_rng([SEED, 56, len(model)])
        primsum = dict(K_low=boot_q(np.concatenate([r["K_low"] for r in prim]), rng),
                       N_A=boot_q(np.concatenate([r["N_A"] for r in prim]), rng),
                       K_high=boot_q(np.concatenate([r["K_high"] for r in prim]), rng),
                       packing_low=q(np.concatenate([r["pack_low"] for r in prim])),
                       N_A_by_participant={r["part"]: q(r["N_A"]) for r in prim},
                       K_low_by_participant={r["part"]: q(r["K_low"]) for r in prim},
                       K_high_by_participant={r["part"]: q(r["K_high"]) for r in prim},
                       U_low_by_participant={r["part"]: q(r["U_low"]) for r in prim},
                       U_high_by_participant={r["part"]: q(r["U_high"]) for r in prim}, gate=pg)
        vr = verdict_rule(dfn) if dfn else None
        cls_counts = {}
        for r in dfn:
            k = cfg_class(r["K_low"], r["K_high"])
            cls_counts[k] = cls_counts.get(k, 0) + 1
        fails = {"V1": sum(not r["gate"]["V1"] for r in rows), "V2": sum(not r["gate"]["V2"] for r in rows),
                 "V3": sum(not r["gate"]["V3"] for r in rows)}
        models[model] = dict(rows=rows, prim=prim, dfn=dfn)
        out[model] = dict(primary=primsum, n_configs=len(rows), n_defensible=len(dfn), frac_defensible=len(dfn) / len(rows),
                          gate_fail_counts=fails, rule=vr, class_counts_defensible=cls_counts,
                          configs={cfg_name(dict(r, shift=r["shift"])): summarize(r) for r in rows},
                          max_bound_identity_err=float(max(r["ident_err"] for r in rows)))
        # DESCRIPTIVE (no verdict): the section-6 quantities over ALL configurations, gate ignored
        ra = verdict_rule(rows)
        out[model]["rule_all_configs_DESCRIPTIVE"] = dict(ra, rule_outcome_if_gate_ignored=decide(
            ra["K_design_low"]["value"], ra["K_design_high"]["value"], ra["frac_cfg_p2_5_Klow_ge5"],
            ra["frac_cfg_p2_5_Khigh_ge5"], ra["frac_cfg_p97_5_Khigh_lt5"]))
        out[model]["class_counts_all"] = {c: sum(cfg_class(r["K_low"], r["K_high"]) == c for r in rows)
                                          for c in ("PASS", "CONDITIONAL PASS", "INCONCLUSIVE", "FAIL")}
        tolv = np.array([max(2.0, 0.25 * d) for d in CURVE_D[:6]] + [0.40 * CURVE_D[6]])
        out[model]["V1_bin_fail_counts"] = np.sum([np.abs(np.array(r["gate"]["sim_means"]) - CURVE_D) > tolv
                                                   for r in rows], 0).tolist()
        out[model]["V3_detail_counts"] = dict(
            U_meas_below_lo=sum(any(v["U_meas"] < v["lo"] for v in r["gate"]["V3_detail"].values()) for r in rows),
            U_meas_above_hi=sum(any(v["U_meas"] > v["hi"] for v in r["gate"]["V3_detail"].values()) for r in rows),
            V3_fail_by_participant={p: sum((not r["gate"]["V3"]) and r["part"] == p for r in rows) for p in PARTS})
        if model == "corr":
            keep_prim = prim
    # ---- verdict (correlated model), scatter-artefact flag
    C = out["corr"]
    abandon = (not C["primary"]["gate"]["passed"]) or C["frac_defensible"] < 0.5
    flag = False
    I = out["ind"]
    ind_passes = bool(I["primary"]["gate"]["passed"])
    if ind_passes and I["rule"] and C["rule"]:
        dl = abs(I["rule"]["K_design_low"]["value"] / C["rule"]["K_design_low"]["value"] - 1)
        dh = abs(I["rule"]["K_design_high"]["value"] / C["rule"]["K_design_high"]["value"] - 1)
        flag = bool(dl > 0.30 or dh > 0.30)
        out["scatter_artefact"] = dict(ind_primary_passes_gate=True, rel_diff_K_design_low=dl, rel_diff_K_design_high=dh, flag=flag)
    else:
        out["scatter_artefact"] = dict(ind_primary_passes_gate=ind_passes, flag=False)
    if abandon:
        verdict = "ABANDONED"
        Kdl = Kdh = None
    else:
        R = C["rule"]
        Kdl, Kdh = R["K_design_low"]["value"], R["K_design_high"]["value"]
        frl, frh, frf = R["frac_cfg_p2_5_Klow_ge5"], R["frac_cfg_p2_5_Khigh_ge5"], R["frac_cfg_p97_5_Khigh_lt5"]
        if flag:
            RI = I["rule"]
            Kdl, Kdh = min(Kdl, RI["K_design_low"]["value"]), min(Kdh, RI["K_design_high"]["value"])
            frl, frh = min(frl, RI["frac_cfg_p2_5_Klow_ge5"]), min(frh, RI["frac_cfg_p2_5_Khigh_ge5"])
            frf = max(frf, RI["frac_cfg_p97_5_Khigh_lt5"])
        verdict = decide(Kdl, Kdh, frl, frh, frf)
        # robustness: same per-configuration class in >= 70% of defensible configurations
        same = sum(cfg_class(r["K_low"], r["K_high"]) == verdict for r in models["corr"]["dfn"])
        out["robustness"] = dict(n_same_class=same, n_defensible=len(models["corr"]["dfn"]),
                                 frac=same / len(models["corr"]["dfn"]), robust=bool(same >= 0.7 * len(models["corr"]["dfn"])))
    out["verdict"] = verdict
    out["abandoned"] = bool(abandon)
    out["K_design_used"] = dict(low=Kdl, high=Kdh)
    print("verdict", verdict, "t", time.time() - t0, flush=True)
    # ---- controls, D-sweep (primary, correlated)
    fitp = fits[fit_key("corr", "iso", 20.0, 0.0)]
    out["controls"] = controls(keep_prim, fits, bds)
    out["d_sweep"] = d_sweep(keep_prim, bds, fitp)
    ctl = out["controls"]
    out["controls"]["bound_identity"] = dict(max_err=max(out["corr"]["max_bound_identity_err"], out["ind"]["max_bound_identity_err"]),
                                             passed=bool(max(out["corr"]["max_bound_identity_err"], out["ind"]["max_bound_identity_err"]) < 1e-9))
    out["controls_all_passed"] = bool(all(v["passed"] for v in ctl.values() if isinstance(v, dict) and "passed" in v))
    out["verified"] = bool(not abandon and C["primary"]["gate"]["passed"] and out.get("robustness", {}).get("robust", False)
                           and not flag)
    print("controls", {k: v.get("passed") for k, v in ctl.items()}, "t", time.time() - t0, flush=True)
    # ---- amplitude conditions (defensible correlated configs), pooled
    dfn = models["corr"]["dfn"] or models["corr"]["rows"]
    out["descriptive_basis"] = ("defensible configurations (correlated model)" if models["corr"]["dfn"]
                                else "ALL configurations (correlated model; none/too few passed the gate) - DESCRIPTIVE")
    out["pooled_60uA"] = {k: q(np.concatenate([r[k] for r in dfn])) for k in ("K_low", "N_A", "K_high")}
    amp = {}
    for I_, gam in AMP_CONDS:
        kk = f"I{I_}_g{gam}"
        d = {k: np.concatenate([r["amp"][kk][k] for r in dfn]) for k in ("K_low", "N_A", "K_high")}
        amp[kk] = {k: q(v) for k, v in d.items()}
        amp[kk]["K_design_low_p2_5"] = float(np.percentile(d["K_low"], 2.5))
        amp[kk]["K_design_high_p2_5"] = float(np.percentile(d["K_high"], 2.5))
        amp[kk]["rel_change_median_vs_60"] = {k: float(np.median(d[k]) / out["pooled_60uA"][k]["median"] - 1) for k in d}
        pr = {k: np.concatenate([r["amp"][kk][k] for r in keep_prim]) for k in ("K_low", "N_A", "K_high")}
        amp[kk]["primary"] = {k: q(v) for k, v in pr.items()}
    out["amplitude_conditions"] = amp
    # ---- by-factor medians (1-D vs iso, ellipse vs disc), defensible corr configs
    fac = {}
    for name, key, vals in (("map", "map", MAPS), ("shape", "shape", SHAPES), ("fmode", "fmode", FMODES), ("W", "W", W_LIST),
                            ("participant", "part", PARTS)):
        fac[name] = {str(v): {k: float(np.median(np.concatenate([r[k] for r in dfn if r[key] == v])))
                              if any(r[key] == v for r in dfn) else None for k in ("K_low", "N_A", "K_high")} for v in vals}
    out["factor_medians_defensible"] = fac
    # ---- geometry-only row (BCI03 / CRS08, identity UNVERIFIED)
    geo_rows = {}
    for p in ("C2?", "P4?"):
        r = run_config(p, "iso", 20.0, "disc", "part", fitp, base_draws(p, N_DISC), amps=False, want_pack=False)
        geo_rows[p + "(" + PART_CODE[p] + ")"] = dict(K_low=q(r["K_low"]), N_A=q(r["N_A"]), K_high=q(r["K_high"]))
    out["geometry_only_rows"] = geo_rows
    # ---- capacity (3.9), descriptive
    def cap(K, nPF):
        K = int(np.floor(K))
        if K < 1:
            return dict(K=K, total_bits=0.0)
        M = nPF / K
        nl = p4.n_levels(M, 0.162, 0.0)
        c = p4.capacity_M(M, 0.162, 0.0)["C"] if nl >= 2 else 0.0
        return dict(K=K, M=M, levels=float(nl), C_per_channel=float(c), total_bits=float(K * c))
    Kcl, Kch = (Kdl, Kdh) if Kdl is not None else (out["corr"]["rule_all_configs_DESCRIPTIVE"]["K_design_low"]["value"],
                                                    out["corr"]["rule_all_configs_DESCRIPTIVE"]["K_design_high"]["value"])
    out["capacity_basis"] = "K_design (verdict)" if Kdl is not None else "descriptive all-config K quantiles (ABANDONED)"
    if True:
        Kdl_, Kdh_ = Kcl, Kch
        out["capacity"] = {f"nPF{n}": dict(K_design_low=cap(Kdl_, n), K_design_high=cap(Kdh_, n), pooled_K1=cap(1, n),
                                             K5=cap(5, n)) for n in (48, 26)}
    out["downey_cosine"] = downey_index()
    out["runtime_s"] = time.time() - t0
    for m in ("corr", "ind"):
        for r in models[m]["rows"]:
            for k in ("_cc", "_idx", "_A", "acc"):
                r.pop(k, None)
    with open(os.path.join(RES, "p5b_channels_measured.json"), "w") as f:
        json.dump(p4.jsonable(out), f, indent=1)
    figures(out, dfn, out["corr"]["primary"], out["d_sweep"], fits)
    short = dict(verdict=verdict, abandoned=abandon, K_design=out["K_design_used"], rule_corr=C["rule"], rule_ind=I["rule"],
                 scatter=out["scatter_artefact"], robustness=out.get("robustness"), verified=out["verified"],
                 prim_corr={k: C["primary"][k] for k in ("K_low", "N_A", "K_high")}, prim_gate=C["primary"]["gate"],
                 ind_prim_gate=I["primary"]["gate"], defensible=(C["n_defensible"], I["n_defensible"]),
                 gate_fails=(C["gate_fail_counts"], I["gate_fail_counts"]),
                 classes=C["class_counts_defensible"],
                 controls={k: v.get("passed") for k, v in out["controls"].items()}, dsweep=out["d_sweep"],
                 runtime=out["runtime_s"])
    print(json.dumps(p4.jsonable(short), indent=1))


def stage_posthoc():
    """POST-HOC diagnostic (added AFTER the run showed V1 failing in 84/84 configurations; no verdict change):
    can ANY theta in the pre-registered bounds meet V1 (and V2) for the primary setting? Differential evolution on the
    worst-bin V1 violation, max_b |m_b - d_b| / tol_b (<= 1 means V1 holds), same pooled calibration CRN as the fit."""
    from scipy.optimize import differential_evolution
    t0 = time.time()
    tol = np.array([max(2.0, 0.25 * d) for d in CURVE_D[:6]] + [0.40 * CURVE_D[6]])
    out = {}
    for model, mapv in (("corr", "iso"), ("ind", "iso"), ("corr", "1d")):
        crn = cal_crn(900)
        for joint in (False, True):
            def worst(th):
                acc = cal_stats(th, model, mapv, 20.0, crn, per_array=False)
                m = acc.means()
                if not np.all(np.isfinite(m)):
                    return 1e3
                v = float((np.abs(m - CURVE_D) / tol).max())
                # joint: V2 pooled-r window [0.59, 0.79] as a normalised violation |r - 0.69| / 0.10 (<= 1 means inside)
                return max(v, abs(acc.r() - R_T) / 0.10) if joint else v
            B = B_CORR if model == "corr" else B_IND
            res = differential_evolution(worst, B, seed=SEED, maxiter=40, popsize=10, tol=1e-6, polish=False)
            acc = cal_stats(res.x, model, mapv, 20.0, crn)
            key = f"{model}|{mapv}|W20|{'V1+V2' if joint else 'V1 only'}"
            out[key] = dict(theta=res.x.tolist(), min_worst_violation=float(res.fun), achievable=bool(res.fun <= 1.0),
                            means=acc.means().tolist(), r_pooled=acc.r(), r_array_median=float(np.median(acc.r_arr)),
                            nfev=int(res.nfev))
            print(key, out[key], round(time.time() - t0), flush=True)
    # primary configurations re-run at the gate-reachable corr theta (descriptive; NOT a verdict, NOT a re-fit of PF size)
    thv = out["corr|iso|W20|V1+V2"]["theta"]
    fit_ph = dict(theta=dict(g=thv[0], sigma_f=thv[1], l=thv[2], sigma_n=thv[3]))
    rows = []
    for p in PARTS:
        r = run_config(p, "iso", 20.0, "disc", "part", fit_ph, base_draws(p, N_DISC), amps=False, want_pack=False)
        r["gate"] = gate(r["acc"], {p: r["U_low"]}, {p: r["U_high"]})
        rows.append(r)
    acc = PairAcc()
    for r in rows:
        acc.merge(r["acc"])
    pg = gate(acc, {r["part"]: r["U_low"] for r in rows}, {r["part"]: r["U_high"] for r in rows})
    out["primary_at_gate_reachable_theta_DESCRIPTIVE"] = dict(
        theta=fit_ph["theta"], gate=pg, K_low=q(np.concatenate([r["K_low"] for r in rows])),
        N_A=q(np.concatenate([r["N_A"] for r in rows])), K_high=q(np.concatenate([r["K_high"] for r in rows])),
        cls=cfg_class(np.concatenate([r["K_low"] for r in rows]), np.concatenate([r["K_high"] for r in rows])))
    print(json.dumps(p4.jsonable(out["primary_at_gate_reachable_theta_DESCRIPTIVE"]), indent=0), flush=True)
    with open(os.path.join(RES, "p5b_posthoc_v1_reachability.json"), "w") as f:
        json.dump(dict(note=stage_posthoc.__doc__, results=out, runtime_s=time.time() - t0), f, indent=1)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        print(json.dumps(selftest(), indent=1))
    elif "--stage" in sys.argv and sys.argv[sys.argv.index("--stage") + 1] == "fit":
        stage_fit()
    elif "--stage" in sys.argv and sys.argv[sys.argv.index("--stage") + 1] == "posthoc":
        stage_posthoc()
    else:
        stage_run()
