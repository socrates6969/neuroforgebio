"""Test-only LSL outlet (SEC-091 allows outlets only under ``tests/``). It plays a synthetic
device whose timestamps are on a clock ``skew_s`` ahead of this machine's LSL clock."""

from __future__ import annotations

import threading
import time
import uuid

import numpy as np


class SyntheticOutlet:
    def __init__(
        self, n_channels: int = 8, sfreq: float = 250.0, *, skew_s: float = 0.0, chunk: int = 10
    ) -> None:
        import pylsl

        self.pylsl = pylsl
        self.name = f"nf-test-{uuid.uuid4().hex[:8]}"
        self.n_channels, self.sfreq, self.skew_s, self.chunk = n_channels, sfreq, skew_s, chunk
        info = pylsl.StreamInfo(self.name, "EEG", n_channels, sfreq, pylsl.cf_float32, self.name)
        self.outlet = pylsl.StreamOutlet(info, chunk_size=chunk)
        self.pushed: list[np.ndarray] = []
        self.stamps: list[np.ndarray] = []
        self.push_clock: list[float] = []  # true local LSL clock when each block was pushed
        self._stop = threading.Event()
        self._th: threading.Thread | None = None

    def start(self) -> None:
        self._th = threading.Thread(target=self._loop, daemon=True)
        self._th.start()

    def _loop(self) -> None:
        k = 0
        t_next = time.monotonic()
        while not self._stop.is_set():
            block = (
                np.arange(k, k + self.chunk)[:, None] * 0.5 + np.arange(self.n_channels)[None, :]
            ).astype(np.float32)
            now = self.pylsl.local_clock()
            stamps = now + self.skew_s + (np.arange(self.chunk) - (self.chunk - 1)) / self.sfreq
            for row, ts in zip(block, stamps, strict=True):
                self.outlet.push_sample(row.tolist(), float(ts))
            self.pushed.append(block)
            self.stamps.append(stamps)
            self.push_clock.append(now)
            k += self.chunk
            t_next += self.chunk / self.sfreq
            time.sleep(max(0.0, t_next - time.monotonic()))

    def stop(self) -> None:
        self._stop.set()
        if self._th is not None:
            self._th.join()

    def close(self) -> None:
        self.stop()
        del self.outlet
