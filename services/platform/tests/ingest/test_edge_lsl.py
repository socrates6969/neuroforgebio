"""2.7 with a real LSL stream: a synthetic LSL outlet (test fixture only; SEC-091 keeps outlets
out of the product code) -> ``LslSource`` inlet -> WAL -> IngestService. Runs locally when the
pylsl wheel works and LSL discovery is allowed on this machine; otherwise skipped (CI runs it)."""

from __future__ import annotations

import threading
import time
import uuid

import numpy as np
import pytest
from edge_prototype.client import EdgeClient
from edge_prototype.wal import EphemeralKeyProvider, WriteAheadLog
from sqlalchemy import create_engine
from stream_helpers import open_stream_env

pylsl = pytest.importorskip("pylsl")
pytestmark = pytest.mark.postgres
N_CH, SFREQ = 8, 250.0


def test_lsl_outlet_to_platform(client, as_role, tree, tenants, storage, db_url, tmp_path):
    from edge_prototype.source import LslSource

    name = f"nf-test-{uuid.uuid4().hex[:8]}"
    info = pylsl.StreamInfo(name, "EEG", N_CH, SFREQ, pylsl.cf_float32, name)
    outlet = pylsl.StreamOutlet(info, chunk_size=10)
    try:
        src = LslSource("name", name, timeout=5.0)
    except TimeoutError:
        pytest.skip("LSL discovery unavailable here (firewall/multicast); CI runs this test")
    assert (src.info.n_channels, src.info.sfreq, src.info.dtype) == (N_CH, SFREQ, "float32")
    eng = create_engine(db_url, pool_size=4, max_overflow=4)
    env = open_stream_env(
        client, as_role("owner"), tree, tenants.a, storage, eng, n_channels=N_CH, sfreq=SFREQ
    )
    wal = WriteAheadLog(tmp_path / "wal", env.stream_id, EphemeralKeyProvider(), fsync=False)
    edge = EdgeClient(
        src,
        env.target,
        device_key=env.key,
        tenant_id=env.tenant_id,
        device_id=env.device_id,
        stream_id=env.stream_id,
        wal=wal,
        chunk_samples=25,
    )
    pushed: list[np.ndarray] = []
    stop = threading.Event()

    def push() -> None:
        k = 0
        t_next = time.monotonic()
        while not stop.is_set():
            block = (np.arange(k, k + 10)[:, None] * 0.5 + np.arange(N_CH)[None, :]).astype(
                np.float32
            )
            outlet.push_chunk(block.tolist())
            pushed.append(block)
            k += 10
            t_next += 10 / SFREQ
            time.sleep(max(0.0, t_next - time.monotonic()))

    try:
        edge.start()
        th = threading.Thread(target=push, daemon=True)
        th.start()
        time.sleep(3.0)
        stop.set()
        th.join()
        time.sleep(0.5)  # let the inlet receive the tail
        assert edge.drain(timeout=30), edge.stats
        sent = np.concatenate(pushed)
        n = env.state().n_samples
        assert n == len(sent), (n, len(sent))
        env.finish()
        r = client.get(
            f"/v1/recordings/{env.recording_id}/data?start=0&end=60&format=binary",
            headers=as_role("data-steward"),
        )
        from nf_platform.ingest import recording_store as rs

        _, data = rs.decode_binary(r.content)
        np.testing.assert_array_equal(data.T, sent)
    finally:
        edge.close()
        env.close()
        src.close()
        eng.dispose()
