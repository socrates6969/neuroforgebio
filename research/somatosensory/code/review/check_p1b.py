"""Reviewer check for P1b (cycle 2). Does not modify any script or result.
1. Re-run the coder's simulate() (imported) for NAT and NOFB, N = 1000, all SM, and measure the failure rate among trials
   with >= 1 delivered detection (claim: 100%).
2. Analytic bound: at a slip, L(t_s) = 2 mu Geff(t_s); after delivery mu_hat = 0.9 L/(2 Geff) and L_fb = L(t_s), so the new
   command is (1+SM) L(t_s) / (2 mu_hat) = (1+SM) Geff(t_s) / 0.9. Pre-slip grip is (1+SM) mg / (2 mu_hat0), so
   L(t_s)/mg >= (1+SM) mu/mu_hat0 >= (1+SM)/1.1 (noise-free). Crush iff (1+SM) L(t_s) / (0.9 c mg) > 1, i.e. the bound
   (1+SM)^2 / (0.99 c) > 1 guarantees crush. Report the SM above which crush is certain for all c <= 2.5.
3. Counterfactuals (reviewer-patched copies of simulate(), NOT prereg arms): (a) no L_fb hold (grip uses mg*ramp only,
   mu update kept); (b) L_fb kept, mu update disabled; (c) both disabled. Which component produces the crush?
"""
import inspect
import os
import sys

import numpy as np

CODE = r"C:\Users\mariu\neuro-company\research\somatosensory\code"
sys.path.insert(0, CODE)
import p1b_grip_latency_v2 as p1b  # noqa: E402
from p1_grip_latency import SM_GRID, resolve  # noqa: E402

N = 1000
P = dict(p1b.DEFAULT)
tr = p1b.make_trials(N, P)
conds = resolve([dict(name="NAT", kind="FB", tau=None, p=None), dict(name="NOFB", kind="NOFB", tau=0, p=0.0),
                 dict(name="ART100", kind="FB", tau=0.174, p=0.95)], P)
o = p1b.simulate(tr, P, conds)
fail, ndel = o["fail"], o["ndel"]
print("=== 1. failure among trials with >=1 delivered detection (coder's simulate, N=1000) ===")
for ci, nm in enumerate(["NAT", "NOFB", "ART+100"]):
    rate = (fail[ci] > 0).mean(0)
    j = int(np.argmin(rate))
    print(f"{nm}: F* = {rate[j]:.3f} at SM {SM_GRID[j]}")
    if nm == "NOFB":
        continue
    for sm in (0.2, 0.4, 0.6, 0.7, 1.0):
        k = int(np.where(SM_GRID == sm)[0][0])
        d = ndel[ci][:, k] >= 1
        fd = fail[ci][d, k]
        print(f"   SM {sm}: frac trials with delivery {d.mean():.3f}; fail|delivery {np.mean(fd > 0):.3f} "
              f"(crush {np.mean(fd == 2):.3f}, drop {np.mean(fd == 1):.3f}); fail|no delivery {np.mean(fail[ci][~d, k] > 0):.3f}")

print("\n=== 2. analytic compounding bound (noise-free, worst-case prior r = 1/1.1) ===")
for sm in (0.2, 0.4, 0.5, 0.6, 0.7, 1.0):
    b = (1 + sm) ** 2 / 0.99
    print(f"SM {sm}: (1+SM)^2/(0.99 c) > 1 for c < {b:.2f}  -> crush certain for all c in [1.6,2.5]: {b > 2.5}")
print("SM threshold for certainty at c = 2.5:", round(np.sqrt(2.5 * 0.99) - 1, 3))

print("\n=== 3. counterfactual component knock-outs (reviewer patches; not prereg arms) ===")
src = inspect.getsource(p1b.simulate)
variants = {
    "a_no_Lfb_hold": src.replace("np.maximum(a[\"mg\"] * ramp_lead, a[\"Lfb\"])", "a[\"mg\"] * ramp_lead"),
    "b_no_mu_update": src.replace("a[\"muh\"][p] = muc          # C2", "pass  # C2"),
}
variants["c_neither"] = variants["a_no_Lfb_hold"].replace("a[\"muh\"][p] = muc          # C2", "pass  # C2")
for k, s in variants.items():
    assert s != src, k
for name, s in variants.items():
    ns = dict(vars(p1b))
    exec(compile(s, name, "exec"), ns)
    oo = ns["simulate"](tr, P, conds[:2])
    f, nd = oo["fail"], oo["ndel"]
    rate = (f[0] > 0).mean(0)
    j = int(np.argmin(rate))
    rn = (f[1] > 0).mean(0)
    k7 = int(np.where(SM_GRID == 0.7)[0][0])
    d = nd[0][:, k7] >= 1
    print(f"{name}: F*_NAT {rate[j]:.3f} (SM {SM_GRID[j]}), F*_NOFB {rn.min():.3f}; ratio {rate[j] / rn.min():.2f}; "
          f"SM0.7 fail|delivery {np.mean(f[0][d, k7] > 0):.3f} crush|delivery {np.mean(f[0][d, k7] == 2):.3f}")
