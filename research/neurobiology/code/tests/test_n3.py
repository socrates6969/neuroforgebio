"""N3 tests (prereg N3 §3 step 2): the pooled statistic's exactness on a hand fixture; the montage assertion (E1); the
§4.4 PL-B-code violation test; plus the byte-identity of the chunked synthetic EDF writer, the null re-computation, the
FP grid, the gate logic and the stream rebinding.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. Synthetic in-memory / temporary data only (stream key (98, ...)).
"""
import datetime as dt
import hashlib
from fractions import Fraction

import numpy as np
import pytest

from nfharness.config import CHANNEL_LABELS_23, TAU_GRID
from nfharness.data import FileRecord, write_edf
from nfharness.errors import ThresholdSelectionError
from nfharness.postprocess import TaggedScores, hypothesis_mask, select_tau

import n3
from n3.montage import MontageError, assert_montage
from n3.pooled import f1_exact, f1_float, fisher, mid_p, null_draws_full, pooled_test
from n3.synth import write_edf_chunked
from n3.verdict import event_gate, fp_grid, harness_verdict, model_overall, pla_trips, window_gate


# --------------------------------------------------------------------------------------------- pooled statistic
def test_pooled_sigmaF1_hand_fixture():
    # replicate 1: obs (TP, FP, N_ref) = (1, 0, 1) -> F1 = 1; nulls -> 0, 2/3, 1
    # replicate 2: obs (0, 1, 1) -> F1 = 0; nulls -> 0, 1, 2/3
    obs = [(1, 0, 1), (0, 1, 1)]
    nulls = [np.array([(0, 0, 1), (1, 1, 1), (1, 0, 1)]), np.array([(0, 0, 1), (1, 0, 1), (1, 1, 1)])]
    r = pooled_test(obs, nulls, "F1")
    # T = 1; T_null = [0, 5/3, 5/3]; #{>= 1} = 2 -> p_up = 3/4; #{<= 1} = 1 -> p_lo = 2/4
    assert r["T_exact"] == "1"
    assert r["p_up"] == 3 / 4 and r["p_lo"] == 2 / 4
    assert r["null_mean"] == pytest.approx(10 / 9)
    rt = pooled_test(obs, nulls, "TP")
    # TP: T = 1; null = [0, 2, 2] -> p_up 3/4, p_lo 2/4
    assert rt["T"] == 1 and rt["p_up"] == 3 / 4 and rt["p_lo"] == 2 / 4


def test_pooled_exact_ties_no_float_error():
    # exact fractions: F1 = 2TP / (2TP + FP + (N_ref - TP))
    assert f1_exact(1, 2, 2) == Fraction(2, 5)
    assert f1_exact(1, 0, 5) == Fraction(1, 3)
    assert f1_exact(0, 0, 0) == 0
    assert f1_float(1, 0, 5) == 2 / 6
    # 3 replicates of 1/10-type sums: obs sum = 1/3 + 1/3 + 1/3 = 1 exactly; null draw b=0 equals it exactly
    obs = [(1, 0, 5)] * 3
    nulls = [np.array([(1, 0, 5), (0, 0, 5)])] * 3
    r = pooled_test(obs, nulls, "F1")
    assert r["T_exact"] == "1"
    assert r["p_up"] == 2 / 3 and r["p_lo"] == 3 / 3


def test_pooled_empty_is_nan_and_fails_gate():
    r = pooled_test([], [], "F1")
    assert r["n_retained"] == 0 and r["p_up"] != r["p_up"]
    assert event_gate(r["p_up"], r["p_lo"]) is False


def test_pooled_single_replicate_equals_its_own_exact_p():
    g = np.random.default_rng(np.random.SeedSequence(20261001, spawn_key=(98, 0)))
    arr = np.stack([g.integers(0, 3, 199), g.integers(0, 6, 199), np.full(199, 4)], axis=1)
    obs = (1, 3, 4)
    r = pooled_test([obs], [arr], "F1")
    f = np.array([f1_float(*x) for x in arr])
    o = f1_float(*obs)
    assert r["p_up"] == (1 + int(np.sum(f >= o))) / 200
    assert r["p_lo"] == (1 + int(np.sum(f <= o))) / 200


def test_mid_p_and_fisher_hand():
    arr = np.array([(0, 0, 1), (1, 0, 1), (1, 0, 1)])     # F1 = 0, 1, 1
    assert mid_p((1, 0, 1), arr) == (0 + 0.5 * (2 + 1)) / 4
    assert mid_p((0, 0, 1), arr) == (2 + 0.5 * (1 + 1)) / 4
    p, n = fisher([0.5, float("nan")])
    assert n == 1 and p == pytest.approx(0.5)


def test_null_draws_full_mirrors_n1b():
    from n1b.ncp import EventArm, ScoreSide, null_draws
    g = np.random.default_rng(np.random.SeedSequence(20261001, spawn_key=(98, 1)))
    recs = [FileRecord("x", "a", "<m>", 0.0, 1500), FileRecord("x", "b", "<m>", 1600.0, 1200)]
    p = {r.name: g.random(r.duration - 1) for r in recs}
    hyp = {r.name: hypothesis_mask(p[r.name], 0.7, r.duration) for r in recs}
    ts = ScoreSide(recs, p)
    arms = {"rm": EventArm(ts, hyp)}
    lens, order = [1500, 1200], [60, 40]
    key = (98, 2)
    TA1, TE1, _ = null_draws(ts, arms, lens, order, np.random.default_rng(np.random.SeedSequence(20261001, spawn_key=key)), 40)
    TA2, cnt = null_draws_full(ts, arms, lens, order, np.random.default_rng(np.random.SeedSequence(20261001, spawn_key=key)), 40)
    assert np.array_equal(TA1, TA2)
    assert np.array_equal(TE1["rm"], np.array([f1_float(*r) for r in cnt["rm"]]))


# --------------------------------------------------------------------------------------------- montage E1
def _edf(path, labels):
    x = np.zeros((len(labels), 256 * 3), dtype=np.float32)
    write_edf(str(path), x, 256, list(labels), dt.datetime(2000, 1, 1))
    return str(path)


def test_montage_assertion_accepts_standard_23(tmp_path):
    p = _edf(tmp_path / "ok.edf", CHANNEL_LABELS_23)
    out = assert_montage([p])
    assert out[p]["labels_equal_standard_23"] is True


def test_montage_assertion_rejects_swapped_order(tmp_path):
    lab = list(CHANNEL_LABELS_23)
    lab[0], lab[1] = lab[1], lab[0]
    p = _edf(tmp_path / "swap.edf", lab)
    with pytest.raises(MontageError):
        assert_montage([p])


def test_montage_assertion_rejects_extra_or_dummy_channel(tmp_path):
    p = _edf(tmp_path / "extra.edf", list(CHANNEL_LABELS_23) + ["-"])
    with pytest.raises(MontageError):
        assert_montage([p])
    p2 = _edf(tmp_path / "short.edf", list(CHANNEL_LABELS_23)[:22])
    with pytest.raises(MontageError):
        assert_montage([p2])


# --------------------------------------------------------------------------------------------- §4.4 PL-B-code
def test_PLB_code_select_tau_raises_on_test_tagged_scores():
    """PL-B-code (formal): the N2 threshold selector must refuse test-tagged scores."""
    g = np.random.default_rng(np.random.SeedSequence(20261001, spawn_key=(98, 3)))
    scores = {"t.edf": g.random(599)}
    durs = {"t.edf": 600}
    for tag in ("test", "test_phantom", "train", ""):
        with pytest.raises(ThresholdSelectionError):
            select_tau(TaggedScores(tag, scores, durs), lambda masks: 0.0)
    with pytest.raises(ThresholdSelectionError):
        select_tau({"t.edf": scores["t.edf"]}, lambda masks: 0.0)
    tau, _ = select_tau(TaggedScores("train_oof", scores, durs), lambda masks: 0.0)   # control: accepted
    assert tau == TAU_GRID[0]


# --------------------------------------------------------------------------------------------- writer, grid, gate
def test_chunked_writer_byte_identical(tmp_path):
    g = np.random.default_rng(np.random.SeedSequence(20261001, spawn_key=(98, 4)))
    x = (g.standard_normal((23, 256 * 25)) * 300).astype(np.float32)   # includes clipping beyond +/-800
    st = dt.datetime(2053, 10, 23, 8, 57, 57)
    a, b = tmp_path / "a.edf", tmp_path / "b.edf"
    write_edf(str(a), x, 256, list(CHANNEL_LABELS_23), st)
    write_edf_chunked(str(b), x, 256, list(CHANNEL_LABELS_23), st, chunk_s=7)
    assert a.read_bytes() == b.read_bytes()


def test_fp_grid_equals_prereg_table():
    assert fp_grid(14426 / 3600.0) == n3.FP_GRID_PREREG["chb23"] == (4, 8)
    assert fp_grid(7200 / 3600.0) == n3.FP_GRID_PREREG["chb24"] == (2, 5)


def test_split_hash_literal():
    s = ("chb23;train=chb23_06.edf,chb23_08.edf;test=chb23_09.edf\n"
         "chb24;train=chb24_01.edf,chb24_03.edf;test=chb24_04.edf,chb24_06.edf")
    assert hashlib.sha256(s.encode()).hexdigest() == n3.EXPECTED_SPLIT_HASH_N3


def test_gate_logic():
    assert window_gate(0.5, 0.01, 1, 20) == (True, True)
    assert window_gate(0.002, 0.5, 0, 20) == (False, True)
    assert window_gate(0.5, 0.5, 2, 20) == (True, False)
    assert window_gate(float("nan"), 0.5, 0, 20)[0] is False
    assert event_gate(0.0025, 0.9) is True and event_gate(0.0024, 0.9) is False
    assert pla_trips(0.0024) is True and pla_trips(0.0025) is False and pla_trips(float("nan")) is False
    items = {k: True for k in ["step2_pytest", "step3_dry_run", "step5_real_run_complete", "step6_rerun_identical",
                               "V1-A", "V2-A", "V1-E", "C3prime_i", "C3prime_ii", "PL-A_trips_T_A",
                               "PL-B-code_raises", "PL-C_trips", "PL-B_specificity"]}
    assert harness_verdict(items) == ("PASS", [], [])
    bad = dict(items, **{"PL-A_trips_T_A": False})
    v, f, fl = harness_verdict(bad)
    assert v == "FAIL" and f == ["PL-A_trips_T_A"] and "controls powerless" in fl[0]
    v, f, fl = harness_verdict(dict(items, **{"V1-E": False}))
    assert v == "FAIL" and any("possible leak" in x for x in fl)
    assert model_overall(["PASS", "PASS"]) == "PASS"
    assert model_overall(["FAIL", "FAIL"]) == "FAIL"
    assert model_overall(["PASS", "FAIL"]) == "INCONCLUSIVE"
    assert model_overall(["PASS", "INCONCLUSIVE"]) == "INCONCLUSIVE"


def test_stream_rebinding_restores_n1b_constants():
    from n1b import ncp
    before = (ncp.K_TRAIN_PH, ncp.K_TEST_PH, ncp.K_NULL, ncp.K_PLA, ncp.PL_A_FRAC)
    with n3.n3_streams() as m:
        assert (m.K_TRAIN_PH, m.K_TEST_PH, m.K_NULL, m.K_PLA) == (20, 21, 22, 23)
        with n3.pla_fraction(0.10):
            assert ncp.PL_A_FRAC == 0.10
        assert ncp.PL_A_FRAC == 0.25
    assert (ncp.K_TRAIN_PH, ncp.K_TEST_PH, ncp.K_NULL, ncp.K_PLA, ncp.PL_A_FRAC) == before == (10, 11, 12, 13, 0.25)
    a = n3.rng(22, 1, 3).random(3)
    b = np.random.default_rng(np.random.SeedSequence(20261001, spawn_key=(22, 1, 3))).random(3)
    assert np.array_equal(a, b)
