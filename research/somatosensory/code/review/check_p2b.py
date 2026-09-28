"""Reviewer check for P2b (cycle 2). Does not modify any script or result.
Independent construction of the three noise arms from the prereg text (not via p2b.noise_sd):
  Weber: s_t = sqrt(nT)(w r_t + sigma0);  FV: s = sqrt(nT)(w rbar_ep + sigma0) on contact samples (F > 0.02, own mask),
  rbar_ep = mean of r over contact samples;  HS: s = sqrt(nT) * 13.5/(Phi^-1(.75) sqrt 2) (prereg C4 literal).
Own AUC (scipy rankdata Mann-Whitney), own d' = sqrt2 Phi^-1(AUC), own V = 1 - Delta_FV/Delta_W.
Cycle-1 episode generator, encoders, charge matching and detector windows are reused (verified in cycle 1).
Extra probes: (i) variance-only probe under FV noise (must be ~0 if FV removes the variance cue);
(ii) HS sigma_h by a direct Monte Carlo JND (constant noise, two 1-s trains at 60 uA).
"""
import sys

import numpy as np
from scipy.special import ndtri
from scipy.stats import rankdata

CODE = r"C:\Users\mariu\neuro-company\research\somatosensory\code"
sys.path.insert(0, CODE)
import p2_biomimetic_info as p2  # noqa: E402


def auc(pos, neg):
    r = rankdata(np.r_[pos, neg])
    return (r[:pos.size].sum() - pos.size * (pos.size + 1) / 2) / (pos.size * neg.size)


def dp(y, E, P):
    d1p, d2p = p2.scores(y, E["ev_ep"], E["ev_idx"], P)
    d1n, d2n = p2.scores(y, E["nu_ep"], E["nu_idx"], P)
    a1, a2 = auc(d1p, d1n), auc(d2p, d2n)
    return max(np.sqrt(2) * ndtri(a1), np.sqrt(2) * ndtri(a2)), (a1, a2)


P = dict(p2.DEF)
E, dF, enc, info = p2.build(P)
w = p2.calibrate_w(np.inf, P)
nT = P["T_train"] / p2.DT
contact = E["F"] > 0.02
print("contact mask identical to a>0 for both encoders:",
      bool(np.array_equal(contact, enc["charge"] > 0) and np.array_equal(contact, enc["lin"] > 0)))
sh_ps = 13.5 / (ndtri(0.75) * np.sqrt(2)) * np.sqrt(nT)


def sd_arm(a, arm):
    r = a  # tau_ad = inf: r = a
    if arm == "weber":
        return np.sqrt(nT) * (w * r + P["sigma0"])
    if arm == "hs":
        return np.full(a.shape, sh_ps)
    rbar = np.array([r[i, contact[i]].mean() if contact[i].any() else 0.0 for i in range(a.shape[0])])
    s = np.sqrt(nT) * (w * r + P["sigma0"])
    s[contact] = (np.sqrt(nT) * (w * rbar + P["sigma0"]))[:, None].repeat(a.shape[1], 1)[contact]
    return s


res = {}
for arm in ("weber", "fv", "hs"):
    db, ab = dp(enc["charge"] + sd_arm(enc["charge"], arm) * E["Z"], E, P)
    dl, al = dp(enc["lin"] + sd_arm(enc["lin"], arm) * E["Z"], E, P)
    res[arm] = db - dl
    print(f"{arm}: d'_bio {db:.4f} d'_lin {dl:.4f} Delta {db - dl:.4f}  AUC bio {np.round(ab, 3)} lin {np.round(al, 3)}")
print(f"V_FV = {1 - res['fv'] / res['weber']:.4f}   V_HS = {1 - res['hs'] / res['weber']:.4f}")
print("coder JSON: Delta W/FV/HS 0.5252/0.1121/0.0550, V_FV 0.7865, V_HS 0.8953")

# (i) variance-only probe under Weber and under FV noise (mean held at 0)
for arm in ("weber", "fv"):
    d, a = dp(sd_arm(enc["charge"], arm) * E["Z"], E, P)
    print(f"variance-only probe, bio sd course of arm {arm}: d' {d:.4f} AUC {np.round(a, 3)}")

# (ii) HS JND by Monte Carlo: two 1-s flat trains, constant per-sample sd, 2AFC on summed y
rng = np.random.default_rng(1)
cc = np.linspace(30, 90, 31)
pr = [np.mean((c + sh_ps * rng.standard_normal((20000, 100))).sum(1) > (60 + sh_ps * rng.standard_normal((20000, 100))).sum(1))
      for c in cc]
jnd = 0.5 * (np.interp(0.75, pr, cc) - np.interp(0.25, pr, cc))
print(f"HS per-sample sd {sh_ps:.2f}; MC JND {jnd:.2f} (target 13.5)")

# mean rbar per encoder (FV noise power matching)
rb = lambda a: np.array([a[i, contact[i]].mean() for i in range(a.shape[0]) if contact[i].any()])
print(f"mean rbar bio {rb(enc['charge']).mean():.3f} lin {rb(enc['lin']).mean():.3f}")
