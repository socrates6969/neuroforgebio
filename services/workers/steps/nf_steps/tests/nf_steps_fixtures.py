"""Synthetic signals for the step-library tests (tools/synth ground truth; no real human data).

A uniquely named helper module (not ``conftest``) so imports do not collide with other test
directories' conftest modules in one pytest session.
"""

from __future__ import annotations

from nf_steps import Signal
from nf_synth.generate import SynthParams, generate


def synth_signal(seed: int = 1, **kw) -> tuple[Signal, dict]:
    data, truth = generate(SynthParams(seed=seed, **kw))
    sig = Signal(
        kind="raw",
        data=data,
        sfreq=float(truth["sfreq"]),
        ch_names=list(truth["channels"]),
        ch_types=["eeg"] * len(truth["channels"]),
        events=[[e["sample"], e["code"]] for e in truth["events"]],
    )
    return sig, truth
