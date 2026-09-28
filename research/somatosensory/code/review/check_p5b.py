"""Reviewer check for P5b (cycle 3). Independent re-implementation from the prereg text; imports NO project code.
Reads only notes\\published-derived\\*.csv and the fitted theta values from results\\p5b_fits.json / p5b_posthoc_v1_reachability.json.
Output: stdout (saved as check_p5b_output.txt by the reviewer)."""
import csv
import json
import os

import numpy as np
from scipy.stats import norm

ROOT = r"C:\Users\mariu\neuro-company\research\somatosensory"
DATA = os.path.join(ROOT, "notes", "published-derived")
RES = os.path.join(ROOT, "code", "results")
rng = np.random.default_rng(777)

# ------------------------------------------------------------------ A. data checks
cur = [l for l in open(os.path.join(DATA, "greenspon2025_fig3e_cortical_vs_PF_distance_DIGITISED.csv")) if not l.startswith("#")]
rows = list(csv.DictReader(cur))
x_c = np.array([float(r["cortical_distance_bin_centre_mm"]) for r in rows])
d_c = np.array([float(r["mean_PF_centroid_distance_mm_DIGITISED"]) for r in rows])
notes_vals = np.array([3.1, 6.0, 8.0, 11.8, 18.2, 24.1, 26.6])   # notes\data_cycle3.md A1.4 and prereg section 2
edges = np.linspace(0, 4, 8)
print("A. curve CSV == notes/prereg values:", np.allclose(d_c, notes_vals),
      "| bin centres == linspace(0,4,8) centres:", np.allclose(x_c, (edges[:-1] + edges[1:]) / 2, atol=1e-3))
print("   2 mm point", d_c[3], "vs paper '2 mm cortex ~ 10 mm skin'; slope bins1-3", np.diff(d_c[:3]) / np.diff(x_c[:3]),
      "bins 4-6", np.diff(d_c[3:6]) / np.diff(x_c[3:6]))

geo = {}
for r in csv.DictReader(open(os.path.join(DATA, "greenspon2025_S1_array_channel_maps.csv"))):
    if r["wired"] == "1":
        geo.setdefault((r["subject_code"], r["array_name"][0]), []).append((float(r["x_mm"]), float(r["y_mm"])))
geo = {k: np.array(v) - np.array(v).mean(0) for k, v in geo.items()}
print("   arrays:", {k: v.shape[0] for k, v in geo.items()})
ref = set(map(tuple, np.round(geo[("BCI02", "M")], 6)))
same = {k: len(ref ^ set(map(tuple, np.round(v, 6)))) // 2 for k, v in geo.items()}   # number of differing sites
print("   wiring identical to BCI02 medial:", same)

# ------------------------------------------------------------------ model pieces (own implementation)
MU, SLO, SHI = np.log(2.5), np.log(2.5 / 0.3) / 1.645, np.log(11.3 / 2.5) / 1.645


def areas_cm2(shape):
    """rejection sampling of the two-piece log-normal truncated to [0.05, 40] cm2 (different method from coder's inverse CDF)"""
    out = np.empty(int(np.prod(shape)))
    k = 0
    while k < out.size:
        side = rng.random(out.size) < 0.5
        z = np.abs(rng.standard_normal(out.size))
        a = np.exp(MU + np.where(side, -SLO * z, SHI * z))
        a = a[(a >= 0.05) & (a <= 40)]
        m = min(a.size, out.size - k)
        out[k:k + m] = a[:m]
        k += m
    return out.reshape(shape)


aa = areas_cm2((400000,))
print("   V4 own area sampler quantiles 50/5/95:", np.round(np.percentile(aa, [50, 5, 95]), 3), "mean", round(aa.mean(), 2))


def lens(d, r1, r2):
    d = np.maximum(d, 1e-12)
    rs, rl = np.minimum(r1, r2), np.maximum(r1, r2)
    c1 = np.clip((d ** 2 + r1 ** 2 - r2 ** 2) / (2 * d * r1), -1, 1)
    c2 = np.clip((d ** 2 + r2 ** 2 - r1 ** 2) / (2 * d * r2), -1, 1)
    k = (-d + r1 + r2) * (d + r1 - r2) * (d - r1 + r2) * (d + r1 + r2)
    A = r1 ** 2 * np.arccos(c1) + r2 ** 2 * np.arccos(c2) - 0.5 * np.sqrt(np.maximum(k, 0))
    A = np.where(d >= r1 + r2, 0.0, A)
    return np.where(d <= rl - rs, np.pi * rs ** 2, A)


def neff(c, A):
    """c (n,m,2) mm, A (n,m) mm2 -> participation ratio"""
    r = np.sqrt(A / np.pi)
    d = np.sqrt(((c[:, :, None] - c[:, None]) ** 2).sum(-1))
    C = lens(d, r[:, :, None], r[:, None]) / np.sqrt(A[:, :, None] * A[:, None])
    idx = np.arange(A.shape[1])
    C[:, idx, idx] = 1.0
    return A.shape[1] ** 2 / (C ** 2).sum((1, 2)), (C ** 2).sum((1, 2))


def union_cm2(c, A, h=0.5):
    r = np.sqrt(A / np.pi)
    lo, hi = (c - r[:, None]).min(0), (c + r[:, None]).max(0)
    xs = np.arange(lo[0], hi[0] + h, h) + h / 2
    ys = np.arange(lo[1], hi[1] + h, h) + h / 2
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    cov = np.zeros(X.shape, bool)
    for (cx, cy), ri in zip(c, r):
        cov |= (X - cx) ** 2 + (Y - cy) ** 2 <= ri * ri
    return cov.sum() * h * h / 100.0


def chol(X, l):
    d2 = ((X[:, None] - X[None]) ** 2).sum(-1)
    return np.linalg.cholesky(np.exp(-d2 / (2 * l * l)) + 1e-8 * np.eye(len(X)))


def simulate(part, th, n=500, f=None, n_union=100, area_scale=1.0):
    code = {"C1": "BCI02", "P2": "CRS02", "P3": "CRS07"}[part]
    X1, X2 = geo[(code, "M")], geo[(code, "L")]
    nk = int(round((f if f is not None else {"C1": 0.75, "P2": 0.75, "P3": 0.42}[part]) * 32))
    g, sf, l, sn = th
    Lj, L2 = chol(np.vstack([X1, X2]), l), chol(X2, l)
    ang = rng.uniform(0, 2 * np.pi, n)
    R = np.stack([np.stack([np.cos(ang), -np.sin(ang)], -1), np.stack([np.sin(ang), np.cos(ang)], -1)], -2)  # (n,2,2)
    Xj = np.vstack([X1, X2])
    lin = g * np.einsum("nab,mb->nma", R, Xj)
    fj = sf * np.einsum("ij,njc->nic", Lj, rng.standard_normal((n, 64, 2)))
    f2 = sf * np.einsum("ij,njc->nic", L2, rng.standard_normal((n, 32, 2)))
    nug = sn * rng.standard_normal((n, 64, 2))
    low = lin + fj + nug
    high = low.copy()
    high[:, 32:] = lin[:, 32:] + f2 + nug[:, 32:]
    A = areas_cm2((n, 64)) * 100.0 * area_scale
    keep = np.concatenate([np.argsort(rng.random((n, 32)), 1)[:, :nk], 32 + np.argsort(rng.random((n, 32)), 1)[:, :nk]], 1)
    tk = lambda M: np.take_along_axis(M, keep[:, :, None], 1) if M.ndim == 3 else np.take_along_axis(M, keep, 1)
    cl, ch, Ak = tk(low), tk(high), tk(A)
    K_low, _ = neff(cl, Ak)
    n1, s1 = neff(ch[:, :nk], Ak[:, :nk])
    n2, s2 = neff(ch[:, nk:], Ak[:, nk:])
    K_high = (2 * nk) ** 2 / (s1 + s2)
    out = dict(K_low=K_low, K_high=K_high, N_A=np.concatenate([n1, n2]), high=high, X1=X1, X2=X2)
    if n_union:
        Ul = np.array([union_cm2(cl[k], Ak[k]) for k in range(n_union)])
        Uh = np.array([union_cm2(ch[k, :nk], Ak[k, :nk]) + union_cm2(ch[k, nk:], Ak[k, nk:]) for k in range(n_union)])
        out.update(U_low=Ul, U_high=Uh)
    return out


def pair_stats(sims, W=20.0):
    """V1 bin means (pair-pooled), pooled r, per-(draw,array) r over same-digit pairs; all 32 sites of each array"""
    allx, ally, rs = [], [], []
    bs, bn = np.zeros(7), np.zeros(7)
    for s in sims:
        for X, C in ((s["X1"], s["high"][:, :32]), (s["X2"], s["high"][:, 32:])):
            i, j = np.triu_indices(32, 1)
            dc = np.linalg.norm(X[i] - X[j], axis=1)
            ph = rng.uniform(0, W, C.shape[0])
            strip = np.floor((C[..., 0] + ph[:, None]) / W)
            sm = strip[:, i] == strip[:, j]
            ds = np.linalg.norm(C[:, i] - C[:, j], axis=-1)
            b = np.searchsorted(edges, dc, side="right") - 1
            for k in range(C.shape[0]):
                m = sm[k]
                x, y = dc[m], ds[k, m]
                allx.append(x); ally.append(y)
                ok = b[m] < 7
                np.add.at(bs, b[m][ok], y[ok]); np.add.at(bn, b[m][ok], 1)
                if m.sum() >= 3:
                    rs.append(np.corrcoef(x, y)[0, 1])
    x, y = np.concatenate(allx), np.concatenate(ally)
    return bs / bn, np.corrcoef(x, y)[0, 1], float(np.nanmedian(rs))


tol = np.array([max(2, 0.25 * d) for d in notes_vals[:6]] + [0.4 * notes_vals[6]])


def gate_report(tag, th, parts=("C1", "P2", "P3"), n=500, area_scale=1.0, n_union=100):
    sims = {p: simulate(p, th, n=n, area_scale=area_scale, n_union=n_union) for p in parts}
    m, r, rmed = pair_stats(sims.values())
    V1 = np.all(np.abs(m - notes_vals) <= tol)
    V2 = (0.59 <= r <= 0.79) and rmed > 0.40
    print(f"\n[{tag}] theta g,sf,l,sn = {np.round(th, 3)}  area_scale {area_scale}")
    print("   bin means", np.round(m, 2), " |dev|/tol", np.round(np.abs(m - notes_vals) / tol, 2), "V1", bool(V1))
    print(f"   pooled r {r:.3f}, median per-array r {rmed:.3f}  V2 {bool(V2)}")
    V3 = True
    for p, s in sims.items():
        if n_union:
            lo, hi = 0.7 * np.median(s["U_low"]), 1.3 * np.median(s["U_high"])
            U = {"C1": 12, "P2": 33, "P3": 30}[p]
            ok = lo <= U <= hi
            V3 &= ok
            print(f"   {p}: U_low med {np.median(s['U_low']):.1f}, U_high med {np.median(s['U_high']):.1f} cm2 -> V3 bracket "
                  f"[{lo:.1f}, {hi:.1f}] vs measured {U}: {'ok' if ok else 'FAIL'}")
    KL = np.concatenate([s["K_low"] for s in sims.values()])
    KH = np.concatenate([s["K_high"] for s in sims.values()])
    NA = np.concatenate([s["N_A"] for s in sims.values()])
    q = lambda v: np.round(np.percentile(v, [2.5, 50, 97.5]), 2)
    print("   N_A p2.5/med/p97.5", q(NA), " K_low", q(KL), " K_high", q(KH))
    for p, s in sims.items():
        print(f"     {p}: N_A med {np.median(s['N_A']):.2f}  K_low med {np.median(s['K_low']):.2f}  K_high med {np.median(s['K_high']):.2f}")
    return sims


fits = json.load(open(os.path.join(RES, "p5b_fits.json")))["fits"]
t = fits["corr|iso|W20|c+0"]["theta"]
th_fit = np.array([t["g"], t["sigma_f"], t["l"], t["sigma_n"]])
print("\nB. Independent re-implementation, primary configuration (corr, iso, W20, disc, participant f), fitted theta")
gate_report("primary @ pre-registered LS fit", th_fit)
ti = fits["ind|iso|W20|c+0"]["theta"]
gate_report("independent-scatter control @ its fit", np.array([ti["g"], 0.0, 1.0, ti["sigma_n"]]), n=300, n_union=60)
ph = json.load(open(os.path.join(RES, "p5b_posthoc_v1_reachability.json")))["results"]["corr|iso|W20|V1+V2"]["theta"]
gate_report("post-hoc V1+V2 theta", np.array(ph))

# ------------------------------------------------------------------ C. is V3 for C1 reachable at all under the pooled area model?
print("\nC. C1 union lower bound when ALL 48 PF centroids coincide (union = largest PF), pooled area model:")
mx = areas_cm2((20000, 48)).max(1)
print(f"   median max-area {np.median(mx):.1f} cm2 -> 0.7 x median = {0.7 * np.median(mx):.1f} cm2 vs measured 12 "
      f"(P(max area <= 12/0.7=17.1) = {np.mean(mx <= 17.14):.2f})")
mx64 = areas_cm2((20000, 64)).max(1)
print(f"   f = 1.0 (64 PFs): median max {np.median(mx64):.1f} -> 0.7 x = {0.7 * np.median(mx64):.1f}")
# single array union with zero spread: U_low >= union of one array, so the same bound holds
print("   => with the pooled area distribution, C1's V3 lower bound is ~>= 0.7 x (largest of 48 PFs) regardless of the map fit;")
for sc in (0.5, 0.35):
    s = simulate("C1", th_fit, n=60, area_scale=sc, n_union=60)
    print(f"   area x{sc}: C1 U_low median {np.median(s['U_low']):.1f} -> lo {0.7 * np.median(s['U_low']):.1f} vs 12")
# units sanity: model single PF of median area 2.5 cm2 has radius
print(f"   units: median PF radius = sqrt(250/pi) = {np.sqrt(250 / np.pi):.2f} mm; centroid spacing at 0.4 mm pitch ~ g*0.4 = "
      f"{th_fit[0] * 0.4:.1f} mm; palm 165 cm2 = disc radius {np.sqrt(16500 / np.pi):.1f} mm")
