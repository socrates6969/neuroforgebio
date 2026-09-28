"""Sample sources for the edge prototype. Both expose the same small inlet-like interface.

``SyntheticSource`` produces a deterministic signal paced by the monotonic clock, so a test can
recompute exactly what was acquired (``expected``). ``LslSource`` reads an existing LSL stream
through a pylsl ``StreamInlet``. SEC-091: nothing here creates an LSL outlet or opens a device
handle; test outlets live under ``tests/``.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np


@dataclass(frozen=True)
class SourceInfo:
    name: str
    n_channels: int
    sfreq: float
    dtype: str  # int16 | int32 | float32 | float64
    ch_names: tuple[str, ...]
    units: str = "uV"
    modality: str = "EEG"


class Source(Protocol):
    info: SourceInfo

    def pull_chunk(self, max_samples: int) -> tuple[np.ndarray, np.ndarray]:
        """Return (samples (n, n_channels), timestamps (n,)) acquired since the last call;
        n may be 0. Never blocks for long."""
        ...

    def time_correction(self) -> float:
        """Current clock offset (remote - local), seconds (LSL semantics)."""
        ...

    def local_clock(self) -> float:
        """The local LSL clock, seconds."""
        ...

    def close(self) -> None: ...


def synthetic_block(start: int, n: int, n_channels: int, sfreq: float, dtype: str) -> np.ndarray:
    """Samples ``start .. start+n`` of the deterministic test signal, shape (n, n_channels)."""
    i = np.arange(start, start + n, dtype=np.int64)[:, None]
    c = np.arange(n_channels, dtype=np.int64)[None, :]
    if np.dtype(dtype).kind == "f":
        # A few µV-scale sines plus a slow ramp; float64 math, cast once (bit-reproducible).
        t = i.astype(np.float64) / sfreq
        x = 40.0 * np.sin(2 * np.pi * (5.0 + c) * t) + 0.001 * (i % 1000) + c
        return x.astype(dtype)
    return (((i * 7 + c * 131) % 4001) - 2000).astype(dtype)


class SyntheticSource:
    """A paced synthetic "device": ``sfreq`` samples per second of the monotonic clock.

    Timestamps are ``t0 + index / sfreq`` on the local clock, like a regular LSL stream. The
    clock offset is a known function of time so tests can check it was stored unchanged.
    """

    def __init__(
        self,
        n_channels: int = 64,
        sfreq: float = 1000.0,
        dtype: str = "float32",
        *,
        name: str = "synthetic",
        clock: Any = time.monotonic,
        max_samples: int | None = None,
    ) -> None:
        self.info = SourceInfo(
            name=name,
            n_channels=n_channels,
            sfreq=float(sfreq),
            dtype=dtype,
            ch_names=tuple(f"EEG{i:03d}" for i in range(n_channels)),
        )
        self._clock = clock
        self._t0 = clock()
        self._next = 0
        self._max = max_samples
        self._lock = threading.Lock()

    @property
    def produced(self) -> int:
        return self._next

    def local_clock(self) -> float:
        return float(self._clock())

    def time_correction(self) -> float:
        # A slowly drifting offset (remote clock ahead by ~1.5 ms, drifting 2 µs/s).
        return 0.0015 + 2e-6 * (self._clock() - self._t0)

    def pull_chunk(self, max_samples: int) -> tuple[np.ndarray, np.ndarray]:
        with self._lock:
            due = int((self._clock() - self._t0) * self.info.sfreq)
            if self._max is not None:
                due = min(due, self._max)
            n = max(0, min(max_samples, due - self._next))
            start = self._next
            self._next += n
        data = synthetic_block(start, n, self.info.n_channels, self.info.sfreq, self.info.dtype)
        ts = self._t0 + np.arange(start, start + n, dtype=np.float64) / self.info.sfreq
        return data, ts

    def expected(self, n: int) -> tuple[np.ndarray, np.ndarray]:
        data = synthetic_block(0, n, self.info.n_channels, self.info.sfreq, self.info.dtype)
        return data, self._t0 + np.arange(n, dtype=np.float64) / self.info.sfreq

    def close(self) -> None:
        pass


class LslSource:
    """An LSL inlet (pylsl). Resolves one stream by property, e.g. ``("name", "nf-synth")``."""

    def __init__(self, prop: str, value: str, *, timeout: float = 5.0, units: str = "uV") -> None:
        import pylsl  # noqa: PLC0415 (optional dependency: only the LSL bridge needs it)

        self._pylsl = pylsl
        found = pylsl.resolve_byprop(prop, value, 1, timeout)
        if not found:
            raise TimeoutError(f"no LSL stream with {prop}={value!r}")
        si = found[0]
        fmt = {
            pylsl.cf_float32: "float32",
            pylsl.cf_double64: "float64",
            pylsl.cf_int16: "int16",
            pylsl.cf_int32: "int32",
        }.get(si.channel_format())
        if fmt is None:
            raise ValueError("unsupported LSL channel format")
        self._inlet = pylsl.StreamInlet(si, max_buflen=360, recover=True)
        self._inlet.open_stream(timeout=timeout)  # buffer from now on, before the first pull
        self.info = SourceInfo(
            name=si.name(),
            n_channels=si.channel_count(),
            sfreq=float(si.nominal_srate()),
            dtype=fmt,
            ch_names=tuple(f"ch{i:03d}" for i in range(si.channel_count())),
            units=units,
        )
        self._np_dtype = np.dtype(fmt)

    def local_clock(self) -> float:
        return float(self._pylsl.local_clock())

    def time_correction(self) -> float:
        return float(self._inlet.time_correction(timeout=1.0))

    def pull_chunk(self, max_samples: int) -> tuple[np.ndarray, np.ndarray]:
        samples, ts = self._inlet.pull_chunk(timeout=0.0, max_samples=max_samples)
        if not ts:
            return np.empty((0, self.info.n_channels), self._np_dtype), np.empty(0)
        return np.asarray(samples, dtype=self._np_dtype), np.asarray(ts, dtype=np.float64)

    def close(self) -> None:
        self._inlet.close_stream()
