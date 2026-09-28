"""Step runners: how one pipeline step executes (BUILD-GUIDE 3.3).

Every runner takes the same inputs -- a :class:`nf_steps.pipeline.StepCall`, the run seed, an input
directory holding ``signal.npy`` + ``signal.json`` and an empty output directory -- and returns the
step record the step wrote (``step.json``). Locally, steps run in-process or as a sandboxed
subprocess with pinned threads (:mod:`nf_runner.sandbox`); in production they run in a container
pulled by digest after its signature is verified (:class:`ContainerRunner`, tested in CI only).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from nf_steps.pipeline import STEP_RECORD, StepCall, run_step_files

from nf_runner import sandbox

StopCheck = Callable[[], bool]
IMAGE_RE = re.compile(r"^[a-z0-9][a-z0-9._/:-]*@sha256:[0-9a-f]{64}$")
_ZERO_DIGEST = "sha256:" + "0" * 64


class StepFailed(Exception):
    """The step failed. ``retryable`` is False for parameter/input errors (same result on retry)."""

    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


class StepTimeout(StepFailed):
    def __init__(self, message: str) -> None:
        super().__init__(message, retryable=True)


class StepStopped(Exception):
    """The worker asked the step to stop (cancel requested or lease lost)."""


class ImageRefused(StepFailed):
    """SEC-044: the image is not pinned by digest, or its signature does not verify."""

    def __init__(self, message: str) -> None:
        super().__init__(message, retryable=False)


class StepRunner(Protocol):
    name: str

    def run(
        self,
        call: StepCall,
        seed: int | None,
        in_dir: Path,
        out_dir: Path,
        *,
        timeout_s: float,
        should_stop: StopCheck,
    ) -> dict[str, Any]: ...


def _write_params(call: StepCall, workdir: Path) -> Path:
    p = workdir / "params.json"
    p.write_text(json.dumps(call.params, sort_keys=True), encoding="utf-8")
    return p


def _read_record(out_dir: Path) -> dict[str, Any]:
    return json.loads((out_dir / STEP_RECORD).read_text(encoding="utf-8"))


@dataclass
class InProcessRunner:
    """Runs the step in the worker process (tests, dev). The worker process should have been started
    with the thread pins of ``nf_steps.PINNED_ENV`` for bit-reproducible BLAS results."""

    extra_libraries: tuple[str, ...] = ()
    name: str = "inprocess"

    def run(self, call, seed, in_dir, out_dir, *, timeout_s, should_stop):
        from nf_steps import SignalError, StepError  # noqa: PLC0415

        if should_stop():
            raise StepStopped(call.id)
        try:
            return run_step_files(
                call.step, call.params, seed, in_dir, out_dir, self.extra_libraries
            )
        except (StepError, SignalError) as e:
            raise StepFailed(f"{call.id}: {e}", retryable=False) from e


def _wait(
    proc: subprocess.Popen, call: StepCall, timeout_s: float, should_stop: StopCheck, poll_s: float
) -> None:
    deadline = time.monotonic() + timeout_s
    while proc.poll() is None:
        if should_stop():
            proc.kill()
            proc.wait()
            raise StepStopped(call.id)
        if time.monotonic() > deadline:
            proc.kill()
            proc.wait()
            raise StepTimeout(f"{call.id}: timed out after {timeout_s:.0f} s")
        time.sleep(poll_s)


@dataclass
class SubprocessRunner:
    """A fresh interpreter per step with a from-scratch environment, pinned threads, no network
    (in-interpreter guard) and a timeout; :mod:`nf_runner.sandbox` says what it does not cover."""

    extra_paths: tuple[str, ...] = ()
    extra_libraries: tuple[str, ...] = ()
    python: str = field(default_factory=lambda: sys.executable)
    poll_s: float = 0.05
    name: str = "subprocess"

    def command(self, call: StepCall, seed: int | None, params: Path, in_dir, out_dir) -> list[str]:
        cmd = [self.python, "-c", sandbox.BOOTSTRAP, "run", "--step", call.step]
        cmd += ["--params", str(params), "--in", str(in_dir), "--out", str(out_dir)]
        if seed is not None:
            cmd += ["--seed", str(int(seed))]
        return cmd

    def run(self, call, seed, in_dir, out_dir, *, timeout_s, should_stop):
        workdir = Path(out_dir).parent
        workdir.mkdir(parents=True, exist_ok=True)
        params = _write_params(call, workdir)
        env = sandbox.step_env(
            workdir, extra_paths=self.extra_paths, extra_libraries=self.extra_libraries
        )
        cmd = self.command(call, seed, params, in_dir, out_dir)
        err_path = workdir / f"{call.id}.stderr"
        with err_path.open("wb") as err:
            proc = subprocess.Popen(  # noqa: S603 - fixed interpreter, argument list, no shell
                cmd, cwd=workdir, env=env, stdin=subprocess.DEVNULL, stdout=err, stderr=err
            )
            _wait(proc, call, timeout_s, should_stop, self.poll_s)
        if proc.returncode != 0:
            tail = err_path.read_text(encoding="utf-8", errors="replace")[-800:]
            raise StepFailed(
                f"{call.id}: exit {proc.returncode}: {tail.strip()}",
                retryable=proc.returncode != 2,
            )
        return _read_record(Path(out_dir))


class ImageVerifier(Protocol):
    def verify(self, image: str) -> None:
        """Raise :class:`ImageRefused` unless ``image`` carries a valid signature."""


@dataclass
class CosignVerifier:
    """Verify a step image's signature with cosign against a pinned public key (SEC-044). CI/prod
    only: needs the ``cosign`` binary and network access to the registry."""

    public_key: str
    cosign: str = "cosign"
    timeout_s: float = 120.0

    def verify(self, image: str) -> None:
        cmd = [self.cosign, "verify", "--key", self.public_key, image]
        try:
            r = subprocess.run(  # noqa: S603 - fixed binary, argument list, no shell
                cmd, capture_output=True, timeout=self.timeout_s, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            raise ImageRefused(f"cannot verify {image}: {type(e).__name__}") from e
        if r.returncode != 0:
            raise ImageRefused(f"signature verification failed for {image}")


def check_image(image: str | None) -> str:
    """Digest-pinned only (SEC-044); the library's placeholder digest is never runnable."""
    if not image or not IMAGE_RE.match(image):
        raise ImageRefused(f"image must be pinned as name@sha256:<64 hex>, got {image!r}")
    if image.endswith(_ZERO_DIGEST) or image.startswith("registry.invalid/"):
        raise ImageRefused(f"placeholder image {image} is not a built, signed image")
    return image


@dataclass
class ContainerRunner:
    """``docker run`` of the step image, pinned by digest and signature-verified first (SEC-044),
    with the SEC-073/074 sandbox: no network, read-only root FS, non-root user, no capabilities,
    no privilege escalation, CPU/memory/pids limits, only the job's input (read-only) and output
    directories mounted, thread pins in the environment. Tested in CI only (no Docker locally)."""

    verifier: ImageVerifier
    docker: str = "docker"
    memory: str = "1g"
    cpus: str = "1"
    pids_limit: int = 256
    user: str = "65534:65534"
    poll_s: float = 0.2
    name: str = "container"

    def command(self, call: StepCall, seed: int | None, in_dir: Path, out_dir: Path) -> list[str]:
        from nf_steps import PINNED_ENV  # noqa: PLC0415

        image = check_image(call.image)
        cmd = [self.docker, "run", "--rm", "--network", "none", "--read-only"]
        cmd += ["--user", self.user, "--cap-drop", "ALL"]
        cmd += ["--security-opt", "no-new-privileges"]
        cmd += ["--memory", self.memory, "--cpus", self.cpus, "--pids-limit", str(self.pids_limit)]
        cmd += ["--tmpfs", "/tmp:rw,noexec,nosuid,size=256m"]
        cmd += [
            "-v",
            f"{Path(in_dir).resolve()}:/in:ro",
            "-v",
            f"{Path(out_dir).resolve()}:/out:rw",
        ]
        for k, v in sorted(PINNED_ENV.items()):
            cmd += ["-e", f"{k}={v}"]
        entry = list(call.entrypoint) or ["nf-step", "run"]
        cmd += ["--entrypoint", entry[0], image, *entry[1:]]
        cmd += ["--step", call.step, "--params", "/in/params.json", "--in", "/in", "--out", "/out"]
        if seed is not None:
            cmd += ["--seed", str(int(seed))]
        return cmd

    def run(self, call, seed, in_dir, out_dir, *, timeout_s, should_stop):
        cmd = self.command(call, seed, Path(in_dir), Path(out_dir))  # refuses unpinned first
        self.verifier.verify(check_image(call.image))  # then refuses unsigned, before any pull
        (Path(in_dir) / "params.json").write_text(
            json.dumps(call.params, sort_keys=True), encoding="utf-8"
        )
        err_path = Path(out_dir).parent / f"{call.id}.stderr"
        with err_path.open("wb") as err:
            proc = subprocess.Popen(  # noqa: S603 - fixed binary, argument list, no shell
                cmd, stdin=subprocess.DEVNULL, stdout=err, stderr=err
            )
            _wait(proc, call, timeout_s, should_stop, self.poll_s)
        if proc.returncode != 0:
            raise StepFailed(f"{call.id}: container exit {proc.returncode}", retryable=True)
        return _read_record(Path(out_dir))


def make_runner(
    kind: str,
    *,
    extra_paths: Iterable[str] = (),
    extra_libraries: Iterable[str] = (),
    verifier: ImageVerifier | None = None,
) -> StepRunner:
    if kind == "inprocess":
        return InProcessRunner(extra_libraries=tuple(extra_libraries))
    if kind == "subprocess":
        return SubprocessRunner(
            extra_paths=tuple(extra_paths), extra_libraries=tuple(extra_libraries)
        )
    if kind == "container":
        if verifier is None:
            raise ValueError("the container runner needs an image verifier (SEC-044)")
        return ContainerRunner(verifier=verifier)
    raise ValueError(f"unknown runner {kind!r}")
