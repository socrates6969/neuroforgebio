"""2.7 acceptance with the edge prototype: encrypted WAL (SEC-037), resume after network cuts
(server array == sent samples, no gaps, no duplicates), a 5 s server stall does not stop local
acquisition (SEC-093), measured throughput headroom for 64 ch x 1 kHz.

Local runs are SHORT (NF_STREAM_ACCEPT_S, default 25 s). The full 10-minute run is CI-only
(``integration`` marker, ``NF_STREAM_ACCEPT_FULL=1``). Measured numbers are printed and written to
``$NF_STREAM_REPORT`` when set.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time

import numpy as np
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from edge_prototype.client import EdgeClient
from edge_prototype.source import SourceInfo, SyntheticSource, synthetic_block
from edge_prototype.wal import (
    DpapiKeyProvider,
    EphemeralKeyProvider,
    WalError,
    WriteAheadLog,
)
from nf_platform.db import models as m
from nf_platform.db.context import tenant_session
from nf_platform.ingest import recording_store as rs
from nf_platform.ingest.stream.service import IngestServicer
from nf_platform.signals.zarr_store import read_array, read_window
from nf_platform.storage.runtime import service_principal
from sqlalchemy import create_engine, select
from stream_helpers import CuttableProxy, open_stream_env

N_CH, SFREQ = 64, 1000.0
REPORT: dict = {}


def _report(key: str, value) -> None:
    REPORT[key] = value
    print(f"[2.7 measurement] {key} = {value}", file=sys.stderr)  # noqa: T201
    path = os.environ.get("NF_STREAM_REPORT")
    if path:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(REPORT, fh, indent=2, sort_keys=True)


# ---------------------------------------------------------------- chunk length (no server)
class _InfoOnly:
    def __init__(self, sfreq: float) -> None:
        self.info = SourceInfo("s", 2, sfreq, "float32", ("a", "b"))

    def pull_chunk(self, max_samples: int):
        return np.empty((0, 2), np.float32), np.empty(0)


def test_edge_client_refuses_chunks_shorter_than_20ms(tmp_path):
    """P7.7 R1: the old 100-sample default at 30 kHz (3.3 ms) is refused; 20 ms and more, and
    streams without a nominal rate (sfreq 0), are accepted. No connection is made."""

    def edge(sfreq: float, chunk_samples: int, name: str) -> EdgeClient:
        wal = WriteAheadLog(tmp_path / name, "s", EphemeralKeyProvider(), fsync=False)
        return EdgeClient(
            _InfoOnly(sfreq),
            "127.0.0.1:1",
            device_key=Ed25519PrivateKey.generate(),
            tenant_id="t",
            device_id="d",
            stream_id="s",
            wal=wal,
            chunk_samples=chunk_samples,
        )

    with pytest.raises(ValueError, match="shorter than 20 ms: use at least 600 samples"):
        edge(30_000.0, 100, "a")
    with pytest.raises(ValueError, match="20 ms"):
        edge(1000.0, 19, "b")
    with pytest.raises(ValueError, match=">= 1"):
        edge(1000.0, 0, "c")
    for sfreq, n, name in (
        (1000.0, 20, "d"),
        (250.0, 25, "e"),
        (30_000.0, 600, "f"),
        (0.0, 1, "g"),
    ):
        edge(sfreq, n, name)._channel.close()


# ---------------------------------------------------------------- WAL (no server)
def test_wal_is_ciphertext_and_deleted_after_ack(tmp_path):
    wal = WriteAheadLog(tmp_path / "wal", "stream-1", EphemeralKeyProvider())
    rec = synthetic_block(0, 50, 8, 1000.0, "float32").tobytes()
    for s in range(3):
        wal.append(s, rec)
    files = sorted((tmp_path / "wal").iterdir())
    assert len(files) == 3
    for f in files:
        blob = f.read_bytes()
        assert blob.startswith(b"NFWAL1") and rec[:32] not in blob and rec[100:132] not in blob
    assert wal.read(1) == rec
    assert wal.ack(2) == 2 and wal.pending() == [2]
    assert sorted(p.name for p in (tmp_path / "wal").iterdir()) == ["0000000000000002.nfwal"]
    # tampering and a different key are detected, never silently skipped
    f = tmp_path / "wal" / "0000000000000002.nfwal"
    b = bytearray(f.read_bytes())
    b[-1] ^= 1
    f.write_bytes(bytes(b))
    with pytest.raises(WalError):
        wal.read(2)
    other = WriteAheadLog(tmp_path / "wal", "stream-1", EphemeralKeyProvider())
    assert other.pending() == [2]  # a restarted client finds its records
    with pytest.raises(WalError):
        other.read(2)


@pytest.mark.skipif(
    sys.platform != "win32", reason="DPAPI is Windows-only (Keychain/libsecret: 4.2)"
)
def test_wal_key_sealed_with_dpapi(tmp_path):
    kp = DpapiKeyProvider(tmp_path / "wal.key")
    k = kp.key()
    sealed = (tmp_path / "wal.key").read_bytes()
    assert len(k) == 32 and k not in sealed
    assert DpapiKeyProvider(tmp_path / "wal.key").key() == k  # same user can unseal
    wal = WriteAheadLog(tmp_path / "w", "s", kp)
    wal.append(0, b"hello")
    assert (
        WriteAheadLog(tmp_path / "w", "s", DpapiKeyProvider(tmp_path / "wal.key")).read(0)
        == b"hello"
    )


# ---------------------------------------------------------------- with the server
@pytest.fixture
def grpc_engine(db_url):
    eng = create_engine(db_url, pool_size=4, max_overflow=4)
    yield eng
    eng.dispose()


def _open(client, as_role, tree, tenants, storage, engine, **kw):
    return open_stream_env(
        client,
        as_role("owner"),
        tree,
        tenants.a,
        storage,
        engine,
        n_channels=N_CH,
        sfreq=SFREQ,
        **kw,
    )


def _edge(env, source, target, tmp_path, **kw) -> EdgeClient:
    wal = WriteAheadLog(tmp_path / "wal", env.stream_id, EphemeralKeyProvider(), fsync=False)
    return EdgeClient(
        source,
        target,
        device_key=env.key,
        tenant_id=env.tenant_id,
        device_id=env.device_id,
        stream_id=env.stream_id,
        wal=wal,
        **kw,
    )


def _verify_server_copy(env, storage, tree, tenants, engine, source, n_sent):
    """Server array == sent samples; seqs contiguous (no gaps, no duplicates); timestamps kept."""
    st = env.state()
    assert st.n_samples == n_sent, (st.n_samples, n_sent)
    with tenant_session(service_principal(tenants.a), engine=engine) as s:
        rows = s.execute(
            select(m.StreamChunk.seq, m.StreamChunk.sample_start, m.StreamChunk.n_samples)
            .where(m.StreamChunk.stream_id == env.stream_id)
            .order_by(m.StreamChunk.seq)
        ).all()
    assert [r.seq for r in rows] == list(range(len(rows)))
    pos = 0
    for r in rows:
        assert r.sample_start == pos
        pos += r.n_samples
    assert pos == n_sent
    fin = env.finish()
    assert fin.state == "closed"
    prefix, group = rs.parse_ref(
        rs.make_ref(rs.stream_prefix(tenants.a, tree["subject_id"], env.recording_id), "signal")
    )
    store = rs.open_store(storage, tenants.a, tree["subject_id"], prefix, read_only=True)
    want, want_ts = source.expected(n_sent)
    got = read_window(store, group, 0, n_sent / SFREQ + 1).T
    assert got.shape == want.shape
    np.testing.assert_array_equal(got, want)
    np.testing.assert_array_equal(read_array(store, group, "timestamps"), want_ts)
    assert read_array(store, group, "clock_offsets").shape[0] >= 1


@pytest.mark.postgres
def test_throughput_headroom_64ch_1khz(
    client, as_role, tree, tenants, storage, grpc_engine, tmp_path
):
    """MEASUREMENT (no target claimed beforehand): 20 s of 64 ch x 1 kHz float32 pre-acquired
    into the WAL, then drained as fast as the server accepts it. Headroom = data seconds / wall
    seconds (>= 1 means the server keeps up with real time)."""
    env = _open(client, as_role, tree, tenants, storage, grpc_engine)
    # measure the server, not the per-stream chunk-rate limit (60/s, burst 120 by default)
    env.servicer.chunk_rate, env.servicer.chunk_burst = 1e9, 10**9
    seconds = float(os.environ.get("NF_STREAM_BENCH_S", "20"))
    n = int(seconds * SFREQ)
    fake_clock = [0.0]
    src = SyntheticSource(N_CH, SFREQ, "float32", clock=lambda: fake_clock[0], max_samples=n)
    edge = _edge(env, src, env.target, tmp_path, chunk_samples=100, batch_max=100)
    try:
        # pre-acquire with the network idle: build every chunk into the WAL
        fake_clock[0] = seconds + 1
        seq = 0
        while True:
            data, ts = src.pull_chunk(edge.chunk_samples)
            if not len(ts):
                break
            msg = edge.make_chunk(seq, data, ts, [(ts[0], 0.0015)], [(ts[-1], time.monotonic())])
            edge.wal.append(seq, msg.SerializeToString())
            seq += 1
        t0 = time.perf_counter()
        edge._stop_acq.set()  # nothing more to acquire; only the sender runs
        snd = threading.Thread(target=edge._send_loop, daemon=True)
        snd.start()
        deadline = time.monotonic() + 600
        while len(edge.wal) and time.monotonic() < deadline:
            time.sleep(0.01)
        wall = time.perf_counter() - t0
        edge._stop_send.set()
        snd.join(10)
        assert len(edge.wal) == 0
        headroom = seconds / wall
        _report("bench_data_s", seconds)
        _report("bench_wall_s", round(wall, 2))
        _report("bench_chunk_ms", 100)
        _report("throughput_headroom_x", round(headroom, 2))
        _report("server_samples_per_s", round(n / wall))
        _verify_server_copy(env, storage, tree, tenants, grpc_engine, src, n)
    finally:
        edge.close()
        env.close()


@pytest.mark.postgres
def test_short_acceptance_two_network_cuts(
    client, as_role, tree, tenants, storage, grpc_engine, tmp_path
):
    """Local SHORT version of the 2.7 acceptance: 64 ch x 1 kHz for NF_STREAM_ACCEPT_S seconds
    (default 25), the network is cut twice; afterwards the server array equals the sent samples
    with no gaps and no duplicates."""
    duration = float(os.environ.get("NF_STREAM_ACCEPT_S", "25"))
    _run_acceptance(client, as_role, tree, tenants, storage, grpc_engine, tmp_path, duration)


@pytest.mark.integration
@pytest.mark.postgres
@pytest.mark.skipif(not os.environ.get("NF_STREAM_ACCEPT_FULL"), reason="CI-only: 10-minute run")
def test_full_acceptance_ten_minutes(
    client, as_role, tree, tenants, storage, grpc_engine, tmp_path
):
    _run_acceptance(client, as_role, tree, tenants, storage, grpc_engine, tmp_path, 600.0)


def _run_acceptance(client, as_role, tree, tenants, storage, engine, tmp_path, duration):
    env = _open(client, as_role, tree, tenants, storage, engine)
    proxy = CuttableProxy(env.target)
    src = SyntheticSource(N_CH, SFREQ, "float32", max_samples=int(duration * SFREQ))
    edge = _edge(
        env, src, proxy.address, tmp_path, chunk_samples=100, batch_max=20, call_timeout_s=5
    )
    try:
        edge.start()
        cut_at = (duration * 0.3, duration * 0.65)
        t0 = time.monotonic()
        for at in cut_at:
            time.sleep(max(0.0, t0 + at - time.monotonic()))
            proxy.cut(2.0)
        time.sleep(max(0.0, t0 + duration - time.monotonic()))
        assert edge.drain(timeout=120), f"WAL not drained: {len(edge.wal)} left, {edge.stats}"
        assert edge.stats.fatal is None, edge.stats
        n = src.produced
        assert n == int(duration * SFREQ)
        _report("accept_duration_s", duration)
        _report("accept_network_cuts", proxy.cuts)
        _report("accept_rpc_errors", edge.stats.rpc_errors)
        _report("accept_wal_peak_chunks", edge.stats.wal_peak)
        _report("accept_max_acq_gap_s", round(edge.stats.max_acq_gap_s, 3))
        assert proxy.cuts == 2 and edge.stats.rpc_errors >= 1  # the cuts really hit the stream
        _verify_server_copy(env, storage, tree, tenants, engine, src, n)
    finally:
        edge.close()
        proxy.close()
        env.close()


class StallingServicer(IngestServicer):
    """Stalls the next StreamChunks call for ``stall_s`` once ``armed`` is set."""

    stall_s = 5.0

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.armed = threading.Event()
        self.stalled = threading.Event()

    def StreamChunks(self, request_iterator, context):  # noqa: N802
        if self.armed.is_set() and not self.stalled.is_set():
            self.stalled.set()
            time.sleep(self.stall_s)
        return super().StreamChunks(request_iterator, context)


@pytest.mark.postgres
def test_server_stall_does_not_block_acquisition(
    client, as_role, tree, tenants, storage, grpc_engine, tmp_path
):
    """SEC-093: the server stalls for 5 s; the client keeps acquiring into the WAL without loss."""
    env = _open(client, as_role, tree, tenants, storage, grpc_engine, servicer_cls=StallingServicer)
    duration = 10.0
    src = SyntheticSource(N_CH, SFREQ, "float32", max_samples=int(duration * SFREQ))
    edge = _edge(env, src, env.target, tmp_path, chunk_samples=100, batch_max=10, call_timeout_s=30)
    try:
        edge.start()
        time.sleep(2.0)
        env.servicer.armed.set()
        acquired_before = src.produced
        time.sleep(6.0)
        assert env.servicer.stalled.is_set()
        # during the stall acquisition kept going at the device rate and the WAL absorbed it
        assert src.produced - acquired_before >= 5.5 * SFREQ
        assert edge.stats.max_acq_gap_s < 0.5, edge.stats.max_acq_gap_s
        assert edge.stats.wal_peak >= 40  # >= 4 s of 100 ms chunks waited in the WAL
        time.sleep(max(0.0, duration - 8.0))
        assert edge.drain(timeout=60), edge.stats
        _report("stall_s", StallingServicer.stall_s)
        _report("stall_wal_peak_chunks", edge.stats.wal_peak)
        _report("stall_max_acq_gap_s", round(edge.stats.max_acq_gap_s, 3))
        _verify_server_copy(env, storage, tree, tenants, grpc_engine, src, src.produced)
    finally:
        edge.close()
        env.close()
