"""Spatially random nulls for N_eff (research P6 control C4, prereg section 7).

N_eff depends only on the label multiset, so "spatially random" means each of the map's N PF
electrodes lands on the hand independently of the others:

- Null A (area-proportional): each electrode gets a segment with probability proportional to segment
  area (full reference table, palm and dorsum pooled). A variant without the wrist segment is
  reported.
- Null B (pooled marginal): segments drawn i.i.d. from the pooled R1 dominant segments of the three
  published participants.

The draws are ported verbatim from the research code (same numpy calls, same order), so with the
same generator state they reproduce the research numbers bit for bit. p = P(null N_eff <= observed),
ties counted; ratio = observed / null median.
"""

from __future__ import annotations

from typing import TypedDict

import numpy as np

from .reference import NULL_TERRITORY_CLASSES, ReferenceData


class NullStat(TypedDict):
    """Observed statistic vs a null distribution."""

    observed: float
    null_median: float
    ratio: float | None
    p_value: float


class NullCountStat(TypedDict):
    """Observed K_digit vs its null distribution (descriptive)."""

    observed: int
    null_median: float
    p_value: float


class NullBlock(TypedDict):
    """One null model at segment and digit level."""

    segment_level: NullStat
    digit_level: NullStat
    k_digit: NullCountStat


class NullNoWrist(TypedDict):
    """Null A without the wrist segment, segment level only (descriptive)."""

    null_median: float
    p_value: float


def counts_from_idx(cls_idx: np.ndarray, n_classes: int) -> np.ndarray:
    """Row-wise class counts of a (draws x N) index matrix."""
    b = cls_idx.shape[0]
    out = np.zeros((b, n_classes))
    np.add.at(out, (np.repeat(np.arange(b), cls_idx.shape[1]), cls_idx.ravel()), 1)
    return out


def neff_rows(cnt: np.ndarray) -> np.ndarray:
    """Row-wise inverse Simpson index."""
    n = cnt.sum(1)
    return n**2 / np.sum(cnt**2, 1)


def area_weights(ref: ReferenceData, without_wrist: bool = False) -> np.ndarray:
    """Null A segment probabilities (area-proportional; optionally with the wrist set to 0)."""
    if without_wrist:
        w = np.array([0.0 if s["tag"] == "W" else s["area_mm2"] for s in ref.segments])
    else:
        w = np.array([s["area_mm2"] for s in ref.segments], float)
    return w / w.sum()


def draw_null_a(g: np.random.Generator, ref: ReferenceData, n: int, draws: int) -> np.ndarray:
    """Null A segment indices, shape (draws, n)."""
    return g.choice(len(ref.segments), (draws, n), p=area_weights(ref))


def draw_null_a_no_wrist(
    g: np.random.Generator, ref: ReferenceData, n: int, draws: int
) -> np.ndarray:
    """Null A without the wrist, shape (draws, n)."""
    return g.choice(len(ref.segments), (draws, n), p=area_weights(ref, without_wrist=True))


def draw_null_b(g: np.random.Generator, ref: ReferenceData, n: int, draws: int) -> np.ndarray:
    """Null B segment indices, shape (draws, n)."""
    kidx = ref.key_index
    pooled = np.array([kidx[k] for k in ref.pooled_keys])
    return pooled[g.integers(0, len(pooled), (draws, n))]


def _ratio(obs: float, med: float) -> float | None:
    return None if med == 0 else obs / med


def summarise_null(
    seg_idx: np.ndarray, ref: ReferenceData, obs_seg: float, obs_digit: float, obs_k: int, m: int
) -> NullBlock:
    """Compare observed N_eff (segment, digit) and K_digit(m) with the null draws ``seg_idx``."""
    seg_tc = np.array(ref.segment_territory_index)
    ns = neff_rows(counts_from_idx(seg_idx, len(ref.segments)))
    cd = counts_from_idx(seg_tc[seg_idx], len(NULL_TERRITORY_CLASSES))
    nd = neff_rows(cd)
    kd = (cd[:, :5] >= m).sum(1)
    ms, md = float(np.median(ns)), float(np.median(nd))
    return {
        "segment_level": {
            "observed": obs_seg,
            "null_median": ms,
            "ratio": _ratio(obs_seg, ms),
            "p_value": float(np.mean(ns <= obs_seg)),
        },
        "digit_level": {
            "observed": obs_digit,
            "null_median": md,
            "ratio": _ratio(obs_digit, md),
            "p_value": float(np.mean(nd <= obs_digit)),
        },
        "k_digit": {
            "observed": int(obs_k),
            "null_median": float(np.median(kd)),
            "p_value": float(np.mean(kd <= obs_k)),
        },
    }


def summarise_no_wrist(seg_idx: np.ndarray, ref: ReferenceData, obs_seg: float) -> NullNoWrist:
    """Segment-level summary of the no-wrist Null A draws."""
    ns = neff_rows(counts_from_idx(seg_idx, len(ref.segments)))
    return {"null_median": float(np.median(ns)), "p_value": float(np.mean(ns <= obs_seg))}


class NullResults(TypedDict):
    """All three null summaries for one map."""

    null_a_area: NullBlock
    null_b_pooled: NullBlock
    null_a_area_no_wrist: NullNoWrist


def run_nulls(
    g_a: np.random.Generator,
    g_b: np.random.Generator,
    ref: ReferenceData,
    n: int,
    draws: int,
    obs_seg: float,
    obs_digit: float,
    obs_k: int,
    m: int,
) -> NullResults:
    """Null A, Null B, then Null A without wrist, consuming the generators in the research order."""
    a = summarise_null(draw_null_a(g_a, ref, n, draws), ref, obs_seg, obs_digit, obs_k, m)
    b = summarise_null(draw_null_b(g_b, ref, n, draws), ref, obs_seg, obs_digit, obs_k, m)
    nw = summarise_no_wrist(draw_null_a_no_wrist(g_a, ref, n, draws), ref, obs_seg)
    return {"null_a_area": a, "null_b_pooled": b, "null_a_area_no_wrist": nw}
