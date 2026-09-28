"""M4 4.7 (OWNER-GATED): schema ``site`` with ``early_access_signup``, role ``nf_site``.

The early-access list is not tenant data, so it does not live in ``public`` (where every table is
tenant-scoped). Only the ``nf_site`` role (NOLOGIN, NOBYPASSRLS) can read or write it, through a
forced-RLS policy; ``nf_app``/``nf_auth``/``nf_audit``/``nf_worker`` have no grant on the schema.

The table exists regardless of the feature flag; the public route is mounted only when
``Settings.early_access_enabled`` is true (owner approval, BUILD-GUIDE 4.7).

Revision ID: 0011m4_early_access
Revises: 0010m4_quotas_webhooks
Create Date: 2026-09-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0011m4_early_access"
down_revision = "0010m4_quotas_webhooks"
branch_labels = None
depends_on = None

SITE = "nf_site"
ROLES = ("researcher", "engineer", "clinician", "founder", "student", "other")


def upgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nf_site') "
        f"THEN CREATE ROLE {SITE} NOLOGIN NOSUPERUSER NOBYPASSRLS; END IF; END $$"
    )
    op.execute("CREATE SCHEMA site")
    op.create_table(
        "early_access_signup",
        sa.Column("id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("organisation", sa.Text()),
        sa.Column("confirm_hash", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id", name="pk_early_access_signup"),
        sa.UniqueConstraint("email", name="uq_early_access_signup_email"),
        sa.UniqueConstraint("confirm_hash", name="uq_early_access_signup_confirm_hash"),
        sa.CheckConstraint(
            "role IN (" + ", ".join(f"'{r}'" for r in ROLES) + ")",
            name="ck_early_access_signup_role",
        ),
        sa.CheckConstraint(
            "octet_length(confirm_hash) = 32", name="ck_early_access_signup_confirm_hash_len"
        ),
        schema="site",
    )
    op.execute(f"GRANT USAGE ON SCHEMA site TO {SITE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON site.early_access_signup TO {SITE}")
    op.execute("ALTER TABLE site.early_access_signup ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE site.early_access_signup FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY site_only ON site.early_access_signup TO {SITE} "
        "USING (true) WITH CHECK (true)"
    )


def downgrade() -> None:
    op.drop_table("early_access_signup", schema="site")
    op.execute(f"REVOKE USAGE ON SCHEMA site FROM {SITE}")
    op.execute("DROP SCHEMA site")
