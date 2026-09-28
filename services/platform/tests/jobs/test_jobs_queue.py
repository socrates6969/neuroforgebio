"""3.3: the Postgres queue itself -- SKIP LOCKED claims, leases + fencing, retries with backoff,
timeouts, cancellation, dedupe, and two-tenant isolation (RLS; the nf_worker role sees only
``job``)."""

from __future__ import annotations

import time
import uuid

import pytest
from nf_platform.db.context import tenant_session
from nf_platform.jobs import queue
from nf_platform.storage.runtime import service_principal
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

pytestmark = pytest.mark.postgres
KIND = "test.echo"


def _enqueue(engine, tenant: str, **kw) -> uuid.UUID:
    with tenant_session(service_principal(tenant), engine=engine) as s:
        return queue.enqueue(s, KIND, {"n": 1}, **kw)


def _claim(engine, lease_s: float = 30.0) -> queue.Job | None:
    with queue.worker_session(engine) as s:
        queue.reap(s)
        return queue.claim(s, "w-test", [KIND], lease_s=lease_s)


def _row(engine, job_id) -> dict:
    with engine.connect() as c:
        return dict(
            c.execute(text("SELECT * FROM job WHERE id = :i"), {"i": job_id}).first()._mapping
        )


def _age(engine, job_id, *, lease_s: float = 0, started_s: float = 0) -> None:
    """Move the lease/start into the past (instead of sleeping)."""
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE job SET lease_expires_at = lease_expires_at - make_interval(secs => :l), "
                "started_at = started_at - make_interval(secs => :s) WHERE id = :i"
            ),
            {"l": lease_s, "s": started_s, "i": job_id},
        )


def test_enqueue_claim_complete_and_dedupe(engine, tenants):
    a = _enqueue(engine, tenants.a, dedupe_key="k1")
    assert _enqueue(engine, tenants.a, dedupe_key="k1") == a  # idempotent
    job = _claim(engine)
    assert job.id == a and job.tenant_id == tenants.a and job.attempts == 1
    assert _claim(engine) is None
    with queue.worker_session(engine) as s:
        assert queue.heartbeat(s, job.id, job.lease_token) is queue.Beat.OK
        queue.complete(s, job.id, job.lease_token, {"ok": True})
    r = _row(engine, a)
    assert r["state"] == "succeeded" and r["result"] == {"ok": True} and r["lease_token"] is None


def test_skip_locked_concurrent_claims_never_share_a_job(engine, tenants):
    ids = {_enqueue(engine, tenants.a) for _ in range(2)}
    s1, s2 = Session(engine), Session(engine)
    try:
        s1.begin()
        s1.execute(text("SET LOCAL ROLE nf_worker"))
        j1 = queue.claim(s1, "w1", [KIND])  # row stays locked until s1 commits
        s2.begin()
        s2.execute(text("SET LOCAL ROLE nf_worker"))
        j2 = queue.claim(s2, "w2", [KIND])  # does not block: skips the locked row
        assert j1 and j2 and j1.id != j2.id and {j1.id, j2.id} == ids
        assert queue.claim(s2, "w2", [KIND]) is None  # j1 is locked by s1, j2 already taken
    finally:
        s1.rollback()
        s2.rollback()
        s1.close()
        s2.close()


def test_expired_lease_is_retried_and_the_old_worker_is_fenced_out(engine, tenants):
    a = _enqueue(engine, tenants.a, backoff_s=0)
    old = _claim(engine, lease_s=30)
    _age(engine, a, lease_s=60)  # the worker died: no heartbeat, lease in the past
    new = _claim(engine)
    assert new.id == a and new.attempts == 2 and new.lease_token != old.lease_token
    with queue.worker_session(engine) as s:
        assert queue.heartbeat(s, a, old.lease_token) is queue.Beat.LOST
        with pytest.raises(queue.LeaseLost):
            queue.complete(s, a, old.lease_token)
    with queue.worker_session(engine) as s, pytest.raises(queue.LeaseLost):
        queue.lock_lease(s, a, old.lease_token)
    assert "lease expired" in _row(engine, a)["last_error"]


def test_retries_with_exponential_backoff_then_failed(engine, tenants):
    a = _enqueue(engine, tenants.a, max_attempts=3, backoff_s=10)
    for attempt, wait_s in ((1, 10), (2, 20)):
        job = _claim(engine)
        assert job.attempts == attempt
        with queue.worker_session(engine) as s:
            assert queue.fail(s, a, job.lease_token, "boom") == "queued"
        r = _row(engine, a)
        delay = (r["run_after"] - r["heartbeat_at"]).total_seconds()
        assert wait_s - 1 < delay < wait_s + 5, delay  # backoff_s * 2**(attempts-1)
        assert _claim(engine) is None  # not due yet
        with engine.begin() as c:
            c.execute(text("UPDATE job SET run_after = now() WHERE id = :i"), {"i": a})
    job = _claim(engine)
    with queue.worker_session(engine) as s:
        assert queue.fail(s, a, job.lease_token, "boom") == "failed"
    r = _row(engine, a)
    assert r["state"] == "failed" and r["attempts"] == 3 and r["finished_at"] is not None


def test_non_retryable_failure_fails_at_once(engine, tenants):
    a = _enqueue(engine, tenants.a, max_attempts=5)
    job = _claim(engine)
    with queue.worker_session(engine) as s:
        assert queue.fail(s, a, job.lease_token, "bad params", retryable=False) == "failed"


def test_timeout_is_reported_to_the_worker_and_reaped(engine, tenants):
    a = _enqueue(engine, tenants.a, timeout_s=5, backoff_s=0, max_attempts=2)
    job = _claim(engine)
    _age(engine, a, started_s=10)  # ran past its timeout while still heartbeating
    with queue.worker_session(engine) as s:
        assert queue.heartbeat(s, a, job.lease_token) is queue.Beat.TIMED_OUT
    with queue.worker_session(engine) as s:
        settled = queue.reap(s)
    assert [(x.id, x.state) for x in settled] == [(a, "queued")]
    assert _row(engine, a)["last_error"] == "timed out"
    job2 = _claim(engine)
    _age(engine, a, started_s=10)
    with queue.worker_session(engine) as s:
        assert [x.state for x in queue.reap(s)] == ["failed"]  # attempts exhausted
    assert job2.attempts == 2


def test_cancel_queued_running_and_dead(engine, tenants):
    svc = service_principal(tenants.a)
    a = _enqueue(engine, tenants.a)
    with tenant_session(svc, engine=engine) as s:
        assert queue.cancel(s, a) == "cancelled"
    assert _claim(engine) is None

    b = _enqueue(engine, tenants.a)
    job = _claim(engine)
    with tenant_session(svc, engine=engine) as s:
        assert queue.cancel(s, b) == "running"  # the worker has to stop first
    with queue.worker_session(engine) as s:
        assert queue.heartbeat(s, b, job.lease_token) is queue.Beat.CANCELLED
        with pytest.raises(queue.JobCancelled):
            queue.lock_lease(s, b, job.lease_token)
    with queue.worker_session(engine) as s:
        queue.ack_cancel(s, b, job.lease_token)
    assert _row(engine, b)["state"] == "cancelled"

    c = _enqueue(engine, tenants.a)
    _claim(engine)
    with tenant_session(svc, engine=engine) as s:
        queue.cancel(s, c)
    _age(engine, c, lease_s=60)  # the worker died before it saw the cancel
    with queue.worker_session(engine) as s:
        assert [x.state for x in queue.reap(s)] == ["cancelled"]


def test_two_tenant_isolation_on_the_queue(engine, tenants):
    a = _enqueue(engine, tenants.a)
    b = _enqueue(engine, tenants.b)
    with tenant_session(service_principal(tenants.a), engine=engine) as s:
        seen = {r.id for r in s.execute(text("SELECT id FROM job"))}
        assert seen == {a}
        with pytest.raises(queue.QueueError, match="not found"):
            queue.cancel(s, b)  # RLS: B's job does not exist for A
    assert _row(engine, b)["state"] == "queued"
    # the claim role sees both tenants' jobs, each claimed job carries its own tenant ...
    got = {j.tenant_id for j in (_claim(engine), _claim(engine))}
    assert got == {tenants.a, tenants.b}
    # ... and it can read nothing but the job table
    for table in ("run", "run_artifact", "recording", "subject_key", "prov_node"):
        with queue.worker_session(engine) as s, pytest.raises(ProgrammingError):
            s.execute(text(f"SELECT count(*) FROM {table}"))


def test_heartbeat_extends_the_lease(engine, tenants):
    _enqueue(engine, tenants.a)
    job = _claim(engine, lease_s=2)
    before = _row(engine, job.id)["lease_expires_at"]
    time.sleep(0.05)
    with queue.worker_session(engine) as s:
        assert queue.heartbeat(s, job.id, job.lease_token, lease_s=30) is queue.Beat.OK
    assert (_row(engine, job.id)["lease_expires_at"] - before).total_seconds() > 20
