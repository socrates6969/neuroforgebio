"""The 20 ms signed-chunk floor (P7.7 R1) as the Python SDK exposes it: ``Stream`` cuts chunks by
time from the registered ``sfreq``, refuses shorter chunks, and ``open_stream`` hands the writer
the rate the platform registered. No platform or PostgreSQL needed."""

from __future__ import annotations

import numpy as np
import pytest
from neuroforge import _native
from neuroforge.streaming import DeviceKey, Stream, TransportError, open_stream


def _stream(tmp_path, **kw) -> Stream:
    return Stream(
        stream_id="st-1",
        tenant_id="tn",
        device_id="dev",
        key=DeviceKey.generate(),
        transport=None,
        dtype="float32",
        n_channels=2,
        wal_dir=tmp_path / "wal",
        fsync=False,
        **kw,
    )


def _push(s: Stream, start: int, n: int) -> int:
    data = np.zeros((n, s.n_channels), dtype=np.float32)
    return s.push(data, 100.0 + np.arange(start, start + n) / 1000.0)


def test_30khz_default_is_100ms_not_100_samples(tmp_path):
    s = _stream(tmp_path, sfreq=30_000)
    assert s.chunk_samples == 3000
    assert s.writer.chunk_samples == 3000
    assert s.writer.sfreq == 30_000.0


def test_chunk_ms_sets_the_length_with_ceil(tmp_path):
    assert _stream(tmp_path / "a", sfreq=1000.0, chunk_ms=20.0).chunk_samples == 20
    assert _stream(tmp_path / "b", sfreq=250.5, chunk_ms=20.0).chunk_samples == 6


@pytest.mark.parametrize(
    "kw",
    [
        {"sfreq": 30_000.0, "chunk_samples": 100},  # the old default: 3.3 ms
        {"sfreq": 1000.0, "chunk_ms": 19.9},
        {"sfreq": 1000.0, "chunk_ms": 1.0},
    ],
)
def test_chunk_shorter_than_20ms_is_refused(tmp_path, kw):
    with pytest.raises(ValueError, match="20 ms"):
        _stream(tmp_path, **kw)


def test_explicit_chunk_samples_of_at_least_20ms_is_accepted(tmp_path):
    s = _stream(tmp_path, sfreq=250.0, chunk_samples=25)
    assert s.chunk_samples == 25 and s.writer.sfreq == 250.0


def test_value_cap_error_names_both_limits(tmp_path):
    # 1,024 channels x 3,000 samples (100 ms at 30 kHz) = 3.07 M values: refused, not shrunk.
    with pytest.raises(ValueError, match="1,000,000") as e:
        Stream(
            stream_id="st-1",
            tenant_id="tn",
            device_id="dev",
            key=DeviceKey.generate(),
            transport=None,
            dtype="int16",
            n_channels=1024,
            wal_dir=tmp_path / "wal",
            fsync=False,
            sfreq=30_000.0,
            chunk_ms=100.0,
        )
    assert "20 ms" in str(e.value)


def test_regular_stream_without_sfreq_is_refused(tmp_path):
    with pytest.raises(TypeError, match="sfreq"):
        _stream(tmp_path)
    with pytest.raises(TypeError, match="sfreq"):
        _stream(tmp_path, chunk_samples=100)  # the old sample-only constructor


@pytest.mark.parametrize("bad", [0, -250.0, float("nan"), float("inf")])
def test_bad_sfreq_is_refused(tmp_path, bad):
    with pytest.raises(ValueError, match="sfreq"):
        _stream(tmp_path, sfreq=bad)


def test_irregular_stream_needs_chunk_samples_and_no_sfreq(tmp_path):
    s = _stream(tmp_path / "ok", irregular=True, chunk_samples=1)
    assert s.chunk_samples == 1 and s.writer.sfreq is None
    assert _push(s, 0, 3) == 3
    assert s.writer.flush() is False
    with pytest.raises(ValueError, match="chunk_samples"):
        _stream(tmp_path / "a", irregular=True)
    with pytest.raises(ValueError, match="sfreq"):
        _stream(tmp_path / "b", irregular=True, chunk_samples=5, sfreq=250.0)


def test_short_final_chunk_closes_a_timed_writer(tmp_path):
    s = _stream(tmp_path, sfreq=1000.0, chunk_ms=20.0)
    assert _push(s, 0, 25) == 1
    assert s.writer.flush() is True
    assert s.writer.closed
    with pytest.raises(_native.CoreError, match="writer flushed"):
        _push(s, 25, 20)


def test_empty_flush_keeps_a_timed_writer_open(tmp_path):
    s = _stream(tmp_path, sfreq=1000.0, chunk_ms=20.0)
    assert _push(s, 0, 40) == 2
    assert s.writer.flush() is False
    assert not s.writer.closed
    assert _push(s, 40, 20) == 1


def test_native_writer_arguments(tmp_path):
    key = DeviceKey.generate()
    wal = _native.Wal(str(tmp_path / "w"), "st-1", None, None, False)
    w = _native.StreamWriter("st-1", "float32", 2, None, key, wal, sfreq=1000.0)
    assert w.chunk_samples == 100 and w.sfreq == 1000.0 and not w.closed
    legacy = _native.StreamWriter("st-1", "float32", 2, 4, key, wal)  # positional, no rate
    assert legacy.chunk_samples == 4 and legacy.sfreq is None
    with pytest.raises(ValueError, match="not both"):
        _native.StreamWriter("st-1", "float32", 2, 50, key, wal, sfreq=1e3, chunk_ms=50.0)
    with pytest.raises(ValueError, match="needs sfreq"):
        _native.StreamWriter("st-1", "float32", 2, None, key, wal, chunk_ms=50.0)
    with pytest.raises(ValueError, match="chunk_samples"):
        _native.StreamWriter("st-1", "float32", 2, None, key, wal)
    with pytest.raises(ValueError, match="20 ms"):
        _native.StreamWriter("st-1", "float32", 2, 100, key, wal, sfreq=30_000.0)


class _Unreachable:
    """Every call fails as UNAVAILABLE (retried): the sender never reaches a server."""

    def get_stream_state(self, request, auth, timeout):
        raise TransportError(14, "unavailable")

    def stream_chunks(self, chunks, auth, timeout):
        raise TransportError(14, "unavailable")

    def finish_stream(self, request, auth, timeout):
        raise TransportError(14, "unavailable")


class _FakeClient:
    """Records the stream registration; ``echo`` adds ``sfreq`` to the response."""

    session = "sess-1"
    ingest_target = None
    synthetic = True

    def __init__(self, echo: float | None = None) -> None:
        self.echo = echo
        self.posted: list[tuple[str, dict]] = []

    def post(self, path, body):
        self.posted.append((path, body))
        out = {"stream_id": "st-1", "recording_id": "rec-1", "next_seq": 0}
        if self.echo is not None:
            out["sfreq"] = self.echo
        return out

    def get(self, path):
        return {"tenant_id": "tn"}


@pytest.mark.parametrize("echo", [None, 500.0])
def test_open_stream_uses_the_registered_sfreq(tmp_path, echo):
    c = _FakeClient(echo)
    s = open_stream(
        device_id="dev",
        key=DeviceKey.generate(),
        sfreq=500.0,
        channels=[{"name": "C3", "modality": "EEG", "units": "uV"}],
        wal_dir=tmp_path / "wal",
        client=c,
        transport=_Unreachable(),
        fsync=False,
    )
    try:
        (path, body) = c.posted[0]
        assert path == "/v1/sessions/sess-1/streams"
        assert s.writer.sfreq == body["sfreq"] == 500.0
        assert s.sfreq == 500.0 and s.chunk_samples == 50  # 100 ms default
    finally:
        s.stop()


def test_open_stream_prefers_the_rate_the_platform_echoes(tmp_path):
    c = _FakeClient(echo=1000.0)
    s = open_stream(
        device_id="dev",
        key=DeviceKey.generate(),
        sfreq=999.9,
        channels=[{"name": "C3", "modality": "EEG", "units": "uV"}],
        wal_dir=tmp_path / "wal",
        client=c,
        transport=_Unreachable(),
        fsync=False,
        chunk_ms=20.0,
    )
    try:
        assert s.writer.sfreq == 1000.0 and s.chunk_samples == 20
    finally:
        s.stop()
