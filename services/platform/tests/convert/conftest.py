"""Fixtures for converter tests. All data is synthetic (tools/synth); nothing real is used."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from nf_platform.signals import EncryptedZarrStore
from nf_platform.storage import InMemoryKeyStore, Keyring, LocalKms, LocalObjectStore
from nf_synth.generate import SynthParams, generate
from nf_synth.writers import write_bdf, write_brainvision, write_edf, write_xdf


@pytest.fixture(scope="session")
def synth():
    """(data_uv[8, 3584], truth): 8 channels, 256 Hz, 14 s, events every 2 s."""
    return generate(SynthParams(seed=7, n_channels=8, sfreq=256, duration_s=14))


@pytest.fixture
def fixture_file(tmp_path, synth):
    data, truth = synth
    writers = {
        "edf": (".edf", write_edf),
        "bdf": (".bdf", write_bdf),
        "brainvision": (".vhdr", write_brainvision),
        "xdf": (".xdf", write_xdf),
    }

    def make(fmt: str) -> Path:
        ext, fn = writers[fmt]
        return Path(fn(tmp_path / f"src-{fmt}{ext}", data, truth))

    return make


@pytest.fixture
def store(tmp_path):
    """Encrypted canonical store, as in production (chunks are ciphertext at rest)."""
    keyring = Keyring(LocalKms(), InMemoryKeyStore())
    return EncryptedZarrStore(
        LocalObjectStore(tmp_path / "objects"), keyring, "tenant-1", "sub-01", "recordings"
    )


def edf_quantum(pmin: float, pmax: float, bdf: bool) -> float:
    span = (2**24 - 1) if bdf else (2**16 - 1)
    return (pmax - pmin) / span


@pytest.fixture
def rng():
    return np.random.default_rng(1234)
