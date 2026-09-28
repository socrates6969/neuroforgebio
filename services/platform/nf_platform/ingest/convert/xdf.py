"""XDF 1.0 via pyxdf (the maintained reader), with a strict structural pre-scan.

pyxdf is deliberately lenient: on a corrupt chunk it logs an error and scans forward, returning
partial data. For ingest that is not acceptable, so `prescan()` walks the chunk framing first
(bounded by the file size, no allocation beyond it) and rejects anything malformed, and any
error pyxdf logs while loading is turned into `CorruptFileError`.

Timestamps and clock offsets are preserved exactly as recorded: streams are loaded with
`synchronize_clocks=False, dejitter_timestamps=False`; each numeric stream becomes one canonical
recording with its original per-sample `timestamps` and its `clock_offsets` (collection time,
offset) pairs, so synchronisation can be recomputed at any time and the export writes the same
ClockOffset chunks back. String streams (markers) are kept in the recording metadata.
"""

from __future__ import annotations

import logging
import math
import struct
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import numpy as np

from nf_platform.ingest.convert.model import (
    DEFAULT_LIMITS,
    Channel,
    CorruptFileError,
    FileTooLargeError,
    Limits,
    MissingDependencyError,
    SourceRecording,
    UnsupportedFormatError,
)

FORMATS = {
    "float32": "<f4",
    "double64": "<f8",
    "int8": "<i1",
    "int16": "<i2",
    "int32": "<i4",
    "int64": "<i8",
    "string": None,
}
_TAGS = {
    1: "FileHeader",
    2: "StreamHeader",
    3: "Samples",
    4: "ClockOffset",
    5: "Boundary",
    6: "Footer",
}
_MAX_XML = 1024 * 1024


def _safe_xml(raw: bytes, what: str) -> ET.Element:
    if len(raw) > _MAX_XML:
        raise FileTooLargeError(f"{what} XML too large")
    low = raw.lower()
    if b"<!doctype" in low or b"<!entity" in low:
        raise CorruptFileError(f"{what}: DTD/entities are not allowed")
    try:
        return ET.fromstring(raw.decode("utf-8", "strict"))
    except (ET.ParseError, UnicodeDecodeError) as e:
        raise CorruptFileError(f"{what}: invalid XML") from e


def _text(el: ET.Element | None, tag: str, default: str = "") -> str:
    if el is None:
        return default
    x = el.find(tag)
    return (x.text or "").strip() if x is not None and x.text is not None else default


def prescan(buf: bytes, limits: Limits = DEFAULT_LIMITS) -> dict[int, dict[str, Any]]:
    """Validate chunk framing and stream headers. Returns {stream_id: header info}."""
    if buf[:4] != b"XDF:":
        raise CorruptFileError("not an XDF file (missing magic)")
    pos, size = 4, len(buf)
    streams: dict[int, dict[str, Any]] = {}
    first = True
    while pos < size:
        nb = buf[pos]
        if nb not in (1, 4, 8) or pos + 1 + nb > size:
            raise CorruptFileError(f"bad chunk length field at byte {pos}")
        (length,) = struct.unpack({1: "<B", 4: "<I", 8: "<Q"}[nb], buf[pos + 1 : pos + 1 + nb])
        pos += 1 + nb
        if length < 2 or pos + length > size:
            raise CorruptFileError(f"chunk length {length} at byte {pos} exceeds the file")
        (tag,) = struct.unpack("<H", buf[pos : pos + 2])
        body = buf[pos + 2 : pos + length]
        pos += length
        if tag not in _TAGS:
            raise CorruptFileError(f"unknown chunk tag {tag}")
        if first:
            if tag != 1:
                raise CorruptFileError("first chunk must be the FileHeader")
            _safe_xml(body, "FileHeader")
            first = False
            continue
        if tag == 1:
            raise CorruptFileError("second FileHeader chunk")
        if tag == 5:
            continue
        if len(body) < 4:
            raise CorruptFileError(f"{_TAGS[tag]} chunk without stream id")
        (sid,) = struct.unpack("<I", body[:4])
        if tag == 2:
            if sid in streams:
                raise CorruptFileError(f"duplicate StreamHeader for stream {sid}")
            info = _safe_xml(body[4:], "StreamHeader")
            try:
                nch = int(_text(info, "channel_count", "0"))
                srate = float(_text(info, "nominal_srate", "0"))
            except ValueError as e:
                raise CorruptFileError("StreamHeader: bad channel_count/nominal_srate") from e
            fmt = _text(info, "channel_format")
            if fmt not in FORMATS:
                raise CorruptFileError(f"StreamHeader: unknown channel_format {fmt!r}")
            if not 1 <= nch <= limits.max_channels:
                raise CorruptFileError("StreamHeader: channel_count out of range")
            if not math.isfinite(srate) or srate < 0:
                raise CorruptFileError("StreamHeader: nominal_srate invalid")
            streams[sid] = {"info": info, "channel_count": nch, "srate": srate, "format": fmt}
        elif sid not in streams:
            raise CorruptFileError(f"{_TAGS[tag]} chunk for undeclared stream {sid}")
        elif tag == 4 and len(body) != 20:
            raise CorruptFileError("ClockOffset chunk must hold exactly two doubles")
        elif tag == 6:
            _safe_xml(body[4:], "StreamFooter")
    if first:
        raise CorruptFileError("empty XDF file")
    return streams


class _ErrorCatcher(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage()[:200])


def _channels(info: ET.Element, nch: int, stream_type: str) -> list[dict[str, str]]:
    out = []
    chs = info.find("desc/channels")
    items = list(chs.findall("channel")) if chs is not None else []
    for i in range(nch):
        el = items[i] if i < len(items) else None
        out.append(
            {
                "label": _text(el, "label") or f"ch{i + 1}",
                "unit": _text(el, "unit"),
                "type": _text(el, "type") or stream_type,
            }
        )
    return out


def read_xdf(path: str | Path, limits: Limits = DEFAULT_LIMITS) -> list[SourceRecording]:
    path = Path(path)
    size = path.stat().st_size
    if size > limits.max_file_bytes:
        raise FileTooLargeError("XDF file exceeds the size limit")
    buf = path.read_bytes()
    headers = prescan(buf, limits)
    del buf
    try:
        import pyxdf  # noqa: PLC0415 - optional at import time, required here
    except ImportError as e:  # pragma: no cover - pyxdf is a runtime dependency
        raise MissingDependencyError("pyxdf is not installed") from e

    catcher = _ErrorCatcher()
    lg = logging.getLogger("pyxdf")
    lg.addHandler(catcher)
    try:
        streams, _ = pyxdf.load_xdf(
            str(path), synchronize_clocks=False, dejitter_timestamps=False, verbose=None
        )
    except Exception as e:  # noqa: BLE001 - pyxdf raises many types; all mean "corrupt"
        raise CorruptFileError(f"pyxdf could not parse the file ({type(e).__name__})") from e
    finally:
        lg.removeHandler(catcher)
    if catcher.messages:
        raise CorruptFileError(f"XDF corruption reported by pyxdf: {catcher.messages[0]}")

    numeric: list[tuple[int, dict[str, Any]]] = []
    markers: list[dict[str, Any]] = []
    all_streams: list[dict[str, Any]] = []
    for st in streams:
        sid = int(st["info"]["stream_id"])
        h = headers[sid]
        info = h["info"]
        desc = {
            "stream_id": sid,
            "name": _text(info, "name"),
            "type": _text(info, "type"),
            "channel_format": h["format"],
            "channel_count": h["channel_count"],
            "nominal_srate": h["srate"],
            "source_id": _text(info, "source_id"),
            "created_at": _text(info, "created_at"),
            "channels": _channels(info, h["channel_count"], _text(info, "type")),
            "clock_offsets": [
                [float(t), float(v)]
                for t, v in zip(st["clock_times"], st["clock_values"], strict=True)
            ],
        }
        all_streams.append({k: v for k, v in desc.items() if k != "clock_offsets"})
        if h["format"] == "string":
            desc["samples"] = [
                [float(t), [str(x) for x in row]]
                for t, row in zip(st["time_stamps"], st["time_series"], strict=True)
            ]
            markers.append(desc)
        else:
            numeric.append((sid, {"desc": desc, "stream": st}))
    if not numeric:
        raise UnsupportedFormatError("XDF file has no numeric streams")

    recs = []
    for sid, item in numeric:
        desc, st = item["desc"], item["stream"]
        ts = np.asarray(st["time_stamps"], dtype=np.float64)
        x = np.asarray(st["time_series"])
        if x.ndim != 2 or x.shape[0] == 0:
            raise UnsupportedFormatError(f"stream {sid} has no samples")
        if x.shape[0] > limits.max_samples_per_channel:
            raise FileTooLargeError("too many samples per channel")
        dtype = np.dtype(FORMATS[desc["channel_format"]]).newbyteorder("=")
        data = np.ascontiguousarray(x.astype(dtype, copy=False).T)
        if data.dtype.kind == "f" and not np.isfinite(data).all():
            raise UnsupportedFormatError(f"stream {sid} contains NaN/Inf samples")
        srate = desc["nominal_srate"]
        if srate == 0:  # irregular stream: timestamps are authoritative; sfreq is nominal only
            span = float(ts[-1] - ts[0]) if len(ts) > 1 else 0.0
            srate = (len(ts) - 1) / span if span > 0 else 1.0
        chans = [
            Channel(name=c["label"], unit=c["unit"], modality=(c["type"] or "MISC").upper())
            for c in desc["channels"]
        ]
        names = [c.name for c in chans]
        if len(set(names)) != len(names):  # XDF does not require unique labels
            for i, c in enumerate(chans):
                c.name = f"{c.name}-{i + 1}" if names.count(c.name) > 1 else c.name
        co = np.asarray(desc["clock_offsets"], dtype=np.float64).reshape(-1, 2)
        recs.append(
            SourceRecording(
                data=data,
                sfreq=float(srate),
                channels=chans,
                source_format="xdf",
                timestamps=ts,
                clock_offsets=co,
                meta={
                    "xdf": {
                        "stream": {k: v for k, v in desc.items() if k != "clock_offsets"},
                        "all_streams": all_streams,
                        "marker_streams": markers,
                    }
                },
            )
        )
        recs[-1].validate(limits)
    return recs


# ---------------------------------------------------------------- writer
def _varlen(n: int) -> bytes:
    if n < 256:
        return b"\x01" + struct.pack("<B", n)
    if n < 2**32:
        return b"\x04" + struct.pack("<I", n)
    return b"\x08" + struct.pack("<Q", n)


def _chunk(tag: int, content: bytes) -> bytes:
    return _varlen(len(content) + 2) + struct.pack("<H", tag) + content


def _header_xml(desc: dict[str, Any]) -> bytes:
    info = ET.Element("info")
    for k in ("name", "type", "channel_count", "nominal_srate", "channel_format"):
        ET.SubElement(info, k).text = str(desc[k])
    for k in ("source_id", "created_at"):
        if desc.get(k):
            ET.SubElement(info, k).text = str(desc[k])
    chs = ET.SubElement(ET.SubElement(info, "desc"), "channels")
    for c in desc.get("channels", []):
        ch = ET.SubElement(chs, "channel")
        for k in ("label", "unit", "type"):
            ET.SubElement(ch, k).text = c.get(k, "")
    return b'<?xml version="1.0"?>' + ET.tostring(info, encoding="utf-8", xml_declaration=False)


def _samples_numeric(sid: int, x: np.ndarray, ts: np.ndarray, fmt: str, block: int) -> bytes:
    """x: (n, ch) in the XDF channel format. Every sample carries its timestamp."""
    out = bytearray()
    dt = np.dtype(FORMATS[fmt])
    for s0 in range(0, len(ts), block):
        s1 = min(len(ts), s0 + block)
        rec = np.zeros(s1 - s0, dtype=[("tb", "u1"), ("t", "<f8"), ("v", dt, (x.shape[1],))])
        rec["tb"] = 8
        rec["t"] = ts[s0:s1]
        rec["v"] = x[s0:s1]
        out += _chunk(3, struct.pack("<I", sid) + _varlen(s1 - s0) + rec.tobytes())
    return bytes(out)


def _samples_string(sid: int, samples: list[list[Any]]) -> bytes:
    if not samples:
        return b""
    body = bytearray(struct.pack("<I", sid) + _varlen(len(samples)))
    for t, row in samples:
        body += b"\x08" + struct.pack("<d", t)
        for v in row:
            b = v.encode("utf-8")
            body += _varlen(len(b)) + b
    return _chunk(3, bytes(body))


def write_xdf(path: str | Path, recs: list[SourceRecording], *, block: int = 1024) -> Path:
    """Write numeric recordings (+ the marker streams stored in their metadata) as one XDF file,
    with the original stream ids, timestamps and clock offsets."""
    path = Path(path)
    out = bytearray(b"XDF:")
    out += _chunk(1, b'<?xml version="1.0"?><info><version>1.0</version></info>')
    body = bytearray()
    footers = bytearray()
    markers: dict[int, dict[str, Any]] = {}
    for rec in recs:
        meta = rec.meta.get("xdf", {})
        desc = dict(meta.get("stream") or {})
        if not desc:
            desc = {
                "stream_id": len(markers) + 1 + recs.index(rec),
                "name": "nf-platform",
                "type": rec.channels[0].modality if rec.channels else "EEG",
                "channel_format": {"float64": "double64"}.get(
                    rec.data.dtype.name, rec.data.dtype.name
                ),
                "nominal_srate": rec.sfreq,
            }
        desc["channel_count"] = len(rec.channels)
        desc["channels"] = [
            {"label": c.name, "unit": c.unit, "type": c.modality} for c in rec.channels
        ]
        sid = int(desc["stream_id"])
        fmt = desc["channel_format"]
        if fmt not in FORMATS or fmt == "string":
            raise UnsupportedFormatError(f"cannot export channel format {fmt!r}")
        out += _chunk(2, struct.pack("<I", sid) + _header_xml(desc))
        ts = (
            rec.timestamps
            if rec.timestamps is not None
            else np.arange(rec.data.shape[1]) / rec.sfreq
        )
        body += _samples_numeric(sid, rec.data.T, np.asarray(ts, dtype=np.float64), fmt, block)
        co = rec.clock_offsets if rec.clock_offsets is not None else np.zeros((0, 2))
        for t, v in np.asarray(co, dtype=np.float64).reshape(-1, 2):
            body += _chunk(4, struct.pack("<Idd", sid, t, v))
        footers += _footer(sid, ts[0], ts[-1], len(ts))
        for m in meta.get("marker_streams", []):
            markers.setdefault(int(m["stream_id"]), m)
    for sid, m in sorted(markers.items()):
        out += _chunk(2, struct.pack("<I", sid) + _header_xml(m))
        body += _samples_string(sid, m.get("samples", []))
        for t, v in m.get("clock_offsets", []):
            body += _chunk(4, struct.pack("<Idd", sid, t, v))
        s = m.get("samples", [])
        footers += _footer(sid, s[0][0] if s else 0.0, s[-1][0] if s else 0.0, len(s))
    out += body + footers
    path.write_bytes(bytes(out))
    return path


def _footer(sid: int, first: float, last: float, count: int) -> bytes:
    xml = (
        f'<?xml version="1.0"?><info><first_timestamp>{first!r}</first_timestamp>'
        f"<last_timestamp>{last!r}</last_timestamp><sample_count>{count}</sample_count></info>"
    )
    return _chunk(6, struct.pack("<I", sid) + xml.encode())
