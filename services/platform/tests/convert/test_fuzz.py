"""2.5 acceptance / SEC-062 (short local run): corrupt inputs give clean typed errors, never crashes
or hangs. Seeded mutations of tools/synth fixtures: truncations, byte flips, targeted bad header
fields, bad sizes, path tricks and random bytes. Every case must either parse or raise a
`ConversionError` subclass within a time budget. The long fuzz run (Atheris) is CI/nightly.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest
from nf_platform.ingest.convert import ConversionError, read_source
from nf_platform.ingest.convert.bids import write_bids

SEED = 20260926
BUDGET_S = 5.0


def _check(path: Path, fmt: str) -> str:
    t = time.perf_counter()
    try:
        recs = read_source(path, fmt)
        outcome = "ok"
        assert recs and all(r.data.shape[1] > 0 for r in recs)
    except ConversionError as e:
        outcome = type(e).__name__
        assert str(e)  # a message, not an empty error
    # anything else propagates and fails the test (a "crash")
    assert time.perf_counter() - t < BUDGET_S, f"{path.name} took too long"
    return outcome


def _mutations(raw: bytes, rng: np.random.Generator, header_len: int) -> list[bytes]:
    n = len(raw)
    cases = [b"", raw[:1], raw[:8], raw[: min(n, 100)]]
    cuts = {header_len - 1, header_len, header_len + 1, n // 2, n - 1}
    cuts |= set(rng.integers(1, n, size=6).tolist())
    cases += [raw[:c] for c in sorted(cuts) if 0 < c < n]
    for _ in range(15):  # header byte flips
        b = bytearray(raw)
        for p in rng.integers(0, min(n, header_len + 64), size=rng.integers(1, 4)):
            b[p] = int(rng.integers(0, 256))
        cases.append(bytes(b))
    for _ in range(5):  # data byte flips
        b = bytearray(raw)
        for p in rng.integers(0, n, size=8):
            b[p] ^= 0xFF
        cases.append(bytes(b))
    cases.append(raw + rng.bytes(333))  # trailing garbage
    cases += [rng.bytes(int(k)) for k in (1, 17, 300, 4096)]
    return cases


def _edf_field(raw: bytes, start: int, width: int, value: str) -> bytes:
    b = bytearray(raw)
    b[start : start + width] = value.ljust(width)[:width].encode("latin-1")
    return bytes(b)


def _edf_targeted(raw: bytes) -> list[bytes]:
    ns = int(raw[252:256].decode())
    sig = 256
    cases = []
    for v in ("99999999", "-5", "abc", "0", "1e308"):
        cases.append(_edf_field(raw, 236, 8, v))  # number of records
    for v in ("9999", "0", "-1", "x"):
        cases.append(_edf_field(raw, 252, 4, v))  # number of signals
    for v in ("1", "999999", "nan"):
        cases.append(_edf_field(raw, 184, 8, v))  # header bytes
    for v in ("0", "-1", "nan", "inf", "1e-300"):
        cases.append(_edf_field(raw, 244, 8, v))  # record duration
    # per-signal fields of signal 0
    off_pmin = sig + ns * (16 + 80 + 8)
    off_dmin = off_pmin + ns * 16
    off_dmax = off_dmin + ns * 8
    off_nsamp = off_dmax + ns * 8 + ns * 80
    cases.append(_edf_field(raw, off_pmin, 8, "nan"))
    cases.append(
        _edf_field(raw, off_pmin, 8, raw[off_pmin + ns * 8 : off_pmin + ns * 8 + 8].decode())
    )
    cases.append(_edf_field(raw, off_dmin, 8, "40000"))
    cases.append(_edf_field(raw, off_dmax, 8, "-40000"))
    for v in ("0", "-3", "99999999", "7"):
        cases.append(_edf_field(raw, off_nsamp, 8, v))
    cases.append(_edf_field(raw, 0, 8, "1"))  # bad version
    cases.append(_edf_field(raw, 192, 44, "EDF+D"))  # discontinuous
    b = bytearray(raw)
    b[8] = 0xE9  # non-ASCII in patient field
    cases.append(bytes(b))
    return cases


@pytest.mark.parametrize("fmt", ["edf", "bdf"])
def test_fuzz_edf_bdf(fmt, fixture_file, tmp_path):
    rng = np.random.default_rng(SEED)
    raw = fixture_file(fmt).read_bytes()
    ns = int(raw[252:256].decode())
    outcomes: dict[str, int] = {}
    cases = _mutations(raw, rng, 256 * (ns + 1)) + _edf_targeted(raw)
    for i, case in enumerate(cases):
        p = tmp_path / f"case{i}.{fmt}"
        p.write_bytes(case)
        o = _check(p, fmt)
        outcomes[o] = outcomes.get(o, 0) + 1
    assert outcomes.get("CorruptFileError", 0) > len(cases) // 2, outcomes


def test_fuzz_xdf(fixture_file, tmp_path):
    pytest.importorskip("pyxdf")
    rng = np.random.default_rng(SEED + 1)
    raw = fixture_file("xdf").read_bytes()
    cases = _mutations(raw, rng, 600)
    # targeted: first chunk length huge, bad tag, undeclared stream id, bad channel_format
    b = bytearray(raw)
    b[4:6] = b"\x08\xff"
    cases.append(bytes(b))
    cases.append(raw.replace(b"<channel_format>float32<", b"<channel_format>float99<", 1))
    cases.append(raw.replace(b"<channel_count>8<", b"<channel_count>0<", 1))
    cases.append(raw.replace(b"<nominal_srate>256<", b"<nominal_srate>-1<", 1))
    cases.append(raw[:4] + raw[4:].replace(b"<?xml", b"<!DOCTYPE x [<!ENTITY a 'b'>]><?xml", 1))
    cases.append(raw.replace(b"XDF:", b"XDF;", 1))
    outcomes: dict[str, int] = {}
    for i, case in enumerate(cases):
        p = tmp_path / f"case{i}.xdf"
        p.write_bytes(case)
        o = _check(p, "xdf")
        outcomes[o] = outcomes.get(o, 0) + 1
    assert outcomes.get("CorruptFileError", 0) > len(cases) // 2, outcomes


def test_fuzz_brainvision(fixture_file, tmp_path):
    rng = np.random.default_rng(SEED + 2)
    vhdr = fixture_file("brainvision")
    text = vhdr.read_bytes()
    eeg = vhdr.with_suffix(".eeg").read_bytes()
    vmrk = vhdr.with_suffix(".vmrk").read_bytes()
    cases: list[tuple[bytes, bytes, bytes]] = []
    for m in _mutations(text, rng, len(text)):
        cases.append((m, eeg, vmrk))
    for m in _mutations(vmrk, rng, len(vmrk))[:20]:
        cases.append((text, eeg, m))
    for cut in (0, 1, 3, len(eeg) - 1, len(eeg) // 2 + 1):
        cases.append((text, eeg[:cut], vmrk))
    for old, new in [
        (b"NumberOfChannels=8", b"NumberOfChannels=0"),
        (b"NumberOfChannels=8", b"NumberOfChannels=99999"),
        (b"NumberOfChannels=8", b"NumberOfChannels=9"),
        (b"SamplingInterval=3906.25", b"SamplingInterval=0"),
        (b"SamplingInterval=3906.25", b"SamplingInterval=nan"),
        (b"BinaryFormat=IEEE_FLOAT_32", b"BinaryFormat=IEEE_FLOAT_64"),
        (b"DataFormat=BINARY", b"DataFormat=ASCII"),
        (b"DataOrientation=MULTIPLEXED", b"DataOrientation=SIDEWAYS"),
        (b"DataFile=src-brainvision.eeg", b"DataFile=../../../Windows/win.ini"),
        (b"DataFile=src-brainvision.eeg", b"DataFile=C:\\Windows\\win.ini"),
        (b"MarkerFile=src-brainvision.vmrk", b"MarkerFile=..\\x.vmrk"),
        (b",,1,", b",,0,"),
        (b",,1,", b",,abc,"),
        (b"Ch8=", b"Cx8="),
    ]:
        assert old in text or old in vmrk, old
        cases.append((text.replace(old, new), eeg, vmrk))
    cases.append((text, eeg, vmrk.replace(b"Stimulus,S  1,", b"Stimulus,S  1,-5", 1)))
    outcomes: dict[str, int] = {}
    for i, (h, d, m) in enumerate(cases):
        folder = tmp_path / f"c{i}"
        folder.mkdir()
        (folder / "src-brainvision.vhdr").write_bytes(h)
        (folder / "src-brainvision.eeg").write_bytes(d)
        (folder / "src-brainvision.vmrk").write_bytes(m)
        o = _check(folder / "src-brainvision.vhdr", "brainvision")
        outcomes[o] = outcomes.get(o, 0) + 1
    assert outcomes.get("CorruptFileError", 0) > len(cases) // 3, outcomes


def test_fuzz_bids_sidecars(fixture_file, tmp_path):
    from nf_platform.ingest.convert import read_source as rs

    rec = rs(fixture_file("edf"))[0]
    rec.meta["bids"] = {"entities": {"sub": "01", "task": "rest"}, "data_format": "edf"}
    good = tmp_path / "good"
    data = write_bids(good, rec)
    files = {
        "desc": good / "dataset_description.json",
        "json": data.with_name("sub-01_task-rest_eeg.json"),
        "chan": data.with_name("sub-01_task-rest_channels.tsv"),
        "ev": data.with_name("sub-01_task-rest_events.tsv"),
        "part": good / "participants.tsv",
    }
    bad_contents = {
        "desc": [b"", b"{", b"[]", b'{"Name": "x"}', b"\xff\xfe"],
        "json": [b"{", b'{"SamplingFrequency": 999}', b"null"],
        "chan": [b"name\ttype\nFp1\tEEG\n", b"name\ttype\tunits\nFp1\tEEG\tuV\textra\n", b""],
        "ev": [b"onset\tduration\nabc\t1\n", b"duration\n1\n", b"onset\tduration\n1\n"],
        "part": [b"participant_id\tdob\nsub-01\t1970-01-01\n"],
    }
    outcomes: dict[str, int] = {}
    for key, variants in bad_contents.items():
        for j, content in enumerate(variants):
            import shutil

            case = tmp_path / f"{key}{j}"
            shutil.copytree(good, case)
            target = case / files[key].relative_to(good)
            target.write_bytes(content)
            o = _check(case / data.relative_to(good), "bids")
            outcomes[o] = outcomes.get(o, 0) + 1
    assert outcomes.get("ok", 0) == 0, outcomes
    # a data file outside any BIDS dataset, and a non-BIDS name
    lone = tmp_path / "lone" / "sub-01_task-x_eeg.edf"
    lone.parent.mkdir()
    lone.write_bytes(data.read_bytes())
    assert _check(lone, "bids") == "CorruptFileError"
