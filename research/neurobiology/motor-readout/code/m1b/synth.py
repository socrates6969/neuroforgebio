"""M1b power-check synthetic generators (stream 7; DEVIATIONS_M1b B.17). Known ground truth.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
- synth_d1: MC_Maze-like trials on the M1 20 ms grid (85 bins, onset at 750 ms), 27 reach directions, velocity = sum of 8
  reach profiles, 150 units x_t = C v_{t+5} + s N(0, I).
- SynthD2: LINK-like 375-trial centre-out sessions at 20 ms, 96 channels x = C_k v_{t+3} + mu_k + noise, drift =
  loading rotation by theta(lag) = (pi/2) min(1, lag/240) + mean shift (lag/120) N(0,1).
"""
import numpy as np

from m1lib import data as D
from nfharness.config import rng as nf_rng

from . import K_SYN

NB, ONSET_MS, BIN = 85, 750, 20


def _bump(t_ms, c, sd):
    return np.exp(-0.5 * ((t_ms - c) / sd) ** 2)


def synth_d1(key, s_noise, n_trials=250, n_units=150, lead=5):
    g = nf_rng(K_SYN, *key)
    Cload = nf_rng(K_SYN, 999).standard_normal((n_units, 2))          # loadings shared by every synthetic D1 draw
    nbx = NB + lead
    t = -ONSET_MS + BIN * (np.arange(nbx) + 0.5)                      # onset-relative bin centres (ms)
    cond = g.integers(0, 27, size=n_trials)
    V = np.zeros((n_trials, nbx, 2))
    for i in range(n_trials):
        th = 2 * np.pi * cond[i] / 27.0
        V[i] += g.uniform(0.8, 1.2) * _bump(t, 200.0, 80.0)[:, None] * np.array([np.cos(th), np.sin(th)])[None]
        for _ in range(7):
            ph = g.uniform(0, 2 * np.pi)
            V[i] += g.uniform(0.2, 0.5) * _bump(t, g.uniform(-750, 1050), g.uniform(40, 150))[:, None] * \
                np.array([np.cos(ph), np.sin(ph)])[None]
    X = V[:, lead:lead + NB] @ Cload.T + s_noise * g.standard_normal((n_trials, NB, n_units))
    ids = np.arange(n_trials)
    return dict(C=X.astype(np.float32), V=V[:, :NB].copy(), cond=[(int(c), 0) for c in cond], id=ids,
                start=2.0 * ids, stop=2.0 * ids + 1.9, n_units=n_units)


class SynthD2:
    """Loader with the m1lib.data D2 interface (trials / neural / behaviour) + conditions; path = 'synth:<key>:<lag>'."""

    def __init__(self, noise=6.0):
        self.noise = noise
        self._cache = {}
        b = nf_rng(K_SYN, 2000)
        self.C0 = b.standard_normal((96, 2))
        R = b.standard_normal((96, 2))
        R -= self.C0 @ np.linalg.lstsq(self.C0, R, rcond=None)[0]
        self.Cp = R / np.linalg.norm(R, axis=0) * np.linalg.norm(self.C0, axis=0)
        self.mu0 = b.standard_normal(96) * 2 + 10

    def _session(self, path):
        if path in self._cache:
            return self._cache[path]
        _, key, lag = path.split(":")
        lag = int(lag)
        g = nf_rng(K_SYN, 2001, int(key), lag)
        n = 375
        lens = g.integers(50, 101, size=n)
        T = int(lens.sum()) + 20
        tg_out = [(round(a, 4), round(b, 4)) for a in (0.1, 0.3, 0.5, 0.7, 0.9) for b in (0.1, 0.3, 0.5, 0.7, 0.9)
                  if (a, b) != (0.5, 0.5)][:21]
        pos = np.zeros((T + 3, 2)) + 0.5
        tgts = []
        cur = np.array([0.5, 0.5])
        a0 = 10
        starts = []
        for i in range(n):
            tg = np.array([0.5, 0.5]) if i % 2 else np.array(tg_out[g.integers(0, len(tg_out))])
            tgts.append((round(float(tg[0]), 4), round(float(tg[1]), 4)))
            L = int(lens[i])
            m = int(0.6 * L)
            s = np.linspace(0, 1, m)
            mj = 10 * s ** 3 - 15 * s ** 4 + 6 * s ** 5
            pos[a0:a0 + m] = cur + (tg - cur) * mj[:, None]
            pos[a0 + m:a0 + L] = tg
            cur = tg
            starts.append(a0)
            a0 += L
        pos[a0:] = cur
        v = np.diff(pos, axis=0, prepend=pos[:1]) * 50.0
        th = (np.pi / 2) * min(1.0, lag / 240.0)
        C = np.cos(th) * self.C0 + np.sin(th) * self.Cp
        mu = self.mu0 + (lag / 120.0) * g.standard_normal(96)
        x = v[3:T + 3] @ C.T * 3.0 + mu + self.noise * g.standard_normal((T, 96))
        ts = 5.0 + 0.02 * np.arange(T)
        starts = np.array(starts)
        tr = dict(id=np.arange(n), start=ts[starts], stop=ts[starts + lens - 1], style=np.array(["CO"] * n),
                  ts0=float(ts[0]), T20=T)
        cond = {i: tgts[i] for i in range(n)}
        self._cache = {path: (tr, x, v[:T], ts, cond)}
        return self._cache[path]

    def trials(self, path):
        return self._session(path)[0]

    def neural(self, path):
        tr, x, v, ts, _ = self._session(path)
        d = np.diff(ts)
        return D.rebin(x), dict(dt_median_s=float(np.median(d)), dt_min_s=float(d.min()), dt_max_s=float(d.max()),
                                n20=len(ts))

    def behaviour(self, path):
        return D.rebin(self._session(path)[2])

    def conditions(self, path):
        return self._session(path)[4]
