"""nfharness: leak-proof evaluation harness for seizure-detection models (cycle 1, CHB-MIT).

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims.

Modules: config (locked N2 config, RNG streams, guard registry), errors (named guard exceptions), data (manifest/hash
verification, summary parsing, synthetic EDFs), splits (S1/S5/S7/F6), windows (F4), features (F7), labels (F8 vault),
model (F1 normaliser, F2 config lock, F5 resampling guard, L2-LR), postprocess (F3, k-of-n), scoring (F9 timescoring
wrapper, independent re-implementation, latency, Scorer), stats (AUROC/AUPRC, Clopper-Pearson, Garwood, bootstraps),
pipeline (the locked N2 flow + N1 control variants), provenance (hashes, versions, peak RAM, canonical JSON),
card (evaluation card JSON/Markdown + figure).
"""
__version__ = "0.1.0"
