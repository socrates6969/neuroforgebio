"""2.5 acceptance: XDF multi-stream clock offsets are preserved (synthetic XDF, known offsets).

The fixture is written here byte by byte from the XDF 1.0 chunk layout (independent of the
converter's own writer) and checked against pyxdf, the maintained reader.
"""

from __future__ import annotations

import struct

import numpy as np
import pytest
from nf_platform.ingest.convert import convert_file, export_recording, load_source
from nf_platform.signals import read_array, read_window

pyxdf = pytest.importorskip("pyxdf")


def _vl(n: int) -> bytes:
    return b"\x01" + struct.pack("<B", n) if n < 256 else b"\x04" + struct.pack("<I", n)


def _chunk(tag: int, content: bytes) -> bytes:
    return _vl(len(content) + 2) + struct.pack("<H", tag) + content


def _hdr(sid, name, typ, nch, srate, fmt, labels):
    chans = "".join(f"<channel><label>{c}</label><unit>uV</unit></channel>" for c in labels)
    xml = (
        f'<?xml version="1.0"?><info><name>{name}</name><type>{typ}</type>'
        f"<channel_count>{nch}</channel_count><nominal_srate>{srate}</nominal_srate>"
        f"<channel_format>{fmt}</channel_format><created_at>0</created_at>"
        f"<desc><channels>{chans}</channels></desc></info>"
    )
    return _chunk(2, struct.pack("<I", sid) + xml.encode())


# Known ground truth
EEG = {"sid": 3, "n": 600, "srate": 100.0, "t0": 50.0, "nch": 4}
AUX = {"sid": 7, "n": 300, "srate": 50.0, "t0": 1000.0, "nch": 2}
EEG_OFFSETS = [(50.0 + 5 * k, -12.5 + 1e-4 * k) for k in range(3)]
AUX_OFFSETS = [(1000.0 + 5 * k, 3.25 - 2e-4 * k) for k in range(3)]
MRK_OFFSETS = [(50.0, -12.5), (55.0, -12.4999)]
MARKERS = [(51.0, "start"), (53.5, "stim/1"), (55.25, "end")]


def build_xdf(path, rng) -> dict:
    eeg = rng.standard_normal((EEG["n"], EEG["nch"])).astype("<f4")
    aux = rng.integers(-3000, 3000, size=(AUX["n"], AUX["nch"])).astype("<i2")
    out = bytearray(b"XDF:")
    out += _chunk(1, b'<?xml version="1.0"?><info><version>1.0</version></info>')
    out += _hdr(EEG["sid"], "eeg", "EEG", 4, 100, "float32", ["Fz", "Cz", "Pz", "Oz"])
    out += _hdr(AUX["sid"], "aux", "MISC", 2, 50, "int16", ["x", "y"])
    out += _hdr(9, "markers", "Markers", 1, 0, "string", ["m"])
    # EEG: every sample stamped, blocks of 37 samples, interleaved with offsets
    for s0 in range(0, EEG["n"], 37):
        body = bytearray(struct.pack("<I", EEG["sid"]) + _vl(min(37, EEG["n"] - s0)))
        for s in range(s0, min(EEG["n"], s0 + 37)):
            body += b"\x08" + struct.pack("<d", EEG["t0"] + s / EEG["srate"]) + eeg[s].tobytes()
        out += _chunk(3, bytes(body))
    # AUX: only the first sample of each block is stamped (the reader deduces the rest)
    for s0 in range(0, AUX["n"], 50):
        body = bytearray(struct.pack("<I", AUX["sid"]) + _vl(50))
        for s in range(s0, s0 + 50):
            stamp = (
                b"\x08" + struct.pack("<d", AUX["t0"] + s / AUX["srate"]) if s == s0 else b"\x00"
            )
            body += stamp + aux[s].tobytes()
        out += _chunk(3, bytes(body))
    body = bytearray(struct.pack("<I", 9) + _vl(len(MARKERS)))
    for t, lab in MARKERS:
        body += b"\x08" + struct.pack("<d", t) + _vl(len(lab)) + lab.encode()
    out += _chunk(3, bytes(body))
    for sid, offs in ((EEG["sid"], EEG_OFFSETS), (AUX["sid"], AUX_OFFSETS), (9, MRK_OFFSETS)):
        for t, v in offs:
            out += _chunk(4, struct.pack("<Idd", sid, t, v))
    path.write_bytes(bytes(out))
    return {"eeg": eeg, "aux": aux}


def _by_id(streams):
    return {int(s["info"]["stream_id"]): s for s in streams}


def test_clock_offsets_preserved(tmp_path, store, rng):
    src = tmp_path / "multi.xdf"
    truth = build_xdf(src, rng)
    res = convert_file(src, store, "x")
    assert res.recording_ids == ["x-s3", "x-s7"]

    # 1. canonical copy holds the exact recorded offsets and original timestamps
    assert np.array_equal(read_array(store, "x-s3", "clock_offsets"), np.array(EEG_OFFSETS))
    assert np.array_equal(read_array(store, "x-s7", "clock_offsets"), np.array(AUX_OFFSETS))
    ts3 = read_array(store, "x-s3", "timestamps")
    assert np.array_equal(ts3, EEG["t0"] + np.arange(EEG["n"]) / EEG["srate"])
    ts7 = read_array(store, "x-s7", "timestamps")
    np.testing.assert_allclose(ts7, AUX["t0"] + np.arange(AUX["n"]) / AUX["srate"], atol=1e-9)
    assert np.array_equal(read_window(store, "x-s3", 0, 1e6), truth["eeg"].T)
    assert np.array_equal(read_window(store, "x-s7", 0, 1e6), truth["aux"].T)
    mk = load_source(store, "x-s3").meta["xdf"]["marker_streams"]
    assert mk[0]["clock_offsets"] == [list(o) for o in MRK_OFFSETS]
    assert [(t, v[0]) for t, v in mk[0]["samples"]] == MARKERS

    # 2. export writes the same ClockOffset chunks: pyxdf's synchronised clocks agree
    out = export_recording(store, res.recording_ids, "xdf", tmp_path / "out.xdf")
    for sync in (False, True):
        a, _ = pyxdf.load_xdf(str(src), synchronize_clocks=sync, dejitter_timestamps=False)
        b, _ = pyxdf.load_xdf(str(out), synchronize_clocks=sync, dejitter_timestamps=False)
        a, b = _by_id(a), _by_id(b)
        assert set(a) == set(b) == {3, 7, 9}
        for sid in (3, 7, 9):
            np.testing.assert_allclose(a[sid]["time_stamps"], b[sid]["time_stamps"], atol=1e-9)
            assert a[sid]["clock_times"] == b[sid]["clock_times"]
            assert a[sid]["clock_values"] == b[sid]["clock_values"]
        if sync:  # sanity: synchronisation applied the known offsets
            np.testing.assert_allclose(b[3]["time_stamps"][:10] - ts3[:10], -12.5, atol=1e-3)
            np.testing.assert_allclose(b[7]["time_stamps"][:10] - ts7[:10], 3.25, atol=1e-3)
