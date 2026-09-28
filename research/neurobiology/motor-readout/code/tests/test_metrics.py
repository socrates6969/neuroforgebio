"""Metric fixtures for M1 (prereg §4): M-R2 definition, bits/s on known Gaussians, Miller-Madow MI, Wolpaw, bootstraps.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from m1lib import metrics as M  # noqa: E402


def test_r2_variance_weighted_definition():
    rng = np.random.default_rng(1)
    y = rng.standard_normal((200, 2)) * [1.0, 5.0]
    yh = y + rng.standard_normal((200, 2)) * [0.5, 1.0]
    r2d = [1 - ((y[:, d] - yh[:, d]) ** 2).sum() / ((y[:, d] - y[:, d].mean()) ** 2).sum() for d in range(2)]
    w = y.var(0)
    assert np.isclose(M.r2_vw(y, yh), (w * r2d).sum() / w.sum())
    assert M.r2_vw(y, y) == 1.0
    assert np.isclose(M.r2_vw(y, np.repeat(y.mean(0)[None], 200, 0)), 0.0)


def test_rho2_scale_invariant():
    rng = np.random.default_rng(2)
    y = rng.standard_normal((500, 2))
    yh = 3 * y + 7 + 0.1 * rng.standard_normal((500, 2))
    assert M.rho2(y, yh) > 0.98 and M.r2_vw(y, yh) < 0


def test_r2_from_stats_matches_pooled():
    rng = np.random.default_rng(3)
    ys = [rng.standard_normal((35, 2)) for _ in range(20)]
    hs = [y + 0.3 * rng.standard_normal((35, 2)) for y in ys]
    st = M.unit_stats(ys, hs)
    assert np.isclose(M.r2_from_stats(np.ones((1, 20)), st)[0], M.r2_vw(np.vstack(ys), np.vstack(hs)))
    W = np.zeros((1, 20))
    W[0, :5] = 2
    assert np.isclose(M.r2_from_stats(W, st)[0], M.r2_vw(np.vstack(ys[:5] * 2), np.vstack(hs[:5] * 2)))


def test_freq_mask_exact():
    m, df = M.freq_mask(35, 20)
    assert m.sum() == 8 and np.isclose(df, 1000 / 700)        # 0 .. 10.0 Hz inclusive
    m, df = M.freq_mask(64, 32)
    assert m.sum() == 21 and np.isclose(df, 1000 / 2048)       # 0 .. 9.77 Hz


def test_bits_known_gaussian():
    """White Gaussian x, y = x + noise at SNR s: gamma^2 = s/(1+s) flat -> I = n_f * df * log2(1+s)."""
    rng = np.random.default_rng(4)
    K, n, s = 3000, 35, 3.0
    x = rng.standard_normal((K, n, 2))
    y = x + rng.standard_normal((K, n, 2)) / np.sqrt(s)
    m, df = M.freq_mask(n, 20)
    expect = 2 * m.sum() * df * np.log2(1 + s)
    r = M.bits_with_null(x, y, 20, np.random.default_rng(5), n_perm=20)
    assert abs(r["I_raw"] - expect) / expect < 0.03
    assert abs(r["I_null_median"]) < 0.05 * expect


def test_bits_independent_is_null():
    rng = np.random.default_rng(6)
    x = rng.standard_normal((200, 35, 2))
    y = rng.standard_normal((200, 35, 2))
    r = M.bits_with_null(x, y, 20, np.random.default_rng(7), n_perm=50)
    assert abs(r["I_net"]) < 0.5 and r["I_raw"] > 0


def test_bits_bootstrap_identity_weights():
    rng = np.random.default_rng(8)
    x = rng.standard_normal((50, 64, 2))
    y = x + rng.standard_normal((50, 64, 2))
    X, Y = M.seg_spectra(x, y)
    m, df = M.freq_mask(64, 32)
    assert np.isclose(M.bits_from_spectra(X, Y, m, df, W=np.ones((1, 50)))[0], M.bits_from_spectra(X, Y, m, df))


def test_miller_madow_and_wolpaw():
    mm, mi = M.mi_miller_madow([[50, 0], [0, 50]])
    assert np.isclose(mi, 1.0) and np.isclose(mm, 1 - 1 / (200 * np.log(2)))
    assert abs(M.wolpaw_bits(2, 0.8) - 0.278) < 1e-3 and abs(M.wolpaw_bits(2, 0.7) - 0.119) < 1e-3
    assert abs(M.wolpaw_bits(36, 1.0) - 5.17) < 1e-2
    mm, mi = M.mi_miller_madow([[25, 25], [25, 25]])
    assert np.isclose(mi, 0.0) and mm < 0


def test_signflip():
    rng = np.random.default_rng(9)
    assert M.signflip_p(np.full(20, 0.1), 2000, rng) < 0.01
    assert M.signflip_p(np.array([0.1, -0.1] * 10), 2000, rng) > 0.3


def test_pct_ci():
    assert M.pct_ci(np.arange(101), 98) == [1.0, 99.0]
