"""MNE-Python interop (``pip install neuroforge[mne]``). Signal processing stays in MNE
(BLUEPRINT §5: the SDK core does not reimplement it)."""

from __future__ import annotations

import os
from typing import Any

import numpy as np

__all__ = ["raw_from_window", "read_raw", "to_signal"]

_TO_VOLTS = {"V": 1.0, "mV": 1e-3, "uV": 1e-6, "µV": 1e-6, "μV": 1e-6, "nV": 1e-9}
_MNE_TYPES = {
    "EEG": "eeg",
    "MEG": "mag",
    "EMG": "emg",
    "EOG": "eog",
    "ECG": "ecg",
    "SEEG": "seeg",
    "ECOG": "ecog",
    "MISC": "misc",
}


def read_raw(path: str | os.PathLike[str], preload: bool = True):
    import mne

    return mne.io.read_raw(os.fspath(path), preload=preload, verbose="error")


def raw_from_window(header: dict[str, Any], data: np.ndarray, types: list[str] | None = None):
    """``mne.io.RawArray`` from an ``nf-window/1`` header and physical-unit data
    (channels x samples). Voltage units are converted to volts (MNE's convention)."""
    import mne

    names = list(header["channels"])
    units = list(header.get("units") or ["uV"] * len(names))
    factors = np.asarray([_TO_VOLTS.get(u, 1.0) for u in units])[:, None]
    ch_types = types or [
        _MNE_TYPES.get(str(m).upper(), "misc")
        for m in header.get("modalities", ["EEG"] * len(names))
    ]
    info = mne.create_info(names, float(header["sfreq"]), ch_types)
    return mne.io.RawArray(np.asarray(data, dtype=np.float64) * factors, info, verbose="error")


def to_signal(raw) -> tuple[np.ndarray, float, list[str], list[str]]:
    """(samples x channels float64 in microvolts for EEG-like channels, sfreq, names, units)
    from an MNE Raw, ready for :func:`neuroforge.local.write_signal`."""
    data = raw.get_data()  # volts
    types = raw.get_channel_types()
    volt_like = {"eeg", "eog", "emg", "ecg", "seeg", "ecog"}
    scale = np.asarray([1e6 if t in volt_like else 1.0 for t in types])[:, None]
    units = ["uV" if t in volt_like else "au" for t in types]
    return (data * scale).T.copy(), float(raw.info["sfreq"]), list(raw.ch_names), units
