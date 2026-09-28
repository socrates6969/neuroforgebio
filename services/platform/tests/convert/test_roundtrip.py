"""2.5 acceptance: source -> canonical Zarr -> export (same format) -> re-read matches.

Local: EDF, BDF, BrainVision, XDF, BIDS(EDF/BrainVision) with the nf readers, pyedflib (EDFlib)
and pyxdf as independent reference readers. CI-only (skipped here when absent): MNE, mne-bids,
pynwb (NWB), bids-validator.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess

import numpy as np
import pytest
from nf_platform.ingest.convert import (
    IdentifierPolicyError,
    convert_file,
    export_recording,
    load_source,
    read_source,
)
from nf_platform.ingest.convert.bids import write_bids
from nf_platform.ingest.convert.edf import read_edf
from nf_platform.signals import open_recording, read_window


def edf_quantum(pmin: float, pmax: float, bdf: bool) -> float:
    return (pmax - pmin) / ((2**24 - 1) if bdf else (2**16 - 1))


def _canonical_attrs_text(store, rid) -> str:
    return json.dumps(open_recording(store, rid).attrs, ensure_ascii=False)


# ---------------------------------------------------------------- EDF / BDF
@pytest.mark.parametrize("fmt", ["edf", "bdf"])
def test_edf_bdf_roundtrip(fmt, fixture_file, store, synth, tmp_path):
    data_uv, truth = synth
    src = fixture_file(fmt)
    res = convert_file(src, store, "rec1")
    assert res.recording_ids == ["rec1"]
    ref = res.refs[0]
    assert ref.dtype == ("int32" if fmt == "bdf" else "int16")
    assert ref.shape == (data_uv.shape[1], data_uv.shape[0])

    # canonical physical values match the synthetic truth within one quantisation step
    phys = read_window(store, "rec1", 0, 100, physical=True)
    orig = read_edf(src)
    for i, ch in enumerate(orig.channels):
        e = ch.extra["edf"]
        q = edf_quantum(e["pmin"], e["pmax"], fmt == "bdf")
        assert np.max(np.abs(phys[i] - data_uv[i])) <= q * 0.51 + 1e-9

    out = export_recording(store, "rec1", fmt, tmp_path / f"out.{fmt}")
    back = read_edf(out)
    assert np.array_equal(back.data, orig.data)  # digital values bit-exact
    assert [c.name for c in back.channels] == [c.name for c in orig.channels]
    for a, b in zip(back.channels, orig.channels, strict=True):
        assert a.extra["edf"]["pmin"] == b.extra["edf"]["pmin"]
        assert a.extra["edf"]["dmax"] == b.extra["edf"]["dmax"]
        assert a.unit == b.unit
    assert back.sfreq == orig.sfreq == truth["sfreq"]
    assert [(e.onset_s, e.label) for e in back.events] == [
        (e.onset_s, e.label) for e in orig.events
    ]
    assert [e.label for e in orig.events] == [ev["label"] for ev in truth["events"]]


@pytest.mark.parametrize("fmt", ["edf", "bdf"])
def test_edf_bdf_independent_reader_pyedflib(fmt, fixture_file, store, tmp_path):
    pyedflib = pytest.importorskip("pyedflib")
    src = fixture_file(fmt)
    convert_file(src, store, "r")
    out = export_recording(store, "r", fmt, tmp_path / f"out.{fmt}")
    ours = read_edf(src)
    for path in (src, out):
        with pyedflib.EdfReader(str(path)) as f:
            labels = f.getSignalLabels()
            assert labels == [c.name for c in ours.channels]
            for i in range(len(labels)):
                dig = f.readSignal(i, digital=True)
                assert np.array_equal(dig, ours.data[i])
                phys = f.readSignal(i)
                np.testing.assert_allclose(
                    phys,
                    ours.data[i] * ours.channels[i].scale + ours.channels[i].offset,
                    rtol=0,
                    atol=1e-6 * max(1.0, float(np.abs(phys).max())),
                )
            onsets, _, texts = f.readAnnotations()
            assert list(texts) == [e.label for e in ours.events]


# ---------------------------------------------------------------- BrainVision
def test_brainvision_roundtrip_exact(fixture_file, store, synth, tmp_path):
    data_uv, truth = synth
    src = fixture_file("brainvision")
    convert_file(src, store, "bv")
    got = read_window(store, "bv", 0, 100)
    assert got.dtype == np.float32
    assert np.array_equal(got, data_uv.astype(np.float32))
    out = export_recording(store, "bv", "brainvision", tmp_path / "out.vhdr")
    a, b = read_source(src)[0], read_source(out)[0]
    assert np.array_equal(a.data, b.data)
    assert [c.name for c in a.channels] == [c.name for c in b.channels]
    assert [c.unit for c in b.channels] == ["µV"] * len(b.channels)
    assert [(e.onset_s, e.label) for e in a.events] == [(e.onset_s, e.label) for e in b.events]
    stim = [e for e in b.events if e.kind == "Stimulus"]
    assert [round(e.onset_s * 256) for e in stim] == [ev["sample"] for ev in truth["events"]]


# ---------------------------------------------------------------- XDF
def test_xdf_roundtrip_with_pyxdf(fixture_file, store, synth, tmp_path):
    pyxdf = pytest.importorskip("pyxdf")
    data_uv, truth = synth
    src = fixture_file("xdf")
    res = convert_file(src, store, "x")
    assert res.recording_ids == ["x-s1"]
    assert np.array_equal(read_window(store, "x-s1", 0, 100), data_uv.astype(np.float32))
    out = export_recording(store, res.recording_ids, "xdf", tmp_path / "out.xdf")
    kw = {"synchronize_clocks": False, "dejitter_timestamps": False}
    a, _ = pyxdf.load_xdf(str(src), **kw)
    b, _ = pyxdf.load_xdf(str(out), **kw)
    by_id = lambda streams: {int(s["info"]["stream_id"]): s for s in streams}  # noqa: E731
    a, b = by_id(a), by_id(b)
    assert set(a) == set(b) == {1, 2}
    assert np.array_equal(a[1]["time_series"], b[1]["time_series"])
    assert np.array_equal(a[1]["time_stamps"], b[1]["time_stamps"])
    assert a[2]["time_series"] == b[2]["time_series"]
    assert np.array_equal(a[2]["time_stamps"], b[2]["time_stamps"])
    assert b[1]["info"]["name"] == a[1]["info"]["name"]


# ---------------------------------------------------------------- BIDS
@pytest.mark.parametrize("data_format", ["edf", "brainvision"])
def test_bids_roundtrip(data_format, fixture_file, store, tmp_path):
    base = read_source(fixture_file("edf" if data_format == "edf" else "brainvision"))[0]
    base.meta["bids"] = {
        "entities": {"sub": "01", "ses": "a", "task": "rest", "run": "1"},
        "data_format": data_format,
        "participant": {"age": "30", "sex": "F"},
        "eeg_json": {"PowerLineFrequency": 50, "EEGReference": "Cz"},
    }
    src = write_bids(tmp_path / "bids-in", base)
    assert (
        src.name == f"sub-01_ses-a_task-rest_run-1_eeg.{'edf' if data_format == 'edf' else 'vhdr'}"
    )
    res = convert_file(src, store, "b")
    rec = load_source(store, "b")
    assert rec.meta["bids"]["entities"]["task"] == "rest"
    assert rec.meta["bids"]["participant"] == {"participant_id": "sub-01", "age": "30", "sex": "F"}
    out = export_recording(store, "b", "bids", tmp_path / "bids-out")
    a, b = read_source(src)[0], read_source(out)[0]
    assert np.array_equal(a.data, b.data)
    assert [(c.name, c.modality, c.unit) for c in a.channels] == [
        (c.name, c.modality, c.unit) for c in b.channels
    ]
    assert [(e.onset_s, e.label) for e in a.events] == [(e.onset_s, e.label) for e in b.events]
    assert res.provenance.source_format == "bids"


def _bids_with_participants(tmp_path, fixture_file, header: str, row: str):
    rec = read_source(fixture_file("edf"))[0]
    rec.meta["bids"] = {"entities": {"sub": "07", "task": "rest"}, "data_format": "edf"}
    src = write_bids(tmp_path / "bids", rec)
    (tmp_path / "bids" / "participants.tsv").write_text(f"{header}\n{row}\n", encoding="utf-8")
    return src


def test_bids_identifier_columns_rejected(tmp_path, fixture_file, store):
    """SEC-140: a name column in participants.tsv is flagged and rejected by default."""
    src = _bids_with_participants(
        tmp_path, fixture_file, "participant_id\tname\tage", "sub-07\tJane Q Synthetic\t40"
    )
    with pytest.raises(IdentifierPolicyError):
        convert_file(src, store, "p")
    res = convert_file(src, store, "p", allow_identified=True)
    assert res.identifiers["bids_name"] == "Jane Q Synthetic"
    assert "Jane Q" not in _canonical_attrs_text(store, "p")
    out = export_recording(store, "p", "bids", tmp_path / "out")
    exported = "".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in (tmp_path / "out").rglob("*")
        if p.is_file()
    )
    assert "Jane Q" not in exported
    assert "age" in (tmp_path / "out" / "participants.tsv").read_text()
    assert out.exists()


# ---------------------------------------------------------------- SEC-141 header scrubbing
def test_edf_header_identifiers_scrubbed(fixture_file, store, tmp_path):
    src = fixture_file("edf")
    raw = bytearray(src.read_bytes())
    raw[8:88] = "MRN-99812 F 02-MAR-1971 Jane_Synthetic_Doe".ljust(80).encode()
    raw[88:168] = "Startdate 01-JAN-2020 EXAM-77 Dr_Synthetic device-1".ljust(80).encode()
    src.write_bytes(bytes(raw))
    res = convert_file(src, store, "s")
    assert "Jane_Synthetic_Doe" in res.identifiers["edf_patient"]
    assert "Dr_Synthetic" in res.identifiers["edf_recording"]
    text = _canonical_attrs_text(store, "s")
    for secret in ("Jane_Synthetic_Doe", "MRN-99812", "Dr_Synthetic", "EXAM-77"):
        assert secret not in text
    out = export_recording(store, "s", "edf", tmp_path / "scrubbed.edf")
    head = out.read_bytes()[:256]
    for secret in (b"Jane_Synthetic_Doe", b"MRN-99812", b"Dr_Synthetic", b"EXAM-77"):
        assert secret not in head
    assert head[8:88].strip() == b"X X X X"


# ---------------------------------------------------------------- provenance + governance
def test_provenance_and_governance(fixture_file, store):
    src = fixture_file("edf")
    raw = bytearray(src.read_bytes())
    # rename channel 2 to an ECG label to check modality defaults (label field of signal 2)
    ns = int(raw[252:256].decode())
    off = 256 + 16 * 1
    raw[off : off + 16] = b"ECG II".ljust(16)
    src.write_bytes(bytes(raw))
    res = convert_file(src, store, "g", raw_object_key="raw/t/g.edf")
    p = res.provenance
    assert p.raw_sha256 == hashlib.sha256(src.read_bytes()).hexdigest()
    assert p.recording_ids == ("g",) and p.converter.startswith("nf-convert@")
    assert "--convert@" in p.edge and p.to_dict()["activity"]["type"] == "convert"
    chans = open_recording(store, "g").attrs["channels"]
    assert len(chans) == ns - 1
    assert chans[0]["modality"] == "EEG" and chans[0]["nervous_system"] == "central"
    assert chans[0]["derived_from_non_neural"] is False
    assert chans[1]["name"] == "ECG II" and chans[1]["modality"] == "ECG"
    assert chans[1]["nervous_system"] == "unknown" and chans[1]["derived_from_non_neural"] is True
    assert all(c["governance_source"] == "default-by-modality" for c in chans)
    assert all(c["sampling_rate"] == 256.0 for c in chans)


# ---------------------------------------------------------------- CI-only reference readers
@pytest.mark.parametrize("fmt,ext", [("edf", "edf"), ("bdf", "bdf"), ("brainvision", "vhdr")])
def test_exports_open_in_mne(fmt, ext, fixture_file, store, tmp_path):
    mne = pytest.importorskip("mne", reason="CI-only: MNE is in the readers extra")
    src = fixture_file(fmt)
    convert_file(src, store, "m")
    out = export_recording(store, "m", fmt, tmp_path / f"out.{ext}")
    reader = {
        "edf": mne.io.read_raw_edf,
        "bdf": mne.io.read_raw_bdf,
        "brainvision": mne.io.read_raw_brainvision,
    }[fmt]
    a = reader(str(src), preload=True, verbose="error").get_data()
    b = reader(str(out), preload=True, verbose="error").get_data()
    np.testing.assert_allclose(a, b, rtol=0, atol=1e-9)


def test_nwb_roundtrip(synth, store, tmp_path):
    pynwb = pytest.importorskip("pynwb", reason="CI-only: pynwb is in the readers extra")
    from nf_synth.writers import write_nwb

    data_uv, truth = synth
    src = write_nwb(tmp_path / "src.nwb", data_uv, truth)
    res = convert_file(src, store, "n")
    out = export_recording(store, res.recording_ids, "nwb", tmp_path / "out.nwb")
    with pynwb.NWBHDF5IO(str(src), "r") as a, pynwb.NWBHDF5IO(str(out), "r") as b:
        sa = next(iter(a.read().acquisition.values()))
        sb = next(iter(b.read().acquisition.values()))
        assert np.array_equal(np.asarray(sa.data[:]), np.asarray(sb.data[:]))
        assert sa.rate == sb.rate
    phys = read_window(store, res.recording_ids[0], 0, 100, physical=True)
    np.testing.assert_allclose(phys, data_uv * 1e-6, rtol=1e-6, atol=1e-12)


def test_bids_export_passes_validator(fixture_file, store, tmp_path):
    exe = shutil.which("bids-validator")
    if not exe:
        pytest.skip("CI-only: bids-validator not installed")
    convert_file(fixture_file("edf"), store, "v")
    export_recording(store, "v", "bids", tmp_path / "ds")
    r = subprocess.run([exe, str(tmp_path / "ds")], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]


def test_bids_export_reads_with_mne_bids(fixture_file, store, tmp_path):
    mne_bids = pytest.importorskip("mne_bids", reason="CI-only: mne-bids is in the readers extra")
    convert_file(fixture_file("edf"), store, "mb")
    export_recording(store, "mb", "bids", tmp_path / "ds")
    path = mne_bids.BIDSPath(subject="01", task="nfexport", datatype="eeg", root=tmp_path / "ds")
    raw = mne_bids.read_raw_bids(path, verbose="error")
    assert raw.info["sfreq"] == 256.0
