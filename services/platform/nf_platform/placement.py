"""PHI placement guard (BUILD-GUIDE 5.7; BLUEPRINT §8.5; market/regulation.md §3).

A tenant with ``phi=true`` may only be placed on services listed as BAA-covered in
``infra/policy/phi-services.json`` (the same file the OpenTofu ``phi-guard`` module reads). The
deployment's placement (``Settings.placement``: which service holds storage, the database and
compute) is checked whenever PHI-tenant data would be written or processed (uploads, streams,
runs). Anything not listed, unknown or unreadable is a denial (fail closed).

This is a technical guard for a DRAFT readiness pack. No provider BAA is signed (owner action) and
nothing here claims HIPAA compliance.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from nf_platform.auth.authorize import Forbidden
from nf_platform.config import Placement
from nf_platform.db import models as m

SCHEMA = "nf.phi-services/v1"
ROLES = ("storage", "database", "compute")


class PlacementDenied(Forbidden):
    """A phi=true tenant would be placed on a service that is not BAA-listed (403)."""


@dataclass(frozen=True)
class PhiPolicy:
    covered: frozenset[str]
    catalog: dict[str, str]
    iac_modules: dict[str, tuple[str, ...]]


def default_path() -> Path:
    env = os.environ.get("NF_PHI_SERVICES_FILE")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3] / "infra" / "policy" / "phi-services.json"


def parse_policy(doc: Any) -> PhiPolicy:
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise ValueError(f"phi-services: schema must be {SCHEMA}")
    catalog = {str(k): str(v) for k, v in (doc.get("catalog") or {}).items()}
    covered = frozenset(str(s["id"]) for s in doc.get("baa_covered") or ())
    unknown = covered - catalog.keys()
    if unknown:
        raise ValueError(
            f"phi-services: listed services missing from the catalog: {sorted(unknown)}"
        )
    mods = {str(k): tuple(str(x) for x in v) for k, v in (doc.get("iac_modules") or {}).items()}
    return PhiPolicy(covered=covered, catalog=catalog, iac_modules=mods)


@lru_cache(maxsize=4)
def _load(path: str) -> PhiPolicy:
    return parse_policy(json.loads(Path(path).read_text(encoding="utf-8")))


def load_policy(path: str | Path | None = None) -> PhiPolicy:
    return _load(str(path or default_path()))


def violations(
    phi: bool,
    services: Iterable[str],
    policy: PhiPolicy,
) -> list[str]:
    """Services a tenant would use that are not allowed for it (empty = allowed). Non-PHI tenants
    are not restricted by this guard."""
    if not phi:
        return []
    return sorted({s for s in services if s not in policy.covered})


def placement_services(placement: Placement, roles: Iterable[str] = ROLES) -> list[str]:
    return [getattr(placement, r) for r in roles]


def check_tenant(
    session: Session,
    tenant_id: str | uuid.UUID,
    placement: Placement,
    roles: Iterable[str] = ROLES,
    policy: PhiPolicy | None = None,
) -> None:
    """Raise :class:`PlacementDenied` when the tenant is ``phi=true`` and any service this
    deployment uses for ``roles`` is not BAA-listed. Fail closed on any lookup error."""
    try:
        tenant = session.get(m.Tenant, uuid.UUID(str(tenant_id)))
        phi = True if tenant is None else bool(tenant.phi)
        if not phi:
            return
        bad = violations(True, placement_services(placement, roles), policy or load_policy())
    except PlacementDenied:
        raise
    except Exception as e:  # noqa: BLE001 - fail closed (SEC-026 style)
        raise PlacementDenied("PHI placement could not be evaluated") from e
    if bad:
        raise PlacementDenied(
            "this tenant holds PHI and may only use BAA-listed services; not listed: "
            + ", ".join(bad)
        )
