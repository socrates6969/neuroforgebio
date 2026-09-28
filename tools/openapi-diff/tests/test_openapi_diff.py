"""tools/openapi-diff: fixture tests (BUILD-GUIDE 4.1 "a breaking change without a major version
bump fails the diff check") and the check of the real contract against its committed baseline."""

from __future__ import annotations

import copy
from pathlib import Path

import openapi_diff as od
import pytest

HERE = Path(__file__).resolve().parent
FX = HERE / "fixtures"
ROOT = HERE.parents[2]
BASE = od.load(FX / "base.yaml")


def _breaking(new: dict) -> list[str]:
    changes, _ = od.diff(BASE, new)
    return [f"{c.where}: {c.what}" for c in changes if c.level == "breaking"]


def test_identical_documents_have_no_changes():
    assert od.diff(BASE, copy.deepcopy(BASE)) == ([], True)


def test_additive_fixture_passes_with_only_info_changes():
    changes, ok = od.diff(BASE, od.load(FX / "additive.yaml"))
    assert ok
    assert [c for c in changes if c.level == "breaking"] == []
    whats = {f"{c.where}: {c.what}" for c in changes}
    assert "DELETE /v1/items/{item_id}: added" in whats
    assert "POST itemDeleted: added" in whats
    assert any("optional parameter added" in w for w in whats)
    assert any("response property added" in w for w in whats)


def _mut(fn):
    d = copy.deepcopy(BASE)
    fn(d)
    return d


S = "components"


CASES = {
    "operation removed": (
        lambda d: d["paths"]["/v1/items"].pop("post"),
        "POST /v1/items: operation removed",
    ),
    "path removed": (
        lambda d: d["paths"].pop("/v1/items/{item_id}"),
        "GET /v1/items/{item_id}: operation removed",
    ),
    "operation disabled": (
        lambda d: d["paths"]["/v1/items"]["get"].__setitem__("x-nf-status", "disabled"),
        "operation disabled",
    ),
    "webhook removed": (lambda d: d["webhooks"].pop("itemChanged"), "webhook removed"),
    "new required parameter": (
        lambda d: d["paths"]["/v1/items"]["get"]["parameters"].append(
            {"name": "owner", "in": "query", "required": True, "schema": {"type": "string"}}
        ),
        "new required parameter",
    ),
    "parameter made required": (
        lambda d: d["paths"]["/v1/items"]["get"]["parameters"][0].__setitem__("required", True),
        "parameter made required",
    ),
    "parameter removed": (
        lambda d: d["paths"]["/v1/items"]["get"]["parameters"].pop(1),
        "parameter removed",
    ),
    "parameter bound tightened": (
        lambda d: d["paths"]["/v1/items"]["get"]["parameters"][0]["schema"].__setitem__(
            "maximum", 100
        ),
        "request maximum tightened to 100",
    ),
    "request enum narrowed": (
        lambda d: d["paths"]["/v1/items"]["get"]["parameters"][1]["schema"].__setitem__(
            "enum", ["open"]
        ),
        "request enum narrowed",
    ),
    "new required request property": (
        lambda d: (
            d[S]["schemas"]["ItemIn"]["properties"].__setitem__("owner", {"type": "string"}),
            d[S]["schemas"]["ItemIn"]["required"].append("owner"),
        ),
        "new required request property",
    ),
    "request property made required": (
        lambda d: d[S]["schemas"]["ItemIn"]["required"].append("note"),
        "request property made required",
    ),
    "request maxLength tightened": (
        lambda d: d[S]["schemas"]["ItemIn"]["properties"]["name"].__setitem__("maxLength", 50),
        "request maxLength tightened to 50",
    ),
    "request type narrowed (null no longer allowed)": (
        lambda d: d[S]["schemas"]["ItemIn"]["properties"].__setitem__("note", {"type": "string"}),
        "request type narrowed",
    ),
    "response property removed": (
        lambda d: d[S]["schemas"]["Item"]["properties"].pop("size"),
        "response property removed",
    ),
    "response property made optional": (
        lambda d: d[S]["schemas"]["Item"]["required"].remove("state"),
        "response property made optional",
    ),
    "response type changed": (
        lambda d: d[S]["schemas"]["Item"]["properties"].__setitem__("size", {"type": "string"}),
        "response type changed",
    ),
    "response became nullable": (
        lambda d: d[S]["schemas"]["Item"]["properties"].__setitem__(
            "name", {"anyOf": [{"type": "string"}, {"type": "null"}]}
        ),
        "response type changed",
    ),
    "response enum gained a value": (
        lambda d: d[S]["schemas"]["Item"]["properties"]["state"]["enum"].append("archived"),
        "response enum gained",
    ),
    "success status removed": (
        lambda d: d["paths"]["/v1/items"]["post"]["responses"].__setitem__(
            "202", d["paths"]["/v1/items"]["post"]["responses"].pop("201")
        ),
        "success response 201 removed",
    ),
    "response media type removed": (
        lambda d: d["paths"]["/v1/items/{item_id}"]["get"]["responses"]["200"].__setitem__(
            "content",
            {"application/xml": {"schema": {"type": "string"}}},
        ),
        "media type application/json removed",
    ),
    "public operation now authenticated": (
        lambda d: d["paths"]["/v1/health"]["get"].__setitem__("security", [{"oidc": []}]),
        "public operation now requires authentication",
    ),
    "api-key scope changed": (
        lambda d: d["paths"]["/v1/items"]["get"].__setitem__("x-nf-api-key-scope", "data:read"),
        "API-key scope changed",
    ),
    "webhook payload property removed": (
        lambda d: d[S]["schemas"]["ItemEvent"]["properties"].pop("id"),
        "response property removed",
    ),
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_breaking_change_without_major_bump_fails(case):
    mutate, expected = CASES[case]
    new = _mut(mutate)
    breaking = _breaking(new)
    assert any(expected in b for b in breaking), (case, breaking)
    _, ok = od.diff(BASE, new)
    assert not ok


@pytest.mark.parametrize("case", ["operation removed", "response property removed"])
def test_breaking_change_with_a_major_bump_passes(case):
    new = _mut(CASES[case][0])
    new["info"]["version"] = "2.0.0"
    changes, ok = od.diff(BASE, new)
    assert ok and any(c.level == "breaking" for c in changes)


def test_minor_bump_does_not_excuse_a_breaking_change():
    new = _mut(CASES["operation removed"][0])
    new["info"]["version"] = "1.9.0"
    assert od.diff(BASE, new)[1] is False


def test_cli_exit_codes(tmp_path, capsys):
    import yaml

    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump(_mut(CASES["operation removed"][0])), encoding="utf-8")
    assert od.main(["--base", str(FX / "base.yaml"), "--new", str(bad)]) == 1
    assert "breaking" in capsys.readouterr().out
    assert od.main(["--base", str(FX / "base.yaml"), "--new", str(FX / "additive.yaml")]) == 0
    assert od.main(["--base", str(tmp_path / "missing.yaml"), "--new", str(bad)]) == 2


def test_cyclic_refs_terminate():
    d = copy.deepcopy(BASE)
    d[S]["schemas"]["Item"]["properties"]["parent"] = {"$ref": "#/components/schemas/Item"}
    n = copy.deepcopy(d)
    n[S]["schemas"]["Item"]["properties"].pop("size")
    changes, ok = od.diff(d, n)
    assert not ok


def test_the_real_contract_has_no_breaking_change_against_its_baseline():
    """CI gate: openapi/v1.yaml vs openapi/baseline/v1.yaml (the published 1.x contract)."""
    code = od.main(
        [
            "--base",
            str(ROOT / "openapi" / "baseline" / "v1.yaml"),
            "--new",
            str(ROOT / "openapi" / "v1.yaml"),
            "--quiet",
        ]
    )
    assert code == 0
