"""Reviewer check for P1 zero-perturbation diagnosis. Imports the coder's simulate() read-only; writes nothing."""
import sys, time
import numpy as np
sys.path.insert(0, r"C:\Users\mariu\neuro-company\research\somatosensory\code")
import p1_grip_latency as p1

# 1. analytic noise-free, lag-free lower bound for NOFB at K=0: fail if 1+SM < 0.75/mu (slip) or 1+SM > 0.75c/mu (crush)
rng = np.random.default_rng(1)
mu = rng.uniform(0.3, 1.2, 2_000_000); c = rng.uniform(1.6, 2.5, 2_000_000)
best = []
for sm in p1.SM_GRID:
    k = 1 + sm
    best.append(np.mean((k < 0.75 / mu) | (k > 0.75 * c / mu)))
best = np.array(best)
print("analytic NOFB K=0 fail by SM:", best.round(3).tolist())
print("analytic NOFB K=0 min fail =", best.min().round(4), "at SM", p1.SM_GRID[best.argmin()])
# is there ANY SM (continuous) with fail <= 0.01?
ks = np.linspace(1, 3, 2001)
fc = np.array([np.mean((k < 0.75 / mu[:200000]) | (k > 0.75 * c[:200000] / mu[:200000])) for k in ks])
print("continuous 1+SM in [1,3]: min fail =", fc.min().round(4), "at 1+SM =", ks[fc.argmin()].round(3))

def run(label, P, N=1000, mu_fix=None):
    t = time.time()
    tr = p1.make_trials(N, P)
    if mu_fix is not None:
        tr["mu"][:] = mu_fix
        tr["Gcrush"] = tr["c"] * tr["mg"] / (2 * tr["mu"])
    conds = p1.resolve([dict(name="NAT", kind="FB", tau=None, p=None), dict(name="NOFB", kind="NOFB", tau=0, p=0.0)], P)
    o = p1.simulate(tr, P, conds)
    for i, nm in enumerate(["NAT", "NOFB"]):
        f = p1.fstar(o["fail"][i])
        j = int(np.argmin(f["rate_by_SM"]))
        fl = o["fail"][i][:, j]
        m = tr["mu"]
        split = {f"mu<{0.75/(1+f['SM_opt']):.2f}": float((fl[m < 0.75 / (1 + f["SM_opt"])] > 0).mean()) if (m < 0.75/(1+f['SM_opt'])).any() else None,
                 "mu>0.9": float((fl[m > 0.9] > 0).mean()) if (m > 0.9).any() else None}
        print(f"{label:34s} {nm:4s} F*={f['F']:.4f} SM_opt={f['SM_opt']} drop={f['drop']:.4f} crush={f['crush']:.4f} fail-frac by mu {split}")
    print(f"   ({time.time()-t:.0f}s)")

run("K=0 default (noise .05), N=1000", dict(p1.DEFAULT, K_zero=True))
run("K=0 noise=0, N=1000", dict(p1.DEFAULT, K_zero=True, noise=0.0))
run("K=0 mu fixed = prior 0.75", dict(p1.DEFAULT, K_zero=True), mu_fix=0.75)
run("K=0 mu_prior=0.3 (lowest mu)", dict(p1.DEFAULT, K_zero=True, mu_prior=0.3))
