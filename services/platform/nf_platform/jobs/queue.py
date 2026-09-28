"""Postgres job queue (BUILD-GUIDE 3.3; BLUEPRINT §3.5 orchestration; migration 0004).

- :func:`enqueue` runs in the caller's tenant session (RLS); ``dedupe_key`` makes it idempotent.
- :func:`reap` and :func:`claim` run in a :func:`worker_session` (role ``nf_worker``, which sees
  ``job`` rows of every tenant and nothing else). ``reap`` settles attempts whose lease expired
  (worker died) or whose wall-clock timeout passed; ``claim`` takes the next due job with
  ``SELECT ... FOR UPDATE SKIP LOCKED``, so concurrent workers never claim the same job and never
  block on each other.
- Every claim creates a new ``lease_token`` (fencing token). :func:`heartbeat`, :func:`complete`,
  :func:`fail`, :func:`ack_cancel` and :func:`lock_lease` only act when the caller still holds that
  token, so a worker that was presumed dead (lease expired, job re-claimed) cannot finish, stage or
  publish anything afterwards.
- Retries: a failed or expired attempt is re-queued with exponential backoff
  (``backoff_s * 2**(attempts-1)``) until ``max_attempts``; then the job is ``failed``.
- Cancellation: a queued job is cancelled at once; a running job gets ``cancel_requested`` and its
  worker sees it on the next heartbeat (or the reaper cancels it when the lease expires).

All times are the database's ``now()`` (one clock for every worker).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import Engine, bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Session
from sqlalchemy.types import Text

from nf_platform.db.context import get_engine

WORKER_DB_ROLE = "nf_worker"
DEFAULT_LEASE_S = 30.0
DEFAULT_TIMEOUT_S = 3600
MAX_ERROR_LEN = 1000
TERMINAL = frozenset({"succeeded", "failed", "cancelled"})


class QueueError(RuntimeError):
    pass


class LeaseLost(QueueError):
    """The caller no longer holds the job's lease (expired and re-claimed, cancelled, finished)."""


class JobCancelled(QueueError):
    """A cancel was requested while the caller holds the lease: stop and :func:`ack_cancel`."""


class Beat(StrEnum):
    OK = "ok"
    CANCELLED = "cancelled"  # cancel requested: stop, then ack_cancel
    TIMED_OUT = "timed_out"  # wall-clock timeout passed: stop, then fail
    LOST = "lost"  # lease gone: stop, touch nothing


@dataclass(frozen=True)
class Job:
    id: uuid.UUID
    tenant_id: str
    kind: str
    payload: dict[str, Any]
    attempts: int
    max_attempts: int
    timeout_s: int
    lease_token: uuid.UUID
    lease_expires_at: datetime
    worker_id: str
    started_at: datetime


def _tenant(session: Session) -> uuid.UUID:
    tid = session.info.get("tenant_id")
    if tid is None:
        raise QueueError("enqueue needs a tenant session")
    return tid


def enqueue(
    session: Session,
    kind: str,
    payload: dict[str, Any],
    *,
    max_attempts: int = 3,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    backoff_s: float = 5.0,
    priority: int = 0,
    dedupe_key: str | None = None,
    delay_s: float = 0.0,
    created_by: str = "system",
) -> uuid.UUID:
    """Queue a job in the session's tenant. With ``dedupe_key`` a second enqueue of the same
    (kind, key) returns the existing job's id instead of queuing twice."""
    tid = _tenant(session)
    row = session.execute(
        text(
            "INSERT INTO job (id, tenant_id, kind, payload, max_attempts, timeout_s, backoff_s, "
            "priority, dedupe_key, run_after, created_by) VALUES (:id, :t, :kind, :payload, :ma, "
            ":to, :bo, :prio, :dk, now() + make_interval(secs => :delay), :by) "
            "ON CONFLICT (tenant_id, kind, dedupe_key) DO NOTHING RETURNING id"
        ).bindparams(bindparam("payload", type_=JSONB)),
        {
            "id": uuid.uuid4(),
            "t": tid,
            "kind": kind,
            "payload": payload,
            "ma": max_attempts,
            "to": timeout_s,
            "bo": backoff_s,
            "prio": priority,
            "dk": dedupe_key,
            "delay": float(delay_s),
            "by": created_by,
        },
    ).first()
    if row is not None:
        return row.id
    return session.execute(
        text("SELECT id FROM job WHERE tenant_id = :t AND kind = :k AND dedupe_key = :dk"),
        {"t": tid, "k": kind, "dk": dedupe_key},
    ).scalar_one()


@contextmanager
def worker_session(engine: Engine | None = None) -> Iterator[Session]:
    """One transaction as ``nf_worker`` (cross-tenant, ``job`` table only). Commits on success."""
    with Session(engine or get_engine()) as s, s.begin():
        s.execute(text(f"SET LOCAL ROLE {WORKER_DB_ROLE}"))
        yield s


_BACKOFF = "make_interval(secs => backoff_s * power(2, greatest(attempts - 1, 0)))"
_EXPIRED = (
    "state = 'running' AND (lease_expires_at < now() "
    "OR started_at + make_interval(secs => timeout_s) < now())"
)


@dataclass(frozen=True)
class Settled:
    id: uuid.UUID
    tenant_id: str
    kind: str
    payload: dict[str, Any]
    state: str


def reap(session: Session) -> list[Settled]:
    """Settle attempts whose lease expired (worker died) or that ran past their timeout: cancel if
    requested, fail if attempts are exhausted, otherwise re-queue with backoff. Returns them, so the
    caller can align dependent rows (e.g. a run whose job ended ``failed``)."""
    rows = session.execute(
        text(
            "UPDATE job SET "
            "state = CASE WHEN cancel_requested THEN 'cancelled' "
            "  WHEN attempts >= max_attempts THEN 'failed' ELSE 'queued' END, "
            "run_after = CASE WHEN cancel_requested OR attempts >= max_attempts THEN run_after "
            f"  ELSE now() + {_BACKOFF} END, "
            "finished_at = CASE WHEN cancel_requested OR attempts >= max_attempts THEN now() "
            "  ELSE NULL END, "
            "last_error = CASE WHEN lease_expires_at < now() "
            "  THEN 'lease expired (worker lost)' ELSE 'timed out' END, "
            "lease_token = NULL, lease_expires_at = NULL, worker_id = NULL "
            f"WHERE id IN (SELECT id FROM job WHERE {_EXPIRED} FOR UPDATE SKIP LOCKED) "
            "RETURNING id, tenant_id, kind, payload, state"
        )
    ).all()
    return [Settled(r.id, str(r.tenant_id), r.kind, dict(r.payload or {}), r.state) for r in rows]


def claim(
    session: Session,
    worker_id: str,
    kinds: Sequence[str],
    *,
    lease_s: float = DEFAULT_LEASE_S,
) -> Job | None:
    """Claim the next due job of ``kinds`` (worker session). ``None`` when nothing is due. Call
    :func:`reap` first (the worker loop does) so dead attempts become claimable again."""
    row = session.execute(
        text(
            "WITH c AS (SELECT id FROM job WHERE state = 'queued' AND run_after <= now() "
            "AND kind = ANY(:kinds) ORDER BY priority DESC, run_after, created_at "
            "FOR UPDATE SKIP LOCKED LIMIT 1) "
            "UPDATE job j SET state = 'running', attempts = j.attempts + 1, lease_token = :tok, "
            "lease_expires_at = now() + make_interval(secs => :lease), heartbeat_at = now(), "
            "worker_id = :w, started_at = now() "
            "FROM c WHERE j.id = c.id RETURNING j.id, j.tenant_id, j.kind, j.payload, "
            "j.attempts, j.max_attempts, j.timeout_s, j.lease_token, j.lease_expires_at, "
            "j.worker_id, j.started_at"
        ).bindparams(bindparam("kinds", type_=ARRAY(Text))),
        {"kinds": list(kinds), "tok": uuid.uuid4(), "lease": float(lease_s), "w": worker_id},
    ).first()
    if row is None:
        return None
    return Job(
        id=row.id,
        tenant_id=str(row.tenant_id),
        kind=row.kind,
        payload=dict(row.payload or {}),
        attempts=row.attempts,
        max_attempts=row.max_attempts,
        timeout_s=row.timeout_s,
        lease_token=row.lease_token,
        lease_expires_at=row.lease_expires_at,
        worker_id=row.worker_id,
        started_at=row.started_at,
    )


def heartbeat(
    session: Session, job_id: uuid.UUID, token: uuid.UUID, *, lease_s: float = DEFAULT_LEASE_S
) -> Beat:
    """Extend the lease while the attempt is healthy; tell the worker to stop otherwise."""
    ok = session.execute(
        text(
            "UPDATE job SET lease_expires_at = now() + make_interval(secs => :lease), "
            "heartbeat_at = now() WHERE id = :id AND lease_token = :tok AND state = 'running' "
            "AND NOT cancel_requested AND lease_expires_at >= now() "
            "AND started_at + make_interval(secs => timeout_s) >= now() RETURNING id"
        ),
        {"id": job_id, "tok": token, "lease": float(lease_s)},
    ).first()
    if ok is not None:
        return Beat.OK
    row = session.execute(
        text(
            "SELECT state, lease_token, cancel_requested, lease_expires_at < now() AS expired, "
            "started_at + make_interval(secs => timeout_s) < now() AS timed_out "
            "FROM job WHERE id = :id"
        ),
        {"id": job_id},
    ).first()
    if row is None or row.state != "running" or row.lease_token != token or row.expired:
        return Beat.LOST
    if row.cancel_requested:
        return Beat.CANCELLED
    return Beat.TIMED_OUT if row.timed_out else Beat.LOST


def lock_lease(session: Session, job_id: uuid.UUID, token: uuid.UUID) -> None:
    """Row-lock the job for the rest of the transaction iff the caller holds a live lease and no
    cancel is pending; raise :class:`JobCancelled` / :class:`LeaseLost` otherwise. Finishing a run
    calls this first, in the same transaction that publishes the outputs (fencing)."""
    row = session.execute(
        text(
            "SELECT cancel_requested FROM job WHERE id = :id AND lease_token = :tok "
            "AND state = 'running' AND lease_expires_at >= now() FOR UPDATE"
        ),
        {"id": job_id, "tok": token},
    ).first()
    if row is None:
        raise LeaseLost(f"job {job_id}: lease lost")
    if row.cancel_requested:
        raise JobCancelled(f"job {job_id}: cancel requested")


def _finish(
    session: Session,
    job_id: uuid.UUID,
    token: uuid.UUID,
    sql_set: str,
    params: dict[str, Any],
    *,
    json_params: tuple[str, ...] = (),
) -> str:
    stmt = text(
        f"UPDATE job SET {sql_set}, lease_token = NULL, lease_expires_at = NULL, "
        "worker_id = NULL WHERE id = :id AND lease_token = :tok AND state = 'running' "
        "RETURNING state"
    )
    if json_params:
        stmt = stmt.bindparams(*(bindparam(n, type_=JSONB) for n in json_params))
    row = session.execute(stmt, {"id": job_id, "tok": token, **params}).first()
    if row is None:
        raise LeaseLost(f"job {job_id}: lease lost")
    return row.state


def complete(
    session: Session, job_id: uuid.UUID, token: uuid.UUID, result: dict[str, Any] | None = None
) -> None:
    _finish(
        session,
        job_id,
        token,
        "state = 'succeeded', finished_at = now(), result = :result, last_error = NULL",
        {"result": result},
        json_params=("result",),
    )


def fail(
    session: Session,
    job_id: uuid.UUID,
    token: uuid.UUID,
    error: str,
    *,
    retryable: bool = True,
) -> str:
    """End the attempt with ``error``. Re-queued with backoff while attempts remain (and the error
    is retryable), else ``failed``. Returns the new state."""
    return _finish(
        session,
        job_id,
        token,
        "state = CASE WHEN :retry AND attempts < max_attempts AND NOT cancel_requested "
        "THEN 'queued' WHEN cancel_requested THEN 'cancelled' ELSE 'failed' END, "
        "run_after = CASE WHEN :retry AND attempts < max_attempts "
        f"THEN now() + {_BACKOFF} ELSE run_after END, "
        "finished_at = CASE WHEN :retry AND attempts < max_attempts AND NOT cancel_requested "
        "THEN NULL ELSE now() END, last_error = :err",
        {"retry": bool(retryable), "err": str(error)[:MAX_ERROR_LEN]},
    )


def ack_cancel(session: Session, job_id: uuid.UUID, token: uuid.UUID) -> None:
    """The worker stopped after a cancel request."""
    _finish(
        session,
        job_id,
        token,
        "state = 'cancelled', finished_at = now(), last_error = 'cancelled'",
        {},
    )


def cancel(session: Session, job_id: uuid.UUID) -> str:
    """Cancel (tenant session; RLS scopes it). Queued → ``cancelled`` now; running →
    ``cancel_requested`` (state stays ``running`` until the worker stops or its lease expires);
    finished jobs are left as they are. Returns the job's state afterwards."""
    row = session.execute(
        text(
            "UPDATE job SET "
            "state = CASE WHEN state = 'queued' THEN 'cancelled' ELSE state END, "
            "finished_at = CASE WHEN state = 'queued' THEN now() ELSE finished_at END, "
            "cancel_requested = true "
            "WHERE id = :id AND state IN ('queued', 'running') RETURNING state"
        ),
        {"id": job_id},
    ).first()
    if row is not None:
        return row.state
    state = session.execute(text("SELECT state FROM job WHERE id = :id"), {"id": job_id}).first()
    if state is None:
        raise QueueError(f"job {job_id} not found")
    return state.state


def state_of(session: Session, job_id: uuid.UUID) -> dict[str, Any] | None:
    row = session.execute(
        text(
            "SELECT id, kind, state, attempts, max_attempts, cancel_requested, last_error, "
            "run_after, started_at, finished_at FROM job WHERE id = :id"
        ),
        {"id": job_id},
    ).first()
    return None if row is None else dict(row._mapping)
