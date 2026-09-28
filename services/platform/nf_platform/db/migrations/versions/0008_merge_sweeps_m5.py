"""Merge the M3 sweeps head (0005_sweeps) and the M5 ledger head (0007m5_deletion).

Both branches started from 0004 in parallel (M3 wave B and M5 5.1-5.5). The two sets of tables do
not reference each other, so the merge has no schema changes.

Revision ID: 0008_merge_sweeps_m5
Revises: 0005_sweeps, 0007m5_deletion
Create Date: 2026-09-26
"""

from __future__ import annotations

revision = "0008_merge_sweeps_m5"
down_revision = ("0005_sweeps", "0007m5_deletion")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
