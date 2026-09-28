"""Per-tenant quotas (BUILD-GUIDE 4.8; SEC-075).

Two quotas, checked inside the caller's tenant transaction:

- **storage** (bytes): stored objects plus the declared size of uploads still in flight. Exceeding
  it is a 403 ``quota-exceeded`` (it does not clear by waiting; delete data or raise the quota).
- **active runs** (queued + running): exceeding it is a 429 ``quota-exceeded`` with ``Retry-After``
  (it clears as runs finish).

Limits come from the ``tenant_quota`` row (migration 0010m4; written by provisioning, read-only to
the API role) or, without a row, from :class:`~nf_platform.config.Settings`. A per-tenant advisory
transaction lock serialises concurrent checks so two requests cannot both squeeze under the limit.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from nf_platform.config import Settings
from nf_platform.db import models as m
from nf_platform.limits import LimitExceeded
from nf_platform.limits.ratelimit import retry_after_header

ACTIVE_RUN_STATES = ("queued", "running")
IN_FLIGHT_UPLOADS = ("open", "uploaded", "processing")


@dataclass(frozen=True)
class Limits:
    storage_bytes: int
    active_runs: int


@dataclass(frozen=True)
class Usage:
    storage_bytes: int
    active_runs: int


def limits_for(s: Session, tenant_id: uuid.UUID, settings: Settings) -> Limits:
    row = s.scalar(select(m.TenantQuota).where(m.TenantQuota.tenant_id == tenant_id))
    storage = row.max_storage_bytes if row and row.max_storage_bytes is not None else None
    runs = row.max_active_runs if row and row.max_active_runs is not None else None
    return Limits(
        storage_bytes=settings.quota_storage_bytes if storage is None else int(storage),
        active_runs=settings.quota_active_runs if runs is None else int(runs),
    )


def usage(s: Session, tenant_id: uuid.UUID) -> Usage:
    stored = s.scalar(
        select(func.coalesce(func.sum(m.StoredObject.size_bytes), 0)).where(
            m.StoredObject.tenant_id == tenant_id
        )
    )
    pending = s.scalar(
        select(func.coalesce(func.sum(m.Upload.size_bytes), 0)).where(
            m.Upload.tenant_id == tenant_id, m.Upload.state.in_(IN_FLIGHT_UPLOADS)
        )
    )
    runs = s.scalar(
        select(func.count())
        .select_from(m.Run)
        .where(m.Run.tenant_id == tenant_id, m.Run.state.in_(ACTIVE_RUN_STATES))
    )
    return Usage(storage_bytes=int(stored) + int(pending), active_runs=int(runs))


def _lock(s: Session, tenant_id: uuid.UUID) -> None:
    s.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"nf-quota:{tenant_id}"})


def check_storage(s: Session, tenant_id: uuid.UUID, add_bytes: int, settings: Settings) -> None:
    """Before accepting ``add_bytes`` more (an upload session): 403 when it would exceed."""
    _lock(s, tenant_id)
    lim = limits_for(s, tenant_id, settings)
    used = usage(s, tenant_id).storage_bytes
    if used + add_bytes > lim.storage_bytes:
        raise LimitExceeded(
            403,
            "The tenant's storage quota would be exceeded.",
            kind="quota-exceeded",
            extra={"quota": "storage_bytes", "limit": lim.storage_bytes, "used": used},
        )


def check_active_runs(s: Session, tenant_id: uuid.UUID, settings: Settings) -> None:
    """After queuing new runs in this transaction: 429 (the transaction rolls back) when the tenant
    now has more active runs than allowed."""
    _lock(s, tenant_id)
    s.flush()
    lim = limits_for(s, tenant_id, settings)
    active = usage(s, tenant_id).active_runs
    if active > lim.active_runs:
        raise LimitExceeded(
            429,
            "Too many active runs for this tenant; retry when some have finished.",
            kind="quota-exceeded",
            headers=retry_after_header(settings.quota_retry_after_s),
            extra={"quota": "active_runs", "limit": lim.active_runs},
        )
