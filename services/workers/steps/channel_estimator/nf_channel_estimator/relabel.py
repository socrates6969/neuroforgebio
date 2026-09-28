"""Digitisation relabelling robustness (research P6, prereg section 5; DEVIATIONS P6 item 4).

In each draw exactly ``round(x N)`` PF electrodes (without replacement) get their R1 dominant
segment replaced by one of the 3 nearest other segments of the same surface (uniform), by
reference-table centroid distance; territories are then recomputed under R1. Ported verbatim from
the research code so that the same generator state gives the same draws.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TypedDict

import numpy as np

from .reference import NULL_TERRITORY_CLASSES, ReferenceData


class RelabelLevel(TypedDict):
    """Relabelling outcome for one fraction x."""

    fraction: float
    electrodes_relabelled: int
    draws: int
    p_k_digit_at_least: list[float]
    p_k_territory_at_least: list[float]
    p_k_digit_within_1_of_observed: float
    k_digit_distribution: dict[str, int]


def neighbour_table(ref: ReferenceData) -> np.ndarray:
    """Row index -> the 3 nearest other same-surface segments (centroid distance, stable ties)."""
    segs = ref.segments
    nbr = np.zeros((len(segs), 3), int)
    for i, s in enumerate(segs):
        cand = [
            (math.hypot(s["cx"] - t["cx"], s["cy"] - t["cy"]), j)
            for j, t in enumerate(segs)
            if j != i and t["surface"] == s["surface"]
        ]
        cand.sort()
        nbr[i] = [j for _, j in cand[:3]]
    return nbr


def relabel_draws(
    g: np.random.Generator,
    base: np.ndarray,
    nbr: np.ndarray,
    seg_tc: np.ndarray,
    x: float,
    draws: int,
    m: int,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Return (K_digit per draw, K_terr per draw, electrodes relabelled per draw)."""
    n = len(base)
    k = int(round(x * n))
    kd_all = np.zeros(draws, int)
    kt_all = np.zeros(draws, int)
    n_cls = len(NULL_TERRITORY_CLASSES)
    for b in range(draws):
        dom = base.copy()
        if k:
            idx = g.choice(n, k, replace=False)
            dom[idx] = nbr[dom[idx], g.integers(0, 3, k)]
        cnt = np.bincount(seg_tc[dom], minlength=n_cls)
        kd = int((cnt[:5] >= m).sum())
        kd_all[b] = kd
        kt_all[b] = kd + int(cnt[5] + cnt[6] >= m)
    return kd_all, kt_all, k


def run_relabelling(
    g: np.random.Generator,
    ref: ReferenceData,
    dominant_keys: Sequence[str],
    fractions: Sequence[float],
    draws: int,
    m: int,
    observed_k_digit: int,
) -> list[RelabelLevel]:
    """Relabelling summary for each fraction, consuming ``g`` in the research order."""
    kidx = ref.key_index
    base = np.array([kidx[k] for k in dominant_keys], int)
    nbr = neighbour_table(ref)
    seg_tc = np.array(ref.segment_territory_index)
    out: list[RelabelLevel] = []
    for x in fractions:
        kd, kt, k = relabel_draws(g, base, nbr, seg_tc, x, draws, m)
        out.append(
            {
                "fraction": float(x),
                "electrodes_relabelled": k,
                "draws": draws,
                "p_k_digit_at_least": [float(np.mean(kd >= lv)) for lv in range(1, 6)],
                "p_k_territory_at_least": [float(np.mean(kt >= lv)) for lv in range(1, 7)],
                "p_k_digit_within_1_of_observed": float(
                    np.mean(np.abs(kd - observed_k_digit) <= 1)
                ),
                "k_digit_distribution": {str(int(v)): int(np.sum(kd == v)) for v in np.unique(kd)},
            }
        )
    return out
