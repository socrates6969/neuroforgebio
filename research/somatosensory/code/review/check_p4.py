"""Reviewer check for P4: closed-form A/B numbers and an independent Blahut-Arimoto (finer grid, fixed long iteration)."""
import json
import numpy as np
from scipy.stats import norm

w = 0.162; z = norm.ppf(0.75); s = np.log1p(w) / (z * np.sqrt(2))
print("kappa_hat(w)", {ww: round(1 - 8.5 * np.log1p(ww) / np.log(4), 4) for ww in (0.128, 0.162, 0.225, 0.268)})
print("N4 kappa0", {ww: round(11 + np.log(4) / np.log1p(ww), 3) for ww in (0.128, 0.162, 0.225, 0.268)})
print("M* kappa0", {ww: round(np.exp(36.5 * np.log1p(ww)), 1) for ww in (0.128, 0.162, 0.225, 0.268)})
print("model K N4", {q: round((400 - q) / ((100 - q) / 11), 2) for q in (20, 24, 35)})

def ba(range_over_s, nx=300, ny=900, it=15000):
    x = np.linspace(0, range_over_s, nx); y = np.linspace(-6, range_over_s + 6, ny)
    e = np.concatenate([[-np.inf], (y[1:] + y[:-1]) / 2, [np.inf]])
    P = np.diff(norm.cdf(e[None, :] - x[:, None]), axis=1); P /= P.sum(1, keepdims=True)
    lP = np.log(np.maximum(P, 1e-300)); r = np.full(nx, 1 / nx)
    for _ in range(it):
        q = r @ P; D = (P * (lP - np.log(np.maximum(q, 1e-300)))).sum(1)
        c = np.exp(D - D.max()); r = r * c / (r @ c)
    q = r @ P; D = (P * (lP - np.log(np.maximum(q, 1e-300)))).sum(1)
    return np.log(r @ np.exp(D - D.max())) / np.log(2) + D.max() / np.log(2), D.max() / np.log(2)

C1 = ba(11 * np.log1p(w) / s); N64 = 11 + np.log(64) / np.log1p(w); C64 = ba(N64 * np.log1p(w) / s)
print(f"independent BA: C(1) = {C1[0]:.4f} [upper {C1[1]:.4f}], C(64) = {C64[0]:.4f} [upper {C64[1]:.4f}], dC = {C64[0]-C1[0]:.4f}")
o = json.load(open(r"C:\Users\mariu\neuro-company\research\somatosensory\code\results\p4_pooling_capacity.json"))
tb = o["B"]["table"]
print("coder: C(1) =", tb["0|0.162|1"]["C"], " C(64) =", tb["0|0.162|64"]["C"], " dC =", o["B"]["dC_64_minus_1_w0162_k0"])
print("coder verdicts A/B/C:", o["A"]["verdict"], o["A"]["checks"], o["B"]["verdict"], o["B"]["checks"], o["C"]["verdict"])
print("coder C counts:", {M: (v["count_int"], round(v["analytic"], 3), round(v["rel_err_int"], 4)) for M, v in o["C"]["per_M"].items()})
