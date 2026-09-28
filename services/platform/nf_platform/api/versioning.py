"""API versioning helpers (BLUEPRINT §4.3; BUILD-GUIDE 4.1).

- URI major version (``/v1``); only additive changes within a major version (enforced by
  ``tools/openapi-diff`` against the committed baseline).
- Deprecation: register an operation in :data:`DEPRECATIONS` and every response of it carries
  ``Deprecation: @<unix seconds>`` (RFC 9745), ``Sunset: <HTTP-date>`` (RFC 8594) and
  ``Link: <changelog>; rel="deprecation"``; the OpenAPI document marks it ``deprecated: true`` with
  ``x-nf-sunset``. Minimum support window after deprecation: 12 months (recommendation, §4.3).
- operationIds are the route function names in camelCase (``list_projects`` -> ``listProjects``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import format_datetime

from fastapi import Request, Response
from fastapi.routing import APIRoute

CHANGELOG_URL = "https://docs.example.invalid/api/changelog"


def operation_id(route: APIRoute) -> str:
    head, *rest = route.name.split("_")
    return head + "".join(w[:1].upper() + w[1:] for w in rest)


@dataclass(frozen=True)
class Deprecation:
    deprecated_at: datetime
    sunset: datetime | None = None
    link: str = CHANGELOG_URL

    def headers(self) -> dict[str, str]:
        h = {
            "Deprecation": f"@{int(self.deprecated_at.timestamp())}",
            "Link": f'<{self.link}>; rel="deprecation"',
        }
        if self.sunset is not None:
            h["Sunset"] = format_datetime(self.sunset.astimezone(UTC), usegmt=True)
        return h


# (METHOD, path template) -> Deprecation. Empty: nothing in v1 is deprecated yet.
DEPRECATIONS: dict[tuple[str, str], Deprecation] = {}


def apply_headers(request: Request, response: Response) -> None:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if path is None:
        return
    dep = DEPRECATIONS.get((request.method.upper(), path))
    if dep is not None:
        for k, v in dep.headers().items():
            response.headers[k] = v
