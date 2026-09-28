"""Test-only step library for the m5-ledger tests (allow-listed explicitly by the tests' worker):
one pass-through step, so pipeline runs are fast and their output equals the input signal."""

from __future__ import annotations

from nf_steps import Library, Params

LIBRARY = Library("nf_gov_teststeps")


class NoParams(Params):
    pass


@LIBRARY.step("passthrough", "1", NoParams, ("raw", "epochs", "features"), tolerance="exact")
def passthrough(sig, p: NoParams, _seed):
    """Return the signal unchanged."""
    return sig, {"passthrough": True}
