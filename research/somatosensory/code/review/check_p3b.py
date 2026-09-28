"""Reviewer check for P3b (cycle 2). Does not modify any script or result.
Independent re-implementation of the threshold-only psi from the prereg text only:
1-D posterior over alpha (200 log-spaced values in [2, 200] uA, uniform in ln alpha), slope fixed beta_a (3, or the true beta
for the oracle), lam 0.02, gamma 0.5 (Weibull 2AFC p = .5 + (.5-lam)(1-exp(-(x/alpha)^beta))); candidates = 40 log-spaced
values in [2, 100] rounded to unique integers; each trial chooses the candidate minimising expected posterior entropy, computed
here by explicit per-outcome posteriors (not the coder's closed form). Estimate: exp(E[ln theta75(alpha, beta_a, 0.02)]).
Own RNG (different seeds), 300 runs per cell. Compared with results\\p3b_threshold_psi.json (main and oracle) on 5 cells.
Also re-checks the abandonment/control counts from the JSON.
"""
import json

import numpy as np

RES = r"C:\Users\mariu\neuro-company\research\somatosensory\code\results\p3b_threshold_psi.json"
BUD = [10, 15, 20, 30, 40, 50, 60, 80, 100, 120, 150]
THR = np.log(1.2)
A = np.exp(np.linspace(np.log(2), np.log(200), 200))
CANDS = np.unique(np.round(np.exp(np.linspace(np.log(2), np.log(100), 40)))).astype(float)


def pw(x, al, be, lam):
    return 0.5 + (0.5 - lam) * (1 - np.exp(-(x / al) ** be))


def x75(al, be, lam):
    q = (0.75 - 0.5) / (0.5 - lam)
    return al * (-np.log(1 - q)) ** (1 / be)


def run(theta, beta, lam, beta_a, seed, R=300):
    rng = np.random.default_rng(seed)
    alpha_true = theta / (-np.log(1 - 0.25 / (0.5 - lam))) ** (1 / beta)
    L = np.clip(pw(CANDS[None, :], A[:, None], beta_a, 0.02), 1e-12, 1 - 1e-12)   # (200, C)
    lt = np.log(x75(A, beta_a, 0.02))
    post = np.full((R, A.size), 1.0 / A.size)
    est = {}
    for t in range(1, 151):
        # explicit expected entropy: for each candidate, posterior after "correct" and after "wrong"
        pc = post[:, :, None] * L[None]                       # (R, 200, C)
        Zc = pc.sum(1)                                        # (R, C)
        qc = pc / Zc[:, None, :]
        qw = post[:, :, None] * (1 - L[None])
        qw = qw / (1 - Zc)[:, None, :]
        H = lambda q: -(q * np.log(np.where(q > 0, q, 1))).sum(1)
        EH = Zc * H(qc) + (1 - Zc) * H(qw)
        j = EH.argmin(1)
        x = CANDS[j]
        resp = rng.random(R) < pw(x, alpha_true, beta, lam)
        like = np.where(resp[:, None], L[:, j].T, 1 - L[:, j].T)
        post = post * like
        post /= post.sum(1, keepdims=True)
        if t in BUD:
            est[t] = np.exp(post @ lt)
    e = np.stack([np.log(est[b] / theta) for b in BUD], 1)
    rmse = np.sqrt((e ** 2).mean(0))
    ok = np.nonzero(rmse <= THR)[0]
    if ok.size == 0:
        nreq = np.inf
    elif ok[0] == 0:
        nreq = BUD[0]
    else:
        i = ok[0]
        nreq = BUD[i - 1] + (rmse[i - 1] - THR) / (rmse[i - 1] - rmse[i]) * (BUD[i] - BUD[i - 1])
    return nreq, float(e[:, BUD.index(60)].mean()), float(rmse[BUD.index(60)])


d = json.load(open(RES))
cells_main = {(c["theta75"], c["beta"], c["lam"]): c for c in d["main"]["cells"]}
cells_or = {(c["theta75"], c["beta"], c["lam"]): c for c in d["oracle"]["cells"]}
test = [(20.0, 3.0, 0.02), (20.0, 1.5, 0.02), (10.0, 1.5, 0.05), (50.0, 6.0, 0.0), (31.5, 3.0, 0.10)]
print("cell | arm | reviewer N_req, bias60, rmse60 | coder N_req, bias60, rmse60")
for k, cell in enumerate(test):
    for arm, ba, ref in (("A", 3.0, cells_main), ("oracle", cell[1], cells_or)):
        n, b, r = run(*cell, beta_a=ba, seed=[99, k, int(ba * 10)])
        c = ref[cell]
        cr = c.get("rmse_psi", [np.nan] * 11)[BUD.index(60)]
        print(f"{cell} | {arm} | {n:.1f}, {b:+.3f}, {r:.3f} | {c['N_req_psi']}, {c['bias60_psi']:+.3f}, {cr:.3f}")

print("\n--- rule re-check from JSON ---")
m = d["main"]
print("main verdict", m["verdict"], "n_sav", m["n_savings_cells"], "bias fails", m["n_bias_fail_lam_le_0p05"])
n_sav = sum(c["savings_ok"] for c in m["cells"])
nb = sum(abs(c["bias60_psi"]) > np.log(1.1) and c["lam"] <= 0.05 for c in m["cells"])
print("recount: savings", n_sav, "bias fails", nb, "-> verdict", "PASS" if (n_sav >= 36 and nb == 0) else "FAIL")
ab = d["abandonment"]
print("abandonment block", ab)
no = sum(c["savings_ok"] for c in d["oracle"]["cells"])
print("oracle recount", no, "-> stop-line rule (< 24):", no < 24)
nw = sum(c["ctrl_within_10pct"] for c in m["cells"])
print("control within 10% recount", nw, "-> control rule (>= 36 = 75%):", nw >= 36)
