"""Test-only steps for the runner sandbox tests (allow-listed explicitly by those tests)."""

from __future__ import annotations

import os
import socket
import time

from nf_steps import Library, Params

LIBRARY = Library("nf_runner_teststeps")


class NetParams(Params):
    host: str = "192.0.2.1"  # TEST-NET-1 (RFC 5737): never routed
    port: int = 9


@LIBRARY.step("net", "1", NetParams, ("raw",), tolerance="exact")
def net_step(sig, p: NetParams, _seed):
    """Tries an outbound connection (SEC-074)."""
    with socket.create_connection((p.host, p.port), timeout=2):
        pass
    return sig, {"connected": True}


class SleepParams(Params):
    seconds: float = 30.0


@LIBRARY.step("sleep", "1", SleepParams, ("raw",), tolerance="exact")
def sleep_step(sig, p: SleepParams, _seed):
    time.sleep(p.seconds)
    return sig, {}


class NoParams(Params):
    pass


@LIBRARY.step("env", "1", NoParams, ("raw",), tolerance="exact")
def env_step(sig, p: NoParams, _seed):
    """Reports the environment variable NAMES the step process sees."""
    return sig, {"env": sorted(os.environ)}
