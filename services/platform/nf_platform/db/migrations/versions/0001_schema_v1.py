"""Schema v1: tenant → project → dataset → subject → session → recording → channel/segment, key and
object metadata, API keys, audit log; roles, RLS (ENABLE + FORCE) on every table.

Revision ID: 0001
Revises:
Create Date: 2026-09-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

APP, AUDIT, AUTH = "nf_app", "nf_audit", "nf_auth"

MODALITIES = (
    "EEG",
    "iEEG",
    "ECoG",
    "SEEG",
    "LFP",
    "spikes",
    "MEG",
    "EMG",
    "ENG",
    "EOG",
    "ECG",
    "fNIRS",
    "other",
)


def _in(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


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


# Tables whose rows belong to one tenant via tenant_id and that the app role reads/writes.
APP_RW = (
    "project",
    "dataset",
    "subject",
    "session",
    "recording",
    "channel",
    "segment",
    "tenant_key",
    "subject_key",
    "stored_object",
)


def upgrade() -> None:
    # ---------------------------------------------------------------- roles (cluster-wide; kept on
    # downgrade)
    for role in (APP, AUDIT, AUTH):
        op.execute(
            f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') "
            f"THEN CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS; END IF; END $$"
        )
    op.execute(f"GRANT USAGE ON SCHEMA public TO {APP}, {AUDIT}, {AUTH}")

    # Tenant of the current transaction; NULL (no rows) when app.tenant_id is unset: fail closed.
    op.execute(
        "CREATE FUNCTION nf_current_tenant() RETURNS uuid LANGUAGE sql STABLE AS "
        "$$ SELECT NULLIF(current_setting('app.tenant_id', true), '')::uuid $$"
    )
    op.execute(
        "CREATE FUNCTION nf_append_only() RETURNS trigger LANGUAGE plpgsql AS "
        "$$ BEGIN RAISE EXCEPTION 'table % is append-only', TG_TABLE_NAME; END $$"
    )

    # ---------------------------------------------------------------- metadata hierarchy
    op.create_table(
        "tenant",
        _uuid("id", nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        _created(),
        sa.PrimaryKeyConstraint("id", name="pk_tenant"),
    )
    op.create_table(
        "project",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("created_by", sa.Text(), nullable=False),
        _created(),
        sa.PrimaryKeyConstraint("id", name="pk_project"),
        _tenant_fk("project"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_project_tenant_id_id"),
    )
    op.create_table(
        "dataset",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        _uuid("project_id", nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("created_by", sa.Text(), nullable=False),
        _created(),
        sa.PrimaryKeyConstraint("id", name="pk_dataset"),
        _tenant_fk("dataset"),
        _parent_fk("dataset", "project", "project_id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_dataset_tenant_id_id"),
    )
    op.create_table(
        "subject",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        _uuid("dataset_id", nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        _created(),
        sa.PrimaryKeyConstraint("id", name="pk_subject"),
        _tenant_fk("subject"),
        _parent_fk("subject", "dataset", "dataset_id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_subject_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "dataset_id", "label", name="uq_subject_dataset_label"),
    )
    op.create_table(
        "session",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        _uuid("subject_id", nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        _ts("started_at"),
        sa.Column("created_by", sa.Text(), nullable=False),
        _created(),
        sa.PrimaryKeyConstraint("id", name="pk_session"),
        _tenant_fk("session"),
        _parent_fk("session", "subject", "subject_id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_session_tenant_id_id"),
    )
    op.create_table(
        "recording",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        _uuid("session_id", nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("source_format", sa.Text()),
        sa.Column("state", sa.Text(), nullable=False, server_default="active"),
        sa.Column("duration_s", sa.Double()),
        sa.Column("created_by", sa.Text(), nullable=False),
        _created(),
        sa.PrimaryKeyConstraint("id", name="pk_recording"),
        _tenant_fk("recording"),
        _parent_fk("recording", "session", "session_id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_recording_tenant_id_id"),
        sa.CheckConstraint(_in("state", ("active", "quarantined")), name="ck_recording_state"),
    )
    op.create_table(
        "channel",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        _uuid("recording_id", nullable=False),
        sa.Column("index", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("modality", sa.Text(), nullable=False),
        sa.Column("nervous_system", sa.Text(), nullable=False, server_default="unknown"),
        sa.Column("derived_from_non_neural", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("sampling_rate", sa.Double(), nullable=False),
        sa.Column("units", sa.Text(), nullable=False),
        sa.Column("device_ref", sa.Text()),
        sa.PrimaryKeyConstraint("id", name="pk_channel"),
        _tenant_fk("channel"),
        _parent_fk("channel", "recording", "recording_id", ondelete="CASCADE"),
        sa.UniqueConstraint(
            "tenant_id", "recording_id", "index", name="uq_channel_recording_index"
        ),
        sa.CheckConstraint(_in("modality", MODALITIES), name="ck_channel_modality"),
        sa.CheckConstraint(
            _in("nervous_system", ("central", "peripheral", "unknown")),
            name="ck_channel_nervous_system",
        ),
        sa.CheckConstraint("sampling_rate > 0", name="ck_channel_sampling_rate"),
        sa.CheckConstraint('"index" >= 0', name="ck_channel_index"),
    )
    op.create_table(
        "segment",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        _uuid("recording_id", nullable=False),
        sa.Column("start_s", sa.Double(), nullable=False),
        sa.Column("end_s", sa.Double(), nullable=False),
        sa.Column("zarr_ref", sa.Text()),
        _created(),
        sa.PrimaryKeyConstraint("id", name="pk_segment"),
        _tenant_fk("segment"),
        _parent_fk("segment", "recording", "recording_id", ondelete="CASCADE"),
        sa.CheckConstraint("start_s >= 0 AND end_s > start_s", name="ck_segment_range"),
    )

    # ---------------------------------------------------------------- keys and objects (2.3)
    op.create_table(
        "tenant_key",
        _uuid("tenant_id", nullable=False),
        sa.Column("kek_version", sa.Integer(), nullable=False),
        sa.Column("kek_id", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False, server_default="active"),
        _created(),
        _ts("rotated_at"),
        sa.PrimaryKeyConstraint("tenant_id", "kek_version", name="pk_tenant_key"),
        _tenant_fk("tenant_key"),
        sa.CheckConstraint(
            _in("state", ("active", "retired", "disabled")), name="ck_tenant_key_state"
        ),
    )
    op.create_table(
        "subject_key",
        _uuid("tenant_id", nullable=False),
        _uuid("subject_id", nullable=False),
        sa.Column("dek_version", sa.Integer(), nullable=False),
        sa.Column("kek_id", sa.Text(), nullable=False),
        sa.Column("kek_version", sa.Integer(), nullable=False),
        sa.Column("wrapped_dek", sa.LargeBinary()),
        sa.Column("alg", sa.Text(), nullable=False, server_default="AES-256-GCM"),
        sa.Column("encryption_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("state", sa.Text(), nullable=False, server_default="active"),
        _created(),
        _ts("shredded_at"),
        sa.PrimaryKeyConstraint("tenant_id", "subject_id", "dek_version", name="pk_subject_key"),
        _tenant_fk("subject_key"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "subject_id"],
            ["subject.tenant_id", "subject.id"],
            name="fk_subject_key_subject",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            _in("state", ("active", "retired", "shredded")), name="ck_subject_key_state"
        ),
        sa.CheckConstraint(
            "(state = 'shredded') OR (wrapped_dek IS NOT NULL)",
            name="ck_subject_key_wrapped_unless_shredded",
        ),
    )
    op.create_table(
        "stored_object",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        _uuid("subject_id"),
        sa.Column("bucket", sa.Text(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("object_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("ciphertext_size", sa.BigInteger(), nullable=False),
        sa.Column("dek_version", sa.Integer()),
        sa.Column("kek_id", sa.Text()),
        sa.Column("kek_version", sa.Integer()),
        sa.Column("alg", sa.Text(), nullable=False, server_default="AES-256-GCM"),
        sa.Column("content_type", sa.Text()),
        _created(),
        sa.PrimaryKeyConstraint("id", name="pk_stored_object"),
        _tenant_fk("stored_object"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "subject_id"],
            ["subject.tenant_id", "subject.id"],
            name="fk_stored_object_subject",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "tenant_id", "bucket", "object_key", "object_version", name="uq_stored_object_key"
        ),
        sa.CheckConstraint(
            _in("bucket", ("raw", "zarr", "artifacts", "models", "audit")),
            name="ck_stored_object_bucket",
        ),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_stored_object_sha256"),
    )

    # ---------------------------------------------------------------- API keys (2.2, SEC-014)
    op.create_table(
        "api_key",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        sa.Column("public_id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("key_hash", sa.LargeBinary(), nullable=False),
        sa.Column("pepper_version", sa.Text(), nullable=False),
        sa.Column("roles", pg.ARRAY(sa.Text()), nullable=False),
        sa.Column("scopes", pg.ARRAY(sa.Text()), nullable=False),
        _created(),
        _ts("expires_at", nullable=False),
        _ts("revoked_at"),
        sa.PrimaryKeyConstraint("id", name="pk_api_key"),
        _tenant_fk("api_key"),
        sa.UniqueConstraint("public_id", name="uq_api_key_public_id"),
        sa.CheckConstraint("octet_length(key_hash) = 32", name="ck_api_key_key_hash_len"),
        sa.CheckConstraint("expires_at > created_at", name="ck_api_key_expiry"),
    )

    # ---------------------------------------------------------------- audit (2.8)
    op.create_table(
        "audit_event",
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        _uuid("id", nullable=False),
        _ts("ts", nullable=False, server_default=sa.func.now()),
        _uuid("tenant_id"),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("action", sa.Text()),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("actor_kind", sa.Text()),
        sa.Column("actor_id", sa.Text()),
        sa.Column("auth_method", sa.Text()),
        sa.Column("resource_type", sa.Text()),
        sa.Column("resource_id", sa.Text()),
        sa.Column("request_id", sa.Text()),
        sa.Column("details", pg.JSONB(), nullable=False, server_default="{}"),
        sa.PrimaryKeyConstraint("seq", name="pk_audit_event"),
        sa.UniqueConstraint("id", name="uq_audit_event_id"),
    )
    op.create_table(
        "audit_batch",
        sa.Column("tenant_scope", sa.Text(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Text(), nullable=False),
        sa.Column("prev_id", sa.Text()),
        _ts("period_start", nullable=False),
        _ts("period_end", nullable=False),
        sa.Column("first_event_seq", sa.BigInteger()),
        sa.Column("last_event_seq", sa.BigInteger()),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        _created(),
        sa.PrimaryKeyConstraint("tenant_scope", "seq", name="pk_audit_batch"),
        sa.UniqueConstraint("batch_id", name="uq_audit_batch_batch_id"),
    )
    for t in ("audit_event", "audit_batch"):
        op.execute(
            f"CREATE TRIGGER {t}_append_only BEFORE UPDATE OR DELETE ON {t} "
            "FOR EACH ROW EXECUTE FUNCTION nf_append_only()"
        )
        op.execute(
            f"CREATE TRIGGER {t}_no_truncate BEFORE TRUNCATE ON {t} "
            "FOR EACH STATEMENT EXECUTE FUNCTION nf_append_only()"
        )

    # ---------------------------------------------------------------- grants (least privilege)
    op.execute(f"GRANT SELECT ON tenant TO {APP}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {', '.join(APP_RW)} TO {APP}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON api_key TO {APP}")
    op.execute(f"GRANT SELECT ON audit_event, audit_batch TO {APP}")
    op.execute(f"GRANT SELECT, INSERT ON audit_event, audit_batch TO {AUDIT}")
    op.execute(f"GRANT SELECT ON api_key TO {AUTH}")

    # ---------------------------------------------------------------- row-level security (SEC-021)
    for t in ("tenant", *APP_RW, "api_key", "audit_event", "audit_batch"):
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON tenant TO {APP} USING (id = nf_current_tenant())"
    )
    for t in (*APP_RW, "api_key"):
        op.execute(
            f"CREATE POLICY tenant_isolation ON {t} TO {APP} "
            "USING (tenant_id = nf_current_tenant()) WITH CHECK (tenant_id = nf_current_tenant())"
        )
    # API-key lookup by public id happens before the tenant is known: read-only role, nothing else.
    op.execute(f"CREATE POLICY auth_lookup ON api_key FOR SELECT TO {AUTH} USING (true)")
    # Audit: the app reads its own tenant's events/batches (auditor export); the audit role writes
    # and batches.
    op.execute(
        f"CREATE POLICY tenant_read ON audit_event FOR SELECT TO {APP} "
        "USING (tenant_id = nf_current_tenant())"
    )
    op.execute(
        f"CREATE POLICY tenant_read ON audit_batch FOR SELECT TO {APP} "
        "USING (tenant_scope = nf_current_tenant()::text)"
    )
    for t in ("audit_event", "audit_batch"):
        op.execute(f"CREATE POLICY audit_write ON {t} FOR INSERT TO {AUDIT} WITH CHECK (true)")
        op.execute(f"CREATE POLICY audit_read ON {t} FOR SELECT TO {AUDIT} USING (true)")


def downgrade() -> None:
    for t in (
        "audit_batch",
        "audit_event",
        "api_key",
        "stored_object",
        "subject_key",
        "tenant_key",
        "segment",
        "channel",
        "recording",
        "session",
        "subject",
        "dataset",
        "project",
        "tenant",
    ):
        op.drop_table(t)
    op.execute("DROP FUNCTION nf_append_only()")
    op.execute("DROP FUNCTION nf_current_tenant()")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {APP}, {AUDIT}, {AUTH}")
    # Roles are cluster-wide (other databases may use them) and are deliberately not dropped.
