"""Provenance graph (3.1) and published PipelineVersions (3.2): prov_batch, prov_node, prov_edge,
pipeline_version. Forced RLS with the tenant policy of 0001 on every table; append-only (UPDATE,
DELETE, TRUNCATE raise; nf_app has SELECT + INSERT only), SEC-043/SEC-044.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

APP = "nf_app"
NEW_TABLES = ("prov_batch", "prov_node", "prov_edge", "pipeline_version")
KINDS = ("entity", "activity", "agent")
RELS = (
    "used",
    "wasGeneratedBy",
    "wasDerivedFrom",
    "wasAttributedTo",
    "wasAssociatedWith",
    "wasInformedBy",
)
CONTENT_ID_RE = "^(blob|pv|chunk|provb):sha256:[0-9a-f]{64}$"


def _uuid(name: str, **kw) -> sa.Column:
    return sa.Column(name, pg.UUID(as_uuid=True), **kw)


def _created() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


def _tenant_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["tenant_id"], ["tenant.id"], name=f"fk_{table}_tenant_id_tenant", ondelete="RESTRICT"
    )


def _in(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.create_table(
        "prov_batch",
        _uuid("tenant_id", nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Text(), nullable=False),
        sa.Column("prev_id", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("n_records", sa.Integer(), nullable=False),
        sa.Column("key_id", sa.Text(), nullable=False),
        sa.Column("signature", sa.LargeBinary(), nullable=False),
        sa.PrimaryKeyConstraint("tenant_id", "seq", name="pk_prov_batch"),
        _tenant_fk("prov_batch"),
        sa.UniqueConstraint("batch_id", name="uq_prov_batch_batch_id"),
        sa.CheckConstraint("seq >= 0", name="ck_prov_batch_seq"),
        sa.CheckConstraint(
            "batch_id ~ '^provb:sha256:[0-9a-f]{64}$'", name="ck_prov_batch_batch_id"
        ),
        sa.CheckConstraint("(seq = 0) = (prev_id IS NULL)", name="ck_prov_batch_prev"),
        sa.CheckConstraint("octet_length(signature) = 64", name="ck_prov_batch_signature_len"),
    )
    op.create_table(
        "prov_node",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("ref_id", sa.Text()),
        sa.Column("content_hash", sa.Text()),
        sa.Column("attrs", pg.JSONB(), nullable=False, server_default="{}"),
        sa.Column("node_hash", sa.String(64), nullable=False),
        sa.Column("batch_seq", sa.Integer(), nullable=False),
        sa.Column("ord", sa.Integer(), nullable=False),
        _created(),
        sa.PrimaryKeyConstraint("id", name="pk_prov_node"),
        _tenant_fk("prov_node"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_prov_node_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "batch_seq", "ord", name="uq_prov_node_batch_ord"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "batch_seq"],
            ["prov_batch.tenant_id", "prov_batch.seq"],
            name="fk_prov_node_prov_batch",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(_in("kind", KINDS), name="ck_prov_node_kind"),
        sa.CheckConstraint(
            f"content_hash IS NULL OR content_hash ~ '{CONTENT_ID_RE}'",
            name="ck_prov_node_content_hash",
        ),
        sa.CheckConstraint("node_hash ~ '^[0-9a-f]{64}$'", name="ck_prov_node_node_hash"),
    )
    op.create_index(
        "uq_prov_node_ref",
        "prov_node",
        ["tenant_id", "kind", "type", "ref_id"],
        unique=True,
        postgresql_where=sa.text("ref_id IS NOT NULL"),
    )
    op.create_table(
        "prov_edge",
        _uuid("tenant_id", nullable=False),
        _uuid("src", nullable=False),
        sa.Column("rel", sa.Text(), nullable=False),
        _uuid("dst", nullable=False),
        sa.Column("batch_seq", sa.Integer(), nullable=False),
        sa.Column("ord", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("src", "rel", "dst", name="pk_prov_edge"),
        _tenant_fk("prov_edge"),
        sa.UniqueConstraint("tenant_id", "batch_seq", "ord", name="uq_prov_edge_batch_ord"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "src"],
            ["prov_node.tenant_id", "prov_node.id"],
            name="fk_prov_edge_src",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "dst"],
            ["prov_node.tenant_id", "prov_node.id"],
            name="fk_prov_edge_dst",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "batch_seq"],
            ["prov_batch.tenant_id", "prov_batch.seq"],
            name="fk_prov_edge_prov_batch",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(_in("rel", RELS), name="ck_prov_edge_rel"),
        sa.CheckConstraint("src <> dst", name="ck_prov_edge_no_self_loop"),
    )
    op.create_index("ix_prov_edge_dst", "prov_edge", ["dst"])
    op.create_table(
        "pipeline_version",
        _uuid("tenant_id", nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("pv_id", sa.Text(), nullable=False),
        sa.Column("spec", pg.JSONB(), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        _created(),
        sa.PrimaryKeyConstraint("tenant_id", "name", "version", name="pk_pipeline_version"),
        _tenant_fk("pipeline_version"),
        sa.CheckConstraint("pv_id ~ '^pv:sha256:[0-9a-f]{64}$'", name="ck_pipeline_version_pv_id"),
    )
    op.create_index("ix_pipeline_version_pv_id", "pipeline_version", ["tenant_id", "pv_id"])

    # ---------------------------------------------------------------- append-only (SEC-043/044)
    for t in NEW_TABLES:
        op.execute(
            f"CREATE TRIGGER {t}_append_only BEFORE UPDATE OR DELETE ON {t} "
            "FOR EACH ROW EXECUTE FUNCTION nf_append_only()"
        )
        op.execute(
            f"CREATE TRIGGER {t}_no_truncate BEFORE TRUNCATE ON {t} "
            "FOR EACH STATEMENT EXECUTE FUNCTION nf_append_only()"
        )

    # ---------------------------------------------------------------- grants + RLS (SEC-021)
    op.execute(f"GRANT SELECT, INSERT ON {', '.join(NEW_TABLES)} TO {APP}")
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
