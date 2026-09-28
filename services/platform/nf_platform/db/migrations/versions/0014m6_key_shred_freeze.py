"""SEC-034a (BUG-HUNT M4): a crypto-shredded ``subject_key`` row is frozen.

``0012m6_key_tombstone`` refused only UPDATEs that turn a shredded row back into a live key
(``state`` or ``wrapped_dek``). ``SqlKeyStore.bump_count`` changes neither, so its guard against
"encrypt read a live key, the subject was shredded, then the encryption is counted" was only its
own ``WHERE state <> 'shredded'`` filter. The trigger now rejects (SQLSTATE ``NF34A``) EVERY UPDATE
of a shredded row that changes anything; a no-op UPDATE still passes. The shred itself only
updates non-shredded rows, so it is unaffected. A restore from a pre-shred backup still runs in
replica mode (triggers off, superuser only) and re-applies the WORM shred ledger (SEC-124).

Revision ID: 0014m6_key_shred_freeze
Revises: 0013m6_retrain_active
Create Date: 2026-09-26
"""

from __future__ import annotations

from alembic import op

revision = "0014m6_key_shred_freeze"
down_revision = "0013m6_retrain_active"
branch_labels = None
depends_on = None

SQLSTATE = "NF34A"

_INSERT_BRANCH = f"""
            PERFORM nf_subject_key_lock(NEW.tenant_id, NEW.subject_id);
            IF NEW.state <> 'shredded' AND EXISTS (
                SELECT 1 FROM subject_key k
                WHERE k.tenant_id = NEW.tenant_id AND k.subject_id = NEW.subject_id
                  AND k.state = 'shredded'
            ) THEN
                RAISE EXCEPTION USING
                    ERRCODE = '{SQLSTATE}',
                    MESSAGE = 'SEC-034a: subject is crypto-shredded; no new key may be created';
            END IF;
            RETURN NEW;
"""


def _function(update_guard: str) -> str:
    return f"""
        CREATE OR REPLACE FUNCTION nf_subject_key_tombstone_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'UPDATE' THEN
{update_guard}
                IF NEW.state = 'shredded' AND OLD.state <> 'shredded' THEN
                    PERFORM nf_subject_key_lock(NEW.tenant_id, NEW.subject_id);
                END IF;
                RETURN NEW;
            END IF;
{_INSERT_BRANCH}
        END $$
        """


FROZEN = f"""
                IF OLD.state = 'shredded' AND NEW IS DISTINCT FROM OLD THEN
                    RAISE EXCEPTION USING
                        ERRCODE = '{SQLSTATE}',
                        MESSAGE = 'SEC-034a: subject key is crypto-shredded and cannot be changed';
                END IF;"""

UNSHRED_ONLY = f"""
                IF OLD.state = 'shredded'
                   AND (NEW.state <> 'shredded' OR NEW.wrapped_dek IS NOT NULL) THEN
                    RAISE EXCEPTION USING
                        ERRCODE = '{SQLSTATE}',
                        MESSAGE = 'SEC-034a: subject key is crypto-shredded and cannot be restored';
                END IF;"""


def upgrade() -> None:
    op.execute(_function(FROZEN))


def downgrade() -> None:
    op.execute(_function(UNSHRED_ONLY))  # the 0012m6_key_tombstone body
