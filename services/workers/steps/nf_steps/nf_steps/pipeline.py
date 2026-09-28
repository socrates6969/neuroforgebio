"""Chaining the steps of a PipelineVersion in-process (runners and the repro harness build on it).

A spec is a PipelineVersion document (docs/spec/hashing.md §5.1; ``nf_platform.pipelines.spec``):
``{"schema", "meta": {"name", "version"}, "steps": [{"name", "step", "image", "entrypoint",
"params", "tolerance": {"kind", "value"}}], "seed"}`` -- a dict or an object with
``to_document()``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nf_steps import signal
from nf_steps.base import StepError, StepOutput, environment, get_step
from nf_steps.signal import Signal, canonical_json

STEP_RECORD = "step.json"


def document(spec: Any) -> dict[str, Any]:
    if hasattr(spec, "to_document"):
        return spec.to_document()
    if isinstance(spec, Mapping):
        return dict(spec)
    raise StepError("pipeline spec must be a document dict or have to_document()")


@dataclass(frozen=True)
class StepCall:
    id: str
    step: str
    params: dict[str, Any]
    tolerance: dict[str, Any]
    image: str | None = None
    entrypoint: tuple[str, ...] = ()

    @property
    def exact(self) -> bool:
        return self.tolerance.get("kind") == "exact"


def step_calls(spec: Any, extra_libraries: Iterable[str] = ()) -> list[StepCall]:
    """The spec's steps with fully resolved parameters (every default explicit)."""
    out = []
    seen: set[str] = set()
    for s in document(spec).get("steps") or []:
        sid = str(s.get("name"))
        if sid in seen:
            raise StepError(f"duplicate step name {sid!r}")
        seen.add(sid)
        if not s.get("step"):
            raise StepError(f"step {sid!r} has no step-library reference")
        st = get_step(str(s["step"]), extra_libraries)
        tol = dict(s.get("tolerance") or st.tolerance_doc())
        if tol.get("kind") not in ("exact", "abs", "rel"):
            raise StepError(f"step {sid!r}: bad tolerance {tol!r}")
        out.append(
            StepCall(
                id=sid,
                step=st.ref,
                params=st.resolve(dict(s.get("params") or {})),
                tolerance=tol,
                image=s.get("image"),
                entrypoint=tuple(s.get("entrypoint") or ()),
            )
        )
    if not out:
        raise StepError("pipeline has no steps")
    return out


def spec_seed(spec: Any) -> int | None:
    seed = document(spec).get("seed")
    return None if seed is None else int(seed)


def spec_ref(spec: Any) -> str:
    meta = document(spec).get("meta") or {}
    return f"{meta.get('name')}@{meta.get('version')}"


def run_chain(
    calls: list[StepCall],
    sig: Signal,
    seed: int | None,
    *,
    extra_libraries: Iterable[str] = (),
    on_step: Callable[[StepCall, StepOutput], None] | None = None,
) -> list[tuple[StepCall, StepOutput]]:
    """Run ``calls`` in order, each on the previous output. ``on_step`` sees each result (the worker
    uses it to stage outputs and heartbeat)."""
    results = []
    cur = sig
    for call in calls:
        out = get_step(call.step, extra_libraries)(cur, call.params, seed)
        if on_step is not None:
            on_step(call, out)
        results.append((call, out))
        cur = out.signal
    return results


def run_step_files(
    ref: str,
    params: dict[str, Any],
    seed: int | None,
    in_dir: str | Path,
    out_dir: str | Path,
    extra_libraries: Iterable[str] = (),
) -> dict[str, Any]:
    """Run one step from an input directory into an output directory (``signal.npy``,
    ``signal.json``, and ``step.json`` = the step's record: resolved parameters, seed, info, output
    hashes, environment). Every runner (in-process, subprocess, container) goes through this."""
    st = get_step(ref, extra_libraries)
    out = st(signal.read(in_dir), params, seed)
    hashes = signal.write(out.signal, out_dir)
    record = {
        "step": st.ref,
        "params": out.params,
        "seed": seed,
        "info": out.info,
        "outputs": hashes,
        "environment": environment(),
    }
    (Path(out_dir) / STEP_RECORD).write_bytes(canonical_json(record))
    return record


class StepLibraryCatalog:
    """``nf_platform.pipelines.spec.StepCatalog`` for this library (publish fills every default)."""

    def __init__(self, extra_libraries: Iterable[str] = ()) -> None:
        self.extra = tuple(extra_libraries)

    def defaults(self, step_ref: str) -> Mapping[str, Any] | None:
        try:
            return get_step(step_ref, self.extra).resolve({})
        except StepError:
            return None
