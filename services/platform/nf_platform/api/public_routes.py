"""Public (unauthenticated) website endpoints: early access (BUILD-GUIDE 4.7; SEC-159).

OWNER-GATED. ``create_app`` includes this router ONLY when ``Settings.early_access_enabled`` is
true (default false), so with the flag off the routes do not exist (404, not in the route table).
``openapi/v1.yaml`` documents them with ``x-nf-status: disabled``.

No cookies and no session, so CSRF does not apply; CORS answers only the configured site origins
(``Settings.early_access_origins``) and a request carrying any other ``Origin`` is refused.
"""

from __future__ import annotations

import time
from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from nf_platform.api.deps import PUBLIC, action_extra, guard
from nf_platform.api.errors import ApiProblem
from nf_platform.audit import log as audit
from nf_platform.db import models as m
from nf_platform.limits.ratelimit import RateLimiter, retry_after_header
from nf_platform.site import early_access

router = APIRouter(prefix="/v1/public")
Role = Literal[*m.EARLY_ACCESS_ROLES]  # type: ignore[valid-type]
PATH = "/early-access"
CONFIRM = "/early-access/confirm"
ALLOW_METHODS = "POST, OPTIONS"
ALLOW_HEADERS = "Content-Type"


def _route(method: str, path: str, **kw):
    def deco(fn):
        router.add_api_route(
            path,
            fn,
            methods=[method],
            openapi_extra=action_extra(PUBLIC),
            dependencies=[Depends(guard)],
            **kw,
        )
        return fn

    return deco


class EarlyAccessIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    role: Role
    organisation: str | None = Field(default=None, max_length=200)
    website: str | None = Field(
        default=None, max_length=200, description="Honeypot: leave empty (hidden from people)."
    )

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        if not early_access.EMAIL_RE.match(v.strip()):
            raise ValueError("not an e-mail address")
        return v


class ConfirmIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=20, max_length=200)


class AcceptedOut(BaseModel):
    status: Literal["pending-confirmation"] = "pending-confirmation"


class ConfirmedOut(BaseModel):
    status: Literal["confirmed"] = "confirmed"


def _origin_ok(request: Request) -> str | None:
    """The allowed Origin to echo, or None when the request has no Origin. Any other Origin is a
    403 (defence in depth; browsers already block by the missing CORS header)."""
    origin = request.headers.get("origin")
    if origin is None:
        return None
    if origin not in request.app.state.settings.early_access_origins:
        raise ApiProblem(403, "Forbidden", "origin not allowed", kind="forbidden")
    return origin


def _cors(origin: str | None) -> dict[str, str]:
    if origin is None:
        return {}
    return {"Access-Control-Allow-Origin": origin, "Vary": "Origin"}


def _limiters(request: Request) -> tuple[RateLimiter, RateLimiter]:
    st = request.app.state
    if getattr(st, "early_access_limiters", None) is None:
        s = st.settings
        clock = getattr(st, "early_access_clock", time.monotonic)
        st.early_access_limiters = (
            RateLimiter(
                s.early_access_ip_per_hour / 3600.0, s.early_access_ip_per_hour, clock=clock
            ),
            RateLimiter(
                s.early_access_email_per_day / 86400.0, s.early_access_email_per_day, clock=clock
            ),
        )
    return st.early_access_limiters


def _limit(limiter: RateLimiter, key: str) -> None:
    wait = limiter.take(key)
    if wait > 0:
        raise ApiProblem(
            429,
            "Too Many Requests",
            "Too many sign-up attempts; try again later.",
            kind="rate-limited",
            headers=retry_after_header(wait),
        )


def _audit(outcome: str, **details) -> None:
    audit.emit(
        audit.AuditEvent(
            type="site.early_access",
            outcome=outcome,  # type: ignore[arg-type]
            action="public",
            resource_type="early_access",
            details=details,
        )
    )


_ERRORS = {403: {"description": "Origin not allowed (CORS)."}}


@_route("POST", PATH, status_code=202, response_model=AcceptedOut, responses=_ERRORS)
def join_early_access(body: EarlyAccessIn, request: Request):
    origin = _origin_ok(request)
    ip_limiter, email_limiter = _limiters(request)
    _limit(ip_limiter, "ea-ip:" + (request.client.host if request.client else "unknown"))
    if body.website:  # honeypot: same answer, nothing stored, nothing sent
        _audit("denied", reason="honeypot")
        return JSONResponse(AcceptedOut().model_dump(), status_code=202, headers=_cors(origin))
    _limit(email_limiter, early_access.email_key(body.email))
    res = early_access.sign_up(
        email=body.email,
        role=body.role,
        organisation=body.organisation or None,
        mailer=request.app.state.mailer,
    )
    _audit("success", stored=res.stored)
    return JSONResponse(AcceptedOut().model_dump(), status_code=202, headers=_cors(origin))


@_route(
    "POST",
    CONFIRM,
    response_model=ConfirmedOut,
    responses={**_ERRORS, 404: {"description": "Unknown or expired token."}},
)
def confirm_early_access(body: ConfirmIn, request: Request):
    origin = _origin_ok(request)
    ip_limiter, _ = _limiters(request)
    _limit(ip_limiter, "ea-ip:" + (request.client.host if request.client else "unknown"))
    ok = early_access.confirm(
        body.token, purge_days=request.app.state.settings.early_access_purge_days
    )
    if not ok:
        raise ApiProblem(
            404, "Not Found", "unknown or expired confirmation token", kind="not-found"
        )
    _audit("success", confirmed=True)
    return JSONResponse(ConfirmedOut().model_dump(), headers=_cors(origin))


def _preflight(request: Request) -> Response:
    origin = _origin_ok(request)
    if origin is None:
        raise ApiProblem(400, "Bad Request", "CORS preflight needs an Origin", kind="bad-request")
    headers = {
        **_cors(origin),
        "Access-Control-Allow-Methods": ALLOW_METHODS,
        "Access-Control-Allow-Headers": ALLOW_HEADERS,
        "Access-Control-Max-Age": "600",
    }
    return Response(status_code=204, headers=headers)


_PREFLIGHT = {**_ERRORS, 400: {"description": "No Origin header."}}


@_route("OPTIONS", PATH, status_code=204, response_class=Response, responses=_PREFLIGHT)
def early_access_preflight(request: Request) -> Response:
    return _preflight(request)


@_route("OPTIONS", CONFIRM, status_code=204, response_class=Response, responses=_PREFLIGHT)
def early_access_confirm_preflight(request: Request) -> Response:
    return _preflight(request)
