"""Offline decoders for the Neural Playground: binning, ridge (Wiener) filter, Kalman filter, R².

numpy only, deterministic, no fitting on test data. Shapes: counts (T, N) spike counts per bin,
states (T, D) behaviour per bin.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def bin_spikes(spike_times: list[np.ndarray], edges: np.ndarray) -> np.ndarray:
    """Spike counts per bin: (len(edges) - 1, n_units). Bins are [edges[i], edges[i + 1])."""
    out = np.zeros((len(edges) - 1, len(spike_times)), dtype=np.float64)
    for j, st in enumerate(spike_times):
        # np.histogram closes the last bin; searchsorted keeps every bin half-open.
        idx = np.searchsorted(edges, st, side="right") - 1
        idx = idx[(idx >= 0) & (idx < len(edges) - 1)]
        out[:, j] = np.bincount(idx, minlength=len(edges) - 1)
    return out


def lagged(counts: np.ndarray, n_lags: int, segment_ids: np.ndarray) -> np.ndarray:
    """Causal history features: row t holds counts[t], counts[t-1], ... counts[t-n_lags+1].

    History never crosses a segment boundary (a gap in the recording); missing history is zero.
    """
    t, n = counts.shape
    out = np.zeros((t, n * n_lags), dtype=np.float64)
    for k in range(n_lags):
        shifted = np.zeros_like(counts)
        if k == 0:
            shifted[:] = counts
        else:
            shifted[k:] = counts[:-k]
            same = np.zeros(t, dtype=bool)
            same[k:] = segment_ids[k:] == segment_ids[:-k]
            shifted[~same] = 0.0
        out[:, k * n : (k + 1) * n] = shifted
    return out


def r2_score(y: np.ndarray, yhat: np.ndarray) -> float:
    """Coefficient of determination, averaged over output columns (uniform weights)."""
    y = np.asarray(y, dtype=np.float64)
    yhat = np.asarray(yhat, dtype=np.float64)
    if y.ndim == 1:
        y, yhat = y[:, None], yhat[:, None]
    ss_res = ((y - yhat) ** 2).sum(axis=0)
    ss_tot = ((y - y.mean(axis=0)) ** 2).sum(axis=0)
    return float(np.mean(1.0 - ss_res / ss_tot))


@dataclass
class Ridge:
    """Linear (Wiener) filter with an L2 penalty, fit on z-scored features and centred targets."""

    alpha: float
    mu: np.ndarray | None = None
    sd: np.ndarray | None = None
    ymu: np.ndarray | None = None
    w: np.ndarray | None = None

    def fit(self, x: np.ndarray, y: np.ndarray) -> Ridge:
        self.mu = x.mean(axis=0)
        sd = x.std(axis=0)
        self.sd = np.where(sd > 0, sd, 1.0)
        xs = (x - self.mu) / self.sd
        self.ymu = y.mean(axis=0)
        gram = xs.T @ xs + self.alpha * np.eye(xs.shape[1])
        self.w = np.linalg.solve(gram, xs.T @ (y - self.ymu))
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        assert self.w is not None, "fit first"
        return ((x - self.mu) / self.sd) @ self.w + self.ymu


@dataclass
class Kalman:
    """Linear-Gaussian state-space decoder (Wu et al. 2003 style), fit by least squares.

    State z = [px, py, vx, vy]; z_t = A z_{t-1} + b + w, w ~ N(0, W);
    observations y_t = H z_t + c + q, q ~ N(0, Q).
    """

    ridge: float = 1e-6
    a: np.ndarray | None = None
    b: np.ndarray | None = None
    w_cov: np.ndarray | None = None
    h: np.ndarray | None = None
    c: np.ndarray | None = None
    q_cov: np.ndarray | None = None
    z0: np.ndarray | None = None
    p0: np.ndarray | None = None

    def fit(self, z: np.ndarray, y: np.ndarray, contiguous: np.ndarray) -> Kalman:
        """z (T, D) states, y (T, N) observations; contiguous[t] says z[t-1] -> z[t] is one step."""
        d = z.shape[1]
        zp, zn = z[:-1][contiguous[1:]], z[1:][contiguous[1:]]
        xa = np.hstack([zp, np.ones((len(zp), 1))])
        coef = np.linalg.lstsq(xa, zn, rcond=None)[0]
        self.a, self.b = coef[:d].T, coef[d]
        res = zn - xa @ coef
        self.w_cov = np.cov(res.T) + self.ridge * np.eye(d)
        xh = np.hstack([z, np.ones((len(z), 1))])
        coef_h = np.linalg.lstsq(xh, y, rcond=None)[0]
        self.h, self.c = coef_h[:d].T, coef_h[d]
        res_h = y - xh @ coef_h
        q = np.cov(res_h.T)
        q = np.atleast_2d(q)
        # A silent unit has zero variance; keep Q invertible.
        self.q_cov = q + (self.ridge + 1e-3 * np.mean(np.diag(q))) * np.eye(q.shape[0])
        self.z0 = z.mean(axis=0)
        self.p0 = np.cov(z.T)
        return self

    def filter(self, y: np.ndarray, segment_start: np.ndarray) -> np.ndarray:
        """Causal estimates for every row of y; the state resets at each segment start."""
        assert self.a is not None, "fit first"
        t = len(y)
        out = np.zeros((t, self.a.shape[0]))
        z, p = self.z0.copy(), self.p0.copy()
        q_inv = np.linalg.inv(self.q_cov)
        ht_qi = self.h.T @ q_inv
        ht_qi_h = ht_qi @ self.h
        for i in range(t):
            if segment_start[i]:
                z, p = self.z0.copy(), self.p0.copy()
            else:
                z = self.a @ z + self.b
                p = self.a @ p @ self.a.T + self.w_cov
            # Information-form update: cheaper than inverting an N x N innovation covariance.
            p_post = np.linalg.inv(np.linalg.inv(p) + ht_qi_h)
            innov = y[i] - (self.h @ z + self.c)
            z = z + p_post @ ht_qi @ innov
            p = p_post
            out[i] = z
        return out
