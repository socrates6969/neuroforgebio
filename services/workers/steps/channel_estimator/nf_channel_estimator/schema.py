"""JSON Schemas (draft 2020-12) for the input map and the output document.

Both are closed (``additionalProperties: false``) so that no field outside the documented set, and
in particular no stimulation-like field, can appear. ``schemas/*.schema.json`` are exports of these
dictionaries (``python -m nf_channel_estimator schema input|output``); a test keeps them in sync.
"""

from __future__ import annotations

from typing import Any

from .estimate import OUTPUT_SCHEMA_ID, TERRITORY_CLASSES
from .labels import DIGITS
from .pfmap import MAX_ELECTRODES, SCHEMA_ID

DRAFT = "https://json-schema.org/draft/2020-12/schema"

NUM: dict[str, Any] = {"type": "number"}
INT: dict[str, Any] = {"type": "integer"}
PROB: dict[str, Any] = {"type": "number", "minimum": 0, "maximum": 1}
STR: dict[str, Any] = {"type": "string"}
NULLABLE_NUM: dict[str, Any] = {"type": ["number", "null"]}
SHA256: dict[str, Any] = {"type": "string", "pattern": "^[0-9a-f]{64}$"}


def obj(props: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    """A closed object schema; every property is required unless listed otherwise."""
    return {
        "type": "object",
        "properties": props,
        "required": list(props) if required is None else required,
        "additionalProperties": False,
    }


def counts(keys: tuple[str, ...]) -> dict[str, Any]:
    """An object of non-negative integer counts with exactly these keys."""
    return obj({k: {"type": "integer", "minimum": 0} for k in keys})


def input_schema() -> dict[str, Any]:
    """JSON Schema of the ``nf.pf-map/v1`` input."""
    tag = {"type": "string", "pattern": "^([A-Za-z0-9][A-Za-z0-9+\\-]{0,63})?$"}
    ident = {"type": "string", "minLength": 1, "maxLength": 128}
    electrode = obj(
        {
            "electrode_id": ident,
            "array_id": ident,
            "has_pf": {"type": "boolean", "default": True},
            "palm_segment": {**tag, "default": ""},
            "dorsum_segment": {**tag, "default": ""},
            "x_mm": {"type": ["number", "null"]},
            "y_mm": {"type": ["number", "null"]},
            "dominant_segment": {
                "type": ["string", "null"],
                "description": "optional check value: palm:<tag> or dors:<tag> (palm first)",
            },
        },
        required=["electrode_id", "array_id"],
    )
    return {
        "$schema": DRAFT,
        "$id": "https://schemas.invalid/nf/pf-map/v1",
        "title": "Projected-field map (nf.pf-map/v1)",
        "description": "Per-electrode projected-field labels of one implant. A PF electrode needs "
        "a palm_segment or a dorsum_segment; a non-PF electrode has neither. Research use only.",
        **obj(
            {
                "schema": {"const": SCHEMA_ID},
                "map_id": {"type": ["string", "null"], "minLength": 1, "maxLength": 128},
                "electrodes": {"type": "array", "items": electrode, "maxItems": MAX_ELECTRODES},
            },
            required=["schema", "electrodes"],
        ),
    }


def output_schema() -> dict[str, Any]:
    """JSON Schema of the ``nf.channel-estimate/v1`` output."""
    kprob = obj({"k": {"type": "integer", "minimum": 1}, "probability": PROB})
    kprobs = {"type": "array", "items": kprob}
    rule_counts = {
        rule: obj(
            {
                "territory_counts": counts(TERRITORY_CLASSES[rule]),
                "k_digit": {"type": "integer", "minimum": 0, "maximum": 5},
                "k_territory": {"type": "integer", "minimum": 0, "maximum": 6},
            }
        )
        for rule in ("R1", "R2", "R3", "ray")
    }
    null_stat = obj(
        {
            "observed": NUM,
            "null_median": NUM,
            "ratio": NULLABLE_NUM,
            "p_value": PROB,
        }
    )
    null_block = obj(
        {
            "segment_level": null_stat,
            "digit_level": null_stat,
            "k_digit": obj({"observed": INT, "null_median": NUM, "p_value": PROB}),
        }
    )
    rng = obj(
        {
            "construction": STR,
            "streams_used": obj({"null_a": STR, "null_b": STR, "relabelling": STR}),
        }
    )
    skipped = obj({"status": {"const": "skipped"}, "reason": STR})
    clustering = {
        "oneOf": [
            skipped,
            obj(
                {
                    "status": {"const": "computed"},
                    "statistic": STR,
                    "seed": INT,
                    "draws": INT,
                    "rng": rng,
                    "null_a_area": null_block,
                    "null_b_pooled": null_block,
                    "null_a_area_no_wrist": obj({"null_median": NUM, "p_value": PROB}),
                    "reference": obj(
                        {
                            "source": STR,
                            "segments_sha256": SHA256,
                            "pooled_sha256": SHA256,
                            "pooled_electrodes": INT,
                        }
                    ),
                }
            ),
        ]
    }
    relabel_level = obj(
        {
            "fraction": PROB,
            "electrodes_relabelled": INT,
            "draws": INT,
            "p_k_digit_at_least": {"type": "array", "items": PROB},
            "p_k_territory_at_least": {"type": "array", "items": PROB},
            "p_k_digit_within_1_of_observed": PROB,
            "k_digit_distribution": {
                "type": "object",
                "propertyNames": {"pattern": "^[0-5]$"},
                "additionalProperties": INT,
            },
        }
    )
    relabelling = {
        "oneOf": [
            obj({"status": {"const": "not_requested"}}),
            skipped,
            obj(
                {
                    "status": {"const": "computed"},
                    "rule": {"const": "R1"},
                    "method": STR,
                    "seed": INT,
                    "rng": rng,
                    "levels": {"type": "array", "items": relabel_level},
                }
            ),
        ]
    }
    attrition_level = {
        "digit_level": obj({"class_sizes": counts(DIGITS), "p_k_at_least": kprobs}),
        "territory_level": obj(
            {"class_sizes": counts((*DIGITS, "HAND_POOLED")), "p_k_at_least": kprobs}
        ),
    }
    attrition = obj(
        {
            "rule": {"enum": ["R1", "R2", "R3", "ray"]},
            "m": INT,
            "survival": PROB,
            "model": STR,
            **attrition_level,
            "sensitivity": {
                "type": "array",
                "items": obj({"survival": PROB, "digit_level": kprobs, "territory_level": kprobs}),
            },
        }
    )
    params = obj(
        {
            "m": INT,
            "survival": PROB,
            "rule": {"enum": ["R1", "R2", "R3", "ray"]},
            "seed": INT,
            "null_draws": INT,
            "sensitivity": {"type": "array", "items": PROB},
            "relabel": {"type": "boolean"},
            "relabel_fractions": {"type": "array", "items": PROB},
            "relabel_draws": INT,
        }
    )
    provenance = obj(
        {
            "package": STR,
            "version": STR,
            "code_commit": {"type": ["string", "null"]},
            "input_sha256": SHA256,
            "input_hash_scheme": STR,
            "parameters": params,
            "reference_data": {
                "oneOf": [
                    obj({"segments_sha256": SHA256, "pooled_sha256": SHA256}),
                    obj({"status": {"const": "not_installed"}}),
                ]
            },
            "method": STR,
            "runtime": obj({"python": STR, "numpy": STR}),
        }
    )
    body = obj(
        {
            "schema": {"const": OUTPUT_SCHEMA_ID},
            "notice": STR,
            "map_id": {"type": ["string", "null"]},
            "input_summary": obj(
                {
                    "electrodes_listed": INT,
                    "pf_electrodes": INT,
                    "arrays": {
                        "type": "array",
                        "items": obj(
                            {"array_id": STR, "electrodes_listed": INT, "pf_electrodes": INT}
                        ),
                    },
                    "positions_present": {"type": "boolean"},
                    "dominant_segments_outside_reference": {"type": "array", "items": STR},
                }
            ),
            "channel_counts": obj(
                {
                    "m": INT,
                    "definition": STR,
                    "by_rule": obj(rule_counts),
                    "per_array_R1": {
                        "type": "array",
                        "items": obj({"array_id": STR, "k_digit": INT, "k_territory": INT}),
                    },
                    "second_array_gain_R1": {"type": ["integer", "null"]},
                }
            ),
            "diversity": obj(
                {
                    "rule": {"const": "R1"},
                    "n_eff_digit": NULLABLE_NUM,
                    "n_eff_digit_bias_corrected": NULLABLE_NUM,
                    "n_eff_segment": NULLABLE_NUM,
                    "n_eff_segment_bias_corrected": NULLABLE_NUM,
                    "n_segment_classes": INT,
                    "n_eff_soft": NULLABLE_NUM,
                }
            ),
            "clustering": clustering,
            "attrition": attrition,
            "relabelling": relabelling,
            "limitations": {"type": "array", "items": STR},
            "provenance": provenance,
        }
    )
    return {
        "$schema": DRAFT,
        "$id": "https://schemas.invalid/nf/channel-estimate/v1",
        "title": "Channel estimate (nf.channel-estimate/v1)",
        "description": "Distinct-channel counts, clustering statistics and attrition "
        "probabilities for one projected-field map. Channel counts and statistics only; "
        "no stimulation parameters. Research use only.",
        **body,
    }


def schema_properties(schema: Any) -> list[str]:
    """Every property name declared anywhere in a schema (for the no-stimulation test)."""
    out: list[str] = []
    if isinstance(schema, dict):
        for k, v in schema.items():
            if k == "properties" and isinstance(v, dict):
                out.extend(v)
            out.extend(schema_properties(v))
    elif isinstance(schema, list):
        for v in schema:
            out.extend(schema_properties(v))
    return out
