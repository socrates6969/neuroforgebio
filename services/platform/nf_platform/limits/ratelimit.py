"""In-process token-bucket rate limiter (BUILD-GUIDE 4.8; SEC-075).

This is the *local* layer: one bucket per key (an authenticated credential, or a client IP / e-mail
hash for the public early-access form) inside one API process. It protects a single instance and
gives the same 429 problem+json the gateway gives. It is NOT the whole defence: with N replicas a
client gets N x the rate, so the edge gateway enforces the global per-tenant limit (see
``docs/platform/rate-limits.md``).

The clock is injectable so tests never sleep.
"""

from __future__ import annotations

import math
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class _Bucket:
    tokens: float
    updated: float


class RateLimiter:
    """``rate`` tokens per second refill, at most ``burst`` tokens. ``take(key)`` returns 0.0 when
    the request may proceed, else the seconds until one token is available.

    Memory is bounded: at most ``max_keys`` buckets (least recently used evicted; an evicted key
    starts again with a full bucket, which only ever errs towards allowing).
    """

    def __init__(
        self,
        rate: float,
        burst: int,
        *,
        clock: Callable[[], float] = time.monotonic,
        max_keys: int = 100_000,
    ) -> None:
        if rate <= 0 or burst < 1:
            raise ValueError("rate must be > 0 and burst >= 1")
        self.rate = float(rate)
        self.burst = float(burst)
        self.clock = clock
        self.max_keys = max_keys
        self._buckets: OrderedDict[str, _Bucket] = OrderedDict()
        self._lock = threading.Lock()

    def take(self, key: str, cost: float = 1.0) -> float:
        now = self.clock()
        with self._lock:
            b = self._buckets.get(key)
            if b is None:
                b = _Bucket(tokens=self.burst, updated=now)
                self._buckets[key] = b
                if len(self._buckets) > self.max_keys:
                    self._buckets.popitem(last=False)
            else:
                self._buckets.move_to_end(key)
                b.tokens = min(self.burst, b.tokens + (now - b.updated) * self.rate)
                b.updated = now
            if b.tokens >= cost:
                b.tokens -= cost
                return 0.0
            return (cost - b.tokens) / self.rate


def retry_after_header(wait_s: float) -> dict[str, str]:
    """``Retry-After`` in whole seconds (RFC 9110 §10.2.3), at least 1."""
    return {"Retry-After": str(max(1, math.ceil(wait_s)))}
