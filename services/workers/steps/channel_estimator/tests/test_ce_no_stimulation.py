"""No-stimulation rule (SEC-090 spirit): outputs hold channel counts and statistics only.

Walks every key of real outputs over all golden inputs (and edge inputs), and every property of the
exported output JSON Schema, and fails on any stimulation-like name. Also bans "guarantee" wording.
"""

from __future__ import annotations

import json
import re
from functools import cache
from pathlib import Path
from typing import Any

import pytest
from golden_io import PARTICIPANTS, PKG_ROOT, participant_document
from nf_channel_estimator import EstimateParams, estimate, from_document
from nf_channel_estimator.schema import input_schema, output_schema, schema_properties

BANNED_PREFIXES = (
    "stim",
    "pulse",
    "amplitude",
    "current",
    "charge",
    "frequency",
    "freq",
    "waveform",
    "train",
    "duty",
    "phase_width",
    "phasewidth",
    "microamp",
    "electrode_setting",
    "trigger",
    "command",
)
BANNED_EXACT = {"ua", "µa", "μa"}


def words(key: str) -> list[str]:
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
    return [w for w in re.split(r"[^A-Za-z0-9µμ]+", s.lower()) if w]


def stim_like(key: str) -> bool:
    k = key.lower()
    ws = words(key)
    if any(k.startswith(p) for p in BANNED_PREFIXES):
        return True
    if any(w.startswith(p) for w in ws for p in BANNED_PREFIXES):
        return True
    joined = "_".join(ws)
    if any(p in joined for p in ("phase_width", "electrode_setting")):
        return True
    return k in BANNED_EXACT or any(w in BANNED_EXACT for w in ws)


def walk_keys(o: Any, path: str = "$") -> list[tuple[str, str]]:
    out = []
    if isinstance(o, dict):
        for k, v in o.items():
            out.append((f"{path}.{k}", k))
            out.extend(walk_keys(v, f"{path}.{k}"))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            out.extend(walk_keys(v, f"{path}[{i}]"))
    return out


def walk_strings(o: Any) -> list[str]:
    if isinstance(o, dict):
        return [s for k, v in o.items() for s in [k, *walk_strings(v)]]
    if isinstance(o, list):
        return [s for v in o for s in walk_strings(v)]
    return [o] if isinstance(o, str) else []


@cache
def outputs() -> list[dict]:
    docs = [participant_document(q) for q in PARTICIPANTS]
    docs.append({"schema": "nf.pf-map/v1", "electrodes": []})
    res = []
    for d in docs:
        for rule in ("R1", "R2", "R3", "ray"):
            p = EstimateParams(rule=rule, null_draws=100, relabel=True, relabel_draws=50)
            res.append(estimate(from_document(d), p).to_dict())
    return res


def test_detector_catches_examples() -> None:
    for bad in (
        "stim_amplitude",
        "StimParams",
        "pulse_width_us",
        "amplitude",
        "current_uA",
        "chargeDensity",
        "frequency_hz",
        "freq",
        "waveform",
        "train_duration",
        "duty_cycle",
        "phase_width",
        "microamps",
        "uA",
        "electrode_settings",
        "trigger_out",
        "command",
        "set_stimulus",
    ):
        assert stim_like(bad), bad
    for ok in ("k_digit", "survival", "null_draws", "p_value", "territory_counts", "seed"):
        assert not stim_like(ok), ok


def test_real_outputs_have_no_stimulation_like_keys() -> None:
    hits = [(p, k) for out in outputs() for p, k in walk_keys(out) if stim_like(k)]
    assert hits == []


def test_output_schema_has_no_stimulation_like_properties() -> None:
    props = schema_properties(output_schema())
    assert props, "schema declares properties"
    assert [p for p in props if stim_like(p)] == []
    exported = json.loads((PKG_ROOT / "schemas" / "channel-estimate.v1.schema.json").read_text())
    assert [p for p in schema_properties(exported) if stim_like(p)] == []


def test_input_schema_has_no_stimulation_like_properties() -> None:
    assert [p for p in schema_properties(input_schema()) if stim_like(p)] == []


def test_output_schema_is_closed_everywhere() -> None:
    """Every object in the output schema forbids undeclared properties."""

    def check(s: Any, path: str) -> None:
        if isinstance(s, dict):
            if s.get("type") == "object":
                assert s.get("additionalProperties") is not True, path
                assert "additionalProperties" in s, path
            for k, v in s.items():
                check(v, f"{path}.{k}")
        elif isinstance(s, list):
            for i, v in enumerate(s):
                check(v, f"{path}[{i}]")

    check(output_schema(), "$")


@pytest.mark.parametrize("word", ["guarantee"])
def test_no_guarantee_wording_in_outputs_or_schema(word: str) -> None:
    texts = [s for out in outputs() for s in walk_strings(out)]
    texts += walk_strings(output_schema())
    assert [t for t in texts if word in t.lower()] == []


def test_input_rejects_stimulation_fields() -> None:
    from nf_channel_estimator import PFMapError

    d = participant_document("C1")
    d["electrodes"][0]["stim_amplitude_uA"] = 60
    with pytest.raises(PFMapError, match="unknown field"):
        from_document(d)


def test_package_sources_have_no_guarantee_wording() -> None:
    src = Path(PKG_ROOT / "nf_channel_estimator")
    for f in src.rglob("*.py"):
        assert "guarantee" not in f.read_text(encoding="utf-8").lower(), f
