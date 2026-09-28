"""EDF/EDF+ and BDF/BDF+ (continuous) reader and writer.

A small strict reader is used here instead of MNE because (a) MNE is CI-only on the dev PC (RAM)
and (b) the strict header validation is what turns corrupt inputs into clean typed errors before
any allocation. MNE (CI) and pyedflib/EDFlib (local) are the independent reference readers in the
tests. Digital values are kept as-is (int16 EDF, int32 for 24-bit BDF) with per-channel
scale/offset, so EDF -> Zarr -> EDF is bit-exact.

Header scrubbing (SEC-141): the EDF+ patient and recording identification fields are returned in
`identifiers` (for the governed table) and never stored in the canonical copy; exports write the
EDF+ "unknown" forms (`X X X X`, `Startdate <date> X X X`).
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
    modality_from_label,
)

_SIG_FIELDS = (
    ("label", 16),
    ("transducer", 80),
    ("unit", 8),
    ("pmin", 8),
    ("pmax", 8),
    ("dmin", 8),
    ("dmax", 8),
    ("prefilter", 80),
    ("nsamples", 8),
    ("reserved", 32),
)
_ANN_LABELS = {"EDF Annotations", "BDF Annotations"}
_MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
_TAL_RE = re.compile(rb"^([+-]\d+(?:\.\d+)?)(?:\x15(\d+(?:\.\d+)?))?\x14(.*)\x14$", re.S)


def _ascii(b: bytes, what: str) -> str:
    try:
        s = b.decode("ascii")
    except UnicodeDecodeError as e:
        raise CorruptFileError(f"{what}: non-ASCII header bytes") from e
    if any(ord(c) < 32 or ord(c) > 126 for c in s):
        raise CorruptFileError(f"{what}: control characters in header")
    return s.strip()


def _int(b: bytes, what: str) -> int:
    s = _ascii(b, what)
    try:
        return int(s)
    except ValueError as e:
        raise CorruptFileError(f"{what}: {s!r} is not an integer") from e


def _float(b: bytes, what: str) -> float:
    s = _ascii(b, what)
    try:
        v = float(s)
    except ValueError as e:
        raise CorruptFileError(f"{what}: {s!r} is not a number") from e
    if not math.isfinite(v):
        raise CorruptFileError(f"{what}: not finite")
    return v


def _start_time(date: str, time: str) -> str | None:
    try:
        dd, mm, yy = (int(x) for x in date.split("."))
        hh, mi, ss = (int(x) for x in time.split("."))
        year = 1900 + yy if yy >= 85 else 2000 + yy
        return datetime(year, mm, dd, hh, mi, ss).isoformat()
    except (ValueError, TypeError):
        return None


def _parse_tals(raw: bytes, max_events: int) -> tuple[list[Event], float | None]:
    """Parse one annotation-signal record. Returns (events, record start time)."""
    events: list[Event] = []
    rec_start = None
    for tal in raw.split(b"\x00"):
        if not tal:
            continue
        m = _TAL_RE.match(tal)
        if not m:
            raise CorruptFileError("malformed EDF+ annotation (TAL)")
        onset = float(m.group(1))
        dur = float(m.group(2)) if m.group(2) else 0.0
        texts = m.group(3).split(b"\x14")
        if texts == [b""]:
            if rec_start is None:
                rec_start = onset
            continue
        for t in texts:
            if t:
                events.append(Event(onset, dur, t.decode("utf-8", "replace")))
        if len(events) > max_events:
            raise FileTooLargeError("too many annotations")
    return events, rec_start


def read_edf(path: str | Path, limits: Limits = DEFAULT_LIMITS) -> SourceRecording:
    path = Path(path)
    size = path.stat().st_size
    if size > limits.max_file_bytes:
        raise FileTooLargeError(f"file is {size} bytes; limit {limits.max_file_bytes}")
    with path.open("rb") as fh:
        hdr = fh.read(256)
        if len(hdr) < 256:
            raise CorruptFileError("truncated header (< 256 bytes)")
        ver = hdr[:8]
        if ver == b"\xffBIOSEMI":
            bdf = True
        elif ver == b"0       ":
            bdf = False
        else:
            raise CorruptFileError("not an EDF/BDF file (bad version field)")
        patient = _ascii(hdr[8:88], "patient")
        recording = _ascii(hdr[88:168], "recording")
        start = _start_time(_ascii(hdr[168:176], "startdate"), _ascii(hdr[176:184], "starttime"))
        header_bytes = _int(hdr[184:192], "header bytes")
        reserved = _ascii(hdr[192:236], "reserved")
        n_records = _int(hdr[236:244], "number of records")
        rec_dur = _float(hdr[244:252], "record duration")
        ns = _int(hdr[252:256], "number of signals")
        if not 1 <= ns <= limits.max_channels + 1:
            raise CorruptFileError(f"number of signals {ns} out of range")
        if header_bytes != 256 * (ns + 1):
            raise CorruptFileError("header size does not match the number of signals")
        if reserved.startswith(("EDF+D", "BDF+D")):
            raise UnsupportedFormatError("discontinuous EDF+D/BDF+D is not supported yet")
        if rec_dur <= 0:
            raise UnsupportedFormatError("record duration 0 (annotation-only file)")
        sig_hdr = fh.read(256 * ns)
        if len(sig_hdr) < 256 * ns:
            raise CorruptFileError("truncated signal header")

        fields: dict[str, list[bytes]] = {}
        pos = 0
        for name, width in _SIG_FIELDS:
            fields[name] = [sig_hdr[pos + i * width : pos + (i + 1) * width] for i in range(ns)]
            pos += width * ns

        width = 3 if bdf else 2
        lo, hi = (-(2**23), 2**23 - 1) if bdf else (-(2**15), 2**15 - 1)
        sigs: list[dict[str, Any]] = []
        for i in range(ns):
            s = {
                "label": _ascii(fields["label"][i], f"signal {i} label"),
                "transducer": _ascii(fields["transducer"][i], f"signal {i} transducer"),
                "unit": _ascii(fields["unit"][i], f"signal {i} unit"),
                "prefilter": _ascii(fields["prefilter"][i], f"signal {i} prefilter"),
                "nsamples": _int(fields["nsamples"][i], f"signal {i} samples per record"),
            }
            if not 1 <= s["nsamples"] <= 10_000_000:
                raise CorruptFileError(f"signal {i}: samples per record out of range")
            s["annotation"] = s["label"] in _ANN_LABELS
            if not s["annotation"]:
                s["pmin"] = _float(fields["pmin"][i], f"signal {i} physical min")
                s["pmax"] = _float(fields["pmax"][i], f"signal {i} physical max")
                s["dmin"] = _int(fields["dmin"][i], f"signal {i} digital min")
                s["dmax"] = _int(fields["dmax"][i], f"signal {i} digital max")
                if not lo <= s["dmin"] < s["dmax"] <= hi:
                    raise CorruptFileError(f"signal {i}: digital range invalid")
                if s["pmin"] == s["pmax"]:
                    raise CorruptFileError(f"signal {i}: physical min equals max")
            sigs.append(s)

        record_bytes = sum(s["nsamples"] for s in sigs) * width
        avail = size - header_bytes
        if n_records == -1:
            if avail <= 0 or avail % record_bytes:
                raise CorruptFileError("record count unknown and data size is not whole records")
            n_records = avail // record_bytes
        if n_records < 1:
            raise CorruptFileError("no data records")
        if n_records * record_bytes > avail:
            raise CorruptFileError(
                f"truncated data: header promises {n_records} records, file holds "
                f"{max(0, avail) // record_bytes}"
            )
        data_sigs = [s for s in sigs if not s["annotation"]]
        if not data_sigs:
            raise UnsupportedFormatError("file has no signal channels")
        if len({s["nsamples"] for s in data_sigs}) != 1:
            raise UnsupportedFormatError("mixed sampling rates in one file are not supported yet")
        spr = data_sigs[0]["nsamples"]
        if n_records * spr > limits.max_samples_per_channel:
            raise FileTooLargeError("too many samples per channel")
        raw = np.frombuffer(fh.read(n_records * record_bytes), dtype=np.uint8)
    raw = raw.reshape(n_records, record_bytes)

    chans: list[Channel] = []
    cols: list[np.ndarray] = []
    events: list[Event] = []
    off = 0
    for s in sigs:
        nb = s["nsamples"] * width
        block = raw[:, off : off + nb]
        off += nb
        if s["annotation"]:
            for r in range(n_records):
                ev, _ = _parse_tals(bytes(block[r]), 1_000_000)
                events.extend(ev)
            continue
        if bdf:
            b = block.reshape(-1, 3).astype(np.int32)
            v = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
            v = np.where(v >= 2**23, v - 2**24, v).astype(np.int32)
        else:
            v = np.ascontiguousarray(block).view("<i2").reshape(-1).astype(np.int16)
        cols.append(v)
        gain = (s["pmax"] - s["pmin"]) / (s["dmax"] - s["dmin"])
        chans.append(
            Channel(
                name=s["label"],
                unit=s["unit"],
                modality=modality_from_label(s["label"]),
                scale=gain,
                offset=s["pmin"] - s["dmin"] * gain,
                extra={
                    "edf": {
                        "pmin": s["pmin"],
                        "pmax": s["pmax"],
                        "dmin": s["dmin"],
                        "dmax": s["dmax"],
                        "transducer": s["transducer"],
                        "prefilter": s["prefilter"],
                    }
                },
            )
        )
    identifiers = {}
    if patient and patient not in ("X X X X", "X"):
        identifiers["edf_patient"] = patient
    if recording and not re.fullmatch(r"Startdate \S+ X X X|Startdate X X X X|", recording):
        identifiers["edf_recording"] = recording
    if len(events) > limits.max_events:
        raise FileTooLargeError("too many annotations")
    rec = SourceRecording(
        data=np.stack(cols),
        sfreq=spr / rec_dur,
        channels=chans,
        source_format="bdf" if bdf else "edf",
        start_time=start,
        events=events,
        meta={
            "edf": {
                "variant": reserved[:5]
                if reserved[:4] in ("EDF+", "BDF+")
                else ("BDF" if bdf else "EDF"),
                "record_duration": rec_dur,
                "samples_per_record": spr,
                "n_records": n_records,
            }
        },
        identifiers=identifiers,
    )
    rec.validate(limits)
    return rec


# ---------------------------------------------------------------- writer
def _fmt(x: float, width: int = 8) -> str:
    for s in (repr(float(x)).removesuffix(".0"), str(int(x)) if float(x).is_integer() else ""):
        if s and len(s) <= width and "e" not in s:
            return s
    for prec in range(width, 0, -1):
        s = f"{x:.{prec}g}"
        if len(s) <= width and "e" not in s:
            return s
    raise ValueError(f"cannot fit {x} in {width} characters")


def _onset(x: float) -> str:
    return ("+" if x >= 0 else "-") + _fmt(abs(x), 20)


def _field(v: Any, width: int) -> bytes:
    s = str(v)
    if len(s) > width:
        s = s[:width]
    return s.ljust(width).encode("ascii", "replace")


def _quantize(rec: SourceRecording, bdf: bool) -> tuple[np.ndarray, list[dict[str, float]]]:
    """Digital samples + EDF ranges. Uses the stored EDF ranges when present (exact round trip);
    otherwise quantizes the physical values to the full digital range."""
    lo, hi = (-(2**23), 2**23 - 1) if bdf else (-(2**15), 2**15 - 1)
    out = np.empty(rec.data.shape, dtype=np.int32)
    ranges = []
    for i, ch in enumerate(rec.channels):
        e = ch.extra.get("edf")
        if e and rec.data.dtype.kind == "i" and lo <= e["dmin"] and e["dmax"] <= hi:
            out[i] = rec.data[i]
            ranges.append(e)
            continue
        phys = rec.data[i].astype(np.float64) * ch.scale + ch.offset
        pmin, pmax = float(np.floor(phys.min())) - 1.0, float(np.ceil(phys.max())) + 1.0
        out[i] = np.clip(np.round((phys - pmin) / (pmax - pmin) * (hi - lo) + lo), lo, hi)
        ranges.append({"pmin": pmin, "pmax": pmax, "dmin": lo, "dmax": hi})
    return out, ranges


def _record_plan(n: int, sfreq: float, meta: dict[str, Any]) -> tuple[int, float]:
    e = meta.get("edf", {})
    spr = e.get("samples_per_record")
    if spr and n % spr == 0 and e.get("record_duration"):
        return int(spr), float(e["record_duration"])
    if float(sfreq).is_integer() and n % int(sfreq) == 0:
        return int(sfreq), 1.0
    if n <= 99_999_999:
        return n, n / sfreq
    raise UnsupportedFormatError("cannot split this recording into whole EDF records")


def write_edf(path: str | Path, rec: SourceRecording, *, bdf: bool | None = None) -> Path:
    path = Path(path)
    bdf = rec.source_format == "bdf" if bdf is None else bdf
    n_ch, n = rec.data.shape
    spr, dur = _record_plan(n, rec.sfreq, rec.meta)
    n_rec = n // spr
    dig, ranges = _quantize(rec, bdf)
    width = 3 if bdf else 2

    tals = []
    evs = sorted(rec.events, key=lambda e: e.onset_s)
    for r in range(n_rec):
        t0 = r * dur
        tal = f"{_onset(t0)}\x14\x14\x00".encode()
        for ev in evs:
            if t0 <= ev.onset_s < t0 + dur or (r == n_rec - 1 and ev.onset_s >= t0 + dur):
                d = f"\x15{_fmt(ev.duration_s, 20)}" if ev.duration_s else ""
                tal += f"{_onset(ev.onset_s)}{d}\x14{ev.label}\x14\x00".encode()
        tals.append(tal)
    ann_samples = -(-max(len(t) for t in tals) // width) + 1
    ns = n_ch + 1
    start = None
    if rec.start_time:
        try:
            start = datetime.fromisoformat(rec.start_time)
        except ValueError:
            start = None
    start = start or datetime(1985, 1, 1)
    labels = [c.name for c in rec.channels] + ["BDF Annotations" if bdf else "EDF Annotations"]

    h = bytearray()
    h += b"\xffBIOSEMI" if bdf else _field("0", 8)
    h += _field("X X X X", 80)  # SEC-141: identifiers never exported
    h += _field(f"Startdate {start.day:02d}-{_MONTHS[start.month - 1]}-{start.year} X X X", 80)
    h += _field(start.strftime("%d.%m.%y"), 8)
    h += _field(start.strftime("%H.%M.%S"), 8)
    h += _field(256 * (ns + 1), 8)
    h += _field("BDF+C" if bdf else "EDF+C", 44)
    h += _field(n_rec, 8)
    h += _field(_fmt(dur), 8)
    h += _field(ns, 4)
    h += b"".join(_field(lb, 16) for lb in labels)
    h += b"".join(
        _field(c.extra.get("edf", {}).get("transducer", ""), 80) for c in rec.channels
    ) + _field("", 80)
    h += b"".join(_field(c.unit, 8) for c in rec.channels) + _field("", 8)
    h += b"".join(_field(_fmt(r["pmin"]), 8) for r in ranges) + _field(-1, 8)
    h += b"".join(_field(_fmt(r["pmax"]), 8) for r in ranges) + _field(1, 8)
    lo, hi = (-(2**23), 2**23 - 1) if bdf else (-(2**15), 2**15 - 1)
    h += b"".join(_field(int(r["dmin"]), 8) for r in ranges) + _field(lo, 8)
    h += b"".join(_field(int(r["dmax"]), 8) for r in ranges) + _field(hi, 8)
    h += b"".join(
        _field(c.extra.get("edf", {}).get("prefilter", ""), 80) for c in rec.channels
    ) + _field("", 80)
    h += b"".join(_field(spr, 8) for _ in range(n_ch)) + _field(ann_samples, 8)
    h += b"".join(_field("", 32) for _ in range(ns))
    assert len(h) == 256 * (ns + 1)

    with path.open("wb") as fh:
        fh.write(bytes(h))
        for r in range(n_rec):
            block = dig[:, r * spr : (r + 1) * spr]
            if bdf:
                u = (block.astype(np.int64) & 0xFFFFFF).astype("<u4")
                b = u.view(np.uint8).reshape(n_ch, spr, 4)[:, :, :3]
                fh.write(np.ascontiguousarray(b).tobytes())
            else:
                fh.write(block.astype("<i2").tobytes())
            fh.write(tals[r].ljust(ann_samples * width, b"\x00"))
    return path
