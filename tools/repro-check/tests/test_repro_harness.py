"""3.5 acceptance: the harness FAILS on a deliberately non-deterministic step (an unseeded random
call) and PASSES on the v1 step library (locally, x86-64; the arm64 leg is the CI matrix)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pytest
from nf_repro import harness
from nf_repro.__main__ import main as repro_main
from nf_runner.steprunner import SubprocessRunner
from nf_steps import Signal, get_step, signal
from nf_steps.pipelines import ENTRYPOINT, PLACEHOLDER_IMAGE

HERE = Path(__file__).resolve().parent
BAD = "nf_repro_badsteps"


def _step(name, ref, params=None, tolerance=None):
    st = get_step(ref, (BAD,))
    return {
        "name": name,
        "step": ref,
        "image": PLACEHOLDER_IMAGE,
        "entrypoint": list(ENTRYPOINT),
        "params": st.resolve(params or {}),
        "tolerance": tolerance or st.tolerance_doc(),
    }


def _doc(name, steps):
    return {
        "schema": "nf.pipeline-version/v1",
        "meta": {"name": name, "version": "0.0.1"},
        "steps": steps,
        "seed": 1,
    }


NONDETERMINISTIC = _doc(
    "nondeterministic",
    [
        _step("bandpass", "nf_steps.filter@1", {"l_freq": 1.0, "h_freq": 40.0}),
        _step("noise", f"{BAD}.noise@1"),
    ],
)


def test_harness_fails_on_an_unseeded_random_step(tmp_path):
    runner = SubprocessRunner(extra_paths=(str(HERE),), extra_libraries=(BAD,))
    fixtures = harness.synth_fixtures([1])
    rep = harness.check(
        [NONDETERMINISTIC], fixtures, tmp_path, runner=runner, extra_libraries=(BAD,)
    )
    assert not rep.ok
    by_step = {r.step: r for r in rep.results}
    assert by_step["bandpass"].ok and by_step["bandpass"].detail.endswith("(byte-identical)")
    assert not by_step["noise"].ok and by_step["noise"].detail.startswith("not byte-identical")
    # declaring a tolerance does not hide it either: the noise is far above 1e-9 relative
    loose = _doc(
        "nondeterministic-rel",
        [_step("noise", f"{BAD}.noise@1", tolerance={"kind": "rel", "value": 1e-9})],
    )
    rep2 = harness.check([loose], fixtures, tmp_path / "rel", runner=runner, extra_libraries=(BAD,))
    assert not rep2.ok and "exceeds rel" in rep2.results[0].detail


def test_cli_exit_code_and_report_on_failure(tmp_path):
    spec = tmp_path / "bad.json"
    spec.write_text(json.dumps(NONDETERMINISTIC), encoding="utf-8")
    out = tmp_path / "report"
    code = repro_main(
        ["check", "--out", str(out), "--pipeline", str(spec), "--only-extra",
         "--runner", "inprocess", "--extra-library", BAD, "--extra-path", str(HERE)]
    )  # fmt: skip
    assert code == 1
    body = json.loads((out / "repro-report.json").read_text(encoding="utf-8"))
    assert body["ok"] is False and body["schema"] == harness.REPORT_SCHEMA
    assert "**FAIL**" in (out / "repro-report.md").read_text(encoding="utf-8")


def test_harness_passes_on_the_v1_library(tmp_path):
    """Every published v1 pipeline, run twice (fresh pinned processes per step), reproduces:
    exact steps byte-identical, tolerance steps within their declared tolerance."""
    out = tmp_path / "v1"
    assert repro_main(["check", "--out", str(out), "--label", "local"]) == 0
    body = json.loads((out / "repro-report.json").read_text(encoding="utf-8"))
    names = {r["pipeline"] for r in body["results"]}
    assert names == {"eeg-basic@1.0.0", "eeg-resample-features@1.0.0"}
    assert len(body["results"]) == 11 and all(r["ok"] for r in body["results"])
    assert body["environment"]["threads"]["OMP_NUM_THREADS"] == "1"
    assert (out / "repro-report.md").read_text(encoding="utf-8").count("| pass |") == 11
    # the same tree against itself passes the cross-architecture comparison too
    xa = harness.compare_trees(out, out, harness.published_pipelines())
    assert xa.ok and len(xa.results) == 11


def _sig(data) -> Signal:
    return Signal("raw", data, 100.0, ["a", "b"], ["eeg", "eeg"])


def test_compare_step_tolerance_semantics(tmp_path):
    base = np.arange(20, dtype=float).reshape(2, 10) + 1.0
    signal.write(_sig(base), tmp_path / "a")
    signal.write(_sig(base + 1e-12), tmp_path / "b")
    signal.write(_sig(base + 1e-3), tmp_path / "c")
    exact, rel, abs_ = (
        {"kind": "exact"},
        {"kind": "rel", "value": 1e-9},
        {"kind": "abs", "value": 1e-2},
    )
    assert harness.compare_step(tmp_path / "a", tmp_path / "a", exact)[0]
    assert not harness.compare_step(tmp_path / "a", tmp_path / "b", exact)[0]
    assert harness.compare_step(tmp_path / "a", tmp_path / "b", rel)[0]
    assert not harness.compare_step(tmp_path / "a", tmp_path / "c", rel)[0]
    assert harness.compare_step(tmp_path / "a", tmp_path / "c", abs_)[0]
    other = Signal("raw", base, 100.0, ["a", "x"], ["eeg", "eeg"])
    signal.write(other, tmp_path / "d")
    ok, detail, *_ = harness.compare_step(tmp_path / "a", tmp_path / "d", abs_)
    assert not ok and detail == "metadata differs"


def test_cross_architecture_comparison_uses_tolerance_after_float_steps(tmp_path):
    """Simulate the arm64 leg: perturb a float step's output slightly (pass) or grossly (fail)."""
    spec = harness.published_pipelines()[1]  # eeg-resample-features: float steps, then exact
    a = tmp_path / "x86"
    rep = harness.check([spec], harness.synth_fixtures([1]), a,
                        runner=harness.InProcessRunner())  # fmt: skip
    assert rep.ok
    b = tmp_path / "arm"
    shutil.copytree(a, b)
    step_dir = next((b / "outputs").glob("*/*/a/02-resample"))
    sig = signal.read(step_dir)
    sig.data = sig.data * (1 + 1e-10)
    signal.write(sig, step_dir)
    assert harness.compare_trees(a, b, [spec]).ok
    sig.data = sig.data * 1.01
    signal.write(sig, step_dir)
    bad = harness.compare_trees(a, b, [spec])
    assert not bad.ok and [r.step for r in bad.results if not r.ok] == ["resample"]


@pytest.mark.parametrize("pipeline", ["eeg-basic", "eeg-resample-features"])
def test_published_pipelines_declare_tolerances(pipeline):
    from nf_steps import pipelines

    doc = pipelines.load(pipeline)
    assert all(s["tolerance"]["kind"] in ("exact", "abs", "rel") for s in doc["steps"])
