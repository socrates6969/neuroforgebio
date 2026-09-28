"""M4 public API (4.6, 4.8): tenant_quota, webhook_endpoint, webhook_key, webhook_delivery.

- ``tenant_quota``: per-tenant quota overrides (SEC-075). The API role may only READ it; quotas are
  set by provisioning (superuser / migration tooling), never through the API.
- ``webhook_endpoint`` / ``webhook_key`` / ``webhook_delivery``: signed webhooks (SEC-045). Signing
  keys are stored AES-GCM-encrypted (``key_ciphertext``), never in plaintext.
- Role ``nf_webhook`` (NOLOGIN, NOBYPASSRLS): the delivery dispatcher's claim path. Like
  ``nf_worker`` on ``job`` it sees ``webhook_delivery`` rows of every tenant (SELECT, UPDATE of the
  lease column) and nothing else; delivering happens in the tenant's own session.

Tenant isolation: forced RLS with the tenant policy of 0001 on every new table (SEC-021).

Revision ID: 0010m4_quotas_webhooks
Revises: 0009m5_phi
Create Date: 2026-09-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0010m4_quotas_webhooks"
down_revision = "0009m5_phi"
branch_labels = None
depends_on = None

APP = "nf_app"
WEBHOOK = "nf_webhook"
NEW_TABLES = ("tenant_quota", "webhook_endpoint", "webhook_key", "webhook_delivery")


def _uuid(name: str, **kw) -> sa.Column:
    return sa.Column(name, pg.UUID(as_uuid=True), **kw)


def _ts(name: str, **kw) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), **kw)


def _tenant_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["tenant_id"], ["tenant.id"], name=f"fk_{table}_tenant_id_tenant", ondelete="RESTRICT"
    )


def _endpoint_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["tenant_id", "endpoint_id"],
        ["webhook_endpoint.tenant_id", "webhook_endpoint.id"],
        name=f"fk_{table}_endpoint",
        ondelete="CASCADE",
    )


def upgrade() -> None:
    op.create_table(
        "tenant_quota",
        _uuid("tenant_id", nullable=False),
        sa.Column("max_storage_bytes", sa.BigInteger()),
        sa.Column("max_active_runs", sa.Integer()),
        _ts("updated_at", nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("tenant_id", name="pk_tenant_quota"),
        _tenant_fk("tenant_quota"),
        sa.CheckConstraint(
            "(max_storage_bytes IS NULL OR max_storage_bytes >= 0) AND "
            "(max_active_runs IS NULL OR max_active_runs >= 0)",
            name="ck_tenant_quota_limits",
        ),
    )
    op.create_table(
        "webhook_endpoint",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("event_types", pg.ARRAY(sa.Text()), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        _ts("created_at", nullable=False, server_default=sa.func.now()),
        _ts("disabled_at"),
        sa.PrimaryKeyConstraint("id", name="pk_webhook_endpoint"),
        _tenant_fk("webhook_endpoint"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_webhook_endpoint_tenant_id_id"),
        sa.CheckConstraint("url LIKE 'https://%'", name="ck_webhook_endpoint_https"),
        sa.CheckConstraint("cardinality(event_types) >= 1", name="ck_webhook_endpoint_event_types"),
    )
    op.create_table(
        "webhook_key",
        _uuid("tenant_id", nullable=False),
        _uuid("endpoint_id", nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("key_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("wrap_version", sa.Text(), nullable=False),
        _ts("created_at", nullable=False, server_default=sa.func.now()),
        _ts("expires_at"),
        sa.PrimaryKeyConstraint("tenant_id", "endpoint_id", "version", name="pk_webhook_key"),
        _tenant_fk("webhook_key"),
        _endpoint_fk("webhook_key"),
        sa.CheckConstraint("version >= 1", name="ck_webhook_key_version"),
    )
    op.create_table(
        "webhook_delivery",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        _uuid("endpoint_id", nullable=False),
        _uuid("event_id", nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload", pg.JSONB(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        _ts("next_attempt_at", nullable=False, server_default=sa.func.now()),
        sa.Column("last_status", sa.Integer()),
        sa.Column("last_error", sa.Text()),
        _ts("created_at", nullable=False, server_default=sa.func.now()),
        _ts("delivered_at"),
        sa.PrimaryKeyConstraint("id", name="pk_webhook_delivery"),
        _tenant_fk("webhook_delivery"),
        _endpoint_fk("webhook_delivery"),
        sa.UniqueConstraint(
            "tenant_id", "endpoint_id", "event_id", name="uq_webhook_delivery_event"
        ),
        sa.CheckConstraint(
            "state IN ('pending', 'delivered', 'failed')", name="ck_webhook_delivery_state"
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_webhook_delivery_attempts"),
    )
    op.create_index("ix_webhook_delivery_due", "webhook_delivery", ["state", "next_attempt_at"])

    # ---------------------------------------------------------------- grants + RLS (SEC-021)
    op.execute(f"GRANT SELECT ON tenant_quota TO {APP}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON webhook_endpoint TO {APP}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON webhook_key, webhook_delivery TO {APP}")
    for t in NEW_TABLES:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {t} TO {APP} "
            "USING (tenant_id = nf_current_tenant()) WITH CHECK (tenant_id = nf_current_tenant())"
        )
    # The dispatcher's claim path: nf_webhook sees due deliveries of every tenant, nothing else.
    op.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nf_webhook') "
        f"THEN CREATE ROLE {WEBHOOK} NOLOGIN NOSUPERUSER NOBYPASSRLS; END IF; END $$"
    )
    op.execute(f"GRANT USAGE ON SCHEMA public TO {WEBHOOK}")
    op.execute(f"GRANT SELECT, UPDATE (next_attempt_at) ON webhook_delivery TO {WEBHOOK}")
    op.execute(
        f"CREATE POLICY webhook_claim ON webhook_delivery TO {WEBHOOK} "
        "USING (true) WITH CHECK (true)"
    )


def downgrade() -> None:
    for t in reversed(NEW_TABLES):
        op.drop_table(t)
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {WEBHOOK}")
