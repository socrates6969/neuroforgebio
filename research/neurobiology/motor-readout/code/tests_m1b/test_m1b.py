"""M1b new tests (prereg §9). RESEARCH USE ONLY. NOT A MEDICAL DEVICE. Synthetic data only."""
import hashlib
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import m1b  # noqa: E402
from m1b import core as CO  # noqa: E402
from m1b import d3 as D3  # noqa: E402
from m1b import pipeline as PL  # noqa: E402
from m1lib import decoders as DEC  # noqa: E402
from m1lib import metrics as MET  # noqa: E402
from m1lib.guards import FeatureWhitelistError, SessionOrderError, assert_input_lock  # noqa: E402


def _segs(rng, K=40, n=35, d=2):
    y = rng.standard_normal((K, n, d)).cumsum(1)
    yh = 0.7 * y + rng.standard_normal((K, n, d))
    return y, yh


def _perms(K, rng, n=50):
    return MET.derangements(K, n, rng)


# 1 I_mse <= I_coh (property test on random data)
@pytest.mark.parametrize("seed", range(10))
def test_imse_le_icoh(seed):
    rng = np.random.default_rng(seed)
    y, yh = _segs(rng)
    yh = yh * rng.uniform(-3, 3) + rng.standard_normal()
    X, Y = MET.seg_spectra(y, yh)
    m, df = CO.freq_mask_nodc(35, 20)
    assert CO.mse_bits_from_spectra(X, Y, m, df) <= MET.bits_from_spectra(X, Y, m, df) + 1e-9


# 2 B0 (identical output on every segment) has net = 0 for both metrics
def test_b0_net_zero():
    rng = np.random.default_rng(1)
    y, _ = _segs(rng)
    prof = y.mean(0)
    yh = np.repeat(prof[None], len(y), axis=0)
    b = CO.bits_all(y, yh, 20, _perms(len(y), rng))
    assert abs(b["I_mse_net"]) < 1e-9 and abs(b["I_coh_net"]) < 1e-9


# 3 negation lowers I_mse, coherence unchanged
def test_negation_lowers_imse():
    rng = np.random.default_rng(2)
    y, yh = _segs(rng)
    p = _perms(len(y), rng)
    a, b = CO.bits_all(y, yh, 20, p), CO.bits_all(y, -yh, 20, p)
    assert b["I_mse"] < a["I_mse"] and b["I_mse_net"] < 0
    assert abs(a["I_coh"] - b["I_coh"]) < 1e-9


# 4 constrained derangement: permutation, never same condition (rejection path and DV-b1 mcmc path)
@pytest.mark.parametrize("cond", [[i % 9 for i in range(60)], [0] * 50 + list(range(1, 51))])
def test_constrained_derangement(cond):
    p, info = CO.constrained_derangement(cond, np.random.default_rng(3), max_draws=2000)
    c = np.array(cond)
    assert sorted(p.tolist()) == list(range(len(cond)))
    assert not np.any(c[p] == c)
    assert info["method"] in ("rejection", "mcmc")


def test_mcmc_path_used_and_valid():
    cond = [0] * 50 + [i % 20 + 1 for i in range(50)]
    p, info = CO.constrained_derangement(cond, np.random.default_rng(4), max_draws=10)
    assert info["method"] == "mcmc" and info["mcmc_accepted"] > 0
    assert not np.any(np.array(cond)[p] == np.array(cond))


# 5 fallback flag when a condition holds > 50 %
def test_majority_fallback_flag():
    cond = [0] * 60 + list(range(1, 41))
    p, info = CO.constrained_derangement(cond, np.random.default_rng(5))
    assert info["flag"] and info["method"].startswith("unconstrained")
    assert not np.any(p == np.arange(100))


# 6 analytic E within 10 % on large-n linear-Gaussian data
def test_pl1_expected_large_n():
    g = np.random.default_rng(6)
    n, p = 60000, 20
    X = g.standard_normal((n, p))
    B = g.standard_normal((p, 2)) * 0.3
    v = X @ B + g.standard_normal((n, 2)) * np.array([1.0, 0.7])
    vz = (v - v.mean(0)) / v.std(0)
    s2 = 0.1
    P = vz + np.sqrt(s2) * g.standard_normal(v.shape)
    tr, te = slice(0, n // 2), slice(n // 2, n)
    h = DEC.RidgePath(X[tr], v[tr]).coef(1e-6)
    yh = X[te] @ h[0] + h[1]
    Xp = np.column_stack([X, P])
    hp = DEC.RidgePath(Xp[tr], v[tr]).coef(1e-6)
    yp = Xp[te] @ hp[0] + hp[1]
    rise = MET.r2_vw(v[te], yp) - MET.r2_vw(v[te], yh)
    E, _, _ = CO.pl1_expected(v[te], yh, s2)
    assert abs(rise - E) / E < 0.10


# 7 KF-L with (L, B) = (0, 1) gives exactly KF-0
def test_kfl_01_is_kf0():
    g = np.random.default_rng(7)
    Z = g.standard_normal((30, 45, 8))
    V = g.standard_normal((30, 35, 2)).cumsum(1) * 0.1
    itr, iva = np.arange(20), np.arange(20, 30)
    o = CO.kfl_obs(Z, 10, 35, 0, 1)
    assert np.array_equal(o, Z[:, 10:45])
    a = DEC.KalmanVel().fit([v for v in V[itr]], [Z[s, 10:] for s in itr])
    kf, obs, _ = PL.fit_kf(Z, V[itr], V[iva], itr, iva, 0, 1)
    assert np.array_equal(a.K, kf.K) and np.array_equal(a.predict(Z[25, 10:]), kf.predict(obs[25]))
    assert len(CO.KFL_GRID) == 23 and CO.KFL_GRID[0] == (0, 1)


# 8 KF-L feature is causal
@pytest.mark.parametrize("LB", [(0, 1), (3, 2), (5, 5), (0, 10), (7, 1)])
def test_kfl_causal(LB):
    L, B = LB
    g = np.random.default_rng(8)
    Z = g.standard_normal((4, 45, 5))
    o = CO.kfl_obs(Z, 10, 35, L, B)
    t = 12
    Z2 = Z.copy()
    Z2[:, 10 + t + 1:] = 99.0
    o2 = CO.kfl_obs(Z2, 10, 35, L, B)
    assert np.array_equal(o[:, :t + 1], o2[:, :t + 1])
    ref = Z[:, 10 + t - L - B + 1:10 + t - L + 1].mean(1)
    assert np.allclose(o[:, t], ref)


# 9 row-tag SessionOrderError for a day-k calib row in a day-0 fit
def test_row_tag_session_order():
    tags = [(0, "calib"), (0, "val"), (120, "calib")]
    with pytest.raises(SessionOrderError):
        CO.check_rows(0, tags)
    assert CO.check_rows(0, tags, allow_future=True)
    assert CO.check_rows(120, [(120, "calib"), (120, "val")])
    with pytest.raises(SessionOrderError):
        CO.check_rows(0, [(0, "calib"), (0, "test")])


# 10 whitelist raises for undeclared p_1/p_2 and for the PL-4 channel
def test_whitelists():
    assert PL.pl1_whitelist(10, 3) == "FeatureWhitelistError"
    assert D3.pl4_whitelist() == "FeatureWhitelistError"
    from m1lib.guards import assert_whitelist, causal_whitelist
    with pytest.raises(FeatureWhitelistError):
        assert_whitelist(causal_whitelist("u", 4, 2) + ["planted_v2"], causal_whitelist("u", 4, 2))


# 11 NL-1 keeps exactly 25 % of the pairs
@pytest.mark.parametrize("n", [150, 225, 49])
def test_nl1_keeps_quarter(n):
    cond = [i % 7 for i in range(n)]
    p, keep, info = CO.nl1_permutation(cond, np.random.default_rng(11), np.random.default_rng(12))
    assert int((p == np.arange(n)).sum()) == int(round(0.25 * n)) == len(keep)
    rest = np.setdiff1d(np.arange(n), keep)
    c = np.array(cond)
    assert not np.any(c[p[rest]] == c[rest])
    assert sorted(p.tolist()) == list(range(n))


# 12 lock hashes of §1.5 and the prereg
def test_lock_hashes():
    assert assert_input_lock(m1b.FRESH_LOCK, m1b.FRESH_LOCK_SHA) == m1b.FRESH_LOCK_SHA
    assert assert_input_lock(m1b.POWER_LOCK, m1b.POWER_LOCK_SHA) == m1b.POWER_LOCK_SHA
    assert sum(r[4] for r in m1b.LINK) == m1b.LINK_TOTAL_BYTES
    h = hashlib.sha256(open(m1b.PREREG, "rb").read()).hexdigest()
    assert h == m1b.PREREG_SHA


# extra: DC-free masks (P4 counts) and start-aligned B0
def test_freq_counts_and_b0():
    assert int(CO.freq_mask_nodc(35, 20)[0].sum()) == 7
    assert int(CO.freq_mask_nodc(64, 32)[0].sum()) == 20
    prof = CO.start_aligned_profile([np.ones((3, 2)), 3 * np.ones((5, 2))])
    assert np.allclose(prof[:3], 2) and np.allclose(prof[3:], 3)
    p = CO.start_aligned_predict(prof, [2, 7])
    assert p.shape == (9, 2) and np.allclose(p[-2:], 3)


# extra: PL-4 channel doubles SD inside T2 intervals; log-var gap ~ ln 4
def test_pl4_channel():
    g = np.random.default_rng(13)
    fs = 160.0
    ev = [(10.0 * i, 4.1, "T1" if i % 2 else "T2") for i in range(1, 11)]
    ch = D3.pl4_channel(int(120 * fs), fs, [(on, d) for on, d, t in ev if t == "T2"], g)
    f = D3.pl4_features(ch, fs, ev)[:, 0]
    y = np.array([0 if t == "T1" else 1 for _, _, t in ev])
    assert abs((f[y == 1].mean() - f[y == 0].mean()) - np.log(4)) < 0.4
