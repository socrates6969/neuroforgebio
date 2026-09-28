"""Hourly audit batches with a per-tenant hash chain, written to the ``audit`` bucket (2.8; SEC-100,
SEC-105).

Batch object (the stored bytes ARE the canonical JSON that is hashed, NF-CJSON v1,
docs/spec/hashing.md §3):

    {"schema": "nf.audit-batch/v1", "scope": "<tenant uuid>|_platform", "seq": n, "prev": <id|null>,
     "created_at": "YYYY-MM-DDTHH:MM:SS.sssZ", "period": {"start": ts, "end": ts}, "events": [...]}

ID = ``auditb:sha256:`` + SHA-256(``nf.audit-batch.v1`` 0x00 payload): the same construction as the
``provb`` chain in hashing spec §5.3, with its own domain tag. ``auditb`` is not in spec v1's ID
table; it is proposed for v2 (see the M2 report).

Scheduling (AppSec M1): the queued job ``audit.batch`` (hourly per tenant) runs
``AuditBatcher.run(now, scopes)``, which closes the period ending at the last full hour, and then
writes a signed head anchor per scope; ``audit.verify`` (daily) checks the stored chain against the
``audit_batch`` rows, the events still in ``audit_event`` and the anchor
(:mod:`nf_platform.governance.audit_integrity`; audit itself imports neither storage nor signing).

A batch covers a contiguous run of its scope's event ``seq`` values: an event of the scope that is
not yet due (``ts`` at or after the period end) stops the batch before it, so a later event is never
batched ahead of an earlier one.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy import Engine, Text, func, select, text
from sqlalchemy.orm import Session

from nf_platform.audit import _canonical as cj
from nf_platform.config import AUDIT_BATCHER_DB_ROLE
from nf_platform.db import models

SCHEMA = "nf.audit-batch/v1"
TAG = "nf.audit-batch.v1"
KIND = "auditb"
PLATFORM_SCOPE = "_platform"  # events with no tenant (e.g. unparseable credentials)
BUCKET = "audit"
ID_RE = re.compile(r"^auditb:sha256:[0-9a-f]{64}$")
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


class AuditChainError(ValueError):
    """The chain is broken: a batch was modified, removed, reordered or does not match the expected
    head."""


class BatchStore(Protocol):
    """The subset of storage.objects.ObjectStore the batcher needs (audit must not import
    storage)."""

    def put(
        self, bucket: str, key: str, data: bytes, *, metadata: dict[str, str] | None = None
    ) -> None: ...
    def get(self, bucket: str, key: str) -> bytes: ...
    def list(self, bucket: str, prefix: str) -> Iterator[str]: ...


def ts(dt: datetime) -> str:
    dt = dt.astimezone(UTC)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def batch_payload(batch: dict[str, Any]) -> bytes:
    if batch.get("schema") != SCHEMA:
        raise AuditChainError(f"schema must be {SCHEMA}")
    seq, prev = batch.get("seq"), batch.get("prev")
    if not isinstance(seq, int) or isinstance(seq, bool) or seq < 0:
        raise AuditChainError("seq must be a non-negative integer")
    if (seq == 0) != (prev is None):
        raise AuditChainError("prev must be null exactly when seq == 0")
    if prev is not None and not ID_RE.match(prev):
        raise AuditChainError("prev must be an auditb id")
    if not TS_RE.match(str(batch.get("created_at", ""))):
        raise AuditChainError("created_at must be YYYY-MM-DDTHH:MM:SS.sssZ")
    try:
        return cj.canonicalize(batch)
    except cj.CanonicalError as e:
        raise AuditChainError(str(e)) from e


def batch_id(batch: dict[str, Any]) -> str:
    return f"{KIND}:sha256:" + cj.sha256_hex(cj.tagged_preimage(TAG, batch_payload(batch)))


@dataclass(frozen=True)
class BatchRow:
    """What the ``audit_batch`` table says about one batch (checked against the stored object)."""

    seq: int
    batch_id: str
    prev_id: str | None
    event_count: int
    first_event_seq: int | None
    last_event_seq: int | None


def _check_row(i: int, b: dict[str, Any], bid: str, row: BatchRow) -> None:
    events = b.get("events", [])
    first = events[0]["seq"] if events else None
    last = events[-1]["seq"] if events else None
    for name, want, got in (
        ("seq", i, row.seq),
        ("batch id", bid, row.batch_id),
        ("prev id", b.get("prev"), row.prev_id),
        ("event count", len(events), row.event_count),
        ("first event seq", first, row.first_event_seq),
        ("last event seq", last, row.last_event_seq),
    ):
        if want != got:
            raise AuditChainError(f"batch {i}: {name} of the audit_batch row differs")


def verify_chain(
    batches: list[dict[str, Any]],
    expected_head: str | None = None,
    *,
    scope: str | None = None,
    rows: list[BatchRow] | None = None,
) -> list[str]:
    """Recompute every batch ID in order and check the links. Returns the IDs.

    ``expected_head`` (the last batch ID from the database, an anchor or an earlier export) also
    catches a modified LAST batch, which has no successor whose ``prev`` would expose it.
    ``scope`` is the chain being verified: every batch must name it (a batch copied from another
    tenant's chain fails). ``rows`` (the scope's ``audit_batch`` rows in seq order) must match the
    objects one to one: seq, batch id, prev, event count and first/last event seq (AppSec M1).
    """
    ids: list[str] = []
    if scope is None:
        scope = batches[0].get("scope") if batches else None
    if rows is not None and len(rows) != len(batches):
        raise AuditChainError(f"{len(rows)} audit_batch rows but {len(batches)} stored batches")
    last_event_seq = 0
    for i, b in enumerate(batches):
        if b.get("seq") != i:
            raise AuditChainError(f"batch {i}: seq {b.get('seq')} != {i}")
        if b.get("scope") != scope:
            raise AuditChainError(f"batch {i}: scope {b.get('scope')!r} is not {scope!r}")
        if b.get("prev") != (ids[-1] if ids else None):
            raise AuditChainError(f"batch {i}: prev does not match the previous batch id")
        for ev in b.get("events", []):
            if not isinstance(ev.get("seq"), int) or ev["seq"] <= last_event_seq:
                raise AuditChainError(f"batch {i}: event seq not increasing")
            last_event_seq = ev["seq"]
        ids.append(batch_id(b))
        if rows is not None:
            _check_row(i, b, ids[-1], rows[i])
    if expected_head is not None and (not ids or ids[-1] != expected_head):
        raise AuditChainError("chain head does not match the expected head")
    return ids


def parse_batch(data: bytes) -> dict[str, Any]:
    try:
        obj = cj.parse(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        raise AuditChainError(f"batch is not valid JSON: {e}") from e
    if not isinstance(obj, dict):
        raise AuditChainError("batch is not a JSON object")
    return obj


def object_key(scope: str, seq: int) -> str:
    return f"chain/{scope}/{seq:012d}.json"


def load_chain(store: BatchStore, scope: str) -> list[dict[str, Any]]:
    keys = sorted(store.list(BUCKET, f"chain/{scope}/"))
    return [parse_batch(store.get(BUCKET, k)) for k in keys]


def verify_stored_chain(
    store: BatchStore,
    scope: str,
    expected_head: str | None = None,
    rows: list[BatchRow] | None = None,
) -> list[str]:
    """Verification tool for an exported/stored chain (SEC-105)."""
    return verify_chain(load_chain(store, scope), expected_head, scope=scope, rows=rows)


def _event_dict(e: models.AuditEvent) -> dict[str, Any]:
    return {
        "seq": e.seq,
        "id": str(e.id),
        "ts": ts(e.ts),
        "type": e.type,
        "action": e.action,
        "outcome": e.outcome,
        "actor": {"kind": e.actor_kind, "id": e.actor_id, "auth": e.auth_method},
        "resource": {"type": e.resource_type, "id": e.resource_id},
        "request_id": e.request_id,
        "details": e.details or {},
    }


@dataclass(frozen=True)
class _Head:
    seq: int
    batch_id: str
    period_end: datetime
    last_event_seq: int | None


@dataclass(frozen=True)
class BatchResult:
    scope: str
    seq: int
    batch_id: str
    event_count: int
    object_key: str


class AuditBatcher:
    def __init__(self, engine: Engine, store: BatchStore) -> None:
        self.engine = engine
        self.store = store

    @staticmethod
    def period_end(now: datetime) -> datetime:
        return now.astimezone(UTC).replace(minute=0, second=0, microsecond=0)

    def run(
        self, now: datetime | None = None, scopes: list[str] | None = None
    ) -> list[BatchResult]:
        """Write one batch per scope (every scope with events, or ``scopes``) that has unbatched
        events before the last full hour."""
        end = self.period_end(now or datetime.now(UTC))
        if scopes is None:
            with self._session() as s:
                scopes = list(
                    s.scalars(
                        select(SCOPE_COL)
                        .where(models.AuditEvent.ts < end)
                        .distinct()
                        .order_by(SCOPE_COL)
                    )
                )
        results: list[BatchResult] = []
        for scope in scopes:
            r = self._batch_scope(scope, end)
            if r is not None:
                results.append(r)
        return results

    def _session(self):
        return batcher_session(self.engine)

    def _batch_scope(self, scope: str, end: datetime) -> BatchResult | None:
        with self._session() as s:
            # one batcher per scope at a time: a concurrent run waits here, then sees the new head
            s.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"auditb:{scope}"})
            head = _head(s, scope)
            q = select(models.AuditEvent).where(scope_filter(scope))
            if head is not None and head.last_event_seq is not None:
                q = q.where(models.AuditEvent.seq > head.last_event_seq)
            # the scope's first event that is not due yet ends the batch (contiguous seq range)
            cutoff = s.scalar(
                q.with_only_columns(func.min(models.AuditEvent.seq)).where(
                    models.AuditEvent.ts >= end
                )
            )
            q = q.where(models.AuditEvent.ts < end)
            if cutoff is not None:
                q = q.where(models.AuditEvent.seq < cutoff)
            events = s.scalars(q.order_by(models.AuditEvent.seq)).all()
            if not events:
                return None
            seq = 0 if head is None else head.seq + 1
            start = head.period_end if head is not None else self._first_hour(events[0].ts)
            batch = {
                "schema": SCHEMA,
                "scope": scope,
                "seq": seq,
                "prev": None if head is None else head.batch_id,
                "created_at": ts(datetime.now(UTC)),
                "period": {"start": ts(start), "end": ts(end)},
                "events": [_event_dict(e) for e in events],
            }
            payload = batch_payload(batch)
            bid = batch_id(batch)
            key = object_key(scope, seq)
            s.add(
                models.AuditBatch(
                    tenant_scope=scope,
                    seq=seq,
                    batch_id=bid,
                    prev_id=batch["prev"],
                    period_start=start,
                    period_end=end,
                    first_event_seq=events[0].seq,
                    last_event_seq=events[-1].seq,
                    event_count=len(events),
                    object_key=key,
                )
            )
            s.flush()  # constraint errors (e.g. a concurrent batcher) before the object is written
            self.store.put(BUCKET, key, payload, metadata={"batch-id": bid})
        return BatchResult(scope, seq, bid, len(events), key)

    @staticmethod
    def _first_hour(first: datetime) -> datetime:
        return first.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


SCOPE_COL = func.coalesce(func.cast(models.AuditEvent.tenant_id, Text), PLATFORM_SCOPE)


def scope_filter(scope: str):
    if scope == PLATFORM_SCOPE:
        return models.AuditEvent.tenant_id.is_(None)
    return models.AuditEvent.tenant_id == uuid.UUID(scope)


@contextmanager
def batcher_session(engine: Engine) -> Iterator[Session]:
    """A transaction as ``nf_audit_batcher`` (AppSec M2): the only code path that assumes that role.
    It is deliberately not reachable through ``db.context.role_session`` (the request path).
    ``engine`` should be the batcher's own login (``governance.audit_integrity.batcher_engine``)."""
    with Session(engine) as s, s.begin():
        s.execute(text(f"SET LOCAL ROLE {AUDIT_BATCHER_DB_ROLE}"))
        yield s


def _head(s: Session, scope: str) -> _Head | None:
    b = s.scalar(
        select(models.AuditBatch)
        .where(models.AuditBatch.tenant_scope == scope)
        .order_by(models.AuditBatch.seq.desc())
        .limit(1)
    )
    return None if b is None else _Head(b.seq, b.batch_id, b.period_end, b.last_event_seq)


def chain_head(engine: Engine, scope: str) -> str | None:
    """Latest batch ID of a scope according to the database (verify it against an anchor)."""
    with batcher_session(engine) as s:
        h = _head(s, scope)
        return None if h is None else h.batch_id


def batch_rows(engine: Engine, scope: str) -> list[BatchRow]:
    """The scope's ``audit_batch`` rows in seq order."""
    with batcher_session(engine) as s:
        return [
            BatchRow(
                b.seq,
                b.batch_id,
                b.prev_id,
                b.event_count,
                b.first_event_seq,
                b.last_event_seq,
            )
            for b in s.scalars(
                select(models.AuditBatch)
                .where(models.AuditBatch.tenant_scope == scope)
                .order_by(models.AuditBatch.seq)
            )
        ]


def batched_scopes(engine: Engine) -> list[str]:
    with batcher_session(engine) as s:
        return list(s.scalars(select(models.AuditBatch.tenant_scope).distinct()))


def check_events(engine: Engine, scope: str, batches: list[dict[str, Any]]) -> list[str]:
    """Compare every stored batch with the events still in ``audit_event``: an event row deleted
    or rewritten after it was batched (e.g. with the append-only trigger switched off) shows up
    here. Returns the problems (empty when the table matches the chain)."""
    errors: list[str] = []
    with batcher_session(engine) as s:
        for b in batches:
            events = b.get("events") or []
            if not events:
                continue
            first, last = events[0].get("seq"), events[-1].get("seq")
            rows = s.scalars(
                select(models.AuditEvent)
                .where(
                    scope_filter(scope),
                    models.AuditEvent.seq >= first,
                    models.AuditEvent.seq <= last,
                )
                .order_by(models.AuditEvent.seq)
            ).all()
            db = {e.seq: _event_dict(e) for e in rows}
            stored = {e.get("seq"): e for e in events}
            missing = sorted(set(stored) - set(db))
            extra = sorted(set(db) - set(stored))
            changed = sorted(
                q
                for q in set(stored) & set(db)
                if cj.canonicalize(db[q]) != cj.canonicalize(stored[q])
            )
            n = b.get("seq")
            if missing:
                errors.append(f"batch {n}: event seq {missing[:5]} missing from audit_event")
            if extra:
                errors.append(f"batch {n}: event seq {extra[:5]} in audit_event, not batched")
            if changed:
                errors.append(f"batch {n}: event seq {changed[:5]} changed in audit_event")
    return errors
