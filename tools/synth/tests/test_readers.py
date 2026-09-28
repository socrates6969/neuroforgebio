"""CI-only: generated files open in MNE, pynwb and pyxdf (BUILD-GUIDE 0.6 acceptance test).
Each test is skipped when its reader is not installed (the dev PC does not install them: RAM).
CI installs them with `uv sync --locked --group readers`."""

from __future__ import annotations

import numpy as np
import pytest
from nf_synth import SynthParams, generate
from nf_synth.writers import write_bdf, write_brainvision, write_edf, write_nwb, write_xdf

P = SynthParams(seed=3)


@pytest.fixture(scope="module")
def synth():
    return generate(P)


@pytest.mark.parametrize("kind", ["edf", "bdf", "vhdr"])
def test_mne_opens(tmp_path, synth, kind):
    mne = pytest.importorskip("mne")
    data, truth = synth
    if kind == "edf":
        raw = mne.io.read_raw_edf(write_edf(tmp_path / "x.edf", data, truth), preload=True)
    elif kind == "bdf":
        raw = mne.io.read_raw_bdf(write_bdf(tmp_path / "x.bdf", data, truth), preload=True)
    else:
        raw = mne.io.read_raw_brainvision(
            write_brainvision(tmp_path / "x.vhdr", data, truth), preload=True
        )
    assert raw.ch_names[: len(truth["channels"])] == truth["channels"]
    assert raw.info["sfreq"] == truth["sfreq"]
    eeg = raw.get_data(picks=truth["channels"]) * 1e6  # volts -> uV
    tol = 0.05 if kind == "edf" else 1e-3
    assert np.allclose(eeg, data, atol=tol * np.abs(data).max())
    onsets = sorted(
        a["onset"]
        for a in raw.annotations
        if "stim" in a["description"] or "Stimulus" in a["description"]
    )
    assert onsets[:2] == pytest.approx(
        [e["onset_s"] for e in truth["events"][:2]], abs=1 / truth["sfreq"]
    )


def test_pynwb_opens(tmp_path, synth):
    pynwb = pytest.importorskip("pynwb")
    data, truth = synth
    path = write_nwb(tmp_path / "x.nwb", data, truth)
    with pynwb.NWBHDF5IO(str(path), "r") as io:
        nwb = io.read()
        es = nwb.acquisition["ElectricalSeries"]
        assert es.rate == truth["sfreq"]
        assert es.data.shape == (data.shape[1], data.shape[0])
        assert np.allclose(es.data[:100, 0], data[0, :100], atol=1e-3)


def test_pyxdf_opens(tmp_path, synth):
    pyxdf = pytest.importorskip("pyxdf")
    data, truth = synth
    streams, _ = pyxdf.load_xdf(str(write_xdf(tmp_path / "x.xdf", data, truth)))
    by_type = {s["info"]["type"][0]: s for s in streams}
    eeg = by_type["EEG"]
    assert eeg["time_series"].shape == (data.shape[1], data.shape[0])
    assert np.allclose(eeg["time_series"].T, data, atol=1e-3)
    assert [m[0] for m in by_type["Markers"]["time_series"][:2]] == ["stim/1", "stim/2"]
