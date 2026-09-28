"""Event / sample scoring (timescoring 0.0.7, frozen parameters: F9), an independent re-implementation of harness §3,
detection latency, and the Scorer: the only component that reads test labels (F8).

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
"""
from importlib.metadata import version as _pkg_version

import numpy as np

from .config import guard_hit
from .errors import ScorerParameterError
from .labels import _SCORER_KEY

LOCKED_PARAMS = (30, 60, 0, 300, 90)       # toleranceStart, toleranceEnd, minOverlap, maxEventDuration, minDurationBetweenEvents
LOCKED_TS_VERSION = "0.0.7"
_TS_VERSION_AT_IMPORT = _pkg_version("timescoring")


def assert_scorer(params):
    """F9: timescoring version and the 5 event parameters are frozen."""
    guard_hit("F9")
    if _TS_VERSION_AT_IMPORT != LOCKED_TS_VERSION or _pkg_version("timescoring") != LOCKED_TS_VERSION:
        raise ScorerParameterError("timescoring version %s != %s" % (_pkg_version("timescoring"), LOCKED_TS_VERSION))
    if tuple(params) != LOCKED_PARAMS:
        raise ScorerParameterError("scorer params %s != locked %s" % (tuple(params), LOCKED_PARAMS))


def _ts():
    from timescoring import scoring
    from timescoring.annotations import Annotation
    return scoring, Annotation


def event_score(ref_mask, hyp_mask, params=LOCKED_PARAMS):
    """timescoring EventScoring on 1-Hz masks of one continuous recording. -> dict(tp, fp, n_ref, dur_s)."""
    assert_scorer(params)
    scoring, Annotation = _ts()
    ref = Annotation(np.asarray(ref_mask, dtype=bool), 1)
    hyp = Annotation(np.asarray(hyp_mask, dtype=bool), 1)
    p = scoring.EventScoring.Parameters(toleranceStart=params[0], toleranceEnd=params[1], minOverlap=params[2],
                                        maxEventDuration=params[3], minDurationBetweenEvents=params[4])
    s = scoring.EventScoring(ref, hyp, p)
    return {"tp": int(s.tp), "fp": int(s.fp), "n_ref": int(s.refTrue), "dur_s": float(s.numSamples / s.fs)}


def sample_score(ref_mask, hyp_mask):
    """timescoring SampleScoring at 1 Hz. -> dict(tp, fp, n_ref_samples)."""
    scoring, Annotation = _ts()
    s = scoring.SampleScoring(Annotation(np.asarray(ref_mask, dtype=bool), 1),
                              Annotation(np.asarray(hyp_mask, dtype=bool), 1), fs=1)
    return {"tp": int(s.tp), "fp": int(s.fp), "n_ref": int(s.refTrue)}


# ------------------------------------------------------------------ independent re-implementation (harness §3)
def mask_events(mask):
    m = np.concatenate([[0], np.asarray(mask, dtype=np.int8), [0]])
    d = np.diff(m)
    return np.flatnonzero(d == 1), np.flatnonzero(d == -1)


def merge_events(st, en, min_gap):
    if st.size == 0:
        return st, en
    keep = np.concatenate([[True], (st[1:] - en[:-1]) >= min_gap])
    idx = np.flatnonzero(keep)
    return st[idx], np.concatenate([en[idx[1:] - 1], en[-1:]])


def split_events(st, en, max_dur):
    S, E = [], []
    for a, b in zip(st.tolist(), en.tolist()):
        while b - a > max_dur:
            S.append(a)
            E.append(a + max_dur)
            a += max_dur
        S.append(a)
        E.append(b)
    return np.array(S, dtype=np.int64), np.array(E, dtype=np.int64)


def reimpl_event_score(ref_mask, hyp_mask, params=LOCKED_PARAMS, return_events=False):
    """Re-implementation of harness §3 (merge < 90 s, split > 300 s, both ref and hyp; ref TP if any hyp sample lies
    in [on-30, off+60); FP = hyp event overlapping no extended ref)."""
    t0, t1, _, maxd, gap = params
    rs, re_ = split_events(*merge_events(*mask_events(ref_mask), gap), maxd)
    hs, he = split_events(*merge_events(*mask_events(hyp_mask), gap), maxd)
    xs, xe = rs - t0, re_ + t1
    if hs.size and xs.size:
        ov = (hs[None, :] < xe[:, None]) & (he[None, :] > xs[:, None])      # [n_ref, n_hyp]
        tp = int(ov.any(axis=1).sum())
        fp = int((~ov.any(axis=0)).sum())
    else:
        tp, fp = 0, int(hs.size)
    out = {"tp": tp, "fp": fp, "n_ref": int(rs.size), "dur_s": float(len(ref_mask))}
    if return_events:
        out["ref_events"] = list(zip(rs.tolist(), re_.tolist()))
        out["hyp_events"] = list(zip(hs.tolist(), he.tolist()))
    return out


def latencies(ref_mask, hyp_mask, params=LOCKED_PARAMS):
    """Harness latency per TP reference event: first hypothesis second inside [on-30, off+60) minus onset.
    Uses the raw 1-Hz hypothesis; falls back to the merged hypothesis if only merge-filler overlaps."""
    t0, t1, _, maxd, gap = params
    rs, re_ = split_events(*merge_events(*mask_events(ref_mask), gap), maxd)
    h = np.asarray(hyp_mask, dtype=bool)
    hs, he = merge_events(*mask_events(hyp_mask), gap)
    hm = np.zeros(h.size, dtype=bool)
    for a, b in zip(hs, he):
        hm[a:b] = True
    out = []
    for a, b in zip(rs, re_):
        lo, hi = max(0, a - t0), min(h.size, b + t1)
        j = np.flatnonzero(h[lo:hi])
        if j.size == 0:
            j = np.flatnonzero(hm[lo:hi])
        if j.size:
            out.append(int(lo + j[0] - a))
    return out


def shifted_tp_counts(ref_mask, hyp_mask, offsets, params=LOCKED_PARAMS):
    """TP count of the circularly shifted hypothesis for each offset (chance null, N1 b2 / C3)."""
    return np.array([reimpl_event_score(ref_mask, np.roll(hyp_mask, int(o)), params)["tp"] for o in offsets])


class Scorer:
    """Reads test labels from a LabelVault with the scorer key and returns metrics only."""

    def __init__(self, vault, purpose):
        self.vault, self.purpose = vault, purpose
        self._cache = {}

    def _ref(self, f):
        if f not in self._cache:
            self._cache[f] = self.vault.scorer_mask(f, _SCORER_KEY, self.purpose)
        return self._cache[f]

    def ref_window_labels(self, f):
        m = self._ref(f).astype(bool)
        return (m[:-1] & m[1:]).astype(np.int8)

    def score_file(self, f, hyp_mask):
        ref = self._ref(f)
        e = event_score(ref, hyp_mask)
        s = sample_score(ref, hyp_mask)
        e["latencies"] = latencies(ref, hyp_mask)
        e["tp_indicators"] = _tp_indicators(ref, hyp_mask)
        e["s_tp"], e["s_fp"], e["s_nref"] = s["tp"], s["fp"], s["n_ref"]
        return e

    def window_auc_inputs(self, f):
        return self.ref_window_labels(f)

    def shifted_tp(self, f, hyp_mask, offsets):
        return shifted_tp_counts(self._ref(f), hyp_mask, offsets)

    def reimpl_score(self, f, hyp_mask):
        return reimpl_event_score(self._ref(f), hyp_mask)


def _tp_indicators(ref, hyp):
    """Per merged/split reference event: 1 if detected (for the by-event bootstrap)."""
    t0, t1, _, maxd, gap = LOCKED_PARAMS
    rs, re_ = split_events(*merge_events(*mask_events(ref), gap), maxd)
    hs, he = split_events(*merge_events(*mask_events(hyp), gap), maxd)
    return [int(np.any((hs < b + t1) & (he > a - t0))) for a, b in zip(rs, re_)]
