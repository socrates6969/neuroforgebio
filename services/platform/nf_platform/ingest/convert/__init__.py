"""File converters: EDF/BDF, BrainVision, BIDS, NWB, XDF -> canonical Zarr (BUILD-GUIDE 2.5)."""

from nf_platform.ingest.convert.model import (
    CONVERTER_VERSION,
    Channel,
    ConversionError,
    CorruptFileError,
    Event,
    FileTooLargeError,
    IdentifierPolicyError,
    Limits,
    MissingDependencyError,
    Provenance,
    SourceRecording,
    UnsupportedFormatError,
    governance_defaults,
)
from nf_platform.ingest.convert.pipeline import (
    FORMATS,
    ConvertResult,
    convert_file,
    detect_format,
    export_recording,
    load_source,
    read_source,
)

__all__ = [
    "CONVERTER_VERSION",
    "FORMATS",
    "Channel",
    "ConversionError",
    "ConvertResult",
    "CorruptFileError",
    "Event",
    "FileTooLargeError",
    "IdentifierPolicyError",
    "Limits",
    "MissingDependencyError",
    "Provenance",
    "SourceRecording",
    "UnsupportedFormatError",
    "convert_file",
    "detect_format",
    "export_recording",
    "governance_defaults",
    "load_source",
    "read_source",
]
