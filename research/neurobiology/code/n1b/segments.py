"""§2.1 ictal exclusion: allowed segments -> pseudo-records (FileRecords) with sliced features.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
For every real seizure [on, off) in a file, [on - 600, off + 900) clipped to THAT file is excluded. Each remaining
contiguous interval [a, b) of a file is one pseudo-record: same subject/path, t_start = file t_start + a, duration b - a.
Its windows are the file windows fully inside [a, b): file window indices a .. b-2 (n = b - a - 1 = n_windows(b - a)).
"""
from dataclasses import dataclass

import numpy as np

from nfharness.data import FileRecord
from nfharness.splits import Split

PRE_S, POST_S = 600, 900


def _runs(mask):
    m = np.concatenate([[0], np.asarray(mask, dtype=np.int8), [0]])
    d = np.diff(m)
    return list(zip(np.flatnonzero(d == 1).tolist(), np.flatnonzero(d == -1).tolist()))


def allowed_segments(duration, events, pre=PRE_S, post=POST_S):
    """[(a, b)] allowed intervals of one file (ints, file-local seconds)."""
    ex = np.zeros(int(duration), dtype=bool)
    for on, off in events:
        ex[max(0, int(on) - pre):min(int(duration), int(off) + post)] = True
    return [(a, b) for a, b in _runs(~ex) if b - a >= 2]


def pseudo_name(fname, a, b):
    return "%s[%d:%d]" % (fname, a, b)


@dataclass
class SubjectPseudo:
    subject: str
    subject_index: int
    split: Split                 # causal split over pseudo-records
    groups: list                 # inner-LOFO groups = pseudo-records of one original training file
    parent: dict                 # pseudo name -> (original file name, a, b)
    train_seizure_durations: list   # [(duration, file_order, k)] of the real training seizures
    test_seizure_durations: list
    train_allowed_h: float
    test_allowed_h: float
    n_train_segments: int
    n_test_segments: int


def build_pseudo(split, ann, feats_by_file, subject_index):
    """split: the real causal Split of one subject; ann: {file: [(on, off)]}; feats_by_file: {file: [T-1, 132]}.
    Returns (SubjectPseudo, {pseudo name: feature view})."""
    feats, parent = {}, {}

    def mk(recs):
        out, groups = [], []
        for r in recs:
            g = []
            for a, b in allowed_segments(r.duration, ann[r.name]):
                n = pseudo_name(r.name, a, b)
                pr = FileRecord(r.subject, n, r.path, r.t_start + a, b - a)
                feats[n] = feats_by_file[r.name][a:b - 1]
                parent[n] = (r.name, a, b)
                g.append(pr)
            out += g
            if g:
                groups.append(g)
        return out, groups
    tr, groups = mk(split.train)
    te, _ = mk(split.test)
    sp = Split("causal", tr, te, label="N1b-" + split.label)

    def durs(recs):
        return [(int(off - on), fi, k) for fi, r in enumerate(recs) for k, (on, off) in enumerate(ann[r.name])]
    sp_obj = SubjectPseudo(split.label, subject_index, sp, groups, parent, durs(split.train), durs(split.test),
                           sum(r.duration for r in tr) / 3600.0, sum(r.duration for r in te) / 3600.0, len(tr), len(te))
    return sp_obj, feats
