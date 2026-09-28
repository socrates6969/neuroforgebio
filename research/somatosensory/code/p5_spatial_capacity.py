"""P5: effectively independent spatial channels of 64 wired S1 electrodes (projected-field overlap), H7.

Implements prereg\\P5_spatial_channel_capacity.md (FIXED). Theory/simulation on published summary numbers (quoted in the prereg).
Interpretations/deviations: code\\DEVIATIONS.md, section P5. Reuses code\\p4_pooling_capacity.py (imported, unchanged).

Run:  python p5_spatial_capacity.py            (self-tests + full run)
      python p5_spatial_capacity.py --selftest
"""
import json
import os
import sys
import time

import numpy as np
from scipy.stats import norm

BASE = r"C:\Users\mariu\neuro-company\research\somatosensory\code"
sys.path.insert(0, BASE)
import p4_pooling_capacity as p4  # noqa: E402

RES = os.path.join(BASE, "results")
FIG = os.path.join(BASE, "figures")
SEED = 20260926

PITCH = 0.4                  # mm
NROW, NCOL = 6, 10
G = 5.0                      # mm skin per mm cortex
R_TARGET = 0.69
PF_MED_CM2, PF_SIG = 2.5, 1.10
PF_LO, PF_HI = 0.1, 30.0     # cm2 truncation
PF_EXP = 1.43                # area ~ I^1.43
I_LIST = [40, 60, 80, 100]
D_LIST = [3.0, 5.0, 8.0]
D0 = 5.0
SIG_MULT = [1.0, 0.5, 2.0]
NDRAW = 500
NCAL = 2000
N_E = 64
THRESH = 16
PALM_CM2 = 165.0
V1_RANGE = (6.0, 66.0)       # cm2
RASTER = 0.5                 # mm
W0 = 0.162
IU = np.triu_indices(N_E, 1)  # 2016 pairs


# ----------------------------------------------------------------------------- geometry
def array_sites():
    rr, cc = np.meshgrid(np.arange(NROW), np.arange(NCOL), indexing="ij")
    rr, cc = rr.ravel(), cc.ravel()
    xy = np.stack([(cc - (NCOL - 1) / 2) * PITCH, (rr - (NROW - 1) / 2) * PITCH], 1)
    even = (rr + cc) % 2 == 0
    return xy, np.nonzero(even)[0], np.nonzero(~even)[0]


SITES, EVEN, ODD = array_sites()


def draw_layout(rng, n):
    """per draw: site indices for 2 arrays (30 chequerboard + 2 random odd sites each) -> (n, 2, 32) index array"""
    idx = np.empty((n, 2, 32), int)
    for k in range(n):
        for a in range(2):
            idx[k, a] = np.concatenate([EVEN, rng.choice(ODD, 2, replace=False)])
    return idx


def positions(idx, D):
    """cortical positions (n, 64, 2) mm; arrays separated by D along y (perpendicular to the long axis)"""
    p0 = SITES[idx[:, 0]] + np.array([0.0, -D / 2])
    p1 = SITES[idx[:, 1]] + np.array([0.0, D / 2])
    return np.concatenate([p0, p1], 1)


def trunc_lognorm_area_mm2(u):
    """inverse-CDF sample of log-normal(median 2.5 cm2, sigma 1.10) truncated to [0.1, 30] cm2; returns mm2"""
    mu = np.log(PF_MED_CM2)
    flo, fhi = norm.cdf((np.log(PF_LO) - mu) / PF_SIG), norm.cdf((np.log(PF_HI) - mu) / PF_SIG)
    return np.exp(mu + PF_SIG * norm.ppf(flo + u * (fhi - flo))) * 100.0


def pdist(P):
    """(n, m, 2) -> (n, m, m) distances"""
    d = P[:, :, None, :] - P[:, None, :, :]
    return np.sqrt((d ** 2).sum(-1))


def pearson_rows(a, b):
    a = a - a.mean(1, keepdims=True)
    b = b - b.mean(1, keepdims=True)
    return (a * b).sum(1) / np.sqrt((a ** 2).sum(1) * (b ** 2).sum(1))


# ----------------------------------------------------------------------------- overlap
def lens_area(d, r1, r2):
    """intersection area of two discs (closed form), broadcasting"""
    d, r1, r2 = np.broadcast_arrays(np.asarray(d, float), np.asarray(r1, float), np.asarray(r2, float))
    out = np.zeros(d.shape)
    inside = d <= np.abs(r1 - r2)
    out[inside] = np.pi * np.minimum(r1, r2)[inside] ** 2
    part = (~inside) & (d < r1 + r2)
    if part.any():
        dd, a, b = d[part], r1[part], r2[part]
        c1 = np.clip((dd ** 2 + a ** 2 - b ** 2) / (2 * dd * a), -1, 1)
        c2 = np.clip((dd ** 2 + b ** 2 - a ** 2) / (2 * dd * b), -1, 1)
        k = np.sqrt(np.clip((-dd + a + b) * (dd + a - b) * (dd - a + b) * (dd + a + b), 0, None))
        out[part] = a ** 2 * np.arccos(c1) + b ** 2 * np.arccos(c2) - 0.5 * k
    return out


def neff_from_C(C):
    n = C.shape[-1]
    return n ** 2 / (C ** 2).sum((-1, -2))


def overlap_C(cent, area):
    """cent (n,64,2) mm, area (n,64) mm2 -> C (n,64,64)"""
    r = np.sqrt(area / np.pi)
    d = pdist(cent)
    L = lens_area(d, r[:, :, None], r[:, None, :])
    C = L / np.sqrt(area[:, :, None] * area[:, None, :])
    idx = np.arange(cent.shape[1])
    C[:, idx, idx] = 1.0
    return C


def neff_perceptual(cent, area):
    return neff_from_C(overlap_C(cent, area))


def sphere_C(pos, r):
    d = pdist(pos)
    V = np.where(d < 2 * r, np.pi * (4 * r + d) * (2 * r - d) ** 2 / 12.0, 0.0)
    return V / (4.0 / 3.0 * np.pi * r ** 3)


def packing(cent, area):
    """greedy maximal set of pairwise-disjoint PFs, smallest area first"""
    out = np.zeros(cent.shape[0], int)
    r = np.sqrt(area / np.pi)
    for k in range(cent.shape[0]):
        order = np.argsort(area[k], kind="stable")
        chosen = []
        for i in order:
            if all(np.hypot(*(cent[k, i] - cent[k, j])) >= r[k, i] + r[k, j] for j in chosen):
                chosen.append(i)
        out[k] = len(chosen)
    return out


def union_area(cent, area, h=RASTER):
    """raster estimate (mm2) of the union of discs, per draw"""
    out = np.zeros(cent.shape[0])
    r = np.sqrt(area / np.pi)
    for k in range(cent.shape[0]):
        lo = (cent[k] - r[k, :, None]).min(0)
        hi = (cent[k] + r[k, :, None]).max(0)
        xs = np.arange(lo[0] + h / 2, hi[0], h, dtype=np.float32)
        ys = np.arange(lo[1] + h / 2, hi[1], h, dtype=np.float32)
        X, Y = np.meshgrid(xs, ys, indexing="ij")
        cov = np.zeros(X.shape, bool)
        for i in range(cent.shape[1]):
            cx, cy, ri = cent[k, i, 0], cent[k, i, 1], r[k, i]
            ix = slice(max(0, int((cx - ri - lo[0]) / h) - 1), int((cx + ri - lo[0]) / h) + 2)
            iy = slice(max(0, int((cy - ri - lo[1]) / h) - 1), int((cy + ri - lo[1]) / h) + 2)
            sub = (X[ix, iy] - cx) ** 2 + (Y[ix, iy] - cy) ** 2 <= ri ** 2
            cov[ix, iy] |= sub
        out[k] = cov.sum() * h * h
    return out


def raster_lens(d, r1, r2, n=1500, h=None):
    """raster estimate of a lens area: disc 1 at 0, disc 2 at (d, 0); raster over the lens bounding box
    (n x n points) or with fixed spacing h over the same box"""
    xlo, xhi = max(-r1, d - r2), min(r1, d + r2)
    yh = min(r1, r2)
    if h is None:
        hx, hy = (xhi - xlo) / n, 2 * yh / n
    else:
        hx = hy = h
    xs = np.arange(xlo + hx / 2, xhi, hx)
    ys = np.arange(-yh + hy / 2, yh, hy)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    return float(((X ** 2 + Y ** 2 <= r1 ** 2) & ((X - d) ** 2 + Y ** 2 <= r2 ** 2)).sum() * hx * hy)


# ----------------------------------------------------------------------------- calibration
def mean_r(idx, Z, sigma, D):
    P = positions(idx, D)
    de = pdist(P)[:, IU[0], IU[1]]
    dc = pdist(G * P + sigma * Z)[:, IU[0], IU[1]]
    return float(pearson_rows(de, dc).mean())


def calibrate(D, rng, n=NCAL):
    idx = draw_layout(rng, n)
    Z = rng.standard_normal((n, N_E, 2))
    lo, hi = 0.0, 50.0
    r_lo, r_hi = mean_r(idx, Z, lo, D), mean_r(idx, Z, hi, D)
    reachable = (r_lo - R_TARGET) * (r_hi - R_TARGET) < 0
    if not reachable:
        return dict(sigma_c=None, reachable=False, r_at_0=r_lo, r_at_50=r_hi)
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        if mean_r(idx, Z, mid, D) > R_TARGET:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-4:
            break
    s = 0.5 * (lo + hi)
    return dict(sigma_c=s, reachable=True, r_at_0=r_lo, r_at_50=r_hi, r_at_fit=mean_r(idx, Z, s, D))


# ----------------------------------------------------------------------------- stats helpers
def summ(v, rng=None, nboot=1000):
    v = np.asarray(v, float)
    out = dict(median=float(np.median(v)), mean=float(v.mean()), p2_5=float(np.percentile(v, 2.5)),
               p97_5=float(np.percentile(v, 97.5)), min=float(v.min()), max=float(v.max()))
    if rng is not None:
        b = rng.integers(0, v.size, (nboot, v.size))
        bp = np.percentile(v[b], 2.5, axis=1)
        bm = np.median(v[b], axis=1)
        out["p2_5_boot_ci95"] = [float(np.percentile(bp, 2.5)), float(np.percentile(bp, 97.5))]
        out["median_boot_ci95"] = [float(np.percentile(bm, 2.5)), float(np.percentile(bm, 97.5))]
    return out


def classify(s):
    if s["p2_5"] >= THRESH:
        return "PASS"
    if s["p97_5"] < THRESH:
        return "FAIL"
    return "INCONCLUSIVE"


def capacity_for(neff):
    K = int(np.floor(neff))
    if K < 1:
        return dict(K=K, total_bits=0.0)
    M = N_E / K
    n = p4.n_levels(M, W0, 0.0)
    c = p4.capacity_M(M, W0, 0.0)["C"] if n >= 2 else 0.0
    return dict(K=K, M_per_group=M, levels_per_group=float(n), C_per_group=float(c), total_bits=float(K * c))


# ----------------------------------------------------------------------------- self tests
def selftest():
    res = {}
    # lens closed form: limits and a known value
    r = 3.0
    assert abs(lens_area(0.0, 2.0, 3.0) - np.pi * 4) < 1e-12
    assert lens_area(5.0, 2.0, 3.0) == 0.0 and lens_area(7.0, 2.0, 3.0) == 0.0
    known = 2 * r ** 2 * np.arccos(r / (2 * r)) - (r / 2) * np.sqrt(4 * r ** 2 - r ** 2)   # equal radii, d = r
    res["lens_equal_radii_err"] = float(abs(lens_area(r, r, r) - known))
    assert res["lens_equal_radii_err"] < 1e-12
    assert abs(lens_area(2.2, 1.5, 3.1) - lens_area(2.2, 3.1, 1.5)) < 1e-12
    # N_eff bounds
    assert abs(neff_from_C(np.eye(64)[None])[0] - 64) < 1e-12
    assert abs(neff_from_C(np.ones((1, 64, 64)))[0] - 1) < 1e-12
    # sphere overlap: d = 0 -> 1, d >= 2r -> 0
    P = np.array([[[0, 0], [0, 0], [1, 0]]], float)
    Cs = sphere_C(P, 0.5)
    assert abs(Cs[0, 0, 1] - 1) < 1e-12 and Cs[0, 0, 2] == 0.0
    # layout
    assert EVEN.size == 30 and ODD.size == 30
    lay = draw_layout(np.random.default_rng(1), 5)
    for k in range(5):
        for a in range(2):
            assert np.unique(lay[k, a]).size == 32
    pos = positions(lay, 3.0)
    dmin = pdist(pos)[:, IU[0], IU[1]].min()
    res["min_electrode_distance_mm_Darr3"] = float(dmin)
    assert dmin >= PITCH - 1e-9
    # nearest chequerboard neighbours are 0.566 mm apart
    se = SITES[EVEN]
    dd = np.sqrt(((se[:, None] - se[None]) ** 2).sum(-1)) + np.eye(30) * 99
    res["chequerboard_nn_mm"] = float(dd.min())
    assert abs(dd.min() - PITCH * np.sqrt(2)) < 1e-9
    # truncated log-normal: median of samples ~ within-truncation median, bounds
    a = trunc_lognorm_area_mm2(np.random.default_rng(2).random(200000)) / 100
    res["pf_sample_median_cm2"] = float(np.median(a))
    res["pf_sample_p5_p95_cm2"] = [float(np.percentile(a, 5)), float(np.percentile(a, 95))]
    assert a.min() >= PF_LO - 1e-9 and a.max() <= PF_HI + 1e-9 and abs(np.median(a) - 2.5) < 0.1
    # pearson helper
    x = np.random.default_rng(3).random((2, 50))
    assert abs(pearson_rows(x, 2 * x + 1)[0] - 1) < 1e-12
    # union raster: one disc of area 250 mm2
    u = union_area(np.zeros((1, 1, 2)), np.array([[250.0]]))
    res["union_single_disc_rel_err"] = float(u[0] / 250 - 1)
    assert abs(u[0] / 250 - 1) < 0.01
    res["all_passed"] = True
    return res


def lens_check(rng, n=100):
    errs, errs05 = [], []
    rs = np.sqrt(trunc_lognorm_area_mm2(rng.random((n, 2))) / np.pi)
    for k in range(n):
        r1, r2 = rs[k]
        d = rng.uniform(abs(r1 - r2), r1 + r2)
        cf = float(lens_area(d, r1, r2))
        errs.append(raster_lens(d, r1, r2) / cf - 1)
        errs05.append(raster_lens(d, r1, r2, h=RASTER) / cf - 1)
    errs, errs05 = np.abs(errs), np.abs(errs05)
    return dict(n_pairs=n, max_rel_err_fine=float(errs.max()), median_rel_err_fine=float(np.median(errs)),
                max_rel_err_0p5mm=float(errs05.max()), median_rel_err_0p5mm=float(np.median(errs05)),
                n_0p5mm_over_1pct=int((errs05 > 0.01).sum()), passed=bool(errs.max() < 0.01))


# ----------------------------------------------------------------------------- figures
def figures(out, ex):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 2, figsize=(13, 5))
    ax = axs[0]
    for D, col in zip(D_LIST, ["C0", "C1", "C2"]):
        for sm, ls in zip(SIG_MULT, ["-", "--", ":"]):
            s = [out["robustness"][f"D{D:g}_sig{sm:g}_I{I}"] for I in I_LIST]
            med = [x["median"] for x in s]
            ax.plot(I_LIST, med, ls, color=col, marker="o", ms=3, label=f"D_arr={D:g} mm, sigma_c x{sm:g}")
            if sm == 1.0:
                ax.fill_between(I_LIST, [x["p2_5"] for x in s], [x["p97_5"] for x in s], color=col, alpha=0.12)
    ax.axhline(THRESH, color="k", ls="--", lw=1, label="H7 threshold N_eff = 16 (P4 K = 16)")
    ax.set_xlabel("stimulus amplitude I (uA; PF area scaled by (I/60)^1.43)")
    ax.set_ylabel("perceptual N_eff (participation ratio of PF overlap)")
    ax.set_title(f"Perceptual N_eff, 64 electrodes (median; band 2.5-97.5% for fitted sigma_c)\nprimary verdict: {out['verdict']}", fontsize=9)
    ax.set_ylim(0, max(20, ax.get_ylim()[1]))
    ax.legend(fontsize=6)
    ax = axs[1]
    I_c = [20, 40, 60, 80, 100]
    ax.plot(I_c, [out["cortical"]["stoney_power_law"][str(I)]["median"] for I in I_c], "o-", label="Stoney-based r(I) = 0.1 mm (I/10)^0.653")
    for Kt, mk in zip([100, 1000, 4000], ["s", "^", "v"]):
        ax.plot([60], [out["cortical"]["tehovnik_60uA"][str(Kt)]["median"]], mk, ms=8, label=f"Tehovnik I = K r^2, K = {Kt} uA/mm2")
    ax.plot(I_LIST, [out["robustness"][f"D5_sig1_I{I}"]["median"] for I in I_LIST], "k-o", ms=3, label="perceptual (PF overlap), primary")
    ax.axhline(THRESH, color="k", ls="--", lw=1)
    ax.set_xlabel("stimulus amplitude I (uA)")
    ax.set_ylabel("N_eff (median over draws)")
    ax.set_ylim(0, 66)
    ax.set_title("Cortical current-spread N_eff vs perceptual N_eff (D_arr = 5 mm)", fontsize=9)
    ax.legend(fontsize=7)
    fig.tight_layout()
    for e in ("png", "svg"):
        fig.savefig(os.path.join(FIG, f"p5_neff_vs_amplitude.{e}"), dpi=150)
    plt.close(fig)
    # example PF map
    cent, area = ex
    fig, ax = plt.subplots(figsize=(7, 7))
    r = np.sqrt(area / np.pi)
    for i in range(N_E):
        ax.add_patch(plt.Circle(cent[i], r[i], fill=False, color="C0" if i < 32 else "C3", alpha=0.5, lw=0.8))
    ax.plot(cent[:32, 0], cent[:32, 1], ".", color="C0", label="array 1 PF centroids")
    ax.plot(cent[32:, 0], cent[32:, 1], ".", color="C3", label="array 2 PF centroids")
    pr = np.sqrt(PALM_CM2 * 100 / np.pi)
    ax.add_patch(plt.Circle((0, 0), pr, fill=False, ls="--", color="gray"))
    ax.plot([], [], "--", color="gray", label="disc of palm area 165 cm2 (scale reference)")
    ax.set_aspect("equal")
    lim = max(np.abs(cent).max() + r.max(), pr) * 1.05
    ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim)
    ax.set_xlabel("skin x (mm)"); ax.set_ylabel("skin y (mm)")
    ax.set_title("P5 example draw (primary): projected fields as discs", fontsize=9)
    ax.legend(fontsize=7, loc="upper right")
    fig.tight_layout()
    for e in ("png", "svg"):
        fig.savefig(os.path.join(FIG, f"p5_example_pfs.{e}"), dpi=150)
    plt.close(fig)


# ----------------------------------------------------------------------------- main
def main():
    t0 = time.time()
    st = selftest()
    print("self-tests passed:", json.dumps(st), flush=True)
    if "--selftest" in sys.argv:
        return
    rng_cal = np.random.default_rng([SEED, 5, 1])
    rng = np.random.default_rng([SEED, 5, 2])
    rng_b = np.random.default_rng([SEED, 5, 3])
    out = dict(prereg="prereg/P5_spatial_channel_capacity.md", seed=SEED, ndraw=NDRAW, selftest=st)
    out["lens_check"] = lens_check(np.random.default_rng([SEED, 5, 4]))
    assert out["lens_check"]["passed"], out["lens_check"]

    # 1. calibration (primary D once; re-fitted variants for D 3/8 reported)
    cal = calibrate(D0, rng_cal)
    out["calibration"] = cal
    V2 = bool(cal["reachable"] and 0 <= cal["sigma_c"] <= 50)
    refit = {f"D{D:g}": calibrate(D, np.random.default_rng([SEED, 5, 10 + i])) for i, D in enumerate((3.0, 8.0))}
    out["calibration_refit_other_D"] = refit
    sig = cal["sigma_c"]
    print("calibrated sigma_c", cal, time.time() - t0, flush=True)

    # 2. base draws (common random numbers across configurations)
    idx = draw_layout(rng, NDRAW)
    Z = rng.standard_normal((NDRAW, N_E, 2))
    A60 = trunc_lognorm_area_mm2(rng.random((NDRAW, N_E)))
    cents = {D: G * positions(idx, D) + sig * Z for D in D_LIST}
    # observed r at the primary on the main draws
    Pm = positions(idx, D0)
    out["r_main_draws_primary"] = float(pearson_rows(pdist(Pm)[:, IU[0], IU[1]], pdist(cents[D0])[:, IU[0], IU[1]]).mean())

    # 3. primary
    ne = neff_perceptual(cents[D0], A60)
    prim = summ(ne, rng_b)
    pk = packing(cents[D0], A60)
    t = time.time()
    U = {D: union_area(G * positions(idx, D) + sig * Z, A60) / 100.0 for D in D_LIST}   # cm2
    out["timing_union_s"] = time.time() - t
    V1 = {f"D{D:g}": bool(V1_RANGE[0] <= np.median(U[D]) <= V1_RANGE[1]) for D in D_LIST}
    out["primary"] = dict(neff=prim, packing=summ(pk), union_cm2={f"D{D:g}": summ(U[D]) for D in D_LIST})
    out["gates"] = dict(V1_primary=V1["D5"], V1_by_D=V1, V2=V2, V1_range_cm2=V1_RANGE)
    abandon = not any(V1.values())
    if not (V1["D5"] and V2):
        verdict = "ABANDON (section 6)" if abandon else "GATE FAILED (V1/V2) -> section 6; not abandoned (V1 holds at another D_arr)"
    else:
        verdict = classify(prim)
    out["verdict"] = verdict
    out["abandonment_triggered"] = bool(abandon)
    print("primary", verdict, prim, out["gates"], time.time() - t0, flush=True)

    # 4. robustness grid (36)
    rob = {}
    for D in D_LIST:
        for sm in SIG_MULT:
            c = G * positions(idx, D) + sm * sig * Z
            for I in I_LIST:
                s = summ(neff_perceptual(c, A60 * (I / 60.0) ** PF_EXP))
                s["class"] = classify(s)
                rob[f"D{D:g}_sig{sm:g}_I{I}"] = s
    out["robustness"] = rob
    prim_class = classify(prim)
    n_same = sum(v["class"] == prim_class for v in rob.values())
    out["robustness_summary"] = dict(primary_class=prim_class, n_same=int(n_same), n_total=len(rob),
                                     robust=bool(n_same >= 0.7 * len(rob)),
                                     counts={c: int(sum(v["class"] == c for v in rob.values())) for c in ("PASS", "FAIL", "INCONCLUSIVE")},
                                     max_median_neff=float(max(v["median"] for v in rob.values())),
                                     max_p97_5_neff=float(max(v["p97_5"] for v in rob.values())))
    # re-fitted sigma for D 3 / 8
    out["refit_neff"] = {}
    for D in (3.0, 8.0):
        s_r = refit[f"D{D:g}"]["sigma_c"]
        if s_r is not None:
            out["refit_neff"][f"D{D:g}"] = dict(sigma_c=s_r, neff=summ(neff_perceptual(G * positions(idx, D) + s_r * Z, A60)))

    # 5. controls
    ctrl = {}
    ne_tiny = neff_perceptual(cents[D0], np.full_like(A60, 0.1))
    ctrl["tiny_pf"] = dict(neff=summ(ne_tiny), passed=bool(ne_tiny.min() >= 63))
    ne_id = neff_perceptual(np.zeros_like(cents[D0][:5]), np.full((5, N_E), 250.0))
    ctrl["identical_pf"] = dict(max_abs_dev_from_1=float(np.abs(ne_id - 1).max()), passed=bool(np.abs(ne_id - 1).max() < 1e-9))
    Rpalm = np.sqrt(PALM_CM2 * 100 / np.pi)
    rr = Rpalm * np.sqrt(rng.random((NDRAW, N_E)))
    th = 2 * np.pi * rng.random((NDRAW, N_E))
    null_c = np.stack([rr * np.cos(th), rr * np.sin(th)], -1)
    ne_null = neff_perceptual(null_c, A60)
    ctrl["no_somatotopy_null"] = dict(neff=summ(ne_null), frac_draws_somatotopic_lower=float((ne < ne_null).mean()),
                                      passed=bool(np.median(ne) < np.median(ne_null)))
    perm = np.argsort(rng.random((NDRAW, N_E)), 1)
    ne_sh = neff_perceptual(cents[D0], np.take_along_axis(A60, perm, 1))
    rel = np.median(ne_sh) / np.median(ne) - 1
    ctrl["area_shuffle"] = dict(neff=summ(ne_sh), rel_change_median=float(rel),
                                per_draw_rel_change=summ(ne_sh / ne - 1), passed=bool(abs(rel) < 0.10))
    ctrl["lens_closed_form_vs_raster"] = out["lens_check"]
    out["controls"] = ctrl
    out["controls_all_passed"] = bool(all(v["passed"] for v in ctrl.values()))
    # POST-HOC diagnostic (added after the first run showed the tiny-PF control failing; the control result above is unchanged)
    ne_tiny0 = neff_perceptual(G * positions(idx, D0), np.full_like(A60, 0.1))
    dcen = pdist(cents[D0])[:, IU[0], IU[1]]
    out["posthoc_tiny_pf_diagnostic"] = dict(
        frac_draws_below_63=float((ne_tiny < 63).mean()),
        tiny_pf_sigma_c_0_min_neff=float(ne_tiny0.min()),
        mean_pairs_per_draw_centroids_closer_than_2r_tiny=float((dcen < 2 * np.sqrt(0.1 / np.pi)).sum(1).mean()),
        note="tiny PFs (r = 0.18 mm) overlap only when two noisy centroids (sigma_c ~ 6.5 mm) land < 0.36 mm apart")

    # 6. cortical current-spread N_eff
    Pc = positions(idx, D0)
    cort = {"stoney_power_law": {}, "tehovnik_60uA": {}}
    for I in (20, 40, 60, 80, 100):
        r = 0.1 * (I / 10.0) ** 0.653
        cort["stoney_power_law"][str(I)] = summ(neff_from_C(sphere_C(Pc, r))) | {"radius_mm": r}
    for Kt in (100, 1000, 4000):
        r = np.sqrt(60.0 / Kt)
        cort["tehovnik_60uA"][str(Kt)] = summ(neff_from_C(sphere_C(Pc, r))) | {"radius_mm": float(r)}
    out["cortical"] = cort

    # 7. capacity consequence (descriptive upper bound)
    out["capacity"] = dict(at_median=capacity_for(prim["median"]), at_p2_5=capacity_for(prim["p2_5"]),
                           at_p97_5=capacity_for(prim["p97_5"]),
                           P4_K16_reference_bits=capacity_for(16.0)["total_bits"],
                           P4_pooled_K1_bits=capacity_for(1.0)["total_bits"])
    out["runtime_s"] = time.time() - t0
    with open(os.path.join(RES, "p5_spatial_channels.json"), "w") as f:
        json.dump(p4.jsonable(out), f, indent=1)
    figures(out, (cents[D0][0], A60[0]))
    short = dict(verdict=verdict, sigma_c=sig, V1=V1, V2=V2, primary=prim, packing=out["primary"]["packing"],
                 union=out["primary"]["union_cm2"], robustness=out["robustness_summary"], refit=out["refit_neff"],
                 controls={k: v["passed"] for k, v in ctrl.items()}, null_median=ctrl["no_somatotopy_null"]["neff"]["median"],
                 shuffle_rel=rel, cortical={k: {kk: round(vv["median"], 1) for kk, vv in v.items()} for k, v in cort.items()},
                 capacity=out["capacity"], runtime=out["runtime_s"])
    print(json.dumps(p4.jsonable(short), indent=1))


if __name__ == "__main__":
    main()
