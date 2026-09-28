"""Job queue and pipeline runs (3.3): job, run, run_artifact.

- ``job``: a Postgres queue (claimed with ``FOR UPDATE SKIP LOCKED``), per tenant, with attempts,
  exponential backoff (``run_after``), a per-attempt lease (``lease_token`` fencing token +
  ``lease_expires_at``, extended by heartbeats), a wall-clock timeout and cancellation.
- ``run``: one pipeline run (PipelineVersion ID + input recording) and its run record (every
  resolved parameter and default, seed, thread pins, library versions).
- ``run_artifact``: one output file of a run. Rows are staged with ``visible_at`` NULL by the
  attempt that holds the lease (``attempt_token``) and become visible only in the transaction that
  also commits the run's provenance (BLUEPRINT §3.5). ``UNIQUE (run_id, step, name)`` means a
  retried run can never hold two copies of an output.

Tenant isolation: forced RLS with the tenant policy of 0001 on all three tables (SEC-021). The
cross-tenant claim needs to see every tenant's queued jobs, so a separate NOLOGIN role
``nf_worker`` gets SELECT/UPDATE on ``job`` ONLY, through its own policy; it has no grant on any
other table. After a claim the worker switches to the job's tenant (``nf_app`` + app.tenant_id).

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

APP = "nf_app"
WORKER = "nf_worker"
NEW_TABLES = ("job", "run", "run_artifact")
JOB_STATES = ("queued", "running", "succeeded", "failed", "cancelled")
RUN_STATES = ("queued", "running", "succeeded", "failed", "cancelled")


def _uuid(name: str, **kw) -> sa.Column:
    return sa.Column(name, pg.UUID(as_uuid=True), **kw)


def _ts(name: str, **kw) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), **kw)


def _created() -> sa.Column:
    return _ts("created_at", nullable=False, server_default=sa.func.now())


def _tenant_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["tenant_id"], ["tenant.id"], name=f"fk_{table}_tenant_id_tenant", ondelete="RESTRICT"
    )


def _parent_fk(table: str, parent: str, col: str, ondelete: str = "RESTRICT"):
    return sa.ForeignKeyConstraint(
        ["tenant_id", col],
        [f"{parent}.tenant_id", f"{parent}.id"],
        name=f"fk_{table}_{parent}",
        ondelete=ondelete,
    )


def _in(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nf_worker') "
        f"THEN CREATE ROLE {WORKER} NOLOGIN NOSUPERUSER NOBYPASSRLS; END IF; END $$"
    )
    op.execute(f"GRANT USAGE ON SCHEMA public TO {WORKER}")

    op.create_table(
        "job",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("payload", pg.JSONB(), nullable=False, server_default="{}"),
        sa.Column("state", sa.Text(), nullable=False, server_default="queued"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("timeout_s", sa.Integer(), nullable=False, server_default="3600"),
        sa.Column("backoff_s", sa.Double(), nullable=False, server_default="5"),
        _ts("run_after", nullable=False, server_default=sa.func.now()),
        _uuid("lease_token"),
        _ts("lease_expires_at"),
        _ts("heartbeat_at"),
        sa.Column("worker_id", sa.Text()),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("dedupe_key", sa.Text()),
        sa.Column("last_error", sa.Text()),
        sa.Column("result", pg.JSONB()),
        sa.Column("created_by", sa.Text(), nullable=False),
        _created(),
        _ts("started_at"),
        _ts("finished_at"),
        sa.PrimaryKeyConstraint("id", name="pk_job"),
        _tenant_fk("job"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_job_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "kind", "dedupe_key", name="uq_job_dedupe"),
        sa.CheckConstraint(_in("state", JOB_STATES), name="ck_job_state"),
        sa.CheckConstraint("kind ~ '^[a-z][a-z0-9_.-]{0,63}$'", name="ck_job_kind"),
        sa.CheckConstraint(
            "max_attempts >= 1 AND attempts >= 0 AND timeout_s > 0 AND backoff_s >= 0",
            name="ck_job_limits",
        ),
        sa.CheckConstraint(
            "(state = 'running') = (lease_token IS NOT NULL AND lease_expires_at IS NOT NULL)",
            name="ck_job_lease",
        ),
    )
    op.create_index("ix_job_claim", "job", ["state", "run_after"])
    op.create_index("ix_job_lease", "job", ["state", "lease_expires_at"])

    op.create_table(
        "run",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        sa.Column("pipeline_version_id", sa.Text(), nullable=False),
        sa.Column("pipeline_ref", sa.Text(), nullable=False),
        _uuid("recording_id", nullable=False),
        _uuid("job_id"),
        sa.Column("state", sa.Text(), nullable=False, server_default="queued"),
        sa.Column("seed", sa.BigInteger()),
        sa.Column("record", pg.JSONB(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text()),
        _uuid("prov_activity_id"),
        sa.Column("prov_batch_id", sa.Text()),
        sa.Column("created_by", sa.Text(), nullable=False),
        _created(),
        _ts("started_at"),
        _ts("finished_at"),
        sa.PrimaryKeyConstraint("id", name="pk_run"),
        _tenant_fk("run"),
        _parent_fk("run", "recording", "recording_id"),
        _parent_fk("run", "job", "job_id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_run_tenant_id_id"),
        sa.CheckConstraint(_in("state", RUN_STATES), name="ck_run_state"),
        sa.CheckConstraint(
            "pipeline_version_id ~ '^pv:sha256:[0-9a-f]{64}$'", name="ck_run_pipeline_version_id"
        ),
        sa.CheckConstraint(
            "state <> 'succeeded' OR prov_batch_id IS NOT NULL", name="ck_run_provenance"
        ),
    )

    op.create_table(
        "run_artifact",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        _uuid("run_id", nullable=False),
        sa.Column("step", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("bucket", sa.Text(), nullable=False, server_default="artifacts"),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        _uuid("attempt_token", nullable=False),
        _ts("visible_at"),
        _uuid("prov_node_id"),
        _created(),
        sa.PrimaryKeyConstraint("id", name="pk_run_artifact"),
        _tenant_fk("run_artifact"),
        _parent_fk("run_artifact", "run", "run_id", ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "run_id", "step", "name", name="uq_run_artifact_output"),
        sa.CheckConstraint("bucket = 'artifacts'", name="ck_run_artifact_bucket"),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_run_artifact_sha256"),
        sa.CheckConstraint(
            "visible_at IS NULL OR prov_node_id IS NOT NULL", name="ck_run_artifact_provenance"
        ),
    )

    # ---------------------------------------------------------------- grants + RLS (SEC-021)
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {', '.join(NEW_TABLES)} TO {APP}")
    for t in NEW_TABLES:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {t} TO {APP} "
            "USING (tenant_id = nf_current_tenant()) WITH CHECK (tenant_id = nf_current_tenant())"
        )
    # The claim path: nf_worker sees every tenant's job rows, and nothing else.
    op.execute(f"GRANT SELECT, UPDATE ON job TO {WORKER}")
    op.execute(f"CREATE POLICY worker_claim ON job TO {WORKER} USING (true) WITH CHECK (true)")


def downgrade() -> None:
    for t in reversed(NEW_TABLES):
        op.drop_table(t)
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {WORKER}")
