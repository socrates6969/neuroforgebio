"""PhantomVault (same interface as nfharness.labels.LabelVault), the N1b order log, the deferred scorer, the
planted-leak flag guard and the observational select_tau capture.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
- Training-side reads (train_mask / train_window_labels) are served by a harness LabelVault that holds the TRAINING
  phantoms and protects every test pseudo-record (reads raise TestLabelAccessError, as in N2).
- Test phantoms do not exist until seal_test_phantoms() is called. Before that, scorer_mask raises (order violation).
  After sealing, scorer reads go through a second harness LabelVault (scorer key check + hash-chained access log).
- release_test_labels() and every planted leak require allow_planted_leak=True, else PlantedLeakFlagError.
"""
import contextlib
import hashlib

import numpy as np

from nfharness.errors import TestLabelAccessError
from nfharness.labels import LabelVault, mask_from_events


class PlantedLeakFlagError(Exception):
    """A planted leak (PL-A/PL-B/PL-C) or an early test-label release was requested without allow_planted_leak=True."""


def require_flag(allow_planted_leak, what):
    if allow_planted_leak is not True:
        raise PlantedLeakFlagError("%s requires allow_planted_leak=True" % what)


class OrderLog:
    """Deterministic ordered event log (no wall-clock times; those go to the runtime block)."""

    def __init__(self):
        self.events = []

    def add(self, kind, detail=""):
        self.events.append("%03d %s %s" % (len(self.events), kind, detail))
        return len(self.events) - 1

    def index(self, kind):
        for i, e in enumerate(self.events):
            if e.split(" ", 2)[1] == kind:
                return i
        return None


class PhantomVault:
    def __init__(self, train_annotations, durations, test_files, name, log):
        self.name = name
        self.log = log
        self._durs = dict(durations)
        self._test = tuple(test_files)
        ann = {f: list(train_annotations.get(f, [])) for f in self._durs if f not in self._test}
        ann.update({f: [] for f in self._test})          # the training vault holds NO test phantoms
        self._train = LabelVault(ann, self._durs, protected_files=self._test, name=name + "-train")
        self._testv = None
        self._test_ann = None

    # ---- training side (same as LabelVault)
    def train_mask(self, f):
        return self._train.train_mask(f)

    def train_window_labels(self, f, idx=None):
        return self._train.train_window_labels(f, idx)

    def is_protected(self, f):
        return self._train.is_protected(f)

    # ---- test phantoms
    @property
    def sealed(self):
        return self._testv is not None

    def seal_test_phantoms(self, test_annotations, detail=""):
        if self._testv is not None:
            raise RuntimeError("test phantoms already sealed")
        self._test_ann = {f: list(test_annotations.get(f, [])) for f in self._test}
        self._testv = LabelVault(self._test_ann, {f: self._durs[f] for f in self._test}, name=self.name + "-test")
        self.log.add("seal_test_phantoms", detail)

    def scorer_mask(self, f, key, purpose):
        if f not in self._test:
            raise TestLabelAccessError("PhantomVault: scorer read of a non-test record %s" % f)
        if self._testv is None:
            raise TestLabelAccessError("PhantomVault: test phantom labels requested before they were drawn (order violation)")
        return self._testv.scorer_mask(f, key, purpose)

    def release_test_labels(self, allow_planted_leak=False):
        """PLANTED-LEAK path only: the sealed test phantom masks, handed to non-scorer code."""
        require_flag(allow_planted_leak, "PhantomVault.release_test_labels")
        if self._testv is None:
            raise TestLabelAccessError("nothing sealed")
        self.log.add("PLANTED_release_test_labels")
        return {f: mask_from_events(self._test_ann[f], self._durs[f]) for f in self._test}

    def summary(self):
        s = {"vault": self.name, "train": self._train.summary()}
        if self._testv is not None:
            s["test"] = self._testv.summary()
        return s


class DeferredScorer:
    """Passed as run_split(scorer=...) (an existing parameter of the unchanged harness) so that NO test label is read
    inside the fit: it returns placeholders; the real scoring happens afterwards through nfharness Scorer."""
    reads = 0

    def score_file(self, f, hyp_mask):
        return None

    def ref_window_labels(self, f):
        return None


@contextlib.contextmanager
def capture_select_tau():
    """Observational hook (DEVIATIONS N1b-2): wraps nfharness.pipeline.select_tau for the duration of one run_split
    call, records its INPUT (the TaggedScores 'train_oof') and OUTPUT, and returns the original output unchanged.
    No harness file is modified; the original function object is restored on exit."""
    import nfharness.pipeline as P
    orig = P.select_tau
    box = []

    def wrapped(oof, fa_of_masks, *a, **k):
        out = orig(oof, fa_of_masks, *a, **k)
        box.append((oof, out))
        return out
    P.select_tau = wrapped
    try:
        yield box
    finally:
        P.select_tau = orig


def sha_scores_hyps(order, p, hyps):
    """SHA-256 of the test scores and hypothesis masks (order = test pseudo-record names)."""
    h = hashlib.sha256()
    for f in order:
        h.update(np.ascontiguousarray(np.asarray(p[f], dtype=np.float64)).tobytes())
    for hyp in hyps:
        for f in order:
            h.update(np.ascontiguousarray(np.asarray(hyp[f], dtype=np.int8)).tobytes())
    return h.hexdigest()
