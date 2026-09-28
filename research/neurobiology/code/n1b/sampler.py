"""Sampler S (prereg §2.2): phantom seizures placed by EXACT enumeration of the valid (segment, onset) set.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
Definition implemented (DEVIATIONS N1b-3):
- phantoms are placed in a fixed order: longest first, ties by (file order, seizure index within file);
- a phantom of duration d in a segment of length L may start at an integer onset o (segment-local seconds) iff
  [o - 30, o + d + 60) lies inside [0, L)  <=>  30 <= o <= L - d - 60;
- and, for every phantom (o', d') already placed in the SAME segment, the gap between the two intervals is >= 300 s:
  o + d + 300 <= o'  or  o >= o' + d' + 300;
- the valid set is enumerated in (segment order, onset ascending) and one element is drawn uniformly with
  rng.integers(0, |valid set|). An empty valid set returns None (the caller redraws the replicate and logs it).
"""
import numpy as np

PRE_TOL, POST_TOL, MIN_GAP = 30, 60, 300


def placement_order(durations):
    """durations: [(d, file_order, k)] -> list of d in placement order (longest first, ties by file order)."""
    return [d for d, fo, k in sorted(durations, key=lambda x: (-x[0], x[1], x[2]))]


def valid_onsets(L, d, placed=()):
    """All valid integer onsets of a phantom of duration d in a segment of length L, given phantoms already placed in
    that segment as [(onset, duration)]."""
    lo, hi = PRE_TOL, int(L) - int(d) - POST_TOL
    if hi < lo:
        return np.zeros(0, dtype=np.int64)
    on = np.arange(lo, hi + 1, dtype=np.int64)
    ok = np.ones(on.size, dtype=bool)
    for o2, d2 in placed:
        ok &= (on + d + MIN_GAP <= o2) | (on >= o2 + d2 + MIN_GAP)
    return on[ok]


def valid_set(seg_lengths, d, placed_by_seg):
    """Enumerated valid set as (segment index array, onset array), in (segment, onset) order."""
    S, O = [], []
    for j, L in enumerate(seg_lengths):
        o = valid_onsets(L, d, placed_by_seg.get(j, ()))
        if o.size:
            S.append(np.full(o.size, j, dtype=np.int64))
            O.append(o)
    if not S:
        return np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int64)
    return np.concatenate(S), np.concatenate(O)


def place(seg_lengths, durations_in_order, rng):
    """One draw of sampler S. Returns [(segment index, onset, d)] in placement order, or None if some valid set is empty."""
    placed_by_seg, out = {}, []
    for d in durations_in_order:
        S, O = valid_set(seg_lengths, d, placed_by_seg)
        if S.size == 0:
            return None
        i = int(rng.integers(0, S.size))
        j, o = int(S[i]), int(O[i])
        placed_by_seg.setdefault(j, []).append((o, int(d)))
        out.append((j, o, int(d)))
    return out


def place_with_redraw(seg_lengths, durations_in_order, rng, max_redraws=1000):
    """Draw; if the valid set is empty, redraw (same generator, continued). Returns (placement, n_redraws)."""
    for n in range(max_redraws + 1):
        p = place(seg_lengths, durations_in_order, rng)
        if p is not None:
            return p, n
    raise RuntimeError("sampler S: no valid placement after %d redraws" % max_redraws)


def to_annotations(placement, seg_names):
    """-> {pseudo-record name: [(on, off)]} (segment-local seconds, sorted)."""
    ann = {n: [] for n in seg_names}
    for j, o, d in placement:
        ann[seg_names[j]].append((o, o + d))
    for n in ann:
        ann[n].sort()
    return ann
