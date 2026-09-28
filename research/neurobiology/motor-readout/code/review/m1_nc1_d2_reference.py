r"""Reviewer check: is the D2 NC1 R^2 bar (max(0.05, R^2_B0 + 0.02), B0 = flat calib mean) mis-specified?

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. Reviewer check; no m1lib import.
On LINK day 0 (20200127) test block: R^2 of (a) the flat calib-mean B0 (prereg D2 reference) and (b) a
trial-start-aligned mean velocity profile from calib trials (the D2 analogue of D1's onset-aligned B0), plus the
fraction of shuffled calib pairs that share the same target (CO), i.e. pairs that are 'accidentally correct'.
Output: review\m1_nc1_d2_reference_out.json
"""
import json
import os

import h5py
import numpy as np

ROOT = r"C:\Users\mariu\neuro-company\research\neurobiology\motor-readout"
P = os.path.join(ROOT, "data", "raw", "001201", "sub-Monkey-N_ses-20200127_ecephys.nwb")
with h5py.File(P, "r") as f:
    ts = f["analysis/SpikingBandPower/timestamps"][:]
    v = np.column_stack([f["analysis/index_velocity/data"][:, 0], f["analysis/mrs_velocity/data"][:, 0]])
    t = f["intervals/trials"]
    st, sp = t["start_time"][:], t["stop_time"][:]
    tgt = np.column_stack([t["index_target_position"][:], t["mrs_target_position"][:]])
fine = np.repeat(v, 5, axis=0)
n = fine.shape[0] // 8
V = fine[:n * 8].reshape(n, 8, 2).mean(1)
cen = ts[0] + (np.arange(n) + 0.5) * 0.032
o = np.argsort(st, kind="stable")
c1, c2 = int(round(0.6 * len(o))), int(round(0.8 * len(o)))
cal, te = o[:c1], o[c2 + 1:]


def rows(i):
    return np.flatnonzero((cen >= st[i]) & (cen < sp[i] + 0.020))


calrows = np.concatenate([rows(i) for i in cal])
flat = V[calrows].mean(0)
L = max(len(rows(i)) for i in cal)
acc, cnt = np.zeros((L, 2)), np.zeros(L)
for i in cal:
    r = rows(i)
    acc[:len(r)] += V[r]
    cnt[:len(r)] += 1
prof = acc / np.maximum(cnt, 1)[:, None]
ys, pf, pa = [], [], []
for i in te:
    r = rows(i)
    ys.append(V[r])
    pf.append(np.repeat(flat[None], len(r), 0))
    k = min(len(r), L)
    pa.append(np.vstack([prof[:k], np.repeat(flat[None], len(r) - k, 0)]))
y = np.vstack(ys)


def r2(p):
    return float(1 - ((y - p) ** 2).sum() / ((y - y.mean(0)) ** 2).sum())


rng = np.random.default_rng(99)
same = [float(np.mean(np.all(tgt[cal] == tgt[cal][rng.permutation(len(cal))], axis=1))) for _ in range(200)]
out = dict(B0_flat_r2=r2(np.vstack(pf)), B0_start_aligned_profile_r2=r2(np.vstack(pa)),
           n_distinct_targets_calib=int(len({tuple(x) for x in tgt[cal].round(4).tolist()})),
           frac_shuffled_pairs_same_target_mean=float(np.mean(same)),
           bar_prereg=max(0.05, r2(np.vstack(pf)) + 0.02), bar_if_start_aligned_B0=max(0.05, r2(np.vstack(pa)) + 0.02))
json.dump(out, open(os.path.join(ROOT, "code", "review", "m1_nc1_d2_reference_out.json"), "w"), indent=1)
print(out)
