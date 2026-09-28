"""Causal k-of-n post-processing and the training-only threshold selector (F3).

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
"""
from dataclasses import dataclass

import numpy as np

from .config import K_OF_N, TAU_GRID, guard_hit
from .errors import ThresholdSelectionError


def assert_kn(k, n):
    guard_hit("F3")
    if (k, n) != K_OF_N:
        raise ThresholdSelectionError("k-of-n must be %s, got %s" % (K_OF_N, (k, n)))


def assert_tau(tau):
    guard_hit("F3")
    if not any(abs(tau - g) < 1e-12 for g in TAU_GRID):
        raise ThresholdSelectionError("tau %r not in the locked grid" % tau)


def hypothesis_mask(p, tau, duration, k=4, n=5):
    """p: raw window scores of one file (len T-1). Returns the 1-Hz hypothesis mask (len T):
    b_i = p_i >= tau; d_i = 1 iff >= k of windows i-n+1..i have b = 1 (d_i = 0 for i < k-1);
    second j = d_{j-1}, second 0 = 0."""
    assert_kn(k, n)
    b = (np.asarray(p) >= tau).astype(np.int32)
    c = np.convolve(b, np.ones(n, dtype=np.int32))[:b.size]      # sum over i-n+1..i (truncated at file start)
    d = (c >= k).astype(np.int8)
    d[:k - 1] = 0
    m = np.zeros(int(duration), dtype=np.int8)
    m[1:1 + d.size] = d[:int(duration) - 1]
    return m


@dataclass(frozen=True)
class TaggedScores:
    """Window scores with provenance. Only tag == 'train_oof' is accepted by the threshold selector."""
    tag: str
    scores: dict          # {file: p array}
    durations: dict       # {file: seconds}


def select_tau(oof, fa_of_masks, fa_target=12.0, grid=TAU_GRID):
    """F3: tau* = smallest grid value whose training-OOF event FA/24 h <= fa_target; 0.99 if none.
    fa_of_masks(masks_by_file) -> FA per 24 h on the training files (training labels only)."""
    guard_hit("F3")
    if not isinstance(oof, TaggedScores) or oof.tag != "train_oof":
        raise ThresholdSelectionError("threshold selection accepts only train_oof scores, got %r"
                                      % getattr(oof, "tag", type(oof).__name__))
    if tuple(grid) != TAU_GRID:
        raise ThresholdSelectionError("tau grid differs from the locked grid")
    curve = []
    for tau in grid:
        masks = {f: hypothesis_mask(oof.scores[f], tau, oof.durations[f]) for f in oof.scores}
        fa = fa_of_masks(masks)
        curve.append((tau, fa))
        if fa <= fa_target:
            assert_tau(tau)
            return tau, curve
    return 0.99, curve
