"""Webhook endpoints, signing-key rotation and the delivery queue (4.6; SEC-045, SEC-076).

Signing keys (the endpoint's "signing secret", shown to the customer once) are random 256-bit
values rendered as ``nfb_whk_<base64url>``; the HMAC key is that string's UTF-8 bytes (as in the
sample verifier). At rest a key is AES-256-GCM-encrypted under a wrapping key derived (HKDF-SHA-256)
from the server pepper (KMS-held in a deployment), with the tenant, endpoint and key version bound
as associated data, so a row copied to another endpoint does not decrypt.

Rotation keeps the previous key valid for ``Settings.webhook_rotation_overlap_s``; while both are
valid every delivery carries both signatures.

Delivery: an event creates one ``webhook_delivery`` row per subscribed endpoint (same
transaction as the state change that caused it). ``claim_due`` (role ``nf_webhook``) leases due
rows across tenants; ``deliver`` sends one in the tenant's own session: resolve + pin (SSRF), sign,
POST with a timeout and no redirects; 2xx = delivered; otherwise retry with exponential backoff
(``base * 2**(attempt-1)``, capped) until ``webhook_max_attempts``, then ``failed``.
Transports are injectable; tests never touch the network.
"""

from __future__ import annotations

import base64
import json
import logging
import secrets
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy import Engine, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from nf_platform.config import SecretProvider, Settings
from nf_platform.db import models as m
from nf_platform.db.context import role_session, tenant_session
from nf_platform.webhooks import signing, ssrf
from nf_platform.webhooks.payloads import EVENTS, RunFinishedData, RunFinishedEvent

KEY_PREFIX = "nfb_whk_"
WEBHOOK_DB_ROLE = "nf_webhook"
SERVICE_ID = "svc:webhooks"
USER_AGENT = "nf-webhooks/1"
_WRAP_INFO = b"nf.webhook-key-wrap.v1"
# Allow-listed fields only (SEC-147): never keys, payloads or URLs with credentials.
log = logging.getLogger("nf_platform.webhooks")


class WebhookError(ValueError):
    """Invalid webhook request (422)."""


# ---------------------------------------------------------------- key wrapping
def _wrap_key(secret_provider: SecretProvider, version: str | None = None) -> tuple[str, bytes]:
    cur_version, pepper = secret_provider.api_key_pepper()
    if version is not None and version != cur_version:
        raise WebhookError("signing key was wrapped under a retired pepper version")
    hk = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_WRAP_INFO)
    return cur_version, hk.derive(pepper)


def _aad(tenant_id: uuid.UUID, endpoint_id: uuid.UUID, version: int) -> bytes:
    return f"nf.webhook-key.v1|{tenant_id}|{endpoint_id}|{version}".encode()


def _seal(sp: SecretProvider, tenant_id, endpoint_id, version: int, key: str) -> tuple[str, bytes]:
    wrap_version, wk = _wrap_key(sp)
    nonce = secrets.token_bytes(12)
    ct = AESGCM(wk).encrypt(nonce, key.encode("utf-8"), _aad(tenant_id, endpoint_id, version))
    return wrap_version, nonce + ct


def _open(sp: SecretProvider, row: m.WebhookKey) -> bytes:
    _, wk = _wrap_key(sp, row.wrap_version)
    blob = bytes(row.key_ciphertext)
    return AESGCM(wk).decrypt(
        blob[:12], blob[12:], _aad(row.tenant_id, row.endpoint_id, row.version)
    )


def new_signing_key() -> str:
    raw = secrets.token_bytes(signing.KEY_BYTES)
    return KEY_PREFIX + base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


# ---------------------------------------------------------------- endpoints
@dataclass(frozen=True)
class IssuedEndpoint:
    endpoint: m.WebhookEndpoint
    signing_key: str  # shown once


def create_endpoint(
    s: Session,
    *,
    tenant_id: uuid.UUID,
    created_by: str,
    url: str,
    event_types: list[str],
    description: str | None,
    secret_provider: SecretProvider,
) -> IssuedEndpoint:
    try:
        ssrf.check_url(url)
    except ssrf.BlockedUrl as e:
        raise WebhookError(f"url rejected: {e}") from e
    unknown = set(event_types) - set(EVENTS)
    if not event_types or unknown:
        raise WebhookError(f"event_types must be a non-empty subset of {sorted(EVENTS)}")
    ep = m.WebhookEndpoint(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        url=url,
        description=description,
        event_types=sorted(set(event_types)),
        created_by=created_by,
    )
    s.add(ep)
    s.flush()
    key = new_signing_key()
    wrap_version, blob = _seal(secret_provider, tenant_id, ep.id, 1, key)
    s.add(
        m.WebhookKey(
            tenant_id=tenant_id,
            endpoint_id=ep.id,
            version=1,
            key_ciphertext=blob,
            wrap_version=wrap_version,
        )
    )
    s.flush()
    s.refresh(ep)
    return IssuedEndpoint(ep, key)


def key_versions(s: Session, endpoint_id: uuid.UUID) -> list[m.WebhookKey]:
    q = select(m.WebhookKey).where(m.WebhookKey.endpoint_id == endpoint_id)
    return list(s.scalars(q.order_by(m.WebhookKey.version.desc())))


def rotate_key(
    s: Session, ep: m.WebhookEndpoint, *, secret_provider: SecretProvider, overlap_s: int, now=None
) -> tuple[str, int, datetime]:
    """New key version; every older still-valid key expires ``overlap_s`` from now. Returns
    (new key, new version, old keys' expiry)."""
    now = now or datetime.now(UTC)
    versions = key_versions(s, ep.id)
    new_version = (versions[0].version if versions else 0) + 1
    until = now + timedelta(seconds=overlap_s)
    for k in versions:
        if k.expires_at is None or k.expires_at > until:
            k.expires_at = until
    key = new_signing_key()
    wrap_version, blob = _seal(secret_provider, ep.tenant_id, ep.id, new_version, key)
    s.add(
        m.WebhookKey(
            tenant_id=ep.tenant_id,
            endpoint_id=ep.id,
            version=new_version,
            key_ciphertext=blob,
            wrap_version=wrap_version,
        )
    )
    s.flush()
    return key, new_version, until


def active_keys(s: Session, ep_id: uuid.UUID, sp: SecretProvider, now: datetime) -> list[bytes]:
    """Plaintext HMAC keys still valid at ``now``, newest first."""
    return [
        _open(sp, k) for k in key_versions(s, ep_id) if k.expires_at is None or k.expires_at > now
    ]


# ---------------------------------------------------------------- events
def enqueue(s: Session, tenant_id: uuid.UUID, event: RunFinishedEvent) -> int:
    """One pending delivery per enabled endpoint of ``tenant_id`` subscribed to the event type.
    Runs in the caller's tenant session and transaction. Returns the number of deliveries."""
    q = select(m.WebhookEndpoint).where(
        m.WebhookEndpoint.tenant_id == tenant_id,
        m.WebhookEndpoint.disabled_at.is_(None),
        m.WebhookEndpoint.event_types.contains([event.type]),
    )
    payload = json.loads(event.model_dump_json())
    n = 0
    for ep in s.scalars(q).all():
        seen = s.scalar(
            select(m.WebhookDelivery.id).where(
                m.WebhookDelivery.endpoint_id == ep.id, m.WebhookDelivery.event_id == event.id
            )
        )
        if seen is not None:  # the same event is enqueued at most once per endpoint
            continue
        try:
            # savepoint: a concurrent enqueue of the same event (uq_webhook_delivery_event) is a
            # harmless duplicate, not an error for the caller's transaction
            with s.begin_nested():
                s.add(
                    m.WebhookDelivery(
                        tenant_id=tenant_id,
                        endpoint_id=ep.id,
                        event_id=event.id,
                        event_type=event.type,
                        payload=payload,
                    )
                )
        except IntegrityError:
            continue
        n += 1
    return n


def run_finished(s: Session, run: m.Run) -> int:
    """Hook called by ``nf_platform.jobs.runs`` whenever a run reaches a terminal state."""
    if run.state not in ("succeeded", "failed", "cancelled"):
        return 0
    event = RunFinishedEvent(
        id=uuid.uuid5(uuid.NAMESPACE_URL, f"nf:run.finished:{run.id}"),
        type="run.finished",
        created_at=datetime.now(UTC),
        tenant_id=run.tenant_id,
        data=RunFinishedData(
            run_id=run.id,
            pipeline_ref=run.pipeline_ref,
            pipeline_version_id=run.pipeline_version_id,
            recording_id=run.recording_id,
            state=run.state,  # type: ignore[arg-type]
            finished_at=run.finished_at,
            prov_activity_id=run.prov_activity_id,
        ),
    )
    return enqueue(s, run.tenant_id, event)


# ---------------------------------------------------------------- delivery
class Transport(Protocol):
    def post(
        self, target: ssrf.PinnedTarget, headers: dict[str, str], body: bytes, timeout_s: float
    ) -> int:
        """POST ``body`` to ``target.address`` (SNI/Host = ``target.host``); return the status.
        Must not follow redirects. Raise ``OSError`` on network failure."""
        ...


class HttpxTransport:
    """Production transport: connects to the pinned, checked address; TLS is verified against the
    host name (SNI); redirects are never followed. Not exercised by tests (no egress)."""

    def post(self, target, headers, body, timeout_s):  # pragma: no cover - network
        import httpx

        parts = target.url.split("/", 3)
        path = "/" + (parts[3] if len(parts) > 3 else "")
        ip = f"[{target.address}]" if ":" in target.address else target.address
        url = f"https://{ip}:{target.port}{path}"
        with httpx.Client(timeout=timeout_s, follow_redirects=False, trust_env=False) as c:
            r = c.post(
                url,
                content=body,
                headers={**headers, "Host": target.host},
                extensions={"sni_hostname": target.host},
            )
        return r.status_code


def backoff_s(attempt: int, settings: Settings) -> float:
    return min(settings.webhook_backoff_max_s, settings.webhook_backoff_base_s * 2 ** (attempt - 1))


def claim_due(
    limit: int, *, engine: Engine | None = None, lease_s: float = 120.0
) -> list[tuple[str, uuid.UUID]]:
    """Lease up to ``limit`` due deliveries of any tenant (role ``nf_webhook``); returns
    (tenant_id, delivery_id). The lease (``next_attempt_at`` moved forward) keeps a second
    dispatcher off them while this one delivers."""
    with role_session(WEBHOOK_DB_ROLE, engine=engine) as s:
        rows = s.execute(
            text(
                "SELECT tenant_id, id FROM webhook_delivery "
                "WHERE state = 'pending' AND next_attempt_at <= now() "
                "ORDER BY next_attempt_at LIMIT :n FOR UPDATE SKIP LOCKED"
            ),
            {"n": limit},
        ).all()
        if rows:
            s.execute(
                text(
                    "UPDATE webhook_delivery "
                    "SET next_attempt_at = now() + make_interval(secs => :l) "
                    "WHERE id = ANY(:ids)"
                ),
                {"l": lease_s, "ids": [r[1] for r in rows]},
            )
    return [(str(r[0]), r[1]) for r in rows]


def deliver(
    tenant_id: str,
    delivery_id: uuid.UUID,
    *,
    settings: Settings,
    transport: Transport,
    resolver: ssrf.Resolver = ssrf.system_resolver,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    engine: Engine | None = None,
) -> str:
    """Attempt one delivery; returns the delivery state afterwards."""
    from nf_platform.storage.runtime import service_principal

    with tenant_session(service_principal(tenant_id, SERVICE_ID), engine=engine) as s:
        d = s.scalar(
            select(m.WebhookDelivery).where(m.WebhookDelivery.id == delivery_id).with_for_update()
        )
        if d is None or d.state != "pending":
            return d.state if d is not None else "missing"
        ep = s.scalar(select(m.WebhookEndpoint).where(m.WebhookEndpoint.id == d.endpoint_id))
        now = clock()
        d.attempts += 1
        status: int | None = None
        error: str | None = None
        if ep is None or ep.disabled_at is not None:
            error = "endpoint disabled"
        else:
            body = json.dumps(d.payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
            try:
                target = ssrf.resolve_pinned(ep.url, resolver)
                keys = active_keys(s, ep.id, settings.secrets, now)
                ts = int(now.timestamp())
                headers = {
                    "Content-Type": "application/json",
                    "User-Agent": USER_AGENT,
                    signing.HEADER_ID: str(d.event_id),
                    signing.HEADER_TIMESTAMP: str(ts),
                    signing.HEADER_SIGNATURE: signing.sign(keys, ts, body),
                }
                status = transport.post(target, headers, body, settings.webhook_timeout_s)
            except ssrf.BlockedUrl as e:
                error = f"blocked: {e}"
            except (OSError, TimeoutError) as e:
                error = f"network: {type(e).__name__}"
            except (WebhookError, InvalidTag):
                # e.g. the key was sealed under a retired pepper version: this delivery cannot be
                # signed. It is retried with backoff and ends failed; other rows are unaffected.
                error = "signing key unavailable"
        d.last_status = status
        d.last_error = error
        if status is not None and 200 <= status < 300:
            d.state = "delivered"
            d.delivered_at = now
            d.last_error = None
        elif (
            ep is None or ep.disabled_at is not None or d.attempts >= settings.webhook_max_attempts
        ):
            d.state = "failed"
        else:
            if error is None:
                d.last_error = f"http {status}"
            d.next_attempt_at = now + timedelta(seconds=backoff_s(d.attempts, settings))
        return d.state


def deliver_due(
    *,
    settings: Settings,
    transport: Transport,
    resolver: ssrf.Resolver = ssrf.system_resolver,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    engine: Engine | None = None,
    limit: int = 50,
) -> dict[str, int]:
    """One dispatcher pass: claim, deliver, count the resulting states."""
    counts: dict[str, int] = {}
    for tenant_id, did in claim_due(limit, engine=engine):
        try:
            st = deliver(
                tenant_id,
                did,
                settings=settings,
                transport=transport,
                resolver=resolver,
                clock=clock,
                engine=engine,
            )
        except Exception as e:  # one bad row must never abort the batch (other tenants' rows)
            log.error(
                "webhook delivery crashed",
                extra={"delivery_id": str(did), "error": type(e).__name__},
            )
            st = _record_crash(tenant_id, did, type(e).__name__, settings, clock, engine)
        counts[st] = counts.get(st, 0) + 1
    return counts


def _record_crash(
    tenant_id: str,
    delivery_id: uuid.UUID,
    error: str,
    settings: Settings,
    clock: Callable[[], datetime],
    engine: Engine | None,
) -> str:
    """Count the crashed attempt in a fresh transaction, so the row backs off and finally fails
    instead of being re-leased forever. If even that fails, the lease expires and it is retried."""
    from nf_platform.storage.runtime import service_principal

    try:
        with tenant_session(service_principal(tenant_id, SERVICE_ID), engine=engine) as s:
            d = s.scalar(
                select(m.WebhookDelivery)
                .where(m.WebhookDelivery.id == delivery_id)
                .with_for_update()
            )
            if d is None or d.state != "pending":
                return "error"
            d.attempts += 1
            d.last_error = f"internal: {error}"
            if d.attempts >= settings.webhook_max_attempts:
                d.state = "failed"
            else:
                d.next_attempt_at = clock() + timedelta(seconds=backoff_s(d.attempts, settings))
            return "error" if d.state == "pending" else d.state
    except Exception as e:
        log.error(
            "webhook crash not recorded",
            extra={"delivery_id": str(delivery_id), "error": type(e).__name__},
        )
        return "error"


def disable_endpoint(s: Session, ep: m.WebhookEndpoint, now: datetime | None = None) -> None:
    if ep.disabled_at is None:
        ep.disabled_at = now or datetime.now(UTC)
    s.execute(
        update(m.WebhookDelivery)
        .where(m.WebhookDelivery.endpoint_id == ep.id, m.WebhookDelivery.state == "pending")
        .values(state="failed", last_error="endpoint disabled")
    )


def endpoint_view(s: Session, ep: m.WebhookEndpoint, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    keys = key_versions(s, ep.id)
    return {
        "id": ep.id,
        "url": ep.url,
        "description": ep.description,
        "event_types": list(ep.event_types),
        "created_by": ep.created_by,
        "created_at": ep.created_at,
        "disabled_at": ep.disabled_at,
        "key_versions": [
            {"version": k.version, "created_at": k.created_at, "expires_at": k.expires_at}
            for k in keys
            if k.expires_at is None or k.expires_at > now
        ],
    }
