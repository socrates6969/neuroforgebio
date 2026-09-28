"""File writers for synthetic recordings. EDF+/BDF/BrainVision/XDF are written by hand from the
format specifications (no dependencies beyond numpy); NWB needs pynwb and is CI-only.

Format references (from the published specifications; not re-opened in this session, so the
reader round-trips below are the real check):
- EDF / EDF+: edfplus.info/specs/edf.html and edfplus.info/specs/edfplus.html
- BDF: BioSemi 24-bit variant of EDF (biosemi.com/faq/file_format.htm)
- BrainVision: Brain Products "BrainVision Core Data Format 1.0"
- XDF: github.com/sccn/xdf/wiki/Specifications
Reader round-trips with MNE / pynwb / pyxdf run in CI (tools/synth/tests/test_readers.py).
"""

from __future__ import annotations

import json
import struct
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

START = datetime(2020, 1, 1, 0, 0, 0, tzinfo=UTC)  # fixed: keeps files deterministic


# ---------------------------------------------------------------- EDF+ / BDF
def _field(value: Any, width: int) -> bytes:
    s = str(value)
    if len(s) > width:
        raise ValueError(f"{s!r} does not fit in {width} chars")
    return s.ljust(width).encode("ascii")


def _num(x: float, width: int = 8) -> str:
    """Shortest decimal representation of x that fits in `width` chars."""
    if float(x).is_integer():
        s = str(int(x))
        if len(s) <= width:
            return s
    for prec in range(width, 0, -1):
        s = f"{x:.{prec}g}"
        if len(s) <= width and "e" not in s:
            return s
    raise ValueError(f"cannot fit {x} in {width} chars")


def _phys_range(row: np.ndarray) -> tuple[float, float]:
    lo, hi = float(np.floor(row.min())) - 1.0, float(np.ceil(row.max())) + 1.0
    return lo, hi


def _tal_records(events: list[dict[str, Any]], n_records: int) -> list[bytes]:
    """EDF+ annotation bytes per 1-s data record: time-keeping TAL + events in that second."""
    recs = []
    for r in range(n_records):
        tal = f"+{r}\x14\x14\x00".encode()
        for ev in events:
            if r <= ev["onset_s"] < r + 1:
                tal += f"+{ev['onset_s']:g}\x14{ev['label']}\x14\x00".encode()
        recs.append(tal)
    return recs


def _write_edf_like(
    path: Path,
    data_uv: np.ndarray,
    truth: dict[str, Any],
    *,
    bdf: bool,
) -> Path:
    sf = int(truth["sfreq"])
    chans = truth["channels"]
    n_ch, n = data_uv.shape
    if n % sf:
        raise ValueError("n_samples must be a whole number of 1-s records")
    n_rec = n // sf
    if bdf:
        dmin, dmax, width, ann_label = -8388608, 8388607, 3, "BDF Annotations"
    else:
        dmin, dmax, width, ann_label = -32768, 32767, 2, "EDF Annotations"

    tals = _tal_records(truth.get("events", []), n_rec)
    ann_bytes = max(len(t) for t in tals)
    ann_samples = -(-ann_bytes // width) + 1  # ceil, plus one sample of zero padding
    ns = n_ch + 1

    labels = [*chans, ann_label]
    ranges = [_phys_range(data_uv[i]) for i in range(n_ch)]
    hdr = bytearray()
    hdr += b"\xffBIOSEMI" if bdf else _field("0", 8)
    hdr += _field("X X X X", 80)  # EDF+ patient: code sex birthdate name, all unknown
    hdr += _field(f"Startdate {START.strftime('%d-%b-%Y').upper()} X X nf-synth", 80)
    hdr += _field(START.strftime("%d.%m.%y"), 8)
    hdr += _field(START.strftime("%H.%M.%S"), 8)
    hdr += _field(256 * (ns + 1), 8)
    hdr += _field("BDF+C" if bdf else "EDF+C", 44)
    hdr += _field(n_rec, 8)
    hdr += _field(1, 8)
    hdr += _field(ns, 4)
    hdr += b"".join(_field(lb, 16) for lb in labels)
    hdr += b"".join(_field("AgAgCl electrode" if i < n_ch else "", 80) for i in range(ns))
    hdr += b"".join(_field("uV" if i < n_ch else "", 8) for i in range(ns))
    hdr += b"".join(_field(_num(r[0]), 8) for r in ranges) + _field(-1, 8)
    hdr += b"".join(_field(_num(r[1]), 8) for r in ranges) + _field(1, 8)
    hdr += b"".join(_field(dmin, 8) for _ in range(ns))
    hdr += b"".join(_field(dmax, 8) for _ in range(ns))
    hdr += b"".join(_field("", 80) for _ in range(ns))
    hdr += b"".join(_field(sf, 8) for _ in range(n_ch)) + _field(ann_samples, 8)
    hdr += b"".join(_field("", 32) for _ in range(ns))
    assert len(hdr) == 256 * (ns + 1)

    # digital = (phys - pmin) / (pmax - pmin) * (dmax - dmin) + dmin
    dig = np.empty((n_ch, n), dtype=np.int64)
    for i, (pmin, pmax) in enumerate(ranges):
        d = np.round((data_uv[i] - pmin) / (pmax - pmin) * (dmax - dmin) + dmin)
        dig[i] = np.clip(d, dmin, dmax).astype(np.int64)

    body = bytearray()
    for r in range(n_rec):
        for i in range(n_ch):
            block = dig[i, r * sf : (r + 1) * sf]
            if bdf:
                u = (block & 0xFFFFFF).astype("<u4").tobytes()
                body += b"".join(u[k : k + 3] for k in range(0, len(u), 4))
            else:
                body += block.astype("<i2").tobytes()
        body += tals[r].ljust(ann_samples * width, b"\x00")
    path.write_bytes(bytes(hdr) + bytes(body))
    return path


def write_edf(path: str | Path, data_uv: np.ndarray, truth: dict[str, Any]) -> Path:
    """EDF+C, 16-bit, 1-s records, events as EDF+ annotations."""
    return _write_edf_like(Path(path), data_uv, truth, bdf=False)


def write_bdf(path: str | Path, data_uv: np.ndarray, truth: dict[str, Any]) -> Path:
    """BDF+C (24-bit BioSemi variant), same layout as write_edf."""
    return _write_edf_like(Path(path), data_uv, truth, bdf=True)


# ---------------------------------------------------------------- BrainVision
def write_brainvision(path: str | Path, data_uv: np.ndarray, truth: dict[str, Any]) -> Path:
    """Write <stem>.vhdr/.vmrk/.eeg (IEEE float32, multiplexed, uV). Returns the .vhdr path."""
    vhdr = Path(path).with_suffix(".vhdr")
    stem = vhdr.stem
    sf = truth["sfreq"]
    chans = truth["channels"]
    lines = [
        "Brain Vision Data Exchange Header File Version 1.0",
        "; Synthetic data written by nf-synth (not a real recording)",
        "",
        "[Common Infos]",
        "Codepage=UTF-8",
        f"DataFile={stem}.eeg",
        f"MarkerFile={stem}.vmrk",
        "DataFormat=BINARY",
        "DataOrientation=MULTIPLEXED",
        f"NumberOfChannels={len(chans)}",
        f"SamplingInterval={1e6 / sf:g}",
        "",
        "[Binary Infos]",
        "BinaryFormat=IEEE_FLOAT_32",
        "",
        "[Channel Infos]",
        *[f"Ch{i + 1}={c},,1,µV" for i, c in enumerate(chans)],
        "",
    ]
    vhdr.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    mk = [
        "Brain Vision Data Exchange Marker File, Version 1.0",
        "",
        "[Common Infos]",
        "Codepage=UTF-8",
        f"DataFile={stem}.eeg",
        "",
        "[Marker Infos]",
        "Mk1=New Segment,,1,1,0",
        *[
            f"Mk{k + 2}=Stimulus,S{ev['code']:>3},{ev['sample'] + 1},1,0"
            for k, ev in enumerate(truth.get("events", []))
        ],
        "",
    ]
    vhdr.with_suffix(".vmrk").write_text("\n".join(mk), encoding="utf-8", newline="\n")
    vhdr.with_suffix(".eeg").write_bytes(np.ascontiguousarray(data_uv.T, dtype="<f4").tobytes())
    return vhdr


# ---------------------------------------------------------------- XDF
def _varlen(n: int) -> bytes:
    if n < 256:
        return b"\x01" + struct.pack("<B", n)
    if n < 2**32:
        return b"\x04" + struct.pack("<I", n)
    return b"\x08" + struct.pack("<Q", n)


def _chunk(tag: int, content: bytes) -> bytes:
    return _varlen(len(content) + 2) + struct.pack("<H", tag) + content


def _xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def write_xdf(path: str | Path, data_uv: np.ndarray, truth: dict[str, Any]) -> Path:
    """XDF 1.0: stream 1 = EEG (float32), stream 2 = markers (string). Timestamps from t=0."""
    path = Path(path)
    sf = truth["sfreq"]
    chans = truth["channels"]
    n = data_uv.shape[1]
    events = truth.get("events", [])
    out = bytearray(b"XDF:")
    out += _chunk(1, b'<?xml version="1.0"?><info><version>1.0</version></info>')
    ch_xml = "".join(
        f"<channel><label>{_xml_escape(c)}</label><unit>microvolts</unit><type>EEG</type></channel>"
        for c in chans
    )
    eeg_hdr = (
        '<?xml version="1.0"?><info><name>nf-synth EEG</name><type>EEG</type>'
        f"<channel_count>{len(chans)}</channel_count><nominal_srate>{sf}</nominal_srate>"
        "<channel_format>float32</channel_format><created_at>0</created_at>"
        f"<desc><channels>{ch_xml}</channels></desc></info>"
    )
    mk_hdr = (
        '<?xml version="1.0"?><info><name>nf-synth Markers</name><type>Markers</type>'
        "<channel_count>1</channel_count><nominal_srate>0</nominal_srate>"
        "<channel_format>string</channel_format><created_at>0</created_at></info>"
    )
    out += _chunk(2, struct.pack("<I", 1) + eeg_hdr.encode())
    out += _chunk(2, struct.pack("<I", 2) + mk_hdr.encode())
    # EEG samples in blocks of one second; every sample carries its timestamp.
    x = np.ascontiguousarray(data_uv.T, dtype="<f4")
    for s0 in range(0, n, sf):
        block = bytearray(struct.pack("<I", 1) + _varlen(min(sf, n - s0)))
        for s in range(s0, min(s0 + sf, n)):
            block += b"\x08" + struct.pack("<d", s / sf) + x[s].tobytes()
        out += _chunk(3, bytes(block))
    if events:
        block = bytearray(struct.pack("<I", 2) + _varlen(len(events)))
        for ev in events:
            lab = ev["label"].encode()
            block += b"\x08" + struct.pack("<d", ev["onset_s"]) + _varlen(len(lab)) + lab
        out += _chunk(3, bytes(block))
    for sid, count, first, last in (
        (1, n, 0.0, (n - 1) / sf),
        (
            2,
            len(events),
            events[0]["onset_s"] if events else 0.0,
            events[-1]["onset_s"] if events else 0.0,
        ),
    ):
        footer = (
            f'<?xml version="1.0"?><info><first_timestamp>{first}</first_timestamp>'
            f"<last_timestamp>{last}</last_timestamp><sample_count>{count}</sample_count></info>"
        )
        out += _chunk(6, struct.pack("<I", sid) + footer.encode())
    path.write_bytes(bytes(out))
    return path


# ---------------------------------------------------------------- NWB (CI-only: needs pynwb)
def write_nwb(path: str | Path, data_uv: np.ndarray, truth: dict[str, Any]) -> Path:
    from pynwb import NWBHDF5IO, NWBFile  # noqa: PLC0415 - optional, CI-only dependency
    from pynwb.ecephys import ElectricalSeries  # noqa: PLC0415

    path = Path(path)
    nwb = NWBFile(
        session_description="nf-synth synthetic recording (not real data)",
        identifier=f"nf-synth-{truth['data_sha256'][:16]}",
        session_start_time=START,
    )
    dev = nwb.create_device(name="nf-synth")
    grp = nwb.create_electrode_group(
        name="scalp", description="synthetic 10-20", location="scalp", device=dev
    )
    for c in truth["channels"]:
        nwb.add_electrode(group=grp, location=c)
    region = nwb.create_electrode_table_region(list(range(len(truth["channels"]))), "all channels")
    nwb.add_acquisition(
        ElectricalSeries(
            name="ElectricalSeries",
            data=np.ascontiguousarray(data_uv.T, dtype="<f4"),
            electrodes=region,
            rate=float(truth["sfreq"]),
            conversion=1e-6,  # stored in uV; NWB unit is volts
        )
    )
    with NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)
    return path


def write_truth(path: str | Path, truth: dict[str, Any]) -> Path:
    path = Path(path)
    path.write_text(
        json.dumps(truth, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    return path


WRITERS = {
    "edf": (".edf", write_edf),
    "bdf": (".bdf", write_bdf),
    "vhdr": (".vhdr", write_brainvision),
    "xdf": (".xdf", write_xdf),
    "nwb": (".nwb", write_nwb),
}
