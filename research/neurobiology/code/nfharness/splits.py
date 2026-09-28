"""Split construction and split guards (S1, S5, S7, F6).

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
The split is computed from the manifest records (file order = EDF header start time) and per-file seizure COUNTS
before any feature is computed (S7); its hash is compared with the prereg literal.
"""
import hashlib
from dataclasses import dataclass, field

import numpy as np

from .config import guard_hit
from .errors import CausalSplitError, RandomSplitForbiddenError, SplitHashError, SubjectOverlapError


@dataclass
class Split:
    kind: str                      # "causal" | "future_leak" | "cross_patient" | "window_random"
    train: list                    # FileRecords
    test: list                     # FileRecords
    label: str = ""
    meta: dict = field(default_factory=dict)

    @property
    def train_names(self):
        return [r.name for r in self.train]

    @property
    def test_names(self):
        return [r.name for r in self.test]


def causal_splits(records, seizure_counts, n_train_seizures=3):
    """Primary split per subject: train = every file up to and including the file containing the subject's
    n-th seizure (chronological by header start), test = every later file."""
    out = {}
    for s in sorted({r.subject for r in records}):
        rs = sorted([r for r in records if r.subject == s], key=lambda r: r.t_start)
        cum, cut = 0, None
        for i, r in enumerate(rs):
            cum += seizure_counts[r.name]
            if cum >= n_train_seizures:
                cut = i
                break
        if cut is None:
            raise ValueError("subject %s has < %d seizures" % (s, n_train_seizures))
        out[s] = Split("causal", rs[:cut + 1], rs[cut + 1:], label=s)
    return out


def split_string(splits):
    lines = []
    for s in sorted(splits):
        sp = splits[s]
        lines.append("%s;train=%s;test=%s" % (s, ",".join(sp.train_names), ",".join(sp.test_names)))
    return "\n".join(lines)


def split_hash(splits):
    return hashlib.sha256(split_string(splits).encode("utf-8")).hexdigest()


def assert_split_hash(splits, expected):
    """S7: the split recomputed from the manifest must hash to the prereg literal."""
    guard_hit("S7")
    h = split_hash(splits)
    if h != expected:
        raise SplitHashError("split hash %s != prereg %s" % (h, expected))
    return h


def assert_causal(split):
    """F6: in the primary patient-specific split, max(end of training files) <= min(start of test files)."""
    guard_hit("F6")
    if split.kind != "causal":
        raise CausalSplitError("assert_causal called on a %r split" % split.kind)
    for s in {r.subject for r in split.train + split.test}:
        tr = [r for r in split.train if r.subject == s]
        te = [r for r in split.test if r.subject == s]
        if tr and te and max(r.t_end for r in tr) > min(r.t_start for r in te):
            raise CausalSplitError("subject %s: training data recorded after test data" % s)


def assert_subject_disjoint(train_subjects, test_subjects):
    """S1: cross-patient folds must be subject-disjoint (chb01/chb21 would map to one subject id)."""
    guard_hit("S1")
    inter = set(train_subjects) & set(test_subjects)
    if inter:
        raise SubjectOverlapError("subjects on both sides: %s" % sorted(inter))


def random_window_split(n_windows_by_file, p_train, rng, allow_random_split=False):
    """S5: window-level random split. FORBIDDEN except in the deliberate-leak positive control (C2a).
    Returns {file: bool array, True = train}. Files are visited in the given (chronological) order."""
    guard_hit("S5")
    if not allow_random_split:
        raise RandomSplitForbiddenError("window-random split requested without allow_random_split=True")
    return {f: rng.random(n) < p_train for f, n in n_windows_by_file.items()}
