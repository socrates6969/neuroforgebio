"""M5 deletion propagation (5.5; BLUEPRINT §8.4): deletion_job, derived_object, artifact_status,
model_flag.

- ``deletion_job``: one subject withdrawal, its queue job, timings and the signed certificate.
- ``derived_object``: multi-subject derived objects (group averages, toy/trained models) with their
  own KMS-wrapped data key (they cannot live under one subject's key). Destroying the key
  (``key_state='shredded'``, ``wrapped_dek`` NULL) makes every copy unreadable.
- ``artifact_status``: what a DeletionJob did to a provenance entity (deleted / stale / tombstoned /
  superseded); the provenance graph itself stays append-only.
- ``model_flag``: the ``retrain_required`` hook the model registry (M6) reads.

Forced RLS with the tenant policy of 0001 on every table (SEC-021).

Revision ID: 0007m5_deletion
Revises: 0006m5_consent
Create Date: 2026-09-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0007m5_deletion"
down_revision = "0006m5_consent"
branch_labels = None
depends_on = None

APP = "nf_app"
NEW_TABLES = ("deletion_job", "derived_object", "artifact_status", "model_flag")


def _uuid(name: str, **kw) -> sa.Column:
    return sa.Column(name, pg.UUID(as_uuid=True), **kw)


def _ts(name: str, **kw) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), **kw)


def _in(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def _tenant_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["tenant_id"], ["tenant.id"], name=f"fk_{table}_tenant_id_tenant", ondelete="RESTRICT"
    )


def _node_fk(table: str, col: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["tenant_id", col],
        ["prov_node.tenant_id", "prov_node.id"],
        name=f"fk_{table}_prov_node",
        ondelete="RESTRICT",
    )


def upgrade() -> None:
    op.create_table(
        "deletion_job",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        _uuid("subject_id", nullable=False),
        _uuid("job_id"),
        sa.Column("state", sa.Text(), nullable=False, server_default="queued"),
        sa.Column("aggregate_policy", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.Text(), nullable=False),
        _ts("requested_at", nullable=False, server_default=sa.func.now()),
        _ts("started_at"),
        _ts("finished_at"),
        sa.Column("duration_s", sa.Double()),
        sa.Column("certificate", pg.JSONB()),
        sa.Column("error", sa.Text()),
        sa.PrimaryKeyConstraint("id", name="pk_deletion_job"),
        _tenant_fk("deletion_job"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_deletion_job_tenant_id_id"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "subject_id"],
            ["subject.tenant_id", "subject.id"],
            name="fk_deletion_job_subject",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "job_id"],
            ["job.tenant_id", "job.id"],
            name="fk_deletion_job_job",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            _in("state", ("queued", "running", "succeeded", "failed")),
            name="ck_deletion_job_state",
        ),
        sa.CheckConstraint(
            _in("aggregate_policy", ("rerun", "tombstone")), name="ck_deletion_job_aggregate"
        ),
    )
    op.create_table(
        "derived_object",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        _uuid("node_id"),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("bucket", sa.Text(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("kek_id", sa.Text(), nullable=False),
        sa.Column("wrapped_dek", sa.LargeBinary()),
        sa.Column("key_state", sa.Text(), nullable=False, server_default="active"),
        sa.Column("input_node_ids", pg.ARRAY(pg.UUID(as_uuid=True)), nullable=False),
        sa.Column("params", pg.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_by", sa.Text(), nullable=False),
        _ts("created_at", nullable=False, server_default=sa.func.now()),
        _ts("shredded_at"),
        sa.PrimaryKeyConstraint("id", name="pk_derived_object"),
        _tenant_fk("derived_object"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_derived_object_tenant_id_id"),
        sa.CheckConstraint(_in("kind", ("group_average", "model")), name="ck_derived_object_kind"),
        sa.CheckConstraint("bucket IN ('artifacts', 'models')", name="ck_derived_object_bucket"),
        sa.CheckConstraint(
            "key_state IN ('active', 'shredded')", name="ck_derived_object_key_state"
        ),
        sa.CheckConstraint(
            "(key_state = 'shredded') OR (wrapped_dek IS NOT NULL)",
            name="ck_derived_object_wrapped_unless_shredded",
        ),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_derived_object_sha256"),
    )
    op.create_table(
        "artifact_status",
        _uuid("tenant_id", nullable=False),
        _uuid("node_id", nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        _uuid("deletion_job_id"),
        _uuid("replaced_by"),
        _ts("updated_at", nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("tenant_id", "node_id", name="pk_artifact_status"),
        _tenant_fk("artifact_status"),
        _node_fk("artifact_status", "node_id"),
        sa.CheckConstraint(
            _in("status", ("deleted", "stale", "tombstoned", "superseded")),
            name="ck_artifact_status_status",
        ),
    )
    op.create_table(
        "model_flag",
        _uuid("tenant_id", nullable=False),
        _uuid("model_node_id", nullable=False),
        _uuid("deletion_job_id", nullable=False),
        sa.Column("flag", sa.Text(), nullable=False, server_default="retrain_required"),
        sa.Column("block_deployments", sa.Boolean(), nullable=False),
        _ts("created_at", nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint(
            "tenant_id", "model_node_id", "deletion_job_id", name="pk_model_flag"
        ),
        _tenant_fk("model_flag"),
        _node_fk("model_flag", "model_node_id"),
        sa.CheckConstraint("flag = 'retrain_required'", name="ck_model_flag_flag"),
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON {', '.join(NEW_TABLES)} TO {APP}")
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
