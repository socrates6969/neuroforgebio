"""Step definitions, parameter resolution and the library registry.

Every step has a pydantic parameter model with ``extra="forbid"`` and an explicit default for
every field. :meth:`Step.resolve` returns the complete parameter set (user values + every default)
as JSON; that is what the run record stores (BLUEPRINT §3.5: defaults are written into the run
record, not left implicit).

Step references are ``<library>.<name>@<version>``, e.g. ``nf_steps.filter@1``. A library is a
module exposing ``LIBRARY``. Only allow-listed libraries are importable by reference
(``nf_steps`` plus explicitly passed extras), so a pipeline spec cannot make a worker import
arbitrary modules.
"""

from __future__ import annotations

import importlib
import os
import platform
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from nf_steps.signal import Kind, Signal, SignalError

ToleranceKind = Literal["exact", "abs", "rel"]
REF_RE = re.compile(r"^(?P<lib>[a-z_][a-z0-9_]*)\.(?P<name>[a-z_][a-z0-9_]*)@(?P<ver>[0-9]+)$")
DEFAULT_LIBRARIES = ("nf_steps",)
# Thread pins for deterministic BLAS/FFT (BLUEPRINT §3.5 determinism controls). Workers set these in
# the environment of every step process/container; ``environment()`` records them in the run record.
PINNED_ENV = {
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
    "PYTHONHASHSEED": "0",
}


class StepError(Exception):
    """A step cannot run with these inputs/parameters (not retryable)."""


class Params(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


@dataclass(frozen=True)
class StepOutput:
    signal: Signal
    params: dict[str, Any]
    info: dict[str, Any] = field(default_factory=dict)


StepFn = Callable[[Signal, Any, "int | None"], tuple[Signal, dict[str, Any]]]


@dataclass(frozen=True)
class Step:
    library: str
    name: str
    version: str
    params_model: type[Params]
    accepts: tuple[Kind, ...]
    fn: StepFn
    # Reproducibility class (hashing.md §5.1 tolerance object): "exact" = byte-identical outputs;
    # "abs" = |a - b| <= value; "rel" = |a - b| <= value * max|b| (relative to the output's scale).
    tolerance: ToleranceKind = "rel"
    tolerance_value: float | None = 1e-9
    needs_seed: bool = False
    doc: str = ""

    @property
    def ref(self) -> str:
        return f"{self.library}.{self.name}@{self.version}"

    def tolerance_doc(self) -> dict[str, Any]:
        if self.tolerance == "exact":
            return {"kind": "exact"}
        return {"kind": self.tolerance, "value": self.tolerance_value}

    def resolve(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            return self.params_model(**(params or {})).model_dump(mode="json")
        except ValidationError as e:
            raise StepError(f"{self.ref}: invalid parameters: {e.errors(include_url=False)}") from e

    def __call__(
        self, sig: Signal, params: dict[str, Any] | None = None, seed: int | None = None
    ) -> StepOutput:
        resolved = self.resolve(params)
        if sig.kind not in self.accepts:
            raise StepError(f"{self.ref} accepts {list(self.accepts)}, got {sig.kind!r}")
        if self.needs_seed and seed is None:
            raise StepError(f"{self.ref} is randomized and needs an explicit seed")
        try:
            out, info = self.fn(sig, self.params_model(**resolved), seed)
        except SignalError as e:
            raise StepError(f"{self.ref}: {e}") from e
        return StepOutput(signal=out, params=resolved, info=info)


@dataclass
class Library:
    name: str
    steps: dict[str, Step] = field(default_factory=dict)

    def step(
        self,
        name: str,
        version: str,
        params_model: type[Params],
        accepts: Iterable[Kind],
        *,
        tolerance: ToleranceKind = "rel",
        tolerance_value: float | None = 1e-9,
        needs_seed: bool = False,
    ) -> Callable[[StepFn], StepFn]:
        def deco(fn: StepFn) -> StepFn:
            st = Step(
                library=self.name,
                name=name,
                version=version,
                params_model=params_model,
                accepts=tuple(accepts),
                fn=fn,
                tolerance=tolerance,
                tolerance_value=None if tolerance == "exact" else tolerance_value,
                needs_seed=needs_seed,
                doc=(fn.__doc__ or "").strip(),
            )
            if st.ref in self.steps:
                raise ValueError(f"duplicate step {st.ref}")
            self.steps[st.ref] = st
            return fn

        return deco


def parse_ref(ref: str) -> tuple[str, str, str]:
    m = REF_RE.match(ref)
    if not m:
        raise StepError(f"bad step reference {ref!r} (expected <library>.<name>@<version>)")
    return m["lib"], m["name"], m["ver"]


def get_step(ref: str, extra_libraries: Iterable[str] = ()) -> Step:
    lib, _, _ = parse_ref(ref)
    allowed = set(DEFAULT_LIBRARIES) | set(extra_libraries)
    if lib not in allowed:
        raise StepError(f"step library {lib!r} is not allow-listed")
    mod = importlib.import_module(lib)
    library: Library | None = getattr(mod, "LIBRARY", None)
    if library is None or ref not in library.steps:
        raise StepError(f"unknown step {ref!r}")
    return library.steps[ref]


def environment() -> dict[str, Any]:
    """Library versions and thread pins, for the run record."""
    import mne  # noqa: PLC0415 - heavy import only when recording the environment
    import numpy  # noqa: PLC0415
    import scipy  # noqa: PLC0415

    from nf_steps import __version__  # noqa: PLC0415

    return {
        "nf_steps": __version__,
        "mne": mne.__version__,
        "numpy": numpy.__version__,
        "scipy": scipy.__version__,
        "python": platform.python_version(),
        "machine": platform.machine().lower(),
        "threads": {k: os.environ.get(k) for k in PINNED_ENV},
    }
