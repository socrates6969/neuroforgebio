"""Locked N2 configuration, RNG streams and the guard-call registry.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
Every value here is copied from prereg\\N2_baseline_detection.md (LOCKED). The F2 guard compares the SHA-256 of the
canonical JSON of the config actually used with LOCKED_CONFIG_HASH; any edit to a model/post-processing value raises.
"""
import hashlib
import json
from collections import Counter

import numpy as np

SEED = 20261001
# RNG stream ids (N2 §8)
STREAM_LEAK_SPLIT = 0
STREAM_IID_PERM = 1
STREAM_CIRC_SHIFT = 2
STREAM_BOOTSTRAP = 3
STREAM_CHANCE_NULL = 4
STREAM_SYNTHETIC = 5

CHANNEL_LABELS_23 = ["FP1-F7", "F7-T7", "T7-P7", "P7-O1", "FP1-F3", "F3-C3", "C3-P3", "P3-O1", "FP2-F4", "F4-C4",
                     "C4-P4", "P4-O2", "FP2-F8", "F8-T8", "T8-P8", "P8-O2", "FZ-CZ", "CZ-PZ", "P7-T7", "T7-FT9",
                     "FT9-FT10", "FT10-T8", "T8-P8"]
CHANNEL_INDEX = list(range(22))           # drop 0-based index 22 (the duplicate T8-P8)
BANDS = [(1.0, 4.0), (4.0, 8.0), (8.0, 13.0), (13.0, 30.0), (30.0, 55.0)]
FEATURE_KINDS = ["LL"] + ["BP%g_%g" % b for b in BANDS]

LOCKED_CONFIG = {
    "fs": 256,
    "channels": CHANNEL_INDEX,
    "window_s": 2,
    "step_s": 1,
    "window_label_rule": "window [i,i+2) fully inside [onset,offset)",
    "features": FEATURE_KINDS,
    "bands_hz": [list(b) for b in BANDS],
    "feature_log_eps": 1e-3,
    "taper": "numpy.hanning(512)",
    "normaliser": {"type": "zscore", "ddof": 0, "sd_floor": 1e-8, "fit_on": "train"},
    "classifier": {"type": "logreg_l2", "C": 1.0, "class_weight": "balanced", "intercept_penalised": False,
                   "solver": "scipy L-BFGS-B", "gtol": 1e-6, "maxiter": 1000, "init": "zeros"},
    "postprocess": {"k": 4, "n": 5, "causal": True},
    "tau_grid": [round(0.05 + 0.01 * i, 2) for i in range(95)],
    "tau_rule": {"fa_target_per_24h": 12.0, "pick": "smallest tau with train-OOF FA <= target", "fallback": 0.99,
                 "inner_cv": "leave-one-training-file-out"},
    "buffer_s": 10,
    "scorer": {"package": "timescoring", "version": "0.0.7", "params": [30, 60, 0, 300, 90]},
}


def canonical_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=_default)


def _default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


def config_hash(cfg):
    return hashlib.sha256(canonical_json(cfg).encode("utf-8")).hexdigest()


# Hash of the locked configuration, frozen as a literal when N2 was transcribed (2026-09-26). An edit to
# LOCKED_CONFIG therefore makes assert_config_locked(LOCKED_CONFIG) raise (tests/test_violations.py checks both).
LOCKED_CONFIG_HASH_LITERAL = "b6775e9aad8958cfce6cbfe805674c55fd13b1c8969a8320b681edb451bd1e4f"
LOCKED_CONFIG_HASH = config_hash(LOCKED_CONFIG)
TAU_GRID = tuple(LOCKED_CONFIG["tau_grid"])
K_OF_N = (4, 5)
BUFFER_S = 10
EXPECTED_SPLIT_HASH = "433d818f305ba2095ef854b1f7f8b594895ad070f5fc28584a5507bdc7d9f1e2"


def rng(stream, *sub):
    """numpy Generator for stream k (N2 §8). Extra sub-keys give documented child streams (DEVIATIONS D6)."""
    return np.random.default_rng(np.random.SeedSequence(SEED, spawn_key=(stream,) + tuple(sub)))


# ---- guard registry: every guard increments its counter; the card records the counts (N1 d "silent on real run")
GUARD_CALLS = Counter()


def guard_hit(rule):
    GUARD_CALLS[rule] += 1
