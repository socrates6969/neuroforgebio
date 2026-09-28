"""The v1 OpenAPI 3.1 document (BUILD-GUIDE 4.1; SEC-077, SEC-079, SEC-090).

``openapi/v1.yaml`` is the committed contract. It is generated from the FastAPI routes plus the
platform conventions below, then committed; tests fail when the app and the committed file differ
(drift), when the app serves a route the file does not document (SEC-077), when a response breaks
its documented schema (contract tests), and ``tools/openapi-diff`` fails a breaking change against
``openapi/baseline/v1.yaml`` without a major version bump.

Conventions added on top of FastAPI's output:
- ``info`` (title, API version), ``servers``, security schemes: ``oidc`` (users) and ``apiKey``
  (``Authorization: Bearer nfb_live_...``). Operations without an API-key scope list only ``oidc``;
  public operations have ``security: []``.
- Errors are RFC 9457 ``application/problem+json`` (``#/components/schemas/Problem``) for 401, 403,
  404, 422, 429 and 500 (FastAPI's default 422 schema is replaced).
- ``x-nf-action``: the authorization action of the route (SEC-020); ``x-nf-api-key-scope``: the
  scope an API key needs (absent: API keys are refused).
- Deprecated operations (``nf_platform.api.versioning.DEPRECATIONS``): ``deprecated: true``,
  ``x-nf-sunset`` and the ``Deprecation``/``Sunset``/``Link`` response headers.
- OWNER-GATED routes that are not mounted by default (early access, 4.7) are documented with
  ``x-nf-status: disabled``.
- ``webhooks`` (OpenAPI 3.1): the signed outbound events (``nf_platform.webhooks.payloads``).

Regenerate: ``python -m nf_platform.api.openapi_doc --write`` (``--check`` exits 1 on drift).
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from nf_platform.api import versioning
from nf_platform.api.deps import ACTION_KEY, PUBLIC
from nf_platform.api.events_routes import RunStateEvent
from nf_platform.auth.authorize import ACTION_SCOPE
from nf_platform.webhooks import signing
from nf_platform.webhooks.payloads import EVENTS

# Brand-neutral on purpose: the company name is a brand token (BLUEPRINT §2.2) and the brand-token
# scan covers openapi/. Readers get the name from the docs site that renders this document.
TITLE = "Platform API"
# The API contract version (semver). The major number is the URI version (/v1); tools/openapi-diff
# requires a major bump for a breaking change. The service's own build version is separate.
API_VERSION = "1.0.0"
SERVER = "https://api.example.invalid"
ROOT = Path(__file__).resolve().parents[4]
SPEC_PATH = ROOT / "openapi" / "v1.yaml"
DISABLED = "disabled"
STATUS_KEY = "x-nf-status"
DESCRIPTION = (
    "Platform API v1. Data flows device -> SDK -> platform only: no operation, event "
    "or field sends anything to acquisition hardware (SEC-090). Errors are RFC 9457 "
    "application/problem+json. Only additive changes within v1; deprecations carry Deprecation "
    "and Sunset headers."
)

PROBLEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": "RFC 9457 problem details. Never contains stack traces, SQL, host names or "
    "credentials (SEC-079).",
    "required": ["type", "title", "status"],
    "properties": {
        "type": {"type": "string", "description": "urn:nf:problem:<kind> or about:blank"},
        "title": {"type": "string"},
        "status": {"type": "integer", "minimum": 400, "maximum": 599},
        "detail": {"type": "string"},
        "instance": {"type": "string", "description": "The request path."},
        "request_id": {"type": "string", "description": "Also in the X-Request-Id header."},
        "errors": {
            "type": "array",
            "description": "Validation errors (422): location and message, never the input.",
            "items": {
                "type": "object",
                "properties": {
                    "loc": {"type": "array", "items": {"type": "string"}},
                    "msg": {"type": "string"},
                },
            },
        },
    },
    "additionalProperties": True,
}

_PROBLEM_CONTENT = {
    "application/problem+json": {"schema": {"$ref": "#/components/schemas/Problem"}}
}
RESPONSES: dict[str, dict[str, Any]] = {
    "Unauthorized": {
        "description": "Missing, invalid, expired or revoked credential.",
        "headers": {"WWW-Authenticate": {"schema": {"type": "string"}}},
        "content": _PROBLEM_CONTENT,
    },
    "Forbidden": {
        "description": "Authenticated but not allowed (role, scope, tenant, quota).",
        "content": _PROBLEM_CONTENT,
    },
    "NotFound": {
        "description": "Not found (also for resources of another tenant).",
        "content": _PROBLEM_CONTENT,
    },
    "Invalid": {"description": "The request is not valid.", "content": _PROBLEM_CONTENT},
    "TooManyRequests": {
        "description": "Rate limit or quota exceeded.",
        "headers": {"Retry-After": {"schema": {"type": "integer", "minimum": 1}}},
        "content": _PROBLEM_CONTENT,
    },
    "OtherError": {
        "description": "Any other error status, e.g. 409 conflict, 410 gone, 413 too large.",
        "content": _PROBLEM_CONTENT,
    },
    "InternalError": {
        "description": "Unexpected error (a fixed body; details stay in the server log).",
        "content": _PROBLEM_CONTENT,
    },
}
DEPRECATION_HEADERS = {
    "Deprecation": {"schema": {"type": "string"}, "description": "RFC 9745: @<unix seconds>"},
    "Sunset": {"schema": {"type": "string"}, "description": "RFC 8594 HTTP-date"},
    "Link": {"schema": {"type": "string"}, "description": '<changelog>; rel="deprecation"'},
}
SECURITY_SCHEMES = {
    "oidc": {
        "type": "openIdConnect",
        "openIdConnectUrl": "https://id.example.invalid/.well-known/openid-configuration",
        "description": "User access token from the identity provider (Authorization: Bearer).",
    },
    "apiKey": {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "nfb_live_<public id>_<secret>",
        "description": "Scoped, expiring API key (SEC-014). Revocation is effective at once for "
        "new requests and within 60 s for open streams (SEC-017).",
    },
}
EXTRA_SCHEMAS = (RunStateEvent,)
_METHODS = ("get", "put", "post", "delete", "patch", "options", "head")


def spec_app(*, early_access: bool = True) -> FastAPI:
    """The routes the document is generated from, including OWNER-GATED ones. No engine, audit
    sink or IdP is configured (``create_app`` side effects are avoided on purpose)."""
    from nf_platform.app import bare_app, include_routers

    app = bare_app()
    include_routers(app, early_access=early_access)
    return app


def operations(doc: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    return [
        (method.upper(), path, op)
        for path, ops in doc.get("paths", {}).items()
        for method, op in ops.items()
        if method in _METHODS
    ]


def _webhooks(schemas: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for event_type, (name, model) in sorted(EVENTS.items()):
        js = model.model_json_schema(ref_template="#/components/schemas/{model}")
        for k, v in js.pop("$defs", {}).items():
            schemas[k] = v
        schemas[model.__name__] = js
        out[name] = {
            "post": {
                "operationId": name,
                "summary": f"{event_type} event",
                "description": (model.__doc__ or "").strip()
                + " Verify NF-Webhook-Signature over the raw body before parsing (SEC-045).",
                "parameters": [
                    {
                        "name": signing.HEADER_ID,
                        "in": "header",
                        "required": True,
                        "schema": {"type": "string", "format": "uuid"},
                    },
                    {
                        "name": signing.HEADER_TIMESTAMP,
                        "in": "header",
                        "required": True,
                        "schema": {"type": "integer"},
                    },
                    {
                        "name": signing.HEADER_SIGNATURE,
                        "in": "header",
                        "required": True,
                        "description": "t=<unix seconds>,v1=<hex HMAC-SHA-256 of '<t>.' + body>"
                        "[,v1=...] (one v1 per valid signing secret)",
                        "schema": {"type": "string"},
                    },
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": f"#/components/schemas/{model.__name__}"}
                        }
                    },
                },
                "responses": {
                    "2XX": {"description": "Received. Anything else is retried with backoff."}
                },
            }
        }
    return out


def build(app: FastAPI, *, disabled: set[tuple[str, str]] | None = None) -> dict[str, Any]:
    """The contract document for ``app``. ``disabled``: (METHOD, path) operations to mark
    ``x-nf-status: disabled`` (mounted in ``app`` but off by default)."""
    doc = get_openapi(
        title=TITLE,
        version=API_VERSION,
        openapi_version="3.1.0",
        description=DESCRIPTION,
        routes=app.routes,
        servers=[{"url": SERVER}],
    )
    doc = copy.deepcopy(doc)
    comps = doc.setdefault("components", {})
    schemas = comps.setdefault("schemas", {})
    schemas.pop("HTTPValidationError", None)
    schemas.pop("ValidationError", None)
    schemas["Problem"] = PROBLEM_SCHEMA
    comps["responses"] = RESPONSES
    comps["securitySchemes"] = SECURITY_SCHEMES
    for method, path, op in operations(doc):
        action = op.get(ACTION_KEY)
        responses = op.setdefault("responses", {})
        responses.pop("422", None)
        params = op.get("parameters", [])
        has_input = bool(params) or "requestBody" in op
        if action == PUBLIC:
            op["security"] = []
        else:
            scope = ACTION_SCOPE.get(action) if action in ACTION_SCOPE else None
            if action in ACTION_SCOPE:
                op["security"] = [{"oidc": []}, {"apiKey": []}]
                if scope:
                    op["x-nf-api-key-scope"] = scope
            else:
                op["security"] = [{"oidc": []}]
            responses["401"] = {"$ref": "#/components/responses/Unauthorized"}
            responses["403"] = {"$ref": "#/components/responses/Forbidden"}
        if any(p.get("in") == "path" for p in params):
            responses["404"] = {"$ref": "#/components/responses/NotFound"}
        if has_input:
            responses["422"] = {"$ref": "#/components/responses/Invalid"}
        responses["429"] = {"$ref": "#/components/responses/TooManyRequests"}
        responses["500"] = {"$ref": "#/components/responses/InternalError"}
        # Any other error status (409 conflict, 410 gone, 413 too large, ...) is problem+json too.
        responses["default"] = {"$ref": "#/components/responses/OtherError"}
        for code, r in responses.items():  # route-specific errors are problem+json too
            if code[:1] in "45" and "$ref" not in r and "content" not in r:
                r["content"] = copy.deepcopy(_PROBLEM_CONTENT)
        dep = versioning.DEPRECATIONS.get((method, path))
        if dep is not None:
            op["deprecated"] = True
            if dep.sunset is not None:
                op["x-nf-sunset"] = dep.sunset.date().isoformat()
            for code, r in responses.items():
                if code.startswith("2") and "$ref" not in r:
                    r.setdefault("headers", {}).update(DEPRECATION_HEADERS)
        if disabled and (method, path) in disabled:
            op[STATUS_KEY] = DISABLED
    doc["webhooks"] = _webhooks(schemas)
    for model in EXTRA_SCHEMAS:  # schemas referenced by x- extensions (SSE event data)
        schemas[model.__name__] = model.model_json_schema(
            ref_template="#/components/schemas/{model}"
        )
    return doc


def public_gated_operations() -> set[tuple[str, str]]:
    """Operations that exist only with ``early_access_enabled`` (OWNER-GATED, 4.7)."""

    def ops(early_access: bool) -> set[tuple[str, str]]:
        routes = spec_app(early_access=early_access).routes
        return {
            (m, p) for m, p, _ in operations(get_openapi(title="x", version="0", routes=routes))
        }

    return ops(True) - ops(False)


def current() -> dict[str, Any]:
    return build(spec_app(early_access=True), disabled=public_gated_operations())


def dump_yaml(doc: dict[str, Any]) -> str:
    import yaml

    return yaml.safe_dump(doc, sort_keys=True, allow_unicode=True, width=100)


def load_yaml(path: Path) -> dict[str, Any]:
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def normalise(doc: dict[str, Any]) -> dict[str, Any]:
    """Round-trip through JSON (tuples -> lists etc.) so a generated doc compares equal to a
    loaded one."""
    return json.loads(json.dumps(doc))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", action="store_true", help="write openapi/v1.yaml")
    ap.add_argument("--check", action="store_true", help="exit 1 if openapi/v1.yaml is stale")
    ap.add_argument("--json", action="store_true", help="print the document as JSON")
    ap.add_argument("--path", type=Path, default=SPEC_PATH)
    a = ap.parse_args(argv)
    doc = current()
    if a.json:
        json.dump(doc, sys.stdout, sort_keys=True, indent=1)
        return 0
    text = dump_yaml(doc)
    if a.check:
        if not a.path.exists() or normalise(load_yaml(a.path)) != normalise(doc):
            print(
                f"{a.path} is out of date: python -m nf_platform.api.openapi_doc --write",
                file=sys.stderr,
            )
            return 1
        return 0
    if a.write:
        a.path.parent.mkdir(parents=True, exist_ok=True)
        a.path.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {a.path}", file=sys.stderr)
        return 0
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
