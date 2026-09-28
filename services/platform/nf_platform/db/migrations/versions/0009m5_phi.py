"""M5 5.7: ``tenant.phi`` flag (BAA-readiness pack; BLUEPRINT §8.5).

A tenant with ``phi = true`` may only be placed on BAA-listed services (``nf_platform.placement``,
``infra/policy/phi-services.json``). Default false: existing tenants are unchanged. The tenant
table keeps its RLS policy from 0001.

Revision ID: 0009m5_phi
Revises: 0008_merge_sweeps_m5
Create Date: 2026-09-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009m5_phi"
down_revision = "0008_merge_sweeps_m5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenant", sa.Column("phi", sa.Boolean(), nullable=False, server_default="false"))


def downgrade() -> None:
    op.drop_column("tenant", "phi")
