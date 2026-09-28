"""3.3 step runners: sandboxed subprocess (local) and signed container (CI) -- SEC-044, SEC-073,
SEC-074 -- without a database."""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

import numpy as np
import pytest
from nf_runner import sandbox
from nf_runner.__main__ import EARLY_PINS
from nf_runner.steprunner import (
    ContainerRunner,
    CosignVerifier,
    ImageRefused,
    InProcessRunner,
    StepFailed,
    StepStopped,
    StepTimeout,
    SubprocessRunner,
    check_image,
)
from nf_steps import PINNED_ENV, Signal, signal
from nf_steps.pipeline import StepCall, step_calls
from nf_steps.pipelines import PLACEHOLDER_IMAGE

HERE = Path(__file__).resolve().parent
LIB = "nf_runner_teststeps"
IMAGE = "ghcr.io/example/nf-steps@sha256:" + "ab" * 32


def _sig() -> Signal:
    rng = np.random.default_rng(0)
    return Signal("raw", rng.standard_normal((4, 512)), 128.0, ["a", "b", "c", "d"], ["eeg"] * 4)


def _call(step: str, params=None, image=IMAGE) -> StepCall:
    doc = {"steps": [{"name": "s1", "step": step, "params": params or {}, "image": image}]}
    return step_calls(doc, (LIB,))[0]


@pytest.fixture
def io(tmp_path):
    signal.write(_sig(), tmp_path / "in")
    return tmp_path / "in", tmp_path / "out"


def _sub() -> SubprocessRunner:
    return SubprocessRunner(extra_paths=(str(HERE),), extra_libraries=(LIB,))


def _never() -> bool:
    return False


def test_early_pins_match_the_step_library():
    assert EARLY_PINS == PINNED_ENV


def test_subprocess_step_runs_with_pinned_threads_and_a_scrubbed_env(io, monkeypatch):
    monkeypatch.setenv("NF_DATABASE_URL", "postgresql://secret@db/nf")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "not-for-steps")
    rec = _sub().run(_call(f"{LIB}.env@1"), 7, *io, timeout_s=120, should_stop=_never)
    assert rec["environment"]["threads"] == PINNED_ENV
    assert rec["seed"] == 7
    names = set(rec["info"]["env"])
    assert not names & {"NF_DATABASE_URL", "AWS_SECRET_ACCESS_KEY"}
    assert set(PINNED_ENV) <= names
    assert signal.read(io[1]).data.shape == (4, 512)


def test_subprocess_and_inprocess_outputs_are_byte_identical(io, tmp_path):
    call = _call("nf_steps.filter@1", {"l_freq": 1.0, "h_freq": 30.0})
    a, b = tmp_path / "a" / "out", tmp_path / "b" / "out"
    _sub().run(call, None, io[0], a, timeout_s=120, should_stop=_never)
    InProcessRunner().run(call, None, io[0], b, timeout_s=120, should_stop=_never)
    for f in signal.FILES:
        assert (a / f).read_bytes() == (b / f).read_bytes()


def test_sec074_outbound_connection_fails_in_the_sandbox(io):
    with pytest.raises(StepFailed, match="network access is disabled"):
        _sub().run(_call(f"{LIB}.net@1"), None, *io, timeout_s=120, should_stop=_never)
    assert not (io[1] / signal.DATA_FILE).exists()


def test_step_timeout_kills_the_process(io):
    t0 = time.monotonic()
    call = _call(f"{LIB}.sleep@1", {"seconds": 60})
    with pytest.raises(StepTimeout):
        _sub().run(call, None, *io, timeout_s=8, should_stop=_never)
    assert time.monotonic() - t0 < 30


def test_stop_request_kills_the_process(io):
    t0 = time.monotonic()
    call = _call(f"{LIB}.sleep@1", {"seconds": 60})
    with pytest.raises(StepStopped):
        _sub().run(call, None, *io, timeout_s=120, should_stop=lambda: time.monotonic() > t0 + 6)
    assert time.monotonic() - t0 < 30


def test_parameter_errors_are_not_retryable(io):
    call = StepCall("s1", "nf_steps.filter@1", {"l_freq": None, "h_freq": None}, {"kind": "exact"})
    with pytest.raises(StepFailed) as e:
        _sub().run(call, None, *io, timeout_s=120, should_stop=_never)
    assert e.value.retryable is False


def test_bootstrap_blocks_network_before_any_step_code():
    assert "socket.create_connection = _deny" in sandbox.BOOTSTRAP
    assert "socket.getaddrinfo = _deny" in sandbox.BOOTSTRAP


# ------------------------------------------------------------- container runner (SEC-044/073/074)
class Refuse:
    def verify(self, image: str) -> None:
        raise ImageRefused(f"unsigned {image}")


class Accept:
    def verify(self, image: str) -> None:
        return None


def test_container_command_is_sandboxed(io):
    cmd = ContainerRunner(verifier=Accept()).command(_call("nf_steps.filter@1"), 3, *io)
    joined = " ".join(cmd)
    for flag in (
        "--network none",
        "--read-only",
        "--user 65534:65534",
        "--cap-drop ALL",
        "--security-opt no-new-privileges",
        "--memory 1g",
        "--cpus 1",
        "--pids-limit 256",
        ":/in:ro",
        "--seed 3",
    ):
        assert flag in joined, flag
    assert IMAGE in cmd and "--privileged" not in cmd
    assert all(f"{k}={v}" in cmd for k, v in PINNED_ENV.items())


@pytest.mark.parametrize(
    "image",
    ["ghcr.io/example/nf-steps:latest", "ghcr.io/example/nf-steps", PLACEHOLDER_IMAGE, None],
)
def test_unpinned_or_placeholder_images_are_refused(image):
    with pytest.raises(ImageRefused):
        check_image(image)


def test_unsigned_image_run_is_refused_before_docker_runs(io):
    """SEC-044 acceptance: unsigned image -> run refused (docker is never invoked)."""
    r = ContainerRunner(verifier=Refuse(), docker=str(io[0] / "no-such-docker"))
    with pytest.raises(ImageRefused, match="unsigned"):
        r.run(_call("nf_steps.filter@1"), None, *io, timeout_s=10, should_stop=_never)


def test_cosign_verifier_fails_closed_without_cosign():
    v = CosignVerifier(public_key="cosign.pub", cosign=str(Path("no-such-dir") / "cosign"))
    with pytest.raises(ImageRefused):
        v.verify(IMAGE)


@pytest.mark.integration
@pytest.mark.skipif(
    not (os.environ.get("NF_TEST_STEP_IMAGE") and shutil.which("docker")),
    reason="CI-only: needs Docker and a built, signed step image (NF_TEST_STEP_IMAGE, cosign key)",
)
def test_container_runner_runs_a_signed_image(io):  # pragma: no cover - CI only
    image = os.environ["NF_TEST_STEP_IMAGE"]
    r = ContainerRunner(verifier=CosignVerifier(os.environ["NF_TEST_COSIGN_KEY"]))
    call = _call("nf_steps.filter@1", image=image)
    rec = r.run(call, None, *io, timeout_s=600, should_stop=_never)
    assert rec["environment"]["threads"] == PINNED_ENV
