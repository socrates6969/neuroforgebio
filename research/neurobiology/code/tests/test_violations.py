"""N1 (d): one deliberate-violation test per guard (F1-F9, S1, S5, S7). Each must raise its NAMED exception.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
The 12 IDs are listed in VIOLATION_IDS; run_n1.py counts a guard as caught only if every test tagged with its ID passes.
"""
import copy

import numpy as np
import pytest

from nfharness import config as C
from nfharness import errors as E
from nfharness.data import FileRecord
from nfharness.features import FEATURE_NAMES, assert_whitelist
from nfharness.labels import LabelVault
from nfharness.model import ZScore, assert_config_locked, resample_training
from nfharness.pipeline import TrainLabels, fit, predict, run_split
from nfharness.postprocess import TaggedScores, hypothesis_mask, select_tau
from nfharness.scoring import event_score
from nfharness.splits import (Split, assert_causal, assert_split_hash, assert_subject_disjoint, causal_splits,
                              random_window_split)
from nfharness.windows import assert_buffer, assert_windows_in_file

VIOLATION_IDS = ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "S1", "S5", "S7"]


def _vault(syn):
    return LabelVault(syn["ann"], syn["durations"], protected_files=syn["split"].test_names, name="t")


def _all(r):
    return np.arange(r.duration - 1)


def test_honest_pipeline_is_silent(syn):
    """Control: the honest pipeline on synthetic data raises nothing and scores all test windows."""
    res = run_split(syn["split"], syn["feats"], _vault(syn), [[r] for r in syn["split"].train])
    assert all(res["p"][r.name].size == r.duration - 1 for r in syn["split"].test)


# ---------------------------------------------------------------- F1
@pytest.mark.parametrize("vid", ["F1"])
def test_F1_normaliser_fitted_on_train_plus_test(syn, vid):
    sp = syn["split"]
    v = LabelVault(syn["ann"], syn["durations"], name="t-F1")   # labels readable: the violation is the normaliser
    lab = lambda f, i: v.train_window_labels(f, i)  # noqa: E731
    parts = [(r.name, _all(r)) for r in sp.train + sp.test]
    model = fit(syn["feats"], lab, parts)            # z-scorer (and model) fitted on train + test windows
    with pytest.raises(E.NormaliserLeakError):
        predict(model, syn["feats"], [(r.name, _all(r)) for r in sp.test])
    z = ZScore().fit(np.zeros((4, 2)), {"a": np.arange(4)})
    with pytest.raises(E.NormaliserLeakError):
        z.transform(np.zeros((2, 2)), {"a": np.array([2, 3])})


# ---------------------------------------------------------------- F2
def test_F2_test_file_in_inner_cv(syn):
    sp = syn["split"]
    bad = Split("future_leak", sp.train + [sp.test[0]], sp.test, label="bad")
    with pytest.raises(E.ConfigLockError):
        run_split(bad, syn["feats"], _vault(syn), [[r] for r in bad.train])


def test_F2_change_C(syn):
    cfg = copy.deepcopy(C.LOCKED_CONFIG)
    cfg["classifier"]["C"] = 0.5
    with pytest.raises(E.ConfigLockError):
        assert_config_locked(cfg)
    assert_config_locked(C.LOCKED_CONFIG)   # the locked config itself passes


# ---------------------------------------------------------------- F3
def test_F3_tau_on_test_scores(syn):
    sp = syn["split"]
    scores = TaggedScores("test", {r.name: np.random.default_rng(0).random(r.duration - 1) for r in sp.test},
                          {r.name: r.duration for r in sp.test})
    with pytest.raises(E.ThresholdSelectionError):
        select_tau(scores, lambda masks: 0.0)


def test_F3_k_equals_3():
    with pytest.raises(E.ThresholdSelectionError):
        hypothesis_mask(np.ones(99), 0.5, 100, k=3, n=5)


# ---------------------------------------------------------------- F4
def test_F4_window_spanning_file_end():
    with pytest.raises(E.WindowBoundaryError):
        assert_windows_in_file(np.array([0, 898]), np.array([2, 900 + 1]), 900)


def test_F4_train_window_5s_before_test_file(syn):
    te = syn["split"].test[0]
    st = np.array([te.t_start - 7.0])
    with pytest.raises(E.WindowBoundaryError):
        assert_buffer([("syn", st, st + 2)], [te])     # window ends 5 s before the test file starts


# ---------------------------------------------------------------- F5
def test_F5_oversample_from_train_plus_test(syn):
    sp = syn["split"]
    ids = {r.name: _all(r)[:10] for r in sp.train + sp.test}
    with pytest.raises(E.ResamplingLeakError):
        resample_training(ids, sp.train_names, None)


# ---------------------------------------------------------------- F6
def test_F6_later_file_moved_into_training(syn):
    recs = syn["recs"]
    bad = Split("causal", recs[:4] + [recs[5]], [recs[4]], label="bad")   # like moving chb01_26 into training
    with pytest.raises(E.CausalSplitError):
        assert_causal(bad)
    with pytest.raises(E.CausalSplitError):
        run_split(bad, syn["feats"], LabelVault(syn["ann"], syn["durations"], protected_files=[recs[4].name]),
                  [[r] for r in bad.train])


# ---------------------------------------------------------------- F7
@pytest.mark.parametrize("extra", ["file_index", "time_of_day"])
def test_F7_metadata_column(extra):
    with pytest.raises(E.FeatureWhitelistError):
        assert_whitelist(list(FEATURE_NAMES) + [extra])
    assert assert_whitelist(list(FEATURE_NAMES))


# ---------------------------------------------------------------- F8
def test_F8_read_test_labels_in_training(syn):
    sp = syn["split"]
    v = _vault(syn)
    with pytest.raises(E.TestLabelAccessError):
        TrainLabels(v, sp.train + [sp.test[0]])            # the training routine reads a test file's labels
    with pytest.raises(E.TestLabelAccessError):
        v.train_window_labels(sp.test[0].name)
    with pytest.raises(E.TestLabelAccessError):
        v.scorer_mask(sp.test[0].name, key=object(), purpose="not the scorer")
    assert len(v.access_log) == 0


# ---------------------------------------------------------------- F9
def test_F9_tolerance_start_20():
    ref = np.zeros(3600, np.int8)
    ref[1000:1060] = 1
    with pytest.raises(E.ScorerParameterError):
        event_score(ref, ref, params=(20, 60, 0, 300, 90))
    assert event_score(ref, ref)["tp"] == 1


# ---------------------------------------------------------------- S1, S5, S7
def test_S1_subject_on_both_sides():
    with pytest.raises(E.SubjectOverlapError):
        assert_subject_disjoint(["chb01", "chb03"], ["chb01"])


def test_S5_random_split_without_flag():
    with pytest.raises(E.RandomSplitForbiddenError):
        random_window_split({"a.edf": 100}, 0.5, C.rng(C.STREAM_SYNTHETIC))
    assert random_window_split({"a.edf": 100}, 0.5, C.rng(C.STREAM_SYNTHETIC), allow_random_split=True)["a.edf"].size == 100


def test_S7_split_hash_mismatch():
    recs = [FileRecord("chb01", "chb01_%02d.edf" % i, "", 3607.0 * i, 3600) for i in range(1, 6)]
    counts = {r.name: (1 if i in (1, 2, 3) else 0) for i, r in enumerate(recs)}
    sp = causal_splits(recs, counts)
    with pytest.raises(E.SplitHashError):
        assert_split_hash(sp, C.EXPECTED_SPLIT_HASH)


# map tests -> violation ids (used by run_n1.py)
TEST_IDS = {
    "test_F1_normaliser_fitted_on_train_plus_test": "F1", "test_F2_test_file_in_inner_cv": "F2", "test_F2_change_C": "F2",
    "test_F3_tau_on_test_scores": "F3", "test_F3_k_equals_3": "F3", "test_F4_window_spanning_file_end": "F4",
    "test_F4_train_window_5s_before_test_file": "F4", "test_F5_oversample_from_train_plus_test": "F5",
    "test_F6_later_file_moved_into_training": "F6", "test_F7_metadata_column": "F7",
    "test_F8_read_test_labels_in_training": "F8", "test_F9_tolerance_start_20": "F9",
    "test_S1_subject_on_both_sides": "S1", "test_S5_random_split_without_flag": "S5", "test_S7_split_hash_mismatch": "S7",
}
