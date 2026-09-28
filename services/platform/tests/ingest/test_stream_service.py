"""2.7 ``IngestService`` against a real Postgres + encrypted Zarr: idempotency on (stream_id, seq),
device-token auth (SEC-016), chunk authentication (SEC-040), sanity checks -> suspect (SEC-041),
original timestamps + clock-offset series stored unchanged (SEC-094), tenant isolation."""

from __future__ import annotations

import grpc
import numpy as np
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from nf_platform.db import models as m
from nf_platform.db.context import tenant_session
from nf_platform.ingest import recording_store as rs
from nf_platform.ingest.stream._proto import ingest_pb2 as pb
from nf_platform.signals.zarr_store import read_array, read_window
from nf_platform.storage.runtime import service_principal
from sqlalchemy import create_engine, select, text
from stream_helpers import open_stream_env

pytestmark = pytest.mark.postgres
N_CH = 4


@pytest.fixture
def grpc_engine(db_url):
    eng = create_engine(db_url, pool_size=4, max_overflow=4)
    yield eng
    eng.dispose()


@pytest.fixture
def env(client, as_role, tree, tenants, storage, grpc_engine):
    e = open_stream_env(
        client, as_role("owner"), tree, tenants.a, storage, grpc_engine, n_channels=N_CH
    )
    yield e
    e.close()


@pytest.fixture
def env_no_consent(client, as_role, tree, tenants, storage, grpc_engine):
    """m5-ledger (5.4): without `collection` consent the ledger policy (which replaced the M2 stub)
    quarantines the stream's new recording."""
    r = client.post(
        f"/v1/subjects/{tree['subject_id']}/consents",
        json={"kind": "withdraw", "scopes": ["collection"]},
        headers=as_role("owner"),
    )
    assert r.status_code == 201, r.text
    e = open_stream_env(
        client, as_role("owner"), tree, tenants.a, storage, grpc_engine, n_channels=N_CH
    )
    yield e
    e.close()


def _data(start: int, n: int) -> np.ndarray:
    i = np.arange(start, start + n)[:, None]
    return (np.sin(i / 7.0 + np.arange(N_CH)[None, :]) * 30).astype(np.float32)


def _chunks(env, first_seq: int, count: int, n: int = 100) -> list[pb.Chunk]:
    return [
        env.chunk(s, _data(s * n, n), 100.0 + s * n / env.sfreq)
        for s in range(first_seq, first_seq + count)
    ]


def _abort_code(fn) -> grpc.StatusCode:
    with pytest.raises(grpc.RpcError) as ei:
        fn()
    return ei.value.code()


def _window(storage, env, tree, tenants, n):
    prefix, group = rs.parse_ref(
        rs.make_ref(rs.stream_prefix(tenants.a, tree["subject_id"], env.recording_id), "signal")
    )
    store = rs.open_store(storage, tenants.a, tree["subject_id"], prefix, read_only=True)
    return store, group


def test_stream_roundtrip_live_read_and_finish(
    env_no_consent, client, as_role, tree, tenants, storage
):
    env = env_no_consent
    sent = _chunks(env, 0, 15)
    ack = env.send(sent[:12])
    assert (ack.next_seq, ack.accepted, ack.duplicates, ack.suspect) == (12, 12, 0, 0)
    # a live (unfinished) stream is readable through the 2.4 endpoint (no collection consent:
    # quarantined; the steward reviews it)
    assert env.extra["open"]["recording_state"] == "quarantined"
    assert env.extra["open"]["ack_timing"] == "none"
    url = f"/v1/recordings/{env.recording_id}/data?start=0&end=0.5&format=binary"
    assert client.get(url, headers=as_role("scientist")).status_code == 403
    r = client.get(url, headers=as_role("data-steward"))
    assert r.status_code == 200, r.text
    _, win = rs.decode_binary(r.content)
    np.testing.assert_array_equal(win.T, _data(0, 500))
    # live reads see whole ~1 s time chunks (published once per completed chunk)
    r = client.get(url.replace("end=0.5", "end=5"), headers=as_role("data-steward"))
    assert rs.decode_binary(r.content)[1].shape == (N_CH, 1000)
    # finish: pyramid + timing series; level 0 and the original timestamps are unchanged
    ack = env.send(sent[12:])
    st = env.finish()
    assert (st.state, st.n_samples, st.next_seq) == ("closed", 1500, 15)
    store, group = _window(storage, env, tree, tenants, 1500)
    np.testing.assert_array_equal(read_window(store, group, 0, 2.0).T, _data(0, 1500))
    ts = read_array(store, group, "timestamps")
    # SEC-094: the original per-sample timestamps, bit-exact as sent
    np.testing.assert_array_equal(ts, np.concatenate([list(c.lsl_timestamps) for c in sent]))
    co = read_array(store, group, "clock_offsets")
    np.testing.assert_array_equal(co, [[100.0 + s * 0.1, 0.001] for s in range(15)])
    lc = read_array(store, group, "local_clock")
    assert lc.shape == (15, 2) and lc[0, 1] == pytest.approx(107.0)
    # closed: nothing more is accepted
    assert _abort_code(lambda: env.send(_chunks(env, 15, 1))) == grpc.StatusCode.FAILED_PRECONDITION


def test_idempotent_on_stream_and_seq(env, grpc_engine, tenants, audit_events):
    ch = _chunks(env, 0, 3)
    env.send(ch)
    ack = env.send(ch + _chunks(env, 3, 1))  # overlap: resend after a lost ack
    assert (ack.next_seq, ack.accepted, ack.duplicates) == (4, 1, 3)
    assert env.state().n_samples == 400
    # a DIFFERENT chunk under a committed seq: rejected + audited (the alert hook)
    other = env.chunk(1, _data(0, 100) + 1, 100.1)
    assert _abort_code(lambda: env.send([other])) == grpc.StatusCode.ALREADY_EXISTS
    conflicts = [
        e for e in audit_events(type_="stream.conflict") if e["resource_id"] == env.stream_id
    ]
    assert conflicts and conflicts[0]["details"]["seq"] == 1
    # a gap is refused; the client must resend from next_seq
    assert _abort_code(lambda: env.send(_chunks(env, 6, 1))) == grpc.StatusCode.FAILED_PRECONDITION
    with tenant_session(service_principal(tenants.a), engine=grpc_engine) as s:
        seqs = s.scalars(select(m.StreamChunk.seq).order_by(m.StreamChunk.seq)).all()
    assert seqs == [0, 1, 2, 3]


def test_sec040_valid_hash_bad_signature_is_rejected(env, audit_events):
    good = _chunks(env, 0, 1)[0]
    forged = env.chunk(0, _data(0, 100), 100.0, key=Ed25519PrivateKey.generate())
    assert forged.chunk_id == good.chunk_id  # the hash alone is valid
    assert _abort_code(lambda: env.send([forged])) == grpc.StatusCode.UNAUTHENTICATED
    bad_hash = pb.Chunk()
    bad_hash.CopyFrom(good)
    bad_hash.samples = bytes(len(good.samples))
    assert _abort_code(lambda: env.send([bad_hash])) == grpc.StatusCode.DATA_LOSS
    assert env.state().next_seq == 0
    fails = [e for e in audit_events(type_="auth.failure") if e["resource_id"] == env.stream_id]
    assert any(e["details"]["reason"] == "bad chunk signature" for e in fails)


def test_sec016_device_token(env, client, as_role, tenants):
    other = Ed25519PrivateKey.generate()
    ch = _chunks(env, 0, 1)
    # signed by another key -> 401-equivalent
    code = _abort_code(lambda: env.send(ch, metadata=env.token(key=other)))
    assert code == grpc.StatusCode.UNAUTHENTICATED
    # no / malformed credentials
    assert _abort_code(lambda: env.send(ch, metadata=(("authorization", "Bearer x"),))) == (
        grpc.StatusCode.UNAUTHENTICATED
    )
    # a token for another stream id cannot write this stream
    import uuid

    tok = env.token(stream_id=str(uuid.uuid4()))
    assert _abort_code(lambda: env.send(ch, metadata=tok)) == grpc.StatusCode.PERMISSION_DENIED
    # tenant B's registered device, claiming tenant A's stream: no such device in A
    tok = env.token(tenant_id=tenants.b)
    assert _abort_code(lambda: env.send(ch, metadata=tok)) == grpc.StatusCode.UNAUTHENTICATED
    assert env.state().next_seq == 0


def test_revoked_device_is_refused(env, grpc_engine):
    with grpc_engine.begin() as c:
        c.execute(text("UPDATE device SET revoked_at = now() WHERE id = :d"), {"d": env.device_id})
    assert _abort_code(lambda: env.send(_chunks(env, 0, 1))) == grpc.StatusCode.UNAUTHENTICATED


def test_sec041_violations_are_stored_as_suspect(env, grpc_engine, tenants, audit_events):
    env.send(_chunks(env, 0, 2))  # t = 100.0 .. 100.199
    jump = env.chunk(2, _data(200, 100), 105.0)  # 4.8 s gap
    replay = env.chunk(3, _data(300, 100), 100.05)  # goes backwards (spliced replay)
    big = _data(400, 100)
    big[10, 2] = 5e6  # 5 V at an EEG electrode
    amp = env.chunk(4, big, 105.3)
    ack = env.send([jump, replay, amp])
    assert (ack.accepted, ack.suspect, ack.next_seq) == (3, 3, 5)
    assert env.state().suspect and env.state().n_samples == 500  # nothing dropped
    with tenant_session(service_principal(tenants.a), engine=grpc_engine) as s:
        segs = s.scalars(select(m.Segment).where(m.Segment.quality == "suspect")).all()
        reasons = " | ".join(x.reason for x in segs)
    assert len(segs) == 3
    assert "jump" in reasons and "backwards" in reasons and "amplitude" in reasons
    evs = [e for e in audit_events(type_="stream.suspect") if e["resource_id"] == env.stream_id]
    assert sorted(e["details"]["seq"] for e in evs) == [2, 3, 4]


def test_shape_and_dtype_must_match_the_registered_stream(env):
    wrong_ch = env.chunk(0, np.zeros((10, N_CH + 1), np.float32), 100.0)
    assert _abort_code(lambda: env.send([wrong_ch])) == grpc.StatusCode.INVALID_ARGUMENT
    msg = _chunks(env, 0, 1)[0]
    del msg.lsl_timestamps[-1]
    assert _abort_code(lambda: env.send([msg])) == grpc.StatusCode.INVALID_ARGUMENT
