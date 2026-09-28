"""Principal and tenant-scoped database sessions (M2-CONTRACTS §3).

Tenant isolation has two layers here (the third, per-tenant KMS keys, is in storage):

1. Postgres RLS: every transaction runs as the non-owner role ``nf_app`` with ``app.tenant_id`` set
   (transaction-local), so the policies of migration 0001 filter every table.
2. App level: every ORM SELECT gets ``tenant_id = <principal's tenant>`` added, and a flush that
would write a
   row of another tenant raises before it reaches the database.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, with_loader_criteria

from nf_platform.config import APP_DB_ROLE
from nf_platform.db.models import TenantScoped

PrincipalKind = Literal["user", "api_key", "device", "service"]


@dataclass(frozen=True)
class Principal:
    id: str
    tenant_id: str
    roles: frozenset[str]
    scopes: frozenset[str]
    kind: PrincipalKind
    mfa_phr: bool
    # Not part of the contract's positional fields: how the principal authenticated, for audit
    # ("oidc", "api_key").
    auth_method: str = field(default="oidc", compare=False)
    # API-key id (public id) when kind == "api_key"; never the secret.
    credential_id: str | None = field(default=None, compare=False)


class TenantViolation(RuntimeError):
    """An attempt to write a row that belongs to another tenant (app-level check, SEC-021 layer
    1)."""


_engine: Engine | None = None


def configure_engine(url_or_engine: str | Engine) -> Engine:
    """Set the process-wide engine used by :func:`tenant_session` (called by ``create_app``)."""
    global _engine
    if isinstance(url_or_engine, Engine):
        _engine = url_or_engine
    else:
        _engine = create_engine(url_or_engine, pool_pre_ping=True, pool_size=5, max_overflow=5)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("database engine not configured (call configure_engine)")
    return _engine


def _tenant_uuid(tenant_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(tenant_id))
    except ValueError as e:
        raise TenantViolation("tenant id is not a UUID") from e


@contextmanager
def role_session(role: str, *, engine: Engine | None = None) -> Iterator[Session]:
    """A transaction running as ``role`` (SET LOCAL ROLE) with no tenant set. Internal use (audit,
    auth)."""
    with Session(engine or get_engine()) as s, s.begin():
        s.execute(text(f"SET LOCAL ROLE {_checked_role(role)}"))
        yield s


def _checked_role(role: str) -> str:
    # AppSec M2: never the batcher role (nf_audit_batcher); only its own session may assume it.
    if role not in {"nf_app", "nf_audit_writer", "nf_auth", "nf_site", "nf_webhook"}:
        raise ValueError(f"unknown database role {role!r}")
    return role


@contextmanager
def tenant_session(principal: Principal, *, engine: Engine | None = None) -> Iterator[Session]:
    """One transaction scoped to ``principal.tenant_id`` (RLS + app filter). Commits on success."""
    tid = _tenant_uuid(principal.tenant_id)
    with Session(engine or get_engine()) as s:
        s.info["tenant_id"] = tid

        @event.listens_for(s, "do_orm_execute")
        def _filter(state) -> None:  # app-level tenant filter on every ORM SELECT
            if state.is_select:
                state.statement = state.statement.options(
                    with_loader_criteria(
                        TenantScoped, lambda cls: cls.tenant_id == tid, include_aliases=True
                    )
                )

        @event.listens_for(s, "before_flush")
        def _check(session, _ctx, _instances) -> None:
            for obj in list(session.new) + list(session.dirty):
                if isinstance(obj, TenantScoped) and obj.tenant_id != tid:
                    raise TenantViolation("row belongs to another tenant")

        with s.begin():
            s.execute(text(f"SET LOCAL ROLE {APP_DB_ROLE}"))
            s.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tid)})
            yield s
