"""Per-file windowing, window labels from 1-Hz masks, and the F4 boundary / buffer guards.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
Window i of a file covers [i, i+2) s, i = 0 .. T-2; windows are built after splitting, per file, never across files.
"""
import numpy as np

from .config import BUFFER_S, guard_hit
from .errors import WindowBoundaryError

WIN_S = 2
STEP_S = 1


def n_windows(duration_s):
    return int(duration_s) - WIN_S + 1


def window_starts(duration_s):
    starts = np.arange(n_windows(duration_s), dtype=np.int64) * STEP_S
    assert_windows_in_file(starts, starts + WIN_S, duration_s)
    return starts


def assert_windows_in_file(starts, ends, duration_s):
    """F4a: every window [start, end) lies inside one file."""
    guard_hit("F4")
    starts = np.asarray(starts)
    ends = np.asarray(ends)
    if starts.size and (starts.min() < 0 or ends.max() > duration_s or np.any(ends <= starts)):
        raise WindowBoundaryError("window outside its file [0, %s)" % duration_s)


def window_labels_from_mask(mask_1hz):
    """Window label = 1 iff [i, i+2) lies fully inside the ictal mask (integer-second annotations)."""
    m = np.asarray(mask_1hz, dtype=bool)
    return (m[:-1] & m[1:]).astype(np.int8)


def buffer_keep(train_rec, test_recs, B=BUFFER_S):
    """Boolean keep-mask over train_rec's windows: drop windows that end within B s of any test file of the same
    subject (absolute subject time), or overlap it. Returns (keep, n_dropped)."""
    st = window_starts(train_rec.duration).astype(float) + train_rec.t_start
    en = st + WIN_S
    keep = np.ones(st.size, dtype=bool)
    for te in test_recs:
        if te.subject != train_rec.subject:
            continue
        keep &= ~((en > te.t_start - B) & (st < te.t_end + B))
    return keep, int((~keep).sum())


def assert_buffer(train_windows_abs, test_recs, B=BUFFER_S):
    """F4b: no TRAINING window (absolute [start, end) in subject time, with subject id) lies within B of a test file.
    train_windows_abs: iterable of (subject, abs_start_array, abs_end_array)."""
    guard_hit("F4")
    for subj, st, en in train_windows_abs:
        for te in test_recs:
            if te.subject != subj:
                continue
            bad = (np.asarray(en) > te.t_start - B) & (np.asarray(st) < te.t_end + B)
            if np.any(bad):
                raise WindowBoundaryError("%d training windows within %s s of test file %s" % (int(bad.sum()), B, te.name))
