"""Audit events (BUILD-GUIDE 2.8; SEC-100, SEC-103, SEC-147).

``emit(event)`` writes one event to the append-only ``audit_event`` table as the insert-only role
``nf_audit_writer`` (AppSec M2: it cannot write ``audit_batch``), in its own transaction (so
denials and failures are recorded even when the request's transaction rolls back). There is no
default sink: emitting before ``configure()`` raises, so a misconfigured process fails closed.

Payload hygiene: ``details`` keys are allow-listed and no value may look like a credential (API key,
JWT, bearer header); violating events are rejected rather than silently written.
"""

from __future__ import annotations

import re
import threading
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from sqlalchemy import Engine, insert

from nf_platform.config import AUDIT_WRITER_DB_ROLE
from nf_platform.db import models
from nf_platform.db.context import role_session

Outcome = Literal["success", "failure", "denied"]

# Event types (stable strings; auditors filter on them).
AUTH_SUCCESS = "auth.success"
AUTH_FAILURE = "auth.failure"
AUTHZ_DENIED = "authz.denied"
DATA_READ = "data.read"
DATA_EXPORT = "data.export"
DATA_CREATE = "data.create"
ADMIN_ACTION = "admin.action"
# Stream ingest events are defined next to the servicer (nf_platform.ingest.stream.service):
# stream.suspect, stream.conflict, stream.aborted, stream.rate_limited, stream.short_chunk.
BREAK_GLASS = (
    "admin.break_glass"  # SEC-025: reserved; break-glass flow arrives with the console (3.8)
)

DETAIL_KEYS = frozenset(
    {
        "status",
        "reason",
        "count",
        "method",
        "route",
        "scopes",
        "roles",
        "expires_at",
        "key_public_id",
        "missing_scope",
        "format",
        "seq",
        # m4-api: webhooks (4.6), SSE (4.6), early access (4.7)
        "event_types",
        "op",
        "key_version",
        "stream",
        "stored",
        "confirmed",
        # m5-ledger: governance changes carry {field, old, new, ...} (attribute values, never signal
        # data or names), consent scopes, DeletionJob phases, policy decisions
        "changes",
        "phase",
        "policy",
        "decision",
        "obligations",
        "duration_s",
        # m5-evidence: SHA-256 of an exported evidence kit
        "sha256",
        # stream.short_chunk (P7.7 R1): shortest non-final chunk in the aggregated window (ms)
        "min_duration_ms",
    }
)

# Things that must never reach an audit payload: our API keys, JWTs, Authorization headers, PEM
# blocks.
_SECRET_PATTERNS = (
    re.compile(r"nfb_live_"),
    re.compile(r"nfb_whk_"),  # m4-api: webhook signing secrets
    re.compile(r"nfd1\.[A-Za-z0-9_-]{8,}"),  # m4-api (M2-REVIEW F5): device tokens
    re.compile(r"eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\."),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{16,}"),
    re.compile(r"-----BEGIN [A-Z ]*KEY-----"),
    re.compile(r"\bnfd1\.[A-Za-z0-9_-]{8,}\."),  # device tokens (SEC-016, M2-REVIEW F5)
)


class AuditPayloadError(ValueError):
    """An event carried a non-allow-listed detail key or something that looks like a credential."""


@dataclass(frozen=True)
class AuditEvent:
    type: str
    outcome: Outcome
    action: str | None = None
    tenant_id: str | None = None
    actor_kind: str | None = None
    actor_id: str | None = None
    auth_method: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    request_id: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


def _check_value(v: Any) -> None:
    if isinstance(v, str):
        for pat in _SECRET_PATTERNS:
            if pat.search(v):
                raise AuditPayloadError("audit payload contains something that looks like a secret")
    elif isinstance(v, Mapping):
        for k, x in v.items():
            _check_value(k)
            _check_value(x)
    elif isinstance(v, (list, tuple, set, frozenset)):
        for x in v:
            _check_value(x)


def validate(event: AuditEvent) -> None:
    bad = set(event.details) - DETAIL_KEYS
    if bad:
        raise AuditPayloadError(f"detail keys not allow-listed: {sorted(bad)}")
    for name in (
        "type",
        "action",
        "tenant_id",
        "actor_kind",
        "actor_id",
        "auth_method",
        "resource_type",
        "resource_id",
        "request_id",
    ):
        _check_value(getattr(event, name))
    _check_value(dict(event.details))


class AuditSink(Protocol):
    def write(self, event: AuditEvent) -> None: ...


class PostgresAuditSink:
    """Inserts into ``audit_event`` as ``nf_audit_writer`` (INSERT only, no RETURNING: the role
    cannot read the table; the table is append-only)."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def write(self, event: AuditEvent) -> None:
        tenant = uuid.UUID(event.tenant_id) if event.tenant_id else None
        with role_session(AUDIT_WRITER_DB_ROLE, engine=self.engine) as s:
            # Core insert, ``inline``: no implicit ``RETURNING seq`` (the writer cannot SELECT)
            s.connection().execute(
                insert(models.AuditEvent.__table__)
                .inline()
                .values(
                    id=uuid.UUID(event.id),
                    tenant_id=tenant,
                    type=event.type,
                    action=event.action,
                    outcome=event.outcome,
                    actor_kind=event.actor_kind,
                    actor_id=event.actor_id,
                    auth_method=event.auth_method,
                    resource_type=event.resource_type,
                    resource_id=event.resource_id,
                    request_id=event.request_id,
                    details=_jsonable(event.details),
                )
            )


class MemoryAuditSink:
    """For unit tests of code that emits events without a database."""

    def __init__(self) -> None:
        self.events: list[AuditEvent] = []
        self._lock = threading.Lock()

    def write(self, event: AuditEvent) -> None:
        with self._lock:
            self.events.append(event)


def _jsonable(v: Any) -> Any:
    if isinstance(v, Mapping):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set, frozenset)):
        items = [_jsonable(x) for x in v]
        return sorted(items) if isinstance(v, (set, frozenset)) else items
    return v


_sink: AuditSink | None = None


def configure(sink: AuditSink | None) -> None:
    global _sink
    _sink = sink


def emit(event: AuditEvent) -> None:
    """Record one audit event. Raises if the payload is not clean or no sink is configured (fail
    closed)."""
    validate(event)
    if _sink is None:
        raise RuntimeError("audit sink not configured")
    _sink.write(event)
