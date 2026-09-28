"""Shared converter types: errors, limits, the in-memory `SourceRecording`, channel governance
defaults (BLUEPRINT §3.2) and the provenance record `raw --convert@version--> recording`."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

import numpy as np

CONVERTER_NAME = "nf-convert"
CONVERTER_VERSION = "0.1.0"


# ---------------------------------------------------------------- errors (all typed, all clean)
class ConversionError(Exception):
    """Base class: every converter failure is (a subclass of) this, never a bare crash."""


class CorruptFileError(ConversionError):
    """The input does not follow its format (truncated, bad sizes, bad fields, random bytes)."""


class UnsupportedFormatError(ConversionError):
    """Valid input using a feature this converter does not support (yet)."""


class FileTooLargeError(ConversionError):
    """The input exceeds the configured size/shape limits (SEC-060)."""


class IdentifierPolicyError(ConversionError):
    """Direct identifiers found where the tenant policy forbids them (SEC-140)."""


class MissingDependencyError(ConversionError):
    """The maintained reader for this format is not installed here (CI-only readers)."""


@dataclass(frozen=True)
class Limits:
    """Size limits enforced before any large allocation (SEC-060). Time limits are the worker
    sandbox's job (M3); converters are linear in the input size and never loop unboundedly."""

    max_file_bytes: int = 8 * 1024**3
    max_channels: int = 4096
    max_samples_per_channel: int = 2**31 - 1
    max_events: int = 1_000_000


DEFAULT_LIMITS = Limits()


# ---------------------------------------------------------------- governance defaults (§3.2)
_CENTRAL = {"EEG", "ECOG", "SEEG", "IEEG", "LFP", "MEG", "SPIKES", "DBS", "EPHYS"}
_PERIPHERAL = {"EMG", "ENG"}
_NON_NEURAL = {"EOG", "ECG", "EKG", "RESP", "GSR", "EDA", "PPG", "TEMP", "SPO2", "ACC", "GYRO"}


def governance_defaults(modality: str) -> dict[str, Any]:
    """Default governance attributes by modality. Editable later; a default, not a legal finding.
    Unknown modalities get the conservative reading (not marked as derived from non-neural data)."""
    m = modality.upper()
    if m in _CENTRAL:
        ns, derived = "central", False
    elif m in _PERIPHERAL:
        ns, derived = "peripheral", False
    elif m in _NON_NEURAL:
        ns, derived = "unknown", True
    else:
        ns, derived = "unknown", False
    return {
        "modality": m,
        "nervous_system": ns,
        "derived_from_non_neural": derived,
        "governance_source": "default-by-modality",
    }


def modality_from_label(label: str, default: str = "EEG") -> str:
    """EDF-style labels often carry the type first ("EEG Fp1", "ECG II", "EMG chin")."""
    tokens = label.upper().replace("-", " ").replace("_", " ").split()
    if tokens and tokens[0] in (_CENTRAL | _PERIPHERAL | _NON_NEURAL):
        return tokens[0]
    return default


@dataclass
class Channel:
    name: str
    unit: str
    modality: str = "EEG"
    scale: float = 1.0
    offset: float = 0.0
    device_ref: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_attr(self, sfreq: float) -> dict[str, Any]:
        d = {
            "name": self.name,
            "units": self.unit,
            "sampling_rate": sfreq,
            "device_ref": self.device_ref,
            **governance_defaults(self.modality),
        }
        if self.extra:
            d["format"] = self.extra
        return d


@dataclass
class Event:
    onset_s: float
    duration_s: float
    label: str
    kind: str = "annotation"

    def to_attr(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SourceRecording:
    """One regularly sampled multichannel signal from a source file (before the canonical write)."""

    data: np.ndarray  # (n_channels, n_samples), stored dtype
    sfreq: float
    channels: list[Channel]
    source_format: str
    start_time: str | None = None
    events: list[Event] = field(default_factory=list)
    timestamps: np.ndarray | None = None
    clock_offsets: np.ndarray | None = None
    meta: dict[str, Any] = field(default_factory=dict)  # non-identifying format metadata
    identifiers: dict[str, str] = field(default_factory=dict)  # scrubbed; for the governed table

    def validate(self, limits: Limits = DEFAULT_LIMITS) -> None:
        if self.data.ndim != 2 or self.data.shape[0] != len(self.channels):
            raise CorruptFileError("channel count does not match the data")
        if self.data.shape[0] > limits.max_channels:
            raise FileTooLargeError(f"{self.data.shape[0]} channels exceed the limit")
        if self.data.shape[1] < 1:
            raise CorruptFileError("no samples")
        if not (math.isfinite(self.sfreq) and self.sfreq > 0):
            raise CorruptFileError("sampling rate must be positive and finite")
        if len({c.name for c in self.channels}) != len(self.channels):
            raise CorruptFileError("duplicate channel names")


@dataclass(frozen=True)
class Provenance:
    """`raw file --(activity: convert@version)--> recording(s)`. M3 persists it in the graph."""

    raw_sha256: str
    raw_object_key: str | None
    source_format: str
    reader: str
    recording_ids: tuple[str, ...]
    started_at: str
    ended_at: str
    converter: str = f"{CONVERTER_NAME}@{CONVERTER_VERSION}"
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def edge(self) -> str:
        outs = ",".join(self.recording_ids)
        return f"raw:{self.raw_sha256[:12]} --convert@{CONVERTER_VERSION}--> recording:{outs}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_in": {
                "kind": "raw_file",
                "sha256": self.raw_sha256,
                "object_key": self.raw_object_key,
                "format": self.source_format,
            },
            "activity": {
                "type": "convert",
                "agent": self.converter,
                "reader": self.reader,
                "params": self.params,
                "started_at": self.started_at,
                "ended_at": self.ended_at,
            },
            "entities_out": [{"kind": "recording", "id": r} for r in self.recording_ids],
        }


def utcnow() -> str:
    return datetime.now(UTC).isoformat()
