"""Reviewer check for P5 (cycle 2). Does not modify any script or result. Written from the prereg text only
(no import of p5_spatial_capacity.py), own seeds, own formulas:
- layout: two 6 x 10 grids, 0.4 mm pitch, chequerboard 30 + 2 random non-chequerboard sites per array, arrays D apart
  along the short axis (coder's assumption) and, as an extra, along the long axis;
- lens area by the circular-segment formula (different algebra from the coder's); sphere overlap by Monte Carlo check;
- truncated log-normal by REJECTION sampling (coder: inverse CDF);
- sigma_c by bisection on the mean per-draw Pearson r (own 2000 draws);
- N_eff = 64^2 / sum C_ij^2, C_ij = lens / sqrt(A_i A_j);
- union area by Monte Carlo point sampling (coder: raster).
Compared with results\\p5_spatial_channels.json. Extra reviewer sensitivities (NOT prereg): sigma_c fitted on within-array
pairs only; sigma_c = 0; the sigma_c that makes the model union match the reported unions (~25 cm2).
"""
import json

import numpy as np

RES = r"C:\Users\mariu\neuro-company\research\somatosensory\code\results\p5_spatial_channels.json"
J = json.load(open(RES))
G, PITCH = 5.0, 0.4
rng0 = np.random.default_rng(777)

r_, c_ = np.meshgrid(np.arange(6), np.arange(10), indexing="ij")
r_, c_ = r_.ravel(), c_.ravel()
SITE = np.c_[(c_ - 4.5) * PITCH, (r_ - 2.5) * PITCH]
CHK = np.where((r_ + c_) % 2 == 0)[0]
OTH = np.where((r_ + c_) % 2 == 1)[0]


def layout(rng, n, D, axis=1):
    P = np.empty((n, 64, 2))
    off = np.zeros(2)
    off[axis] = D / 2
    for k in range(n):
        for a, sgn in ((0, -1), (1, 1)):
            s = np.r_[CHK, rng.choice(OTH, 2, replace=False)]
            P[k, 32 * a:32 * (a + 1)] = SITE[s] + sgn * off
    return P


def areas(rng, shape):
    out = np.empty(int(np.prod(shape)))
    i = 0
    while i < out.size:
        x = np.exp(np.log(2.5) + 1.10 * rng.standard_normal(out.size))
        x = x[(x >= 0.1) & (x <= 30.0)]
        k = min(x.size, out.size - i)
        out[i:i + k] = x[:k]
        i += k
    return out.reshape(shape) * 100.0   # mm2


def dist(P):
    return np.linalg.norm(P[:, :, None, :] - P[:, None, :, :], axis=-1)


def lens(d, R, r):
    """segment formula; R, r radii (broadcast)"""
    d, R, r = np.broadcast_arrays(d, R, r)
    out = np.zeros(d.shape)
    big, small = np.maximum(R, r), np.minimum(R, r)
    full = d <= big - small
    out[full] = np.pi * small[full] ** 2
    m = (~full) & (d < R + r)
    dd, a, b = d[m], R[m], r[m]
    x = (dd ** 2 + a ** 2 - b ** 2) / (2 * dd)          # distance from centre 1 to the chord
    h = np.sqrt(np.maximum(a ** 2 - x ** 2, 0))
    seg = lambda rad, t: rad ** 2 * np.arccos(np.clip(t / rad, -1, 1)) - t * np.sqrt(np.maximum(rad ** 2 - t ** 2, 0))
    out[m] = seg(a, x) + seg(b, dd - x)
    return out


def neff(cent, A):
    rad = np.sqrt(A / np.pi)
    C = lens(dist(cent), rad[:, :, None], rad[:, None, :]) / np.sqrt(A[:, :, None] * A[:, None, :])
    i = np.arange(64)
    C[:, i, i] = 1.0
    return 64.0 ** 2 / (C ** 2).sum((1, 2))


IU = np.triu_indices(64, 1)
WITHIN = (IU[0] < 32) == (IU[1] < 32)


def mean_r(P, Z, s, mask=None):
    de = dist(P)[:, IU[0], IU[1]]
    dc = dist(G * P + s * Z)[:, IU[0], IU[1]]
    if mask is not None:
        de, dc = de[:, mask], dc[:, mask]
    de = de - de.mean(1, keepdims=True)
    dc = dc - dc.mean(1, keepdims=True)
    return float(((de * dc).sum(1) / np.sqrt((de ** 2).sum(1) * (dc ** 2).sum(1))).mean())


def fit_sigma(P, Z, mask=None):
    lo, hi = 0.0, 50.0
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if mean_r(P, Z, mid, mask) > 0.69 else (lo, mid)
    return 0.5 * (lo + hi)


def summ(v):
    return f"median {np.median(v):6.2f}  p2.5 {np.percentile(v, 2.5):6.2f}  p97.5 {np.percentile(v, 97.5):6.2f}"


def cls(v):
    lo, hi = np.percentile(v, 2.5), np.percentile(v, 97.5)
    return "PASS" if lo >= 16 else ("FAIL" if hi < 16 else "INCONCLUSIVE")


def union_mc(cent, A, npts=40000, rng=rng0):
    out = np.empty(cent.shape[0])
    rad = np.sqrt(A / np.pi)
    for k in range(cent.shape[0]):
        lo = (cent[k] - rad[k, :, None]).min(0)
        hi = (cent[k] + rad[k, :, None]).max(0)
        pts = lo + (hi - lo) * rng.random((npts, 2))
        inside = np.zeros(npts, bool)
        for i in range(64):
            inside |= ((pts - cent[k, i]) ** 2).sum(1) <= rad[k, i] ** 2
        out[k] = inside.mean() * np.prod(hi - lo) / 100.0
    return out


# ---- 0. unit checks of the reviewer's own lens formula
t = [(0.0, 2.0, 3.0), (3.0, 3.0, 3.0), (2.2, 1.5, 3.1), (4.9, 2.0, 3.0)]
mc = np.random.default_rng(5).random((400000, 2))
for d, R, r in t:
    box_lo, box_hi = np.array([-R, -R]), np.array([R, R])
    p = box_lo + (box_hi - box_lo) * mc
    est = np.mean(((p ** 2).sum(1) <= R ** 2) & (((p - [d, 0]) ** 2).sum(1) <= r ** 2)) * (2 * R) ** 2
    print(f"lens d={d} R={R} r={r}: segment formula {float(lens(np.array(d), np.array(R), np.array(r))):.4f}  MC {est:.4f}")

# sphere overlap formula check by MC (r = 0.5, d = 0.566)
rs, dsp = 0.5, 0.566
q = np.random.default_rng(6).uniform(-rs, rs, (600000, 3))
q = q[(q ** 2).sum(1) <= rs ** 2]
frac_mc = np.mean(((q - [dsp, 0, 0]) ** 2).sum(1) <= rs ** 2)
frac_cf = np.pi * (4 * rs + dsp) * (2 * rs - dsp) ** 2 / 12 / (4 / 3 * np.pi * rs ** 3)
print(f"sphere overlap fraction r=0.5 d=0.566: closed form {frac_cf:.4f}  MC {frac_mc:.4f}")

# ---- 1. calibration (own draws)
rng = np.random.default_rng(12345)
Pc = layout(rng, 2000, 5.0)
Zc = rng.standard_normal((2000, 64, 2))
s_fit = fit_sigma(Pc, Zc)
s_within = fit_sigma(Pc, Zc, WITHIN)
print(f"\nsigma_c fit (all 2016 pairs, D 5): reviewer {s_fit:.3f}  coder {J['calibration']['sigma_c']:.3f}")
print(f"REVIEWER SENSITIVITY: sigma_c fitted on WITHIN-array pairs only (r = 0.69): {s_within:.3f} mm")
print(f"  r over all pairs at that sigma: {mean_r(Pc, Zc, s_within):.3f};  within-array r at coder sigma: "
      f"{mean_r(Pc, Zc, J['calibration']['sigma_c'], WITHIN):.3f}")

# ---- 2. main draws
n = 500
P5 = layout(rng, n, 5.0)
Z = rng.standard_normal((n, 64, 2))
A60 = areas(rng, (n, 64))
print("\nPF areas (cm2): median %.2f  p5 %.2f  p95 %.2f  (Greenspon: 2.5, 0.3, 11.3)" %
      tuple(np.percentile(A60 / 100, [50, 5, 95])))
ne = neff(G * P5 + s_fit * Z, A60)
pj = J["primary"]["neff"]
print(f"PRIMARY N_eff reviewer: {summ(ne)} -> {cls(ne)}")
print(f"PRIMARY N_eff coder   : median {pj['median']:6.2f}  p2.5 {pj['p2_5']:6.2f}  p97.5 {pj['p97_5']:6.2f} -> {J['verdict']}")

# ---- 3. a few robustness configurations vs coder
print("\nconfig                 reviewer                                     coder median/p2.5/p97.5 class")
for D in (3.0, 5.0, 8.0):
    P = layout(np.random.default_rng([1, int(D)]), n, D)
    for sm in (0.5, 1.0, 2.0):
        for I in (40, 100):
            v = neff(G * P + sm * J["calibration"]["sigma_c"] * Z, A60 * (I / 60) ** 1.43)
            key = f"D{D:g}_sig{sm:g}_I{I}"
            c = J["robustness"][key]
            print(f"{key:18s} {summ(v)} {cls(v):12s} | {c['median']:.2f}/{c['p2_5']:.2f}/{c['p97_5']:.2f} {c['class']}")

# ---- 4. union (V1) and controls
U = union_mc(G * P5[:100] + s_fit * Z[:100], A60[:100])
print(f"\nunion U (cm2, 100 draws, MC): median {np.median(U):.1f}  (coder median {J['primary']['union_cm2']['D5']['median']:.1f}; "
      f"reported data 12/33/30)")
tiny = neff(G * P5 + s_fit * Z, np.full((n, 64), 0.1))
print(f"tiny-PF (0.1 mm2): median {np.median(tiny):.2f} min {tiny.min():.2f} frac<63 {np.mean(tiny < 63):.3f}  "
      f"(coder min {J['controls']['tiny_pf']['neff']['min']:.2f}, frac {J['posthoc_tiny_pf_diagnostic']['frac_draws_below_63']})")
tiny0 = neff(G * P5, np.full((n, 64), 0.1))
print(f"tiny-PF at sigma_c = 0: min {tiny0.min():.3f}")
print("one fully coincident pair gives N_eff = 4096/66 =", round(4096 / 66, 2), "< 63: the >= 63 bound cannot tolerate ONE coincidence")
Rp = np.sqrt(16500 / np.pi)
rr = Rp * np.sqrt(rng.random((n, 64)))
th = 2 * np.pi * rng.random((n, 64))
nnull = neff(np.stack([rr * np.cos(th), rr * np.sin(th)], -1), A60)
print(f"no-somatotopy null median {np.median(nnull):.1f} (coder {J['controls']['no_somatotopy_null']['neff']['median']:.1f})")

# ---- 5. cortical N_eff (Stoney power law), own sphere formula
def sphere_neff(P, rad):
    d = dist(P)
    V = np.where(d < 2 * rad, np.pi * (4 * rad + d) * (2 * rad - d) ** 2 / 12, 0.0)
    C = V / (4 / 3 * np.pi * rad ** 3)
    return 4096 / (C ** 2).sum((1, 2))


print("\ncortical N_eff median, reviewer vs coder:")
for I in (20, 60, 100):
    rad = 0.1 * (I / 10) ** 0.653
    v = sphere_neff(P5, rad)
    print(f"  Stoney I={I}: r={rad:.3f} mm  {np.median(v):.1f} vs {J['cortical']['stoney_power_law'][str(I)]['median']:.1f}")
for K in (100, 1000):
    v = sphere_neff(P5, np.sqrt(60 / K))
    print(f"  Tehovnik K={K}: {np.median(v):.1f} vs {J['cortical']['tehovnik_60uA'][str(K)]['median']:.1f}")

# ---- 6. reviewer sensitivities (NOT prereg)
print("\nREVIEWER SENSITIVITIES (not prereg):")
for lab, s in (("sigma_c = 0 (pure somatotopy)", 0.0), ("sigma_c within-array fit", s_within)):
    v = neff(G * P5 + s * Z, A60)
    print(f"  {lab:32s} ({s:.2f} mm): {summ(v)} -> {cls(v)}")
PLc = layout(np.random.default_rng(4), 1000, 5.0, axis=0)
PL = layout(np.random.default_rng(3), n, 5.0, axis=0)
sL = fit_sigma(PLc, Zc[:1000])
v = neff(G * PL + sL * Z, A60)
print(f"  arrays separated along LONG axis, sigma re-fit {sL:.2f}: {summ(v)} -> {cls(v)}")
for sm in (0.25, 0.5):
    Us = union_mc(G * P5[:60] + sm * s_fit * Z[:60], A60[:60])
    v = neff(G * P5 + sm * s_fit * Z, A60)
    print(f"  sigma_c x{sm}: union median {np.median(Us):.1f} cm2, N_eff {summ(v)} -> {cls(v)}")

# split-normal PF areas that hit Greenspon's 5th/95th percentiles exactly (sigma 1.289 below the median, 0.917 above)
zz = rng.standard_normal((n, 64))
Asn = np.clip(np.exp(np.log(2.5) + np.where(zz < 0, 1.289, 0.917) * zz), 0.1, 30.0) * 100
v = neff(G * P5 + s_fit * Z, Asn)
print(f"  split-normal PF areas (p5/p95 = {np.percentile(Asn / 100, 5):.2f}/{np.percentile(Asn / 100, 95):.2f} cm2): {summ(v)} -> {cls(v)}")
