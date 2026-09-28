"""Generate the docs API reference data from the committed OpenAPI document (BUILD-GUIDE 4.5).

    python tools/doc-snippets/gen_api_reference.py          # writes the docs api-reference.json
    python tools/doc-snippets/gen_api_reference.py --check  # exit 1 if it is stale

Output: ``apps/web/src/docs/api-reference.json``. It records the SHA-256 of ``openapi/v1.yaml``
(LF-normalised); ``apps/web/test/docs.test.mjs`` fails the web tests when the spec changed without
regenerating.

Each operation carries its ``x-nf-status`` as ``status`` (designed/planned/roadmap: a pill).
Operations with ``x-nf-status: disabled`` (not served, e.g. the owner-gated early-access routes)
are left out, and so are the schemas that only they use. Schema use is the transitive closure of
every ``$ref`` (also through ``#/components/responses``, parameters and request bodies), so a
schema that a served operation reaches in any way (such as ``Problem``) always stays.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "openapi/v1.yaml"
OUT = REPO / "apps/web/src/docs/api-reference.json"
METHODS = ("get", "post", "put", "patch", "delete")
GROUP_NAMES = {"api-keys": "API keys", "whoami": "Identity", "health": "Health"}


def _ref_name(obj: Any) -> str | None:
    if isinstance(obj, dict):
        if "$ref" in obj:
            return obj["$ref"].rsplit("/", 1)[-1]
        if obj.get("type") == "array" and "items" in obj:
            inner = _ref_name(obj["items"])
            return f"{inner}[]" if inner else "array"
        for key in ("anyOf", "oneOf", "allOf"):
            if key in obj:
                names = [n for n in (_ref_name(x) for x in obj[key]) if n]
                return " | ".join(names) or None
        if "type" in obj:
            return str(obj["type"])
    return None


def _type(schema: dict[str, Any]) -> str:
    return _ref_name(schema) or "any"


def _resolve(spec: dict[str, Any], obj: dict[str, Any]) -> dict[str, Any]:
    if "$ref" in obj:
        node: Any = spec
        for part in obj["$ref"].lstrip("#/").split("/"):
            node = node[part]
        return node
    return obj


DISABLED = "disabled"


def _disabled(op: dict[str, Any]) -> bool:
    return op.get("x-nf-status") == DISABLED


def _schemas_reached(spec: dict[str, Any], roots: list[Any]) -> set[str]:
    """Names of ``components.schemas`` reachable from ``roots`` through any ``$ref`` chain."""
    seen_refs: set[str] = set()
    schemas: set[str] = set()
    stack = list(roots)
    while stack:
        obj = stack.pop()
        if isinstance(obj, list):
            stack.extend(obj)
        elif isinstance(obj, dict):
            ref = obj.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/") and ref not in seen_refs:
                seen_refs.add(ref)
                if ref.startswith("#/components/schemas/"):
                    schemas.add(ref.rsplit("/", 1)[-1])
                node: Any = spec
                for part in ref[2:].split("/"):
                    node = node[part.replace("~1", "/").replace("~0", "~")]
                stack.append(node)
            stack.extend(v for k, v in obj.items() if k != "$ref")
    return schemas


def _schemas_only_disabled(spec: dict[str, Any]) -> set[str]:
    """Schemas used by disabled operations and by nothing that is served."""
    served: list[Any] = [spec.get("webhooks") or {}]
    disabled: list[Any] = []
    for item in spec["paths"].values():
        shared = item.get("parameters", [])
        for method in (*METHODS, "options", "head", "trace"):
            op = item.get(method)
            if op:
                (disabled if _disabled(op) else served).append([shared, op])
    return _schemas_reached(spec, disabled) - _schemas_reached(spec, served)


def build(spec_text: str) -> dict[str, Any]:
    spec = yaml.safe_load(spec_text)
    hidden_schemas = _schemas_only_disabled(spec)
    groups: dict[str, list[dict[str, Any]]] = {}
    for path, item in spec["paths"].items():
        seg = path.removeprefix("/v1/").split("/")[0] or "root"
        for method in METHODS:
            op = item.get(method)
            if not op or _disabled(op):
                continue
            params = [
                _resolve(spec, p) for p in item.get("parameters", []) + op.get("parameters", [])
            ]
            body = op.get("requestBody")
            body_out = None
            if body:
                content = _resolve(spec, body).get("content", {})
                body_out = {
                    "contentTypes": sorted(content),
                    "schema": next(
                        (_ref_name(c.get("schema")) for c in content.values() if c.get("schema")),
                        None,
                    ),
                }
            responses = []
            for status, r in op.get("responses", {}).items():
                rr = _resolve(spec, r)
                schema = next(
                    (
                        _ref_name(c.get("schema"))
                        for c in rr.get("content", {}).values()
                        if c.get("schema")
                    ),
                    None,
                )
                responses.append(
                    {
                        "status": str(status),
                        "description": rr.get("description", ""),
                        "schema": schema,
                    }
                )
            groups.setdefault(seg, []).append(
                {
                    "method": method.upper(),
                    "path": path,
                    "operationId": op.get("operationId", ""),
                    "summary": op.get("summary", ""),
                    "status": op.get("x-nf-status"),
                    "description": (op.get("description") or "").strip(),
                    "action": op.get("x-nf-action"),
                    "apiKeyScope": op.get("x-nf-api-key-scope"),
                    "public": op.get("security") == [],
                    "deprecated": bool(op.get("deprecated")),
                    "parameters": [
                        {
                            "name": p["name"],
                            "in": p["in"],
                            "required": bool(p.get("required")),
                            "type": _type(p.get("schema", {})),
                            "description": (p.get("description") or "").strip(),
                        }
                        for p in params
                    ],
                    "requestBody": body_out,
                    "responses": responses,
                }
            )
    schemas = []
    for name, s in sorted(spec.get("components", {}).get("schemas", {}).items()):
        if name in hidden_schemas:
            continue
        required = set(s.get("required", []))
        schemas.append(
            {
                "name": name,
                "description": (s.get("description") or "").strip(),
                "properties": [
                    {
                        "name": pn,
                        "type": _type(ps),
                        "required": pn in required,
                        "description": (ps.get("description") or "").strip(),
                    }
                    for pn, ps in (s.get("properties") or {}).items()
                ],
                "enum": [str(x) for x in s.get("enum", [])],
            }
        )
    return {
        "source": "openapi/v1.yaml",
        "sha256": hashlib.sha256(spec_text.replace("\r\n", "\n").encode("utf-8")).hexdigest(),
        "title": spec["info"]["title"],
        "version": spec["info"]["version"],
        "description": spec["info"].get("description", ""),
        "groups": [
            {
                "id": seg,
                "heading": GROUP_NAMES.get(seg, seg.replace("-", " ").capitalize()),
                "operations": sorted(
                    ops, key=lambda o: (o["path"], METHODS.index(o["method"].lower()))
                ),
            }
            for seg, ops in sorted(groups.items())
        ],
        "webhooks": sorted((spec.get("webhooks") or {}).keys()),
        "schemas": schemas,
    }


def render(spec_text: str) -> str:
    return json.dumps(build(spec_text), indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str]) -> int:
    text = SPEC.read_text("utf-8")
    out = render(text)
    if "--check" in argv:
        ok = OUT.exists() and OUT.read_text("utf-8").replace("\r\n", "\n") == out
        if not ok:
            print(
                "api-reference.json is stale: run tools/doc-snippets/gen_api_reference.py",
                file=sys.stderr,
            )  # noqa: T201
        return 0 if ok else 1
    OUT.write_text(out, "utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(REPO)}")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
