"""M4 4.1: ``openapi/v1.yaml`` is the contract.

- the committed file equals what the app generates (drift);
- every route the app serves is documented, and every documented operation is served unless it is
  marked ``x-nf-status: disabled`` (SEC-077); an added, undocumented route fails;
- the document is structurally valid (every schema is Draft 2020-12, every ``$ref`` resolves);
- errors are RFC 9457 problem+json without internals, also for a forced exception (SEC-079);
- ``Deprecation``/``Sunset`` headers and ``deprecated: true`` come from one registry;
- SEC-090: hw-guard's surface scan over the app-generated document + webhook payloads + the gRPC
  servicer names finds nothing, and does find a planted name (so the wiring is real).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from jsonschema import Draft202012Validator
from nf_contract import SPEC_PATH, Contract, load_spec
from nf_platform.api import openapi_doc, versioning
from nf_platform.api.deps import ACTION_KEY, PUBLIC
from nf_platform.ingest.stream._proto import ingest_pb2 as pb

ROOT = Path(__file__).resolve().parents[4]
NODE22 = Path(r"C:\Users\mariu\.local\node22\node_modules\node\bin\node.exe")
CI = os.environ.get("CI", "").lower() in ("1", "true")


def _walk(routes) -> list:
    out = []
    for r in routes:
        inner = getattr(r, "original_router", None)  # FastAPI wraps included routers
        out.extend(_walk(inner.routes) if inner is not None else [r])
    return out


def served(app) -> set[tuple[str, str]]:
    """(METHOD, path) of every route the app answers. Non-API routes fail: they would bypass the
    guard and the schema."""
    out = set()
    for r in _walk(app.routes):
        assert isinstance(r, APIRoute), f"non-API route {getattr(r, 'path', r)}"
        out |= {(m, r.path) for m in r.methods if m != "HEAD"}
    return out


def documented(doc) -> dict[tuple[str, str], dict]:
    return {(m, p): op for m, p, op in openapi_doc.operations(doc)}


def undocumented_routes(app, doc) -> list[tuple[str, str]]:
    """SEC-077: routes the app serves that the contract does not document."""
    return sorted(served(app) - set(documented(doc)))


# ---------------------------------------------------------------- drift + enumeration
def test_committed_spec_matches_the_app():
    committed = openapi_doc.normalise(load_spec())
    assert committed == openapi_doc.normalise(openapi_doc.current()), (
        "openapi/v1.yaml is stale: python -m nf_platform.api.openapi_doc --write"
    )


def test_every_served_route_is_documented_and_vice_versa(app):
    doc = load_spec()
    ops = documented(doc)
    assert undocumented_routes(app, doc) == []
    missing = {k for k in ops if k not in served(app)}
    # documented but not served: only OWNER-GATED operations that are off by default
    assert missing == {k for k, op in ops.items() if op.get("x-nf-status") == "disabled"}
    assert missing, "the early-access operations are documented as disabled"
    for k in missing:
        assert k[1].startswith("/v1/public/")


def test_with_the_flag_on_the_app_serves_exactly_the_spec():
    app_on = openapi_doc.spec_app(early_access=True)
    assert served(app_on) == set(documented(load_spec()))


def test_an_undocumented_route_fails_the_enumeration(app):
    @app.get("/v1/not-in-the-spec")
    def sneaky():
        return {}

    assert undocumented_routes(app, load_spec()) == [("GET", "/v1/not-in-the-spec")]


def test_every_operation_declares_action_security_and_problem_errors():
    doc = load_spec()
    assert doc["openapi"] == "3.1.0"
    assert doc["info"]["version"].split(".")[0] == "1"
    ids = set()
    for method, path, op in openapi_doc.operations(doc):
        assert path.startswith("/v1/"), path
        assert op.get(ACTION_KEY), (method, path)
        assert op["operationId"] not in ids
        ids.add(op["operationId"])
        assert "security" in op
        if op[ACTION_KEY] == PUBLIC:
            assert op["security"] == []
        else:
            assert {"401", "403"} <= set(op["responses"])
        assert op["responses"]["500"] == {"$ref": "#/components/responses/InternalError"}
        assert "default" in op["responses"]
    for name, r in doc["components"]["responses"].items():
        assert list(r["content"]) == ["application/problem+json"], name
    assert "HTTPValidationError" not in doc["components"]["schemas"]


def test_typed_responses_for_formerly_untyped_routes():
    """M3 open issue 5: whoami, lineage and window JSON have schemas now."""
    doc = load_spec()
    ops = documented(doc)

    def ok_schema(method, path, code="200"):
        return ops[(method, path)]["responses"][code]["content"]["application/json"]["schema"]

    assert ok_schema("GET", "/v1/whoami") == {"$ref": "#/components/schemas/WhoAmIOut"}
    assert ok_schema("GET", "/v1/provenance/{node_id}/lineage") == {
        "$ref": "#/components/schemas/LineageOut"
    }
    assert ok_schema("GET", "/v1/recordings/{recording_id}/data") == {
        "$ref": "#/components/schemas/WindowJsonOut"
    }
    for p in ("/v1/runs", "/v1/sweeps"):
        assert ok_schema("GET", p)["type"] == "array"


def test_document_is_structurally_valid():
    doc = load_spec()
    for schema in doc["components"]["schemas"].values():
        Draft202012Validator.check_schema(schema)
    refs: list[str] = []

    def walk(x):
        if isinstance(x, dict):
            if isinstance(x.get("$ref"), str):
                refs.append(x["$ref"])
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(doc)
    assert refs
    for ref in set(refs):
        node = doc
        for part in ref.removeprefix("#/").split("/"):
            assert part in node, f"unresolved $ref {ref}"
            node = node[part]
    # the webhook section (OpenAPI 3.1) documents the signed event
    hook = doc["webhooks"]["runFinished"]["post"]
    assert {p["name"] for p in hook["parameters"]} == {
        "NF-Webhook-Id",
        "NF-Webhook-Timestamp",
        "NF-Webhook-Signature",
    }


def test_cli_check_passes_on_the_committed_file():
    assert openapi_doc.main(["--check", "--path", str(SPEC_PATH)]) == 0


# ---------------------------------------------------------------- SEC-079 problem+json
def test_forced_exception_is_a_problem_without_internals(app, client, as_role):
    from fastapi import Depends
    from nf_platform.api.deps import action_extra, guard

    secret_bits = "SELECT key_hash FROM api_key WHERE db-7.internal.example:5432"

    def boom():
        raise RuntimeError(secret_bits)

    app.add_api_route(
        "/v1/boom",
        boom,
        methods=["GET"],
        openapi_extra=action_extra("self:read"),
        dependencies=[Depends(guard)],
    )
    r = client.get("/v1/boom", headers=as_role("viewer"))
    assert r.status_code == 500
    assert r.headers["content-type"] == "application/problem+json"
    body = r.json()
    assert body["type"] == "urn:nf:problem:internal"
    assert body["title"] == "Internal Server Error" and body["status"] == 500
    text = r.text
    for leak in ("SELECT", "key_hash", "internal.example", "5432", "Traceback", "RuntimeError"):
        assert leak not in text


def test_404_405_and_401_are_problem_json(client, as_role):
    r = client.get("/v1/does-not-exist", headers=as_role("viewer"))
    assert r.status_code == 404 and r.headers["content-type"] == "application/problem+json"
    r = client.patch("/v1/projects", headers=as_role("viewer"))
    assert r.status_code == 405 and r.headers["content-type"] == "application/problem+json"
    assert r.json()["title"] == "Method Not Allowed"
    r = client.get("/v1/projects")
    assert r.status_code == 401 and r.headers["content-type"] == "application/problem+json"


def test_early_access_is_not_served_by_default(client):
    """4.7 OWNER-GATED: with the flag off the route does not exist."""
    r = client.post("/v1/public/early-access", json={"email": "a@b.example", "role": "other"})
    assert r.status_code == 404


# ---------------------------------------------------------------- Deprecation / Sunset
def test_deprecation_and_sunset_headers(monkeypatch, client):
    dep = versioning.Deprecation(
        deprecated_at=datetime(2026, 10, 1, tzinfo=UTC), sunset=datetime(2027, 10, 1, tzinfo=UTC)
    )
    monkeypatch.setitem(versioning.DEPRECATIONS, ("GET", "/v1/health"), dep)
    r = client.get("/v1/health")
    assert r.status_code == 200
    assert r.headers["Deprecation"] == f"@{int(dep.deprecated_at.timestamp())}"
    assert r.headers["Sunset"] == "Fri, 01 Oct 2027 00:00:00 GMT"
    assert r.headers["Link"].endswith('rel="deprecation"')
    op = documented(openapi_doc.current())[("GET", "/v1/health")]
    assert op["deprecated"] is True and op["x-nf-sunset"] == "2027-10-01"
    assert "Sunset" in op["responses"]["200"]["headers"]
    # without the registry entry: no headers
    monkeypatch.delitem(versioning.DEPRECATIONS, ("GET", "/v1/health"))
    assert "Deprecation" not in client.get("/v1/health").headers


# ---------------------------------------------------------------- SEC-090 surface scan
def _node() -> str | None:
    return str(NODE22) if NODE22.exists() else shutil.which("node")


def surface_document() -> dict:
    """What leaves the service: the app-generated OpenAPI incl. webhook payload schemas, plus the
    gRPC service, method, message and field names from the runtime descriptors."""
    doc = openapi_doc.current()
    grpc_names: dict[str, list[str]] = {"services": [], "methods": [], "messages": [], "fields": []}
    for svc in pb.DESCRIPTOR.services_by_name.values():
        grpc_names["services"].append(svc.name)
        grpc_names["methods"] += [m.name for m in svc.methods]
    for msg in pb.DESCRIPTOR.message_types_by_name.values():
        grpc_names["messages"].append(msg.name)
        grpc_names["fields"] += [f.name for f in msg.fields]
    doc["x-nf-grpc"] = grpc_names
    return doc


def _hw_guard(tmp_path, doc) -> subprocess.CompletedProcess:
    node = _node()
    if not node:
        if CI:
            raise AssertionError("CI needs node for hw-guard")
        pytest.skip("node not available; CI runs the surface scan")
    f = tmp_path / "surface.json"
    f.write_text(json.dumps(doc), encoding="utf-8")
    return subprocess.run(
        [node, str(ROOT / "tools" / "hw-guard" / "cli.mjs"), "--surface", str(f)],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_sec090_surface_scan_of_the_generated_api_is_clean(tmp_path):
    r = _hw_guard(tmp_path, surface_document())
    assert r.returncode == 0, r.stdout + r.stderr


def test_sec090_surface_scan_catches_a_planted_name(tmp_path):
    doc = surface_document()
    doc["components"]["schemas"]["RunFinishedData"]["properties"]["stimulus_level"] = {
        "type": "number"
    }
    r = _hw_guard(tmp_path, doc)
    assert r.returncode == 1
    assert "stim* (stimulus_level)" in r.stdout


def test_contract_checker_rejects_a_wrong_body():
    """The checker used by the matrix and the fuzz test really validates."""

    class R:
        status_code = 200
        headers = {"content-type": "application/json"}
        content = b'{"id": 1}'

        def json(self):
            return {"id": 1}

    with pytest.raises(AssertionError, match="violates the schema"):
        Contract().check("GET", "/v1/whoami", R())
    R.status_code = 418
    with pytest.raises(AssertionError):
        Contract().check("GET", "/v1/health", R())


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json", "/v1/openapi.json"])
def test_no_debug_or_schema_endpoints_are_served(client, path):
    """SEC-079: no interactive docs or schema endpoint; the contract is the committed file."""
    r = client.get(path)
    assert r.status_code == 404 and r.headers["content-type"] == "application/problem+json"
