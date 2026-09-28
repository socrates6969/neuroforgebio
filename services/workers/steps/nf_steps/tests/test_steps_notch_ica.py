"""3.4 acceptance on synthetic ground truth (tools/synth):

- notch removes the injected line-noise peak by at least the attenuation that the filter DESIGN
  gives at the line frequency (computed in the test from the FIR taps MNE builds for these
  parameters), minus a stated allowance for edge effects -- a derived threshold, not a benchmark;
- seeded ICA is stable across two runs (bit-identical), in-process and in two fresh processes.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import mne
import numpy as np
import pytest
from nf_steps import get_step, signal
from nf_steps_fixtures import synth_signal

EDGE_ALLOWANCE_DB = 3.0  # padding/edge effects over a 20 s record; the design value is the target


def line_amplitude(x: np.ndarray, sfreq: float, f: float) -> np.ndarray:
    """Per-channel amplitude of the f-Hz component: Hann-windowed DFT at exactly f. The Hann window
    keeps broadband noise from outside the notch (sidelobe leakage) and the filter's edge transients
    out of the estimate; an unwindowed projection measures the leakage floor, not the notch."""
    n = x.shape[-1]
    w = np.hanning(n)
    z = (x * w) @ np.exp(-2j * np.pi * f * np.arange(n) / sfreq)
    return np.abs(z) * 2 / w.sum()


def design_attenuation_db(sfreq: float, p: dict, f: float) -> float:
    """-20 log10 |H(f)| of the band-stop filter that ``notch_filter`` builds for these parameters
    (MNE: stop band f +- (width + trans)/2, transition = trans/2 on each side)."""
    tb2 = p["trans_bandwidth"] / 2
    lo = f - p["notch_widths"] / 2 - tb2
    hi = f + p["notch_widths"] / 2 + tb2
    h = mne.filter.create_filter(
        None, sfreq, l_freq=hi, h_freq=lo, filter_length=p["filter_length"],
        l_trans_bandwidth=tb2, h_trans_bandwidth=tb2, method="fir", phase=p["phase"],
        fir_window=p["fir_window"], fir_design=p["fir_design"], verbose=False,
    )  # fmt: skip
    n = np.arange(len(h))
    resp = abs(np.sum(h * np.exp(-2j * np.pi * f / sfreq * n)))
    return float(-20 * np.log10(resp))


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_notch_removes_line_noise_by_the_design_attenuation(seed):
    sig, truth = synth_signal(seed)
    f = float(truth["line_noise"]["freq_hz"])
    st = get_step("nf_steps.notch@1")
    params = st.resolve({"freqs": [f]})
    design_db = design_attenuation_db(sig.sfreq, params, f)
    assert design_db > 20, "the design itself must be a real notch for this test to mean anything"
    before = line_amplitude(sig.data, sig.sfreq, f)
    # ground truth: the injected line amplitude is present before filtering (common mode on every
    # channel; the noisy channel C3 carries it too)
    assert np.all(before > 0.5 * truth["line_noise"]["amp_uv"])
    after = line_amplitude(st(sig, params).signal.data, sig.sfreq, f)
    measured_db = 20 * np.log10(before / after)
    assert np.all(measured_db >= design_db - EDGE_ALLOWANCE_DB), (design_db, measured_db)
    # and the neighbouring alpha peak (10 Hz) is untouched
    a0 = line_amplitude(sig.data, sig.sfreq, truth["alpha"]["freq_hz"])
    a1 = line_amplitude(st(sig, params).signal.data, sig.sfreq, truth["alpha"]["freq_hz"])
    assert np.allclose(a0, a1, rtol=1e-3)


def _ica_input(synth):
    sig, _ = synth
    return get_step("nf_steps.filter@1")(sig, {"l_freq": 1.0, "h_freq": 40.0}).signal


def test_seeded_ica_is_stable_across_two_runs(synth):
    x = _ica_input(synth)
    st = get_step("nf_steps.ica@1")
    a = st(x, {"n_components": 5}, 42)
    b = st(x, {"n_components": 5}, 42)
    assert signal.to_files(a.signal) == signal.to_files(b.signal)
    assert a.info == b.info


def test_seeded_ica_is_stable_across_two_processes(synth, tmp_path):
    x = _ica_input(synth)
    signal.write(x, tmp_path / "in")
    (tmp_path / "p.json").write_text('{"n_components": 5}')
    root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(root), "OMP_NUM_THREADS": "1"}
    outs = []
    for i in range(2):
        out = tmp_path / f"out{i}"
        cmd = [sys.executable, "-m", "nf_steps", "run", "--step", "nf_steps.ica@1"]
        cmd += ["--params", str(tmp_path / "p.json"), "--seed", "42"]
        cmd += ["--in", str(tmp_path / "in"), "--out", str(out)]
        subprocess.run(cmd, check=True, env=env, timeout=300)
        outs.append({n: (out / n).read_bytes() for n in (signal.DATA_FILE, signal.META_FILE)})
    assert outs[0] == outs[1]
