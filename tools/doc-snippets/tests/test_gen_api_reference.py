"""The docs API reference (4.5): statuses are carried, disabled operations and the schemas only
they use are left out, and shared schemas reached through ``#/components/responses`` stay."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "nf_gen_api_reference", HERE.parent / "gen_api_reference.py"
)
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)

EARLY_ACCESS_ONLY = {"AcceptedOut", "ConfirmIn", "ConfirmedOut", "EarlyAccessIn"}

FIXTURE = {
    "openapi": "3.1.0",
    "info": {"title": "t", "version": "1.0.0"},
    "paths": {
        "/v1/things": {
            "get": {
                "operationId": "listThings",
                "x-nf-status": "planned",
                "responses": {
                    "200": {
                        "description": "ok",
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/Thing"}}
                        },
                    },
                    "404": {"$ref": "#/components/responses/NotFound"},
                },
            }
        },
        "/v1/public/secret": {
            "post": {
                "operationId": "joinSecret",
                "x-nf-status": "disabled",
                "requestBody": {
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/SecretIn"}}
                    }
                },
                "responses": {
                    "202": {
                        "description": "accepted",
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/Wrapper"}}
                        },
                    },
                    "400": {
                        "description": "bad",
                        "content": {
                            "application/problem+json": {
                                "schema": {"$ref": "#/components/schemas/Problem"}
                            }
                        },
                    },
                },
            }
        },
    },
    "components": {
        "responses": {
            "NotFound": {
                "description": "missing",
                "content": {
                    "application/problem+json": {"schema": {"$ref": "#/components/schemas/Problem"}}
                },
            }
        },
        "schemas": {
            "Thing": {"type": "object", "properties": {"id": {"type": "string"}}},
            "Problem": {
                "type": "object",
                "properties": {"detail": {"$ref": "#/components/schemas/Detail"}},
            },
            "Detail": {"type": "string"},
            "SecretIn": {"type": "object", "properties": {"email": {"type": "string"}}},
            "Wrapper": {
                "type": "object",
                "properties": {"inner": {"$ref": "#/components/schemas/Inner"}},
            },
            "Inner": {"type": "string"},
            "Unused": {"type": "string"},
        },
    },
}


def _ops(ref: dict) -> list[dict]:
    return [o for g in ref["groups"] for o in g["operations"]]


def test_fixture_status_carried_and_disabled_left_out():
    ref = gen.build(yaml.safe_dump(FIXTURE))
    ops = _ops(ref)
    assert [o["operationId"] for o in ops] == ["listThings"]
    assert ops[0]["status"] == "planned"
    names = {s["name"] for s in ref["schemas"]}
    # Problem (and Detail, through it) is reached only via #/components/responses from a served
    # operation, and is also used by the disabled one: it must stay.
    assert {"Thing", "Problem", "Detail", "Unused"} <= names
    # used by the disabled operation only, directly or transitively
    assert not names & {"SecretIn", "Wrapper", "Inner"}


def test_real_spec_hides_exactly_the_early_access_schemas():
    text = gen.SPEC.read_text("utf-8")
    spec = yaml.safe_load(text)
    assert gen._schemas_only_disabled(spec) == EARLY_ACCESS_ONLY
    ref = gen.build(text)
    names = {s["name"] for s in ref["schemas"]}
    assert "Problem" in names
    assert not names & EARLY_ACCESS_ONLY
    served = [o for o in _ops(ref)]
    assert served and all(o["status"] != "disabled" for o in served)
    assert not [o for o in served if "early-access" in o["path"]]
    assert "early-access" not in json.dumps(ref).lower().replace("early_access", "")


def test_every_other_schema_is_kept():
    text = gen.SPEC.read_text("utf-8")
    all_names = set(yaml.safe_load(text)["components"]["schemas"])
    kept = {s["name"] for s in gen.build(text)["schemas"]}
    assert kept == all_names - EARLY_ACCESS_ONLY
