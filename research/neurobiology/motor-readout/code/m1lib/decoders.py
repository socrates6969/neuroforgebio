"""Decoders for M1 (prereg §3): ridge (Wiener with history), velocity Kalman filter (steady state), GRU (torch CPU),
factor analysis + orthogonal Procrustes, shrinkage LDA, Riemannian tangent space + L2 logistic regression.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
"""
import copy
import hashlib

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit

from .metrics import r2_vw

LAMBDAS = np.logspace(-1, 5, 13)


def arr_hash(*arrs):
    h = hashlib.sha256()
    for a in arrs:
        h.update(np.ascontiguousarray(np.asarray(a, dtype=np.float64)).tobytes())
    return h.hexdigest()


# ---------------------------------------------------------------- ridge
class RidgePath:
    """Ridge with unpenalised intercept (X, Y centred on training means); all lambdas from one eigendecomposition."""

    def __init__(self, X, Y):
        self.xm = X.mean(0)
        self.ym = Y.mean(0)
        Xc = X - self.xm
        e, Q = np.linalg.eigh(Xc.T @ Xc)
        self.e, self.Q = e, Q
        self.QtXtY = Q.T @ (Xc.T @ (Y - self.ym))

    def coef(self, lam):
        W = self.Q @ (self.QtXtY / (self.e + lam)[:, None])
        return W, self.ym - self.xm @ W


class RidgeStream:
    """Same estimator as RidgePath, accumulated over row chunks (bounded RAM for wide designs)."""

    def __init__(self, p, d):
        self.G = np.zeros((p, p))
        self.xs = np.zeros(p)
        self.XtY = np.zeros((p, d))
        self.ys = np.zeros(d)
        self.n = 0

    def add(self, X, Y):
        self.G += X.T @ X
        self.xs += X.sum(0)
        self.XtY += X.T @ Y
        self.ys += Y.sum(0)
        self.n += len(X)

    def finalize(self, lams=LAMBDAS):
        xm, ym = self.xs / self.n, self.ys / self.n
        Gc = self.G - self.n * np.outer(xm, xm)
        XtYc = self.XtY - self.n * np.outer(xm, ym)
        e, Q = np.linalg.eigh(Gc)
        QtXtY = Q.T @ XtYc
        self.G = None
        out = []
        for lam in lams:
            W = Q @ (QtXtY / (e + lam)[:, None])
            out.append(Ridge(W, ym - xm @ W, float(lam)))
        return out


def select_ridge(models, val_chunks):
    """val_chunks: iterable of (X, Y) (re-iterable list or generator factory). First max of validation R^2."""
    ys, preds = [], [[] for _ in models]
    for X, Y in val_chunks():
        ys.append(Y)
        for i, m in enumerate(models):
            preds[i].append(m.predict(X))
    y = np.vstack(ys)
    sc = [r2_vw(y, np.vstack(p)) for p in preds]
    k = int(np.argmax(sc))
    return models[k], dict(lambda_=models[k].lam, val_r2=float(sc[k]), val_curve=[float(s) for s in sc])


class Ridge:
    def __init__(self, W, b, lam):
        self.W, self.b, self.lam = W, b, lam

    def predict(self, X):
        return X @ self.W + self.b

    def hash(self):
        return arr_hash(self.W, self.b, [self.lam])


def fit_ridge_select(Xtr, Ytr, val_pred_fn, lams=LAMBDAS):
    """val_pred_fn(model) -> (y_val, yhat_val). Chooses lambda by validation R^2 (first max). Model fitted on train."""
    path = RidgePath(Xtr, Ytr)
    best, scores = None, []
    for lam in lams:
        W, b = path.coef(lam)
        m = Ridge(W, b, float(lam))
        yv, yh = val_pred_fn(m)
        s = r2_vw(yv, yh)
        scores.append(s)
        if best is None or s > best[0]:
            best = (s, m)
    return best[1], dict(lambda_=best[1].lam, val_r2=float(best[0]), val_curve=[float(s) for s in scores])


# ---------------------------------------------------------------- Kalman
class KalmanVel:
    """State z = [v1, v2, 1]; A, Q, C, R by least squares [Wu 2006-style]; steady-state gain from the Riccati
    recursion iterated to convergence (TD §3.2); filter z_t = (I-KC) A z_{t-1} + K x_t."""

    def fit(self, Zsegs, Xsegs):
        Zs = [np.column_stack([z, np.ones(len(z))]) for z in Zsegs]
        Zp = np.vstack([z[:-1] for z in Zs])
        Zn = np.vstack([z[1:] for z in Zs])
        A = np.linalg.lstsq(Zp, Zn, rcond=None)[0].T
        A[2] = [0.0, 0.0, 1.0]
        Er = Zn - Zp @ A.T
        Q = Er.T @ Er / len(Er)
        Q[2, :] = 0.0
        Q[:, 2] = 0.0
        Z = np.vstack(Zs)
        X = np.vstack(Xsegs)
        C = np.linalg.lstsq(Z, X, rcond=None)[0].T
        E = X - Z @ C.T
        R = E.T @ E / len(E)
        self.A, self.Q, self.C, self.R = A, Q, C, R
        self.z0 = Z.mean(0)
        Rinv = np.linalg.inv(R)
        CtRinv = C.T @ Rinv
        CtRinvC = CtRinv @ C
        P = Q.copy()
        K = np.zeros((3, C.shape[0]))
        self.riccati_iters = None
        for it in range(20000):
            Pp = A @ P @ A.T + Q
            Kn = Pp @ np.linalg.solve(np.eye(3) + CtRinvC @ Pp, CtRinv)
            P = (np.eye(3) - Kn @ C) @ Pp
            if np.max(np.abs(Kn - K)) < 1e-13:
                K = Kn
                self.riccati_iters = it + 1
                break
            K = Kn
        self.K = K
        self.M = (np.eye(3) - K @ C) @ A
        return self

    def predict(self, X):
        z = self.z0.copy()
        out = np.empty((len(X), 2))
        KX = X @ self.K.T
        for t in range(len(X)):
            z = self.M @ z + KX[t]
            out[t] = z[:2]
        return out

    def hash(self):
        return arr_hash(self.A, self.Q, self.C, self.R, self.K, self.z0)


# ---------------------------------------------------------------- GRU (torch)
def torch_setup():
    import torch
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    return torch


def make_gru(n_in, d_out, h=64):
    import torch.nn as nn

    class GRUDec(nn.Module):
        def __init__(self):
            super().__init__()
            self.drop = nn.Dropout(0.2)
            self.gru = nn.GRU(n_in, h, num_layers=1, batch_first=True)
            self.out = nn.Linear(h, d_out)

        def forward(self, x):
            y, _ = self.gru(self.drop(x))
            return self.out(y)
    return GRUDec()


class GRUEnsemble:
    def __init__(self, models, ym, ys):
        self.models, self.ym, self.ys = models, ym, ys

    def predict_seqs(self, Xs):
        """Xs [S, T, N] float -> [S, T, d] averaged over seeds, original units."""
        import torch
        out = 0
        with torch.no_grad():
            x = torch.from_numpy(np.ascontiguousarray(Xs, dtype=np.float32))
            for m in self.models:
                m.eval()
                out = out + m(x).numpy().astype(np.float64)
        return out / len(self.models) * self.ys + self.ym

    def hash(self):
        h = hashlib.sha256()
        for m in self.models:
            for k, v in m.state_dict().items():
                h.update(k.encode())
                h.update(v.detach().numpy().tobytes())
        h.update(np.asarray(self.ym, np.float64).tobytes())
        h.update(np.asarray(self.ys, np.float64).tobytes())
        return h.hexdigest()


def train_gru(Xs, Ys, mask, val_fn, seeds=(20261001, 20261002, 20261003), batch=32, max_epochs=50, patience=5,
              lr=1e-3, wd=1e-4):
    """Xs [S, T, N], Ys [S, T, d] (NaN allowed where mask==0), mask [S, T] 1 = in loss.
    val_fn(GRUEnsemble-of-one) -> validation R^2 (early stopping). Returns GRUEnsemble and per-seed info."""
    torch = torch_setup()
    ym = np.nanmean(Ys[mask > 0], axis=0)
    ys = np.nanstd(Ys[mask > 0], axis=0)
    Yn = np.where(mask[..., None] > 0, (Ys - ym) / ys, 0.0)
    X_t = torch.from_numpy(np.ascontiguousarray(Xs, dtype=np.float32))
    Y_t = torch.from_numpy(np.ascontiguousarray(Yn, dtype=np.float32))
    M_t = torch.from_numpy(np.ascontiguousarray(mask, dtype=np.float32))
    models, info = [], []
    S = Xs.shape[0]
    for seed in seeds:
        torch.manual_seed(seed)
        rng = np.random.default_rng(seed)
        m = make_gru(Xs.shape[2], Ys.shape[2])
        opt = torch.optim.Adam(m.parameters(), lr=lr, weight_decay=wd)
        best, best_state, bad, curve = -np.inf, None, 0, []
        for ep in range(max_epochs):
            m.train()
            perm = rng.permutation(S)
            for i in range(0, S, batch):
                b = torch.from_numpy(perm[i:i + batch])
                opt.zero_grad()
                pr = m(X_t[b])
                w = M_t[b].unsqueeze(-1)
                loss = (((pr - Y_t[b]) ** 2) * w).sum() / (w.sum() * pr.shape[-1])
                loss.backward()
                opt.step()
            m.eval()
            v = float(val_fn(GRUEnsemble([m], ym, ys)))
            curve.append(v)
            if v > best:
                best, best_state, bad = v, copy.deepcopy(m.state_dict()), 0
            else:
                bad += 1
                if bad >= patience:
                    break
        m.load_state_dict(best_state)
        m.eval()
        models.append(m)
        info.append(dict(seed=seed, epochs=len(curve), best_val_r2=float(best), best_epoch=int(np.argmax(curve)) + 1))
    return GRUEnsemble(models, ym, ys), info


# ---------------------------------------------------------------- factor analysis + Procrustes (TD §5.2)
class FA:
    def fit(self, X, k=10, iters=200):
        self.mu = X.mean(0)
        Xc = X - self.mu
        S = Xc.T @ Xc / len(Xc)
        e, V = np.linalg.eigh(S)
        e, V = e[::-1], V[:, ::-1]
        s2 = e[k:].mean()
        L = V[:, :k] * np.sqrt(np.maximum(e[:k] - s2, 1e-9))
        psi = np.maximum(np.diag(S) - (L * L).sum(1), 1e-6 * np.diag(S).mean())
        for _ in range(iters):
            B = L.T / psi
            G = np.linalg.inv(np.eye(k) + B @ L)
            beta = G @ B
            Ezz = G + beta @ S @ beta.T
            L = S @ beta.T @ np.linalg.inv(Ezz)
            psi = np.maximum(np.diag(S) - np.einsum("ij,ji->i", L, beta @ S), 1e-6 * np.diag(S).mean())
        self.L, self.psi, self.k = L, psi, k
        B = L.T / psi
        self.beta = np.linalg.inv(np.eye(k) + B @ L) @ B
        return self

    def posterior_mean(self, X):
        return (X - self.mu) @ self.beta.T


def procrustes(Lk, L0):
    """O = argmin_{O'O=I} ||Lk O - L0||_F = U V' with U S V' = svd(Lk' L0)."""
    U, _, Vt = np.linalg.svd(Lk.T @ L0)
    return U @ Vt


# ---------------------------------------------------------------- D3: shrinkage LDA
class ShrinkLDA:
    def fit(self, X, y, gamma):
        c0, c1 = X[y == 0], X[y == 1]
        m0, m1 = c0.mean(0), c1.mean(0)
        Sw = (np.cov(c0, rowvar=False, bias=True) * len(c0) + np.cov(c1, rowvar=False, bias=True) * len(c1)) / len(X)
        p = X.shape[1]
        Sg = (1 - gamma) * Sw + gamma * np.trace(Sw) / p * np.eye(p)
        self.w = np.linalg.pinv(Sg) @ (m1 - m0)
        self.b = -self.w @ (m0 + m1) / 2 + np.log(len(c1) / len(c0))
        return self

    def predict(self, X):
        return (X @ self.w + self.b > 0).astype(int)


# ---------------------------------------------------------------- D3: Riemannian tangent space
def _eig_fn(C, f):
    e, V = np.linalg.eigh(C)
    return (V * f(e)) @ V.T


def riemann_mean(Cs, iters=20, tol=1e-8):
    M = Cs.mean(0)
    for _ in range(iters):
        Ms = _eig_fn(M, np.sqrt)
        Mi = _eig_fn(M, lambda e: 1 / np.sqrt(e))
        T = np.mean([_eig_fn(Mi @ C @ Mi, np.log) for C in Cs], axis=0)
        M = Ms @ _eig_fn(T, np.exp) @ Ms
        if np.linalg.norm(T) < tol:
            break
    return M


def tangent(Cs, M):
    Mi = _eig_fn(M, lambda e: 1 / np.sqrt(e))
    n = M.shape[0]
    iu = np.triu_indices(n)
    coef = np.where(iu[0] == iu[1], 1.0, np.sqrt(2.0))
    return np.array([_eig_fn(Mi @ C @ Mi, np.log)[iu] * coef for C in Cs])


def reg_cov(X):
    """X [n_ch, T] -> X X'/(T-1) + 1e-3 tr(C)/n I."""
    C = X @ X.T / (X.shape[1] - 1)
    return C + 1e-3 * np.trace(C) / C.shape[0] * np.eye(C.shape[0])


class LogRegL2:
    """min 0.5||w||^2 + C sum log(1+exp(-s_i (w.x_i + b))); intercept unpenalised; L-BFGS-B from zeros."""

    def fit(self, X, y, C):
        s = 2.0 * y - 1.0

        def f(p):
            w, b = p[:-1], p[-1]
            m = s * (X @ w + b)
            lo = np.logaddexp(0, -m)
            g = -s * expit(-m)
            return 0.5 * w @ w + C * lo.sum(), np.concatenate([w + C * (X.T @ g), [C * g.sum()]])
        r = minimize(f, np.zeros(X.shape[1] + 1), jac=True, method="L-BFGS-B", options=dict(gtol=1e-6, maxiter=1000))
        self.w, self.b = r.x[:-1], r.x[-1]
        return self

    def predict(self, X):
        return (X @ self.w + self.b > 0).astype(int)
