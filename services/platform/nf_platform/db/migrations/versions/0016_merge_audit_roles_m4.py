"""Merge the AppSec head (0015_audit_roles) and the M4/M6 join (0015_merge_m4_m6).

Both revise 0014m6_key_shred_freeze's line in parallel: AppSec M1-M3 split the audit role and
added the batch-continuity trigger; the M4/M6 join brought in the quotas, webhooks and
early-access tables. Neither set references the other, so the merge has no schema changes.

Revision ID: 0016_merge_audit_roles_m4
Revises: 0015_audit_roles, 0015_merge_m4_m6
Create Date: 2026-09-27
"""

from __future__ import annotations

revision = "0016_merge_audit_roles_m4"
down_revision = ("0015_audit_roles", "0015_merge_m4_m6")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
