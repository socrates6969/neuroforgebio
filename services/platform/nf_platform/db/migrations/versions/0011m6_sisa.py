"""M6 (m6-sisa, 6.5): model_version_sbom, the CycloneDX SBOM of the container a model version
runs in. The SOUP export (``GET /v1/models/{model_id}/versions/{version}/soup``) lists every
component of it. One SBOM per version; re-attaching replaces it (audited). Forced RLS with the
tenant policy of 0001 (SEC-021).

Revision ID: 0011m6_sisa
Revises: 0010m6_registry
Create Date: 2026-09-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0011m6_sisa"
down_revision = "0010m6_registry"
branch_labels = None
depends_on = None

APP = "nf_app"
TABLE = "model_version_sbom"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("version_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("sbom", pg.JSONB(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("spec_version", sa.Text(), nullable=False),
        sa.Column("component_count", sa.Integer(), nullable=False),
        sa.Column("attached_by", sa.Text(), nullable=False),
        sa.Column(
            "attached_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("tenant_id", "version_id", name="pk_model_version_sbom"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
            name="fk_model_version_sbom_tenant_id_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "version_id"],
            ["model_version.tenant_id", "model_version.id"],
            name="fk_model_version_sbom_version",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_model_version_sbom_sha256"),
        sa.CheckConstraint("component_count >= 0", name="ck_model_version_sbom_component_count"),
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON {TABLE} TO {APP}")
    op.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {TABLE} TO {APP} "
        "USING (tenant_id = nf_current_tenant()) WITH CHECK (tenant_id = nf_current_tenant())"
    )


def downgrade() -> None:
    op.drop_table(TABLE)
