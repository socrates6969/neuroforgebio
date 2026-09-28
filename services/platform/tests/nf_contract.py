"""Contract checker for the committed OpenAPI document (M4 4.1; used instead of schemathesis).

``Contract(doc).check(method, path_template, response)`` asserts that a real response is allowed by
``openapi/v1.yaml``: the status code is documented (explicitly, as ``NXX`` or by ``default``), the
media type is one the operation documents, and a JSON body validates against the documented JSON
Schema (Draft 2020-12, ``$ref``s resolved inside the document). Binary and event-stream bodies are
checked for media type only.

Why not schemathesis: it would add ~15 transitive packages to the locked environment for what this
~100-line checker plus the hypothesis strategies in ``tests/api/test_api_contract.py`` do; the
authz matrix drives every operation with valid inputs and the fuzz test drives them with generated
ones, both through this checker.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[3]
SPEC_PATH = ROOT / "openapi" / "v1.yaml"
_METHODS = ("get", "put", "post", "delete", "patch", "options", "head")


def load_spec(path: Path = SPEC_PATH) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class ContractError(AssertionError):
    pass


class Contract:
    def __init__(self, doc: dict[str, Any] | None = None) -> None:
        self.doc = doc if doc is not None else load_spec()
        self._validators: dict[str, Draft202012Validator] = {}

    # ---------------------------------------------------------------- lookups
    def operations(self) -> list[tuple[str, str, dict[str, Any]]]:
        return [
            (m.upper(), p, op)
            for p, item in self.doc["paths"].items()
            for m, op in item.items()
            if m in _METHODS
        ]

    def op(self, method: str, path: str) -> dict[str, Any]:
        try:
            return self.doc["paths"][path][method.lower()]
        except KeyError:
            raise ContractError(f"{method} {path} is not in the spec (SEC-077)") from None

    def _deref(self, obj: dict[str, Any]) -> dict[str, Any]:
        while "$ref" in obj:
            node: Any = self.doc
            for part in obj["$ref"].removeprefix("#/").split("/"):
                node = node[part]
            obj = node
        return obj

    def _validator(self, schema: dict[str, Any]) -> Draft202012Validator:
        key = json.dumps(schema, sort_keys=True)
        v = self._validators.get(key)
        if v is None:
            # The document root is the schema's root, so "#/components/schemas/X" resolves.
            root = {"components": self.doc["components"], **schema}
            v = Draft202012Validator(root)
            self._validators[key] = v
        return v

    # ---------------------------------------------------------------- the check
    def response_spec(self, method: str, path: str, status: int) -> dict[str, Any]:
        responses = self.op(method, path).get("responses", {})
        code = str(status)
        for k in (code, f"{code[0]}XX", "default"):
            if k in responses:
                return self._deref(responses[k])
        raise ContractError(f"{method} {path}: status {status} is not documented")

    def check(self, method: str, path: str, response: Any) -> None:
        spec = self.response_spec(method, path, response.status_code)
        content = spec.get("content") or {}
        body = response.content
        if not content:
            if response.status_code != 204 and body not in (b"", b"null"):
                raise ContractError(
                    f"{method} {path}: undocumented body for {response.status_code}"
                )
            return
        ctype = response.headers.get("content-type", "").split(";")[0].strip()
        if ctype not in content:
            raise ContractError(
                f"{method} {path} {response.status_code}: media type {ctype!r} not in "
                f"{sorted(content)}"
            )
        if ctype.endswith("json"):
            schema = content[ctype].get("schema")
            if schema:
                errors = sorted(
                    self._validator(schema).iter_errors(response.json()), key=lambda e: e.path
                )
                if errors:
                    e = errors[0]
                    raise ContractError(
                        f"{method} {path} {response.status_code}: body violates the schema at "
                        f"{list(e.absolute_path)}: {e.message[:300]}"
                    )
