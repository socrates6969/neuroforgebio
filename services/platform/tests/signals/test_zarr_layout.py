"""2.4 acceptance: exact window round-trip, pyramid vs reference, encrypted chunks, bench."""

from __future__ import annotations

import json
import os

import numpy as np
import pytest
from nf_platform.signals import (
    EncryptedZarrStore,
    SignalError,
    bench,
    open_recording,
    read_array,
    read_window,
    write_recording,
)
from nf_platform.storage import InMemoryKeyStore, Keyring, LocalKms, LocalObjectStore
from nf_platform.storage.keyring import SubjectKeyUnavailable
from zarr.storage import MemoryStore

RNG = np.random.default_rng(42)
NAMES = [f"ch{i}" for i in range(6)]


def _enc_store(tmp_path, subject="sub-1", keyring=None):
    keyring = keyring or Keyring(LocalKms(), InMemoryKeyStore())
    return EncryptedZarrStore(LocalObjectStore(tmp_path), keyring, "t1", subject, "recs")


def _decimated(x: np.ndarray, d: int):
    """Independent reference: pad to a multiple of d with NaN and reduce with nan-aware numpy."""
    n_ch, n = x.shape
    m = -(-n // d) * d
    pad = np.full((n_ch, m), np.nan)
    pad[:, :n] = x
    blocks = pad.reshape(n_ch, m // d, d)
    return np.nanmean(blocks, axis=2), np.nanmin(blocks, axis=2), np.nanmax(blocks, axis=2)


@pytest.mark.parametrize("dtype", ["int16", "int32", "int8", "uint16"])
def test_int_roundtrip_exact(tmp_path, dtype):
    info = np.iinfo(dtype)
    x = RNG.integers(info.min, info.max, size=(6, 5003), endpoint=True).astype(dtype)
    store = _enc_store(tmp_path)
    ref = write_recording(store, "r", x, 500.0, NAMES, "uV", chunk_s=1.3, chunk_channels=4)
    assert ref.shape == (5003, 6)
    full = read_window(store, "r", 0, 11)
    assert np.array_equal(full, x) and full.dtype.kind == "i"
    # arbitrary windows and channel subsets
    for start, end, chans in [(1.0, 2.0, None), (0.123, 0.5, ["ch5", "ch0"]), (9.9, 10.1, [2])]:
        i0, i1 = int(np.ceil(start * 500 - 1e-9)), min(5003, int(np.ceil(end * 500 - 1e-9)))
        idx = [NAMES.index(c) if isinstance(c, str) else c for c in chans] if chans else range(6)
        got = read_window(store, "r", start, end, chans)
        assert np.array_equal(got, x[list(idx), i0:i1])


@pytest.mark.parametrize("dtype,tol", [("float32", 0.0), ("float64", 0.0)])
def test_float_roundtrip(tmp_path, dtype, tol):
    x = (RNG.standard_normal((6, 3000)) * 50).astype(dtype)
    store = MemoryStore()
    write_recording(store, "r", x, 256.0, NAMES, "uV")
    got = read_window(store, "r", 0, 100)
    assert got.dtype == np.dtype(dtype)
    np.testing.assert_allclose(got, x, rtol=0, atol=tol)


def test_physical_scaling(tmp_path):
    x = RNG.integers(-100, 100, size=(2, 100)).astype(np.int16)
    store = MemoryStore()
    write_recording(store, "r", x, 100.0, ["a", "b"], ["uV", "mV"], scale=[0.5, 2.0], offset=1.0)
    phys = read_window(store, "r", 0, 1, physical=True)
    np.testing.assert_allclose(phys, x * np.array([[0.5], [2.0]]) + 1.0)
    info = open_recording(store, "r")
    assert info.signal["units"] == ["uV", "mV"] and info.sfreq == 100.0


@pytest.mark.parametrize("n", [4096, 5003, 70001])
def test_pyramid_levels_match_decimated_reference(tmp_path, n):
    x = RNG.integers(-2000, 2000, size=(6, n)).astype(np.int16)
    store = MemoryStore()
    ref = write_recording(store, "r", x, 1000.0, NAMES, "uV", chunk_s=1.0, pyramid_min_samples=64)
    info = open_recording(store, "r")
    levels = info.signal["pyramid"]["levels"]
    assert ref.levels == len(levels) >= 3
    for lv in levels[1:]:
        k, d = lv["level"], lv["decimation"]
        assert d == 4**k
        mean, mn, mx = _decimated(x.astype(np.float64), d)
        got = read_window(store, "r", 0, n / 1000 + 1, level=k)
        np.testing.assert_allclose(got, mean, rtol=1e-6, atol=1e-3)
        assert np.array_equal(read_window(store, "r", 0, 1e9, level=k, kind="min"), mn)
        assert np.array_equal(read_window(store, "r", 0, 1e9, level=k, kind="max"), mx)
        # windowed read at level k
        s0 = 3.0
        j0 = int(np.ceil(s0 * 1000 / d - 1e-9))
        j1 = min(mean.shape[1], int(np.ceil((s0 + 2.0) * 1000 / d - 1e-9)))
        got_w = read_window(store, "r", s0, s0 + 2.0, level=k)
        np.testing.assert_allclose(got_w, mean[:, j0:j1], rtol=1e-6, atol=1e-3)


def test_zarr_at_rest_is_ciphertext_and_shreddable(tmp_path):
    keyring = Keyring(LocalKms(), InMemoryKeyStore())
    x = np.tile(np.arange(1000, dtype=np.int16), (6, 4))  # highly compressible, easy to spot
    store = _enc_store(tmp_path, keyring=keyring)
    write_recording(store, "r", x, 1000.0, NAMES, "uV", compressors=None)
    files = [p for p in (tmp_path / "zarr").rglob("*") if p.is_file()]
    assert files
    needle = np.arange(100, 120, dtype="<i2").tobytes()
    for p in files:
        raw = p.read_bytes()
        assert raw.startswith(b"NFE1")
        assert needle not in raw
        assert b"ch0" not in raw and b"nf_signal" not in raw  # metadata is encrypted too
    other = _enc_store(tmp_path, subject="sub-2", keyring=keyring)
    with pytest.raises(Exception):  # noqa: B017 - any failure is fine; the point is no plaintext
        read_window(other, "r", 0, 1)
    keyring.shred_subject("t1", "sub-1")
    with pytest.raises(SubjectKeyUnavailable):
        read_window(store, "r", 0, 1)


def test_timestamps_and_clock_offsets_preserved():
    x = RNG.standard_normal((2, 50)).astype(np.float32)
    ts = 1000.0 + np.arange(50) / 100.0 + RNG.normal(0, 1e-4, 50)
    co = np.array([[1000.0, -0.25], [1005.0, -0.2501]])
    store = MemoryStore()
    write_recording(store, "r", x, 100.0, ["a", "b"], "uV", timestamps=ts, clock_offsets=co)
    assert np.array_equal(read_array(store, "r", "timestamps"), ts)
    assert np.array_equal(read_array(store, "r", "clock_offsets"), co)


@pytest.mark.parametrize(
    "kwargs,err",
    [
        ({"data": np.zeros((0, 10))}, "non-empty"),
        ({"data": np.zeros(10)}, "2-D"),
        ({"data": np.zeros((2, 10), dtype=np.complex64)}, "not accepted"),
        ({"data": np.array([[np.nan, 1.0]])}, "finite"),
        ({"sfreq": 0}, "sfreq"),
        ({"sfreq": float("nan")}, "sfreq"),
        ({"ch_names": ["a", "a"]}, "unique"),
        ({"units": ["uV"] * 3}, "one entry per channel"),
    ],
)
def test_writer_validation(kwargs, err):
    args = {
        "data": np.zeros((2, 10), dtype=np.int16),
        "sfreq": 10.0,
        "ch_names": ["a", "b"],
        "units": "uV",
    }
    args.update(kwargs)
    if "ch_names" not in kwargs and args["data"].ndim == 2 and args["data"].shape[0] == 1:
        args["ch_names"] = ["a"]
    with pytest.raises(SignalError, match=err):
        write_recording(MemoryStore(), "r", **args)


def test_reader_validation():
    store = MemoryStore()
    write_recording(store, "r", np.zeros((2, 100), np.int16), 10.0, ["a", "b"], "uV")
    for args, kw in [
        ((2.0, 1.0), {}),
        ((-1.0, 1.0), {}),
        ((0.0, 1.0), {"level": 7}),
        ((0.0, 1.0), {"channels": ["zz"]}),
        ((0.0, 1.0), {"channels": [5]}),
    ]:
        with pytest.raises(SignalError):
            read_window(store, "r", *args, **kw)
    with pytest.raises(SignalError):
        read_window(store, "missing", 0.0, 1.0)


def test_chunk_benchmark_64ch_1khz_measurement(tmp_path, capsys):
    """MEASUREMENT only (BUILD-GUIDE 2.4): small duration locally; numbers printed + saved."""
    res = bench.run(64, 1000, 20, [1.0, 4.0, 10.0], n_windows=5)
    out = tmp_path / "bench-64ch-1khz.json"
    out.write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))
    assert len(res["results"]) == 3 and res["kind"].startswith("MEASUREMENT")


@pytest.mark.skipif(not os.environ.get("CI"), reason="CI-only: 1,024 ch x 30 kHz needs > 1 GB RAM")
def test_chunk_benchmark_1024ch_30khz_measurement(capsys):
    res = bench.run(1024, 30000, 10, [0.1, 0.5, 1.0], chunk_channels=128, n_windows=5)
    print(json.dumps(res, indent=2))
    assert len(res["results"]) == 3
