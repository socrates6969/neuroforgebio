"""Webhook signatures (SEC-045).

Headers on every delivery::

    NF-Webhook-Id: <event id>
    NF-Webhook-Timestamp: <unix seconds>
    NF-Webhook-Signature: t=<unix seconds>,v1=<hex HMAC-SHA-256>[,v1=<hex>...]

``v1 = HMAC-SHA-256(key, "<t>." + raw body bytes)``. During a key rotation the platform signs with
every key that is still valid (new and previous), so a receiver holding either key verifies. A
receiver must reject a timestamp more than ``TOLERANCE_S`` (5 min) from its clock (replay window)
and compare in constant time. ``services/platform/examples/verify_webhook.py`` is the
dependency-free sample verifier for customers; ``verify`` here is the same rule.
"""

from __future__ import annotations

import hashlib
import hmac

HEADER_ID = "NF-Webhook-Id"
HEADER_TIMESTAMP = "NF-Webhook-Timestamp"
HEADER_SIGNATURE = "NF-Webhook-Signature"
SCHEME = "v1"
TOLERANCE_S = 300
KEY_BYTES = 32


class SignatureError(ValueError):
    """The signature header is missing, malformed, stale or does not verify."""


def signature(key: bytes, timestamp: int, body: bytes) -> str:
    return hmac.new(key, f"{int(timestamp)}.".encode("ascii") + body, hashlib.sha256).hexdigest()


def sign(keys: list[bytes], timestamp: int, body: bytes) -> str:
    """``NF-Webhook-Signature`` for ``body`` under every key in ``keys`` (newest first)."""
    if not keys:
        raise ValueError("no signing key")
    parts = [f"t={int(timestamp)}"] + [f"{SCHEME}={signature(k, timestamp, body)}" for k in keys]
    return ",".join(parts)


def parse(header: str) -> tuple[int, list[str]]:
    ts: int | None = None
    sigs: list[str] = []
    for item in header.split(","):
        k, sep, v = item.strip().partition("=")
        if not sep:
            raise SignatureError("malformed signature header")
        if k == "t":
            if ts is not None or not v.isdigit() or len(v) > 12:
                raise SignatureError("malformed timestamp")
            ts = int(v)
        elif k == SCHEME:
            sigs.append(v)
    if ts is None or not sigs:
        raise SignatureError("signature header needs t= and v1=")
    return ts, sigs


def verify(header: str, body: bytes, key: bytes, now: float, tolerance_s: int = TOLERANCE_S) -> int:
    """Return the verified timestamp or raise :class:`SignatureError`."""
    ts, sigs = parse(header)
    if abs(now - ts) > tolerance_s:
        raise SignatureError("timestamp outside the tolerance (replay?)")
    expected = signature(key, ts, body)
    if not any(hmac.compare_digest(expected, s) for s in sigs):
        raise SignatureError("no signature matches")
    return ts
