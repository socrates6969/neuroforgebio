"""AppSec M2: the insert-only audit role could forge the chain head and stop all batching.

- the role is split: ``nf_audit_writer`` (INSERT on ``audit_event`` only; the API/worker event
  sink) and ``nf_audit_batcher`` (INSERT on ``audit_batch``; only the batcher job's session);
- a BEFORE INSERT trigger on ``audit_batch`` makes every new row continue its scope's chain
  (seq = max + 1, prev_id = the previous batch id, first_event_seq after the previous
  last_event_seq, last_event_seq not beyond the scope's newest event, event_count = the scope's
  events in the range);
- the ``audit_event`` INSERT policy/trigger reject rows that name an unknown tenant, an unknown
  outcome or actor kind, a back-dated ``ts`` or a hand-picked ``seq``;
- the API's session helper cannot assume the batcher role.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from nf_platform import config
from nf_platform.audit import chain
from nf_platform.audit import log as audit
from nf_platform.db import migrate
from nf_platform.db.context import role_session
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

pytestmark = pytest.mark.postgres

WRITER, BATCHER = "nf_audit_writer", "nf_audit_batcher"


class MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def put(self, bucket, key, data, *, metadata=None) -> None:
        if (bucket, key) in self.objects:
            raise PermissionError("WORM: object exists")
        self.objects[(bucket, key)] = data

    def get(self, bucket, key) -> bytes:
        return self.objects[(bucket, key)]

    def list(self, bucket, prefix):
        return iter(sorted(k for b, k in self.objects if b == bucket and k.startswith(prefix)))


def _backdate(engine, hours: int) -> None:
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


def _one_batch(client, as_role, engine, tenants) -> MemoryStore:
    store = MemoryStore()
    client.get("/v1/whoami", headers=as_role("viewer"))
    _backdate(engine, 2)
    assert chain.AuditBatcher(engine, store).run(scopes=[tenants.a])
    return store


def _head_row(engine, tid: str):
    with engine.connect() as c:
        return c.execute(
            text(
                "SELECT seq, batch_id, last_event_seq FROM audit_batch WHERE tenant_scope = :t "
                "ORDER BY seq DESC LIMIT 1"
            ),
            {"t": tid},
        ).first()


def _insert_batch(engine, role: str | None, **row) -> None:
    now = datetime.now(UTC)
    row = {
        "period_start": now - timedelta(hours=1),
        "period_end": now,
        "object_key": f"chain/{row['tenant_scope']}/{row['seq']:012d}.json",
        **row,
    }
    cols = ", ".join(row)
    vals = ", ".join(f":{k}" for k in row)
    with engine.begin() as c:
        if role:
            c.execute(text(f"SET LOCAL ROLE {role}"))
        c.execute(text(f"INSERT INTO audit_batch ({cols}) VALUES ({vals})"), row)


def _junk_id() -> str:
    return "auditb:sha256:" + uuid.uuid4().hex * 2


# ---------------------------------------------------------------- continuity trigger
@pytest.mark.parametrize("role", [None, BATCHER])  # the superuser/owner too: triggers bind everyone
def test_forged_head_from_the_report_is_rejected(client, as_role, engine, tenants, role):
    _one_batch(client, as_role, engine, tenants)
    head = _head_row(engine, tenants.a)
    with pytest.raises(DBAPIError, match="audit chain continuity"):
        _insert_batch(
            engine,
            role,
            tenant_scope=tenants.a,
            seq=head.seq + 1,
            batch_id=_junk_id(),
            prev_id=head.batch_id,
            first_event_seq=head.last_event_seq + 1,
            last_event_seq=9 * 10**18,
            event_count=1,
        )
    assert _head_row(engine, tenants.a) == head


def test_non_continuing_rows_are_rejected(client, as_role, engine, tenants):
    _one_batch(client, as_role, engine, tenants)
    head = _head_row(engine, tenants.a)
    client.get("/v1/whoami", headers=as_role("viewer"))  # one new, unbatched event
    with engine.connect() as c:
        newest = c.execute(
            text("SELECT max(seq) FROM audit_event WHERE tenant_id = :t"), {"t": tenants.a}
        ).scalar()
    good = {
        "tenant_scope": tenants.a,
        "seq": head.seq + 1,
        "batch_id": _junk_id(),
        "prev_id": head.batch_id,
        "first_event_seq": newest,
        "last_event_seq": newest,
        "event_count": 1,
    }
    bad = {
        "prev_id": {"prev_id": _junk_id()},
        "prev_null": {"prev_id": None},
        "seq_gap": {"seq": head.seq + 2},
        "seq_replay": {"seq": head.seq},
        "overlap": {"first_event_seq": head.last_event_seq},
        "count": {"event_count": 2},
        "reversed": {"first_event_seq": newest, "last_event_seq": newest - 1},
    }
    for name, change in bad.items():
        with pytest.raises(DBAPIError, match="audit chain continuity"):
            _insert_batch(engine, BATCHER, **{**good, **change})
        assert _head_row(engine, tenants.a) == head, name
    # a fresh scope must start at seq 0 without prev
    with pytest.raises(DBAPIError, match="audit chain continuity"):
        _insert_batch(engine, BATCHER, **{**good, "tenant_scope": tenants.b, "seq": 1})


def test_batching_continues_normally_after_rejected_forgeries(client, as_role, engine, tenants):
    store = _one_batch(client, as_role, engine, tenants)
    head = _head_row(engine, tenants.a)
    with pytest.raises(DBAPIError, match="audit chain continuity"):
        _insert_batch(
            engine,
            BATCHER,
            tenant_scope=tenants.a,
            seq=head.seq + 1,
            batch_id=_junk_id(),
            prev_id=head.batch_id,
            first_event_seq=head.last_event_seq + 1,
            last_event_seq=9 * 10**18,
            event_count=1,
        )
    client.get("/v1/whoami", headers=as_role("viewer"))
    _backdate(engine, 1)
    (r,) = chain.AuditBatcher(engine, store).run(scopes=[tenants.a])
    assert r.seq == head.seq + 1
    rows = chain.batch_rows(engine, tenants.a)
    assert chain.verify_stored_chain(store, tenants.a, rows[-1].batch_id, rows=rows)


# ---------------------------------------------------------------- role split
def test_roles_are_split_and_least_privilege(engine, tenants):
    assert config.AUDIT_WRITER_DB_ROLE == WRITER
    assert config.AUDIT_BATCHER_DB_ROLE == BATCHER
    # the writer cannot insert (or read) batches
    with pytest.raises(DBAPIError) as e:
        _insert_batch(
            engine,
            WRITER,
            tenant_scope=tenants.a,
            seq=0,
            batch_id=_junk_id(),
            prev_id=None,
            first_event_seq=1,
            last_event_seq=1,
            event_count=1,
        )
    assert e.value.orig.sqlstate == "42501"  # insufficient_privilege
    # the batcher cannot write events
    with pytest.raises(DBAPIError) as e, engine.begin() as c:
        c.execute(text(f"SET LOCAL ROLE {BATCHER}"))
        c.execute(
            text("INSERT INTO audit_event (id, type, outcome) VALUES (:i, 'x', 'success')"),
            {"i": str(uuid.uuid4())},
        )
    assert e.value.orig.sqlstate == "42501"
    # the old combined role keeps no audit privilege
    with engine.connect() as c:
        privs = c.execute(
            text(
                "SELECT table_name, privilege_type FROM information_schema.role_table_grants "
                "WHERE grantee = 'nf_audit' AND table_name IN ('audit_event', 'audit_batch')"
            )
        ).all()
    assert privs == []


def test_api_session_path_cannot_assume_the_batcher_role(engine):
    """The request-path helper refuses the batcher role; only the batcher's own session uses it
    (deployment: a separate DB login that is the only member of nf_audit_batcher)."""
    with (
        pytest.raises(ValueError, match="unknown database role"),
        role_session(BATCHER, engine=engine),
    ):
        pass
    with role_session(WRITER, engine=engine) as s:
        assert s.execute(text("SELECT current_user")).scalar() == WRITER
    with chain.batcher_session(engine) as s:
        assert s.execute(text("SELECT current_user")).scalar() == BATCHER
    # the event sink writes as the writer role
    sink = audit.PostgresAuditSink(engine)
    sink.write(audit.AuditEvent(type="t.x", outcome="success"))


# ---------------------------------------------------------------- audit_event insert checks
@pytest.mark.parametrize(
    "case",
    ["unknown_tenant", "outcome", "actor_kind", "backdated", "forward_dated", "picked_seq"],
)
def test_audit_event_insert_sanity(engine, tenants, case):
    ev = {"id": str(uuid.uuid4()), "tenant_id": tenants.a, "type": "t.x", "outcome": "success"}
    extra = ""
    if case == "unknown_tenant":
        ev["tenant_id"] = str(uuid.uuid4())
    elif case == "outcome":
        ev["outcome"] = "ok"
    elif case == "actor_kind":
        ev["actor_kind"] = "root"
    elif case == "backdated":
        ev["ts"] = datetime.now(UTC) - timedelta(days=3)
    elif case == "forward_dated":
        ev["ts"] = datetime.now(UTC) + timedelta(days=3)
    else:
        ev["seq"] = 9 * 10**18
        extra = " OVERRIDING SYSTEM VALUE"
    cols = ", ".join(ev)
    vals = ", ".join(f":{k}" for k in ev)
    with pytest.raises(DBAPIError), engine.begin() as c:
        c.execute(text(f"SET LOCAL ROLE {WRITER}"))
        c.execute(text(f"INSERT INTO audit_event ({cols}){extra} VALUES ({vals})"), ev)
    # a sane row passes
    ok = {"id": str(uuid.uuid4()), "tenant_id": tenants.a, "type": "t.x", "outcome": "denied"}
    with engine.begin() as c:
        c.execute(text(f"SET LOCAL ROLE {WRITER}"))
        c.execute(
            text(
                "INSERT INTO audit_event (id, tenant_id, type, outcome, actor_kind) "
                "VALUES (:id, :tenant_id, :type, :outcome, 'service')"
            ),
            ok,
        )


# ---------------------------------------------------------------- migration
def test_migration_up_down_up(pg_url):
    from nf_platform.db import testing

    name = f"nf_m_{uuid.uuid4().hex[:10]}"
    url = testing.create_database(pg_url, name)
    try:
        migrate.upgrade(url)
        migrate.downgrade(url, "0014m6_key_shred_freeze")
        eng = create_engine(url)
        with eng.connect() as c:
            trig = c.execute(
                text("SELECT count(*) FROM pg_trigger WHERE tgname = 'audit_batch_continuity'")
            ).scalar()
            privs = c.execute(
                text(
                    "SELECT count(*) FROM information_schema.role_table_grants "
                    "WHERE grantee = 'nf_audit' AND table_name = 'audit_batch' "
                    "AND privilege_type = 'INSERT'"
                )
            ).scalar()
        eng.dispose()
        assert trig == 0 and privs == 1  # back to the 0001 grants
        migrate.upgrade(url)
        eng = create_engine(url)
        with eng.connect() as c:
            trig = c.execute(
                text("SELECT count(*) FROM pg_trigger WHERE tgname = 'audit_batch_continuity'")
            ).scalar()
        eng.dispose()
        assert trig == 1
    finally:
        testing.drop_database(pg_url, name)


def test_migration_keeps_pre_existing_audit_rows_and_the_chain_continues(pg_url, monkeypatch):
    """Events and a batch written at 0014 (the old combined ``nf_audit`` role, no continuity
    trigger) survive 0015 up/down/up unchanged, and the next batch continues that chain."""
    from nf_platform.db import testing

    name = f"nf_m_{uuid.uuid4().hex[:10]}"
    url = testing.create_database(pg_url, name)
    eng = None
    try:
        migrate.upgrade(url, "0014m6_key_shred_freeze")
        eng = create_engine(url)
        tid = str(uuid.uuid4())
        now = datetime.now(UTC)
        with eng.begin() as c:
            c.execute(text("INSERT INTO tenant (id, name) VALUES (:i, 'tenant-old')"), {"i": tid})
            for i in range(3):
                c.execute(
                    text(
                        "INSERT INTO audit_event (id, tenant_id, type, outcome, ts) "
                        "VALUES (:i, :t, :ty, 'success', :ts)"
                    ),
                    {
                        "i": str(uuid.uuid4()),
                        "t": tid,
                        "ty": f"t.old{i}",
                        "ts": now - timedelta(hours=3),
                    },
                )

        @contextmanager
        def old_batcher_session(engine):  # the pre-0015 batcher: the combined nf_audit role
            with Session(engine) as s, s.begin():
                s.execute(text("SET LOCAL ROLE nf_audit"))
                yield s

        store = MemoryStore()
        with monkeypatch.context() as mp:
            mp.setattr(chain, "batcher_session", old_batcher_session)
            (r0,) = chain.AuditBatcher(eng, store).run(now, scopes=[tid])
        assert r0.seq == 0 and r0.event_count == 3

        def snapshot():
            with eng.connect() as c:
                return (
                    c.execute(text("SELECT * FROM audit_event ORDER BY seq")).all(),
                    c.execute(text("SELECT * FROM audit_batch ORDER BY tenant_scope, seq")).all(),
                )

        before = snapshot()
        assert len(before[0]) == 3 and len(before[1]) == 1
        migrate.upgrade(url)
        assert snapshot() == before
        migrate.downgrade(url, "0014m6_key_shred_freeze")
        assert snapshot() == before
        migrate.upgrade(url)
        assert snapshot() == before

        # after the upgrade: a new event through the writer role, batched by the batcher role
        with eng.begin() as c:
            c.execute(text(f"SET LOCAL ROLE {WRITER}"))
            c.execute(
                text(
                    "INSERT INTO audit_event (id, tenant_id, type, outcome) "
                    "VALUES (:i, :t, 't.new', 'success')"
                ),
                {"i": str(uuid.uuid4()), "t": tid},
            )
        (r1,) = chain.AuditBatcher(eng, store).run(now + timedelta(hours=1), scopes=[tid])
        assert r1.seq == 1 and r1.event_count == 1
        rows = chain.batch_rows(eng, tid)
        assert rows[1].prev_id == r0.batch_id
        assert chain.verify_stored_chain(store, tid, r1.batch_id, rows=rows) == [
            r0.batch_id,
            r1.batch_id,
        ]
        assert chain.check_events(eng, tid, chain.load_chain(store, tid)) == []
    finally:
        if eng is not None:
            eng.dispose()
        testing.drop_database(pg_url, name)
