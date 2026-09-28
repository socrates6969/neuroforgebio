"""Step library v1 (BUILD-GUIDE 3.4): thin wrappers around MNE-Python with every parameter explicit.

Each step maps its parameter model 1:1 onto one documented MNE call; the reference tests
(``tests/test_steps_reference.py``) compare every step with the direct MNE call on the same data.
Bad-channel detection has no sklearn-free MNE equivalent for EEG, so it is a small NumPy
implementation of the PREP "deviation" criterion (Bigdely-Shamlo et al. 2015), tested against an
independent computation and the synthetic ground truth.

Data stay in the recording's units (e.g. microvolts); every operation here is either linear or
scale-invariant, so no unit conversion happens inside a step.
"""

from __future__ import annotations

from typing import Any, Literal

import mne
import numpy as np
from pydantic import Field

from nf_steps.base import Library, Params, StepError
from nf_steps.signal import Signal

LIBRARY = Library("nf_steps")
_MNE_TYPES = {"eeg", "eog", "emg", "ecg", "seeg", "ecog", "dbs", "misc", "stim", "resp", "bio"}


def _mne_type(t: str) -> str:
    t = str(t).lower()
    return t if t in _MNE_TYPES else "misc"


def to_raw(sig: Signal) -> mne.io.RawArray:
    """The signal as an MNE RawArray (no copy semantics relied upon; data are float64)."""
    info = mne.create_info(
        list(sig.ch_names), float(sig.sfreq), [_mne_type(t) for t in sig.ch_types]
    )
    raw = mne.io.RawArray(sig.data.copy(), info, first_samp=0, verbose=False)
    raw.info["bads"] = list(sig.bads)
    # Filter history travels in the signal metadata (MNE checks it, e.g. ICA wants a high-pass).
    with raw.info._unlock():
        if sig.meta.get("highpass") is not None:
            raw.info["highpass"] = float(sig.meta["highpass"])
        if sig.meta.get("lowpass") is not None:
            raw.info["lowpass"] = min(float(sig.meta["lowpass"]), sig.sfreq / 2)
    return raw


def _events_array(sig: Signal) -> np.ndarray:
    if not sig.events:
        return np.zeros((0, 3), dtype=np.int64)
    ev = np.asarray(sig.events, dtype=np.int64)
    return np.column_stack([ev[:, 0], np.zeros(len(ev), dtype=np.int64), ev[:, 1]])


def _like(sig: Signal, data: np.ndarray, **kw: Any) -> Signal:
    fields = {
        "kind": sig.kind,
        "data": data,
        "sfreq": sig.sfreq,
        "ch_names": list(sig.ch_names),
        "ch_types": list(sig.ch_types),
        "bads": list(sig.bads),
        "events": [list(e) for e in sig.events],
        "meta": dict(sig.meta),
    }
    fields.update(kw)
    return Signal(**fields)


# ---------------------------------------------------------------- filter (FIR / IIR)
Phase = Literal["zero", "zero-double", "minimum", "minimum-half", "forward"]
FirWindow = Literal["hamming", "hann", "blackman"]


class FilterParams(Params):
    l_freq: float | None = Field(default=1.0, description="high-pass edge [Hz]; null = none")
    h_freq: float | None = Field(default=40.0, description="low-pass edge [Hz]; null = none")
    method: Literal["fir", "iir"] = "fir"
    filter_length: str | int = "auto"
    l_trans_bandwidth: float | Literal["auto"] = "auto"
    h_trans_bandwidth: float | Literal["auto"] = "auto"
    phase: Phase = "zero"
    fir_window: FirWindow = "hamming"
    fir_design: Literal["firwin", "firwin2"] = "firwin"
    pad: str = "reflect_limited"
    iir_order: int = Field(default=4, ge=1, le=16)
    iir_ftype: Literal["butter", "cheby1", "cheby2", "ellip", "bessel"] = "butter"


def iir_params(p: Any) -> dict[str, Any] | None:
    if p.method != "iir":
        return None
    return {"order": p.iir_order, "ftype": p.iir_ftype, "output": "sos"}


@LIBRARY.step("filter", "1", FilterParams, ("raw",))
def filter_step(sig: Signal, p: FilterParams, _seed: int | None):
    """Band-/high-/low-pass filter: ``mne.filter.filter_data`` on every channel."""
    if p.l_freq is None and p.h_freq is None:
        raise StepError("filter needs l_freq and/or h_freq")
    out = mne.filter.filter_data(
        sig.data,
        sig.sfreq,
        p.l_freq,
        p.h_freq,
        picks=None,
        filter_length=p.filter_length,
        l_trans_bandwidth=p.l_trans_bandwidth,
        h_trans_bandwidth=p.h_trans_bandwidth,
        n_jobs=None,
        method=p.method,
        iir_params=iir_params(p),
        copy=True,
        phase=p.phase,
        fir_window=p.fir_window,
        fir_design=p.fir_design,
        pad=p.pad,
        verbose=False,
    )
    meta = dict(sig.meta)
    if p.l_freq is not None:
        meta["highpass"] = max(float(p.l_freq), float(meta.get("highpass") or 0.0))
    if p.h_freq is not None:
        old = meta.get("lowpass")
        meta["lowpass"] = float(p.h_freq) if old is None else min(float(p.h_freq), float(old))
    return _like(sig, out, meta=meta), {}


# ---------------------------------------------------------------- notch
class NotchParams(Params):
    freqs: list[float] = Field(default=[50.0], min_length=1, description="line frequencies [Hz]")
    notch_widths: float = Field(default=1.0, gt=0, description="stop-band width [Hz]")
    trans_bandwidth: float = Field(default=1.0, gt=0)
    method: Literal["fir", "iir"] = "fir"
    filter_length: str | int = "auto"
    phase: Phase = "zero"
    fir_window: FirWindow = "hamming"
    fir_design: Literal["firwin", "firwin2"] = "firwin"
    pad: str = "reflect_limited"
    iir_order: int = Field(default=4, ge=1, le=16)
    iir_ftype: Literal["butter", "cheby1", "cheby2", "ellip", "bessel"] = "butter"


@LIBRARY.step("notch", "1", NotchParams, ("raw",))
def notch_step(sig: Signal, p: NotchParams, _seed: int | None):
    """Line-noise notch: ``mne.filter.notch_filter`` on every channel."""
    out = mne.filter.notch_filter(
        sig.data,
        sig.sfreq,
        np.asarray(p.freqs, dtype=float),
        filter_length=p.filter_length,
        notch_widths=p.notch_widths,
        trans_bandwidth=p.trans_bandwidth,
        method=p.method,
        iir_params=iir_params(p),
        picks=None,
        n_jobs=None,
        copy=True,
        phase=p.phase,
        fir_window=p.fir_window,
        fir_design=p.fir_design,
        pad=p.pad,
        verbose=False,
    )
    return _like(sig, out), {}


# ---------------------------------------------------------------- re-reference
class RereferenceParams(Params):
    ref_channels: Literal["average"] | list[str] = "average"


@LIBRARY.step("rereference", "1", RereferenceParams, ("raw",))
def rereference_step(sig: Signal, p: RereferenceParams, _seed: int | None):
    """EEG re-reference: ``Raw.set_eeg_reference(ref_channels, projection=False, ch_type="eeg")``.
    Bad channels are excluded from an average reference (MNE behaviour); other types unchanged."""
    if "eeg" not in {_mne_type(t) for t in sig.ch_types}:
        raise StepError("rereference needs EEG channels")
    raw = to_raw(sig)
    raw.set_eeg_reference(p.ref_channels, projection=False, ch_type="eeg", verbose=False)
    return _like(sig, raw.get_data()), {}


# ---------------------------------------------------------------- resample
class ResampleParams(Params):
    sfreq: float = Field(default=128.0, gt=0, description="new sampling rate [Hz]")
    npad: int | Literal["auto"] = "auto"
    window: str = "auto"
    method: Literal["fft", "polyphase"] = "fft"
    pad: str = "auto"


@LIBRARY.step("resample", "1", ResampleParams, ("raw",))
def resample_step(sig: Signal, p: ResampleParams, _seed: int | None):
    """Resample: ``Raw.resample(sfreq, npad, window, events, pad, method)``; events follow."""
    raw = to_raw(sig)
    ev = _events_array(sig)
    kw: dict[str, Any] = {"npad": p.npad, "window": p.window, "pad": p.pad, "method": p.method}
    if len(ev):
        raw, ev = raw.resample(p.sfreq, events=ev, verbose=False, **kw)
    else:
        raw = raw.resample(p.sfreq, verbose=False, **kw)
    events = [[int(s), int(c)] for s, _, c in ev]
    meta = dict(sig.meta)
    meta["lowpass"] = float(raw.info["lowpass"])
    return (
        _like(sig, raw.get_data(), sfreq=float(raw.info["sfreq"]), events=events, meta=meta),
        {},
    )


# ---------------------------------------------------------------- bad-channel detection
class BadChannelParams(Params):
    method: Literal["robust_deviation"] = "robust_deviation"
    z_threshold: float = Field(default=5.0, gt=0, description="robust z of channel amplitude")
    flat_threshold: float = Field(default=1e-9, ge=0, description="robust amplitude below = flat")
    ch_types: list[str] = Field(default=["eeg"], min_length=1)


def robust_amplitude(data: np.ndarray) -> np.ndarray:
    """0.7413 x IQR per channel: a robust standard deviation (PREP deviation criterion)."""
    q75, q25 = np.percentile(data, [75, 25], axis=-1)
    return 0.7413 * (q75 - q25)


@LIBRARY.step("bad_channels", "1", BadChannelParams, ("raw",), tolerance="exact")
def bad_channels_step(sig: Signal, p: BadChannelParams, _seed: int | None):
    """Mark channels whose robust amplitude deviates (robust z > threshold) or is flat. Data
    unchanged; ``bads`` = previous bads + detected."""
    types = {t.lower() for t in p.ch_types}
    idx = [i for i, t in enumerate(sig.ch_types) if str(t).lower() in types]
    if len(idx) < 3:
        raise StepError("bad-channel detection needs at least 3 channels of the chosen types")
    amp = robust_amplitude(sig.data[idx])
    med = float(np.median(amp))
    mad = float(np.median(np.abs(amp - med))) * 1.4826
    z = (amp - med) / mad if mad > 0 else np.zeros_like(amp)
    detected = [
        sig.ch_names[i]
        for i, a, zi in zip(idx, amp, z, strict=True)
        if zi > p.z_threshold or a < p.flat_threshold
    ]
    bads = sorted(set(sig.bads) | set(detected), key=sig.ch_names.index)
    info = {
        "detected": detected,
        "robust_z": {sig.ch_names[i]: round(float(zi), 6) for i, zi in zip(idx, z, strict=True)},
    }
    return _like(sig, sig.data, bads=bads), info


# ---------------------------------------------------------------- ICA (seeded)
class IcaParams(Params):
    n_components: int | float = Field(default=0.99, description="int = count, float = variance")
    method: Literal["infomax", "picard", "fastica"] = "infomax"
    extended: bool = True
    max_iter: int = Field(default=500, ge=1)
    eog_channels: list[str] = Field(default=["Fp1", "Fp2"])
    eog_measure: Literal["correlation", "zscore"] = "correlation"
    eog_threshold: float = Field(default=0.5, gt=0, description="|r| or z, per eog_measure")
    eog_l_freq: float = 1.0
    eog_h_freq: float = 10.0
    exclude: list[int] = Field(default=[], description="components removed in addition")


def make_ica(p: IcaParams, seed: int) -> mne.preprocessing.ICA:
    fit_params = {"extended": p.extended} if p.method in ("infomax", "picard") else None
    return mne.preprocessing.ICA(
        n_components=p.n_components,
        method=p.method,
        fit_params=fit_params,
        max_iter=p.max_iter,
        rng=seed,
        verbose=False,
    )


@LIBRARY.step("ica", "1", IcaParams, ("raw",), tolerance_value=1e-6, needs_seed=True)
def ica_step(sig: Signal, p: IcaParams, seed: int | None):
    """ICA artifact removal: ``ICA(..., rng=seed).fit(raw)``; EOG-like components found with
    ``find_bads_eog`` on the listed frontal channels (blink proxies), plus ``exclude``; then
    ``ica.apply``. The seed is the run's seed (recorded). With only a few components a z-score can
    never pass 3 (max z of n values is (n-1)/sqrt(n)), hence the correlation measure by default."""
    raw = to_raw(sig)
    ica = make_ica(p, int(seed))  # type: ignore[arg-type] - needs_seed guarantees an int
    ica.fit(raw, verbose=False)
    eog = [c for c in p.eog_channels if c in sig.ch_names and c not in sig.bads]
    found: list[int] = []
    if eog:
        found, _ = ica.find_bads_eog(
            raw,
            ch_name=eog,
            threshold=p.eog_threshold,
            measure=p.eog_measure,
            l_freq=p.eog_l_freq,
            h_freq=p.eog_h_freq,
            verbose=False,
        )
    exclude = sorted({int(i) for i in found} | {int(i) for i in p.exclude})
    ica.apply(raw, exclude=exclude, verbose=False)
    info = {"n_components": int(ica.n_components_), "n_iter": int(ica.n_iter_), "exclude": exclude}
    return _like(sig, raw.get_data()), info


# ---------------------------------------------------------------- epoching
class EpochsParams(Params):
    event_source: Literal["events", "fixed_length"] = "events"
    event_codes: list[int] = Field(default=[], description="[] = every code present")
    fixed_length_s: float = Field(default=2.0, gt=0)
    tmin: float = -0.2
    tmax: float = 0.8
    baseline: tuple[float | None, float | None] | None = (None, 0.0)
    detrend: Literal[0, 1] | None = None
    decim: int = Field(default=1, ge=1)


@LIBRARY.step("epochs", "1", EpochsParams, ("raw",))
def epochs_step(sig: Signal, p: EpochsParams, _seed: int | None):
    """Epoching: ``mne.Epochs(raw, events, event_id, tmin, tmax, baseline, picks="all",
    preload=True, reject=None, proj=False, decim, detrend, reject_by_annotation=False)``."""
    raw = to_raw(sig)
    if p.event_source == "fixed_length":
        events = mne.make_fixed_length_events(raw, id=1, duration=p.fixed_length_s)
    else:
        events = _events_array(sig)
    if p.event_codes:
        events = events[np.isin(events[:, 2], p.event_codes)]
    if not len(events):
        raise StepError("no events to epoch")
    event_id = {str(c): int(c) for c in sorted({int(c) for c in events[:, 2]})}
    ep = mne.Epochs(
        raw,
        events,
        event_id=event_id,
        tmin=p.tmin,
        tmax=p.tmax,
        baseline=p.baseline,
        picks="all",
        preload=True,
        reject=None,
        flat=None,
        proj=False,
        decim=p.decim,
        detrend=p.detrend,
        reject_by_annotation=False,
        on_missing="raise",
        verbose=False,
    )
    meta = {
        **sig.meta,
        "tmin": float(ep.tmin),
        "event_codes": [int(c) for c in ep.events[:, 2]],
        "event_samples": [int(s) for s in ep.events[:, 0]],
    }
    out = Signal(
        kind="epochs",
        data=ep.get_data(),
        sfreq=float(ep.info["sfreq"]),
        ch_names=list(ep.ch_names),
        ch_types=list(sig.ch_types),
        bads=list(sig.bads),
        meta=meta,
    )
    return out, {"n_epochs": len(ep), "dropped": len(events) - len(ep)}


# ---------------------------------------------------------------- band-power features
DEFAULT_BANDS = [
    ("delta", 1.0, 4.0),
    ("theta", 4.0, 8.0),
    ("alpha", 8.0, 13.0),
    ("beta", 13.0, 30.0),
]


class BandPowerParams(Params):
    bands: list[tuple[str, float, float]] = Field(default=DEFAULT_BANDS, min_length=1)
    n_fft: int = Field(default=256, ge=8)
    n_overlap: int = Field(default=128, ge=0)
    n_per_seg: int = Field(default=256, ge=8)
    window: str = "hamming"
    average: Literal["mean", "median"] = "mean"
    remove_dc: bool = True
    relative: bool = False


def band_power(psds: np.ndarray, freqs: np.ndarray, p: BandPowerParams) -> np.ndarray:
    """Integrate the PSD over each band [lo, hi) (sum x frequency resolution)."""
    df = float(freqs[1] - freqs[0]) if len(freqs) > 1 else 1.0
    cols = []
    for _, lo, hi in p.bands:
        mask = (freqs >= lo) & (freqs < hi)
        cols.append(psds[..., mask].sum(axis=-1) * df)
    out = np.stack(cols, axis=-1)
    if p.relative:
        lo = min(b[1] for b in p.bands)
        hi = max(b[2] for b in p.bands)
        total = psds[..., (freqs >= lo) & (freqs < hi)].sum(axis=-1) * df
        out = out / total[..., None]
    return out


@LIBRARY.step("band_power", "1", BandPowerParams, ("raw", "epochs"))
def band_power_step(sig: Signal, p: BandPowerParams, _seed: int | None):
    """Band power per epoch and channel: ``mne.time_frequency.psd_array_welch`` then integration
    over each band. Raw input counts as one epoch."""
    x = sig.data[None] if sig.kind == "raw" else sig.data
    if p.n_per_seg > x.shape[-1]:
        raise StepError("n_per_seg is longer than the epochs")
    for name, lo, hi in p.bands:
        if not 0 <= lo < hi <= sig.sfreq / 2:
            raise StepError(f"band {name!r} outside 0..Nyquist")
    psds, freqs = mne.time_frequency.psd_array_welch(
        x,
        sig.sfreq,
        fmin=min(b[1] for b in p.bands),
        fmax=max(b[2] for b in p.bands),
        n_fft=p.n_fft,
        n_overlap=p.n_overlap,
        n_per_seg=p.n_per_seg,
        n_jobs=None,
        average=p.average,
        window=p.window,
        remove_dc=p.remove_dc,
        output="power",
        verbose=False,
    )
    feats = band_power(psds, freqs, p)
    meta = {**sig.meta, "feature_names": [b[0] for b in p.bands], "relative": p.relative}
    out = Signal(
        kind="features",
        data=feats,
        sfreq=sig.sfreq,
        ch_names=list(sig.ch_names),
        ch_types=list(sig.ch_types),
        bads=list(sig.bads),
        meta=meta,
    )
    return out, {"n_freqs": len(freqs)}
