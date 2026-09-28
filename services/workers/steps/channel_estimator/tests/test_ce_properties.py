"""Property and edge tests (seeded random loops; hypothesis is not installed in this repo)."""

from __future__ import annotations

import random

import numpy as np
import pytest
from golden_io import participant_document
from nf_channel_estimator import EstimateParams, estimate, from_document
from nf_channel_estimator.attrition import p_k_ge, p_k_ge_bruteforce
from nf_channel_estimator.labels import class_vector, counts_of, territory

TAGS_PALM = ["", "D1p", "D2m-u+D2m-r", "D3d-dr+D3d-du", "D4p", "P2-mcp", "P3-mcp", "P5-mcp", "W"]
TAGS_DORS = ["", "D1d", "D2m", "D3p", "D5m", "D5p", "P-dr"]
FAST = {"null_draws": 50}


def doc(els: list[dict]) -> dict:
    return {"schema": "nf.pf-map/v1", "electrodes": els}


def random_map(rng: random.Random, n: int, arrays: int = 2) -> dict:
    els = []
    for i in range(n):
        palm, dors = rng.choice(TAGS_PALM), rng.choice(TAGS_DORS)
        if not (palm or dors):
            palm = "D1p"
        els.append(
            {
                "electrode_id": str(i),
                "array_id": f"A{i % arrays}",
                "palm_segment": palm,
                "dorsum_segment": dors,
                "x_mm": float(i % 8) * 0.4,
                "y_mm": float(i // 8) * 0.4,
            }
        )
    return doc(els)


def test_empty_map() -> None:
    r = estimate(from_document(doc([])), EstimateParams())
    d = r.to_dict()
    assert all(
        v["k_digit"] == 0 and v["k_territory"] == 0 for v in d["channel_counts"]["by_rule"].values()
    )
    for k in range(1, 7):
        assert r.p_k_at_least(k, "digit") == 0.0
        assert r.p_k_at_least(k, "territory") == 0.0
    assert r.p_k_at_least(0) == 1.0
    assert d["clustering"]["status"] == "skipped"
    assert d["diversity"]["n_eff_digit"] is None
    r2 = estimate(from_document(doc([])), EstimateParams(relabel=True))
    assert r2.to_dict()["relabelling"]["status"] == "skipped"


def test_only_non_pf_electrodes() -> None:
    els = [{"electrode_id": str(i), "array_id": "A", "has_pf": False} for i in range(5)]
    r = estimate(from_document(doc(els)), EstimateParams())
    assert r.k_digit() == 0 and r.p_k_at_least(1) == 0.0
    assert r.to_dict()["input_summary"]["electrodes_listed"] == 5


@pytest.mark.parametrize("seed", range(5))
def test_m_above_electrode_count_gives_zero(seed: int) -> None:
    rng = random.Random(seed)
    n = rng.randint(1, 12)
    r = estimate(from_document(random_map(rng, n)), EstimateParams(m=n + 1, **FAST))
    for rule in ("R1", "R2", "R3", "ray"):
        assert r.k_digit(rule) == 0 and r.k_territory(rule) == 0
    assert all(r.p_k_at_least(k) == 0.0 for k in range(1, 6))


@pytest.mark.parametrize("seed", range(10))
def test_survival_limits(seed: int) -> None:
    rng = random.Random(100 + seed)
    pf = from_document(random_map(rng, rng.randint(1, 40)))
    r0 = estimate(pf, EstimateParams(survival=0.0, **FAST))
    assert r0.p_k_at_least(1) == 0.0 and r0.p_k_at_least(1, "territory") == 0.0
    for rule in ("R1", "R2", "R3", "ray"):
        r1 = estimate(pf, EstimateParams(survival=1.0, rule=rule, **FAST))
        for level, k_obs in (("digit", r1.k_digit(rule)), ("territory", r1.k_territory(rule))):
            assert r1.p_k_at_least(k_obs, level) == 1.0  # type: ignore[arg-type]
            assert r1.p_k_at_least(k_obs + 1, level) == 0.0  # type: ignore[arg-type]


@pytest.mark.parametrize("seed", range(10))
def test_monotone_in_k_and_p(seed: int) -> None:
    rng = random.Random(200 + seed)
    pf = from_document(random_map(rng, rng.randint(2, 60)))
    grid = [0.0, 0.1, 0.3, 0.47, 0.62, 0.8, 0.95, 1.0]
    prev = None
    for p in grid:
        r = estimate(pf, EstimateParams(survival=p, **FAST))
        for level, top in (("digit", 5), ("territory", 6)):
            vals = [r.p_k_at_least(k, level) for k in range(0, top + 2)]  # type: ignore[arg-type]
            assert all(a >= b - 1e-15 for a, b in zip(vals, vals[1:], strict=False))
        cur = [r.p_k_at_least(k) for k in range(1, 6)]
        if prev is not None:
            assert all(c >= q - 1e-12 for c, q in zip(cur, prev, strict=True))
        prev = cur


def test_dp_equals_bruteforce_random() -> None:
    g = np.random.default_rng(7)
    worst = 0.0
    for _ in range(60):
        nv = [int(v) for v in g.integers(0, 5, int(g.integers(1, 7)))]
        p = float(g.random())
        for m in (1, 2, 3):
            for k in range(0, len(nv) + 2):
                worst = max(worst, abs(p_k_ge(nv, p, m, k) - p_k_ge_bruteforce(nv, p, m, k)))
    assert worst < 1e-12


def test_dp_equals_bruteforce_on_small_random_maps() -> None:
    rng = random.Random(3)
    for _ in range(25):
        pf = from_document(random_map(rng, rng.randint(0, 10)))
        c = counts_of(territory(e.palm_segment, e.dorsum_segment, "R1") for e in pf.pf_electrodes)
        p = rng.random()
        r = estimate(pf, EstimateParams(survival=p, **FAST))
        for level, terr in (("digit", False), ("territory", True)):
            nv = class_vector(c, terr)
            for k in range(1, len(nv) + 1):
                bf = p_k_ge_bruteforce(nv, p, 2, k)
                assert abs(r.p_k_at_least(k, level) - bf) < 1e-12  # type: ignore[arg-type]


def test_planted_truth_c2() -> None:
    """Research control C2: D1..D4 = 6,4,1,2, PALM = 3 -> K_digit 3, K_terr 4, N_eff 256/66."""
    sizes = {"D1p": 6, "D2m": 4, "D3p": 1, "D4p": 2, "P3-mcp": 3}
    els, i = [], 0
    for tag, n in sizes.items():
        for _ in range(n):
            els.append({"electrode_id": str(i), "array_id": "A", "palm_segment": tag})
            i += 1
    r = estimate(from_document(doc(els)), EstimateParams(**FAST))
    assert r.k_digit() == 3 and r.k_territory() == 4
    assert abs(r.to_dict()["diversity"]["n_eff_digit"] - 256 / 66) < 1e-12
    assert abs(r.p_k_at_least(3) - p_k_ge_bruteforce([6, 4, 1, 2, 0], 0.62, 2, 3)) < 1e-12


@pytest.mark.parametrize("part", ["C1", "P2", "P3"])
def test_label_shuffle_within_array_invariants(part: str) -> None:
    """Research control C1: permuting labels among electrodes of an array keeps K and N_eff."""
    base = participant_document(part)
    r0 = estimate(from_document(base), EstimateParams(null_draws=200)).to_dict()
    rng = random.Random(11)
    for _ in range(20):
        d = {**base, "electrodes": [dict(e) for e in base["electrodes"]]}
        for a in {e["array_id"] for e in d["electrodes"]}:
            idx = [i for i, e in enumerate(d["electrodes"]) if e["array_id"] == a]
            labs = [
                (d["electrodes"][i]["has_pf"], d["electrodes"][i]["palm_segment"],
                 d["electrodes"][i]["dorsum_segment"])
                for i in idx
            ]  # fmt: skip
            rng.shuffle(labs)
            for i, (h, p, q) in zip(idx, labs, strict=True):
                d["electrodes"][i].update(has_pf=h, palm_segment=p, dorsum_segment=q)
        r = estimate(from_document(d), EstimateParams(null_draws=200)).to_dict()
        assert r["channel_counts"]["by_rule"] == r0["channel_counts"]["by_rule"]
        soft, soft0 = r["diversity"].pop("n_eff_soft"), r0["diversity"]["n_eff_soft"]
        assert abs(soft - soft0) < 1e-12  # float sum order differs; value is invariant
        assert r["diversity"] == {k: v for k, v in r0["diversity"].items() if k != "n_eff_soft"}
        assert r["attrition"] == r0["attrition"]
        assert r["clustering"]["null_b_pooled"] == r0["clustering"]["null_b_pooled"]


def test_deterministic_for_fixed_seed_and_seed_sensitive() -> None:
    pf = from_document(participant_document("P3"))
    a = estimate(pf, EstimateParams(seed=5, null_draws=500, relabel=True, relabel_draws=200))
    b = estimate(pf, EstimateParams(seed=5, null_draws=500, relabel=True, relabel_draws=200))
    c = estimate(pf, EstimateParams(seed=6, null_draws=500, relabel=True, relabel_draws=200))
    assert a.to_dict() == b.to_dict()
    assert a.to_dict()["clustering"] != c.to_dict()["clustering"]


def test_input_hash_invariant_to_key_order_and_format() -> None:
    d = participant_document("C1")
    rev = {k: d[k] for k in reversed(list(d))}
    rev["electrodes"] = [{k: e[k] for k in reversed(list(e))} for e in d["electrodes"]]
    h1 = from_document(d).sha256()
    assert from_document(rev).sha256() == h1
    # explicit defaults hash like omitted ones
    d2 = {**d, "electrodes": [dict(e) for e in d["electrodes"]]}
    for e in d2["electrodes"]:
        if e["has_pf"]:
            del e["has_pf"]
    assert from_document(d2).sha256() == h1
    # changing a label changes the hash
    d3 = {**d, "electrodes": [dict(e) for e in d["electrodes"]]}
    d3["electrodes"][0]["palm_segment"] = "D1p"
    assert from_document(d3).sha256() != h1
