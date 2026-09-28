"""n1b: negative controls v2 (prereg\\N1b_negative_controls_v2.md). NEW code only; imports nfharness UNCHANGED.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims.

Modules: segments (ictal exclusion -> allowed pseudo-records, §2.1), sampler (sampler S, exact enumeration, §2.2),
vault (PhantomVault + order log + planted-leak flag guard, §2.2/§4), ncp (NC-P replicate, t_rm, degeneracy, exact
conditional-randomisation nulls, Fisher, PL-A, PL-B; §2.3-2.4, §4), c3prime (exact random-alarm distribution, harness
Monte Carlo, PL-C; §3-4), synth (synthetic EDFs with the real layout, §5), figures.
"""
__version__ = "0.1.0"

SEED = 20261001
# stream ids (prereg §7)
K_TRAIN_PH, K_TEST_PH, K_NULL, K_PLA, K_C3MC, K_PLC, K_SYN = 10, 11, 12, 13, 14, 15, 16


def rng(*key):
    """numpy Generator: default_rng(SeedSequence(20261001, spawn_key=key)); key = (k, subject_index, replicate)
    for the real run, (16, k, subject_index, replicate) for the synthetic dry run (DEVIATIONS N1b-4)."""
    import numpy as np
    return np.random.default_rng(np.random.SeedSequence(SEED, spawn_key=tuple(int(k) for k in key)))
