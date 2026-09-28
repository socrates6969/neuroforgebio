"""M5 governance (5.1, 5.5 settings, export log): artifact_governance, tenant_policy, data_export.

- ``artifact_governance``: a data steward's explicit governance attributes for a derived artifact
  (a provenance entity); without a row the artifact inherits the strictest attributes of its
  inputs through the lineage (BLUEPRINT §8.2). Writes are data-steward/admin only (SEC-022) and
  audited; the table is mutable (the audit log is the history).
- ``tenant_policy``: per-tenant withdrawal behaviour for multi-subject aggregates (re-run without
  the subject, or tombstone) and whether a ``retrain_required`` flag blocks deployments.
- ``data_export``: exports that left the platform. Append-only (trigger; ``nf_app`` has SELECT +
  INSERT only); a DeletionJob lists them because they cannot be recalled.

Forced RLS with the tenant policy of 0001 on every table (SEC-021).

Revision ID: 0005m5_governance
Revises: 0004
Create Date: 2026-09-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0005m5_governance"
down_revision = "0004"
branch_labels = None
depends_on = None

APP = "nf_app"
NEW_TABLES = ("artifact_governance", "tenant_policy", "data_export")
NERVOUS_SYSTEMS = ("central", "peripheral", "unknown")


def _uuid(name: str, **kw) -> sa.Column:
    return sa.Column(name, pg.UUID(as_uuid=True), **kw)


def _ts(name: str, **kw) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), **kw)


def _tenant_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["tenant_id"], ["tenant.id"], name=f"fk_{table}_tenant_id_tenant", ondelete="RESTRICT"
    )


def _in(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def enable_rls(tables: tuple[str, ...]) -> None:
    for t in tables:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {t} TO {APP} "
            "USING (tenant_id = nf_current_tenant()) WITH CHECK (tenant_id = nf_current_tenant())"
        )


def append_only(tables: tuple[str, ...]) -> None:
    for t in tables:
        op.execute(
            f"CREATE TRIGGER {t}_append_only BEFORE UPDATE OR DELETE ON {t} "
            "FOR EACH ROW EXECUTE FUNCTION nf_append_only()"
        )
        op.execute(
            f"CREATE TRIGGER {t}_no_truncate BEFORE TRUNCATE ON {t} "
            "FOR EACH STATEMENT EXECUTE FUNCTION nf_append_only()"
        )


def upgrade() -> None:
    op.create_table(
        "artifact_governance",
        _uuid("tenant_id", nullable=False),
        _uuid("node_id", nullable=False),
        sa.Column("modalities", pg.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("nervous_system", sa.Text(), nullable=False),
        sa.Column("derived_from_non_neural", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("updated_by", sa.Text(), nullable=False),
        _ts("updated_at", nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("tenant_id", "node_id", name="pk_artifact_governance"),
        _tenant_fk("artifact_governance"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "node_id"],
            ["prov_node.tenant_id", "prov_node.id"],
            name="fk_artifact_governance_prov_node",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            _in("nervous_system", NERVOUS_SYSTEMS), name="ck_artifact_governance_nervous_system"
        ),
    )
    op.create_table(
        "tenant_policy",
        _uuid("tenant_id", nullable=False),
        sa.Column("aggregate_on_withdrawal", sa.Text(), nullable=False, server_default="rerun"),
        sa.Column(
            "block_deployments_on_retrain", sa.Boolean(), nullable=False, server_default="true"
        ),
        sa.Column("updated_by", sa.Text(), nullable=False),
        _ts("updated_at", nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("tenant_id", name="pk_tenant_policy"),
        _tenant_fk("tenant_policy"),
        sa.CheckConstraint(
            _in("aggregate_on_withdrawal", ("rerun", "tombstone")),
            name="ck_tenant_policy_aggregate",
        ),
    )
    op.create_table(
        "data_export",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        sa.Column("node_ids", pg.ARRAY(pg.UUID(as_uuid=True)), nullable=False),
        sa.Column("subject_ids", pg.ARRAY(pg.UUID(as_uuid=True)), nullable=False),
        sa.Column("destination", sa.Text(), nullable=False),
        sa.Column("format", sa.Text()),
        sa.Column("exported_by", sa.Text(), nullable=False),
        _ts("exported_at", nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_data_export"),
        _tenant_fk("data_export"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_data_export_tenant_id_id"),
    )
    append_only(("data_export",))
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON artifact_governance, tenant_policy TO {APP}")
    op.execute(f"GRANT SELECT, INSERT ON data_export TO {APP}")
    enable_rls(NEW_TABLES)


def downgrade() -> None:
    for t in reversed(NEW_TABLES):
        op.drop_table(t)
