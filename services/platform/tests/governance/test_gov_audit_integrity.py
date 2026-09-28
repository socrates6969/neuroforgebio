"""AppSec M1 (SEC-105 operational): the audit hash chain is built and verified by queued jobs.

- ``audit.batch`` (hourly per tenant) batches the tenant's (and the ``_platform``) events into the
  WORM ``audit`` bucket and writes a signed head anchor per scope;
- ``audit.verify`` (daily per tenant) recomputes the stored chain against the database rows, the
  events still in ``audit_event`` and the latest signed anchor; a mismatch fails the job without
  retry and logs the ``audit_chain_mismatch`` alert (the consent/provenance pattern);
- ``verify_chain`` cross-checks each batch's scope, event count and first/last event seq;
- ``GET /v1/audit/batches/{seq}/object`` gives auditors the stored bytes to recompute themselves.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import UTC, datetime, timedelta

import pytest
from gov_helpers import principal
from nf_platform.audit import _canonical as cj
from nf_platform.audit import chain
from nf_platform.db.context import tenant_session
from nf_platform.governance import audit_integrity as ai
from nf_platform.governance import jobs as gjobs
from nf_platform.jobs import queue
from sqlalchemy import text

pytestmark = pytest.mark.postgres


def _backdate(engine, hours: int) -> None:
    """Move the fresh (not yet backdated, so not yet batched) events into the past (test only:
    the append-only trigger is off meanwhile)."""
    with engine.begin() as c:
        c.execute(text("ALTER TABLE audit_event DISABLE TRIGGER audit_event_append_only"))
        c.execute(
            text(
                "UPDATE audit_event SET ts = ts - make_interval(hours => :h) "
                "WHERE ts > now() - interval '30 minutes'"
            ),
            {"h": hours},
        )
        c.execute(text("ALTER TABLE audit_event ENABLE TRIGGER audit_event_append_only"))


def _enqueue(engine, tid: str, kind: str) -> None:
    with tenant_session(principal(tid, "owner"), engine=engine) as s:
        queue.enqueue(s, kind, {}, dedupe_key=gjobs.dedupe_key(kind, datetime.now(UTC)))


def _job(engine, job_id):
    with engine.connect() as c:
        return c.execute(
            text("SELECT state, last_error, result FROM job WHERE id = :i"), {"i": job_id}
        ).first()


def _two_batches(client, as_role, engine, storage, tid: str) -> None:
    """Two hourly batches for tenant A (plus anchors), written through the queued job."""
    for hours in (3, 1):
        client.get("/v1/whoami", headers=as_role("viewer"))
        _backdate(engine, hours)
        ai.batch_and_anchor(engine, storage.objects, [tid])


# ---------------------------------------------------------------- registration
def test_audit_job_kinds_are_registered_on_the_queue():
    from nf_runner import worker as w

    assert {gjobs.AUDIT_BATCH_KIND, gjobs.AUDIT_VERIFY_KIND} <= set(gjobs.KINDS)
    assert {gjobs.AUDIT_BATCH_KIND, gjobs.AUDIT_VERIFY_KIND} <= set(w.DEFAULT_KINDS)
    now = datetime(2026, 9, 26, 13, 5, tzinfo=UTC)
    assert gjobs.dedupe_key(gjobs.AUDIT_BATCH_KIND, now) == "2026-09-26T13"  # hourly
    assert gjobs.dedupe_key(gjobs.AUDIT_VERIFY_KIND, now) == "2026-09-26"  # daily


def test_batch_and_verify_jobs_run_end_to_end(client, as_role, engine, storage, tenants, worker):
    tid = tenants.a
    client.get("/v1/whoami", headers=as_role("viewer"))
    _backdate(engine, 2)
    _enqueue(engine, tid, gjobs.AUDIT_BATCH_KIND)
    worker.kinds = (gjobs.AUDIT_BATCH_KIND,)
    job = worker.run_once()
    row = _job(engine, job.id)
    assert row.state == "succeeded", row.last_error
    assert list(storage.objects.list("audit", f"chain/{tid}/")) == [chain.object_key(tid, 0)]
    head = chain.chain_head(engine, tid)
    anchor = ai.latest_anchor(storage.objects, tid)
    assert anchor is not None and anchor["head"] == head and anchor["seq"] == 0
    assert anchor["scope"] == tid and anchor["schema"] == ai.ANCHOR_SCHEMA
    _enqueue(engine, tid, gjobs.AUDIT_VERIFY_KIND)
    worker.kinds = (gjobs.AUDIT_VERIFY_KIND,)
    job = worker.run_once()
    row = _job(engine, job.id)
    assert row.state == "succeeded", row.last_error
    assert row.result["scopes"][tid] == {"ok": True, "batches": 1, "head": head}


# ---------------------------------------------------------------- tamper detection
@pytest.mark.parametrize("how", ["delete", "modify"])
def test_event_row_changed_after_batching_is_detected(
    client, as_role, engine, storage, tenants, worker, caplog, how
):
    tid = tenants.a
    _two_batches(client, as_role, engine, storage, tid)
    (ok,) = ai.verify_scopes(engine, storage.objects, [tid])
    assert ok.ok, ok.errors
    batch0 = chain.load_chain(storage.objects, tid)[0]
    victim = batch0["events"][0]["seq"]
    # a DB owner switches the trigger off and erases or rewrites the evidence (report M1)
    with engine.begin() as c:
        c.execute(text("ALTER TABLE audit_event DISABLE TRIGGER audit_event_append_only"))
        if how == "delete":
            c.execute(text("DELETE FROM audit_event WHERE seq = :s"), {"s": victim})
        else:
            c.execute(
                text("UPDATE audit_event SET outcome = 'denied' WHERE seq = :s"), {"s": victim}
            )
        c.execute(text("ALTER TABLE audit_event ENABLE TRIGGER audit_event_append_only"))
    # import-linter's CLI (tests/core/test_core_imports.py) calls logging.config.dictConfig, which
    # disables every logger that already exists in the test process: re-enable ours here
    was_disabled, ai.log.disabled = ai.log.disabled, False
    try:
        with caplog.at_level(logging.ERROR, logger=ai.log.name):
            (bad,) = ai.verify_scopes(engine, storage.objects, [tid])
    finally:
        ai.log.disabled = was_disabled
    assert not bad.ok and any("event" in e for e in bad.errors), bad.errors
    alerts = [r for r in caplog.records if getattr(r, "alert", None) == ai.ALERT]
    assert alerts and alerts[0].levelno == logging.ERROR
    # the queued form fails without retry and names the alert
    _enqueue(engine, tid, gjobs.AUDIT_VERIFY_KIND)
    worker.kinds = (gjobs.AUDIT_VERIFY_KIND,)
    job = worker.run_once()
    row = _job(engine, job.id)
    assert row.state == "failed" and ai.ALERT in row.last_error


def test_swapped_db_head_is_detected_by_the_signed_anchor(
    client, as_role, engine, storage, tenants
):
    """The database head is not trusted: the latest signed anchor in the WORM bucket is."""
    tid = tenants.a
    _two_batches(client, as_role, engine, storage, tid)
    assert ai.verify_scopes(engine, storage.objects, [tid])[0].ok
    # A DB owner removes the newest batch row (trigger off): the database now claims seq 0 is the
    # head. Stored objects are WORM; the stale object of seq 1 is also removed by a bucket admin
    # (governance-mode bypass), so rows and objects agree again. Only the anchor remembers seq 1.
    with engine.begin() as c:
        c.execute(text("ALTER TABLE audit_batch DISABLE TRIGGER audit_batch_append_only"))
        c.execute(text("DELETE FROM audit_batch WHERE tenant_scope = :t AND seq = 1"), {"t": tid})
        c.execute(text("ALTER TABLE audit_batch ENABLE TRIGGER audit_batch_append_only"))
    storage.objects._path("audit", chain.object_key(tid, 1)).unlink()
    (bad,) = ai.verify_scopes(engine, storage.objects, [tid])
    assert not bad.ok and any("anchor" in e for e in bad.errors), bad.errors


def test_forged_anchor_is_rejected(client, as_role, engine, storage, tenants):
    tid = tenants.a
    _two_batches(client, as_role, engine, storage, tid)
    doc = ai.latest_anchor(storage.objects, tid)
    forged = {**doc, "seq": 99, "head": "auditb:sha256:" + "0" * 64}
    storage.objects.put("audit", ai.anchor_key(tid, 99), cj.canonicalize(forged))
    (bad,) = ai.verify_scopes(engine, storage.objects, [tid])
    assert not bad.ok and any("not signed" in e for e in bad.errors), bad.errors


# ---------------------------------------------------------------- verify_chain cross-checks
def test_verify_chain_checks_scope_and_batch_rows(client, as_role, engine, storage, tenants):
    tid = tenants.a
    _two_batches(client, as_role, engine, storage, tid)
    batches = chain.load_chain(storage.objects, tid)
    rows = chain.batch_rows(engine, tid)
    assert len(chain.verify_chain(batches, scope=tid, rows=rows)) == 2
    with pytest.raises(chain.AuditChainError, match="scope"):
        chain.verify_chain(batches, scope=tenants.b)
    # a row whose event count / first / last seq differ from the stored batch
    for field_, delta in (("event_count", 1), ("first_event_seq", -1), ("last_event_seq", 1)):
        bad = [r.__class__(**{**r.__dict__}) for r in rows]
        bad[0] = chain.BatchRow(**{**rows[0].__dict__, field_: getattr(rows[0], field_) + delta})
        with pytest.raises(chain.AuditChainError, match=field_.replace("_", " ")):
            chain.verify_chain(batches, scope=tid, rows=bad)
    with pytest.raises(chain.AuditChainError, match="rows"):
        chain.verify_chain(batches, scope=tid, rows=rows[:1])


# ---------------------------------------------------------------- auditor download
def test_auditor_downloads_a_batch_and_recomputes_it(client, as_role, engine, storage, tenants):
    tid = tenants.a
    _two_batches(client, as_role, engine, storage, tid)
    h = as_role("auditor")
    listed = client.get("/v1/audit/batches", headers=h).json()
    assert [b["seq"] for b in listed] == [0, 1]
    got = []
    for b in listed:
        r = client.get(f"/v1/audit/batches/{b['seq']}/object", headers=h)
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith("application/json")
        assert r.headers["x-nf-batch-id"] == b["batch_id"]
        # independent recomputation: parse the bytes, re-hash with the spec tag, follow the links
        doc = json.loads(r.content)
        assert r.content == cj.canonicalize(doc)
        assert chain.batch_id(doc) == b["batch_id"]
        got.append(doc)
    assert chain.verify_chain(got, expected_head=listed[-1]["batch_id"], scope=tid)
    # audited as an export
    with engine.connect() as c:
        evs = c.execute(
            text("SELECT type, resource_type FROM audit_event WHERE request_id = :r"),
            {"r": r.headers["x-request-id"]},
        ).all()
    assert ("data.export", "audit_batch_object") in {tuple(e) for e in evs}
    # tenant isolation: tenant B has no batch 0 of its own and never sees tenant A's
    hb = as_role("auditor", tenant=tenants.b)
    assert client.get("/v1/audit/batches/0/object", headers=hb).status_code == 404
    assert client.get("/v1/audit/batches/7/object", headers=h).status_code == 404
    # non-auditor roles are refused
    assert client.get("/v1/audit/batches/0/object", headers=as_role("viewer")).status_code == 403


# ---------------------------------------------------------------- batch boundaries (M1)
def _scope_seqs(engine, tid: str) -> list[int]:
    with engine.connect() as c:
        return list(
            c.execute(
                text("SELECT seq FROM audit_event WHERE tenant_id = :t ORDER BY seq"), {"t": tid}
            ).scalars()
        )


def test_event_not_yet_due_between_due_events_ends_the_batch(
    client, as_role, engine, storage, tenants
):
    """seq order: due events, then one NOT due (ts after the period end), then due events again.
    The batch stops before the not-due event (contiguous seq range); the next run batches it and
    the later due events: nothing skipped, nothing twice."""
    tid = tenants.a
    for _ in range(3):
        client.get("/v1/whoami", headers=as_role("viewer"))
    seqs = _scope_seqs(engine, tid)
    assert len(seqs) >= 3, seqs
    held = seqs[len(seqs) // 2]  # neither the first nor the last of the scope's events
    now = datetime.now(UTC)
    with engine.begin() as c:
        c.execute(text("ALTER TABLE audit_event DISABLE TRIGGER audit_event_append_only"))
        c.execute(
            text(
                "UPDATE audit_event SET ts = CASE WHEN seq = :held THEN :late ELSE :early END "
                "WHERE tenant_id = :t"
            ),
            {"held": held, "late": now, "early": now - timedelta(hours=3), "t": tid},
        )
        c.execute(text("ALTER TABLE audit_event ENABLE TRIGGER audit_event_append_only"))
    batcher = chain.AuditBatcher(engine, storage.objects)
    end = chain.AuditBatcher.period_end(now)
    assert now >= end  # the held event is not due in this run
    (r0,) = batcher.run(now, scopes=[tid])
    (b0,) = chain.load_chain(storage.objects, tid)
    assert [e["seq"] for e in b0["events"]] == [q for q in seqs if q < held]
    assert r0.event_count == len(b0["events"])
    # a later run (the held event is due now) continues exactly at the held event
    (r1,) = batcher.run(now + timedelta(hours=2), scopes=[tid])
    b0, b1 = chain.load_chain(storage.objects, tid)
    assert [e["seq"] for e in b1["events"]] == [q for q in seqs if q >= held]
    batched = [e["seq"] for b in (b0, b1) for e in b["events"]]
    assert batched == seqs  # every event once, in seq order
    rows = chain.batch_rows(engine, tid)
    assert chain.verify_chain([b0, b1], expected_head=r1.batch_id, scope=tid, rows=rows)
    assert chain.check_events(engine, tid, [b0, b1]) == []


def test_concurrent_batcher_runs_on_one_scope_write_one_batch(
    client, as_role, engine, storage, tenants
):
    """Two AuditBatcher.run() calls race on the same scope. The per-scope advisory lock serializes
    them: the second sees the first one's head and finds nothing left (one batch, no error)."""
    tid = tenants.a
    client.get("/v1/whoami", headers=as_role("viewer"))
    _backdate(engine, 2)
    now = datetime.now(UTC)
    results: dict[int, object] = {}

    def run(i: int) -> None:
        try:
            results[i] = chain.AuditBatcher(engine, storage.objects).run(now, scopes=[tid])
        except Exception as e:  # reported below
            results[i] = e

    # hold the scope's lock so both runs are queued on it before either can batch
    with engine.connect() as holder:
        tx = holder.begin()
        holder.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"auditb:{tid}"})
        threads = [threading.Thread(target=run, args=(i,)) for i in (0, 1)]
        for t in threads:
            t.start()
        deadline = time.monotonic() + 30
        waiting = 0
        while waiting < 2 and time.monotonic() < deadline:
            waiting = holder.execute(
                text("SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND NOT granted")
            ).scalar()
            time.sleep(0.02)
        assert waiting == 2, "both runs should be waiting on the scope lock"
        tx.commit()  # release: the runs go one after the other
    for t in threads:
        t.join(timeout=60)
        assert not t.is_alive()
    outcomes = [results[0], results[1]]
    assert not [o for o in outcomes if isinstance(o, Exception)], outcomes
    assert sorted(len(o) for o in outcomes) == [0, 1]
    assert list(storage.objects.list("audit", f"chain/{tid}/")) == [chain.object_key(tid, 0)]
    rows = chain.batch_rows(engine, tid)
    assert [r.seq for r in rows] == [0]
    assert chain.verify_stored_chain(storage.objects, tid, rows[0].batch_id, rows=rows)
