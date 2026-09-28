"""Normaliser (F1 guard), L2 logistic regression (N2 §2), config lock (F2) and resampling guard (F5).

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
Window IDs are (file_name, window_index) pairs; ID sets are represented as {file: int array of window indices}.
"""
import numpy as np
from scipy.optimize import minimize

from .config import LOCKED_CONFIG_HASH_LITERAL, config_hash, guard_hit
from .errors import ConfigLockError, NormaliserLeakError, ResamplingLeakError


def _ids_intersect(a, b):
    for f, ia in a.items():
        ib = b.get(f)
        if ib is not None and len(ia) and len(ib) and np.intersect1d(ia, ib).size:
            return True
    return False


def assert_config_locked(cfg):
    """F2: the config actually used must hash to the locked N2 config."""
    guard_hit("F2")
    h = config_hash(cfg)
    if h != LOCKED_CONFIG_HASH_LITERAL:
        raise ConfigLockError("model config hash %s != locked %s" % (h[:12], LOCKED_CONFIG_HASH_LITERAL[:12]))
    return h


def assert_search_ids(search_files, forbidden_files):
    """F2: the inner-CV / search routine refuses any test-file ID."""
    guard_hit("F2")
    bad = sorted(set(search_files) & set(forbidden_files))
    if bad:
        raise ConfigLockError("inner CV / search received test files: %s" % bad)


class ZScore:
    """Per-feature z-score (ddof=0, SD floor 1e-8). Remembers the IDs it was fitted on (F1)."""

    def __init__(self, sd_floor=1e-8):
        self.sd_floor = sd_floor
        self.fit_ids = None

    def fit(self, X, ids):
        X = np.asarray(X, dtype=np.float64)
        self.mu = X.mean(axis=0)
        self.sd = np.maximum(X.std(axis=0, ddof=0), self.sd_floor)
        self.fit_ids = {f: np.asarray(v) for f, v in ids.items()}
        return self

    def transform_training(self, X):
        """Apply to the training matrix itself (the data it was fitted on)."""
        return (np.asarray(X, dtype=np.float64) - self.mu) / self.sd

    def transform(self, X, ids, allow_leak=False):
        """ids = the window IDs of X. Raises if any of them was used to fit (unless the C2b leak control)."""
        guard_hit("F1")
        if not allow_leak and _ids_intersect(self.fit_ids, ids):
            raise NormaliserLeakError("normaliser was fitted on windows it is now applied to as test data")
        return (np.asarray(X, dtype=np.float64) - self.mu) / self.sd


class LogRegL2:
    """sum_i w_i log(1+exp(-y_i(b.z_i+b0))) + ||b||^2/(2C); balanced weights; zero init; scipy L-BFGS-B."""

    def __init__(self, C=1.0, gtol=1e-6, maxiter=1000):
        self.C, self.gtol, self.maxiter = C, gtol, maxiter

    def fit(self, Z, y):
        Z = np.asarray(Z, dtype=np.float64)
        y01 = np.asarray(y).astype(np.int64)
        n = y01.size
        n1 = int(y01.sum())
        n0 = n - n1
        if n1 == 0 or n0 == 0:
            raise ValueError("need both classes to fit")
        w = np.where(y01 == 1, n / (2.0 * n1), n / (2.0 * n0))
        ys = np.where(y01 == 1, 1.0, -1.0)
        d = Z.shape[1]
        C = self.C

        def fg(theta):
            beta, b0 = theta[:d], theta[d]
            m = ys * (Z @ beta + b0)
            loss = np.sum(w * np.logaddexp(0.0, -m)) + beta @ beta / (2 * C)
            s = -w * ys * _expit(-m)
            g = np.empty(d + 1)
            g[:d] = Z.T @ s + beta / C
            g[d] = s.sum()
            return loss, g
        r = minimize(fg, np.zeros(d + 1), jac=True, method="L-BFGS-B",
                     options={"gtol": self.gtol, "maxiter": self.maxiter})
        self.coef_, self.intercept_ = r.x[:d].copy(), float(r.x[d])
        self.converged_, self.n_iter_, self.message_ = bool(r.success), int(r.nit), str(r.message)
        return self

    def predict_proba(self, Z):
        return _expit(np.asarray(Z, dtype=np.float64) @ self.coef_ + self.intercept_)


def _expit(x):
    out = np.empty_like(x)
    pos = x >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-x[pos]))
    ex = np.exp(x[~pos])
    out[~pos] = ex / (1.0 + ex)
    return out


def resample_training(ids, train_files, rng, factor=2, labels=None):
    """F5: any resampling / augmentation routine may receive TRAINING IDs only. N2 uses none; the guard exists
    so that future models cannot oversample from pooled train+test data."""
    guard_hit("F5")
    bad = sorted(set(ids) - set(train_files))
    if bad:
        raise ResamplingLeakError("resampling received non-training files: %s" % bad)
    return {f: np.repeat(np.asarray(v), factor) for f, v in ids.items()}
