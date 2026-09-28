"""Montage assertion E1 (prereg §1): every N3 EDF header lists exactly the 23 standard labels in the standard order.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
Header only (edf_reader.read_header reads 256 * (ns + 1) bytes); no signal sample is read. Aborts on any difference,
because the locked N2 reader selects channels by INDEX.
"""
from edf_reader import read_header
from nfharness.config import CHANNEL_LABELS_23


class MontageError(Exception):
    pass


def assert_montage(paths):
    out = {}
    for p in paths:
        h = read_header(p)
        labels = list(h["labels"])
        fs = sorted(set(float(x) for x in h["fs"]))
        if h["ns"] != 23 or labels != list(CHANNEL_LABELS_23):
            raise MontageError("E1 montage mismatch in %s: ns=%d labels=%s" % (p, h["ns"], labels))
        if fs != [256.0]:
            raise MontageError("E1 sampling-rate mismatch in %s: %s" % (p, fs))
        out[p] = {"ns": h["ns"], "fs": fs, "labels_equal_standard_23": True}
    return out
