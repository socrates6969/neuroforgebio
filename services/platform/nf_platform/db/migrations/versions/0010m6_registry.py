"""M6 governed model registry (6.1-6.3; BLUEPRINT §3.7, §8.4): model, model_version,
model_approval, model_use_exception, model_deployment, model_retrain.

- ``model``: name + model card (``nf.model-card/v1``), private to the tenant (SEC-143).
- ``model_version``: encrypted weights (a ``derived_object`` with its own data key), the model's
  provenance node (the M5 ``model_flag`` hook keys on it), the training manifest of hashed subject
  IDs, pipeline versions, code commit, intended use, use restrictions, publication state.
- ``model_approval``: four-eyes approvals for publication (SEC-143).
- ``model_use_exception``: documented medical/safety exceptions (EU AI Act Art. 5(1)(f)).
- ``model_deployment``: deployment requests with their declared context; refused ones are kept
  (append-only: the app role may only SELECT/INSERT).
- ``model_retrain``: retrain jobs on the 3.3 queue that exclude withdrawn subjects (6.3).

Forced RLS with the tenant policy of 0001 on every table (SEC-021).

Revision ID: 0010m6_registry
Revises: 0009m5_phi
Create Date: 2026-09-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0010m6_registry"
down_revision = "0009m5_phi"
branch_labels = None
depends_on = None

APP = "nf_app"
NEW_TABLES = (
    "model",
    "model_version",
    "model_approval",
    "model_use_exception",
    "model_deployment",
    "model_retrain",
)
APPEND_ONLY = ("model_deployment", "model_approval")


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


def _fk(table: str, cols: list[str], ref: str, name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["tenant_id", *cols],
        [f"{ref}.tenant_id", f"{ref}.id"],
        name=f"fk_{table}_{name}",
        ondelete="RESTRICT",
    )


def upgrade() -> None:
    op.create_table(
        "model",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("card", pg.JSONB(), nullable=False),
        sa.Column("card_sha256", sa.String(64), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        _ts("created_at", nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_model"),
        _tenant_fk("model"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_model_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_model_tenant_id_name"),
        sa.CheckConstraint("card_sha256 ~ '^[0-9a-f]{64}$'", name="ck_model_card_sha256"),
    )
    op.create_table(
        "model_version",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        _uuid("model_id", nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        _uuid("derived_object_id", nullable=False),
        sa.Column("weights_format", sa.Text(), nullable=False),
        sa.Column("weights_sha256", sa.String(64), nullable=False),
        _uuid("prov_node_id", nullable=False),
        sa.Column("manifest", pg.JSONB(), nullable=False),
        sa.Column("manifest_sha256", sa.String(64), nullable=False),
        sa.Column("pipeline_version_ids", pg.ARRAY(sa.Text()), nullable=False),
        sa.Column("code_commit", sa.Text(), nullable=False),
        sa.Column("intended_use", sa.Text(), nullable=False),
        sa.Column("use_restrictions", pg.ARRAY(sa.Text()), nullable=False),
        sa.Column("recipe", sa.Text()),
        _uuid("parent_version_id"),
        sa.Column("visibility", sa.Text(), nullable=False, server_default="private"),
        _ts("published_at"),
        sa.Column("published_by", sa.Text()),
        sa.Column("created_by", sa.Text(), nullable=False),
        _ts("created_at", nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_model_version"),
        _tenant_fk("model_version"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_model_version_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "model_id", "version", name="uq_model_version_number"),
        sa.UniqueConstraint("tenant_id", "prov_node_id", name="uq_model_version_prov_node"),
        sa.UniqueConstraint(
            "tenant_id", "derived_object_id", name="uq_model_version_derived_object"
        ),
        _fk("model_version", ["model_id"], "model", "model"),
        _fk("model_version", ["derived_object_id"], "derived_object", "derived_object"),
        _fk("model_version", ["prov_node_id"], "prov_node", "prov_node"),
        _fk("model_version", ["parent_version_id"], "model_version", "parent"),
        sa.CheckConstraint("version >= 1", name="ck_model_version_version"),
        sa.CheckConstraint(
            "weights_sha256 ~ '^[0-9a-f]{64}$'", name="ck_model_version_weights_sha256"
        ),
        sa.CheckConstraint(
            "manifest_sha256 ~ '^[0-9a-f]{64}$'", name="ck_model_version_manifest_sha256"
        ),
        sa.CheckConstraint("code_commit ~ '^[0-9a-f]{7,64}$'", name="ck_model_version_code_commit"),
        sa.CheckConstraint(
            _in("visibility", ("private", "published")), name="ck_model_version_visibility"
        ),
    )
    op.create_table(
        "model_approval",
        _uuid("tenant_id", nullable=False),
        _uuid("version_id", nullable=False),
        sa.Column("approver_id", sa.Text(), nullable=False),
        sa.Column("approver_roles", pg.ARRAY(sa.Text()), nullable=False),
        _ts("created_at", nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("tenant_id", "version_id", "approver_id", name="pk_model_approval"),
        _tenant_fk("model_approval"),
        _fk("model_approval", ["version_id"], "model_version", "version"),
    )
    op.create_table(
        "model_use_exception",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        _uuid("model_id", nullable=False),
        sa.Column("basis", sa.Text(), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column("setting", sa.Text(), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("evidence_ref", sa.Text(), nullable=False),
        sa.Column("recorded_by", sa.Text(), nullable=False),
        _ts("created_at", nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_model_use_exception"),
        _tenant_fk("model_use_exception"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_model_use_exception_tenant_id_id"),
        _fk("model_use_exception", ["model_id"], "model", "model"),
        sa.CheckConstraint(
            _in("basis", ("medical", "safety")), name="ck_model_use_exception_basis"
        ),
    )
    op.create_table(
        "model_deployment",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        _uuid("model_id", nullable=False),
        _uuid("version_id", nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column("setting", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("context", pg.JSONB(), nullable=False),
        _uuid("exception_id"),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("reasons", pg.ARRAY(sa.Text()), nullable=False),
        sa.Column("requested_by", sa.Text(), nullable=False),
        _ts("created_at", nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_model_deployment"),
        _tenant_fk("model_deployment"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_model_deployment_tenant_id_id"),
        _fk("model_deployment", ["model_id"], "model", "model"),
        _fk("model_deployment", ["version_id"], "model_version", "version"),
        _fk("model_deployment", ["exception_id"], "model_use_exception", "exception"),
        sa.CheckConstraint(_in("state", ("approved", "refused")), name="ck_model_deployment_state"),
    )
    op.create_table(
        "model_retrain",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        _uuid("version_id", nullable=False),
        _uuid("job_id"),
        sa.Column("state", sa.Text(), nullable=False, server_default="queued"),
        _uuid("new_version_id"),
        sa.Column("excluded_subject_hashes", pg.ARRAY(sa.Text()), nullable=False),
        sa.Column("input_node_ids", pg.ARRAY(pg.UUID(as_uuid=True)), nullable=False),
        sa.Column("requested_by", sa.Text(), nullable=False),
        _ts("requested_at", nullable=False, server_default=sa.func.now()),
        _ts("finished_at"),
        sa.Column("error", sa.Text()),
        sa.PrimaryKeyConstraint("id", name="pk_model_retrain"),
        _tenant_fk("model_retrain"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_model_retrain_tenant_id_id"),
        _fk("model_retrain", ["version_id"], "model_version", "version"),
        _fk("model_retrain", ["new_version_id"], "model_version", "new_version"),
        _fk("model_retrain", ["job_id"], "job", "job"),
        sa.CheckConstraint(
            _in("state", ("queued", "running", "succeeded", "failed", "external")),
            name="ck_model_retrain_state",
        ),
    )
    mutable = [t for t in NEW_TABLES if t not in APPEND_ONLY]
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON {', '.join(mutable)} TO {APP}")
    op.execute(f"GRANT SELECT, INSERT ON {', '.join(APPEND_ONLY)} TO {APP}")
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
