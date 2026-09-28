"""Offline pieces: provenance recorder, Zarr v3 interop with zarr-python, chunk cache."""

from __future__ import annotations

import json

import neuroforge as nf
import numpy as np
import pytest
import zarr
from neuroforge import _native
from neuroforge.local import ChunkCache, ProvRecorder, read_signal, write_signal


def test_prov_recorder_chain_verifies_with_the_reference(tmp_path):
    r = ProvRecorder(tmp_path / "prov", chain="local:lab-pc-1")
    raw = nf.canonical.blob_id(b"raw bytes")
    s0, id0 = r.record(
        [
            {"type": "entity", "id": "e1", "label": "raw", "content": raw},
            {"type": "activity", "id": "a1", "label": "acquire"},
            {"type": "edge", "rel": "wasGeneratedBy", "from": "e1", "to": "a1"},
        ]
    )
    s1, id1 = r.record([{"type": "activity", "id": "a2", "label": "filter"}])
    assert (s0, s1) == (0, 1)
    batches = [json.loads(p) for _, _, p in r.pending()]
    assert nf.canonical.verify_chain(batches) == [id0, id1]
    assert batches[1]["prev"] == id0 and batches[0]["tenant"] == "local:lab-pc-1"
    sent = []
    assert r.sync(lambda payload, bid: sent.append(bid)) == 2
    assert sent == [id0, id1] and r.pending() == []
    # reopening re-verifies; editing the file breaks it
    assert len(ProvRecorder(tmp_path / "prov", chain="local:lab-pc-1")) == 2
    f = tmp_path / "prov" / "local_lab-pc-1.provchain.jsonl"
    f.write_text(f.read_text("utf-8").replace('"acquire"', '"acquirE"'), "utf-8")
    with pytest.raises(_native.CoreError):
        ProvRecorder(tmp_path / "prov", chain="local:lab-pc-1")
    with pytest.raises(ValueError):
        ProvRecorder(tmp_path / "p2", chain="c").record([{"type": "not-a-prov-type"}])


def test_nf_core_zarr_is_readable_by_zarr_python(tmp_path):
    data = (np.arange(1000 * 3).reshape(1000, 3) % 2000 - 1000).astype(np.int16)
    ts = 5.0 + np.arange(1000) / 250.0
    write_signal(
        tmp_path / "z",
        "rec-1",
        data,
        250.0,
        ["Cz", "Pz", "Oz"],
        "uV",
        chunk_s=1.0,
        chunk_channels=2,
        timestamps=ts,
    )
    g = zarr.open_group(str(tmp_path / "z"), path="rec-1", mode="r")
    assert g.attrs["nf_signal"]["layout"] == "nf-signal/1"
    a = zarr.open_array(str(tmp_path / "z"), path="rec-1/data/0", mode="r")
    assert a.chunks == (250, 2) and a.dtype == np.int16
    np.testing.assert_array_equal(a[...], data)
    np.testing.assert_array_equal(
        zarr.open_array(str(tmp_path / "z"), path="rec-1/timestamps", mode="r")[...], ts
    )
    np.testing.assert_array_equal(read_signal(tmp_path / "z", "rec-1", 100, 600), data[100:600])


def test_zarr_python_uncompressed_array_is_readable_by_nf_core(tmp_path):
    x = np.random.default_rng(1).standard_normal((37, 5)).astype(np.float32)
    z = zarr.create_array(
        str(tmp_path / "zp"),
        name="arr",
        shape=x.shape,
        chunks=(10, 2),
        dtype="float32",
        compressors=None,
    )
    z[...] = x
    dtype, shape, raw = _native.read_region(str(tmp_path / "zp"), "arr", [3, 1], [30, 5])
    got = np.frombuffer(raw, dtype="<f4").reshape(shape)
    np.testing.assert_array_equal(got, x[3:30, 1:5])
    # compressed arrays are refused, not misread
    zarr.create_array(str(tmp_path / "zc"), name="arr", shape=(4,), chunks=(2,), dtype="int16")[
        ...
    ] = 1
    with pytest.raises(_native.CoreError, match="unsupported codec"):
        _native.read_region(str(tmp_path / "zc"), "arr", [0], [4])


def test_chunk_cache_verifies_entries(tmp_path):
    c = ChunkCache(tmp_path / "cache", max_bytes=10_000)
    a = np.arange(12, dtype=np.float64).reshape(3, 4)
    cid = c.put(a)
    assert cid == nf.canonical.chunk_id(a)
    np.testing.assert_array_equal(c.get(cid), a)
    f = next((tmp_path / "cache").rglob("*.nfchunk"))
    b = bytearray(f.read_bytes())
    b[-1] ^= 0xFF
    f.write_bytes(bytes(b))
    assert c.get(cid) is None and not f.exists()
