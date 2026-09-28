"""Decoding metric step for multiverse sweeps (BUILD-GUIDE 3.6; m3-sweeps).

``nf_steps.decode_lda@1``: cross-validated classification accuracy of a **shrinkage linear
discriminant analysis implemented in NumPy** (no scikit-learn on the dev PC; the name says what it
is). Input: a ``features`` signal (``band_power``) with one label per epoch in
``meta["event_codes"]`` (set by ``epochs``). Output: a one-row ``features`` signal whose data are
``[accuracy, fold_1, ..., fold_k]`` and whose metadata repeat the numbers, so the metric is part of
a content-hashed, provenance-linked artifact (the sweep report cites that artifact's node).

Model (per training fold; nothing is fitted on the test fold):

- features: every (channel, band) value of the non-bad channels, ``log10`` when ``log`` is true;
- z-scored with the training mean / standard deviation;
- pooled within-class covariance ``S`` shrunk toward ``trace(S)/p * I`` with weight ``shrinkage``;
- class scores ``x S^-1 m_k - m_k S^-1 m_k / 2 + log(prior_k)``; the highest score wins (ties go
  to the lowest class code).

Folds are deterministic and stratified: the r-th epoch (in time order) of each class goes to fold
``r % n_folds``. No random numbers, so the step needs no seed.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from pydantic import Field

from nf_steps.base import Params, StepError
from nf_steps.signal import Signal
from nf_steps.steps import LIBRARY

METRIC = "accuracy"


class DecodeLdaParams(Params):
    labels: Literal["event_codes"] = "event_codes"
    n_folds: int = Field(default=5, ge=2, le=20)
    shrinkage: float = Field(default=0.1, ge=0.0, le=1.0)
    log: bool = Field(default=True, description="log10 of the features (band power)")
    exclude_bads: bool = True


def stratified_folds(y: np.ndarray, n_folds: int) -> np.ndarray:
    """Fold index per sample: the r-th sample of each class (in order) goes to fold r % n_folds."""
    folds = np.empty(len(y), dtype=np.int64)
    for c in np.unique(y):
        idx = np.flatnonzero(y == c)
        folds[idx] = np.arange(len(idx)) % n_folds
    return folds


def fit_lda(x: np.ndarray, y: np.ndarray, shrinkage: float):
    """Returns (classes, W, b): scores = x @ W + b (x already standardized)."""
    classes = np.unique(y)
    p = x.shape[1]
    means = np.stack([x[y == c].mean(axis=0) for c in classes])
    resid = x - means[np.searchsorted(classes, y)]
    dof = max(len(y) - len(classes), 1)
    cov = resid.T @ resid / dof
    target = np.trace(cov) / p if p else 0.0
    cov = (1.0 - shrinkage) * cov + shrinkage * target * np.eye(p)
    cov += 1e-12 * np.eye(p)  # keeps a degenerate (e.g. all-constant) fold solvable
    w = np.linalg.solve(cov, means.T)  # (p, n_classes)
    priors = np.array([np.mean(y == c) for c in classes])
    b = -0.5 * np.sum(means.T * w, axis=0) + np.log(priors)
    return classes, w, b


def predict_lda(model, x: np.ndarray) -> np.ndarray:
    classes, w, b = model
    return classes[np.argmax(x @ w + b, axis=1)]


def cross_validate(
    x: np.ndarray, y: np.ndarray, n_folds: int, shrinkage: float
) -> tuple[float, list[float]]:
    folds = stratified_folds(y, n_folds)
    correct = 0
    fold_acc = []
    for k in range(n_folds):
        test = folds == k
        train = ~test
        mu = x[train].mean(axis=0)
        sd = x[train].std(axis=0)
        sd[sd == 0] = 1.0
        model = fit_lda((x[train] - mu) / sd, y[train], shrinkage)
        pred = predict_lda(model, (x[test] - mu) / sd)
        hits = int(np.sum(pred == y[test]))
        correct += hits
        fold_acc.append(hits / int(test.sum()))
    return correct / len(y), fold_acc


@LIBRARY.step("decode_lda", "1", DecodeLdaParams, ("features",))
def decode_lda_step(sig: Signal, p: DecodeLdaParams, _seed: int | None):
    """Cross-validated accuracy of a NumPy shrinkage-LDA classifier on per-epoch features,
    labels = the epochs' event codes (see module docstring)."""
    codes = sig.meta.get("event_codes")
    n_ep = sig.data.shape[0]
    if not isinstance(codes, list) or len(codes) != n_ep:
        raise StepError("decode_lda needs meta.event_codes with one label per epoch (epochs step)")
    y = np.asarray(codes, dtype=np.int64)
    classes, counts = np.unique(y, return_counts=True)
    if len(classes) < 2:
        raise StepError("decode_lda needs at least two classes")
    if int(counts.min()) < p.n_folds:
        raise StepError(f"every class needs at least n_folds={p.n_folds} epochs")
    keep = [i for i, c in enumerate(sig.ch_names) if not (p.exclude_bads and c in set(sig.bads))]
    if not keep:
        raise StepError("no channels left after excluding bad channels")
    feats = sig.data[:, keep, :].reshape(n_ep, -1)
    if p.log:
        if np.any(feats <= 0):
            raise StepError("log features need positive values (band power)")
        feats = np.log10(feats)
    if not np.all(np.isfinite(feats)):
        raise StepError("features are not finite")
    acc, fold_acc = cross_validate(feats, y, p.n_folds, p.shrinkage)
    chance = float(counts.max() / counts.sum())
    summary = {
        "metric": METRIC,
        METRIC: acc,
        "fold_accuracy": fold_acc,
        "chance_level": chance,
        "n_trials": int(n_ep),
        "n_features": int(feats.shape[1]),
        "classes": [int(c) for c in classes],
        "class_counts": [int(c) for c in counts],
    }
    out = Signal(
        kind="features",
        data=np.asarray([[[acc, *fold_acc]]], dtype=float),
        sfreq=sig.sfreq,
        ch_names=["decoder"],
        ch_types=["misc"],
        meta={
            "feature_names": [METRIC] + [f"fold_{k + 1}" for k in range(p.n_folds)],
            "decode": summary,
        },
    )
    return out, summary
