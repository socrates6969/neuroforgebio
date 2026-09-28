"""BUILD-GUIDE 4.4: LSL inlet -> nf-core stream with clock-offset capture (SEC-091, SEC-094).

What one machine can and cannot show. Both ends of an LSL connection on one host read the same
LSL clock, so the true inter-clock offset is exactly 0 s. LSL's ``time_correction`` measures that
offset from round trips and reports an uncertainty (half the best round-trip time); the check
``|offset - 0| <= uncertainty`` is therefore a real test of the capture path. A non-zero clock
offset between two LSL clocks needs two hosts (CI job / lab rig, not run here).

The injected offset: the test outlet stamps its samples on a clock ``SKEW`` ahead of the local
one (a device with a skewed clock). The bridge must deliver those stamps unchanged, never
"correct" them silently (SEC-094): stamp - true push time == SKEW.

Skips when pylsl is missing or LSL discovery is blocked on this machine; CI runs it.
"""

from __future__ import annotations

import os
import threading
import time

import numpy as np
import pytest

pylsl = pytest.importorskip("pylsl")

from lsl_fixtures import SyntheticOutlet  # noqa: E402
from neuroforge.lsl import LslInlet, to_local_clock  # noqa: E402

SKEW = 3.25


@pytest.fixture
def outlet():
    o = SyntheticOutlet(8, 250.0, skew_s=SKEW)
    yield o
    o.close()


def _inlet(o: SyntheticOutlet) -> LslInlet:
    try:
        return LslInlet("name", o.name, timeout=5.0)
    except TimeoutError:
        pytest.skip("LSL discovery unavailable here (firewall/multicast); CI runs this test")


def test_offset_recovered_within_reported_uncertainty_and_stamps_kept(outlet):
    inlet = _inlet(outlet)
    try:
        outlet.start()
        ms = [inlet.time_correction_ex(timeout=5.0) for _ in range(5)]
        for m in ms:
            assert m.uncertainty > 0
            assert abs(m.offset - 0.0) <= m.uncertainty, m  # true offset on one host is 0
        time.sleep(1.0)
        outlet.stop()
        time.sleep(0.3)
        got_ts = []
        while True:
            _, ts = inlet.pull_chunk(1000)
            if not len(ts):
                break
            got_ts.append(ts)
        ts = np.concatenate(got_ts)
        sent = np.concatenate(outlet.stamps)
        np.testing.assert_array_equal(ts, sent[: len(ts)])  # original stamps, bit-exact
        # the injected skew survives; mapping to the local clock is a separate derived array
        push = np.repeat(outlet.push_clock, outlet.chunk)[: len(ts)]
        last_in_block = np.arange(len(ts)) % outlet.chunk == outlet.chunk - 1
        np.testing.assert_allclose((ts - push)[last_in_block], SKEW, atol=1e-9)
        derived = to_local_clock(ts, ms)
        assert derived is not ts and np.all(np.abs(derived - ts) <= max(m.uncertainty for m in ms))
    finally:
        inlet.close()


@pytest.mark.postgres
def test_lsl_to_platform_keeps_timing_provenance(outlet, stack, tmp_path):
    """Outlet (tests only) -> LslInlet -> nf-core Stream -> IngestService: samples equal,
    original (skewed) stamps and the captured clock-offset series stored unchanged."""
    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
    from neuroforge.streaming import DeviceKey, GrpcTransport, Stream, run_acquisition
    from nf_platform.ingest import recording_store as rs
    from nf_platform.signals.zarr_store import read_array
    from stream_helpers import open_stream_env

    inlet = _inlet(outlet)
    duration = float(os.environ.get("NF_LSL_STREAM_S", "3"))
    h = stack.headers(stack.owner_token)
    env = open_stream_env(
        stack.http,
        h,
        stack.ids,
        stack.tenant_id,
        stack.storage,
        stack.engine,
        n_channels=8,
        sfreq=250.0,
    )
    seed = env.key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    transport = GrpcTransport(env.target)
    stream = Stream(
        stream_id=env.stream_id,
        tenant_id=env.tenant_id,
        device_id=env.device_id,
        key=DeviceKey.from_seed(seed),
        transport=transport,
        dtype="float32",
        n_channels=8,
        wal_dir=tmp_path / "wal",
        fsync=False,
        sfreq=250.0,
        chunk_ms=100.0,
    ).start()
    stop = threading.Event()
    try:
        th = threading.Thread(
            target=run_acquisition,
            args=(inlet, stream, stop),
            kwargs={"offset_interval_s": 0.5},
            daemon=True,
        )
        th.start()
        outlet.start()
        time.sleep(duration)
        outlet.stop()
        time.sleep(0.5)  # let the inlet receive the tail
        stop.set()
        th.join(10)
        assert stream.drain(timeout=60), stream.stats
        sent = np.concatenate(outlet.pushed)
        assert env.state().n_samples == len(sent)
        env.finish()
        prefix, group = rs.parse_ref(
            rs.make_ref(
                rs.stream_prefix(stack.tenant_id, stack.ids["subject_id"], env.recording_id),
                "signal",
            )
        )
        store = rs.open_store(
            stack.storage, stack.tenant_id, stack.ids["subject_id"], prefix, read_only=True
        )
        np.testing.assert_array_equal(
            read_array(store, group, "timestamps"), np.concatenate(outlet.stamps)
        )
        stored_offsets = read_array(store, group, "clock_offsets")
        captured = np.asarray([(m.collection_time, m.offset) for m in inlet.offsets])
        # exactly as measured; a measurement after the last sample has no chunk to travel with
        assert len(stored_offsets) >= 1 and len(captured) - len(stored_offsets) <= 1
        np.testing.assert_array_equal(stored_offsets, captured[: len(stored_offsets)])
        r = stack.http.get(
            f"/v1/recordings/{env.recording_id}/data",
            params={"start": 0, "end": 60, "format": "binary"},
            headers=h,
        )
        _, data = rs.decode_binary(r.content)
        np.testing.assert_array_equal(data.T, sent)
    finally:
        stream.stop()
        transport.close()
        env.close()
        inlet.close()


@pytest.mark.integration
@pytest.mark.postgres
@pytest.mark.skipif(not os.environ.get("NF_LSL_LONG"), reason="CI-only: 10-minute LSL stream")
def test_lsl_ten_minute_stream(outlet, stack, tmp_path, monkeypatch):
    monkeypatch.setenv("NF_LSL_STREAM_S", "600")
    test_lsl_to_platform_keeps_timing_provenance(outlet, stack, tmp_path)
