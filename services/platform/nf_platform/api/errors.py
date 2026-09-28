"""Problem Details (RFC 9457) for every error response. Messages never include internals or
credentials."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from nf_platform.auth.api_keys import ApiKeyRequestError
from nf_platform.auth.authorize import Forbidden, Unauthorized
from nf_platform.ingest.errors import IngestError
from nf_platform.limits import LimitExceeded

log = logging.getLogger("nf_platform.errors")
PROBLEM = "application/problem+json"
TYPE_BASE = "urn:nf:problem:"


class ApiProblem(Exception):
    """A client-visible problem raised from anywhere below the routes (quotas, rate limits,
    webhooks). ``detail`` must never carry credentials, SQL, hostnames or stack traces."""

    def __init__(
        self,
        status: int,
        title: str,
        detail: str | None = None,
        *,
        kind: str,
        headers: dict[str, str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail or title)
        self.status = status
        self.title = title
        self.detail = detail
        self.kind = kind
        self.headers = headers
        self.extra = extra


class NotFound(Exception):
    def __init__(self, what: str) -> None:
        super().__init__(what)
        self.what = what


def problem(
    request: Request,
    status: int,
    title: str,
    detail: str | None = None,
    *,
    kind: str | None = None,
    headers: dict[str, str] | None = None,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": TYPE_BASE + kind if kind else "about:blank",
        "title": title,
        "status": status,
        "instance": request.url.path,
    }
    if detail:
        body["detail"] = detail
    rid = getattr(request.state, "request_id", None)
    if rid:
        body["request_id"] = rid
    if extra:
        body.update(extra)
    return JSONResponse(body, status_code=status, media_type=PROBLEM, headers=headers)


def install(app: FastAPI) -> None:
    @app.exception_handler(Unauthorized)
    async def _unauth(request: Request, exc: Unauthorized) -> JSONResponse:
        return problem(
            request,
            401,
            "Unauthorized",
            "A valid bearer token or API key is required.",
            kind="unauthorized",
            headers={"WWW-Authenticate": 'Bearer realm="nf"'},
        )

    @app.exception_handler(Forbidden)
    async def _forbidden(request: Request, exc: Forbidden) -> JSONResponse:
        extra = {"missing_scope": exc.missing_scope} if exc.missing_scope else None
        return problem(request, 403, "Forbidden", exc.reason, kind="forbidden", extra=extra)

    @app.exception_handler(ApiProblem)
    async def _problem(request: Request, exc: ApiProblem) -> JSONResponse:
        return problem(
            request,
            exc.status,
            exc.title,
            exc.detail,
            kind=exc.kind,
            headers=exc.headers,
            extra=exc.extra,
        )

    @app.exception_handler(LimitExceeded)
    async def _limit(request: Request, exc: LimitExceeded) -> JSONResponse:
        title = "Too Many Requests" if exc.status == 429 else "Quota exceeded"
        return problem(
            request,
            exc.status,
            title,
            exc.detail,
            kind=exc.kind,
            headers=exc.headers,
            extra=exc.extra,
        )

    @app.exception_handler(NotFound)
    async def _notfound(request: Request, exc: NotFound) -> JSONResponse:
        return problem(request, 404, "Not Found", f"{exc.what} not found", kind="not-found")

    @app.exception_handler(IngestError)
    async def _ingest(request: Request, exc: IngestError) -> JSONResponse:
        return problem(
            request, exc.status, exc.title, exc.detail, kind=exc.kind, extra=exc.extra or None
        )

    @app.exception_handler(ApiKeyRequestError)
    async def _keyreq(request: Request, exc: ApiKeyRequestError) -> JSONResponse:
        return problem(request, 422, "Invalid request", str(exc), kind="invalid-request")

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        # loc + msg only: the offending input is not echoed back (it may hold anything).
        errors = [
            {"loc": [str(p) for p in e.get("loc", ())], "msg": e.get("msg")} for e in exc.errors()
        ]
        return problem(
            request, 422, "Invalid request", kind="invalid-request", extra={"errors": errors}
        )

    @app.exception_handler(IntegrityError)
    async def _conflict(request: Request, exc: IntegrityError) -> JSONResponse:
        return problem(request, 409, "Conflict", "The request conflicts with existing data.")

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        title = {
            400: "Bad Request",
            404: "Not Found",
            405: "Method Not Allowed",
            413: "Content Too Large",
            415: "Unsupported Media Type",
        }.get(exc.status_code, "Error")
        return problem(request, exc.status_code, title, headers=getattr(exc, "headers", None))

    @app.exception_handler(Exception)
    async def _internal(request: Request, exc: Exception) -> JSONResponse:
        # SEC-079: a fixed body. The exception text, traceback, SQL and host names stay in the
        # server log (by type only, SEC-147), never in the response.
        log.error("unhandled error", extra={"error_type": type(exc).__name__})
        return problem(request, 500, "Internal Server Error", kind="internal")
