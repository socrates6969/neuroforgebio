"""BrainVision Core Data Format 1.0 (.vhdr/.vmrk/.eeg), binary time-domain data only.

Strict minimal reader (MNE is the CI reference reader). Raw sample values are kept in their
binary dtype (INT_16 / INT_32 / IEEE_FLOAT_32) with the per-channel resolution as `scale`, so the
round trip is bit-exact. `DataFile`/`MarkerFile` must be plain file names next to the header (no
path components): a header cannot make the converter read other files (path traversal).
"""

from __future__ import annotations

import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from nf_platform.ingest.convert.model import (
    DEFAULT_LIMITS,
    Channel,
    CorruptFileError,
    Event,
    FileTooLargeError,
    Limits,
    SourceRecording,
    UnsupportedFormatError,
)

_FORMATS = {"INT_16": "<i2", "INT_32": "<i4", "IEEE_FLOAT_32": "<f4"}
_HDR_MAGIC = re.compile(r"^Brain ?Vision Data Exchange Header File", re.I)
_MRK_MAGIC = re.compile(r"^Brain ?Vision Data Exchange Marker File", re.I)
_MAX_TEXT = 16 * 1024 * 1024


def _read_text(path: Path) -> str:
    if path.stat().st_size > _MAX_TEXT:
        raise FileTooLargeError(f"{path.name} is too large for a header/marker file")
    raw = path.read_bytes()
    for enc in ("utf-8", "latin-1"):
        try:
            return raw.decode(enc).lstrip("﻿")
        except UnicodeDecodeError:
            continue
    raise CorruptFileError("undecodable text")  # pragma: no cover - latin-1 decodes anything


def _ini(text: str) -> dict[str, dict[str, str]]:
    sections: dict[str, dict[str, str]] = {}
    cur: dict[str, str] | None = None
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith(";"):
            continue
        if s.startswith("[") and s.endswith("]"):
            cur = sections.setdefault(s[1:-1].strip().lower(), {})
        elif "=" in s and cur is not None:
            k, v = s.split("=", 1)
            cur[k.strip().lower()] = v.strip()
    return sections


def _sibling(vhdr: Path, name: str | None, what: str) -> Path:
    if not name:
        raise CorruptFileError(f"{what} missing in header")
    if "/" in name or "\\" in name or name in (".", "..") or ":" in name:
        raise CorruptFileError(f"{what} must be a plain file name next to the header")
    p = vhdr.parent / name
    if not p.is_file():
        raise CorruptFileError(f"{what} {name!r} not found next to the header")
    return p


def _num(s: str, what: str, cast=float) -> Any:
    try:
        v = cast(s)
    except ValueError as e:
        raise CorruptFileError(f"{what}: {s!r} is not a number") from e
    if isinstance(v, float) and not math.isfinite(v):
        raise CorruptFileError(f"{what}: not finite")
    return v


def read_brainvision(path: str | Path, limits: Limits = DEFAULT_LIMITS) -> SourceRecording:
    vhdr = Path(path)
    text = _read_text(vhdr)
    if not _HDR_MAGIC.match(text):
        raise CorruptFileError("not a BrainVision header")
    ini = _ini(text)
    common = ini.get("common infos")
    if common is None:
        raise CorruptFileError("[Common Infos] missing")
    if common.get("dataformat", "BINARY").upper() != "BINARY":
        raise UnsupportedFormatError("only BINARY BrainVision data is supported")
    if common.get("datatype", "TIMEDOMAIN").upper() != "TIMEDOMAIN":
        raise UnsupportedFormatError("only TIMEDOMAIN BrainVision data is supported")
    orient = common.get("dataorientation", "MULTIPLEXED").upper()
    if orient not in ("MULTIPLEXED", "VECTORIZED"):
        raise CorruptFileError(f"unknown DataOrientation {orient!r}")
    n_ch = _num(common.get("numberofchannels", ""), "NumberOfChannels", int)
    if not 1 <= n_ch <= limits.max_channels:
        raise CorruptFileError(f"NumberOfChannels {n_ch} out of range")
    si = _num(common.get("samplinginterval", ""), "SamplingInterval")
    if si <= 0:
        raise CorruptFileError("SamplingInterval must be positive")
    binfmt = ini.get("binary infos", {}).get("binaryformat", "").upper()
    if binfmt not in _FORMATS:
        raise UnsupportedFormatError(f"BinaryFormat {binfmt!r} not supported")
    dtype = np.dtype(_FORMATS[binfmt])

    chinfo = ini.get("channel infos", {})
    chans: list[Channel] = []
    refs: list[str] = []
    for i in range(1, n_ch + 1):
        spec = chinfo.get(f"ch{i}")
        if spec is None:
            raise CorruptFileError(f"Ch{i} missing in [Channel Infos]")
        parts = [p.replace("\\1", ",") for p in spec.split(",")]
        parts += [""] * (4 - len(parts))
        name, ref, res, unit = parts[0], parts[1], parts[2], ",".join(parts[3:]).rstrip(",")
        if not name:
            raise CorruptFileError(f"Ch{i} has no name")
        scale = _num(res, f"Ch{i} resolution") if res else 1.0
        if scale == 0:
            raise CorruptFileError(f"Ch{i} resolution is 0")
        chans.append(Channel(name=name, unit=unit or "µV", modality="EEG", scale=scale))
        refs.append(ref)

    data_path = _sibling(vhdr, common.get("datafile"), "DataFile")
    nbytes = data_path.stat().st_size
    if nbytes > limits.max_file_bytes:
        raise FileTooLargeError("data file exceeds the size limit")
    frame = n_ch * dtype.itemsize
    if nbytes == 0 or nbytes % frame:
        raise CorruptFileError("data file size is not a whole number of samples")
    n = nbytes // frame
    if n > limits.max_samples_per_channel:
        raise FileTooLargeError("too many samples per channel")
    flat = np.fromfile(data_path, dtype=dtype)
    data = flat.reshape(n, n_ch).T if orient == "MULTIPLEXED" else flat.reshape(n_ch, n)
    data = np.ascontiguousarray(data).astype(dtype.newbyteorder("="))
    if dtype.kind == "f" and not np.isfinite(data).all():
        raise CorruptFileError("non-finite samples in float data")
    sfreq = 1e6 / si

    events: list[Event] = []
    start = None
    if common.get("markerfile"):
        events, start = _read_markers(_sibling(vhdr, common["markerfile"], "MarkerFile"), sfreq)
        if len(events) > limits.max_events:
            raise FileTooLargeError("too many markers")
    rec = SourceRecording(
        data=data,
        sfreq=sfreq,
        channels=chans,
        source_format="brainvision",
        start_time=start,
        events=events,
        meta={
            "brainvision": {
                "binary_format": binfmt,
                "orientation": orient,
                "sampling_interval_us": si,
                "references": refs,
            }
        },
    )
    rec.validate(limits)
    return rec


def _read_markers(vmrk: Path, sfreq: float) -> tuple[list[Event], str | None]:
    text = _read_text(vmrk)
    if not _MRK_MAGIC.match(text):
        raise CorruptFileError("not a BrainVision marker file")
    events: list[Event] = []
    start = None
    for k, v in _ini(text).get("marker infos", {}).items():
        if not re.fullmatch(r"mk\d+", k):
            continue
        parts = v.split(",")
        if len(parts) < 5:
            raise CorruptFileError(f"marker {k} has too few fields")
        mtype, desc = parts[0].replace("\\1", ","), parts[1].replace("\\1", ",")
        pos = _num(parts[2], f"marker {k} position", int)
        pts = _num(parts[3], f"marker {k} points", int)
        if pos < 1 or pts < 0:
            raise CorruptFileError(f"marker {k} has a negative position/size")
        if mtype.lower() == "new segment" and len(parts) > 5 and len(parts[5]) >= 14:
            try:
                start = datetime.strptime(parts[5][:14], "%Y%m%d%H%M%S").isoformat()
            except ValueError:
                start = None
        events.append(Event((pos - 1) / sfreq, pts / sfreq, desc, kind=mtype))
    events.sort(key=lambda e: e.onset_s)
    return events, start


# ---------------------------------------------------------------- writer
_DTYPE_TO_FMT = {"int16": "INT_16", "int32": "INT_32", "float32": "IEEE_FLOAT_32"}


def write_brainvision(path: str | Path, rec: SourceRecording) -> Path:
    vhdr = Path(path).with_suffix(".vhdr")
    stem = vhdr.stem
    data = rec.data
    scales = [c.scale for c in rec.channels]
    if data.dtype.name not in _DTYPE_TO_FMT or any(c.offset for c in rec.channels):
        # Not representable as-is: write physical values as float32 with resolution 1.
        data = (
            data.astype(np.float64) * np.array(scales)[:, None]
            + np.array([c.offset for c in rec.channels])[:, None]
        ).astype(np.float32)
        scales = [1.0] * len(scales)
    binfmt = _DTYPE_TO_FMT[data.dtype.name]
    refs = rec.meta.get("brainvision", {}).get("references") or [""] * len(rec.channels)

    def esc(s: str) -> str:
        return s.replace(",", "\\1")

    lines = [
        "Brain Vision Data Exchange Header File Version 1.0",
        "; Exported by nf-platform (identifiers are never exported)",
        "",
        "[Common Infos]",
        "Codepage=UTF-8",
        f"DataFile={stem}.eeg",
        f"MarkerFile={stem}.vmrk",
        "DataFormat=BINARY",
        "DataOrientation=MULTIPLEXED",
        f"NumberOfChannels={len(rec.channels)}",
        f"SamplingInterval={repr(1e6 / rec.sfreq)}",
        "",
        "[Binary Infos]",
        f"BinaryFormat={binfmt}",
        "",
        "[Channel Infos]",
        *[
            f"Ch{i + 1}={esc(c.name)},{esc(refs[i])},{repr(float(scales[i]))},{esc(c.unit)}"
            for i, c in enumerate(rec.channels)
        ],
        "",
    ]
    vhdr.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    date = ""
    if rec.start_time:
        try:
            date = datetime.fromisoformat(rec.start_time).strftime("%Y%m%d%H%M%S") + "000000"
        except ValueError:
            date = ""
    mk = [
        "Brain Vision Data Exchange Marker File, Version 1.0",
        "",
        "[Common Infos]",
        "Codepage=UTF-8",
        f"DataFile={stem}.eeg",
        "",
        "[Marker Infos]",
    ]
    evs = list(rec.events)
    if not any(e.kind.lower() == "new segment" for e in evs):
        evs.insert(0, Event(0.0, 0.0, "", kind="New Segment"))
    for k, e in enumerate(sorted(evs, key=lambda e: e.onset_s)):
        pos = round(e.onset_s * rec.sfreq) + 1
        pts = max(1, round(e.duration_s * rec.sfreq)) if e.duration_s else 1
        extra = f",{date}" if e.kind.lower() == "new segment" and date else ""
        mk.append(f"Mk{k + 1}={esc(e.kind)},{esc(e.label)},{pos},{pts},0{extra}")
    mk.append("")
    vhdr.with_suffix(".vmrk").write_text("\n".join(mk), encoding="utf-8", newline="\n")
    le = data.astype(data.dtype.newbyteorder("<"), copy=False)
    vhdr.with_suffix(".eeg").write_bytes(np.ascontiguousarray(le.T).tobytes())
    return vhdr
