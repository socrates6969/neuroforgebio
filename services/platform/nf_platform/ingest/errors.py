"""Typed ingest errors that the API maps to RFC 9457 problems (``nf_platform.api.errors``)."""

from __future__ import annotations

from typing import Any


class IngestError(Exception):
    """A client-visible ingest failure. ``detail`` never contains data, keys or identifiers."""

    def __init__(
        self,
        status: int,
        kind: str,
        title: str,
        detail: str | None = None,
        *,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail or title)
        self.status = status
        self.kind = kind
        self.title = title
        self.detail = detail
        self.extra = extra or {}


def invalid(detail: str, **extra: Any) -> IngestError:
    return IngestError(422, "invalid-request", "Invalid request", detail, extra=extra)


def conflict(detail: str, **extra: Any) -> IngestError:
    return IngestError(409, "conflict", "Conflict", detail, extra=extra)


def too_large(detail: str, **extra: Any) -> IngestError:
    return IngestError(413, "too-large", "Content Too Large", detail, extra=extra)
