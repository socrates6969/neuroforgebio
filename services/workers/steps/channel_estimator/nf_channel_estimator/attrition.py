"""Exact attrition probability P(K >= k) under independent electrode survival (P6, prereg 4c).

Each electrode survives independently with probability ``p``. Territory classes are disjoint, so
class ``c`` with ``n_c`` electrodes keeps at least ``m`` survivors with probability ``q_c = 1 -
BinomCDF(m - 1; n_c, p)``, and the number of surviving channels is Poisson-binomial over the
classes. The research code computes the binomial CDF with scipy; here it is the exact finite sum
(numpy only). The two agree to ~1e-16, well inside the 1e-12 golden tolerance.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from itertools import product

import numpy as np


def binom_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k) for X ~ Binomial(n, p), as an exact finite sum."""
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    return float(sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k + 1)))


def class_keep_probability(n: int, p: float, m: int) -> float:
    """P(a class of ``n`` electrodes keeps >= ``m`` survivors); 0 if ``n < m``."""
    return 0.0 if n < m else float(1.0 - binom_cdf(m - 1, n, p))


def p_k_ge(nvec: Sequence[int], p: float, m: int, k: int) -> float:
    """Exact P(#classes keeping >= m survivors >= k): Poisson-binomial DP over disjoint classes."""
    q = [class_keep_probability(int(n), p, m) for n in nvec]
    dist = np.zeros(len(q) + 1)
    dist[0] = 1.0
    for qi in q:
        new = dist * (1 - qi)
        new[1:] += dist[:-1] * qi
        dist = new
    return float(dist[k:].sum()) if k <= len(q) else 0.0


def p_k_ge_curve(nvec: Sequence[int], p: float, m: int) -> list[float]:
    """[P(K >= 1), ..., P(K >= len(nvec))] from the same DP."""
    return [p_k_ge(nvec, p, m, k) for k in range(1, len(nvec) + 1)]


def p_k_ge_bruteforce(nvec: Sequence[int], p: float, m: int, k: int) -> float:
    """Independent check: enumerate every survivor-count vector (exponential; small inputs only)."""
    tot = 0.0
    for s in product(*[range(int(n) + 1) for n in nvec]):
        pr = 1.0
        for si, n in zip(s, nvec, strict=True):
            pr *= math.comb(int(n), si) * p**si * (1 - p) ** (int(n) - si)
        if sum(si >= m for si in s) >= k:
            tot += pr
    return tot
