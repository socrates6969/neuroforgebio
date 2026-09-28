"""RESEARCH USE ONLY. NOT A MEDICAL DEVICE. Shared synthetic fixtures (RNG stream k = 5)."""
import os
import sys

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from nfharness import config as C  # noqa: E402
from nfharness.data import FileRecord  # noqa: E402
from nfharness.splits import Split  # noqa: E402


@pytest.fixture
def syn():
    """One synthetic subject: 6 files x 900 s, 7-s gaps, seizures in files 1..5; in-memory features."""
    g = C.rng(C.STREAM_SYNTHETIC)
    recs, ann, feats = [], {}, {}
    t = 0.0
    for i in range(6):
        name = "syn_%02d.edf" % (i + 1)
        T = 900
        recs.append(FileRecord("syn", name, "<memory>", t, T))
        t += T + 7
        ev = []
        if i >= 1:
            on = int(g.integers(100, 700))
            ev = [(on, on + int(g.integers(40, 90)))]
        ann[name] = ev
        X = g.standard_normal((T - 1, 132)).astype(np.float32)
        for on, off in ev:
            X[on:off - 1, ::6] += 3.0
        feats[name] = X
    train, test = recs[:4], recs[4:]
    split = Split("causal", train, test, label="syn")
    return {"recs": recs, "ann": ann, "feats": feats, "split": split, "durations": {r.name: r.duration for r in recs}}
