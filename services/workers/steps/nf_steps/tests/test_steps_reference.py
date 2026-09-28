"""3.4 acceptance: each step's output equals the direct MNE call with the same parameters.

The direct calls below are written out independently of ``nf_steps.steps`` (same MNE functions, the
parameters taken from the step's resolved parameter set), and compared bit for bit: same machine,
same library versions, single-threaded BLAS (the parameters are the only thing that could differ).
"""

from __future__ import annotations

import mne
import numpy as np
import pytest
from nf_steps import Signal, get_step
from scipy import stats


def _raw(sig: Signal) -> mne.io.RawArray:
    info = mne.create_info(sig.ch_names, sig.sfreq, "eeg")
    raw = mne.io.RawArray(sig.data.copy(), info, verbose=False)
    raw.info["bads"] = list(sig.bads)
    return raw


def _run(ref: str, sig: Signal, params: dict, seed: int | None = None):
    out = get_step(ref)(sig, params, seed)
    return out, out.params


@pytest.mark.parametrize(
    "params",
    [
        {"l_freq": 1.0, "h_freq": 40.0},
        {"l_freq": 0.5, "h_freq": None, "fir_window": "hann", "phase": "minimum"},
        {"l_freq": 1.0, "h_freq": 30.0, "method": "iir", "iir_order": 4, "iir_ftype": "butter"},
    ],
)
def test_filter_equals_mne(synth, params):
    sig, _ = synth
    out, p = _run("nf_steps.filter@1", sig, params)
    iir = {"order": p["iir_order"], "ftype": p["iir_ftype"], "output": "sos"}
    ref = mne.filter.filter_data(
        sig.data.copy(),
        sig.sfreq,
        p["l_freq"],
        p["h_freq"],
        filter_length=p["filter_length"],
        l_trans_bandwidth=p["l_trans_bandwidth"],
        h_trans_bandwidth=p["h_trans_bandwidth"],
        method=p["method"],
        iir_params=iir if p["method"] == "iir" else None,
        phase=p["phase"],
        fir_window=p["fir_window"],
        fir_design=p["fir_design"],
        pad=p["pad"],
        verbose=False,
    )
    assert np.array_equal(out.signal.data, ref)
    assert out.signal.meta["highpass"] == p["l_freq"]


def test_notch_equals_mne(synth):
    sig, _ = synth
    out, p = _run("nf_steps.notch@1", sig, {"freqs": [50.0], "notch_widths": 2.0})
    ref = mne.filter.notch_filter(
        sig.data.copy(),
        sig.sfreq,
        np.array(p["freqs"]),
        filter_length=p["filter_length"],
        notch_widths=p["notch_widths"],
        trans_bandwidth=p["trans_bandwidth"],
        method=p["method"],
        phase=p["phase"],
        fir_window=p["fir_window"],
        fir_design=p["fir_design"],
        pad=p["pad"],
        verbose=False,
    )
    assert np.array_equal(out.signal.data, ref)


@pytest.mark.parametrize("ref_channels", ["average", ["Fp1"], ["P3", "P4"]])
def test_rereference_equals_mne(synth, ref_channels):
    sig, _ = synth
    sig = Signal(**{**sig.__dict__, "bads": ["C3"]})
    out, p = _run("nf_steps.rereference@1", sig, {"ref_channels": ref_channels})
    raw = _raw(sig)
    raw.set_eeg_reference(p["ref_channels"], projection=False, verbose=False)
    assert np.array_equal(out.signal.data, raw.get_data())
    if ref_channels == "average":  # the bad channel is excluded from the average
        good = [i for i, c in enumerate(sig.ch_names) if c != "C3"]
        assert np.allclose(out.signal.data[good].mean(axis=0), 0, atol=1e-9)


@pytest.mark.parametrize("method", ["fft", "polyphase"])
def test_resample_equals_mne(synth, method):
    sig, _ = synth
    out, p = _run("nf_steps.resample@1", sig, {"sfreq": 128.0, "method": method})
    raw = _raw(sig)
    ev = np.column_stack(
        [np.array(sig.events)[:, 0], np.zeros(len(sig.events), int), np.array(sig.events)[:, 1]]
    )
    raw, ev2 = raw.resample(
        p["sfreq"], npad=p["npad"], window=p["window"], pad=p["pad"], method=p["method"],
        events=ev, verbose=False,
    )  # fmt: skip
    assert np.array_equal(out.signal.data, raw.get_data())
    assert out.signal.sfreq == 128.0
    assert out.signal.events == [[int(s), int(c)] for s, _, c in ev2]


def test_ica_equals_mne(synth):
    sig, _ = synth
    filt = get_step("nf_steps.filter@1")(sig, {"l_freq": 1.0, "h_freq": 40.0}).signal
    out, p = _run("nf_steps.ica@1", filt, {"n_components": 5}, seed=42)
    raw = _raw(filt)
    with raw.info._unlock():
        raw.info["highpass"], raw.info["lowpass"] = 1.0, 40.0
    ica = mne.preprocessing.ICA(
        n_components=p["n_components"],
        method=p["method"],
        fit_params={"extended": p["extended"]},
        max_iter=p["max_iter"],
        rng=42,
        verbose=False,
    )
    ica.fit(raw, verbose=False)
    found, _ = ica.find_bads_eog(
        raw,
        ch_name=p["eog_channels"],
        threshold=p["eog_threshold"],
        measure=p["eog_measure"],
        l_freq=p["eog_l_freq"],
        h_freq=p["eog_h_freq"],
        verbose=False,
    )
    ica.apply(raw, exclude=sorted(int(i) for i in found), verbose=False)
    assert np.array_equal(out.signal.data, raw.get_data())
    assert out.info["exclude"] == sorted(int(i) for i in found)
    assert out.info["exclude"], "the synthetic blinks on Fp1/Fp2 should give one EOG component"


@pytest.mark.parametrize(
    "params",
    [
        {"event_codes": [1, 2], "tmin": -0.2, "tmax": 0.8},
        {"event_codes": [2], "tmin": 0.0, "tmax": 0.5, "baseline": None, "detrend": 1},
    ],
)
def test_epochs_equals_mne(synth, params):
    sig, _ = synth
    out, p = _run("nf_steps.epochs@1", sig, params)
    ev = np.array([[s, 0, c] for s, c in sig.events if c in p["event_codes"]])
    ep = mne.Epochs(
        _raw(sig),
        ev,
        event_id={str(c): c for c in sorted(set(ev[:, 2]))},
        tmin=p["tmin"],
        tmax=p["tmax"],
        baseline=None if p["baseline"] is None else tuple(p["baseline"]),
        picks="all",
        preload=True,
        reject=None,
        proj=False,
        decim=p["decim"],
        detrend=p["detrend"],
        reject_by_annotation=False,
        verbose=False,
    )
    assert np.array_equal(out.signal.data, ep.get_data())
    assert out.signal.meta["event_codes"] == ep.events[:, 2].tolist()


def test_fixed_length_epochs_equal_mne(synth):
    sig, _ = synth
    params = {"event_source": "fixed_length", "fixed_length_s": 2.0, "tmin": 0.0}
    out, p = _run("nf_steps.epochs@1", sig, {**params, "tmax": 1.99609375, "baseline": None})
    raw = _raw(sig)
    ev = mne.make_fixed_length_events(raw, id=1, duration=2.0)
    ep = mne.Epochs(raw, ev, {"1": 1}, 0.0, p["tmax"], baseline=None, picks="all", preload=True,
                    proj=False, reject_by_annotation=False, verbose=False)  # fmt: skip
    assert np.array_equal(out.signal.data, ep.get_data())
    assert out.signal.data.shape == (10, 8, 512)


def test_band_power_equals_welch_integration(synth):
    sig, _ = synth
    ep = get_step("nf_steps.epochs@1")(sig, {"event_codes": [1, 2], "tmax": 0.8}).signal
    out, p = _run("nf_steps.band_power@1", ep, {"n_per_seg": 128, "n_overlap": 64})
    psd, freqs = mne.time_frequency.psd_array_welch(
        ep.data, ep.sfreq, fmin=1.0, fmax=30.0, n_fft=p["n_fft"], n_overlap=p["n_overlap"],
        n_per_seg=p["n_per_seg"], window=p["window"], average=p["average"], verbose=False,
    )  # fmt: skip
    df = freqs[1] - freqs[0]
    expected = np.stack(
        [psd[..., (freqs >= lo) & (freqs < hi)].sum(-1) * df for _, lo, hi in p["bands"]], -1
    )
    assert np.array_equal(out.signal.data, expected)
    assert out.signal.meta["feature_names"] == ["delta", "theta", "alpha", "beta"]
    # ground truth: the injected 10 Hz alpha makes alpha the largest band on the posterior channels
    for ch in ("P3", "P4"):
        i = ep.ch_names.index(ch)
        mean = out.signal.data[:, i, :].mean(axis=0)
        assert int(np.argmax(mean[1:])) + 1 == 2, (ch, mean)


def test_bad_channels_independent_computation_and_ground_truth(synth):
    sig, truth = synth
    out, p = _run("nf_steps.bad_channels@1", sig, {})
    amp = stats.iqr(sig.data, axis=1) * 0.7413
    z = (amp - np.median(amp)) / stats.median_abs_deviation(amp, scale=1 / 1.4826)
    expected = [c for c, zi in zip(sig.ch_names, z, strict=True) if zi > p["z_threshold"]]
    assert out.signal.bads == expected == [b["name"] for b in truth["bad_channels"]]
    assert np.array_equal(out.signal.data, sig.data)  # detection never changes the data
    for c, zi in zip(sig.ch_names, z, strict=True):
        assert out.info["robust_z"][c] == pytest.approx(zi, abs=1e-5)


def test_bad_channels_flags_a_flat_channel(synth):
    sig, _ = synth
    data = sig.data.copy()
    data[3] = 0.0
    flat = Signal(**{**sig.__dict__, "data": data})
    out = get_step("nf_steps.bad_channels@1")(flat, {})
    assert set(out.signal.bads) == {"F4", "C3"}
