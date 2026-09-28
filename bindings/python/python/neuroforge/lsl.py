"""LSL bridge: an LSL **inlet** feeding an nf-core stream (BUILD-GUIDE 4.4).

SEC-091: this module only ever *receives*. It resolves an existing LSL stream and opens an
inlet; it creates no outlets and opens no device handles. Test outlets live under ``tests/``
only (``tools/hw-guard`` enforces both).

SEC-094 (timing provenance): the inlet is opened **without** post-processing, so the original
sender timestamps reach the platform unchanged. Clock offsets are captured with
``lsl_time_correction_ex`` (offset, remote time and LSL's reported uncertainty) and stored next
to the samples; mapping to the local clock is a separate, derived step
(:func:`to_local_clock`) that never overwrites the originals.

Requires ``pylsl`` (``pip install neuroforge[lsl]``).
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass, field

import numpy as np

__all__ = ["ClockOffset", "LslInlet", "to_local_clock"]


@dataclass(frozen=True)
class ClockOffset:
    """One LSL time-correction measurement: ``local = remote + offset`` (+/- uncertainty)."""

    collection_time: float  # local LSL clock when the estimate was read
    offset: float
    remote_time: float
    uncertainty: float


@dataclass
class LslInlet:
    """Resolve one LSL stream by property (e.g. ``("name", "EEG-amp")``) and read from it."""

    prop: str
    value: str
    timeout: float = 5.0
    max_buflen: int = 360
    offsets: list[ClockOffset] = field(default_factory=list)

    def __post_init__(self) -> None:
        import pylsl  # optional dependency

        self._pylsl = pylsl
        found = pylsl.resolve_byprop(self.prop, self.value, 1, self.timeout)
        if not found:
            raise TimeoutError(f"no LSL stream with {self.prop}={self.value!r}")
        si = found[0]
        fmt = {
            pylsl.cf_float32: "float32",
            pylsl.cf_double64: "float64",
            pylsl.cf_int16: "int16",
            pylsl.cf_int32: "int32",
        }.get(si.channel_format())
        if fmt is None:
            raise ValueError(
                "unsupported LSL channel format (stream protocol: int16/int32/float32/float64)"
            )
        # processing_flags=0: timestamps are delivered exactly as the sender stamped them
        self._inlet = pylsl.StreamInlet(
            si, max_buflen=self.max_buflen, recover=True, processing_flags=0
        )
        self._inlet.open_stream(timeout=self.timeout)
        self.name = si.name()
        self.n_channels = si.channel_count()
        self.sfreq = float(si.nominal_srate())
        self.dtype = fmt
        self._np = np.dtype(fmt)
        lib = pylsl.lib.lib
        self._tc_ex = lib.lsl_time_correction_ex
        self._tc_ex.restype = ctypes.c_double

    def local_clock(self) -> float:
        return float(self._pylsl.local_clock())

    def time_correction_ex(self, timeout: float = 2.0) -> ClockOffset:
        """Offset with LSL's reported uncertainty (``lsl_time_correction_ex``)."""
        remote = ctypes.c_double()
        unc = ctypes.c_double()
        err = ctypes.c_int()
        off = self._tc_ex(
            self._inlet.obj,
            ctypes.byref(remote),
            ctypes.byref(unc),
            ctypes.c_double(timeout),
            ctypes.byref(err),
        )
        self._pylsl.util.handle_error(err)
        m = ClockOffset(self.local_clock(), float(off), remote.value, unc.value)
        self.offsets.append(m)
        return m

    def time_correction(self) -> float:
        return self.time_correction_ex().offset

    def pull_chunk(self, max_samples: int) -> tuple[np.ndarray, np.ndarray]:
        samples, ts = self._inlet.pull_chunk(timeout=0.0, max_samples=max_samples)
        if not ts:
            return np.empty((0, self.n_channels), self._np), np.empty(0)
        return np.asarray(samples, dtype=self._np), np.asarray(ts, dtype=np.float64)

    def close(self) -> None:
        self._inlet.close_stream()


def to_local_clock(timestamps: np.ndarray, offsets: list[ClockOffset] | np.ndarray) -> np.ndarray:
    """Derived local-clock timestamps: each sample gets the offset of the nearest measurement
    (by remote time). Returns a new array; the originals stay as recorded (SEC-094)."""
    ts = np.asarray(timestamps, dtype=np.float64)
    if isinstance(offsets, np.ndarray):
        remote, off = offsets[:, 0], offsets[:, 1]
    else:
        remote = np.asarray([o.remote_time for o in offsets])
        off = np.asarray([o.offset for o in offsets])
    if len(off) == 0:
        raise ValueError("no clock offsets recorded")
    order = np.argsort(remote)
    remote, off = remote[order], off[order]
    idx = np.clip(np.searchsorted(remote, ts), 1, len(remote)) - 1
    nxt = np.clip(idx + 1, 0, len(remote) - 1)
    nearer = np.abs(remote[nxt] - ts) < np.abs(remote[idx] - ts)
    return ts + np.where(nearer, off[nxt], off[idx])
