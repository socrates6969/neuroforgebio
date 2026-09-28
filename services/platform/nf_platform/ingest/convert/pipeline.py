"""Convert a raw file to canonical Zarr (+ provenance) and export canonical Zarr back to a format.

This is the body of the per-format `ingest` worker job (BUILD-GUIDE 2.5). SEC-060: it is meant to
run in the worker sandbox, never in the API process (import-linter keeps `api` away from it).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import zarr
from zarr.abc.store import Store

from nf_platform.ingest.convert.bids import read_bids, write_bids
from nf_platform.ingest.convert.brainvision import read_brainvision, write_brainvision
from nf_platform.ingest.convert.edf import read_edf, write_edf
from nf_platform.ingest.convert.model import (
    DEFAULT_LIMITS,
    Channel,
    ConversionError,
    CorruptFileError,
    Event,
    FileTooLargeError,
    Limits,
    Provenance,
    SourceRecording,
    UnsupportedFormatError,
    utcnow,
)
from nf_platform.ingest.convert.nwb import read_nwb, write_nwb
from nf_platform.ingest.convert.xdf import read_xdf, write_xdf
from nf_platform.signals.zarr_store import (
    DEFAULT_CHUNK_S,
    ZarrRef,
    open_recording,
    read_array,
    write_recording,
)

FORMATS = ("edf", "bdf", "brainvision", "bids", "nwb", "xdf")
_EXT = {".edf": "edf", ".bdf": "bdf", ".vhdr": "brainvision", ".xdf": "xdf", ".nwb": "nwb"}


def detect_format(path: str | Path) -> str:
    p = Path(path)
    if "_eeg." in p.name:
        for parent in p.resolve().parents:
            if (parent / "dataset_description.json").is_file():
                return "bids"
    fmt = _EXT.get(p.suffix.lower())
    if fmt is None:
        raise UnsupportedFormatError(f"unknown file type {p.suffix!r}")
    return fmt


def _reader_name(fmt: str) -> str:
    if fmt == "xdf":
        import pyxdf  # noqa: PLC0415

        return f"pyxdf {getattr(pyxdf, '__version__', '?')} + nf prescan"
    if fmt == "nwb":
        return "pynwb"
    return f"nf-convert {fmt} reader"


def read_source(
    path: str | Path,
    fmt: str | None = None,
    limits: Limits = DEFAULT_LIMITS,
    *,
    allow_identified: bool = False,
) -> list[SourceRecording]:
    """Parse a source file. Every failure is a `ConversionError` subclass (never a crash)."""
    fmt = fmt or detect_format(path)
    try:
        if fmt in ("edf", "bdf"):
            return [read_edf(path, limits)]
        if fmt == "brainvision":
            return [read_brainvision(path, limits)]
        if fmt == "bids":
            return [read_bids(path, limits, allow_identified=allow_identified)]
        if fmt == "xdf":
            return read_xdf(path, limits)
        if fmt == "nwb":
            return read_nwb(path, limits)
    except ConversionError:
        raise
    except MemoryError as e:
        raise FileTooLargeError("input needs more memory than allowed") from e
    except (OSError, ValueError, IndexError, KeyError, TypeError, OverflowError) as e:
        raise CorruptFileError(f"cannot parse {fmt} input ({type(e).__name__})") from e
    except Exception as e:  # noqa: BLE001 - last line of defence: typed error, never a crash
        raise CorruptFileError(f"unexpected {fmt} parse failure ({type(e).__name__})") from e
    raise UnsupportedFormatError(f"unknown format {fmt!r}")


def source_files(path: str | Path, fmt: str) -> list[Path]:
    """The raw files that make up one upload (hashed together for provenance)."""
    p = Path(path)
    if fmt == "brainvision" or (fmt == "bids" and p.suffix == ".vhdr"):
        return [p, p.with_suffix(".vmrk"), p.with_suffix(".eeg")]
    return [p]


def sha256_files(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for p in paths:
        if p.is_file():
            with p.open("rb") as fh:
                for block in iter(lambda: fh.read(1024 * 1024), b""):
                    h.update(block)
    return h.hexdigest()


@dataclass
class ConvertResult:
    recording_ids: list[str]
    refs: list[ZarrRef]
    provenance: Provenance
    identifiers: dict[str, str] = field(default_factory=dict)  # to the governed table only
    channels: list[list[dict[str, Any]]] = field(default_factory=list)


def convert_file(
    path: str | Path,
    store: Store,
    recording_id: str,
    *,
    fmt: str | None = None,
    limits: Limits = DEFAULT_LIMITS,
    raw_object_key: str | None = None,
    allow_identified: bool = False,
    chunk_s: float = DEFAULT_CHUNK_S,
) -> ConvertResult:
    started = utcnow()
    fmt = fmt or detect_format(path)
    recs = read_source(path, fmt, limits, allow_identified=allow_identified)
    ids: list[str] = []
    refs: list[ZarrRef] = []
    idents: dict[str, str] = {}
    chans: list[list[dict[str, Any]]] = []
    for rec in recs:
        rid = recording_id
        if len(recs) > 1 or fmt == "xdf":
            sid = rec.meta.get("xdf", {}).get("stream", {}).get("stream_id", len(ids) + 1)
            rid = f"{recording_id}-s{sid}"
        ch_attrs = [c.to_attr(rec.sfreq) for c in rec.channels]
        for c, a in zip(rec.channels, ch_attrs, strict=True):
            a["modality_source"] = c.modality
        refs.append(
            write_recording(
                store,
                rid,
                rec.data,
                rec.sfreq,
                [c.name for c in rec.channels],
                [c.unit for c in rec.channels],
                scale=[c.scale for c in rec.channels],
                offset=[c.offset for c in rec.channels],
                timestamps=rec.timestamps,
                clock_offsets=rec.clock_offsets,
                start_time=rec.start_time,
                channels=ch_attrs,
                meta={
                    "source_format": rec.source_format,
                    "events": [e.to_attr() for e in rec.events],
                    **rec.meta,
                },
                chunk_s=chunk_s,
            )
        )
        ids.append(rid)
        idents.update(rec.identifiers)
        chans.append(ch_attrs)
    prov = Provenance(
        raw_sha256=sha256_files(source_files(path, fmt)),
        raw_object_key=raw_object_key,
        source_format=fmt,
        reader=_reader_name(fmt),
        recording_ids=tuple(ids),
        started_at=started,
        ended_at=utcnow(),
        params={"chunk_s": chunk_s},
    )
    return ConvertResult(ids, refs, prov, idents, chans)


def load_source(store: Store, recording_id: str) -> SourceRecording:
    """Rebuild a SourceRecording from canonical Zarr (the input of every exporter)."""
    info = open_recording(store, recording_id)
    sig = info.signal
    data = np.asarray(zarr.open_array(store=store, path=f"{recording_id}/data/0", mode="r")[...])
    chan_attrs = info.attrs.get("channels") or [{} for _ in sig["ch_names"]]
    chans = []
    for i, name in enumerate(sig["ch_names"]):
        a = chan_attrs[i] if i < len(chan_attrs) else {}
        chans.append(
            Channel(
                name=name,
                unit=sig["units"][i],
                modality=a.get("modality_source") or a.get("modality") or "EEG",
                scale=float(sig["scale"][i]),
                offset=float(sig["offset"][i]),
                device_ref=a.get("device_ref"),
                extra=a.get("format") or {},
            )
        )
    meta = dict(info.attrs.get("meta") or {})
    events = [Event(**e) for e in meta.pop("events", [])]
    fmt = meta.pop("source_format", "unknown")
    return SourceRecording(
        data=np.ascontiguousarray(data.T),
        sfreq=float(sig["sfreq"]),
        channels=chans,
        source_format=fmt,
        start_time=sig.get("start_time"),
        events=events,
        timestamps=read_array(store, recording_id, "timestamps") if sig["has_timestamps"] else None,
        clock_offsets=(
            read_array(store, recording_id, "clock_offsets") if sig["has_clock_offsets"] else None
        ),
        meta=meta,
    )


def export_recording(
    store: Store, recording_ids: list[str] | str, fmt: str, out_path: str | Path
) -> Path:
    """Export canonical recording(s) to `fmt`. Direct identifiers are never exported (SEC-141)."""
    ids = [recording_ids] if isinstance(recording_ids, str) else list(recording_ids)
    recs = [load_source(store, r) for r in ids]
    out = Path(out_path)
    if fmt in ("edf", "bdf"):
        return write_edf(out, recs[0], bdf=fmt == "bdf")
    if fmt == "brainvision":
        return write_brainvision(out, recs[0])
    if fmt == "bids":
        return write_bids(out, recs[0])
    if fmt == "xdf":
        return write_xdf(out, recs)
    if fmt == "nwb":
        return write_nwb(out, recs)
    raise UnsupportedFormatError(f"cannot export to {fmt!r}")
