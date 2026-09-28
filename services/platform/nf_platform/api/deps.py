"""Per-request authentication, the route → action guard, and audit helpers.

Every route declares its action in ``openapi_extra={"x-nf-action": ...}`` (``PUBLIC`` for health).
The guard reads it from the matched route, authenticates, and calls ``authorize()``. A route without
an action is denied (and fails the route-enumeration tests), so nothing is reachable by accident
(SEC-020).
"""

from __future__ import annotations

import uuid
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from nf_platform.audit import log as audit
from nf_platform.auth import api_keys
from nf_platform.auth.authorize import Forbidden, ResourceRef, Unauthorized, authorize
from nf_platform.auth.oidc import OidcVerifier
from nf_platform.config import Settings
from nf_platform.db.context import Principal, tenant_session
from nf_platform.limits import LimitExceeded
from nf_platform.limits.ratelimit import RateLimiter, retry_after_header

ACTION_KEY = "x-nf-action"
PUBLIC = "public"


def action_extra(action: str) -> dict[str, Any]:
    return {ACTION_KEY: action}


@dataclass(frozen=True)
class Ctx:
    principal: Principal
    action: str
    request_id: str
    route: str
    method: str

    @property
    def tenant_id(self) -> str:
        return self.principal.tenant_id

    def session(self) -> AbstractContextManager[Session]:
        return tenant_session(self.principal)

    def check_tenant(self, row: Any) -> None:
        """Defence in depth after a load: the row must be in the caller's tenant."""
        authorize(
            self.principal,
            self.action,
            ResourceRef(type=self.action.split(":")[0], tenant_id=str(row.tenant_id)),
        )

    def audit(
        self,
        type_: str,
        *,
        resource_type: str | None = None,
        resource_id: Any = None,
        **details: Any,
    ) -> None:
        emit_for(
            self.principal,
            type_,
            "success",
            action=self.action,
            resource_type=resource_type,
            resource_id=None if resource_id is None else str(resource_id),
            request_id=self.request_id,
            details={"method": self.method, "route": self.route, **details},
        )


def emit_for(
    principal: Principal | None,
    type_: str,
    outcome: audit.Outcome,
    *,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    request_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    audit.emit(
        audit.AuditEvent(
            type=type_,
            outcome=outcome,
            action=action,
            tenant_id=principal.tenant_id if principal else None,
            actor_kind=principal.kind if principal else None,
            actor_id=principal.id if principal else None,
            auth_method=principal.auth_method if principal else None,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=request_id,
            details=details or {},
        )
    )


class Authenticator:
    def __init__(self, settings: Settings, oidc: OidcVerifier) -> None:
        self.settings = settings
        self.oidc = oidc

    def __call__(self, request: Request) -> Principal:
        header = request.headers.get("authorization", "")
        scheme, _, token = header.partition(" ")
        token = token.strip()
        if scheme.lower() != "bearer" or not token:
            raise Unauthorized("missing bearer credential")
        if token.startswith(api_keys.PREFIX):
            return api_keys.verify(token, engine=None, secret_provider=self.settings.secrets)
        return self.oidc.verify(token)


def _route_info(request: Request) -> tuple[str | None, str]:
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)
    extra = getattr(route, "openapi_extra", None) or {}
    return extra.get(ACTION_KEY), path


def guard(request: Request) -> Ctx | None:
    """FastAPI dependency on every route: authenticate + authorize the route's declared action."""
    action, path = _route_info(request)
    rid = request.state.request_id
    if action == PUBLIC:
        return None
    authn: Authenticator = request.app.state.authenticator
    principal: Principal | None = None
    try:
        principal = authn(request)
    except Unauthorized as e:
        emit_for(
            None,
            audit.AUTH_FAILURE,
            "failure",
            action=action,
            request_id=rid,
            details={"reason": str(e), "method": request.method, "route": path},
        )
        raise
    emit_for(
        principal,
        audit.AUTH_SUCCESS,
        "success",
        action=action,
        request_id=rid,
        details={"method": request.method, "route": path},
    )
    rate_limit(request, principal)
    try:
        if action is None:
            raise Forbidden("route has no declared action")
        resource = ResourceRef(type=action.split(":")[0], tenant_id=principal.tenant_id)
        authorize(principal, action, resource)
    except Forbidden as e:
        details: dict[str, Any] = {"reason": e.reason, "method": request.method, "route": path}
        if e.missing_scope:
            details["missing_scope"] = e.missing_scope
        emit_for(
            principal, audit.AUTHZ_DENIED, "denied", action=action, request_id=rid, details=details
        )
        raise
    return Ctx(
        principal=principal, action=action, request_id=rid, route=path, method=request.method
    )


def rate_key(principal: Principal) -> str:
    """One bucket per credential: an API key by its public id, a user or device by its id."""
    cred = principal.credential_id or principal.id
    return f"{principal.tenant_id}:{principal.kind}:{cred}"


def rate_limit(request: Request, principal: Principal) -> None:
    """4.8 local token bucket (the gateway enforces the global per-tenant limit). 429 +
    ``Retry-After`` problem when the credential's bucket is empty."""
    limiter: RateLimiter | None = getattr(request.app.state, "rate_limiter", None)
    if limiter is None:
        return
    wait = limiter.take(rate_key(principal))
    if wait > 0:
        raise LimitExceeded(
            429,
            "Request rate limit exceeded; retry after the indicated delay.",
            kind="rate-limited",
            headers=retry_after_header(wait),
        )


def new_request_id() -> str:
    return str(uuid.uuid4())
