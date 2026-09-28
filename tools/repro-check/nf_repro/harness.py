"""Reproducibility harness (BUILD-GUIDE 3.5; BLUEPRINT §3.5, §10).

Runs every published pipeline twice on synthetic fixtures (tools/synth), each step in a fresh,
thread-pinned process by default, and compares the two runs step by step:

- ``exact`` steps must produce byte-identical files (``signal.npy`` and ``signal.json``);
- ``abs`` / ``rel`` steps must agree within their declared tolerance (abs: ``|a - b| <= value``;
  rel: ``|a - b| <= value * max|b|``), with identical shapes and metadata (numbers in the
  metadata compared with the same tolerance).

The outputs of each run are kept, so a CI job can compare two CPU architectures afterwards
(:func:`compare_trees`): there, byte-identity is required only while every step so far is
``exact``; once a floating-point step came before, results are compared with the step's tolerance
or, for ``exact`` steps, with :data:`CROSS_ARCH_FALLBACK` (BLUEPRINT §3.5: byte-identical on the
same platform class, within tolerance across architectures).
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from nf_runner.steprunner import InProcessRunner, StepRunner, SubprocessRunner
from nf_steps import Signal, pipelines, signal
from nf_steps.pipeline import StepCall, spec_ref, spec_seed, step_calls

CROSS_ARCH_FALLBACK = {"kind": "rel", "value": 1e-6}
REPORT_SCHEMA = "nf.repro-report/v1"


@dataclass
class StepResult:
    pipeline: str
    fixture: str
    step: str
    ref: str
    tolerance: dict[str, Any]
    ok: bool
    detail: str
    sha256_a: dict[str, str]
    sha256_b: dict[str, str]
    max_abs_diff: float | None = None
    max_rel_diff: float | None = None


@dataclass
class Report:
    results: list[StepResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    started: float = field(default_factory=time.time)

    @property
    def ok(self) -> bool:
        return not self.errors and all(r.ok for r in self.results)


def synth_fixtures(seeds: Iterable[int] = (1,)) -> list[tuple[str, Signal]]:
    """Synthetic EEG fixtures with known ground truth (no real human data)."""
    from nf_synth.generate import SynthParams, generate  # noqa: PLC0415

    out = []
    for seed in seeds:
        data, truth = generate(SynthParams(seed=seed))
        sig = Signal(
            kind="raw",
            data=data,
            sfreq=float(truth["sfreq"]),
            ch_names=list(truth["channels"]),
            ch_types=["eeg"] * len(truth["channels"]),
            events=[[e["sample"], e["code"]] for e in truth["events"]],
        )
        out.append((f"synth-seed{seed}", sig))
    return out


def published_pipelines(extra_files: Iterable[str | Path] = ()) -> list[dict[str, Any]]:
    """The step library's published v1 pipelines plus any extra PipelineVersion documents."""
    docs = pipelines.all_specs()
    for f in extra_files:
        docs.append(json.loads(Path(f).read_text(encoding="utf-8")))
    return docs


def run_pipeline(
    calls: list[StepCall],
    seed: int | None,
    sig: Signal,
    out_root: Path,
    runner: StepRunner,
    timeout_s: float = 1800.0,
) -> None:
    """One run: input -> each step's directory under ``out_root`` (``NN-<step>/``)."""
    cur = out_root / "00-input"
    signal.write(sig, cur)
    for i, call in enumerate(calls, start=1):
        out = out_root / f"{i:02d}-{call.id}"
        runner.run(call, seed, cur, out, timeout_s=timeout_s, should_stop=lambda: False)
        cur = out


def _hashes(d: Path) -> dict[str, str]:
    return {f: hashlib.sha256((d / f).read_bytes()).hexdigest() for f in signal.FILES}


def _close_json(a: Any, b: Any, tol: dict[str, Any]) -> bool:
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_close_json(a[k], b[k], tol) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_close_json(x, y, tol) for x, y in zip(a, b, strict=True))
    num = (int, float)
    if isinstance(a, num) and isinstance(b, num) and not isinstance(a, bool):
        if tol["kind"] == "exact":
            return a == b
        v = float(tol["value"])
        lim = v if tol["kind"] == "abs" else v * max(abs(float(b)), 1e-300)
        return math.isclose(a, b, rel_tol=0, abs_tol=lim)
    return a == b


def compare_step(da: Path, db: Path, tol: dict[str, Any]) -> tuple[bool, str, float, float]:
    """(ok, detail, max |a-b|, max |a-b| / max|b|) for one step's two output directories."""
    ha, hb = _hashes(da), _hashes(db)
    a = signal.read(da)
    b = signal.read(db)
    if a.data.shape != b.data.shape:
        return False, f"shape {a.data.shape} != {b.data.shape}", math.inf, math.inf
    diff = np.abs(a.data - b.data)
    finite = np.isfinite(diff)
    mad = float(diff[finite].max()) if finite.any() else 0.0
    scale = float(np.abs(b.data).max()) if b.data.size else 0.0
    mrd = mad / scale if scale > 0 else (0.0 if mad == 0 else math.inf)
    if not np.array_equal(np.isnan(a.data), np.isnan(b.data)):
        return False, "NaN pattern differs", mad, mrd
    if tol["kind"] == "exact":
        if ha == hb:
            return True, "byte-identical", mad, mrd
        which = [f for f in signal.FILES if ha[f] != hb[f]]
        return False, f"not byte-identical: {', '.join(which)}", mad, mrd
    ma, mb = a.metadata(), b.metadata()
    if not _close_json(ma, mb, tol):
        return False, "metadata differs", mad, mrd
    v = float(tol["value"])
    limit = v if tol["kind"] == "abs" else v * scale
    if mad <= limit:
        exact = " (byte-identical)" if ha == hb else ""
        return True, f"within {tol['kind']} {v:g}{exact}", mad, mrd
    return False, f"exceeds {tol['kind']} {v:g}: max |a-b| = {mad:.3g}", mad, mrd


def check(
    specs: list[dict[str, Any]],
    fixtures: list[tuple[str, Signal]],
    out_dir: str | Path,
    *,
    runner: StepRunner | None = None,
    extra_libraries: Iterable[str] = (),
) -> Report:
    """Run every spec twice on every fixture; compare step by step. Outputs stay in ``out_dir``."""
    out = Path(out_dir)
    runner = runner or SubprocessRunner(extra_libraries=tuple(extra_libraries))
    report = Report()
    for spec in specs:
        ref = spec_ref(spec)
        try:
            calls = step_calls(spec, extra_libraries)
        except Exception as e:  # noqa: BLE001 - a broken spec is a harness failure, not a crash
            report.errors.append(f"{ref}: {e}")
            continue
        seed = spec_seed(spec)
        for fname, sig in fixtures:
            base = out / "outputs" / ref.replace("@", "_") / fname
            try:
                for run in ("a", "b"):
                    run_pipeline(calls, seed, sig, base / run, runner)
            except Exception as e:  # noqa: BLE001
                report.errors.append(f"{ref} on {fname}: run failed: {e}")
                continue
            for i, call in enumerate(calls, start=1):
                d = f"{i:02d}-{call.id}"
                ok, detail, mad, mrd = compare_step(base / "a" / d, base / "b" / d, call.tolerance)
                report.results.append(
                    StepResult(
                        pipeline=ref,
                        fixture=fname,
                        step=call.id,
                        ref=call.step,
                        tolerance=call.tolerance,
                        ok=ok,
                        detail=detail,
                        sha256_a=_hashes(base / "a" / d),
                        sha256_b=_hashes(base / "b" / d),
                        max_abs_diff=mad,
                        max_rel_diff=mrd,
                    )
                )
    return report


def _environment() -> dict[str, Any]:
    from nf_steps import environment  # noqa: PLC0415

    env = environment()
    env["platform"] = platform.platform()
    return env


def _num(x: float | None) -> float | str | None:
    if x is None or math.isfinite(x):
        return x
    return "inf"


def write_report(report: Report, out_dir: str | Path, *, label: str = "") -> tuple[Path, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    env = _environment()
    body = {
        "schema": REPORT_SCHEMA,
        "label": label,
        "ok": report.ok,
        "environment": env,
        "errors": report.errors,
        "results": [
            {
                **{
                    k: v for k, v in r.__dict__.items() if k not in ("max_abs_diff", "max_rel_diff")
                },
                "max_abs_diff": _num(r.max_abs_diff),
                "max_rel_diff": _num(r.max_rel_diff),
            }
            for r in report.results
        ],
    }
    jpath = out / "repro-report.json"
    jpath.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        f"# Reproducibility report{f' ({label})' if label else ''}",
        "",
        f"Result: **{'PASS' if report.ok else 'FAIL'}** -- each pipeline run twice per fixture, "
        "compared step by step (exact = byte-identical; abs/rel = declared tolerance).",
        "",
        f"Machine: {env['machine']}, Python {env['python']}, numpy {env['numpy']}, "
        f"scipy {env['scipy']}, MNE {env['mne']}, nf_steps {env['nf_steps']}.",
        "",
        "| Pipeline | Fixture | Step | Tolerance | Result | max abs diff | Detail |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in report.results:
        tol = r.tolerance["kind"] + (f" {r.tolerance['value']:g}" if "value" in r.tolerance else "")
        mad = "" if r.max_abs_diff is None else f"{r.max_abs_diff:.3g}"
        lines.append(
            f"| {r.pipeline} | {r.fixture} | {r.step} (`{r.ref}`) | {tol} | "
            f"{'pass' if r.ok else '**FAIL**'} | {mad} | {r.detail} |"
        )
    if report.errors:
        lines += ["", "## Errors", ""] + [f"- {e}" for e in report.errors]
    mpath = out / "repro-report.md"
    mpath.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return jpath, mpath


def compare_trees(a_root: str | Path, b_root: str | Path, specs: list[dict[str, Any]]) -> Report:
    """Cross-architecture check on two harness output trees (run "a" of each)."""
    report = Report()
    a_root, b_root = Path(a_root), Path(b_root)
    for spec in specs:
        ref = spec_ref(spec)
        calls = step_calls(spec)
        for fixture in sorted(
            p.name for p in (a_root / "outputs" / ref.replace("@", "_")).iterdir()
        ):
            all_exact = True
            for i, call in enumerate(calls, start=1):
                d = f"{i:02d}-{call.id}"
                pa = a_root / "outputs" / ref.replace("@", "_") / fixture / "a" / d
                pb = b_root / "outputs" / ref.replace("@", "_") / fixture / "a" / d
                if not (pa.is_dir() and pb.is_dir()):
                    report.errors.append(f"{ref}/{fixture}/{d}: missing on one architecture")
                    continue
                all_exact = all_exact and call.exact
                tol = call.tolerance if (not call.exact or all_exact) else CROSS_ARCH_FALLBACK
                ok, detail, mad, mrd = compare_step(pa, pb, tol)
                report.results.append(
                    StepResult(
                        ref,
                        fixture,
                        call.id,
                        call.step,
                        tol,
                        ok,
                        detail,
                        _hashes(pa),
                        _hashes(pb),
                        mad,
                        mrd,
                    )  # fmt: skip
                )
    return report


__all__ = [
    "CROSS_ARCH_FALLBACK",
    "InProcessRunner",
    "Report",
    "StepResult",
    "check",
    "compare_step",
    "compare_trees",
    "published_pipelines",
    "synth_fixtures",
    "write_report",
]
