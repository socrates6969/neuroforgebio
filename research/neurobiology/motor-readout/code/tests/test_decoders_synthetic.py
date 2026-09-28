"""Synthetic checks for the M1 decoders and loaders (known ground truth), plus planted-leak power on synthetic data.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from m1lib import data as D  # noqa: E402
from m1lib import decoders as DEC  # noqa: E402
from m1lib import metrics as M  # noqa: E402
from m1lib.guards import lag_offsets, lagged  # noqa: E402


def lds(T, N, rng, noise=1.0):
    """Velocity AR(1) latent -> linear observations."""
    v = np.zeros((T, 2))
    for t in range(1, T):
        v[t] = 0.95 * v[t - 1] + 0.3 * rng.standard_normal(2)
    C = rng.standard_normal((N, 2))
    x = v @ C.T + noise * rng.standard_normal((T, N))
    return v, x


def test_ridge_recovers_linear_map():
    rng = np.random.default_rng(10)
    v, x = lds(4000, 30, rng)
    X = lagged(x, lag_offsets(3))
    m, inf = DEC.fit_ridge_select(X[:3000], v[:3000], lambda mm: (v[3000:3500], mm.predict(X[3000:3500])))
    assert M.r2_vw(v[3500:], m.predict(X[3500:])) > 0.8


def test_ridge_stream_equals_path():
    rng = np.random.default_rng(11)
    X = rng.standard_normal((500, 12))
    Y = X[:, :2] + rng.standard_normal((500, 2))
    rs = DEC.RidgeStream(12, 2)
    for a in range(0, 500, 70):
        rs.add(X[a:a + 70], Y[a:a + 70])
    ms = rs.finalize()
    W, b = DEC.RidgePath(X, Y).coef(DEC.LAMBDAS[3])
    assert np.allclose(ms[3].W, W) and np.allclose(ms[3].b, b)


def test_kalman_matches_truth_model():
    rng = np.random.default_rng(12)
    v, x = lds(6000, 30, rng, noise=3.0)
    kf = DEC.KalmanVel().fit([v[:5000]], [x[:5000]])
    assert kf.riccati_iters is not None
    r2 = M.r2_vw(v[5000:], kf.predict(x[5000:]))
    assert r2 > 0.8
    assert np.allclose(kf.A[:2, :2], 0.95 * np.eye(2), atol=0.03)


def test_fa_procrustes_aligns_partial_channel_change():
    """Day k: 10 of 40 channels get new loadings + all channels an offset; the latent trajectory is the same.
    FA's own rotation ambiguity differs per day; Procrustes on loadings must realign day-k latents to day-0 axes.
    (A pure latent rotation L0 -> L0 Q is not identifiable from x and is not tested.)"""
    rng = np.random.default_rng(13)
    k, N, T = 4, 40, 6000
    L0 = rng.standard_normal((N, k))
    Lk = L0.copy()
    Lk[:10] = rng.standard_normal((10, k))
    z = rng.standard_normal((T, k))
    x0 = z @ L0.T + 0.3 * rng.standard_normal((T, N))
    xk = z @ Lk.T + 0.3 * rng.standard_normal((T, N)) + 2.0
    f0 = DEC.FA().fit(x0, k=k, iters=200)
    fk = DEC.FA().fit(xk, k=k, iters=200)
    O = DEC.procrustes(fk.L, f0.L)
    assert np.allclose(O @ O.T, np.eye(k), atol=1e-10)
    z0 = f0.posterior_mean(x0)
    za = fk.posterior_mean(xk) @ O
    assert M.r2_vw(z0, za) > 0.8
    assert M.r2_vw(z0, za) > M.r2_vw(z0, fk.posterior_mean(xk)) + 0.2


def test_riemann_mean_commuting_is_geometric():
    Cs = np.array([np.diag([1.0, 4.0]), np.diag([4.0, 1.0]), np.diag([2.0, 2.0])])
    M_ = DEC.riemann_mean(Cs)
    assert np.allclose(M_, np.diag([2.0, 2.0]), atol=1e-6)
    assert np.allclose(DEC.tangent(Cs[2:], M_), 0, atol=1e-8)
    assert DEC.tangent(Cs[:1], M_).shape == (1, 3)


def test_riemann_affine_invariance():
    rng = np.random.default_rng(14)
    A = [np.cov(rng.standard_normal((5, 50))) for _ in range(2)]
    Wm = rng.standard_normal((5, 5))

    def dist(P, Q):
        e = np.linalg.eigvals(np.linalg.solve(P, Q)).real
        return np.sqrt((np.log(e) ** 2).sum())
    assert np.isclose(dist(*A), dist(Wm @ A[0] @ Wm.T, Wm @ A[1] @ Wm.T))


def test_logreg_and_lda_separable():
    rng = np.random.default_rng(15)
    X = np.vstack([rng.standard_normal((50, 5)) - 2, rng.standard_normal((50, 5)) + 2])
    y = np.r_[np.zeros(50, int), np.ones(50, int)]
    assert (DEC.LogRegL2().fit(X, y, 1.0).predict(X) == y).mean() > 0.97
    assert (DEC.ShrinkLDA().fit(X, y, 0.3).predict(X) == y).mean() > 0.97


def test_rebin_area_preserving():
    x = np.arange(40, dtype=float)[:, None]
    r = D.rebin(x)
    assert r.shape[0] == 25
    assert np.isclose(r.sum() * 32, x.sum() * 20)
    assert np.allclose(D.rebin(np.full((80, 3), 7.0)), 7.0)
    assert np.isclose(r[0, 0], (0 * 20 + 1 * 12) / 32)


def test_gru_learns_and_is_deterministic():
    pytest.importorskip("torch")
    rng = np.random.default_rng(16)
    v, x = lds(64 * 160, 12, rng, noise=0.5)
    Xs = ((x - x.mean(0)) / x.std(0)).reshape(160, 64, 12)
    Ys = v.reshape(160, 64, 2)
    mask = np.ones((160, 64))
    mask[:, :10] = 0

    def vf(e):
        return M.r2_vw(Ys[128:].reshape(-1, 2), e.predict_seqs(Xs[128:]).reshape(-1, 2))
    e1, _ = DEC.train_gru(Xs[:128], Ys[:128], mask[:128], vf, seeds=(1,), max_epochs=25)
    e2, _ = DEC.train_gru(Xs[:128], Ys[:128], mask[:128], vf, seeds=(1,), max_epochs=25)
    assert e1.hash() == e2.hash()
    assert vf(e1) > 0.5


def test_planted_label_channel_power_synthetic():
    """PL-1 concept: z(v1)+N(0,1) appended to weak features must raise ridge R2 by >= 0.10."""
    rng = np.random.default_rng(17)
    v, x = lds(4000, 20, rng, noise=8.0)
    X = lagged(x, lag_offsets(3))
    pc = (v[:, 0] - v[:3000, 0].mean()) / v[:3000, 0].std() + rng.standard_normal(4000)
    Xp = np.column_stack([X, pc])
    fit = lambda A: DEC.fit_ridge_select(A[:3000], v[:3000], lambda m: (v[3000:3500], m.predict(A[3000:3500])))[0]  # noqa
    r_h = M.r2_vw(v[3500:], fit(X).predict(X[3500:]))
    r_p = M.r2_vw(v[3500:], fit(Xp).predict(Xp[3500:]))
    assert r_p - r_h >= 0.10
