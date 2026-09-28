"""M2-REVIEW fixes on the live stream (m5-secfix):

- F1 / SEC-034a: a subject shredded while its stream is open -> the next chunk is refused with
  ``FAILED_PRECONDITION``, a ``stream.aborted`` audit event is written, no new ``subject_key`` row
  appears, and a reconnect is refused as well;
- F2 / SEC-017: device revocation and token expiry are re-checked inside ``StreamChunks`` (every
  60 s of wall time or every N chunks, whichever comes first) with an injectable clock; the stream
  is aborted with ``UNAUTHENTICATED``; a client with a fresh token resumes from ``next_seq``;
- F5 / SEC-147: the device-auth failure audit row never contains the token (or any part of it).
"""

from __future__ import annotations

import json
import queue
import threading
import uuid
from collections.abc import Callable, Iterator

import grpc
import numpy as np
import pytest
from nf_platform.audit import log as audit
from nf_platform.db import models as m
from nf_platform.db.context import tenant_session
from nf_platform.ingest.stream import protocol as rules
from nf_platform.ingest.stream._proto import ingest_pb2 as pb
from nf_platform.ingest.stream.service import STREAM_ABORTED, IngestServicer
from nf_platform.storage.keyring import SubjectKeyUnavailable
from nf_platform.storage.runtime import service_principal
from sqlalchemy import create_engine, select, text
from stream_helpers import open_stream_env

pytestmark = pytest.mark.postgres
N_CH = 4


class FakeClock:
    def __init__(self) -> None:
        import time

        self.t = time.time()
        self._lock = threading.Lock()

    def __call__(self) -> float:
        with self._lock:
            return self.t

    def advance(self, s: float) -> None:
        with self._lock:
            self.t += s


class TracedServicer(IngestServicer):
    """Reports every processed chunk (or abort) so a test can act between two chunks of ONE
    client-streaming call deterministically."""

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.events: queue.Queue = queue.Queue()

    def authenticate(self, context):
        try:
            return super().authenticate(context)
        except Exception:
            self.events.put(("abort", None))
            raise

    def recheck(self, auth, *, device):
        try:
            return super().recheck(auth, device=device)
        except Exception:
            self.events.put(("abort", None))
            raise

    def commit(self, auth, msg):
        try:
            return super().commit(auth, msg)
        finally:
            self.events.put(("chunk", int(msg.seq)))


@pytest.fixture
def grpc_engine(db_url):
    eng = create_engine(db_url, pool_size=4, max_overflow=4)
    yield eng
    eng.dispose()


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def env(client, as_role, tree, tenants, storage, grpc_engine, clock):
    e = open_stream_env(
        client,
        as_role("owner"),
        tree,
        tenants.a,
        storage,
        grpc_engine,
        n_channels=N_CH,
        servicer_cls=TracedServicer,
    )
    e.servicer.clock = clock
    yield e
    e.close()


def _data(start: int, n: int) -> np.ndarray:
    i = np.arange(start, start + n)[:, None]
    return (np.sin(i / 7.0 + np.arange(N_CH)[None, :]) * 30).astype(np.float32)


def _chunk(env, seq: int, n: int = 100) -> pb.Chunk:
    return env.chunk(seq, _data(seq * n, n), 100.0 + seq * n / env.sfreq)


def _scripted(env, steps: list[tuple[pb.Chunk, Callable[[], None] | None]]) -> Iterator[pb.Chunk]:
    """Yield each chunk after running its action, then wait until the server processed it."""
    for chunk, action in steps:
        if action is not None:
            action()
        yield chunk
        try:
            kind, _ = env.servicer.events.get(timeout=20)
        except queue.Empty:
            return
        if kind == "abort":
            return


def _call(env, steps, metadata=None) -> tuple[grpc.StatusCode | None, str, pb.StreamAck | None]:
    # An earlier call that failed (e.g. a refused token) can leave its event unconsumed; a stale
    # "abort" would end this call's script after one chunk (flaky under load). Start clean.
    while True:
        try:
            env.servicer.events.get_nowait()
        except queue.Empty:
            break
    md = metadata or env.token(now=env.servicer.clock())
    try:
        ack = env.stub.StreamChunks(_scripted(env, steps), metadata=md, timeout=60)
    except grpc.RpcError as e:
        return e.code(), e.details(), None
    return None, "", ack


def _state(env, clock) -> pb.StreamState:
    return env.stub.GetStreamState(
        pb.StreamStateRequest(stream_id=env.stream_id), metadata=env.token(now=clock()), timeout=30
    )


def _seqs(grpc_engine, tenant_id: str, stream_id: str) -> list[int]:
    with tenant_session(service_principal(tenant_id), engine=grpc_engine) as s:
        q = select(m.StreamChunk.seq).where(m.StreamChunk.stream_id == uuid.UUID(stream_id))
        return list(s.scalars(q.order_by(m.StreamChunk.seq)))


def _aborts(audit_events, env) -> list[dict]:
    return [e for e in audit_events(type_=STREAM_ABORTED) if e["resource_id"] == env.stream_id]


def _key_rows(engine, subject_id: str) -> list[tuple]:
    with engine.connect() as c:
        return [
            tuple(r)
            for r in c.execute(
                text(
                    "SELECT dek_version, state, wrapped_dek IS NULL FROM subject_key "
                    "WHERE subject_id = :s ORDER BY dek_version"
                ),
                {"s": subject_id},
            )
        ]


# ------------------------------------------------------------------ F1 / SEC-034a
def test_sec034a_shred_during_open_stream_aborts_it(
    env, storage, tree, tenants, grpc_engine, engine, audit_events
):
    sid = tree["subject_id"]
    state: dict = {}

    def shred() -> None:
        state["keys_before"] = _key_rows(engine, sid)
        assert state["keys_before"], "the stream's first chunks created the subject key"
        assert storage.keyring.shred_subject(tenants.a, sid) >= 1

    code, detail, _ = _call(
        env, [(_chunk(env, 0), None), (_chunk(env, 1), None), (_chunk(env, 2), shred)]
    )
    assert code == grpc.StatusCode.FAILED_PRECONDITION, (code, detail)
    assert "crypto-shredded" in detail
    # the chunk after the shred is refused; nothing more was stored
    assert _seqs(grpc_engine, tenants.a, env.stream_id) == [0, 1]
    # no new subject_key row: the same versions, all tombstoned without key material
    after = _key_rows(engine, sid)
    assert [v for v, *_ in after] == [v for v, *_ in state["keys_before"]]
    assert all(st == "shredded" and gone for _v, st, gone in after)
    # the abort is audited
    evs = _aborts(audit_events, env)
    assert evs and evs[-1]["details"]["reason"] == "subject is crypto-shredded"
    assert evs[-1]["outcome"] == "denied" and evs[-1]["actor_id"] == env.device_id
    # a reconnect for the shredded subject is refused as well, and encrypt still raises
    code, _, _ = _call(env, [(_chunk(env, 2), None)])
    assert code == grpc.StatusCode.FAILED_PRECONDITION
    assert _seqs(grpc_engine, tenants.a, env.stream_id) == [0, 1]
    assert [v for v, *_ in _key_rows(engine, sid)] == [v for v, *_ in state["keys_before"]]
    with pytest.raises(SubjectKeyUnavailable):
        storage.keyring.encrypt(tenants.a, sid, "raw/t/x", 1, b"new data")


# ------------------------------------------------------------------ F2 / SEC-017
def _revoke(grpc_engine, device_id: str) -> None:
    with grpc_engine.begin() as c:
        c.execute(text("UPDATE device SET revoked_at = now() WHERE id = :d"), {"d": device_id})


def test_sec017_revoked_mid_stream_is_aborted_within_60s(
    env, clock, grpc_engine, tenants, audit_events
):
    env.servicer.recheck_every_chunks = 10**6  # time-based re-check only

    def revoke_then_30s() -> None:
        _revoke(grpc_engine, env.device_id)
        clock.advance(30)

    code, detail, _ = _call(
        env,
        [
            (_chunk(env, 0), None),
            (_chunk(env, 1), None),
            (_chunk(env, 2), revoke_then_30s),  # revoked; not yet re-checked (inside 60 s)
            (_chunk(env, 3), lambda: clock.advance(31)),  # 61 s after the last check
            (_chunk(env, 4), None),
        ],
    )
    assert code == grpc.StatusCode.UNAUTHENTICATED, (code, detail)
    assert detail == "device revoked during the stream"
    # aborted no later than 60 s after the revocation: chunk 3 (t = +61 s) was not stored
    assert _seqs(grpc_engine, tenants.a, env.stream_id) == [0, 1, 2]
    evs = _aborts(audit_events, env)
    assert evs and evs[-1]["details"]["reason"] == "device revoked during the stream"
    # the revoked device cannot reconnect
    code, _, _ = _call(env, [(_chunk(env, 3), None)])
    assert code == grpc.StatusCode.UNAUTHENTICATED


def test_sec017_revoked_mid_stream_is_aborted_within_n_chunks(env, grpc_engine, tenants):
    env.servicer.recheck_every_chunks = 3  # the clock never moves: the chunk count triggers it
    code, detail, _ = _call(
        env,
        [
            (_chunk(env, 0), None),
            (_chunk(env, 1), lambda: _revoke(grpc_engine, env.device_id)),
            (_chunk(env, 2), None),
            (_chunk(env, 3), None),
        ],
    )
    assert code == grpc.StatusCode.UNAUTHENTICATED, (code, detail)
    assert _seqs(grpc_engine, tenants.a, env.stream_id) == [0, 1]


def test_sec017_token_expiry_mid_stream_then_resume(env, clock, grpc_engine, tenants, audit_events):
    tok = env.token(lifetime_s=60, now=clock())
    code, detail, _ = _call(
        env,
        [
            (_chunk(env, 0), None),
            (_chunk(env, 1), None),
            # exp + the 30 s clock leeway has passed
            (_chunk(env, 2), lambda: clock.advance(60 + rules.CLOCK_LEEWAY_S + 1)),
        ],
        metadata=tok,
    )
    assert code == grpc.StatusCode.UNAUTHENTICATED, (code, detail)
    assert detail == rules.MIDSTREAM_TOKEN_EXPIRED
    assert _seqs(grpc_engine, tenants.a, env.stream_id) == [0, 1]
    evs = _aborts(audit_events, env)
    assert evs and evs[-1]["details"]["reason"] == rules.MIDSTREAM_TOKEN_EXPIRED
    # the old token is refused outright; a fresh token resumes from the committed next_seq
    code, _, _ = _call(env, [(_chunk(env, 2), None)], metadata=tok)
    assert code == grpc.StatusCode.UNAUTHENTICATED
    nxt = _state(env, clock).next_seq
    assert nxt == 2
    code, detail, ack = _call(env, [(_chunk(env, s), None) for s in range(nxt, nxt + 3)])
    assert code is None, (code, detail)
    assert (ack.next_seq, ack.accepted, ack.duplicates) == (5, 3, 0)
    assert _seqs(grpc_engine, tenants.a, env.stream_id) == [0, 1, 2, 3, 4]


# ------------------------------------------------------------------ F5 / SEC-147
def test_sec147_device_auth_failure_audit_has_no_token(env, audit_events):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    marker = "tok-SECRET-4f1c9e"
    good = rules.make_device_token(
        env.key, tenant_id=env.tenant_id, device_id=env.device_id, stream_id=env.stream_id
    )
    tokens = [
        # signed by another key (signature does not verify)
        rules.make_device_token(
            Ed25519PrivateKey.generate(),
            tenant_id=env.tenant_id,
            device_id=env.device_id,
            stream_id=env.stream_id,
        ),
        # attacker-controlled claim values (not UUIDs)
        rules.make_device_token(
            env.key, tenant_id=marker, device_id=marker, stream_id=env.stream_id
        ),
        # garbage in every part
        f"nfd1.{marker}.{marker}",
        f"{marker}.{marker}",
        # a real token with the signature cut off
        good.rsplit(".", 1)[0] + ".AAAA",
    ]
    before = len(audit_events(type_=audit.AUTH_FAILURE))
    for tok in tokens:
        md = (("authorization", f"{rules.AUTH_SCHEME} {tok}"),)
        code, _, _ = _call(env, [(_chunk(env, 0), None)], metadata=md)
        assert code == grpc.StatusCode.UNAUTHENTICATED
    rows = audit_events(type_=audit.AUTH_FAILURE)[before:]
    assert len(rows) == len(tokens)
    blob = json.dumps(rows, default=str)
    assert marker not in blob
    for tok in [*tokens, good]:
        for part in [tok, *tok.split(".")]:
            if len(part) >= 8:  # every token part long enough to be meaningful
                assert part not in blob, part
    assert all(set(r["details"]) <= {"reason"} for r in rows)
    # defence in depth: the audit layer itself refuses a device token in any field
    with pytest.raises(audit.AuditPayloadError):
        audit.validate(
            audit.AuditEvent(type=audit.AUTH_FAILURE, outcome="failure", details={"reason": good})
        )
