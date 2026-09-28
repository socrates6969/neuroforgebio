"""Golden tests: reproduce the reviewed research P6 numbers from the pinned digitised data.

Reference values come from ``research/somatosensory/code/results/p6_empirical_channels.json`` (read
in place, hash pinned). Exact quantities are compared with ``==`` or to 1e-12; random nulls and
relabelling are reproduced bit for bit by replaying the research RNG stream layout.
"""

from __future__ import annotations

import csv
import io
from functools import cache

import numpy as np
import pytest
from golden_io import (
    GOLDEN,
    PARTICIPANTS,
    PINNED,
    PINNED_RESULTS,
    RESEARCH_DATA,
    RESEARCH_RESULTS,
    lf_bytes,
    lf_sha256,
    participant_document,
    research_results,
)
from nf_channel_estimator import EstimateParams, estimate, from_document
from nf_channel_estimator.estimate import streams
from nf_channel_estimator.nulls import run_nulls
from nf_channel_estimator.reference import load_reference
from nf_channel_estimator.relabel import run_relabelling

P_SENS = (0.47, 0.54, 0.62, 0.64, 0.75, 1.0)
XS = (0.05, 0.10, 0.20)
RULE_KEYS = {"R1": "R1", "R2": "R2", "R3": "R3", "ray": "ray"}


@cache
def res() -> dict:
    return research_results()


@cache
def result(part: str):
    return estimate(from_document(participant_document(part)), EstimateParams(relabel=False))


def pkey(p: float) -> str:
    return "1.0" if p == 1.0 else str(p)


# ------------------------------------------------------------------ input pins
@pytest.mark.parametrize("name", sorted(PINNED))
def test_golden_input_hash_pinned(name: str) -> None:
    assert lf_sha256(GOLDEN / name) == PINNED[name]


@pytest.mark.parametrize("name", sorted(PINNED))
def test_research_copy_matches_when_present(name: str) -> None:
    src = RESEARCH_DATA / name
    if not src.exists():
        pytest.skip("research data folder is git-ignored; vendored copy is the pinned input")
    assert lf_sha256(src) == PINNED[name]


@pytest.mark.parametrize("name", sorted(PINNED_RESULTS))
def test_research_results_hash_pinned(name: str) -> None:
    assert lf_sha256(RESEARCH_RESULTS / name) == PINNED_RESULTS[name]


# ------------------------------------------------------------------ counts
def test_headline_k_digit_r1_m2() -> None:
    assert [result(q).k_digit("R1") for q in PARTICIPANTS] == [4, 2, 4]
    assert [result(q).k_territory("R1") for q in PARTICIPANTS] == [4, 3, 5]
    assert [result(q).k_digit("R2") for q in PARTICIPANTS] == [4, 2, 4]
    assert [result(q).k_digit("R3") for q in PARTICIPANTS] == [4, 1, 3]
    assert [result(q).k_digit("ray") for q in PARTICIPANTS] == [4, 4, 4]


@pytest.mark.parametrize("part", PARTICIPANTS)
@pytest.mark.parametrize("rule", sorted(RULE_KEYS))
@pytest.mark.parametrize("m", [1, 2, 3])
def test_counts_and_k_every_rule_and_m(part: str, rule: str, m: int) -> None:
    ref = res()["observed"][part][rule]
    r = estimate(
        from_document(participant_document(part)), EstimateParams(m=m, null_draws=0)
    ).to_dict()
    got = r["channel_counts"]["by_rule"][rule]
    assert {k: v for k, v in got["territory_counts"].items() if v} == ref["counts"]
    assert got["k_digit"] == ref["K_digit"][str(m)]
    assert got["k_territory"] == ref["K_terr"][str(m)]


@pytest.mark.parametrize("part", PARTICIPANTS)
def test_population_and_per_array(part: str) -> None:
    obs = res()["observed"][part]
    r = result(part).to_dict()
    assert r["input_summary"]["pf_electrodes"] == obs["N_PF"] == 62
    assert r["input_summary"]["electrodes_listed"] == obs["N_wired"] == 64
    for a in r["input_summary"]["arrays"]:
        den = obs["per_array_denominators"][a["array_id"]]
        assert (a["electrodes_listed"], a["pf_electrodes"]) == (den["wired"], den["PF"])
    for a in r["channel_counts"]["per_array_R1"]:
        assert a["k_digit"] == obs["per_array"][a["array_id"]]["K_digit"]["2"]
        assert a["k_territory"] == obs["per_array"][a["array_id"]]["K_terr_m2"]
    assert r["channel_counts"]["second_array_gain_R1"] == obs["G_second_array_gain_m2"] == 1


@pytest.mark.parametrize("part", PARTICIPANTS)
def test_neff_exact(part: str) -> None:
    obs = res()["observed"][part]["R1"]
    d = result(part).to_dict()["diversity"]
    assert d["n_eff_digit"] == obs["N_eff_digit"]
    assert d["n_eff_segment"] == obs["N_eff_seg"]
    assert d["n_eff_digit_bias_corrected"] == obs["N_eff_digit_bc"]
    assert d["n_eff_segment_bias_corrected"] == obs["N_eff_seg_bc"]
    assert d["n_segment_classes"] == obs["n_seg_classes"]
    assert d["n_eff_soft"] == pytest.approx(obs["N_eff_soft"], abs=1e-12)


def test_neff_rounded_headlines() -> None:
    dig = [round(result(q).to_dict()["diversity"]["n_eff_digit"], 2) for q in PARTICIPANTS]
    seg = [round(result(q).to_dict()["diversity"]["n_eff_segment"], 2) for q in PARTICIPANTS]
    assert dig == [2.67, 1.43, 3.70]
    assert seg == [5.15, 4.12, 6.24]


# ------------------------------------------------------------------ attrition
def test_attrition_headlines() -> None:
    assert round(result("C1").p_k_at_least(4), 3) == 0.980
    assert round(result("P3").p_k_at_least(4), 3) == 0.782
    assert round(result("P2").p_k_at_least(2), 3) == 0.383


@pytest.mark.parametrize("part", PARTICIPANTS)
@pytest.mark.parametrize("p", P_SENS)
def test_attrition_exact_vs_research_json(part: str, p: float) -> None:
    ex = res()["attrition"][part][pkey(p)]["exact"]
    r = estimate(
        from_document(participant_document(part)), EstimateParams(survival=p, null_draws=0)
    )
    for lv in (2, 3, 4, 5):
        assert abs(r.p_k_at_least(lv, "digit") - ex[str(lv)]) <= 1e-12
    assert abs(r.p_k_at_least(6, "territory") - ex["6"]) <= 1e-12


@pytest.mark.parametrize("part", PARTICIPANTS)
def test_attrition_sensitivity_rows_in_one_result(part: str) -> None:
    att = result(part).to_dict()["attrition"]
    assert [row["survival"] for row in att["sensitivity"]] == list(P_SENS)
    for row in att["sensitivity"]:
        ex = res()["attrition"][part][pkey(row["survival"])]["exact"]
        for lv in (2, 3, 4, 5):
            assert abs(row["digit_level"][lv - 1]["probability"] - ex[str(lv)]) <= 1e-12
        assert abs(row["territory_level"][5]["probability"] - ex["6"]) <= 1e-12


def test_sensitivity_rounded_rows() -> None:
    def row(part: str, lv: int) -> list[float]:
        sens = result(part).to_dict()["attrition"]["sensitivity"]
        return [round(s["digit_level"][lv - 1]["probability"], 3) for s in sens]

    assert row("C1", 4) == [0.866, 0.939, 0.980, 0.985, 0.998, 1.0]
    assert row("P3", 4) == [0.493, 0.639, 0.782, 0.812, 0.934, 1.0]
    assert row("P2", 2) == [0.214, 0.288, 0.383, 0.409, 0.562, 1.0]


def test_attrition_curve_grid() -> None:
    curve = res()["attrition_curve"]
    for part in PARTICIPANTS:
        pf = from_document(participant_document(part))
        for idx in range(0, len(curve["p"]), 5):
            r = estimate(pf, EstimateParams(survival=curve["p"][idx], null_draws=0))
            for lv in ("2", "3", "4", "5"):
                assert abs(r.p_k_at_least(int(lv)) - curve["P"][part][lv][idx]) <= 1e-12


# ------------------------------------------------------------------ clustering nulls
def _replay_research_nulls() -> dict[str, dict]:
    """Replay the research consumption order: per participant Null A, Null B, Null A no-wrist."""
    ref = load_reference()
    g = streams(20260926)
    out = {}
    for part in PARTICIPANTS:
        d = result(part).to_dict()
        out[part] = run_nulls(
            g["nullA"],
            g["nullB"],
            ref,
            62,
            10000,
            d["diversity"]["n_eff_segment"],
            d["diversity"]["n_eff_digit"],
            d["channel_counts"]["by_rule"]["R1"]["k_digit"],
            2,
        )
    return out


def _check_null_block(got: dict, ref: dict) -> None:
    for lvl, rk in (("segment_level", "seg"), ("digit_level", "digit")):
        assert got[lvl]["observed"] == ref[rk]["obs"]
        assert got[lvl]["null_median"] == ref[rk]["null_median"]
        assert got[lvl]["ratio"] == ref[rk]["ratio"]
        assert got[lvl]["p_value"] == ref[rk]["p"]
    assert got["k_digit"]["observed"] == ref["K_digit_m2"]["obs"]
    assert got["k_digit"]["null_median"] == ref["K_digit_m2"]["null_median"]
    assert got["k_digit"]["p_value"] == ref["K_digit_m2"]["p"]


def test_clustering_public_api_c1_bit_exact() -> None:
    c = result("C1").to_dict()["clustering"]
    ref = res()["C4_nulls"]["C1"]
    assert c["seed"] == res()["seed"] == 20260926 and c["draws"] == 10000
    _check_null_block(c["null_a_area"], ref["nullA_area"])
    _check_null_block(c["null_b_pooled"], ref["nullB_pooled"])
    assert c["null_a_area_no_wrist"]["null_median"] == ref["nullA_noWrist_seg"]["null_median"]
    assert c["null_a_area_no_wrist"]["p_value"] == ref["nullA_noWrist_seg"]["p"]


def test_clustering_all_participants_bit_exact_with_research_stream_order() -> None:
    rep = _replay_research_nulls()
    for part in PARTICIPANTS:
        ref = res()["C4_nulls"][part]
        _check_null_block(rep[part]["null_a_area"], ref["nullA_area"])
        _check_null_block(rep[part]["null_b_pooled"], ref["nullB_pooled"])
        nw = rep[part]["null_a_area_no_wrist"]
        assert nw["null_median"] == ref["nullA_noWrist_seg"]["null_median"]
        assert nw["p_value"] == ref["nullA_noWrist_seg"]["p"]


def test_clustering_rounded_headlines() -> None:
    rep = _replay_research_nulls()

    def r2(block: str, lvl: str) -> list[float]:
        return [round(rep[q][block][lvl]["ratio"], 2) for q in PARTICIPANTS]

    assert r2("null_b_pooled", "segment_level") == [0.54, 0.43, 0.65]
    assert r2("null_b_pooled", "digit_level") == [0.72, 0.38, 0.99]
    assert r2("null_a_area", "segment_level") == [0.29, 0.23, 0.35]


# ------------------------------------------------------------------ relabelling
def test_relabelling_all_participants_bit_exact_with_research_stream_order() -> None:
    ref = load_reference()
    g = streams(20260926)["rel"]
    for part in PARTICIPANTS:
        pf = from_document(participant_document(part)).pf_electrodes
        k_obs = res()["observed"][part]["R1"]["K_digit"]["2"]
        levels = run_relabelling(g, ref, [e.dominant_segment for e in pf], XS, 5000, 2, k_obs)
        for lv, x in zip(levels, XS, strict=True):
            rr = res()["relabelling"][part][str(x)]
            assert lv["electrodes_relabelled"] == rr["k_relabelled"]
            for L in (2, 3, 4, 5):
                assert lv["p_k_digit_at_least"][L - 1] == rr["P_rel"][str(L)]
            assert lv["p_k_territory_at_least"][5] == rr["P_rel"]["6"]
            assert lv["p_k_digit_within_1_of_observed"] == rr["P_change_le1"]
            assert lv["k_digit_distribution"] == {k: v for k, v in rr["K_digit_dist"].items()}


def test_relabelling_public_api_c1_matches() -> None:
    r = estimate(from_document(participant_document("C1")), EstimateParams(relabel=True))
    rel = r.to_dict()["relabelling"]
    assert rel["status"] == "computed"
    for lv, x in zip(rel["levels"], XS, strict=True):
        rr = res()["relabelling"]["C1"][str(x)]
        for L in (2, 3, 4, 5):
            assert lv["p_k_digit_at_least"][L - 1] == rr["P_rel"][str(L)]


# ------------------------------------------------------------------ per-participant CSV
def test_per_participant_csv_row() -> None:
    rows = list(
        csv.DictReader(io.StringIO(lf_bytes(RESEARCH_RESULTS / "p6_per_participant.csv").decode()))
    )
    for row in rows:
        r = result(row["participant"]).to_dict()
        by = r["channel_counts"]["by_rule"]
        assert int(row["K_digit_m2"]) == by["R1"]["k_digit"]
        assert int(row["K_terr_m2"]) == by["R1"]["k_territory"]
        assert int(row["K_digit_m2_R2"]) == by["R2"]["k_digit"]
        assert int(row["K_digit_m2_R3"]) == by["R3"]["k_digit"]
        assert int(row["K_digit_m2_ray"]) == by["ray"]["k_digit"]
        assert float(row["N_eff_digit"]) == round(r["diversity"]["n_eff_digit"], 4)
        assert float(row["Patt_L4_p0.62"]) == round(
            np.float64(r["attrition"]["digit_level"]["p_k_at_least"][3]["probability"]), 6
        )
