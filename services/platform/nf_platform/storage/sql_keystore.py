"""KeyStore backed by m2-core's `subject_key` table (Postgres, RLS per tenant).

`session_for(tenant_id)` must return a context manager yielding a tenant-scoped SQLAlchemy
Session (e.g. `nf_platform.db.context.tenant_session` for a service principal of that tenant), so
RLS and the app-level tenant filter apply to every key operation (SEC-021).

Crypto-shred keeps a tombstone row: `wrapped_dek = NULL`, `state = 'shredded'`, `shredded_at`
set. The wrapped DEK bytes are gone from the live table; database backups taken before the shred
still hold them until they expire (documented D4 caveat; SEC-034).

SEC-034a database guard (migrations ``0012m6_key_tombstone``, ``0014m6_key_shred_freeze``): a
trigger rejects (SQLSTATE ``NF34A``) any INSERT of a live key for a subject that has a
``shredded`` row, and any UPDATE that changes a shredded row (un-shred, counter, key metadata).
Shred and key creation for one subject are serialised by a transaction-scoped advisory lock
(``nf_subject_key_lock``): the INSERT trigger takes it, and
``delete_subject`` takes it BEFORE its UPDATE, so the UPDATE's snapshot sees every key committed
before the lock was granted. A subject that never had a key still gets a tombstone row
(``dek_version`` 0, no key material). ``NF34A`` surfaces as ``SubjectKeyUnavailable``.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import UTC, datetime

from sqlalchemy import exists, func, insert, literal, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from nf_platform.db.models import Subject, SubjectKey
from nf_platform.storage.keyring import SubjectKeyUnavailable, WrappedDek

SessionFor = Callable[[str], AbstractContextManager[Session]]

TOMBSTONE_SQLSTATE = "NF34A"  # raised by the subject_key tombstone trigger (0012m6_key_tombstone)
TOMBSTONE_DEK_VERSION = 0  # tombstone row for a subject shredded before it ever had a key


@contextmanager
def _tombstone_errors() -> Iterator[None]:
    """Map the database tombstone guard (SQLSTATE NF34A) to ``SubjectKeyUnavailable``."""
    try:
        yield
    except DBAPIError as e:
        if getattr(e.orig, "sqlstate", None) == TOMBSTONE_SQLSTATE:
            raise SubjectKeyUnavailable(
                "subject is crypto-shredded; the database refused the key (SEC-034a)"
            ) from e
        raise


def _u(v: str) -> uuid.UUID:
    return uuid.UUID(str(v))


def _to_rec(row: SubjectKey) -> WrappedDek:
    return WrappedDek(
        tenant_id=str(row.tenant_id),
        subject_id=str(row.subject_id),
        dek_version=row.dek_version,
        kek_id=row.kek_id,
        kek_version=row.kek_version,
        wrapped=bytes(row.wrapped_dek or b""),
        alg=row.alg,
        state=row.state,
        encryption_count=int(row.encryption_count),
        created_at=row.created_at,
    )


class SqlKeyStore:
    def __init__(self, session_for: SessionFor) -> None:
        self._session_for = session_for

    def get_wrapped(
        self, tenant_id: str, subject_id: str, dek_version: int | None = None
    ) -> WrappedDek | None:
        with self._session_for(tenant_id) as s:
            q = select(SubjectKey).where(
                SubjectKey.tenant_id == _u(tenant_id), SubjectKey.subject_id == _u(subject_id)
            )
            if dek_version is not None:
                row = s.scalars(q.where(SubjectKey.dek_version == dek_version)).first()
            else:
                row = s.scalars(
                    q.where(SubjectKey.state == "active").order_by(SubjectKey.dek_version.desc())
                ).first()
            if row is None or row.state == "shredded" or row.wrapped_dek is None:
                return None
            return _to_rec(row)

    def put_wrapped(self, rec: WrappedDek) -> None:
        with _tombstone_errors(), self._session_for(rec.tenant_id) as s:
            row = s.get(SubjectKey, (_u(rec.tenant_id), _u(rec.subject_id), rec.dek_version))
            if row is None:
                row = SubjectKey(
                    tenant_id=_u(rec.tenant_id),
                    subject_id=_u(rec.subject_id),
                    dek_version=rec.dek_version,
                )
                s.add(row)
            row.kek_id = rec.kek_id
            row.kek_version = rec.kek_version
            row.wrapped_dek = rec.wrapped
            row.alg = rec.alg
            row.state = rec.state
            row.encryption_count = rec.encryption_count

    def list_wrapped(self, tenant_id: str, subject_id: str) -> list[WrappedDek]:
        with self._session_for(tenant_id) as s:
            rows = s.scalars(
                select(SubjectKey)
                .where(
                    SubjectKey.tenant_id == _u(tenant_id),
                    SubjectKey.subject_id == _u(subject_id),
                )
                .order_by(SubjectKey.dek_version)
            ).all()
            return [_to_rec(r) for r in rows]

    def list_tenant(self, tenant_id: str) -> list[WrappedDek]:
        with self._session_for(tenant_id) as s:
            rows = s.scalars(
                select(SubjectKey).where(
                    SubjectKey.tenant_id == _u(tenant_id), SubjectKey.state != "shredded"
                )
            ).all()
            return [_to_rec(r) for r in rows]

    def is_shredded(self, tenant_id: str, subject_id: str) -> bool:
        """SEC-034a: a tombstone row exists (the subject was crypto-shredded)."""
        with self._session_for(tenant_id) as s:
            row = s.scalar(
                select(SubjectKey.dek_version)
                .where(
                    SubjectKey.tenant_id == _u(tenant_id),
                    SubjectKey.subject_id == _u(subject_id),
                    SubjectKey.state == "shredded",
                )
                .limit(1)
            )
            return row is not None

    def delete_subject(self, tenant_id: str, subject_id: str) -> int:
        t, sub = _u(tenant_id), _u(subject_id)
        now = datetime.now(UTC)
        with self._session_for(tenant_id) as s:
            # Lock first (own statement), so the UPDATE below sees keys committed by a concurrent
            # creator that held the lock; a creator that comes later waits and sees the tombstone.
            s.execute(select(func.nf_subject_key_lock(t, sub)))
            res = s.execute(
                update(SubjectKey)
                .where(
                    SubjectKey.tenant_id == t,
                    SubjectKey.subject_id == sub,
                    SubjectKey.state != "shredded",
                )
                .values(wrapped_dek=None, state="shredded", shredded_at=now)
            )
            n = int(res.rowcount or 0)
            if n == 0:
                # Never had a key (or already shredded): make sure a tombstone row exists, so a
                # later INSERT is refused by the database too. Needs the subject row (FK).
                tomb = exists().where(
                    SubjectKey.tenant_id == t,
                    SubjectKey.subject_id == sub,
                    SubjectKey.state == "shredded",
                )
                s.execute(
                    insert(SubjectKey).from_select(
                        [
                            "tenant_id",
                            "subject_id",
                            "dek_version",
                            "kek_id",
                            "kek_version",
                            "state",
                            "shredded_at",
                        ],
                        select(
                            Subject.tenant_id,
                            Subject.id,
                            literal(TOMBSTONE_DEK_VERSION),
                            literal("tombstone"),
                            literal(0),
                            literal("shredded"),
                            literal(now),
                        ).where(Subject.tenant_id == t, Subject.id == sub, ~tomb),
                    )
                )
            return n

    def bump_count(self, tenant_id: str, subject_id: str, dek_version: int, n: int = 1) -> int:
        # Two guards (BUG-HUNT M4): the filter below, and the trigger (0014m6_key_shred_freeze),
        # which refuses any change to a shredded row with NF34A -> SubjectKeyUnavailable.
        with _tombstone_errors(), self._session_for(tenant_id) as s:
            res = s.execute(
                update(SubjectKey)
                .where(
                    SubjectKey.tenant_id == _u(tenant_id),
                    SubjectKey.subject_id == _u(subject_id),
                    SubjectKey.dek_version == dek_version,
                    SubjectKey.state != "shredded",
                )
                .values(encryption_count=SubjectKey.encryption_count + n)
                .returning(SubjectKey.encryption_count)
            )
            count = res.scalar_one_or_none()
            if count is None:
                # shredded between reading the key and counting this encryption (SEC-034a race)
                raise SubjectKeyUnavailable("subject key was crypto-shredded; encryption refused")
            return int(count)
