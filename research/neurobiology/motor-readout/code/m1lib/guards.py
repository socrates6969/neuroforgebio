"""Leak guards for M1 (prereg §2, §6). New errors subclass nfharness HarnessViolation; F1/F6/F7/F8/S5/S7/C-hash reuse
the nfharness exception classes (imported, unmodified).

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
"""
import hashlib
import time
from collections import Counter

import numpy as np

from . import NB_CODE  # noqa: F401  (puts nfharness on sys.path)
from nfharness.errors import (CausalSplitError, FeatureWhitelistError, HarnessViolation, InputHashError,  # noqa: F401
                              NormaliserLeakError, RandomSplitForbiddenError, SplitHashError, TestLabelAccessError)

GUARD_CALLS = Counter()


class TrialOverlapError(HarnessViolation):
    rule = "M-trial"


class SessionOrderError(HarnessViolation):
    rule = "M-session"


class CausalFeatureError(HarnessViolation):
    rule = "M-causal"


def _hit(r):
    GUARD_CALLS[r] += 1


# ---------------------------------------------------------------- hashes (S7 / C-hash)
def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def assert_input_lock(text, expected):
    _hit("S7")
    h = sha256_bytes(text.encode("utf-8"))
    if h != expected:
        raise SplitHashError("input-lock hash %s != prereg %s" % (h, expected))
    return h


def assert_file_hash(path, expected):
    _hit("C-hash")
    got = sha256_file(path)
    if expected is None or got != expected:
        raise InputHashError("%s: sha256 %s != expected %s" % (path, got, expected))
    return got


# ---------------------------------------------------------------- splits (trial unit; F6; S5)
def chrono_split(trial_ids, start_times, stop_times, fracs=(0.6, 0.2, 0.2), gap=1):
    """Sort trials by start time; first 60% train, next 20% val, last 20% test; `gap` trials dropped at each boundary
    (the trial at each cut index). Returns dict(train, val, test, gap) of id lists; checks F6 + trial disjointness."""
    o = np.argsort(np.asarray(start_times), kind="stable")
    ids = [trial_ids[i] for i in o]
    n = len(ids)
    c1 = int(round(fracs[0] * n))
    c2 = int(round((fracs[0] + fracs[1]) * n))
    parts = dict(train=ids[:c1], gap=ids[c1:c1 + gap] + ids[c2:c2 + gap], val=ids[c1 + gap:c2], test=ids[c2 + gap:])
    st = dict(zip(trial_ids, start_times))
    sp = dict(zip(trial_ids, stop_times))
    assert_trial_disjoint(parts)
    assert_causal_blocks([(st[i], sp[i]) for i in parts["train"]], [(st[i], sp[i]) for i in parts["val"]],
                         [(st[i], sp[i]) for i in parts["test"]])
    return parts


def assert_trial_disjoint(parts):
    """No trial (and hence no bin of a trial) may appear in two partitions."""
    _hit("M-trial")
    seen = {}
    for name, ids in parts.items():
        for i in ids:
            if i in seen:
                raise TrialOverlapError("trial %r in both %s and %s" % (i, seen[i], name))
            seen[i] = name
    return True


def assert_bins_disjoint(bin_owner_by_part):
    """bin_owner_by_part: {part: array of trial ids owning each bin}. A trial's bins must all be in one partition."""
    _hit("M-trial")
    owner = {}
    for p, arr in bin_owner_by_part.items():
        for t in np.unique(arr):
            t = t.item() if hasattr(t, "item") else t
            if t in owner and owner[t] != p:
                raise TrialOverlapError("bins of trial %r in %s and %s" % (t, owner[t], p))
            owner[t] = p
    return True


def assert_causal_blocks(train, val, test):
    """F6: max(train end) < min(val start) and max(val end) < min(test start). Args: lists of (start, stop)."""
    _hit("F6")
    if train and val and max(b for _, b in train) >= min(a for a, _ in val):
        raise CausalSplitError("training trial ends after a validation trial starts")
    if val and test and max(b for _, b in val) >= min(a for a, _ in test):
        raise CausalSplitError("validation trial ends after a test trial starts")
    if train and test and max(b for _, b in train) >= min(a for a, _ in test):
        raise CausalSplitError("training trial ends after a test trial starts")
    return True


def random_bin_split(n, rng, fracs=(0.6, 0.2, 0.2), allow_random_split=False):
    """S5: bin-level random split. FORBIDDEN except in the declared PL-3 planted leak."""
    _hit("S5")
    if not allow_random_split:
        raise RandomSplitForbiddenError("bin-level random split requested without allow_random_split=True")
    u = rng.permutation(n)
    a, b = int(round(fracs[0] * n)), int(round((fracs[0] + fracs[1]) * n))
    lab = np.empty(n, dtype="<U5")
    lab[u[:a]], lab[u[a:b]], lab[u[b:]] = "train", "val", "test"
    return lab


# ---------------------------------------------------------------- features (causal lags; F7 whitelist)
def lag_offsets(H, centred=None, allow_noncausal=False):
    """Offsets k meaning x_{t-k}. Causal = k >= 0. centred=w gives k in -w..w (non-causal; PL-3 only)."""
    _hit("M-causal")
    ks = list(range(H)) if centred is None else list(range(-centred, centred + 1))
    if any(k < 0 for k in ks) and not allow_noncausal:
        raise CausalFeatureError("feature offsets %s use future bins (t+%d)" % (ks, -min(ks)))
    return ks


def lagged(X, ks, allow_noncausal=False):
    """X [T, N] -> [T, N*len(ks)], block j = X[t - ks[j]] (zero outside [0, T)). Column order: lag-major."""
    _hit("M-causal")
    if any(k < 0 for k in ks) and not allow_noncausal:
        raise CausalFeatureError("lagged() got future offsets %s" % [k for k in ks if k < 0])
    T, N = X.shape
    out = np.zeros((T, N * len(ks)), dtype=X.dtype)
    for j, k in enumerate(ks):
        if k > 0:
            out[k:, j * N:(j + 1) * N] = X[:T - k]
        elif k == 0:
            out[:, j * N:(j + 1) * N] = X
        else:
            out[:T + k, j * N:(j + 1) * N] = X[-k:]
    return out


def feature_names(prefix, n, ks):
    return ["%s%03d_t%+d" % (prefix, c, -k) for k in ks for c in range(n)]


def assert_whitelist(columns, whitelist, declared_extra=()):
    """F7: every column must be a whitelisted neural feature or explicitly declared (planted-leak controls only)."""
    _hit("F7")
    wl = set(whitelist) | set(declared_extra)
    bad = [c for c in columns if c not in wl]
    if bad:
        raise FeatureWhitelistError("non-whitelisted feature columns: %s" % bad[:5])
    return True


def causal_whitelist(prefix, n, H):
    return feature_names(prefix, n, list(range(H)))


# ---------------------------------------------------------------- normaliser (F1)
class ZScore:
    """z-score fitted on training rows only. fit() refuses rows whose owner is not in the declared training set."""

    def __init__(self, sd_floor=1e-8):
        self.sd_floor = sd_floor
        self.mu = self.sd = None

    def fit(self, X, row_owner, train_owners):
        _hit("F1")
        tr = set(np.asarray(list(train_owners)).tolist())
        bad = [o for o in np.unique(row_owner).tolist() if o not in tr]
        if bad:
            raise NormaliserLeakError("normaliser fit on non-training rows (owners %s)" % bad[:5])
        self.mu = X.mean(axis=0)
        self.sd = np.maximum(X.std(axis=0), self.sd_floor)
        return self

    def transform(self, X):
        return (X - self.mu) / self.sd


# ---------------------------------------------------------------- session order (D2)
def assert_session_order(declared_day, data_days, data_blocks=None, allow_future=False):
    """A fitting function declared to train on day d may receive data from days <= d only, and from calib/val blocks
    only. The PL-2 planted leak declares allow_future=True."""
    _hit("M-session")
    late = [d for d in data_days if d > declared_day]
    if late and not allow_future:
        raise SessionOrderError("fit declared for day %s received data from later day(s) %s" % (declared_day, sorted(set(late))))
    if data_blocks is not None and not allow_future:
        bad = [b for b in data_blocks if b not in ("calib", "val")]
        if bad:
            raise SessionOrderError("fit received block(s) %s" % sorted(set(bad)))
    return True


# ---------------------------------------------------------------- label vault (F8 concept)
class LabelVault:
    """Holds test-block behaviour/labels. Only final_score() reads them, after freeze(), once per (key, score_id).
    Declared planted-leak controls use planted_access(declared=True), which is logged."""

    def __init__(self, name="M1"):
        self.__store = {}
        self.__used = set()
        self.name = name
        self.frozen_hash = None
        self.log = []
        self._chain = hashlib.sha256(("vault:" + name).encode()).hexdigest()
        self.first_open_time = None

    def deposit(self, key, y):
        if self.frozen_hash is not None:
            raise TestLabelAccessError("deposit after freeze")
        self.__store[key] = np.array(y, copy=True)

    def has(self, key):
        return key in self.__store

    def get(self, key):
        _hit("F8")
        raise TestLabelAccessError("direct read of vault key %r (only final_score may read)" % (key,))

    def __getitem__(self, key):
        return self.get(key)

    def freeze(self, model_hash):
        self.frozen_hash = model_hash

    def _record(self, rec):
        self._chain = hashlib.sha256((self._chain + rec).encode()).hexdigest()
        self.log.append(rec)
        if self.first_open_time is None:
            self.first_open_time = time.time()

    def final_score(self, key, score_id, fn):
        """fn(y_true) -> result. Once per (key, score_id); only after freeze()."""
        _hit("F8")
        if self.frozen_hash is None:
            raise TestLabelAccessError("final_score before models were frozen")
        if key not in self.__store:
            raise KeyError(key)
        k = (str(key), str(score_id))
        if k in self.__used:
            raise TestLabelAccessError("second final_score for %s" % (k,))
        self.__used.add(k)
        self._record("score|%s|%s" % k)
        return fn(self.__store[key].copy())

    def planted_access(self, key, purpose, declared=False):
        _hit("F8")
        if not declared:
            raise TestLabelAccessError("undeclared access to vault key %r for %s" % (key, purpose))
        self._record("planted|%s|%s" % (key, purpose))
        return self.__store[key].copy()

    def summary(self):
        return {"vault": self.name, "reads": len(self.log), "chain_sha256": self._chain,
                "frozen_models_sha256": self.frozen_hash}
