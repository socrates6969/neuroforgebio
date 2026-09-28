"""Merge the M4 API head (0011m4_early_access) and the M6 registry head (0014m6_key_shred_freeze).

Both branches started from 0009m5_phi in parallel (M4 quotas/webhooks/early access and the M6 model
registry). The two sets of tables do not reference each other, so the merge has no schema changes.

Revision ID: 0015_merge_m4_m6
Revises: 0011m4_early_access, 0014m6_key_shred_freeze
Create Date: 2026-09-27
"""

from __future__ import annotations

revision = "0015_merge_m4_m6"
down_revision = ("0011m4_early_access", "0014m6_key_shred_freeze")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
