"""Server-side stream sanity checks (SEC-041).

A violation never drops data: the chunk is stored, the time range becomes a ``suspect`` segment and
an audit event is raised. Checks: monotonic timestamps (within the chunk and across the boundary to
the previous chunk: catches spliced replays), sample-rate consistency, timestamp jumps, and
physically impossible amplitudes per modality. Channel count and dtype mismatches cannot be stored
in the array at all; they are rejected (loudly) before this module runs.

The amplitude limits are deliberately loose ("cannot be a biopotential at the electrode"), not
clinical ranges; they are placeholders for the data team to tune (recorded as an open item).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

# Volts per unit string.
UNIT_TO_V = {"v": 1.0, "mv": 1e-3, "uv": 1e-6, "µv": 1e-6, "μv": 1e-6, "nv": 1e-9}
# Max |physical value| in volts per modality (modality names as in db.models.MODALITIES).
MAX_ABS_V = {
    "EEG": 1.0,
    "iEEG": 1.0,
    "ECoG": 1.0,
    "SEEG": 1.0,
    "LFP": 1.0,
    "spikes": 1.0,
    "EMG": 1.0,
    "ENG": 1.0,
    "EOG": 1.0,
    "ECG": 1.0,
}
RATE_TOLERANCE = 0.10  # effective chunk rate within 10 % of the nominal rate
JUMP_SAMPLES = 10  # a boundary gap of more than 10 sample periods (+ 50 ms slack) is a jump
JUMP_SLACK_S = 0.05


@dataclass(frozen=True)
class ChannelLimit:
    modality: str
    units: str
    scale: float
    offset: float

    def max_abs_stored(self) -> float | None:
        v = UNIT_TO_V.get(self.units.strip().lower())
        lim = MAX_ABS_V.get(self.modality)
        if v is None or lim is None or self.scale == 0:
            return None
        return lim / v


def check_chunk(
    samples: np.ndarray,
    timestamps: np.ndarray,
    sfreq: float,
    prev_t_last: float | None,
    channels: Sequence[ChannelLimit],
) -> list[str]:
    """Return the list of violated rules (empty = ok). ``samples`` is (n_samples, n_channels)."""
    reasons: list[str] = []
    n = len(timestamps)
    if not np.all(np.isfinite(timestamps)):
        reasons.append("non-finite timestamps")
        return reasons
    if n > 1 and not np.all(np.diff(timestamps) > 0):
        reasons.append("non-monotonic timestamps")
    if prev_t_last is not None:
        gap = float(timestamps[0]) - prev_t_last
        if gap <= 0:
            reasons.append("timestamps go backwards across chunks (replay or splice)")
        elif gap > JUMP_SAMPLES / sfreq + JUMP_SLACK_S:
            reasons.append("timestamp jump between chunks")
    if n > 2:
        span = float(timestamps[-1] - timestamps[0])
        if span > 0:
            rate = (n - 1) / span
            if abs(rate - sfreq) / sfreq > RATE_TOLERANCE:
                reasons.append("sample rate inconsistent with the registered rate")
    if samples.dtype.kind == "f" and not np.all(np.isfinite(samples)):
        reasons.append("non-finite sample values")
    else:
        peak = np.max(np.abs(samples.astype(np.float64)), axis=0) if samples.size else []
        for i, ch in enumerate(channels):
            lim = ch.max_abs_stored()
            if lim is None:
                continue
            phys = abs(float(peak[i]) * ch.scale) + abs(ch.offset)
            if phys > lim:
                reasons.append("physically impossible amplitude")
                break
    return reasons
