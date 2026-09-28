"""Reviewer check for P2 d'_lin ~ 0. Uses coder's episode generator/encoders read-only, but an INDEPENDENT noise draw,
independent detector arithmetic and an analytic noise-sd calculation. Writes nothing."""
import sys
import numpy as np
from scipy.special import ndtri, ndtr
sys.path.insert(0, r"C:\Users\mariu\neuro-company\research\somatosensory\code")
import p2_biomimetic_info as p2

P = dict(p2.DEF, N=1500)
E = p2.gen_episodes(P, seed=12345)
alin = p2.a_lin(E["F"])
w = p2.calibrate_w(np.inf, P)
print("calibrated w (tau=inf) =", round(w, 4))

# (1) closed-form check of the calibration: 1-s train mean has sd (w r + sigma0); 2AFC JND = 0.6745*sqrt(2)*sd approx
sd60 = w * 60 + 1
print("train-level sd at 60 uA =", round(sd60, 2), "-> approx JND", round(0.6745 * np.sqrt(((w*60+1)**2 + (w*73.5+1)**2)), 2))

# (2) per-sample sd after recalibration for T_train 0.5/1/2 s (shows the sqrt(n_T) factor is absorbed by calibration)
for T in (0.5, 1.0, 2.0):
    PT = dict(P, T_train=T)
    wT = p2.calibrate_w(np.inf, PT)
    print(f"T_train={T}: w={wT:.4f}, per-sample sd at r=62 uA = {np.sqrt(T/p2.DT)*(wT*62+1):.1f}")

# (3) independent D2 for linear encoder with fresh noise
rng = np.random.default_rng(999)
def d2(y, ep, k):
    out = np.empty(ep.size)
    for i, (e, kk) in enumerate(zip(ep, k)):
        post = y[e, min(kk+10, 299):min(kk+20, 299)+1].mean(); pre = y[e, max(kk-20, 0):kk+1].mean()
        out[i] = post - pre
    return out
def auc(pos, neg):
    allv = np.concatenate([pos, neg]); r = allv.argsort().argsort() + 1.0
    return (r[:pos.size].sum() - pos.size*(pos.size+1)/2) / (pos.size*neg.size)
Z = rng.standard_normal(alin.shape)
y = alin + np.sqrt(P["T_train"]/p2.DT) * (w*alin + P["sigma0"]) * Z
sig = d2(alin, E["ev_ep"], E["ev_idx"])            # noise-free signed signal
sp = d2(y, E["ev_ep"], E["ev_idx"]); sn = d2(y, E["nu_ep"], E["nu_idx"])
rr = alin[E["ev_ep"], E["ev_idx"]]
sd_diff = np.sqrt(P["T_train"]/p2.DT) * (w*rr + 1) * np.sqrt(1/11 + 1/21)
print(f"lin step: mean |signal| {np.abs(sig).mean():.2f} uA; mean sd of D2 difference {sd_diff.mean():.1f} uA; SNR {np.mean(np.abs(sig)/sd_diff):.3f}")
a_abs = auc(np.abs(sp), np.abs(sn)); print(f"linear |D2| AUC (independent) = {a_abs:.4f}, d' = {np.sqrt(2)*ndtri(a_abs):.3f}  (coder: AUC_D2 0.5048, d' 0.017)")
inc = E["ev_sign"] > 0
a_s = auc(sp[inc], sn); print(f"linear SIGNED D2, increases only: AUC {a_s:.4f}, d' {np.sqrt(2)*ndtri(a_s):.3f}  (upper-level cue with sign known)")
# analytic expectation: |N(m,1)| vs |N(0,1)| AUC for m = SNR
m = np.abs(sig)/sd_diff
xs = rng.standard_normal((m.size, 200)); ex = np.abs(m[:, None] + xs).ravel(); nx = np.abs(rng.standard_normal(ex.size))
print(f"analytic-model |D2| AUC for these SNRs = {auc(ex[:200000], nx[:200000]):.4f}")
# (4) counterfactual: if noise were NOT scaled by sqrt(n_T) (same w) -> per-sample sd 10x smaller
y2 = alin + (w*alin + P["sigma0"]) * Z
a2 = auc(np.abs(d2(y2, E["ev_ep"], E["ev_idx"])), np.abs(d2(y2, E["nu_ep"], E["nu_idx"])))
print(f"counterfactual no-sqrt(n_T) noise (NOT the prereg): linear |D2| AUC {a2:.4f}, d' {np.sqrt(2)*ndtri(a2):.3f}")

# (5) how much of d'_bio is the Weber variance cue? charge-matched encoders, coder's detectors (encoder_eval),
#     (a) prereg Weber noise vs (b) homoscedastic noise with the same average per-sample sd (mean-shift cue only)
E2, dF, enc, info = p2.build(P, E)
Zc = np.random.default_rng(77).standard_normal(enc["lin"].shape)
sd_bar = float(np.mean(np.sqrt(P["T_train"]/p2.DT) * (w*enc["lin"][enc["lin"] > 0] + 1)))
for lab, fn in (("Weber (prereg)", lambda a, ww: a + np.sqrt(100)*(ww*a + 1)*Zc),
                ("homoscedastic sd=%.0f" % sd_bar, lambda a, ww: a + sd_bar*(ww/w)*Zc)):
    for sc in (1.0, 0.5, 0.25):
        db = p2.encoder_eval(fn(enc["charge"], w*sc), E, P)["dprime"]; dl = p2.encoder_eval(fn(enc["lin"], w*sc), E, P)["dprime"]
        print(f"{lab:26s} w x{sc:<4}: d'_bio {db:.3f}  d'_lin {dl:.3f}")
