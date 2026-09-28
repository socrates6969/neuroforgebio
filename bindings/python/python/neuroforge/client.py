"""HTTP client: nf-core does auth, retries and error parsing; ``httpx`` moves the bytes.

Security (SEC-030): the default transport requires TLS 1.3 and always verifies certificates;
there is no option to turn verification off. Plain ``http://`` is accepted by nf-core only for
loopback hosts (local development). A caller may inject its own ``httpx.Client``-compatible
object (``http=``), e.g. an in-process test client.
"""

from __future__ import annotations

import json
import os
import ssl
import threading
import warnings
from collections.abc import Callable
from typing import Any

import httpx

from . import _native

__all__ = ["Client", "NfApiError", "configure", "get_client"]


class NfApiError(Exception):
    """An API call failed. ``status`` is the HTTP status (0 for transport/auth errors);
    ``problem`` is the RFC 9457 problem document when the server sent one."""

    def __init__(self, kind: str, status: int, message: str, problem: dict[str, Any] | None):
        super().__init__(message)
        self.kind = kind
        self.status = status
        self.problem = problem or {}

    @property
    def detail(self) -> str | None:
        return self.problem.get("detail")


def _wrap(e: _native.ApiError) -> NfApiError:
    kind, status, message, problem = e.args[0] if len(e.args) == 1 else e.args
    return NfApiError(kind, int(status), message, json.loads(problem) if problem else None)


def tls13_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    return ctx


class Client:
    """One API endpoint + credentials.

    ``token`` is an API key or access token (default ``NF_API_TOKEN``); ``refresh`` is an
    optional callable returning a new token, called once after a 401.
    """

    def __init__(
        self,
        api_url: str | None = None,
        token: str | None = None,
        *,
        session: str | None = None,
        http: Any = None,
        refresh: Callable[[], str] | None = None,
        timeout: float = 30.0,
        max_attempts: int = 5,
        poll_interval: float = 0.5,
        synthetic: bool | None = None,
        ingest_target: str | None = None,
    ) -> None:
        self.api_url = (api_url or os.environ.get("NF_API_URL") or "").rstrip("/")
        if not self.api_url:
            if http is None:
                raise ValueError("no API URL: pass api_url= or set NF_API_URL")
            self.api_url = "http://127.0.0.1"  # injected in-process transport
        self._token = token if token is not None else os.environ.get("NF_API_TOKEN")
        self._refresh = refresh
        self.session = session or os.environ.get("NF_SESSION")
        self.poll_interval = poll_interval
        # SEC-071: non-production environments accept only synthetic or licence-checked public
        # data; uploads and streams from this client are marked accordingly (NF_SYNTHETIC=1).
        self.synthetic = (os.environ.get("NF_SYNTHETIC") == "1") if synthetic is None else synthetic
        # gRPC IngestService address, "host:port" (default NF_INGEST_TARGET)
        self.ingest_target = ingest_target or os.environ.get("NF_INGEST_TARGET")
        self._own_http = http is None
        self._http = http or httpx.Client(
            verify=tls13_context(), timeout=timeout, follow_redirects=False
        )
        from . import __version__

        try:
            self._native = _native.ApiClient(
                self.api_url,
                self._send,
                self._tokens,
                timeout,
                max_attempts,
                f"neuroforge-python/{__version__} nf-core/{_native.__version__}",
            )
        except _native.ApiError as e:
            raise _wrap(e) from None

    # -- nf-core callbacks
    def _tokens(self, refresh: bool) -> str:
        if refresh:
            if self._refresh is None:
                raise PermissionError("token rejected and no refresh callable configured")
            self._token = self._refresh()
        if not self._token:
            raise PermissionError("no API token: pass token= or set NF_API_TOKEN")
        return self._token

    def _send(self, method: str, url: str, headers, body: bytes, timeout: float):
        # the per-request timeout is the transport's own (set when the default client is built)
        r = self._http.request(method, url, headers=dict(headers), content=body)
        if "deprecation" in r.headers:
            sunset = r.headers.get("sunset", "no sunset date announced")
            warnings.warn(
                f"{method} {httpx.URL(url).path} is deprecated (sunset: {sunset})",
                DeprecationWarning,
                stacklevel=4,
            )
        return r.status_code, list(r.headers.items()), r.content

    # -- requests
    def request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        json_body: Any = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        idempotency_key: str | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        h = dict(headers or {})
        body = b""
        if json_body is not None:
            body = json.dumps(json_body, separators=(",", ":"), allow_nan=False).encode()
            h.setdefault("content-type", "application/json")
        elif content is not None:
            body = content
            h.setdefault("content-type", "application/octet-stream")
        h.setdefault("accept", "application/json")
        if idempotency_key:
            h["idempotency-key"] = idempotency_key
        q = [(k, str(v)) for k, v in (query or {}).items() if v is not None]
        try:
            status, hdrs, data = self._native.request(method, path, q, list(h.items()), body)
        except _native.ApiError as e:
            raise _wrap(e) from None
        return status, {k.lower(): v for k, v in hdrs}, data

    def get(self, path: str, **query: Any) -> Any:
        return json.loads(self.request("GET", path, query=query)[2])

    def post(self, path: str, body: Any, *, idempotency_key: str | None = None) -> Any:
        _, _, data = self.request("POST", path, json_body=body, idempotency_key=idempotency_key)
        return json.loads(data) if data else None

    def put_bytes(self, path: str, data: bytes) -> Any:
        _, _, out = self.request("PUT", path, content=data)
        return json.loads(out) if out else None

    def put_presigned(self, url: str, data: bytes) -> None:
        """PUT to a pre-signed object-store URL (no API credentials are sent)."""
        try:
            _native.check_base_url(url)
        except _native.ApiError as e:
            raise _wrap(e) from None
        r = self._http.request("PUT", url, content=data)
        if r.status_code >= 300:
            raise NfApiError("http", r.status_code, f"pre-signed PUT failed: {r.status_code}", None)

    def close(self) -> None:
        if self._own_http:
            self._http.close()

    def __enter__(self) -> Client:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


_default: Client | None = None
_lock = threading.Lock()


def configure(**kwargs: Any) -> Client:
    """Set the module-level client used by ``nf.open``, ``nf.pipelines`` etc."""
    global _default
    with _lock:
        _default = Client(**kwargs)
        return _default


def get_client(client: Client | None = None) -> Client:
    global _default
    if client is not None:
        return client
    with _lock:
        if _default is None:
            _default = Client()
        return _default
