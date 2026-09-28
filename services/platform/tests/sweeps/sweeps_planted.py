"""Synthetic two-class EEG with a KNOWN planted effect for the 3.6 sweep acceptance test.

Construction (every number below is a parameter of :class:`Planted`; nothing is fitted):

- ``n_channels`` channels of white Gaussian noise, ``noise_rms_uv`` RMS (flat PSD 0..Nyquist);
- common-mode line noise at ``line_hz`` with amplitude ``line_amp_uv`` (class-independent);
- ``n_trials`` trials, one event every ``trial_every_s`` seconds starting at ``lead_s``; the labels
  are a seeded, balanced permutation of codes 1 and 2;
- class 2 ONLY: on every channel, a Hann-tapered burst ``effect_amp_uv * hann(t) * sin(2 pi f t +
  phi)`` at ``effect_hz`` covering exactly the 1 s epoch after the event (random phase per trial and
  channel). Its spectrum is the Hann main lobe ``effect_hz +- 2/T`` = [3, 7] Hz for T = 1 s, with
  side lobes at or below -31 dB that fall 18 dB/octave.

So the class information lives only in the band [3, 7] Hz. A high-pass filter whose stop band
covers that band removes it (decoding falls to chance); one whose pass band covers it keeps it.
A notch at 50 or 60 Hz changes nothing below 30 Hz (the feature bands), so decoding must not
depend on the notch choice. ``retained_fraction`` computes, from the filter's actual taps, the
fraction of the class-2 burst energy that survives a filter: the test derives its expected
ordering from that number, not from a run.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

EFFECT_BAND_HZ = (3.0, 7.0)


@dataclass(frozen=True)
class Planted:
    seed: int = 7
    sfreq: float = 128.0
    n_channels: int = 4
    n_trials: int = 60
    trial_every_s: float = 1.5
    lead_s: float = 1.0
    epoch_s: float = 1.0
    noise_rms_uv: float = 10.0
    line_hz: float = 50.0
    line_amp_uv: float = 5.0
    effect_hz: float = 5.0
    effect_amp_uv: float = 8.0

    @property
    def n_samples(self) -> int:
        return int(round((self.lead_s + self.n_trials * self.trial_every_s + 1.0) * self.sfreq))

    @property
    def epoch_len(self) -> int:
        return int(round(self.epoch_s * self.sfreq))

    def channels(self) -> list[str]:
        return [f"E{i + 1}" for i in range(self.n_channels)]


def burst(p: Planted, phase: float) -> np.ndarray:
    n = p.epoch_len
    t = np.arange(n) / p.sfreq
    return p.effect_amp_uv * np.hanning(n) * np.sin(2 * np.pi * p.effect_hz * t + phase)


def generate(p: Planted | None = None) -> tuple[np.ndarray, dict]:
    """Return ``(data_uv[n_channels, n_samples], truth)``; truth lists the events and labels."""
    p = p or Planted()
    rng = np.random.Generator(np.random.PCG64(p.seed))
    n, sf = p.n_samples, p.sfreq
    data = p.noise_rms_uv * rng.standard_normal((p.n_channels, n))
    t = np.arange(n) / sf
    data += p.line_amp_uv * np.sin(2 * np.pi * p.line_hz * t)[None, :]
    half = p.n_trials // 2
    labels = rng.permutation(np.array([1] * half + [2] * (p.n_trials - half)))
    phases = rng.uniform(0, 2 * np.pi, (p.n_trials, p.n_channels))
    events = []
    for i, code in enumerate(labels):
        s0 = int(round((p.lead_s + i * p.trial_every_s) * sf))
        if code == 2:
            for c in range(p.n_channels):
                data[c, s0 : s0 + p.epoch_len] += burst(p, float(phases[i, c]))
        events.append({"onset_s": s0 / sf, "label": f"stim/{int(code)}", "code": int(code)})
    truth = {
        "sfreq": sf,
        "channels": p.channels(),
        "events": events,
        "labels": [int(x) for x in labels],
        "effect_band_hz": list(EFFECT_BAND_HZ),
    }
    return data, truth


def retained_fraction(p: Planted, h: np.ndarray, n_fft: int = 8192) -> float:
    """Fraction of the class-2 burst energy passed by an FIR filter with taps ``h`` (zero phase:
    MNE applies ``h`` once with delay compensation, so the gain is ``|H(f)|``)."""
    b = np.fft.rfft(burst(p, 0.0), n_fft)
    hf = np.fft.rfft(h, n_fft)
    e_in = float(np.sum(np.abs(b) ** 2))
    return float(np.sum(np.abs(b * hf) ** 2) / e_in)
