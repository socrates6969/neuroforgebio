"""n3: harness validation on fresh CHB-MIT subjects (prereg\\N3_harness_validation_fresh.md). NEW code only.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims.
Imports nfharness, edf_reader, run_n2 and n1b UNCHANGED (their SHA-256 are checked by run_n3.py before anything else).
Modules: pooled (exact pooled SigmaF1 / SigmaTP conditional-randomisation statistic, mid-p Fisher), verdict (D1-D3 gate
logic, N2 §4 FP grid), montage (E1 assertion), synth (synthetic EDFs with the chb23/chb24 layout), download, figures.

Streams (prereg §4): numpy default_rng(SeedSequence(20261001, spawn_key=(k, subject_index, replicate))), chb23 = 0,
chb24 = 1; k = 20 training phantoms, 21 test phantoms, 22 null draws, 23 PL-A selection, 24 C3' MC, 25 PL-C, 26 dry run.
The n1b code draws its streams from module constants; n3_streams() rebinds them to 20-23 for the duration of a call
(runtime rebinding only, no file is edited; DEVIATIONS N3-2).
"""
import contextlib

__version__ = "0.1.0"

SEED = 20261001
K_TRAIN_PH, K_TEST_PH, K_NULL, K_PLA, K_C3MC, K_PLC, K_DRY = 20, 21, 22, 23, 24, 25, 26
SUBJECTS = ("chb23", "chb24")
EXPECTED_SPLIT_HASH_N3 = "9320fa73c5e52ce449f7257f47dda5fce87a25b53d812f51dbf6b21bc0397a19"
ALPHA = 0.0025
R_NCP, R_LEAK, M_NULL, M_C = 10, 5, 999, 1000
PL_A_FRAC, PL_A10_FRAC = 0.25, 0.10
FP_GRID_PREREG = {"chb23": (4, 8), "chb24": (2, 5)}     # (meets-bar max FP, inconclusive max FP), prereg §5 table
# prereg §2.2 allowed-time table: train h, train segments (s), test h, test segments (s)
ALLOWED_PREREG = {"chb23": {"train_h": 3.73, "test_h": 2.40, "test_segments_s": [1989, 2725, 3862, 58]},
                  "chb24": {"train_h": 0.50, "train_segments_s": [446, 224, 1123], "test_h": 0.97,
                            "test_segments_s": [488, 936, 629, 1447]}}
TEST_DURS_PREREG = {"chb23": [71, 62, 27, 84], "chb24": [32, 27, 19, 24]}


def rng(*key):
    import numpy as np
    return np.random.default_rng(np.random.SeedSequence(SEED, spawn_key=tuple(int(k) for k in key)))


@contextlib.contextmanager
def n3_streams():
    """Rebind n1b.ncp's stream constants 10/11/12/13 -> 20/21/22/23 (restored on exit)."""
    from n1b import ncp
    old = (ncp.K_TRAIN_PH, ncp.K_TEST_PH, ncp.K_NULL, ncp.K_PLA)
    ncp.K_TRAIN_PH, ncp.K_TEST_PH, ncp.K_NULL, ncp.K_PLA = K_TRAIN_PH, K_TEST_PH, K_NULL, K_PLA
    try:
        yield ncp
    finally:
        ncp.K_TRAIN_PH, ncp.K_TEST_PH, ncp.K_NULL, ncp.K_PLA = old


@contextlib.contextmanager
def pla_fraction(frac):
    """PL-A10: rebind n1b.ncp.PL_A_FRAC for the duration of the call (restored on exit)."""
    from n1b import ncp
    old = ncp.PL_A_FRAC
    ncp.PL_A_FRAC = frac
    try:
        yield
    finally:
        ncp.PL_A_FRAC = old
