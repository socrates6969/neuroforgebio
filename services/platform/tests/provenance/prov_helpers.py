"""Helpers for m3-prov tests (imported as a module, not via ``conftest``)."""

from __future__ import annotations

import uuid


def principal(tenant_id: str, name: str = "svc:test"):
    from nf_platform.db.context import Principal

    return Principal(name, str(tenant_id), frozenset(), frozenset(), "service", False)


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()
