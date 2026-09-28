"""Stateless per-window features (N2 §2) and the F7 whitelist guard.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
132 = 22 channels x (log10 line length, 5 log10 band powers), channel-major. One EDF is streamed at a time.
"""
import os
import sys

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from .config import BANDS, CHANNEL_INDEX, CHANNEL_LABELS_23, FEATURE_KINDS, guard_hit
from .errors import FeatureWhitelistError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from edf_reader import read_edf, read_header  # noqa: E402  (pure-numpy reader by the data agent)

FS = 256
NWIN = 512
EPS = 1e-3
FEATURE_NAMES = tuple("ch%02d_%s_%s" % (c, CHANNEL_LABELS_23[c], k) for c in CHANNEL_INDEX for k in FEATURE_KINDS)
WHITELIST = frozenset(FEATURE_NAMES)
_HANN = np.hanning(NWIN)
_FREQS = 0.5 * np.arange(NWIN // 2 + 1)
_BAND_MASKS = [(_FREQS >= lo) & (_FREQS < hi) for lo, hi in BANDS]


def assert_whitelist(columns):
    """F7: every feature column must be one of the 132 whitelisted signal features."""
    guard_hit("F7")
    bad = [c for c in columns if c not in WHITELIST]
    if bad:
        raise FeatureWhitelistError("non-signal / non-whitelisted feature columns: %s" % bad[:5])
    return True


def features_from_signal(x, fs=FS):
    """x: float [22, T*fs] (uV). Returns float32 [T-1, 132]."""
    if fs != FS:
        raise ValueError("fs must be 256")
    n_ch, n = x.shape
    T = n // fs
    nw = T - 1
    out = np.empty((nw, n_ch * len(FEATURE_KINDS)), dtype=np.float32)
    for c in range(n_ch):
        w = sliding_window_view(x[c, :T * fs].astype(np.float64), NWIN)[::fs][:nw]      # [nw, 512]
        w = w - w.mean(axis=1, keepdims=True)
        ll = np.abs(np.diff(w, axis=1)).mean(axis=1)
        P = np.abs(np.fft.rfft(w * _HANN, axis=1)) ** 2
        cols = [np.log10(ll + EPS)] + [np.log10(P[:, m].sum(axis=1) + EPS) for m in _BAND_MASKS]
        out[:, c * 6:(c + 1) * 6] = np.stack(cols, axis=1)
    return out


def file_features(rec):
    """Stream one EDF (22 channels) and return float32 [T-1, 132]."""
    h = read_header(rec.path)
    if [h["labels"][c] for c in CHANNEL_INDEX] != [CHANNEL_LABELS_23[c] for c in CHANNEL_INDEX]:
        raise ValueError("unexpected montage in %s" % rec.name)
    x, fs, _ = read_edf(rec.path, channels=CHANNEL_INDEX)
    if int(x.shape[1] // fs) != rec.duration:
        raise ValueError("duration mismatch in %s" % rec.name)
    f = features_from_signal(x, int(fs))
    del x
    return f
