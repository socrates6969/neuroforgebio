"""Sample verifier for the platform's webhooks (Python standard library only; copy it freely).

Usage in a receiver (any web framework)::

    from verify_webhook import verify_webhook, WebhookRejected

    try:
        verify_webhook(raw_body, request.headers["NF-Webhook-Signature"], secret)
    except WebhookRejected:
        return 400
    event = json.loads(raw_body)
    # deduplicate on event["id"]: a retried delivery carries the same id

Rules (SEC-045):
- Verify the RAW request body bytes, before any JSON parsing or re-serialisation.
- ``NF-Webhook-Signature: t=<unix seconds>,v1=<hex>[,v1=<hex>]``; the signed message is
  ``b"<t>." + body`` under HMAC-SHA-256 with your endpoint's signing secret.
- Reject timestamps more than 5 minutes from your clock (replays), compare in constant time.
- During a secret rotation several ``v1=`` values are sent; one match is enough.
"""

from __future__ import annotations

import hashlib
import hmac
import time

TOLERANCE_SECONDS = 300


class WebhookRejected(Exception):
    pass


def verify_webhook(
    body: bytes,
    signature_header: str,
    secret: bytes,
    *,
    now: float | None = None,
    tolerance: int = TOLERANCE_SECONDS,
) -> int:
    """Return the signed timestamp if the delivery is authentic and fresh; raise otherwise."""
    timestamp = None
    candidates = []
    for part in signature_header.split(","):
        key, _, value = part.strip().partition("=")
        if key == "t" and value.isdigit():
            timestamp = int(value)
        elif key == "v1":
            candidates.append(value)
    if timestamp is None or not candidates:
        raise WebhookRejected("malformed signature header")
    current = time.time() if now is None else now
    if abs(current - timestamp) > tolerance:
        raise WebhookRejected("stale or future timestamp")
    expected = hmac.new(secret, str(timestamp).encode() + b"." + body, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, c) for c in candidates):
        raise WebhookRejected("signature mismatch")
    return timestamp
