"""m1lib: M1 offline motor-decoder comparison (prereg M1_decoder_comparison.md, SHA 9eada9d7...).

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. Computational decoding of recorded activity only.
Reuses nfharness (research/neurobiology/code/nfharness) by import only; nfharness is not modified.
"""
import os
import sys

NB_CODE = r"C:\Users\mariu\neuro-company\research\neurobiology\code"
if NB_CODE not in sys.path:
    sys.path.insert(0, NB_CODE)

ROOT = r"C:\Users\mariu\neuro-company\research\neurobiology\motor-readout"
RAW = os.path.join(ROOT, "data", "raw")
SEED = 20261001
