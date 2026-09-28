"""Labelling rules and count statistics (port of research P6, prereg section 3-4).

Ported line for line from ``research/somatosensory/code/p6_empirical_channels.py`` (independently
reviewed, cycle 4). The rules are the pre-registered ones; do not change them without a new review.

Territories: ``D1``..``D5`` (digits), ``PALM``, ``DORSUM_HAND``, ``WRIST`` and, under the strict
rule R3, ``HAND`` (palm/dorsum-of-hand only) and ``MIXED``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Literal

import numpy as np

Rule = Literal["R1", "R2", "R3", "ray"]
RULES: tuple[Rule, ...] = ("R1", "R2", "R3", "ray")
DIGITS: tuple[str, ...] = ("D1", "D2", "D3", "D4", "D5")
# Classes pooled into the 6th ("hand") territory. HAND is the pooled class of the R3 variant.
HAND_CLASSES: tuple[str, ...] = ("PALM", "DORSUM_HAND", "HAND")
Surface = Literal["palm", "dors"]


def tmap(surface: Surface, tag: str, ray: bool = False) -> str | None:
    """Territory of one segment tag (prereg 3; research DEVIATIONS P6 item 1).

    ``Dk...`` -> ``Dk``; ``W`` -> ``WRIST``; any other palm tag -> ``PALM`` (with ``ray``, a palm
    ``P{2..5}...-mcp`` tag maps to its digit instead); any other dorsum tag -> ``DORSUM_HAND``.
    An empty tag has no territory (``None``).
    """
    if not tag:
        return None
    if tag[0] == "D" and len(tag) > 1 and tag[1] in "12345":
        return "D" + tag[1]
    if tag == "W":
        return "WRIST"
    if surface == "palm":
        if ray and tag[0] == "P" and len(tag) > 1 and tag[1] in "2345" and tag.endswith("-mcp"):
            return "D" + tag[1]
        return "PALM"
    return "DORSUM_HAND"


def territory(palm: str, dors: str, rule: Rule) -> str | None:
    """Territory of one electrode from its palm and dorsum segment tags under a labelling rule.

    - R1 (primary, palm first): the palm territory if the palm tag is set, else the dorsum one.
    - R2 (liberal): the first digit territory among (palm, dorsum); else as R1.
    - R3 (strict): a digit only if every non-empty segment maps to that digit; palm/dorsum-of-hand
      only -> ``HAND``; anything else -> ``MIXED``.
    - ray: R1 with palm ``P{k}-mcp`` mapped to digit ``Dk``.
    """
    tp, td = tmap("palm", palm), tmap("dors", dors)
    if rule == "R1":
        return tp if tp is not None else td
    if rule == "ray":
        a = tmap("palm", palm, ray=True)
        return a if a is not None else td
    if rule == "R2":
        for t in (tp, td):
            if t in DIGITS:
                return t
        return tp if tp is not None else td
    if rule == "R3":
        ts = {t for t in (tp, td) if t is not None}
        if len(ts) == 1 and next(iter(ts)) in DIGITS:
            return next(iter(ts))
        if ts and ts <= {"PALM", "DORSUM_HAND"}:
            return "HAND"
        return "MIXED"
    raise ValueError(f"unknown labelling rule {rule!r}")


def dominant_segment(palm: str, dors: str) -> str:
    """R1 dominant segment key: ``palm:<tag>`` if the palm tag is set, else ``dors:<tag>``."""
    return ("palm:" + palm) if palm else ("dors:" + dors)


def counts_of(labels: Iterable[str | None]) -> dict[str | None, int]:
    """Class sizes in first-seen order."""
    c: dict[str | None, int] = {}
    for t in labels:
        c[t] = c.get(t, 0) + 1
    return c


def k_digit(c: Mapping[str | None, int], m: int) -> int:
    """Number of digit territories with at least ``m`` electrodes."""
    return int(sum(c.get(d, 0) >= m for d in DIGITS))


def n_hand(c: Mapping[str | None, int]) -> int:
    """Electrodes in the pooled palm/dorsum-of-hand class."""
    return sum(c.get(h, 0) for h in HAND_CLASSES)


def k_terr(c: Mapping[str | None, int], m: int) -> int:
    """K_digit plus 1 if the pooled hand class has at least ``m`` electrodes (the 6th territory)."""
    return k_digit(c, m) + int(n_hand(c) >= m)


def neff(c: Mapping[str | None, int]) -> float:
    """Inverse Simpson index N^2 / sum n_c^2 (participation ratio); NaN for an empty map."""
    n = np.array([v for v in c.values() if v > 0], float)
    if n.size == 0:
        return float("nan")
    return float(n.sum() ** 2 / np.sum(n**2))


def neff_bias_corrected(c: Mapping[str | None, int]) -> float | None:
    """N(N-1) / sum n_c(n_c-1); ``None`` when every class has one electrode (undefined)."""
    n = np.array([v for v in c.values() if v > 0], float)
    den = np.sum(n * (n - 1))
    total = n.sum()
    return None if den == 0 else float(total * (total - 1) / den)


def neff_soft(sets: Sequence[set[str]]) -> float:
    """Participation ratio of the Jaccard matrix over electrode segment sets (descriptive)."""
    n = len(sets)
    if n == 0:
        return float("nan")
    s = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            u = sets[i] | sets[j]
            s[i, j] = len(sets[i] & sets[j]) / len(u) if u else 0.0
    return float(np.trace(s) ** 2 / np.sum(s**2))


def class_vector(c: Mapping[str | None, int], territory_level: bool) -> list[int]:
    """Disjoint class sizes for the DP: D1..D5, plus the pooled hand class at territory level."""
    v = [c.get(d, 0) for d in DIGITS]
    if territory_level:
        v.append(n_hand(c))
    return v
