"""Reviewer check for P3: independent psi (direct posterior, brute-force expected entropy) and independent 3d1u staircase,
written from the prereg text only. Compares RMSE/bias with coder's JSON for a few cells. Writes nothing but stdout."""
import json
import numpy as np

BUD = [10, 15, 20, 30, 40, 50, 60, 80, 100, 120, 150]
def wb(x, a, b, lam): return 0.5 + (0.5 - lam) * (1 - np.exp(-(x / a) ** b))
def x_at(p, a, b, lam): return a * (-np.log(1 - (p - 0.5) / (0.5 - lam))) ** (1 / b)

al = np.exp(np.linspace(np.log(2), np.log(200), 40)); be = np.exp(np.linspace(np.log(0.7), np.log(10), 10))
AA, BB = [v.ravel() for v in np.meshgrid(al, be, indexing="ij")]
cand = np.unique(np.round(np.exp(np.linspace(np.log(2), np.log(100), 40))))
Lk = wb(cand[None, :], AA[:, None], BB[:, None], 0.02)          # (400, C)
lth = np.log(x_at(0.75, AA, BB, 0.02))

def H(p):  # entropy along last axis
    return -(np.where(p > 0, p * np.log(np.where(p > 0, p, 1)), 0)).sum(-1)

def psi(theta, beta, lam, R, rng, T=150):
    a_true = theta / (-np.log(1 - 0.25 / (0.5 - lam))) ** (1 / beta)
    post = np.full((R, AA.size), 1.0 / AA.size)
    est = {}
    for t in range(T):
        # brute force: posterior after success / failure for each candidate
        ps = post[:, :, None] * Lk[None]; Zs = ps.sum(1)            # (R, C)
        pf = post[:, :, None] * (1 - Lk[None]); Zf = pf.sum(1)
        EH = Zs * H(np.moveaxis(ps / Zs[:, None, :], 1, 2)) + Zf * H(np.moveaxis(pf / Zf[:, None, :], 1, 2))
        j = EH.argmin(1); x = cand[j]
        r = rng.random(R) < wb(x, a_true, beta, lam)
        post = post * np.where(r[:, None], Lk[:, j].T, 1 - Lk[:, j].T); post /= post.sum(1, keepdims=True)
        if t + 1 in BUD:
            est[t + 1] = np.exp(post @ lth)
    return np.array([np.log(est[n] / theta) for n in BUD]).T

def stair(theta, beta, lam, R, rng, T=150):
    a_true = theta / (-np.log(1 - 0.25 / (0.5 - lam))) ** (1 / beta)
    tgt = x_at(0.5 ** (1 / 3), a_true, beta, lam)
    E = np.zeros((R, len(BUD)))
    for i in range(R):
        lev, run, last, nrev, pres, revs = 80.0, 0, 0, 0, [], []
        for t in range(T):
            x = round(min(max(lev, 1), 100)); pres.append(x)
            ok = rng.random() < wb(x, a_true, beta, lam)
            d = 0
            if ok:
                run += 1
                if run == 3: d, run = -1, 0
            else:
                d, run = 1, 0
            if d:
                if last and d != last:
                    nrev += 1; revs.append((t, nrev))
                f = 1.26 if nrev >= 2 else 1.585
                lev = min(max(lev * f ** d, 1), 100); last = d
        for k, n in enumerate(BUD):
            use = [pres[t] for t, rn in revs if t < n and rn >= 3]
            E[i, k] = np.log((np.exp(np.mean(np.log(use))) if len(use) >= 2 else pres[n - 1]) / tgt)
    return E

o = json.load(open(r"C:\Users\mariu\neuro-company\research\somatosensory\code\results\p3_psi_staircase.json"))
cells = {(r["theta75"], r["beta"], r["lam"]): r for r in o["main"]["cells"]}
rng = np.random.default_rng(4242)
for cell in [(20.0, 3.0, 0.02), (31.5, 6.0, 0.0), (10.0, 1.5, 0.0), (50.0, 3.0, 0.05)]:
    ep = psi(*cell, R=150, rng=rng); es = stair(*cell, R=300, rng=rng)
    rp, rs = np.sqrt((ep ** 2).mean(0)), np.sqrt((es ** 2).mean(0))
    c = cells[cell]
    print(cell)
    print("  psi  RMSE mine ", rp.round(3).tolist()); print("  psi  RMSE coder", np.round(c["rmse_psi"], 3).tolist())
    print("  stair RMSE mine ", rs.round(3).tolist()); print("  stair RMSE coder", np.round(c["rmse_stair"], 3).tolist())
    print(f"  psi bias@60 mine {ep[:, 6].mean():.3f} (se {ep[:, 6].std()/np.sqrt(ep.shape[0]):.3f})  coder {c['bias60_psi']:.3f}")
