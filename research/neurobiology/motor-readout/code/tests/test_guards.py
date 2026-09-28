"""M1 code-guard suite (prereg §6): each deliberate violation must raise its named error; declared/honest paths must not.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from m1lib.guards import TestLabelAccessError as LabelAccessError  # noqa: E402  (alias: not a test class)
from m1lib.guards import (CausalFeatureError, CausalSplitError, FeatureWhitelistError, HarnessViolation,  # noqa: E402
                          InputHashError, LabelVault, NormaliserLeakError, RandomSplitForbiddenError,
                          SessionOrderError, SplitHashError, TrialOverlapError, ZScore,
                          assert_bins_disjoint, assert_causal_blocks, assert_file_hash, assert_input_lock,
                          assert_session_order, assert_trial_disjoint, assert_whitelist, causal_whitelist, chrono_split,
                          feature_names, lag_offsets, lagged, random_bin_split, sha256_bytes)


def test_new_errors_subclass_harness_violation():
    for e in (TrialOverlapError, SessionOrderError, CausalFeatureError):
        assert issubclass(e, HarnessViolation)


# 1-2 TrialOverlapError
def test_trial_overlap_partitions():
    with pytest.raises(TrialOverlapError):
        assert_trial_disjoint({"train": [1, 2, 3], "test": [3, 4]})


def test_trial_overlap_bins():
    with pytest.raises(TrialOverlapError):
        assert_bins_disjoint({"train": np.array([1, 1, 2]), "val": np.array([2, 5])})


# 3 CausalSplitError (F6)
def test_causal_split_violation():
    with pytest.raises(CausalSplitError):
        assert_causal_blocks([(0, 1), (1, 5)], [(4, 6)], [(7, 8)])
    with pytest.raises(CausalSplitError):
        assert_causal_blocks([(0, 1)], [(2, 3)], [(2.5, 4)])


# 4 NormaliserLeakError (F1)
def test_normaliser_leak():
    X = np.random.default_rng(0).standard_normal((10, 3))
    with pytest.raises(NormaliserLeakError):
        ZScore().fit(X, np.array([0] * 5 + [9] * 5), train_owners=[0])


# 5-8 TestLabelAccessError (F8)
def _vault():
    v = LabelVault("t")
    v.deposit("k", np.arange(5))
    return v


def test_vault_direct_read():
    v = _vault()
    with pytest.raises(LabelAccessError):
        v.get("k")
    with pytest.raises(LabelAccessError):
        v["k"]


def test_vault_score_before_freeze():
    with pytest.raises(LabelAccessError):
        _vault().final_score("k", "ridge", lambda y: y.sum())


def test_vault_second_read():
    v = _vault()
    v.freeze("h")
    assert v.final_score("k", "ridge", lambda y: int(y.sum())) == 10
    with pytest.raises(LabelAccessError):
        v.final_score("k", "ridge", lambda y: int(y.sum()))
    assert len(v.log) == 1


def test_vault_undeclared_planted_and_deposit_after_freeze():
    v = _vault()
    with pytest.raises(LabelAccessError):
        v.planted_access("k", "PL")
    v.freeze("h")
    with pytest.raises(LabelAccessError):
        v.deposit("k2", [1])
    assert v.planted_access("k", "PL", declared=True).sum() == 10


# 9-10 SessionOrderError (PL-2 undeclared)
def test_session_order_future_day():
    with pytest.raises(SessionOrderError):
        assert_session_order(0, [0, 32])


def test_session_order_test_block():
    with pytest.raises(SessionOrderError):
        assert_session_order(0, [0], ["calib", "test"])
    assert assert_session_order(0, [0, 32], ["calib", "test"], allow_future=True)


# 11-12 CausalFeatureError (PL-3 undeclared features)
def test_causal_feature_offsets():
    with pytest.raises(CausalFeatureError):
        lag_offsets(0, centred=5)
    assert lag_offsets(0, centred=5, allow_noncausal=True) == list(range(-5, 6))


def test_causal_feature_lagged():
    with pytest.raises(CausalFeatureError):
        lagged(np.zeros((10, 2)), [0, -1])


# 13 FeatureWhitelistError (PL-1 undeclared)
def test_feature_whitelist():
    cols = feature_names("u", 3, [0, 1]) + ["planted_v1"]
    with pytest.raises(FeatureWhitelistError):
        assert_whitelist(cols, causal_whitelist("u", 3, 2))
    assert assert_whitelist(cols, causal_whitelist("u", 3, 2), declared_extra=["planted_v1"])


# 14 RandomSplitForbiddenError (PL-3 undeclared split)
def test_random_split_forbidden():
    with pytest.raises(RandomSplitForbiddenError):
        random_bin_split(100, np.random.default_rng(0))
    lab = random_bin_split(100, np.random.default_rng(0), allow_random_split=True)
    assert (lab == "train").sum() == 60 and (lab == "test").sum() == 20


# 15 SplitHashError
def test_split_hash_error():
    txt = "000138|x\n001201|y"
    h = sha256_bytes(txt.encode())
    assert assert_input_lock(txt, h) == h
    with pytest.raises(SplitHashError):
        assert_input_lock(txt + " ", h)


# 16 InputHashError
def test_input_hash_error(tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"abc")
    good = sha256_bytes(b"abc")
    assert assert_file_hash(str(p), good) == good
    with pytest.raises(InputHashError):
        assert_file_hash(str(p), "0" * 64)
    with pytest.raises(InputHashError):
        assert_file_hash(str(p), None)


# honest paths
def test_chrono_split_sizes_and_gap():
    ids = list(range(500))
    st = np.arange(500) * 3.0
    p = chrono_split(ids, st, st + 2.9)
    assert len(p["train"]) == 300 and len(p["val"]) == 99 and len(p["test"]) == 99 and p["gap"] == [300, 400]
    assert max(p["train"]) < min(p["val"]) and max(p["val"]) < min(p["test"])


def test_chrono_split_uses_time_not_id_order():
    ids = [5, 3, 9, 1, 7]
    st = np.array([4.0, 1.0, 0.0, 3.0, 2.0])
    p = chrono_split(ids, st, st + 0.5, gap=0)
    assert p["train"] == [9, 3, 7]


def test_lagged_is_causal():
    X = np.arange(10.0)[:, None]
    L = lagged(X, [0, 1, 2])
    assert L[5].tolist() == [5, 4, 3] and L[1].tolist() == [1, 0, 0]
