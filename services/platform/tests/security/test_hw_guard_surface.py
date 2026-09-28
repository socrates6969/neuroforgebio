"""SEC-090 over the EXTERNAL SURFACE of services/ (M2-REVIEW hw-guard scope decision, §G).

The name denylist (``tools/hw-guard/denylist.json``, the same file the ``hw-guard`` lint uses) is
applied to what a client of the platform can see, not to arbitrary Python identifiers:

- the OpenAPI document generated from the FastAPI app (``app.openapi()``): paths, operationIds,
  ``x-nf-action`` values, tags, parameter names, schema names, property names and enum values;
- the gRPC surface: servicer method names and every ``_pb2`` descriptor (services, methods,
  messages, fields, enums, enum values);
- outbound message schemas (webhooks etc.): any ``nf_platform`` module whose name contains
  ``webhook`` or ``outbound``; none exist yet, and each one added is picked up here.

There are no allow markers. Recorded event markers (e.g. "Stimulus" in an XDF file) are data and
must travel in neutral fields (``event_label``, ``annotation_text``), so they need no exception.
"""

from __future__ import annotations

import importlib
import json
import pkgutil
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import nf_platform
import pytest
from fastapi import APIRouter, FastAPI
from google.protobuf.descriptor import Descriptor, EnumDescriptor
from pydantic import BaseModel

REPO = Path(__file__).resolve().parents[4]
DENYLIST = json.loads((REPO / "tools" / "hw-guard" / "denylist.json").read_text("utf-8"))


def words(ident: str) -> list[str]:
    """Same split as tools/hw-guard/lib.mjs ``words``."""
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", ident)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s)
    return [w.lower() for w in re.split(r"[^A-Za-z0-9]+", s) if w]


def denied_terms(name: str) -> list[str]:
    w = words(name)
    keys = [p for p in DENYLIST["prefixes"] if any(x.startswith(p) for x in w)]
    keys += [x for x in DENYLIST["words"] if x in w]
    keys += [
        f"{a} {b}"
        for a, b in DENYLIST["sequences"]
        if any(w[i] == a and w[i + 1] == b for i in range(len(w) - 1))
    ]
    return sorted({DENYLIST["terms"][k] for k in keys})


def violations(surface: list[tuple[str, str]]) -> list[str]:
    return [f"{where}: {name!r} -> {t}" for where, name in surface for t in denied_terms(name)]


# ---------------------------------------------------------------- surface extraction
def _schema_names(node: Any, where: str) -> Iterator[tuple[str, str]]:
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "properties" and isinstance(v, dict):
                for prop in v:
                    yield f"{where}.properties", prop
            elif k == "enum" and isinstance(v, list):
                for e in v:
                    if isinstance(e, str):
                        yield f"{where}.enum", e
            elif k in ("operationId", "x-nf-action", "title") and isinstance(v, str):
                yield f"{where}.{k}", v
            elif k == "tags" and isinstance(v, list):
                for t in v:
                    if isinstance(t, str):
                        yield f"{where}.tags", t
            elif k == "parameters" and isinstance(v, list):
                for p in v:
                    if isinstance(p, dict) and isinstance(p.get("name"), str):
                        yield f"{where}.parameters", p["name"]
            yield from _schema_names(v, where)
    elif isinstance(node, list):
        for x in node:
            yield from _schema_names(x, where)


def openapi_surface(app: FastAPI) -> list[tuple[str, str]]:
    doc = app.openapi()
    out: list[tuple[str, str]] = []
    for path, ops in doc.get("paths", {}).items():
        out.append(("path", path))
        out.extend(_schema_names(ops, f"paths[{path}]"))
    for name, schema in doc.get("components", {}).get("schemas", {}).items():
        out.append(("components.schemas", name))
        out.extend(_schema_names(schema, f"components.schemas[{name}]"))
    for name in doc.get("webhooks", {}) or {}:
        out.append(("webhooks", name))
    out.extend(_schema_names(doc.get("webhooks", {}), "webhooks"))
    return out


def _nf_modules(match: re.Pattern[str]) -> list[Any]:
    mods = []
    for info in pkgutil.walk_packages(nf_platform.__path__, "nf_platform."):
        if match.search(info.name):
            mods.append(importlib.import_module(info.name))
    return mods


def _message_names(d: Descriptor, where: str) -> Iterator[tuple[str, str]]:
    yield where, d.name
    for f in d.fields:
        yield f"{where}.{d.name}.fields", f.name
    for e in d.enum_types:
        yield from _enum_names(e, f"{where}.{d.name}")
    for n in d.nested_types:
        yield from _message_names(n, f"{where}.{d.name}")


def _enum_names(e: EnumDescriptor, where: str) -> Iterator[tuple[str, str]]:
    yield f"{where}.enums", e.name
    for v in e.values:
        yield f"{where}.{e.name}.values", v.name


def grpc_surface() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for mod in _nf_modules(re.compile(r"_pb2$")):
        fd = mod.DESCRIPTOR
        where = f"{mod.__name__}"
        out.append((where, fd.package))
        for svc in fd.services_by_name.values():
            out.append((f"{where}.services", svc.name))
            for meth in svc.methods:
                out.append((f"{where}.{svc.name}.methods", meth.name))
        for msg in fd.message_types_by_name.values():
            out.extend(_message_names(msg, f"{where}.messages"))
        for e in fd.enum_types_by_name.values():
            out.extend(_enum_names(e, where))
    for mod in _nf_modules(re.compile(r"_pb2_grpc$")):
        for cname, cls in vars(mod).items():
            if isinstance(cls, type) and cname.endswith("Servicer"):
                out.append((f"{mod.__name__}.servicers", cname))
                for meth in vars(cls):
                    if not meth.startswith("_"):
                        out.append((f"{mod.__name__}.{cname}", meth))
    return out


def outbound_surface() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for mod in _nf_modules(re.compile(r"webhook|outbound")):
        for name, obj in vars(mod).items():
            if isinstance(obj, type) and issubclass(obj, BaseModel) and obj is not BaseModel:
                out.append((f"{mod.__name__}", name))
                out.extend(_schema_names(obj.model_json_schema(), f"{mod.__name__}.{name}"))
    return out


# ---------------------------------------------------------------- fixtures
@pytest.fixture
def platform_app(monkeypatch) -> FastAPI:
    """The real app, built without a database (``app.openapi()`` needs no connection). The
    process-wide engine and audit sink that ``create_app`` sets are restored afterwards."""
    from nf_platform.app import create_app
    from nf_platform.audit import log as audit
    from nf_platform.config import OidcSettings, Settings, StaticSecretProvider
    from nf_platform.db import context

    monkeypatch.setattr(context, "_engine", context._engine)
    monkeypatch.setattr(audit, "_sink", audit._sink)
    monkeypatch.delenv("NF_OBJECT_ROOT", raising=False)

    class NullSink:
        def write(self, event) -> None:  # pragma: no cover - never called here
            pass

    settings = Settings(
        database_url="postgresql+psycopg://nobody@127.0.0.1:9/none",
        oidc=OidcSettings(issuer="https://idp.test.invalid/realms/nf", audience="nf-api"),
        secrets=StaticSecretProvider(version="p1", pepper=b"\0" * 32),
    )
    return create_app(settings, jwks=lambda: {"keys": []}, audit_sink=NullSink())


# ---------------------------------------------------------------- tests
class Params(BaseModel):  # negative-control schema (module level: pydantic resolves the names)
    trigger_out: bool
    event_label: str


class Kind(BaseModel):
    kind: str


def test_platform_openapi_surface_has_no_denied_names(platform_app):
    surface = openapi_surface(platform_app)
    paths = [n for w, n in surface if w == "path"]
    assert len(paths) >= 20, "the generated OpenAPI document looks empty"
    assert any(w.endswith("x-nf-action") for w, _ in surface)
    assert violations(surface) == []


def test_grpc_surface_has_no_denied_names():
    surface = grpc_surface()
    names = {n for _, n in surface}
    assert {"IngestService", "StreamChunks", "Chunk"} <= names, "descriptors not found"
    assert violations(surface) == []


def test_outbound_schemas_have_no_denied_names():
    # No webhook/outbound module exists yet (4.6); any added one is scanned automatically.
    assert violations(outbound_surface()) == []


def test_checker_catches_a_stimulation_route_and_schema():
    """Negative control: the same extraction flags a FastAPI route /v1/devices/{id}/stimulate and
    denied schema names; neutral names (event_label) pass."""
    router = APIRouter(prefix="/v1")

    @router.post("/devices/{id}/stimulate", openapi_extra={"x-nf-action": "device:actuate"})
    def pulse_train(id: str, body: Params) -> Kind:  # pragma: no cover - never called
        return Kind(kind="x")

    app = FastAPI()
    app.include_router(router)
    found = violations(openapi_surface(app))
    joined = "\n".join(found)
    assert "'/v1/devices/{id}/stimulate' -> stim*" in joined
    assert "'device:actuate' -> actuat*" in joined
    assert "'trigger_out' -> trigger_out" in joined
    assert "pulse*" in joined  # operationId / title derived from the handler name
    assert "event_label" not in joined
    assert denied_terms("command") == ["command"]
    assert denied_terms("SetStimulation") == ["stim*"]
    assert denied_terms("event_label") == []
    assert denied_terms("Stimulus") == ["stim*"]  # hence recorded markers are data, not API names
