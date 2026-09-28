"""nf-synth: deterministic synthetic EEG-like fixtures with known ground truth (BUILD-GUIDE 0.6)."""

from .generate import GENERATOR_VERSION, SynthParams, data_sha256, generate, welch_psd
from .writers import (
    WRITERS,
    write_bdf,
    write_brainvision,
    write_edf,
    write_nwb,
    write_truth,
    write_xdf,
)

__all__ = [
    "GENERATOR_VERSION",
    "WRITERS",
    "SynthParams",
    "data_sha256",
    "generate",
    "welch_psd",
    "write_bdf",
    "write_brainvision",
    "write_edf",
    "write_nwb",
    "write_truth",
    "write_xdf",
]
