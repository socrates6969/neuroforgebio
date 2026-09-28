"""NR-M1: request body caps are enforced while the body streams in (api.body_limit), for declared
Content-Length and for chunked bodies without one, as 413 too-large problems."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Annotated, Any

import pytest
from fastapi import Body, FastAPI, Request
from nf_platform.api import errors
from nf_platform.api.body_limit import (
    DEFAULT_MAX_BODY,
    MODEL_VERSION_MAX_BODY,
    RECORDING_MAX_BODY,
    BodySizeLimit,
    cap_for,
)
from nf_platform.api.pipelines_routes import MAX_SPEC_BYTES
from nf_platform.api.soup_routes import MAX_SBOM_BYTES

KIB = 1024
CHUNK = 64 * KIB


# ---------------------------------------------------------------- per-route caps
def _scope(method: str, path: str, **kw: Any) -> dict[str, Any]:
    return {"type": "http", "method": method, "path": path, "headers": [], **kw}


def test_per_route_caps():
    app = SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(upload_part_max=7 * KIB)))
    u = "0b6c1a52-8d5e-4c3a-9a55-3f0c4d1e2f10"
    assert MAX_SPEC_BYTES == 256 * KIB and DEFAULT_MAX_BODY == 1024 * KIB
    assert cap_for(_scope("POST", "/v1/pipelines")) == MAX_SPEC_BYTES
    assert cap_for(_scope("GET", "/v1/pipelines/name@1.0.0")) == MAX_SPEC_BYTES
    assert cap_for(_scope("PUT", f"/v1/models/{u}/versions/3/sbom")) == MAX_SBOM_BYTES
    assert cap_for(_scope("POST", f"/v1/models/{u}/versions")) == MODEL_VERSION_MAX_BODY
    assert cap_for(_scope("POST", f"/v1/sessions/{u}/recordings")) == RECORDING_MAX_BODY
    assert cap_for(_scope("PUT", f"/v1/uploads/{u}/parts/2", app=app)) == 7 * KIB
    # anything else, including the right path with another method, gets the default
    for method, path in (
        ("POST", "/v1/projects"),
        ("POST", "/v1/governance/channels/bulk"),
        ("POST", f"/v1/uploads/{u}/parts/2"),
        ("GET", f"/v1/models/{u}/versions/3/sbom"),
        ("POST", "/v1/pipelinesX"),
    ):
        assert cap_for(_scope(method, path)) == DEFAULT_MAX_BODY, path
    # routing ignores root_path, and so does the cap lookup
    assert cap_for(_scope("POST", "/api/v1/pipelines", root_path="/api")) == MAX_SPEC_BYTES


def test_model_version_cap_fits_the_largest_inline_weights():
    from nf_platform.registry import weights

    assert MODEL_VERSION_MAX_BODY > (weights.MAX_BYTES * 4) // 3 + 8 + 1024 * KIB


# ---------------------------------------------------------------- the middleware (pure ASGI)
def _mini_app() -> FastAPI:
    app = FastAPI()
    errors.install(app)
    app.add_middleware(BodySizeLimit)

    @app.post("/v1/json")
    def json_route(body: Annotated[dict[str, Any], Body()]):
        return {"keys": len(body)}

    @app.post("/v1/stream")
    async def stream_route(request: Request):
        n = 0
        async for block in request.stream():
            n += len(block)
        return {"bytes": n}

    return app


def _call(app, path: str, chunks: list[bytes], headers: list[tuple[bytes, bytes]]):
    """Run one request through the ASGI app; returns (status, headers, body, chunks consumed)."""
    consumed = 0
    sent: list[dict[str, Any]] = []

    async def receive():
        nonlocal consumed
        if consumed < len(chunks):
            consumed += 1
            return {
                "type": "http.request",
                "body": chunks[consumed - 1],
                "more_body": consumed < len(chunks),
            }
        return {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": [(b"host", b"test"), (b"content-type", b"application/json"), *headers],
        "client": ("127.0.0.1", 1),
        "server": ("test", 80),
    }
    asyncio.run(app(scope, receive, send))
    start = next(m for m in sent if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return start["status"], dict(start["headers"]), body, consumed


def _big_json(n: int) -> bytes:
    return json.dumps({"pad": "x" * n}).encode()


def _assert_too_large(status, headers, body, path, cap=DEFAULT_MAX_BODY):
    assert status == 413
    assert headers[b"content-type"] == b"application/problem+json"
    p = json.loads(body)
    assert p["type"] == "urn:nf:problem:too-large" and p["status"] == 413
    assert p["title"] == "Content Too Large" and p["instance"] == path
    assert p["max_bytes"] == cap


def test_chunked_over_cap_is_stopped_while_streaming():
    """No Content-Length; the body arrives in 64 KiB chunks. The 17th chunk crosses 1 MiB and
    the rest are never read (nothing is buffered to the end)."""
    data = _big_json(2 * DEFAULT_MAX_BODY)
    chunks = [data[i : i + CHUNK] for i in range(0, len(data), CHUNK)]
    for path in ("/v1/json", "/v1/stream"):
        status, headers, body, consumed = _call(_mini_app(), path, chunks, [])
        _assert_too_large(status, headers, body, path)
        assert consumed == DEFAULT_MAX_BODY // CHUNK + 1 < len(chunks)


def test_declared_content_length_over_cap_is_refused_before_reading():
    status, headers, body, consumed = _call(
        _mini_app(), "/v1/json", [b"{}"], [(b"content-length", str(DEFAULT_MAX_BODY + 1).encode())]
    )
    _assert_too_large(status, headers, body, "/v1/json")
    assert consumed == 0


def test_under_cap_passes_chunked_and_declared():
    data = _big_json(DEFAULT_MAX_BODY - 64)
    assert len(data) <= DEFAULT_MAX_BODY
    chunks = [data[i : i + CHUNK] for i in range(0, len(data), CHUNK)]
    status, _, body, consumed = _call(_mini_app(), "/v1/json", chunks, [])
    assert status == 200 and json.loads(body) == {"keys": 1} and consumed == len(chunks)
    status, _, body, _ = _call(
        _mini_app(), "/v1/stream", chunks, [(b"content-length", str(len(data)).encode())]
    )
    assert status == 200 and json.loads(body) == {"bytes": len(data)}


# ---------------------------------------------------------------- the real app
def _chunked(data: bytes):
    """httpx sends a generator body with Transfer-Encoding: chunked and no Content-Length."""

    def gen():
        for i in range(0, len(data), CHUNK):
            yield data[i : i + CHUNK]

    return gen()


def test_app_pipelines_over_cap_content_length(client, as_role):
    data = _big_json(MAX_SPEC_BYTES)
    r = client.post(
        "/v1/pipelines",
        content=data,
        headers={**as_role("owner"), "Content-Type": "application/json"},
    )
    assert r.request.headers["content-length"] == str(len(data))
    _assert_too_large(
        r.status_code,
        {b"content-type": r.headers["content-type"].encode()},
        r.content,
        "/v1/pipelines",
        MAX_SPEC_BYTES,
    )
    # still inside the request_id middleware
    assert r.headers["x-request-id"] and r.json()["request_id"] == r.headers["x-request-id"]


def test_app_pipelines_over_cap_chunked(client, as_role):
    r = client.post(
        "/v1/pipelines",
        content=_chunked(_big_json(MAX_SPEC_BYTES)),
        headers={**as_role("owner"), "Content-Type": "application/json"},
    )
    assert "content-length" not in r.request.headers
    assert r.status_code == 413 and r.headers["content-type"] == "application/problem+json"
    assert r.json()["type"] == "urn:nf:problem:too-large"
    assert r.json()["max_bytes"] == MAX_SPEC_BYTES


def test_app_default_cap_and_under_cap(client, as_role):
    h = {**as_role("owner"), "Content-Type": "application/json"}
    r = client.post("/v1/projects", content=_chunked(_big_json(DEFAULT_MAX_BODY)), headers=h)
    assert r.status_code == 413 and r.json()["max_bytes"] == DEFAULT_MAX_BODY
    # under the cap: a normal create passes, chunked too
    body = json.dumps({"name": "p-under-cap"}).encode()
    assert client.post("/v1/projects", content=_chunked(body), headers=h).status_code == 201
    # 300 KiB is over the pipelines cap but under the default: validated, not refused by size
    r = client.post(
        "/v1/projects",
        content=json.dumps({"name": "p", "description": "x" * 300 * KIB}),
        headers=h,
    )
    assert r.status_code == 422, r.text


def test_app_larger_route_caps_are_not_the_default(client, as_role):
    """The SBOM route takes bodies above the 1 MiB default (MAX_SBOM_BYTES): a 2 MiB body gets
    past the size check (the model does not exist: 404/422, not 413)."""
    import uuid

    h = {**as_role("owner"), "Content-Type": "application/json"}
    r = client.put(
        f"/v1/models/{uuid.uuid4()}/versions/1/sbom",
        content=_chunked(_big_json(2 * DEFAULT_MAX_BODY)),
        headers=h,
    )
    assert r.status_code != 413, r.text


# ---------------------------------------------------------------- malformed Content-Length
def _over_and_under_cap_chunks() -> tuple[list[bytes], list[bytes]]:
    over = _big_json(2 * DEFAULT_MAX_BODY)
    under = _big_json(DEFAULT_MAX_BODY // 2)
    return (
        [over[i : i + CHUNK] for i in range(0, len(over), CHUNK)],
        [under[i : i + CHUNK] for i in range(0, len(under), CHUNK)],
    )


def test_duplicate_content_length_is_treated_as_absent():
    """Two Content-Length values: neither the first nor the last is trusted; the body is
    counted instead (under the cap passes, over the cap is stopped while streaming)."""
    over, under = _over_and_under_cap_chunks()
    big = str(DEFAULT_MAX_BODY + 1).encode()
    for values in ((b"10", big), (big, b"10")):
        headers = [(b"content-length", v) for v in values]
        status, _, body, consumed = _call(_mini_app(), "/v1/stream", under, headers)
        assert status == 200 and consumed == len(under), values  # not refused up front
        assert json.loads(body) == {"bytes": sum(map(len, under))}
        status, headers_, body, consumed = _call(_mini_app(), "/v1/stream", over, headers)
        _assert_too_large(status, headers_, body, "/v1/stream")
        assert consumed == DEFAULT_MAX_BODY // CHUNK + 1 < len(over), values


def test_non_digit_content_length_is_treated_as_absent():
    over, under = _over_and_under_cap_chunks()
    for value in (b"+2000000", b" 2000000", b"-1", b"2e6", b""):
        headers = [(b"content-length", value)]
        status, _, body, consumed = _call(_mini_app(), "/v1/stream", under, headers)
        assert status == 200 and consumed == len(under), value
        status, headers_, body, consumed = _call(_mini_app(), "/v1/stream", over, headers)
        _assert_too_large(status, headers_, body, "/v1/stream")
        assert consumed == DEFAULT_MAX_BODY // CHUNK + 1 < len(over), value


# ---------------------------------------------------------------- response already started
def test_cap_exceeded_after_the_response_started_raises():
    """A (raw ASGI) route that starts its response and then reads the body: when the cap trips,
    a 413 can no longer be sent, so the middleware fails hard with RuntimeError (the server then
    aborts the connection). Nothing is sent after the route's own response start."""

    async def early_responder(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        while (await receive()).get("more_body"):
            pass
        await send({"type": "http.response.body", "body": b"done"})

    over, _ = _over_and_under_cap_chunks()
    consumed = 0
    sent: list[dict[str, Any]] = []

    async def receive():
        nonlocal consumed
        consumed += 1
        return {
            "type": "http.request",
            "body": over[consumed - 1],
            "more_body": consumed < len(over),
        }

    async def send(message):
        sent.append(message)

    scope = {"type": "http", "method": "POST", "path": "/v1/early", "headers": []}
    with pytest.raises(RuntimeError, match="exceeded its cap after the response started"):
        asyncio.run(BodySizeLimit(early_responder)(scope, receive, send))
    assert sent == [{"type": "http.response.start", "status": 200, "headers": []}]
    assert consumed == DEFAULT_MAX_BODY // CHUNK + 1 < len(over)
