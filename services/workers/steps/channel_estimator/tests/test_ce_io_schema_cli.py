"""Input validation, JSON/CSV equivalence, schema exports and conformance, CLI, hashing."""

from __future__ import annotations

import hashlib
import io
import json
import re
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

import pytest
from golden_io import (
    PARTICIPANTS,
    PKG_ROOT,
    REPO_ROOT,
    participant_document,
    reference_pooled,
    reference_segments,
)
from nf_channel_estimator import (
    EstimateParams,
    ParameterError,
    PFMapError,
    PFMapReadError,
    estimate,
    from_csv_text,
    from_document,
    load_map,
)
from nf_channel_estimator import _canonical as cj
from nf_channel_estimator.cli import main
from nf_channel_estimator.schema import input_schema, output_schema


# ------------------------------------------------------------------ minimal JSON Schema validator
def validate(inst: Any, s: dict[str, Any], path: str = "$") -> None:
    """Enough of draft 2020-12 for our schemas (type, const, enum, properties, oneOf, ...)."""
    if "oneOf" in s:
        ok = 0
        for sub in s["oneOf"]:
            try:
                validate(inst, sub, path)
                ok += 1
            except AssertionError:
                pass
        assert ok == 1, f"{path}: matches {ok} oneOf branches"
        return
    if "const" in s:
        assert inst == s["const"], f"{path}: {inst!r} != const {s['const']!r}"
    if "enum" in s:
        assert inst in s["enum"], f"{path}: {inst!r} not in enum"
    t = s.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        checks = {
            "object": lambda v: isinstance(v, dict),
            "array": lambda v: isinstance(v, list),
            "string": lambda v: isinstance(v, str),
            "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
            "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
            "boolean": lambda v: isinstance(v, bool),
            "null": lambda v: v is None,
        }
        assert any(checks[x](inst) for x in types), f"{path}: {inst!r} is not {types}"
    if isinstance(inst, (int, float)) and not isinstance(inst, bool):
        if "minimum" in s:
            assert inst >= s["minimum"], f"{path}: below minimum"
        if "maximum" in s:
            assert inst <= s["maximum"], f"{path}: above maximum"
    if isinstance(inst, str) and "pattern" in s:
        assert re.search(s["pattern"], inst), f"{path}: pattern"
    if isinstance(inst, dict):
        props = s.get("properties", {})
        for r in s.get("required", []):
            assert r in inst, f"{path}: missing {r}"
        for k, v in inst.items():
            if k in props:
                validate(v, props[k], f"{path}.{k}")
            else:
                ap = s.get("additionalProperties", True)
                assert ap is not False, f"{path}: unexpected property {k}"
                if isinstance(ap, dict):
                    validate(v, ap, f"{path}.{k}")
                if "propertyNames" in s:
                    validate(k, {"type": "string", **s["propertyNames"]}, f"{path}.<{k}>")
    if isinstance(inst, list) and "items" in s:
        for i, v in enumerate(inst):
            validate(v, s["items"], f"{path}[{i}]")


@pytest.mark.parametrize("part", PARTICIPANTS)
def test_outputs_conform_to_output_schema(part: str) -> None:
    for relabel in (False, True):
        r = estimate(
            from_document(participant_document(part)),
            EstimateParams(null_draws=100, relabel=relabel, relabel_draws=50),
        )
        validate(json.loads(json.dumps(r.to_dict())), output_schema())


def test_edge_outputs_conform() -> None:
    empty = {"schema": "nf.pf-map/v1", "electrodes": []}
    for p in (EstimateParams(), EstimateParams(relabel=True), EstimateParams(null_draws=0)):
        validate(
            json.loads(json.dumps(estimate(from_document(empty), p).to_dict())), output_schema()
        )


def test_golden_inputs_conform_to_input_schema() -> None:
    for part in PARTICIPANTS:
        validate(participant_document(part), input_schema())


def test_schema_exports_in_sync() -> None:
    for name, s in (("pf-map.v1", input_schema()), ("channel-estimate.v1", output_schema())):
        exported = json.loads((PKG_ROOT / "schemas" / f"{name}.schema.json").read_text("utf-8"))
        assert exported == s, f"regenerate schemas/{name}.schema.json (tests/golden_io.py)"


def test_reference_tables_regenerate_identically() -> None:
    ref_dir = PKG_ROOT / "nf_channel_estimator" / "reference_data"
    seg = json.loads((ref_dir / "greenspon2025_ed1_segments.json").read_text("utf-8"))
    pool = json.loads((ref_dir / "greenspon2025_pooled_dominant_segments.json").read_text("utf-8"))
    assert seg == reference_segments()
    assert pool == reference_pooled()
    assert len(seg["segments"]) == 48 and len(pool["keys"]) == 186


def test_example_maps_match_golden_conversion() -> None:
    for part in PARTICIPANTS:
        path = PKG_ROOT / "examples" / f"greenspon2025_{part}.pf-map.json"
        assert json.loads(path.read_text("utf-8")) == participant_document(part)


# ------------------------------------------------------------------ validation errors
def base_doc() -> dict[str, Any]:
    return {
        "schema": "nf.pf-map/v1",
        "electrodes": [{"electrode_id": "1", "array_id": "A", "palm_segment": "D1p"}],
    }


@pytest.mark.parametrize(
    ("mutate", "msg"),
    [
        (lambda d: d.update(schema="other"), "must be 'nf.pf-map/v1'"),
        (lambda d: d.update(extra=1), "unknown field"),
        (lambda d: d.update(electrodes={}), "must be an array"),
        (lambda d: d["electrodes"][0].pop("array_id"), "'array_id' is required"),
        (lambda d: d["electrodes"][0].update(palm_segment=""), "needs a palm_segment"),
        (lambda d: d["electrodes"][0].update(palm_segment="D1 p"), "not a segment tag"),
        (lambda d: d["electrodes"][0].update(has_pf="yes"), "'has_pf' must be true or false"),
        (lambda d: d["electrodes"][0].update(has_pf=False), "has_pf is false"),
        (lambda d: d["electrodes"][0].update(x_mm=1.0), "both x_mm and y_mm"),
        (lambda d: d["electrodes"][0].update(x_mm="1", y_mm=2), "must be a number"),
        (lambda d: d["electrodes"][0].update(dominant_segment="dors:D1p"), "disagrees"),
        (lambda d: d["electrodes"].append(dict(d["electrodes"][0])), "duplicate electrode"),
        (lambda d: d["electrodes"][0].update(electrode_id=3), "must be a string"),
    ],
)
def test_validation_errors(mutate: Any, msg: str) -> None:
    d = base_doc()
    mutate(d)
    with pytest.raises(PFMapError, match=re.escape(msg)):
        from_document(d)


def test_dominant_segment_consistent_is_accepted() -> None:
    d = base_doc()
    d["electrodes"][0]["dominant_segment"] = "palm:D1p"
    assert from_document(d).electrodes[0].dominant_segment == "palm:D1p"


def test_strict_json_parsing(tmp_path: Path) -> None:
    p = tmp_path / "m.json"
    p.write_text('{"schema": "nf.pf-map/v1", "electrodes": [], "electrodes": []}')
    with pytest.raises(PFMapReadError, match="duplicate key"):
        load_map(p)
    p.write_text("{nope")
    with pytest.raises(PFMapReadError):
        load_map(p)
    with pytest.raises(PFMapReadError):
        load_map(tmp_path / "missing.json")


def test_parameter_validation() -> None:
    for bad in (
        EstimateParams(m=0),
        EstimateParams(survival=1.5),
        EstimateParams(rule="R9"),  # type: ignore[arg-type]
        EstimateParams(seed=-1),
        EstimateParams(null_draws=-1),
    ):
        with pytest.raises(ParameterError):
            bad.validate()


# ------------------------------------------------------------------ CSV form
def to_csv(d: dict[str, Any]) -> str:
    cols = ["electrode_id", "array_id", "has_pf", "palm_segment", "dorsum_segment", "x_mm", "y_mm"]
    lines = [",".join(cols)]
    for e in d["electrodes"]:
        row = {**e, "has_pf": "1" if e.get("has_pf", True) else "0"}
        lines.append(",".join(str(row.get(c, "")) for c in cols))
    return "\n".join(lines) + "\n"


@pytest.mark.parametrize("part", PARTICIPANTS)
def test_csv_and_json_forms_are_equivalent(part: str) -> None:
    d = participant_document(part)
    from_json = from_document(d)
    from_csv = from_csv_text(to_csv(d), map_id=d["map_id"])
    assert from_csv.sha256() == from_json.sha256()
    p = EstimateParams(null_draws=200)
    assert estimate(from_csv, p).to_dict() == estimate(from_json, p).to_dict()


def test_csv_errors() -> None:
    with pytest.raises(PFMapError, match="missing column"):
        from_csv_text("electrode_id,palm_segment\n1,D1p\n")
    with pytest.raises(PFMapError, match="unknown column"):
        from_csv_text("electrode_id,array_id,amplitude\n1,A,3\n")
    with pytest.raises(PFMapError, match="has_pf"):
        from_csv_text("electrode_id,array_id,has_pf,palm_segment\n1,A,maybe,D1p\n")


# ------------------------------------------------------------------ hashing conformance
VEC = REPO_ROOT / "spec" / "test-vectors"


def test_canonical_copy_conforms_to_frozen_vectors() -> None:
    canon = json.loads((VEC / "canonical-json.json").read_text(encoding="ascii"))
    for case in canon["cases"]:
        out = cj.canonicalize_text(case["input"])
        assert out.decode("utf-8") == case["canonical"], case["name"]
        assert hashlib.sha256(out).hexdigest() == case["sha256"], case["name"]
    for case in canon["errors"]:
        with pytest.raises(cj.CanonicalError):
            cj.canonicalize_text(case["input"])


def test_input_sha256_is_canonical_json_sha256() -> None:
    pf = from_document(participant_document("C1"))
    expected = hashlib.sha256(cj.canonicalize(pf.normalised())).hexdigest()
    assert pf.sha256() == expected
    r = estimate(pf, EstimateParams(null_draws=10)).to_dict()
    assert r["provenance"]["input_sha256"] == expected
    assert r["provenance"]["parameters"]["seed"] == 20260926


# ------------------------------------------------------------------ CLI
def run_cli(*args: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = main(list(args))
        except SystemExit as exc:  # argparse usage errors
            code = int(exc.code or 0)
    return code, out.getvalue(), err.getvalue()


def test_cli_estimate_c1() -> None:
    path = str(PKG_ROOT / "examples" / "greenspon2025_C1.pf-map.json")
    code, out, err = run_cli("estimate", path, "--null-draws", "10000")
    assert code == 0, err
    doc = json.loads(out)
    assert doc["channel_counts"]["by_rule"]["R1"]["k_digit"] == 4
    assert doc["clustering"]["null_b_pooled"]["segment_level"]["ratio"] == pytest.approx(
        0.5388739946380697, abs=0
    )
    assert list(doc)[:3] == ["schema", "notice", "map_id"]


def test_cli_exit_codes(tmp_path: Path) -> None:
    good = str(PKG_ROOT / "examples" / "greenspon2025_P2.pf-map.json")
    assert run_cli("estimate", good, "--survival", "2")[0] == 2
    assert run_cli("estimate", good, "--rule", "R9")[0] == 2
    assert run_cli("estimate", str(tmp_path / "missing.json"))[0] == 3
    bad = tmp_path / "bad.json"
    bad.write_text('{"schema": "nf.pf-map/v1", "electrodes": [{"electrode_id": "1"}]}')
    code, _, err = run_cli("estimate", str(bad))
    assert code == 4 and "array_id" in err
    code, out, _ = run_cli("schema", "output")
    assert code == 0 and json.loads(out) == output_schema()


def test_cli_module_entry_point() -> None:
    path = str(PKG_ROOT / "examples" / "greenspon2025_P3.pf-map.json")
    r = subprocess.run(
        [sys.executable, "-m", "nf_channel_estimator", "estimate", path, "--null-draws", "20"],
        capture_output=True,
        text=True,
        cwd=str(PKG_ROOT),
        check=False,
    )
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["channel_counts"]["by_rule"]["R1"]["k_territory"] == 5
