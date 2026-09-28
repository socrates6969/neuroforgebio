"""Toy decoder: L2-regularised binary logistic regression in NumPy (BUILD-GUIDE 6.4).

Deliberately small and fully deterministic: zero initialisation, full-batch gradient descent with
a fixed step size and a fixed number of iterations, float64 throughout, no random numbers. The
same data and the same starting weights give bit-identical weights on the same NumPy build.

Features are z-scored with the mean / standard deviation of the data the model was trained on
(stored in the model, so prediction needs nothing else). Training is *resumable*: ``fit`` accepts
the weights of an earlier checkpoint and continues from them, which is what SISA's per-slice
checkpoints need (``nf_train.sisa``).

A toy for exercising the registry and the SISA retrain path. Not a validated decoder and not for
real-time or safety-critical control.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

SCHEMA = "nf.toy-logreg/v1"


@dataclass(frozen=True)
class FitParams:
    iterations: int = 200
    learning_rate: float = 0.5
    l2: float = 1e-2

    def doc(self) -> dict[str, Any]:
        return {"iterations": self.iterations, "learning_rate": self.learning_rate, "l2": self.l2}


@dataclass(frozen=True)
class LogReg:
    """Weights ``w`` (per feature), bias ``b`` and the z-score statistics ``mu`` / ``sd``."""

    w: np.ndarray
    b: float
    mu: np.ndarray
    sd: np.ndarray
    n_train: int

    def doc(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "w": [float(x) for x in self.w],
            "b": float(self.b),
            "mu": [float(x) for x in self.mu],
            "sd": [float(x) for x in self.sd],
            "n_train": int(self.n_train),
        }

    @classmethod
    def from_doc(cls, d: dict[str, Any]) -> LogReg:
        if d.get("schema") != SCHEMA:
            raise ValueError(f"not a {SCHEMA} document")
        return cls(
            w=np.asarray(d["w"], dtype=np.float64),
            b=float(d["b"]),
            mu=np.asarray(d["mu"], dtype=np.float64),
            sd=np.asarray(d["sd"], dtype=np.float64),
            n_train=int(d["n_train"]),
        )

    def proba(self, x: np.ndarray) -> np.ndarray:
        z = (np.asarray(x, dtype=np.float64) - self.mu) / self.sd
        return _sigmoid(z @ self.w + self.b)


def _sigmoid(t: np.ndarray) -> np.ndarray:
    return 0.5 * (1.0 + np.tanh(0.5 * t))  # numerically stable, deterministic


def fit(x: np.ndarray, y: np.ndarray, params: FitParams, start: LogReg | None = None) -> LogReg:
    """Train on ``x`` (n, p), labels ``y`` in {0, 1}; warm-start from ``start`` when given."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.ndim != 2 or y.shape != (x.shape[0],):
        raise ValueError("x must be (n, p) and y (n,)")
    if x.shape[0] == 0:
        raise ValueError("no training data")
    if not np.all((y == 0) | (y == 1)):
        raise ValueError("labels must be 0 or 1")
    mu = x.mean(axis=0)
    sd = x.std(axis=0)
    sd = np.where(sd > 1e-12, sd, 1.0)
    z = (x - mu) / sd
    n, p = z.shape
    if start is not None:
        if start.w.shape != (p,):
            raise ValueError("checkpoint has a different feature count")
        w, b = start.w.copy(), float(start.b)
    else:
        w, b = np.zeros(p), 0.0
    for _ in range(params.iterations):
        err = _sigmoid(z @ w + b) - y
        w = w - params.learning_rate * (z.T @ err / n + params.l2 * w)
        b = b - params.learning_rate * float(err.mean())
    return LogReg(w=w, b=b, mu=mu, sd=sd, n_train=n)


def accuracy(pred: np.ndarray, y: np.ndarray) -> float:
    y = np.asarray(y)
    return float(np.mean(np.asarray(pred) == y)) if y.size else float("nan")
