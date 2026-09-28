"""Multiverse sweeps (3.6): sweep, sweep_run.

- ``sweep``: a parameter grid over one published PipelineVersion (``pipeline_version_id`` = the
  base), the normalized request (``spec``), the metric the report reads (``metric_step`` /
  ``metric_key``) and the sweep's PROV activity node.
- ``sweep_run``: one cell = one grid point (``variant``, published as its own content-addressed
  PipelineVersion ``pipeline_version_id``) on one recording, and the run that computes it.

Tenant isolation: forced RLS with the tenant policy of 0001 on both tables (SEC-021).

Revision ID: 0005_sweeps
Revises: 0004
Create Date: 2026-09-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0005_sweeps"
down_revision = "0004"
branch_labels = None
depends_on = None

APP = "nf_app"
NEW_TABLES = ("sweep", "sweep_run")


def _uuid(name: str, **kw) -> sa.Column:
    return sa.Column(name, pg.UUID(as_uuid=True), **kw)


def upgrade() -> None:
    op.create_table(
        "sweep",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("pipeline_ref", sa.Text(), nullable=False),
        sa.Column("pipeline_version_id", sa.Text(), nullable=False),
        sa.Column("spec", pg.JSONB(), nullable=False),
        sa.Column("metric_step", sa.Text(), nullable=False),
        sa.Column("metric_key", sa.Text(), nullable=False),
        sa.Column("n_variants", sa.Integer(), nullable=False),
        sa.Column("n_runs", sa.Integer(), nullable=False),
        _uuid("prov_node_id"),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id", name="pk_sweep"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenant.id"], name="fk_sweep_tenant_id_tenant", ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_sweep_tenant_id_id"),
        sa.CheckConstraint(
            "pipeline_version_id ~ '^pv:sha256:[0-9a-f]{64}$'", name="ck_sweep_pipeline_version_id"
        ),
        sa.CheckConstraint("n_variants >= 1 AND n_runs >= 1", name="ck_sweep_counts"),
    )
    op.create_table(
        "sweep_run",
        _uuid("tenant_id", nullable=False),
        _uuid("sweep_id", nullable=False),
        sa.Column("variant", sa.Integer(), nullable=False),
        _uuid("recording_id", nullable=False),
        _uuid("run_id", nullable=False),
        sa.Column("params", pg.JSONB(), nullable=False),
        sa.Column("pipeline_ref", sa.Text(), nullable=False),
        sa.Column("pipeline_version_id", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint(
            "tenant_id", "sweep_id", "variant", "recording_id", name="pk_sweep_run"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenant.id"], name="fk_sweep_run_tenant_id_tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "sweep_id"],
            ["sweep.tenant_id", "sweep.id"],
            name="fk_sweep_run_sweep",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "run_id"],
            ["run.tenant_id", "run.id"],
            name="fk_sweep_run_run",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "run_id", name="uq_sweep_run_run"),
        sa.CheckConstraint("variant >= 0", name="ck_sweep_run_variant"),
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


def downgrade() -> None:
    for t in reversed(NEW_TABLES):
        op.drop_table(t)
