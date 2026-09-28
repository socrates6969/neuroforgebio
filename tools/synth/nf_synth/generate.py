"""Deterministic synthetic EEG-like signals with known ground truth (BUILD-GUIDE 0.6).

Everything is derived from one integer seed through numpy's PCG64. The same seed gives
byte-identical data and truth with the same numpy version (uv.lock pins it); across numpy
versions or CPUs the FFT may differ in the last bits, so compare those within a tolerance.
Units: microvolts (uV). Data shape: (n_channels, n_samples), float64.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

GENERATOR_VERSION = "nf-synth/0.1.0"

# 10-20 montage subset, in a fixed order.
CHANNELS_1020 = [
    "Fp1", "Fp2", "F3", "F4", "C3", "C4", "P3", "P4", "O1", "O2",
    "F7", "F8", "T7", "T8", "P7", "P8", "Fz", "Cz", "Pz",
]  # fmt: skip
FRONTAL = {"Fp1", "Fp2", "F7", "F8"}
POSTERIOR = {"O1", "O2", "P3", "P4", "P7", "P8", "Pz"}
TEMPORAL = {"T7", "T8", "F7", "F8"}


@dataclass(frozen=True)
class SynthParams:
    seed: int = 0
    n_channels: int = 8
    sfreq: int = 256  # Hz; EDF records are 1 s, so duration * sfreq samples
    duration_s: int = 20
    aperiodic_exponent: float = 1.0  # PSD ~ 1/f^exponent
    background_rms_uv: float = 10.0
    alpha_freq_hz: float = 10.0
    alpha_amp_uv: float = 8.0
    line_freq_hz: float = 50.0
    line_amp_uv: float = 4.0
    blink_every_s: float = 5.0
    blink_amp_uv: float = 120.0
    muscle_burst_s: tuple[float, float] = (12.0, 12.5)
    muscle_rms_uv: float = 25.0
    bad_channel: str = "C3"
    bad_channel_gain: float = 20.0
    event_every_s: float = 2.0
    channel_names: tuple[str, ...] = field(default=())

    def channels(self) -> list[str]:
        if self.channel_names:
            return list(self.channel_names)
        if not 1 <= self.n_channels <= len(CHANNELS_1020):
            raise ValueError(f"n_channels must be 1..{len(CHANNELS_1020)}")
        return CHANNELS_1020[: self.n_channels]


def _aperiodic(
    rng: np.random.Generator, n_ch: int, n: int, sfreq: int, exponent: float
) -> np.ndarray:
    white = rng.standard_normal((n_ch, n))
    spec = np.fft.rfft(white, axis=1)
    f = np.fft.rfftfreq(n, 1.0 / sfreq)
    scale = np.zeros_like(f)
    scale[1:] = f[1:] ** (-exponent / 2.0)
    x = np.fft.irfft(spec * scale, n=n, axis=1)
    x -= x.mean(axis=1, keepdims=True)
    return x / x.std(axis=1, keepdims=True)


def _band_noise(rng: np.random.Generator, n: int, sfreq: int, lo: float, hi: float) -> np.ndarray:
    spec = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1.0 / sfreq)
    spec[(f < lo) | (f > hi)] = 0
    x = np.fft.irfft(spec, n=n)
    return x / (x.std() or 1.0)


def generate(params: SynthParams | None = None) -> tuple[np.ndarray, dict[str, Any]]:
    """Return (data_uv[n_channels, n_samples], truth dict)."""
    p = params or SynthParams()
    chans = p.channels()
    n_ch, sf = len(chans), p.sfreq
    n = int(p.duration_s * sf)
    t = np.arange(n) / sf
    rng = np.random.Generator(np.random.PCG64(p.seed))

    data = p.background_rms_uv * _aperiodic(rng, n_ch, n, sf, p.aperiodic_exponent)

    # Alpha: posterior channels at full amplitude, others at 30 %, random phase per channel.
    alpha_phase = rng.uniform(0, 2 * np.pi, n_ch)
    alpha_w = np.array([1.0 if c in POSTERIOR else 0.3 for c in chans])
    data += (alpha_w * p.alpha_amp_uv)[:, None] * np.sin(
        2 * np.pi * p.alpha_freq_hz * t[None, :] + alpha_phase[:, None]
    )

    # Line noise: same phase on every channel (common-mode pickup).
    line_phase = float(rng.uniform(0, 2 * np.pi))
    data += p.line_amp_uv * np.sin(2 * np.pi * p.line_freq_hz * t + line_phase)[None, :]

    # Blinks: 300 ms raised-cosine bumps on frontal channels.
    blinks = []
    blink_len = int(0.3 * sf)
    bump = 0.5 * (1 - np.cos(2 * np.pi * np.arange(blink_len) / (blink_len - 1)))
    blink_ch = [i for i, c in enumerate(chans) if c in FRONTAL]
    onset = p.blink_every_s / 2
    while onset + 0.3 <= p.duration_s:
        s0 = int(round(onset * sf))
        for i in blink_ch:
            weight = 1.0 if chans[i].startswith("Fp") else 0.4
            data[i, s0 : s0 + blink_len] += weight * p.blink_amp_uv * bump
        blinks.append(
            {
                "onset_s": round(s0 / sf, 6),
                "duration_s": 0.3,
                "amp_uv": p.blink_amp_uv,
                "channels": [chans[i] for i in blink_ch],
            }
        )
        onset += p.blink_every_s

    # Muscle: 20-100 Hz burst on temporal channels (or the last channel if none present).
    m0, m1 = (int(round(x * sf)) for x in p.muscle_burst_s)
    mus_ch = [i for i, c in enumerate(chans) if c in TEMPORAL] or [n_ch - 1]
    for i in mus_ch:
        data[i, m0:m1] += p.muscle_rms_uv * _band_noise(
            rng, m1 - m0, sf, 20.0, min(100.0, sf / 2 - 1)
        )
    muscle = [
        {
            "onset_s": m0 / sf,
            "duration_s": (m1 - m0) / sf,
            "band_hz": [20.0, min(100.0, sf / 2 - 1)],
            "rms_uv": p.muscle_rms_uv,
            "channels": [chans[i] for i in mus_ch],
        }
    ]

    # Bad channel: extra broadband noise.
    bad = []
    if p.bad_channel in chans:
        bi = chans.index(p.bad_channel)
        data[bi] += p.bad_channel_gain * p.background_rms_uv * rng.standard_normal(n)
        bad.append({"name": p.bad_channel, "kind": "noisy", "gain": p.bad_channel_gain})

    # Events: alternating codes 1/2 every event_every_s, starting at 1 s.
    events = []
    k, onset = 0, 1.0
    while onset < p.duration_s:
        code = 1 + (k % 2)
        s = int(round(onset * sf))
        events.append({"onset_s": s / sf, "sample": s, "code": code, "label": f"stim/{code}"})
        k += 1
        onset += p.event_every_s

    truth = {
        "generator": GENERATOR_VERSION,
        "params": {k: (list(v) if isinstance(v, tuple) else v) for k, v in asdict(p).items()},
        "sfreq": sf,
        "n_samples": n,
        "channels": chans,
        "units": "uV",
        "aperiodic": {"exponent": p.aperiodic_exponent, "rms_uv": p.background_rms_uv},
        "alpha": {
            "freq_hz": p.alpha_freq_hz,
            "amp_uv": p.alpha_amp_uv,
            "full_amp_channels": [c for c in chans if c in POSTERIOR],
            "other_channels_weight": 0.3,
        },
        "line_noise": {"freq_hz": p.line_freq_hz, "amp_uv": p.line_amp_uv},
        "blinks": blinks,
        "muscle": muscle,
        "bad_channels": bad,
        "events": events,
        "data_sha256": data_sha256(data),
    }
    return data, truth


def data_sha256(data: np.ndarray) -> str:
    """SHA-256 of the float64 little-endian C-order bytes (determinism check)."""
    return hashlib.sha256(np.ascontiguousarray(data, dtype="<f8").tobytes()).hexdigest()


def welch_psd(x: np.ndarray, sfreq: float, nperseg: int) -> tuple[np.ndarray, np.ndarray]:
    """Welch PSD (Hann window, 50 % overlap, mean of segments). numpy only."""
    x = np.asarray(x, dtype=float)
    step = nperseg // 2
    win = np.hanning(nperseg)
    scale = 1.0 / (sfreq * (win**2).sum())
    segs = [x[s : s + nperseg] for s in range(0, len(x) - nperseg + 1, step)]
    ps = [np.abs(np.fft.rfft((seg - seg.mean()) * win)) ** 2 * scale for seg in segs]
    psd = np.mean(ps, axis=0)
    psd[1:-1] *= 2
    return np.fft.rfftfreq(nperseg, 1.0 / sfreq), psd
