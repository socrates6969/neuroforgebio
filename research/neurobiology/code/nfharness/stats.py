"""AUROC / AUPRC, Clopper-Pearson, Garwood (exact Poisson), and bootstraps.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
"""
import numpy as np
from scipy.stats import beta, chi2, rankdata


def auroc(y, s):
    """Mann-Whitney AUROC with average ranks for ties. NaN if a class is absent."""
    y = np.asarray(y).astype(bool)
    n1 = int(y.sum())
    n0 = y.size - n1
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = rankdata(np.asarray(s, dtype=np.float64))
    return float((r[y].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def auprc(y, s):
    """Average precision (step interpolation, ties grouped), as in sklearn.average_precision_score."""
    y = np.asarray(y).astype(bool)
    n1 = int(y.sum())
    if n1 == 0:
        return float("nan")
    s = np.asarray(s, dtype=np.float64)
    o = np.argsort(-s, kind="mergesort")
    ss, yy = s[o], y[o]
    last = np.r_[np.flatnonzero(np.diff(ss) != 0), ss.size - 1]
    tp = np.cumsum(yy)[last]
    fp = (last + 1) - tp
    prec = tp / (tp + fp)
    rec = tp / n1
    rprev = np.r_[0.0, rec[:-1]]
    return float(np.sum((rec - rprev) * prec))


def clopper_pearson(k, n, alpha=0.05):
    if n == 0:
        return (float("nan"), float("nan"))
    lo = 0.0 if k == 0 else float(beta.ppf(alpha / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - alpha / 2, k + 1, n - k))
    return (lo, hi)


def garwood(k, alpha=0.05):
    """Exact Poisson interval on a count k: [chi2(a/2; 2k)/2, chi2(1-a/2; 2k+2)/2]."""
    lo = 0.0 if k == 0 else float(chi2.ppf(alpha / 2, 2 * k) / 2)
    hi = float(chi2.ppf(1 - alpha / 2, 2 * k + 2) / 2)
    return (lo, hi)


def bootstrap_indicators(ind, rng, B=10000):
    ind = np.asarray(ind, dtype=float)
    if ind.size == 0:
        return (float("nan"), float("nan"))
    m = ind[rng.integers(0, ind.size, size=(B, ind.size))].mean(axis=1)
    return (float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5)))


def block_bootstrap_auroc(ys, ss, rng, B=10000):
    """Resample files (blocks) with replacement within a subject; percentile 95% interval of AUROC."""
    # Exact and fast: AUROC of a resample with file multiplicities c is sum_fg c_f c_g U_fg / (sum c_f P_f)(sum c_g N_g),
    # with U_fg = Mann-Whitney pair count (ties 1/2) of positives of file f vs negatives of file g.
    k = len(ys)
    P = np.array([int(np.sum(y)) for y in ys], dtype=float)
    N = np.array([len(y) - int(np.sum(y)) for y in ys], dtype=float)
    U = np.zeros((k, k))
    negs = [np.sort(np.asarray(s, dtype=np.float64)[~np.asarray(y).astype(bool)]) for y, s in zip(ys, ss)]
    for f in range(k):
        pos = np.asarray(ss[f], dtype=np.float64)[np.asarray(ys[f]).astype(bool)]
        for g in range(k):
            lt = np.searchsorted(negs[g], pos, side="left")
            le = np.searchsorted(negs[g], pos, side="right")
            U[f, g] = lt.sum() + 0.5 * (le - lt).sum()
    idx = rng.integers(0, k, size=(B, k))
    C = np.zeros((B, k))
    np.add.at(C, (np.repeat(np.arange(B), k), idx.ravel()), 1.0)
    num = np.einsum("bf,fg,bg->b", C, U, C)
    den = (C @ P) * (C @ N)
    with np.errstate(invalid="ignore", divide="ignore"):
        v = np.where(den > 0, num / den, np.nan)
    v = np.asarray(v)[np.isfinite(v)]
    if v.size == 0:
        return (float("nan"), float("nan")), 0
    return (float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))), int(B - v.size)
