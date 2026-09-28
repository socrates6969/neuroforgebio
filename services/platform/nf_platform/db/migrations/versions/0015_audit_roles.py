"""AppSec M2: split the audit role and make every audit batch continue its chain.

Before: ``nf_audit`` could INSERT into both ``audit_event`` and ``audit_batch`` (policies ``WITH
CHECK (true)``), and the batcher trusted the newest ``audit_batch`` row completely. One forged row
(``last_event_seq = 9e18``) stopped all future batching of a tenant and replaced the chain head.

After:

- ``nf_audit_writer``: INSERT on ``audit_event`` only (the API/worker event sink). Its INSERT
  policy checks what the database can check: the tenant exists (or is NULL for the ``_platform``
  scope), ``outcome`` and ``actor_kind`` are known values, ``ts`` is the insert time (±5 min). The
  BEFORE INSERT trigger ``audit_event_seq_guard`` (every role) refuses a hand-picked ``seq``
  (``OVERRIDING SYSTEM VALUE``): the row's ``seq`` must be the identity value this insert drew.
- ``nf_audit_batcher``: SELECT on both tables, INSERT on ``audit_batch`` (only the batcher job's
  session, ``audit.chain.batcher_session``). Deployment: a separate DB login that is the only
  member of this role; the API login must not be granted it (docs/security/SEC-COVERAGE.md).
- ``nf_audit`` keeps no audit privilege (roles are cluster-wide and survive downgrades).
- BEFORE INSERT trigger ``audit_batch_continuity`` (every role, superuser included; SQLSTATE
  ``NF105``): per scope (under the batcher's advisory lock) ``seq`` = previous + 1 (0 with no
  ``prev_id`` for the first), ``prev_id`` = the previous ``batch_id``, ``first_event_seq`` after the
  previous ``last_event_seq``, and ``first_event_seq``/``last_event_seq``/``event_count`` equal the
  min/max/count of the scope's events in that range (so ``last_event_seq`` never passes the newest
  event).

Revision ID: 0015_audit_roles
Revises: 0014m6_key_shred_freeze
Create Date: 2026-09-26
"""

from __future__ import annotations

from alembic import op

revision = "0015_audit_roles"
down_revision = "0014m6_key_shred_freeze"
branch_labels = None
depends_on = None

OLD, WRITER, BATCHER = "nf_audit", "nf_audit_writer", "nf_audit_batcher"
SQLSTATE = "NF105"
OUTCOMES = "('success', 'failure', 'denied')"
ACTOR_KINDS = "('user', 'api_key', 'device', 'service')"

CONTINUITY = f"""
CREATE FUNCTION nf_audit_batch_continuity() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    prev record;
    n bigint;
    lo bigint;
    hi bigint;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtext('auditb:' || NEW.tenant_scope));
    IF NEW.first_event_seq IS NULL OR NEW.last_event_seq IS NULL OR NEW.event_count < 1
       OR NEW.first_event_seq > NEW.last_event_seq THEN
        RAISE EXCEPTION USING ERRCODE = '{SQLSTATE}',
            MESSAGE = 'audit chain continuity: a batch covers at least one event (first <= last)';
    END IF;
    SELECT seq, batch_id, last_event_seq INTO prev FROM audit_batch
        WHERE tenant_scope = NEW.tenant_scope ORDER BY seq DESC LIMIT 1;
    IF NOT FOUND THEN
        IF NEW.seq <> 0 OR NEW.prev_id IS NOT NULL THEN
            RAISE EXCEPTION USING ERRCODE = '{SQLSTATE}',
                MESSAGE = 'audit chain continuity: a first batch has seq 0 and no prev_id';
        END IF;
    ELSE
        IF NEW.seq <> prev.seq + 1 THEN
            RAISE EXCEPTION USING ERRCODE = '{SQLSTATE}',
                MESSAGE = format('audit chain continuity: seq must be %s', prev.seq + 1);
        END IF;
        IF NEW.prev_id IS DISTINCT FROM prev.batch_id THEN
            RAISE EXCEPTION USING ERRCODE = '{SQLSTATE}',
                MESSAGE = 'audit chain continuity: prev_id must be the previous batch id';
        END IF;
        IF prev.last_event_seq IS NOT NULL AND NEW.first_event_seq <= prev.last_event_seq THEN
            RAISE EXCEPTION USING ERRCODE = '{SQLSTATE}',
                MESSAGE = 'audit chain continuity: first_event_seq must follow the previous batch';
        END IF;
    END IF;
    SELECT count(*), min(e.seq), max(e.seq) INTO n, lo, hi FROM audit_event e
        WHERE e.seq BETWEEN NEW.first_event_seq AND NEW.last_event_seq
          AND CASE WHEN NEW.tenant_scope = '_platform' THEN e.tenant_id IS NULL
                   ELSE e.tenant_id::text = NEW.tenant_scope END;
    IF n <> NEW.event_count OR lo IS DISTINCT FROM NEW.first_event_seq
       OR hi IS DISTINCT FROM NEW.last_event_seq THEN
        RAISE EXCEPTION USING ERRCODE = '{SQLSTATE}',
            MESSAGE = 'audit chain continuity: first/last event seq and event_count must match '
                      'the scope''s events in audit_event';
    END IF;
    RETURN NEW;
END $$
"""

SEQ_GUARD = f"""
CREATE FUNCTION nf_audit_event_seq_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    BEGIN
        IF NEW.seq IS DISTINCT FROM currval(pg_get_serial_sequence('audit_event', 'seq')) THEN
            RAISE EXCEPTION USING ERRCODE = '{SQLSTATE}',
                MESSAGE = 'audit_event: seq is assigned by the database';
        END IF;
    EXCEPTION WHEN object_not_in_prerequisite_state THEN  -- no identity value drawn
        RAISE EXCEPTION USING ERRCODE = '{SQLSTATE}',
            MESSAGE = 'audit_event: seq is assigned by the database';
    END;
    RETURN NEW;
END $$
"""


def upgrade() -> None:
    for role in (WRITER, BATCHER):
        op.execute(
            f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') "
            f"THEN CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS; END IF; END $$"
        )
    op.execute(f"GRANT USAGE ON SCHEMA public TO {WRITER}, {BATCHER}")

    # the combined role loses everything on the audit tables
    for t in ("audit_event", "audit_batch"):
        op.execute(f"DROP POLICY audit_write ON {t}")
        op.execute(f"DROP POLICY audit_read ON {t}")
    op.execute(f"REVOKE ALL ON audit_event, audit_batch FROM {OLD}")

    # writer: insert events, nothing else (no RETURNING either: the sink inserts without it)
    op.execute(f"GRANT INSERT ON audit_event TO {WRITER}")
    op.execute(f"GRANT SELECT ON SEQUENCE audit_event_seq_seq TO {WRITER}")  # currval in the guard
    op.execute(f"GRANT SELECT (id) ON tenant TO {WRITER}")
    op.execute(
        f"CREATE POLICY audit_writer_tenant_exists ON tenant FOR SELECT TO {WRITER} USING (true)"
    )
    op.execute(
        f"CREATE POLICY audit_writer_insert ON audit_event FOR INSERT TO {WRITER} WITH CHECK ("
        "(tenant_id IS NULL OR EXISTS (SELECT 1 FROM tenant t WHERE t.id = tenant_id)) "
        f"AND outcome IN {OUTCOMES} "
        f"AND (actor_kind IS NULL OR actor_kind IN {ACTOR_KINDS}) "
        "AND ts BETWEEN now() - interval '5 minutes' AND now() + interval '5 minutes')"
    )

    # batcher: read both tables, insert batches (the continuity trigger does the checking)
    op.execute(f"GRANT SELECT ON audit_event, audit_batch TO {BATCHER}")
    op.execute(f"GRANT INSERT ON audit_batch TO {BATCHER}")
    for t in ("audit_event", "audit_batch"):
        op.execute(f"CREATE POLICY audit_batcher_read ON {t} FOR SELECT TO {BATCHER} USING (true)")
    op.execute(
        f"CREATE POLICY audit_batcher_insert ON audit_batch FOR INSERT TO {BATCHER} "
        "WITH CHECK (true)"
    )

    op.execute(CONTINUITY)
    op.execute(
        "CREATE TRIGGER audit_batch_continuity BEFORE INSERT ON audit_batch "
        "FOR EACH ROW EXECUTE FUNCTION nf_audit_batch_continuity()"
    )
    op.execute(SEQ_GUARD)
    op.execute(
        "CREATE TRIGGER audit_event_seq_guard BEFORE INSERT ON audit_event "
        "FOR EACH ROW EXECUTE FUNCTION nf_audit_event_seq_guard()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER audit_event_seq_guard ON audit_event")
    op.execute("DROP FUNCTION nf_audit_event_seq_guard()")
    op.execute("DROP TRIGGER audit_batch_continuity ON audit_batch")
    op.execute("DROP FUNCTION nf_audit_batch_continuity()")
    op.execute("DROP POLICY audit_batcher_insert ON audit_batch")
    for t in ("audit_event", "audit_batch"):
        op.execute(f"DROP POLICY audit_batcher_read ON {t}")
    op.execute("DROP POLICY audit_writer_insert ON audit_event")
    op.execute("DROP POLICY audit_writer_tenant_exists ON tenant")
    op.execute(f"REVOKE ALL ON audit_event, audit_batch FROM {WRITER}, {BATCHER}")
    op.execute(f"REVOKE ALL ON SEQUENCE audit_event_seq_seq FROM {WRITER}")
    op.execute(f"REVOKE ALL ON tenant FROM {WRITER}")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {WRITER}, {BATCHER}")
    # back to the 0001 grants and policies of the combined role
    op.execute(f"GRANT SELECT, INSERT ON audit_event, audit_batch TO {OLD}")
    for t in ("audit_event", "audit_batch"):
        op.execute(f"CREATE POLICY audit_write ON {t} FOR INSERT TO {OLD} WITH CHECK (true)")
        op.execute(f"CREATE POLICY audit_read ON {t} FOR SELECT TO {OLD} USING (true)")
