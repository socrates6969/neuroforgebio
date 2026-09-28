"""Synthetic stand-ins for the D2 (LINK) and D3 (EEGMMIDB) loaders, used by `run_m1.py --synthetic` to exercise every
code path (fits, controls, vault scoring, verdict logic) before any real D2/D3 file is read.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. Known ground truth:
- D2: 96-ch 'SBP' = C_k [v1, v2, u] + mu_k + noise, velocity AR(1); C_k drifts with lag (fraction lag/730 of the
  loadings replaced), mu_k drifts; day 32 and 730 are 'RD'. Expected: rho falls with lag, R-a/R-b recover part.
- D3: 64-ch white noise; during T1 (T2) epochs channels 0-7 (8-15) get 1.6x amplitude. Expected accuracy >> 0.5.
"""
import hashlib
import os

import numpy as np

from . import data as D

LAGS = {"20200127": 0, "20200130": 3, "20200204": 8, "20200211": 15, "20200228": 32, "20200626": 151,
        "20200924": 241, "20210223": 393, "20220126": 730}
_BASE = np.random.default_rng(424242)
C0 = _BASE.standard_normal((96, 3))
MU0 = _BASE.standard_normal(96) * 2 + 10
_CACHE = {}


def _key(path):
    return int(hashlib.sha256(os.path.basename(path).encode()).hexdigest()[:8], 16)


def _session(path):
    if path in _CACHE:
        return _CACHE[path]
    date = os.path.basename(path).split("_ses-")[1][:8]
    lag = LAGS[date]
    rng = np.random.default_rng(_key(path))
    lens = rng.integers(55, 90, size=375)
    T = int(lens.sum()) + 20
    v = np.zeros((T, 3))
    for t in range(1, T):
        v[t] = 0.9 * v[t - 1] + 0.4 * rng.standard_normal(3)
    frac = lag / 730.0
    C = C0.copy()
    n_rep = int(round(frac * 60))
    C[:n_rep] = rng.standard_normal((n_rep, 3))
    mu = MU0 + frac * 3 * rng.standard_normal(96)
    x = v @ C.T + mu + 1.5 * rng.standard_normal((T, 96))
    ts = 5.0 + 0.02 * np.arange(T)
    starts = np.concatenate([[10], 10 + np.cumsum(lens)[:-1]])
    tr = dict(id=np.arange(375), start=ts[starts], stop=ts[starts + lens - 1],
              style=np.array(["RD" if lag in (32, 730) else "CO"] * 375), ts0=float(ts[0]), T20=T)
    _CACHE[path] = (tr, x, v[:, :2] * 0.1, ts)
    return _CACHE[path]


def d2_trials(path):
    return _session(path)[0]


def d2_neural(path):
    tr, x, v, ts = _session(path)
    d = np.diff(ts)
    return D.rebin(x), dict(dt_median_s=float(np.median(d)), dt_min_s=float(d.min()), dt_max_s=float(d.max()), n20=len(ts))


def d2_behaviour(path):
    return D.rebin(_session(path)[2])


def _eeg(path):
    rng = np.random.default_rng(_key(path))
    fs, dur = 160.0, 125
    n = int(fs * dur)
    x = rng.standard_normal((64, n)) * 10
    ann, t, k = [], 0.0, 0
    while t + 4.2 < dur:
        lab = "T0" if k % 2 == 0 else ("T1" if rng.random() < 0.5 else "T2")
        ann.append((t, 4.1 if lab != "T0" else 4.2, lab))
        if lab != "T0":
            a, b = int(t * fs), int((t + 4.1) * fs)
            ch = slice(0, 8) if lab == "T1" else slice(8, 16)
            x[ch, a:b] *= 1.6
        t += 4.15
        k += 1
    return x, fs, ann, dur


def edf_annotations(path):
    x, fs, ann, dur = _eeg(path)
    return ann, dict(n_records=dur, record_duration=1.0)


def d3_run(path, n_eeg=64):
    x, fs, ann, dur = _eeg(path)
    return x, fs, ["ch%d" % i for i in range(64)], ann, float(dur)


def patch(module):
    module.d2_trials = d2_trials
    module.d2_neural = d2_neural
    module.d2_behaviour = d2_behaviour
    module.edf_annotations = edf_annotations
    module.d3_run = d3_run
