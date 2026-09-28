"""6.3 (BUG-HUNT M2): at most one active retrain per model version, enforced by the database.

``registry.service.request_retrain`` checks for a queued/running retrain and then inserts one. Two
concurrent requests could both pass the check and queue two retrains (two jobs, two new versions
from one taint event). The partial unique index ``uq_model_retrain_active`` on
(tenant_id, version_id) WHERE state IN ('queued', 'running') (``models.RETRAIN_ACTIVE_STATES``)
lets exactly one in; the service inserts the row and its job inside one savepoint and maps the
loser's unique violation to the winner's retrain (the sequential answer), so no orphan job
remains.

Upgrade fails if a database already holds two active retrains for one version; resolve those by
hand first (none exist: M6 is not deployed).

Revision ID: 0013m6_retrain_active
Revises: 0012m6_key_tombstone
Create Date: 2026-09-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013m6_retrain_active"
down_revision = "0012m6_key_tombstone"
branch_labels = None
depends_on = None

INDEX = "uq_model_retrain_active"


def upgrade() -> None:
    op.create_index(
        INDEX,
        "model_retrain",
        ["tenant_id", "version_id"],
        unique=True,
        postgresql_where=sa.text("state IN ('queued', 'running')"),
    )


def downgrade() -> None:
    op.drop_index(INDEX, table_name="model_retrain")
