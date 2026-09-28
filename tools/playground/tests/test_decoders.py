"""Unit tests for the playground decoders on synthetic data (no dataset download needed)."""

import numpy as np
import pytest
from nf_playground.build import split_reaches, valid_runs
from nf_playground.decoders import Kalman, Ridge, bin_spikes, lagged, r2_score


def test_bin_spikes_counts_half_open_bins():
    edges = np.array([0.0, 0.05, 0.10, 0.15])
    c = bin_spikes([np.array([0.0, 0.049, 0.05, 0.149, 0.15]), np.array([])], edges)
    assert c[:, 0].tolist() == [2, 1, 1]  # 0.15 is outside the last [0.10, 0.15) bin
    assert c[:, 1].tolist() == [0, 0, 0]


def test_lagged_is_causal_and_stops_at_segment_gaps():
    counts = np.arange(1, 7, dtype=float)[:, None]  # one unit, six bins
    seg = np.array([0, 0, 0, 1, 1, 1])
    x = lagged(counts, 3, seg)
    assert x[2].tolist() == [3, 2, 1]
    assert x[3].tolist() == [4, 0, 0]  # history does not cross into segment 0
    assert x[5].tolist() == [6, 5, 4]


def test_r2_perfect_mean_and_worse_than_mean():
    y = np.array([[0.0, 1.0], [1.0, 3.0], [2.0, 5.0]])
    assert r2_score(y, y) == pytest.approx(1.0)
    assert r2_score(y, np.tile(y.mean(0), (3, 1))) == pytest.approx(0.0)
    assert r2_score(y, -y) < 0


def test_ridge_recovers_a_linear_map():
    rng = np.random.default_rng(0)
    x = rng.normal(size=(2000, 6))
    w = rng.normal(size=(6, 2))
    y = x @ w + 3.0 + 0.01 * rng.normal(size=(2000, 2))
    m = Ridge(alpha=1e-3).fit(x[:1500], y[:1500])
    assert r2_score(y[1500:], m.predict(x[1500:])) > 0.999


def test_kalman_tracks_a_simulated_reach_from_tuned_units():
    rng = np.random.default_rng(1)
    t = 3000
    z = np.zeros((t, 4))
    for i in range(1, t):  # smooth random walk in velocity, integrated position
        z[i, 2:] = 0.95 * z[i - 1, 2:] + rng.normal(scale=1.0, size=2)
        z[i, :2] = z[i - 1, :2] + 0.05 * z[i, 2:]
    h = rng.normal(size=(40, 4))
    y = z @ h.T + rng.normal(scale=2.0, size=(t, 40))
    contiguous = np.ones(t, dtype=bool)
    contiguous[0] = False
    kf = Kalman().fit(z[:2000], y[:2000], contiguous[:2000])
    starts = np.zeros(t - 2000, dtype=bool)
    starts[0] = True
    est = kf.filter(y[2000:], starts)
    assert r2_score(z[2000:, 2:], est[:, 2:]) > 0.9


def test_valid_runs_and_blocked_split():
    assert valid_runs(np.array([1, 1, 0, 1, 0, 0, 1], dtype=bool)) == [(0, 2), (3, 4), (6, 7)]
    s = split_reaches(100)
    assert (s[:30] == "train").all()
    assert (s[30:40] == "val").all()
    assert (s[40:50] == "test").all()
    assert (s == "test").sum() == 20


def test_compact_encoding_is_lossless():
    from nf_playground.encode import SCHEMA_V1, SCHEMA_V2, compact, expand

    v1 = {
        "schema": SCHEMA_V1,
        "posScale": 10,
        "trials": [
            {
                "bins": 3,
                "truePos": [10, -5, 12, -4, 15, -9],
                "spikes": [[0, 3, 3, 40], [], [7]],
                "noiseSpikes": [[5, 2, 5, 1, 90, 3], [], [0, 1]],
                "decoded": {"ridge": [[[1, 2, 3, 4, 5, 6], [0, 0, -1, 1, 2, -2]]]},
            }
        ],
    }
    v2 = compact(v1)
    assert v2["schema"] == SCHEMA_V2
    assert v2["trials"][0]["spikes"][0] == [0, 3, 0, 37]
    assert v2["trials"][0]["noiseSpikes"][0] == {"t": [5, 0, 85], "l": "213"}
    assert v2["trials"][0]["truePos"] == [10, -5, 2, 1, 3, -5]
    assert expand(v2) == v1
