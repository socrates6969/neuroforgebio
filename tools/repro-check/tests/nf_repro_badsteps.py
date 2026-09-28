"""Deliberately non-reproducible test step (3.5 acceptance): an UNSEEDED random call. Test fixture
only; allow-listed explicitly by the harness tests, never published."""

from __future__ import annotations

import numpy as np
from nf_steps import Library, Params

LIBRARY = Library("nf_repro_badsteps")


class NoiseParams(Params):
    scale: float = 1e-3


@LIBRARY.step("noise", "1", NoiseParams, ("raw", "epochs", "features"), tolerance="exact")
def noise_step(sig, p: NoiseParams, _seed):
    """Adds noise from an unseeded generator: every run differs."""
    rng = np.random.default_rng()  # deliberately unseeded
    sig.data = sig.data + p.scale * rng.standard_normal(sig.data.shape)
    return sig, {}
