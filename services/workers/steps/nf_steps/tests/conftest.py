"""Fixtures for the step library tests."""

from __future__ import annotations

import pytest
from nf_steps import Signal
from nf_steps_fixtures import synth_signal


@pytest.fixture(scope="module")
def synth() -> tuple[Signal, dict]:
    return synth_signal(1)
