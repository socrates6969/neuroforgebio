"""Test-only step library (allow-listed explicitly by the tests' workers): steps that sleep, fail
or try the network, to exercise the queue and the sandbox. Never part of a published v1 library."""

from __future__ import annotations

import socket
import time
from pathlib import Path

from nf_steps import Library, Params, StepError
from pydantic import Field

LIBRARY = Library("nf_jobs_teststeps")


class SleepParams(Params):
    seconds: float = Field(default=1.0, ge=0)
    # while this file exists (and ``seconds`` has not passed) the step keeps sleeping
    hold_file: str = ""


@LIBRARY.step("sleep", "1", SleepParams, ("raw", "epochs", "features"), tolerance="exact")
def sleep_step(sig, p: SleepParams, _seed):
    """Pass the signal through after sleeping."""
    deadline = time.monotonic() + p.seconds
    while time.monotonic() < deadline:
        if p.hold_file and not Path(p.hold_file).exists():
            break
        time.sleep(0.05)
    return sig, {"slept": True}


class NoParams(Params):
    pass


@LIBRARY.step("fail", "1", NoParams, ("raw", "epochs", "features"), tolerance="exact")
def fail_step(sig, p: NoParams, _seed):
    """A parameter/input error: not retryable."""
    raise StepError("deliberate step error")


class NetParams(Params):
    host: str = "192.0.2.1"  # TEST-NET-1 (RFC 5737): never routed
    port: int = 9


@LIBRARY.step("net", "1", NetParams, ("raw",), tolerance="exact")
def net_step(sig, p: NetParams, _seed):
    """Tries an outbound connection (SEC-074: must fail inside the sandbox)."""
    with socket.create_connection((p.host, p.port), timeout=2):
        pass
    return sig, {"connected": True}
