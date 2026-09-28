"""SEC-034a (M2-REVIEW F1, extra hardening): database-level guard against re-creating a subject key
after a crypto-shred.

The application already refuses to mint a DEK for a tombstoned subject (``Keyring._active`` asks
``KeyStore.is_shredded``). That check and the INSERT of a new key are two statements, so another
process can shred the subject in between (time-of-check to time-of-use). This migration closes the
window in the database:

- ``nf_subject_key_lock(tenant, subject)`` takes a transaction-scoped advisory lock for one subject.
  Every INSERT into ``subject_key`` (trigger) and every shred (``SqlKeyStore.delete_subject``, which
  calls it before its UPDATE) takes it, so a shred and a key creation for the same subject are
  serialised.
- BEFORE INSERT: after taking the lock, an INSERT of a non-shredded row is rejected (SQLSTATE
  ``NF34A``) when a ``shredded`` row exists for (tenant_id, subject_id). Under READ COMMITTED each
  statement in the trigger function takes a fresh snapshot, so a tombstone committed while the
  INSERT waited for the lock is seen.
- BEFORE UPDATE: a ``shredded`` row can never become non-shredded or get key material back
  (``NF34A``). This also stops a concurrent "retire" UPDATE, which re-writes ``wrapped_dek``, from
  resurrecting a key it read before the shred. A restore from a pre-shred backup is a physical
  restore (or runs with ``session_replication_role = replica``, superuser only), and the restore
  procedure re-applies the WORM shred ledger (SEC-124).

Revision ID: 0012m6_key_tombstone
Revises: 0011m6_sisa
Create Date: 2026-09-26
"""

from __future__ import annotations

from alembic import op

revision = "0012m6_key_tombstone"
down_revision = "0011m6_sisa"
branch_labels = None
depends_on = None

SQLSTATE = "NF34A"


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION nf_subject_key_lock(p_tenant uuid, p_subject uuid) RETURNS void
        LANGUAGE plpgsql AS $$
        BEGIN
            PERFORM pg_advisory_xact_lock(
                hashtextextended('nf.subject_key/' || p_tenant::text || '/' || p_subject::text, 0)
            );
        END $$
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION nf_subject_key_tombstone_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                IF OLD.state = 'shredded'
                   AND (NEW.state <> 'shredded' OR NEW.wrapped_dek IS NOT NULL) THEN
                    RAISE EXCEPTION USING
                        ERRCODE = '{SQLSTATE}',
                        MESSAGE = 'SEC-034a: subject key is crypto-shredded and cannot be restored';
                END IF;
                IF NEW.state = 'shredded' AND OLD.state <> 'shredded' THEN
                    PERFORM nf_subject_key_lock(NEW.tenant_id, NEW.subject_id);
                END IF;
                RETURN NEW;
            END IF;
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
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER subject_key_tombstone_guard BEFORE INSERT OR UPDATE ON subject_key "
        "FOR EACH ROW EXECUTE FUNCTION nf_subject_key_tombstone_guard()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER subject_key_tombstone_guard ON subject_key")
    op.execute("DROP FUNCTION nf_subject_key_tombstone_guard()")
    op.execute("DROP FUNCTION nf_subject_key_lock(uuid, uuid)")
