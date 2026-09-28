"""The one authorization function (SEC-020): deny by default.

Roles (BLUEPRINT §4.2): owner, admin, data-steward, auditor, scientist, viewer, device.
Admin-class roles (owner, admin, data-steward, auditor) count only when the principal authenticated
with a phishing-resistant authenticator (``mfa_phr``, from the IdP ``amr`` claim; SEC-011). Without
it they grant nothing, so an admin session without passkey/WebAuthn gets 403 on every route.

API keys additionally need the scope that the action requires (SEC-014); actions without a scope in
``ACTION_SCOPE`` can never be performed with an API key.
"""

from __future__ import annotations

from dataclasses import dataclass

from nf_platform.db.context import Principal

ROLES = ("owner", "admin", "data-steward", "auditor", "scientist", "viewer", "device")
ADMIN_CLASS = frozenset({"owner", "admin", "data-steward", "auditor"})

_READERS = {"owner", "admin", "data-steward", "auditor", "scientist", "viewer"}
_WRITERS = {"owner", "admin", "data-steward", "scientist"}
_KEY_HOLDERS = {"owner", "admin", "data-steward", "scientist", "viewer"}
# SEC-022: governance properties (nervous_system, modality, consent scope...) are writable only by
# data-steward/admin (owner included).
_GOVERNANCE_WRITERS = frozenset({"owner", "admin", "data-steward"})

# action -> roles allowed. Anything not listed is denied.
PERMISSIONS: dict[str, frozenset[str]] = {
    "self:read": frozenset(ROLES),
    "project:read": frozenset(_READERS),
    "project:create": frozenset({"owner", "admin"}),
    "dataset:read": frozenset(_READERS),
    "dataset:create": frozenset(_WRITERS),
    "subject:read": frozenset(_READERS),
    "subject:create": frozenset(_WRITERS),
    "session:read": frozenset(_READERS),
    "session:create": frozenset(_WRITERS),
    "recording:read": frozenset(_READERS),
    "recording:create": frozenset(_WRITERS),
    "apikey:create": frozenset(_KEY_HOLDERS),
    "apikey:read": frozenset(_KEY_HOLDERS),
    "apikey:revoke": frozenset(_KEY_HOLDERS),
    "audit:read": frozenset({"owner", "admin", "auditor"}),
    # m2-stream (2.4 window reads, 2.6 uploads, 2.7 devices + streams)
    "signal:read": frozenset(_READERS),
    "upload:create": frozenset(_WRITERS),
    "upload:read": frozenset(_WRITERS),
    "device:create": frozenset(_WRITERS),
    "device:read": frozenset(_WRITERS),
    "stream:create": frozenset(_WRITERS),
    # m3-prov: provenance graph reads + export (3.1, 3.7), PipelineVersions (3.2)
    "provenance:read": frozenset(_READERS),
    "provenance:export": frozenset(_READERS),
    "pipeline:read": frozenset(_READERS),
    "pipeline:create": frozenset(_WRITERS),
    # m3-exec: pipeline runs (3.3)
    "run:read": frozenset(_READERS),
    "run:create": frozenset(_WRITERS),
    "run:cancel": frozenset(_WRITERS),
    # m5-ledger (M5): governance attributes (5.1; SEC-022 writes: data-steward/admin only),
    # classification (5.2), consent ledger (5.3), policy-checked data actions (5.4), withdrawals
    # and deletion certificates (5.5)
    "governance:read": frozenset(_READERS),
    "governance:write": _GOVERNANCE_WRITERS,
    "governance:admin": frozenset({"owner", "admin"}),
    "classification:read": frozenset(_READERS),
    "consent:read": frozenset({"owner", "admin", "data-steward", "auditor", "scientist"}),
    "consent:create": _GOVERNANCE_WRITERS,
    "withdrawal:create": _GOVERNANCE_WRITERS,
    "withdrawal:read": frozenset({"owner", "admin", "data-steward", "auditor"}),
    "aggregate:create": frozenset(_WRITERS),
    "model:train": frozenset(_WRITERS),
    "model:publish": frozenset({"owner", "admin"}),
    # raw export of signals: a classified action (SEC-142), four-eyes in policy.check (SEC-024)
    "signal:export": _GOVERNANCE_WRITERS,
    # m3-sweeps: multiverse sweeps + report (3.6)
    "sweep:read": frozenset(_READERS),
    "sweep:create": frozenset(_WRITERS),
    # m4-api: quotas (4.8), webhooks (4.6; tenant configuration, so owner/admin only)
    "quota:read": frozenset(_READERS),
    "webhook:read": frozenset({"owner", "admin"}),
    "webhook:create": frozenset({"owner", "admin"}),
    "webhook:update": frozenset({"owner", "admin"}),
    "webhook:delete": frozenset({"owner", "admin"}),
    # m5-evidence: FDA Evidence Kit export (5.8). Compliance roles only; not available to API keys
    # (no ACTION_SCOPE entry).
    "evidence:export": frozenset({"owner", "admin", "data-steward", "auditor"}),
    # m6-registry: governed model registry (6.1-6.3). Registering a version / retraining is
    # model:train (above); publication is model:publish (owner/admin, four-eyes, SEC-143);
    # approvals and Art. 5(1)(f) medical/safety exception records are governance decisions.
    "model:read": frozenset(_READERS),
    "model:create": frozenset(_WRITERS),
    "model:deploy": frozenset(_WRITERS),
    "model:approve": _GOVERNANCE_WRITERS,
    "model:exception": _GOVERNANCE_WRITERS,
    # m6-sisa (6.5): the SOUP/OTS document of a version (anyone who may read the model); attaching
    # the container SBOM that the document lists is an owner/admin decision (not for API keys)
    "model:soup-export": frozenset(_READERS),
    "model:sbom-attach": frozenset({"owner", "admin"}),
}

# Quarantined recordings (2.6; consent policy not yet satisfied) are readable only by these roles:
# they exist to review and release them. Everyone else gets 403 on reads and does not see them in
# lists.
QUARANTINE_READERS = frozenset({"owner", "admin", "data-steward"})

# Scopes an API key may carry, and the scope each action needs when the caller is an API key.
SCOPES = ("metadata:read", "metadata:write", "data:read", "data:write")
ACTION_SCOPE: dict[str, str | None] = {
    "self:read": None,  # any valid key may ask who it is
    **{
        f"{r}:read": "metadata:read"
        for r in ("project", "dataset", "subject", "session", "recording")
    },
    **{
        f"{r}:create": "metadata:write"
        for r in ("project", "dataset", "subject", "session", "recording")
    },
    "signal:read": "data:read",
    "upload:read": "data:write",
    "upload:create": "data:write",
    "device:read": "data:write",
    "device:create": "data:write",
    "stream:create": "data:write",
    "provenance:read": "metadata:read",
    "provenance:export": "metadata:read",
    "pipeline:read": "metadata:read",
    "pipeline:create": "metadata:write",
    "run:read": "data:read",
    "run:create": "data:write",
    "run:cancel": "data:write",
    # m5-ledger: reads only. Governance writes need an admin-class role, which an API key can
    # never hold (not delegable), so they are not available to keys.
    "governance:read": "metadata:read",
    "classification:read": "metadata:read",
    "consent:read": "metadata:read",
    "aggregate:create": "data:write",
    "model:train": "data:write",
    "sweep:read": "data:read",
    "sweep:create": "data:write",
    "quota:read": "metadata:read",
    # webhook:* has no scope on purpose: webhooks are managed only by an interactive owner/admin
    # (phishing-resistant login), never with an API key.
    # m6-registry: reads, model creation and deployment requests; approvals, exceptions and
    # publication need a user with a governance role (not delegable to keys)
    "model:read": "metadata:read",
    "model:create": "metadata:write",
    "model:deploy": "data:write",
    "model:soup-export": "metadata:read",  # m6-sisa (6.5)
}

# Roles that may be delegated to an API key, per role of the creator. Admin-class roles are never
# delegable: a key cannot prove a phishing-resistant login.
DELEGABLE: dict[str, frozenset[str]] = {
    "owner": frozenset({"scientist", "viewer", "device"}),
    "admin": frozenset({"scientist", "viewer", "device"}),
    "data-steward": frozenset({"scientist", "viewer"}),
    "scientist": frozenset({"scientist", "viewer"}),
    "viewer": frozenset({"viewer"}),
}


@dataclass(frozen=True)
class ResourceRef:
    type: str
    tenant_id: str
    id: str | None = None


class Unauthorized(Exception):
    """No valid credential (401)."""


class Forbidden(Exception):
    """Authenticated but not allowed (403)."""

    def __init__(self, reason: str, *, missing_scope: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.missing_scope = missing_scope


def effective_roles(principal: Principal) -> frozenset[str]:
    roles = frozenset(r for r in principal.roles if r in ROLES)
    if not principal.mfa_phr:
        roles = roles - ADMIN_CLASS
    return roles


def delegable_roles(principal: Principal) -> frozenset[str]:
    out: set[str] = set()
    for r in effective_roles(principal):
        out |= DELEGABLE.get(r, frozenset())
    return frozenset(out)


def may_read_quarantined(principal: Principal) -> bool:
    return bool(effective_roles(principal) & QUARANTINE_READERS)


def authorize_recording_state(principal: Principal, state: str) -> None:
    """Second check after a recording row is loaded (2.6): quarantined → only QUARANTINE_READERS."""
    if state == "quarantined" and not may_read_quarantined(principal):
        raise Forbidden("recording is quarantined until the consent policy allows access")


def authorize(principal: Principal | None, action: str, resource: ResourceRef) -> None:
    """Raise :class:`Unauthorized` or :class:`Forbidden` unless ``principal`` may do ``action``."""
    if principal is None:
        raise Unauthorized("authentication required")
    allowed = PERMISSIONS.get(action)
    if allowed is None:
        raise Forbidden("unknown action")
    # Tenant check (SEC-021 layer 1; RLS is layer 2).
    if resource.tenant_id != principal.tenant_id:
        raise Forbidden("resource belongs to another tenant")
    roles = effective_roles(principal)
    if not roles & allowed:
        held_admin = bool(frozenset(principal.roles) & ADMIN_CLASS & allowed)
        if held_admin and not principal.mfa_phr:
            raise Forbidden("phishing-resistant authentication required for this role")
        raise Forbidden("role does not permit this action")
    if principal.kind != "user":
        needed = ACTION_SCOPE.get(action, "__never__")
        if needed == "__never__":
            raise Forbidden("action not available to API keys or devices")
        if needed is not None and needed not in principal.scopes:
            raise Forbidden("missing scope", missing_scope=needed)
