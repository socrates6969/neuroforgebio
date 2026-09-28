"""Toy two-class dataset: band-power features of synthetic EEG from ``tools/synth`` (nf_synth).

Per subject, two synthetic recordings are generated with the 0.6 generator: class 0 with a
subject-specific alpha amplitude ``a``, class 1 with ``a * ALPHA_GAIN`` (an "eyes-closed"-like
alpha increase). Subjects also differ in alpha frequency and background level, so a decoder must
generalise across subjects. Each recording is cut into 2 s epochs; the features are
``log10`` mean periodogram power (Hann window) per channel in theta (4-8 Hz), alpha (8-13 Hz) and
beta (13-30 Hz). Synthetic only: no real human data.

``nf_synth`` lives in ``tools/synth`` (on the repo's pytest path); it is imported lazily, so the
rest of ``nf_train`` does not need it.
"""

from __future__ import annotations

import hashlib

import numpy as np

BANDS = ((4.0, 8.0), (8.0, 13.0), (13.0, 30.0))
ALPHA_GAIN = 1.5
EPOCH_S = 2
DURATION_S = 16
N_CHANNELS = 8
SFREQ = 256


def band_power(data: np.ndarray, sfreq: int, epoch_s: int = EPOCH_S) -> np.ndarray:
    """(n_epochs, n_channels * n_bands) log10 band power of consecutive epochs."""
    n = epoch_s * sfreq
    k = data.shape[1] // n
    ep = data[:, : k * n].reshape(data.shape[0], k, n).transpose(1, 0, 2)
    win = np.hanning(n)
    spec = np.abs(np.fft.rfft(ep * win, axis=2)) ** 2 / (sfreq * np.sum(win**2))
    f = np.fft.rfftfreq(n, 1.0 / sfreq)
    feats = [spec[:, :, (f >= lo) & (f < hi)].mean(axis=2) for lo, hi in BANDS]
    return np.log10(np.stack(feats, axis=2).reshape(k, -1))


def _rng(seed: int, subject: int) -> np.random.Generator:
    d = hashlib.sha256(f"nf-train-toy|{seed}|{subject}".encode()).digest()
    return np.random.Generator(np.random.PCG64(int.from_bytes(d[:8], "big")))


def subject(seed: int, index: int) -> tuple[np.ndarray, np.ndarray]:
    """(x, y) of one synthetic subject; deterministic in (seed, index)."""
    from nf_synth.generate import SynthParams, generate  # tools/synth

    rng = _rng(seed, index)
    alpha = float(rng.uniform(3.0, 9.0))
    freq = float(rng.uniform(9.0, 11.5))
    rms = float(rng.uniform(8.0, 12.0))
    xs, ys = [], []
    for cls, amp in ((0, alpha), (1, alpha * ALPHA_GAIN)):
        p = SynthParams(
            seed=int(rng.integers(0, 2**31 - 1)),
            n_channels=N_CHANNELS,
            sfreq=SFREQ,
            duration_s=DURATION_S,
            alpha_amp_uv=amp,
            alpha_freq_hz=freq,
            background_rms_uv=rms,
        )
        data, _truth = generate(p)
        f = band_power(data, SFREQ)
        xs.append(f)
        ys.append(np.full(f.shape[0], cls, dtype=np.int64))
    return np.concatenate(xs), np.concatenate(ys)


def dataset(
    seed: int, n_subjects: int, offset: int = 0
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """``{"toy-<i>": (x, y)}`` for subjects ``offset .. offset + n_subjects - 1``."""
    return {f"toy-{i:04d}": subject(seed, i) for i in range(offset, offset + n_subjects)}


def encode(x: np.ndarray, y: np.ndarray, scale: float = 1000.0) -> np.ndarray:
    """Pack (x, y) into one int16 array (features + 1 label row) x epochs, for storing a subject's
    feature table as a single-subject artifact in the platform tests."""
    return np.round(np.vstack([x.T * scale, y[None, :].astype(np.float64)])).astype(np.int16)


def decode(a: np.ndarray, scale: float = 1000.0) -> tuple[np.ndarray, np.ndarray]:
    a = np.asarray(a, dtype=np.float64)
    if a.ndim != 2 or a.shape[0] < 2:
        raise ValueError("expected a (features + 1, epochs) table")
    return a[:-1].T / scale, a[-1].astype(np.int64)
