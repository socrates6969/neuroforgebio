"""Request body size limits, enforced while the body streams in (NR-M1).

A pure ASGI middleware: a declared ``Content-Length`` over the route's cap is refused before the
app runs, and otherwise the bytes are counted as ``receive()`` delivers them, so a chunked request
without ``Content-Length`` is stopped as soon as it passes the cap (nothing is buffered here). The
refusal is a 413 ``too-large`` problem (``nf_platform.api.errors``) with ``max_bytes``.

Caps (first match of ``ROUTE_CAPS`` wins, anything else ``DEFAULT_MAX_BODY``):

- ``/v1/pipelines`` routes: ``MAX_SPEC_BYTES`` (256 KiB).
- ``PUT /v1/uploads/{id}/parts/{n}``: ``Settings.upload_part_max`` (read per request; bulk data
  goes through multipart uploads, never through JSON bodies).
- ``PUT /v1/models/{id}/versions/{v}/sbom``: ``MAX_SBOM_BYTES`` (16 MiB).
- ``POST /v1/models/{id}/versions``: inline base64 weights (``weights.MAX_BYTES``) plus 4 MiB for
  the training manifest (up to ``MAX_INPUTS`` node IDs and per-subject hashes/shards).
- ``POST /v1/sessions/{id}/recordings``: 4 MiB (up to 4096 channel descriptions).

Route-level checks (pipelines ``Content-Length``, the SBOM's canonical size, the upload part stream
loop) stay as defence in depth.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from nf_platform.api.errors import problem
from nf_platform.api.pipelines_routes import MAX_SPEC_BYTES
from nf_platform.api.soup_routes import MAX_SBOM_BYTES
from nf_platform.registry import weights

DEFAULT_MAX_BODY = 1024 * 1024
RECORDING_MAX_BODY = 4 * 1024 * 1024
MODEL_VERSION_MAX_BODY = (weights.MAX_BYTES * 4) // 3 + 8 + 4 * 1024 * 1024

Cap = int | Callable[[Scope], int]


def _upload_part_max(scope: Scope) -> int:
    return scope["app"].state.settings.upload_part_max


# (method or None for any, full-match path pattern, cap)
ROUTE_CAPS: tuple[tuple[str | None, re.Pattern[str], Cap], ...] = (
    (None, re.compile(r"/v1/pipelines(/.*)?"), MAX_SPEC_BYTES),
    ("PUT", re.compile(r"/v1/uploads/[^/]+/parts/[^/]+"), _upload_part_max),
    ("PUT", re.compile(r"/v1/models/[^/]+/versions/[^/]+/sbom"), MAX_SBOM_BYTES),
    ("POST", re.compile(r"/v1/models/[^/]+/versions"), MODEL_VERSION_MAX_BODY),
    ("POST", re.compile(r"/v1/sessions/[^/]+/recordings"), RECORDING_MAX_BODY),
)


def _route_path(scope: Scope) -> str:
    path: str = scope["path"]
    root = scope.get("root_path", "")
    return path[len(root) :] if root and path.startswith(root) else path


def cap_for(scope: Scope) -> int:
    path, method = _route_path(scope), scope.get("method")
    for m, pattern, cap in ROUTE_CAPS:
        if (m is None or m == method) and pattern.fullmatch(path):
            return cap(scope) if callable(cap) else cap
    return DEFAULT_MAX_BODY


def _declared_length(scope: Scope) -> int | None:
    values = [v for k, v in scope.get("headers", ()) if k.lower() == b"content-length"]
    if len(values) != 1 or not values[0].isdigit():
        return None  # absent or malformed: the server rejects malformed framing; count instead
    return int(values[0])


class _TooLarge(Exception):
    pass


class BodySizeLimit:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        cap = cap_for(scope)
        declared = _declared_length(scope)
        if declared is not None and declared > cap:
            await self._refuse(scope, receive, send, cap)
            return

        received = 0
        exceeded = False
        started = False

        async def limited_receive() -> Message:
            nonlocal received, exceeded
            if exceeded:
                raise _TooLarge
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > cap:
                    exceeded = True
                    raise _TooLarge
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal started
            if exceeded:
                return  # whatever the app made of the aborted body is replaced by the 413
            started = started or message["type"] == "http.response.start"
            await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except _TooLarge:
            pass
        except Exception:
            if not exceeded:
                raise
        if exceeded:
            if started:
                raise RuntimeError("request body exceeded its cap after the response started")
            await self._refuse(scope, receive, send, cap)

    @staticmethod
    async def _refuse(scope: Scope, receive: Receive, send: Send, cap: int) -> None:
        request = Request(scope)
        response = problem(
            request,
            413,
            "Content Too Large",
            "request body exceeds the size limit",
            kind="too-large",
            headers={"Connection": "close"},
            extra={"max_bytes": cap},
        )
        await response(scope, receive, send)
