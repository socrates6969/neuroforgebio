"""Canonical Zarr v3 signal layout, window reads and multiscale pyramids (BUILD-GUIDE 2.4).

Layout spec: `docs/spec/zarr-layout.md`.
"""

from nf_platform.signals.encrypted_store import EncryptedZarrStore
from nf_platform.signals.zarr_store import (
    LAYOUT_VERSION,
    RecordingInfo,
    SignalError,
    ZarrRef,
    open_recording,
    read_array,
    read_window,
    write_recording,
)

__all__ = [
    "LAYOUT_VERSION",
    "EncryptedZarrStore",
    "RecordingInfo",
    "SignalError",
    "ZarrRef",
    "open_recording",
    "read_array",
    "read_window",
    "write_recording",
]
