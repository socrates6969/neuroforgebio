"""BUILD-GUIDE 4.2 acceptance: the 2.7 network-cut test with nf-core in place of the Python
prototype. 64 ch x 1 kHz float32 from the paced synthetic source, acquisition through
``neuroforge.streaming.run_acquisition`` -> nf-core writer -> encrypted WAL -> nf-core sender
-> the real ``IngestService`` behind a TCP proxy that cuts the network twice. Afterwards the
server array equals the sent samples with no gaps and no duplicates, and the original
timestamps and clock offsets are stored unchanged (SEC-094).

Local runs are short (``NF_SDK_STREAM_S``, default 20 s). The 10-minute run is CI-only
(``NF_STREAM_ACCEPT_FULL=1``).
"""

from __future__ import annotations

import os
import threading
import time

import numpy as np
import pytest
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
from neuroforge.streaming import DeviceKey, GrpcTransport, Stream, run_acquisition

pytestmark = pytest.mark.postgres
N_CH, SFREQ = 64, 1000.0


def _run(stack, tmp_path, duration: float) -> dict:
    from edge_prototype.source import SyntheticSource
    from nf_platform.ingest import recording_store as rs
    from nf_platform.signals.zarr_store import read_array
    from stream_helpers import CuttableProxy, open_stream_env

    h_owner = stack.headers(stack.owner_token)
    env = open_stream_env(
        stack.http,
        h_owner,
        stack.ids,
        stack.tenant_id,
        stack.storage,
        stack.engine,
        n_channels=N_CH,
        sfreq=SFREQ,
    )
    proxy = CuttableProxy(env.target)
    seed = env.key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    transport = GrpcTransport(proxy.address)
    stream = Stream(
        stream_id=env.stream_id,
        tenant_id=env.tenant_id,
        device_id=env.device_id,
        key=DeviceKey.from_seed(seed),
        transport=transport,
        dtype="float32",
        n_channels=N_CH,
        wal_dir=tmp_path / "wal",
        fsync=False,
        sfreq=SFREQ,
        chunk_ms=100.0,
        batch_max=20,
        call_timeout_s=5.0,
    ).start()
    src = SyntheticSource(N_CH, SFREQ, "float32", max_samples=int(duration * SFREQ))
    stop = threading.Event()
    acq: dict = {}
    th = threading.Thread(
        target=lambda: acq.update(run_acquisition(src, stream, stop)), daemon=True
    )
    try:
        th.start()
        t0 = time.monotonic()
        for at in (duration * 0.3, duration * 0.65):
            time.sleep(max(0.0, t0 + at - time.monotonic()))
            proxy.cut(2.0)
        time.sleep(max(0.0, t0 + duration + 0.5 - time.monotonic()))
        stop.set()
        th.join(30)
        assert stream.drain(timeout=120), stream.stats
        stats = stream.stats
        assert stats["sender"]["fatal"] is None, stats
        n = src.produced
        assert n == int(duration * SFREQ)
        assert proxy.cuts == 2 and stats["sender"]["rpc_errors"] >= 1, stats  # the cuts hit
        st = env.state()
        assert st.n_samples == n, (st.n_samples, n)
        fin = env.finish()
        assert fin.state == "closed"
        # server array == sent samples; timestamps stored unchanged
        prefix, group = rs.parse_ref(
            rs.make_ref(
                rs.stream_prefix(stack.tenant_id, stack.ids["subject_id"], env.recording_id),
                "signal",
            )
        )
        store = rs.open_store(
            stack.storage, stack.tenant_id, stack.ids["subject_id"], prefix, read_only=True
        )
        want, want_ts = src.expected(n)
        r = stack.http.get(
            f"/v1/recordings/{env.recording_id}/data",
            params={"start": 0, "end": n / SFREQ + 1, "format": "binary"},
            headers=h_owner,
        )
        assert r.status_code == 200, r.text
        _, data = rs.decode_binary(r.content)
        np.testing.assert_array_equal(data.T, want)
        np.testing.assert_array_equal(read_array(store, group, "timestamps"), want_ts)
        offsets = read_array(store, group, "clock_offsets")
        assert offsets.shape[0] >= int(duration) - 1
        return {"stats": stats, "acq": acq, "n": n}
    finally:
        stream.stop()
        transport.close()
        proxy.close()
        env.close()


def test_network_cuts_nf_core(stack, tmp_path):
    out = _run(stack, tmp_path, float(os.environ.get("NF_SDK_STREAM_S", "20")))
    print(f"[4.2 measurement] sdk_stream {out}")  # noqa: T201
    # SEC-093: acquisition never waited for the network (loop gap stays small during the cuts)
    assert out["acq"]["max_acq_gap_s"] < 0.5, out


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("NF_STREAM_ACCEPT_FULL"), reason="CI-only: 10-minute run")
def test_network_cuts_nf_core_ten_minutes(stack, tmp_path):
    _run(stack, tmp_path, 600.0)
