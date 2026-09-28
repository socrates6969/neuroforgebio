"""LabelVault: the only holder of seizure annotations (F8).

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
Training code may read labels of TRAINING files/windows only (train_mask / train_window_labels). Labels of protected
(test) files/windows are released only to the scorer, which must present the scorer key; every scorer read is logged
as a hash chain (the chain head and read count go into the evaluation card; the wall-clock time of the first read goes
into the card's runtime block). Python cannot make this unbreakable (a caller can import the key); the design makes
any other path raise, and the test suite checks that it does.
"""
import hashlib
import time

import numpy as np

from .config import guard_hit
from .errors import TestLabelAccessError
from .windows import window_labels_from_mask

_SCORER_KEY = object()   # imported only by scoring.py


def mask_from_events(events, duration):
    m = np.zeros(int(duration), dtype=np.int8)
    for on, off in events:
        m[int(on):int(off)] = 1
    return m


class LabelVault:
    def __init__(self, annotations, durations, protected_files=(), protected_windows=None, name="vault"):
        self.__masks = {f: mask_from_events(annotations[f], durations[f]) for f in durations}
        self.__protected = frozenset(protected_files)
        self.__pwin = {k: np.asarray(v, dtype=bool) for k, v in (protected_windows or {}).items()}
        self.name = name
        self.access_log = []          # (index, file, purpose, sha) -- deterministic
        self._chain = hashlib.sha256(b"labelvault:" + name.encode()).hexdigest()
        self.first_scorer_read_time = None

    # ---- training-side access
    def _check_train(self, f, idx):
        guard_hit("F8")
        if f in self.__protected:
            raise TestLabelAccessError("training code tried to read labels of protected file %s" % f)
        if f in self.__pwin:
            pw = self.__pwin[f]
            if idx is None or np.any(pw[np.asarray(idx)]):
                raise TestLabelAccessError("training code tried to read labels of protected windows in %s" % f)

    def train_mask(self, f):
        self._check_train(f, None if f in self.__pwin else [])
        return self.__masks[f].copy()

    def train_window_labels(self, f, idx=None):
        self._check_train(f, idx)
        wl = window_labels_from_mask(self.__masks[f])
        return wl.copy() if idx is None else wl[np.asarray(idx)]

    def is_protected(self, f):
        return f in self.__protected or f in self.__pwin

    # ---- scorer-side access
    def scorer_mask(self, f, key, purpose):
        if key is not _SCORER_KEY:
            raise TestLabelAccessError("labels requested without the scorer key")
        if self.first_scorer_read_time is None:
            self.first_scorer_read_time = time.time()
        rec = "%d|%s|%s" % (len(self.access_log), f, purpose)
        self._chain = hashlib.sha256((self._chain + rec).encode()).hexdigest()
        self.access_log.append(rec)
        return self.__masks[f].copy()

    def summary(self):
        return {"vault": self.name, "scorer_reads": len(self.access_log), "chain_sha256": self._chain}
