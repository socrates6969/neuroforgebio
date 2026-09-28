"""3.4: every parameter explicit, every default written to the record; library hygiene."""

from __future__ import annotations

import json

import pytest
from nf_steps import LIBRARY, StepError, get_step, pipelines, signal
from nf_steps.__main__ import main as step_main
from nf_steps.pipeline import StepLibraryCatalog, run_chain, spec_ref, spec_seed, step_calls

EXPECTED_STEPS = {
    "nf_steps.filter@1",
    "nf_steps.notch@1",
    "nf_steps.rereference@1",
    "nf_steps.resample@1",
    "nf_steps.bad_channels@1",
    "nf_steps.ica@1",
    "nf_steps.epochs@1",
    "nf_steps.band_power@1",
    # m3-sweeps (3.6): decoding metric for sweep reports (tests: services/platform/tests/sweeps)
    "nf_steps.decode_lda@1",
}


def test_library_has_the_v1_steps():
    assert set(LIBRARY.steps) == EXPECTED_STEPS


@pytest.mark.parametrize("ref", sorted(EXPECTED_STEPS))
def test_every_field_has_an_explicit_default_and_resolves_completely(ref):
    st = get_step(ref)
    fields = st.params_model.model_fields
    assert all(not f.is_required() for f in fields.values()), f"{ref}: a field without default"
    resolved = st.resolve({})
    assert set(resolved) == set(fields)
    json.dumps(resolved, allow_nan=False)  # the run record is JSON
    assert st.resolve(resolved) == resolved  # resolution is idempotent


@pytest.mark.parametrize("ref", sorted(EXPECTED_STEPS))
def test_unknown_parameters_are_rejected(ref):
    with pytest.raises(StepError, match="invalid parameters"):
        get_step(ref).resolve({"no_such_param": 1})


def test_step_refs_are_allow_listed():
    for bad in ("os.system@1", "subprocess.run@1", "nf_steps.filter", "nf_steps.nope@1"):
        with pytest.raises(StepError):
            get_step(bad)


def test_ica_refuses_to_run_without_a_seed(synth):
    sig, _ = synth
    with pytest.raises(StepError, match="seed"):
        get_step("nf_steps.ica@1")(sig, {}, None)


def test_bundled_pipelines_are_fully_resolved_and_run(synth):
    sig, _ = synth
    specs = pipelines.all_specs()
    assert {s["meta"]["name"] for s in specs} == {"eeg-basic", "eeg-resample-features"}
    for spec in specs:
        assert spec["schema"] == "nf.pipeline-version/v1"
        calls = step_calls(spec)
        for raw_step, call in zip(spec["steps"], calls, strict=True):
            assert raw_step["params"] == call.params, f"{spec_ref(spec)}/{call.id} not resolved"
            assert raw_step["image"] == pipelines.PLACEHOLDER_IMAGE
        results = run_chain(calls, sig, spec_seed(spec))
        assert results[-1][1].signal.kind == "features"


def test_bundled_pipelines_are_valid_pipeline_versions():
    """The documents pass the platform's PipelineVersion validation, and publishing with this
    library as the StepCatalog changes nothing (every default is already explicit)."""
    from nf_platform.pipelines.spec import fill_defaults, parse_spec  # noqa: PLC0415

    for doc in pipelines.all_specs():
        spec = parse_spec(doc)
        assert fill_defaults(spec, StepLibraryCatalog()) == spec
    assert StepLibraryCatalog().defaults("nf_steps.nope@1") is None


def test_cli_writes_outputs_and_record(synth, tmp_path):
    sig, _ = synth
    signal.write(sig, tmp_path / "in")
    (tmp_path / "p.json").write_text(json.dumps({"l_freq": 1.0, "h_freq": 30.0}))
    args = ["run", "--step", "nf_steps.filter@1", "--params", str(tmp_path / "p.json")]
    args += ["--in", str(tmp_path / "in"), "--out", str(tmp_path / "out")]
    assert step_main(args) == 0
    rec = json.loads((tmp_path / "out" / "step.json").read_text())
    assert rec["params"] == get_step("nf_steps.filter@1").resolve({"l_freq": 1.0, "h_freq": 30.0})
    assert rec["environment"]["mne"] and "OMP_NUM_THREADS" in rec["environment"]["threads"]
    out = signal.read(tmp_path / "out")
    assert out.data.shape == sig.data.shape
    # a parameter error exits 2 (not retryable) and writes nothing
    (tmp_path / "bad.json").write_text(json.dumps({"l_freq": "x"}))
    args[4] = str(tmp_path / "bad.json")
    args[-1] = str(tmp_path / "out2")
    assert step_main(args) == 2
    assert not (tmp_path / "out2").exists()


def test_signal_files_are_byte_deterministic(synth):
    sig, _ = synth
    a = signal.to_files(sig)
    b = signal.to_files(signal.from_files(a))
    assert a == b
