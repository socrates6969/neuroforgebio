"""P7.7 R1 on the server (defence in depth for nf-core's 20 ms signed-chunk floor):

- an ENFORCING per-stream token bucket on NEW chunks: over the limit -> ``RESOURCE_EXHAUSTED`` and a
  ``stream.rate_limited`` audit event; the burst is allowed; resent (already stored) chunks never
  take a token, so a resume is never refused;
- an AUDIT-ONLY ``stream.short_chunk`` event: chunks under 20 ms at the registered rate that are
  not the final chunk, aggregated per stream (count + shortest duration), at most one event per
  minute while the stream is open; the final chunk before ``FinishStream`` is exempt.

The servicer's clock is a fake that only moves when a test advances it.
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any

import grpc
import numpy as np
import pytest
from nf_platform.config import (
    STREAM_CHUNK_BURST,
    STREAM_CHUNK_RATE,
    Settings,
    stream_chunk_limits_from_env,
)
from nf_platform.db import models as m
from nf_platform.db.context import tenant_session
from nf_platform.ingest.stream._proto import ingest_pb2 as pb
from nf_platform.ingest.stream.service import (
    EVICT_SWEEP_S,
    STATE_IDLE_S,
    STREAM_RATE_LIMITED,
    STREAM_SHORT_CHUNK,
    DeviceAuth,
    IngestServicer,
)
from nf_platform.storage.runtime import service_principal
from sqlalchemy import create_engine, select
from stream_helpers import open_stream_env

N_CH = 4


class FakeClock:
    def __init__(self) -> None:
        self.t = time.time()
        self._lock = threading.Lock()

    def __call__(self) -> float:
        with self._lock:
            return self.t

    def advance(self, s: float) -> None:
        with self._lock:
            self.t += s


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
        client, as_role("owner"), tree, tenants.a, storage, grpc_engine, n_channels=N_CH
    )
    e.servicer.clock = clock
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


def _sized(env, sizes: list[int]) -> list[pb.Chunk]:
    """Chunks 0.. with the given sample counts, contiguous samples and timestamps."""
    out, pos = [], 0
    for seq, n in enumerate(sizes):
        out.append(env.chunk(seq, _data(pos, n), 100.0 + pos / env.sfreq))
        pos += n
    return out


def _send(env, chunks: list[pb.Chunk]) -> tuple[grpc.StatusCode | None, str, Any]:
    try:
        ack = env.send(chunks, metadata=env.token(now=env.servicer.clock()))
    except grpc.RpcError as e:
        return e.code(), e.details(), None
    return None, "", ack


def _seqs(grpc_engine, tenant_id: str, stream_id: str) -> list[int]:
    with tenant_session(service_principal(tenant_id), engine=grpc_engine) as s:
        q = select(m.StreamChunk.seq).where(m.StreamChunk.stream_id == uuid.UUID(stream_id))
        return list(s.scalars(q.order_by(m.StreamChunk.seq)))


def _events(audit_events, env, type_: str) -> list[dict]:
    return [e for e in audit_events(type_=type_) if e["resource_id"] == env.stream_id]


def _finish(env) -> pb.StreamState:
    return env.stub.FinishStream(
        pb.FinishStreamRequest(stream_id=env.stream_id),
        metadata=env.token(now=env.servicer.clock()),
        timeout=60,
    )


# ------------------------------------------------------------------ settings (no database)
def test_chunk_limit_defaults_and_env(monkeypatch):
    monkeypatch.delenv("NF_STREAM_CHUNK_RATE", raising=False)
    monkeypatch.delenv("NF_STREAM_CHUNK_BURST", raising=False)
    assert (STREAM_CHUNK_RATE, STREAM_CHUNK_BURST) == (150.0, 300)
    assert stream_chunk_limits_from_env() == (150.0, 300)
    assert Settings.__dataclass_fields__["stream_chunk_rate"].default == 150.0
    assert Settings.__dataclass_fields__["stream_chunk_burst"].default == 300
    monkeypatch.setenv("NF_STREAM_CHUNK_RATE", "30")
    monkeypatch.setenv("NF_STREAM_CHUNK_BURST", "45")
    assert stream_chunk_limits_from_env() == (30.0, 45)
    for bad in ("0", "-1", "nan", "inf"):
        monkeypatch.setenv("NF_STREAM_CHUNK_RATE", bad)
        with pytest.raises(ValueError):
            stream_chunk_limits_from_env()
    monkeypatch.setenv("NF_STREAM_CHUNK_RATE", "60")
    monkeypatch.setenv("NF_STREAM_CHUNK_BURST", "0")
    with pytest.raises(ValueError):
        stream_chunk_limits_from_env()


def test_servicer_refuses_a_bad_limit():
    for rate, burst in ((0.0, 10), (float("nan"), 10), (float("inf"), 10), (10.0, 0)):
        with pytest.raises(ValueError):
            IngestServicer(None, chunk_rate=rate, chunk_burst=burst)


# ------------------------------------------------------------------ enforcing chunk-rate limit
@pytest.mark.postgres
def test_new_chunks_over_the_limit_are_refused_and_audited(env, clock, grpc_engine, audit_events):
    env.servicer.chunk_rate, env.servicer.chunk_burst = 1.0, 3
    code, detail, _ = _send(env, _chunks(env, 0, 5))
    assert code == grpc.StatusCode.RESOURCE_EXHAUSTED, (code, detail)
    assert "chunk rate" in detail
    assert _seqs(grpc_engine, env.tenant_id, env.stream_id) == [0, 1, 2]  # the burst of 3
    evs = _events(audit_events, env, STREAM_RATE_LIMITED)
    assert len(evs) == 1
    assert evs[0]["outcome"] == "denied" and evs[0]["actor_id"] == env.device_id
    assert evs[0]["details"]["seq"] == 3
    assert "burst 3" in evs[0]["details"]["reason"]
    # one second refills one token: the next new chunk goes in, the one after is refused again
    clock.advance(1.0)
    code, detail, _ = _send(env, _chunks(env, 3, 2))
    assert code == grpc.StatusCode.RESOURCE_EXHAUSTED, (code, detail)
    assert _seqs(grpc_engine, env.tenant_id, env.stream_id) == [0, 1, 2, 3]
    assert len(_events(audit_events, env, STREAM_RATE_LIMITED)) == 2


@pytest.mark.postgres
def test_the_burst_is_allowed(env, grpc_engine, audit_events):
    env.servicer.chunk_rate, env.servicer.chunk_burst = 1.0, 10
    code, detail, ack = _send(env, _chunks(env, 0, 10))
    assert code is None, (code, detail)
    assert (ack.next_seq, ack.accepted, ack.duplicates) == (10, 10, 0)
    assert _events(audit_events, env, STREAM_RATE_LIMITED) == []


@pytest.mark.postgres
def test_resent_chunks_never_take_a_token(env, clock, grpc_engine, audit_events):
    env.servicer.chunk_rate, env.servicer.chunk_burst = 1.0, 2
    first = _chunks(env, 0, 2)
    code, detail, ack = _send(env, first)
    assert code is None and ack.accepted == 2, (code, detail)
    # over the limit (bucket empty): a resume that resends stored chunks is still acknowledged
    code, detail, ack = _send(env, first)
    assert code is None, (code, detail)
    assert (ack.next_seq, ack.accepted, ack.duplicates) == (2, 0, 2)
    # under the limit (one token): the resends take none, the one new chunk takes it
    clock.advance(1.0)
    code, detail, ack = _send(env, [*first, *_chunks(env, 2, 1)])
    assert code is None, (code, detail)
    assert (ack.next_seq, ack.accepted, ack.duplicates) == (3, 1, 2)
    # and the bucket is empty again: the next new chunk is refused
    code, _, _ = _send(env, _chunks(env, 3, 1))
    assert code == grpc.StatusCode.RESOURCE_EXHAUSTED
    assert _seqs(grpc_engine, env.tenant_id, env.stream_id) == [0, 1, 2]
    assert len(_events(audit_events, env, STREAM_RATE_LIMITED)) == 1


# ------------------------------------------------------------------ audit-only short chunks
@pytest.mark.postgres
def test_short_chunks_are_aggregated_into_one_event(env, grpc_engine, audit_events):
    # 1 kHz: 10 and 5 samples are 10 ms and 5 ms; the last chunk (10 ms) is the final one
    code, detail, ack = _send(env, _sized(env, [100, 10, 5, 100, 10]))
    assert code is None and ack.accepted == 5, (code, detail)  # audit only: nothing refused
    assert _events(audit_events, env, STREAM_SHORT_CHUNK) == []  # window still open
    assert _finish(env).state == "closed"
    evs = _events(audit_events, env, STREAM_SHORT_CHUNK)
    assert len(evs) == 1
    assert evs[0]["outcome"] == "success" and evs[0]["actor_id"] == env.device_id
    assert evs[0]["details"] == {"count": 2, "min_duration_ms": 5.0}


@pytest.mark.postgres
def test_short_chunk_events_at_most_once_per_minute(env, clock, audit_events):
    sizes = [10, 10, 10, 100, 10, 100, 100]
    chunks = _sized(env, sizes)
    code, detail, _ = _send(env, chunks[:3])
    assert code is None, (code, detail)
    clock.advance(61)
    code, detail, _ = _send(env, chunks[3:4])  # confirms the third short chunk; window >= 60 s
    assert code is None, (code, detail)
    evs = _events(audit_events, env, STREAM_SHORT_CHUNK)
    assert [e["details"] for e in evs] == [{"count": 3, "min_duration_ms": 10.0}]
    code, detail, _ = _send(env, chunks[4:])  # one more short chunk, inside the next minute
    assert code is None, (code, detail)
    assert len(_events(audit_events, env, STREAM_SHORT_CHUNK)) == 1
    _finish(env)
    evs = _events(audit_events, env, STREAM_SHORT_CHUNK)
    assert [e["details"] for e in evs] == [
        {"count": 3, "min_duration_ms": 10.0},
        {"count": 1, "min_duration_ms": 10.0},
    ]


@pytest.mark.postgres
def test_final_short_chunk_is_exempt(env, audit_events):
    code, detail, _ = _send(env, _sized(env, [100, 100, 7]))
    assert code is None, (code, detail)
    _finish(env)
    assert _events(audit_events, env, STREAM_SHORT_CHUNK) == []


@pytest.mark.postgres
def test_resent_short_chunk_is_not_counted_twice(env, audit_events):
    chunks = _sized(env, [100, 10, 100])
    code, detail, _ = _send(env, chunks[:2])
    assert code is None, (code, detail)
    code, detail, ack = _send(env, chunks)  # resume: 0 and 1 are duplicates, 2 is new
    assert code is None and (ack.accepted, ack.duplicates) == (1, 2), (code, detail)
    _finish(env)
    evs = _events(audit_events, env, STREAM_SHORT_CHUNK)
    assert [e["details"] for e in evs] == [{"count": 1, "min_duration_ms": 10.0}]


# ------------------------------------------------------------------ catch-up and idle state (no DB)
def test_backlog_after_a_60s_outage_drains_in_about_60s_at_the_live_rate():
    """nfb-security's sizing: at the default 150/s (burst 300), a live 20 ms stream (50 chunks/s)
    that was offline for 60 s (3,000 queued new chunks) catches up in at most about 60 s, while
    the limit still caps a flood. Simulated on the token bucket with a fake clock (20 ms ticks)."""
    clock = FakeClock()
    svc = IngestServicer(None, clock=clock)
    assert (svc.chunk_rate, svc.chunk_burst) == (150.0, 300)
    live_per_tick, tick = 1, 0.020  # one 20 ms chunk per 20 ms
    queue, elapsed = 60 * 50, 0.0  # the backlog: 60 s of 50 chunks/s
    while queue > live_per_tick:
        queue += live_per_tick
        while queue and svc._take_token("s1"):
            queue -= 1
        clock.advance(tick)
        elapsed += tick
        assert elapsed < 120, "backlog did not drain"
    # headroom 100/s after the 300 burst: (3000 - 300) / 100 = 27 s
    assert 20 <= elapsed <= 60, elapsed
    # a flood is still capped: from full, at most burst + rate * 1 s new chunks in one second
    flood = IngestServicer(None, clock=clock)
    n = 0
    for _ in range(50):
        while flood._take_token("f"):
            n += 1
        clock.advance(0.020)
    assert n <= 300 + 150 + 1, n


def test_idle_stream_state_is_evicted_after_10_minutes():
    clock = FakeClock()
    svc = IngestServicer(None, clock=clock)
    assert svc._take_token("old")
    svc._note_chunk(DeviceAuth("t", "d", "old", b"k"), 100, 1000.0)  # 100 ms: not short
    assert "old" in svc._buckets and "old" in svc._short
    clock.advance(STATE_IDLE_S - 1)
    assert svc._take_token("fresh")  # sweep runs, "old" not idle long enough yet
    assert "old" in svc._buckets
    clock.advance(EVICT_SWEEP_S + 1)  # "old" idle > 10 min, and the next sweep is due
    assert svc._take_token("fresh")
    assert "old" not in svc._buckets and "old" not in svc._short
    assert "fresh" in svc._buckets


def test_evicting_an_open_short_chunk_window_writes_it(monkeypatch):
    from nf_platform.ingest.stream import service

    written = []
    monkeypatch.setattr(service, "_emit", lambda type_, outcome, **kw: written.append((type_, kw)))
    clock = FakeClock()
    svc = IngestServicer(None, clock=clock)
    auth = DeviceAuth("t", "d", "gone", b"k")
    svc._note_chunk(auth, 1, 1000.0)
    svc._note_chunk(auth, 1, 1000.0)  # one counted short chunk, window open, no event yet
    assert written == []
    clock.advance(STATE_IDLE_S + 61)
    svc._take_token("other")
    assert [t for t, _ in written] == [STREAM_SHORT_CHUNK]
    assert written[0][1]["stream_id"] == "gone" and written[0][1]["count"] == 1
