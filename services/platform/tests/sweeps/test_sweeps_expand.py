"""3.6 unit tests (no database): grid validation, expansion order, content addressing of the
variants, deterministic labels, and the report's metric extraction."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from nf_platform.pipelines.spec import PipelineVersionRow, parse_spec, pipeline_version_id
from nf_platform.sweeps import service as sw
from sweeps_helpers import planted_pipeline


def _base(doc=None) -> PipelineVersionRow:
    doc = doc or planted_pipeline()
    return PipelineVersionRow(
        tenant_id="t",
        name=doc["meta"]["name"],
        version=doc["meta"]["version"],
        pv_id=pipeline_version_id(doc),
        document=doc,
        created_by="u",
        created_at=datetime.now(UTC),
    )


def test_expansion_is_the_ordered_cartesian_product():
    base = _base()
    factors = sw.parse_grid(
        {"notch.freqs": [[50.0], [60.0]], "filter.l_freq": [1.0, 4.0, 10.0]}, base.document
    )
    vs = sw.expand(base, factors)
    assert [v.index for v in vs] == list(range(6))
    got = [(v.params["notch.freqs"][0], v.params["filter.l_freq"]) for v in vs]
    assert got == [(50.0, 1.0), (50.0, 4.0), (50.0, 10.0), (60.0, 1.0), (60.0, 4.0), (60.0, 10.0)]


def test_variant_differs_from_the_base_only_in_its_overrides():
    base = _base()
    (v,) = sw.expand(base, sw.parse_grid({"filter.l_freq": [4.0]}, base.document))
    parse_spec(v.document)  # a valid PipelineVersion document
    for s_base, s_var in zip(base.document["steps"], v.document["steps"], strict=True):
        diff = {k for k in s_base["params"] if s_base["params"][k] != s_var["params"][k]}
        assert diff == ({"l_freq"} if s_base["name"] == "filter" else set())
    assert v.document["seed"] == base.document["seed"]
    assert v.document["meta"]["version"] == base.version
    assert v.document["meta"]["name"].startswith(base.name + ".mv-")
    assert pipeline_version_id(v.document) != base.pv_id
    assert base.document["steps"][1]["params"]["l_freq"] == 1.0  # the base is not mutated


def test_a_grid_point_equal_to_the_base_has_the_base_id():
    base = _base()
    (v,) = sw.expand(base, sw.parse_grid({"filter.l_freq": [1.0]}, base.document))
    assert pipeline_version_id(v.document) == base.pv_id  # meta is not hashed


def test_labels_are_deterministic_and_distinct():
    base = _base()
    a = sw.variant_label(base.pv_id, {"filter.l_freq": 4.0})
    assert a == sw.variant_label(base.pv_id, {"filter.l_freq": 4.0})
    assert a != sw.variant_label(base.pv_id, {"filter.l_freq": 4.5})
    assert a != sw.variant_label("pv:sha256:" + "1" * 64, {"filter.l_freq": 4.0})
    assert len(a) == 12


def test_long_base_names_still_give_valid_variant_names():
    doc = planted_pipeline(name="a" * 100)
    base = _base(doc)
    (v,) = sw.expand(base, sw.parse_grid({"filter.l_freq": [2.0]}, doc))
    parse_spec(v.document)
    assert len(v.document["meta"]["name"]) <= 100


@pytest.mark.parametrize(
    "grid",
    [
        {"filter.l_freq": [float("nan")]},
        {"filter.l_freq": [1.0, 1]},  # 1 and 1.0 are the same canonical JSON number
        {"filter.l_freq": list(range(sw.MAX_LEVELS + 1))},
        {"bandpower.bands.x": [1]},
    ],
)
def test_bad_grids(grid):
    with pytest.raises(sw.SweepError) as e:
        sw.parse_grid(grid, planted_pipeline())
    assert e.value.status == 422


def test_metric_value_reads_only_finite_numbers_of_the_named_step():
    rec = {
        "execution": {
            "steps": [
                {"name": "decode", "info": {"accuracy": 0.75, "flag": True, "bad": "x"}},
                {"name": "other", "info": {"accuracy": 0.1}},
            ]
        }
    }
    assert sw.metric_value(rec, "decode", "accuracy") == 0.75
    assert sw.metric_value(rec, "decode", "flag") is None
    assert sw.metric_value(rec, "decode", "bad") is None
    assert sw.metric_value(rec, "decode", "missing") is None
    assert sw.metric_value(rec, "nosuch", "accuracy") is None
    assert sw.metric_value({}, "decode", "accuracy") is None


def test_sweep_state():
    assert sw.sweep_state(["queued", "queued"]) == "queued"
    assert sw.sweep_state(["queued", "succeeded"]) == "running"
    assert sw.sweep_state(["running"]) == "running"
    assert sw.sweep_state(["succeeded", "succeeded"]) == "succeeded"
    assert sw.sweep_state(["succeeded", "failed"]) == "partial"
    assert sw.sweep_state(["failed", "cancelled"]) == "failed"
