"""Resource limits (BUILD-GUIDE 4.8; SEC-075): per-credential rate limits and per-tenant quotas."""

from __future__ import annotations

from typing import Any


class LimitExceeded(Exception):
    """A quota or rate limit was hit; the API maps it to RFC 9457 problem+json (403 or 429)."""

    def __init__(
        self,
        status: int,
        detail: str,
        *,
        kind: str,
        headers: dict[str, str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.kind = kind
        self.headers = headers
        self.extra = extra
