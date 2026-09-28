"""Unit tests: scorer fixture X1-X12 (N1 e), post-processing, windows, features, statistics, config literal.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
"""
import itertools

import numpy as np
import pytest

from nfharness import config as C
from nfharness import stats
from nfharness.features import FEATURE_NAMES, features_from_signal
from nfharness.postprocess import hypothesis_mask
from nfharness.scoring import event_score, latencies, reimpl_event_score
from nfharness.windows import window_labels_from_mask

R = [(1000, 1060)]
# case: (T, ref events, hyp events, TP, FP, N_ref, FA/24h)  -- N1 (e) hand-computed fixture
FIXTURE = {
    "X1": (3600, R, [(1000, 1060)], 1, 0, 1, 0), "X2": (3600, R, [], 0, 0, 1, 0),
    "X3": (3600, R, [(975, 980)], 1, 0, 1, 0), "X4": (3600, R, [(960, 968)], 0, 1, 1, 24),
    "X5": (3600, R, [(1115, 1119)], 1, 0, 1, 0), "X6": (3600, R, [(1125, 1130)], 0, 1, 1, 24),
    "X7": (3600, R, [(1000, 1060), (2000, 2010), (2099, 2109)], 1, 1, 1, 24),
    "X8": (3600, R, [(1000, 1060), (2000, 2010), (2101, 2111)], 1, 2, 1, 48),
    "X9": (3600, R, [(1000, 1060), (2000, 2301)], 1, 2, 1, 48),
    "X10": (3600, [(1000, 1060), (1100, 1130)], [(1110, 1115)], 1, 0, 1, 0),
    "X11": (7200, [], [(100, 110), (1000, 1010), (5000, 5010)], 0, 3, 0, 36),
    "X12a": (3600, R, [(1004, 1030)], 1, 0, 1, 0), "X12b": (3600, R, [(985, 990)], 1, 0, 1, 0),
}


def mask(T, ev):
    m = np.zeros(T, np.int8)
    for a, b in ev:
        m[a:b] = 1
    return m


@pytest.mark.parametrize("case", sorted(FIXTURE))
@pytest.mark.parametrize("scorer", ["timescoring", "reimpl"])
def test_fixture(case, scorer):
    T, r, h, tp, fp, nref, fa = FIXTURE[case]
    f = event_score if scorer == "timescoring" else reimpl_event_score
    out = f(mask(T, r), mask(T, h))
    assert (out["tp"], out["fp"], out["n_ref"]) == (tp, fp, nref)
    assert abs(24 * out["fp"] / (out["dur_s"] / 3600) - fa) < 1e-9


def test_latency_X12():
    assert latencies(mask(3600, R), mask(3600, [(1004, 1030)])) == [4]
    assert latencies(mask(3600, R), mask(3600, [(985, 990)])) == [-15]


def test_k_of_n_causal():
    p = np.zeros(20)
    p[5:9] = 1.0                               # windows 5..8 above tau -> d_8 = 1 (4 of 5), second 9 = d_8
    m = hypothesis_mask(p, 0.5, 21)
    assert m.tolist().index(1) == 9 and m.sum() == 2 and m[0] == 0     # d_8, d_9 = 1; d_10 has 3 of 5
    assert hypothesis_mask(np.ones(20), 0.5, 21)[:4].tolist() == [0, 0, 0, 0]
    assert hypothesis_mask(np.ones(20), 0.5, 21)[4] == 1   # d_3 = 1: 4 of the 4 available windows


def test_window_label_rule():
    m = mask(20, [(5, 10)])
    wl = window_labels_from_mask(m)
    assert np.flatnonzero(wl).tolist() == [5, 6, 7, 8]      # [i, i+2) fully inside [5, 10)


def test_feature_shape_and_names():
    x = np.random.default_rng(0).standard_normal((22, 256 * 10)).astype(np.float32)
    f = features_from_signal(x)
    assert f.shape == (9, 132) and len(FEATURE_NAMES) == 132 and len(set(FEATURE_NAMES)) == 132


def test_feature_bandpower_sine():
    t = np.arange(256 * 4) / 256.0
    x = np.tile(100 * np.sin(2 * np.pi * 10 * t), (22, 1))
    f = features_from_signal(x)
    bands = f[0, 1:6]
    assert np.argmax(bands) == 2                           # 10 Hz -> 8-13 Hz band


def test_auroc_bruteforce():
    g = np.random.default_rng(1)
    y = g.integers(0, 2, 60)
    s = np.round(g.random(60), 1)
    pos, neg = s[y == 1], s[y == 0]
    bf = np.mean([(a > b) + 0.5 * (a == b) for a, b in itertools.product(pos, neg)])
    assert abs(stats.auroc(y, s) - bf) < 1e-12


def test_block_bootstrap_matches_direct():
    g = np.random.default_rng(2)
    ys = [g.integers(0, 2, 50) for _ in range(3)]
    ss = [g.random(50) for _ in range(3)]
    (lo, hi), _ = stats.block_bootstrap_auroc(ys, ss, np.random.default_rng(3), B=200)
    idx = np.random.default_rng(3).integers(0, 3, size=(200, 3))
    direct = [stats.auroc(np.concatenate([ys[i] for i in r]), np.concatenate([ss[i] for i in r])) for r in idx]
    assert abs(lo - np.percentile(direct, 2.5)) < 1e-12 and abs(hi - np.percentile(direct, 97.5)) < 1e-12


def test_clopper_pearson_prereg_values():
    assert np.allclose(stats.clopper_pearson(3, 4), (0.194, 0.994), atol=1e-3)
    assert np.allclose(stats.clopper_pearson(4, 4), (0.398, 1.0), atol=1e-3)
    assert np.allclose(stats.clopper_pearson(2, 4), (0.068, 0.932), atol=1e-3)


def test_garwood_decision_grid():
    """N2 §4 FP grid equals the generic rule: meets = FP <= H; FAIL = Garwood lower bound > H (per-hour bar)."""
    for H, meet, inc in ((3.646, 3, 8), (8.000, 8, 14), (8.009, 8, 14)):
        assert max(k for k in range(50) if k <= H) == meet
        assert max(k for k in range(50) if stats.garwood(k)[0] <= H) == inc
    assert abs(stats.garwood(0)[1] * 24 / 3.646 - 24.3) < 0.05


def test_config_literal():
    assert C.config_hash(C.LOCKED_CONFIG) == C.LOCKED_CONFIG_HASH_LITERAL
    assert len(C.TAU_GRID) == 95 and C.TAU_GRID[0] == 0.05 and C.TAU_GRID[-1] == 0.99


def test_split_hash_literal_from_prereg_text():
    s = ("chb01;train=chb01_01.edf,chb01_02.edf,chb01_03.edf,chb01_04.edf,chb01_05.edf,chb01_06.edf,chb01_15.edf;"
         "test=chb01_16.edf,chb01_18.edf,chb01_21.edf,chb01_26.edf\n"
         "chb03;train=chb03_01.edf,chb03_02.edf,chb03_03.edf;test=chb03_04.edf,chb03_05.edf,chb03_06.edf,chb03_07.edf,"
         "chb03_08.edf,chb03_34.edf,chb03_35.edf,chb03_36.edf\n"
         "chb10;train=chb10_12.edf,chb10_20.edf,chb10_27.edf;test=chb10_30.edf,chb10_31.edf,chb10_38.edf,chb10_89.edf")
    import hashlib
    assert hashlib.sha256(s.encode()).hexdigest() == C.EXPECTED_SPLIT_HASH
