"""M5 consent ledger (5.3; BLUEPRINT §8.3): consent_document, consent_record.

- ``consent_document``: versioned consent documents identified by the SHA-256 of their bytes.
- ``consent_record``: the ledger. Append-only at the DB level: a trigger rejects UPDATE, DELETE and
  TRUNCATE for every role (including the owner), and ``nf_app`` holds SELECT + INSERT only. Each
  entry is hash-chained to the previous entry of its tenant (``prev_hash`` -> ``record_hash``); the
  chain head is anchored daily in the WORM ``audit`` bucket (job ``consent.anchor``).

Forced RLS with the tenant policy of 0001 on both tables (SEC-021).

Revision ID: 0006m5_consent
Revises: 0005m5_governance
Create Date: 2026-09-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0006m5_consent"
down_revision = "0005m5_governance"
branch_labels = None
depends_on = None

APP = "nf_app"
NEW_TABLES = ("consent_document", "consent_record")
SCOPES = ("collection", "processing", "sharing", "model_training", "commercial_use")


def _in(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def _tenant_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["tenant_id"], ["tenant.id"], name=f"fk_{table}_tenant_id_tenant", ondelete="RESTRICT"
    )


def _append_only(tables: tuple[str, ...]) -> None:
    for t in tables:
        op.execute(
            f"CREATE TRIGGER {t}_append_only BEFORE UPDATE OR DELETE ON {t} "
            "FOR EACH ROW EXECUTE FUNCTION nf_append_only()"
        )
        op.execute(
            f"CREATE TRIGGER {t}_no_truncate BEFORE TRUNCATE ON {t} "
            "FOR EACH STATEMENT EXECUTE FUNCTION nf_append_only()"
        )


def _enable_rls(tables: tuple[str, ...]) -> None:
    for t in tables:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {t} TO {APP} "
            "USING (tenant_id = nf_current_tenant()) WITH CHECK (tenant_id = nf_current_tenant())"
        )


def _uuid(name: str, **kw) -> sa.Column:
    return sa.Column(name, pg.UUID(as_uuid=True), **kw)


def upgrade() -> None:
    op.create_table(
        "consent_document",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("uri", sa.Text()),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id", name="pk_consent_document"),
        _tenant_fk("consent_document"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_consent_document_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "name", "version", name="uq_consent_document_version"),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_consent_document_sha256"),
    )
    op.create_table(
        "consent_record",
        _uuid("tenant_id", nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        _uuid("id", nullable=False),
        _uuid("subject_id", nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("scopes", pg.ARRAY(sa.Text()), nullable=False),
        _uuid("document_id"),
        sa.Column("document_sha256", sa.String(64)),
        sa.Column("jurisdiction_basis", sa.Text()),
        sa.Column("collector_id", sa.Text(), nullable=False),
        sa.Column("evidence_ref", sa.Text()),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("prev_hash", sa.String(64)),
        sa.Column("record_hash", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("tenant_id", "seq", name="pk_consent_record"),
        _tenant_fk("consent_record"),
        sa.UniqueConstraint("id", name="uq_consent_record_id"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "subject_id"],
            ["subject.tenant_id", "subject.id"],
            name="fk_consent_record_subject",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "document_id"],
            ["consent_document.tenant_id", "consent_document.id"],
            name="fk_consent_record_consent_document",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(_in("kind", ("grant", "withdraw")), name="ck_consent_record_kind"),
        sa.CheckConstraint(
            "scopes <@ ARRAY[" + ", ".join(f"'{s}'" for s in SCOPES) + "]::text[]",
            name="ck_consent_record_scopes",
        ),
        sa.CheckConstraint(
            "kind = 'withdraw' OR document_id IS NOT NULL", name="ck_consent_record_document"
        ),
        sa.CheckConstraint(
            "seq >= 0 AND (seq = 0) = (prev_hash IS NULL)", name="ck_consent_record_prev"
        ),
        sa.CheckConstraint("record_hash ~ '^[0-9a-f]{64}$'", name="ck_consent_record_record_hash"),
    )
    op.create_index(
        "ix_consent_record_subject", "consent_record", ["tenant_id", "subject_id", "seq"]
    )
    _append_only(NEW_TABLES)
    op.execute(f"GRANT SELECT, INSERT ON {', '.join(NEW_TABLES)} TO {APP}")
    _enable_rls(NEW_TABLES)


def downgrade() -> None:
    for t in reversed(NEW_TABLES):
        op.drop_table(t)
