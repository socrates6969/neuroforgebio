"""``neuroforge.ingest.v1.IngestService`` (BUILD-GUIDE 2.7). Device → platform only (SEC-090).

Per chunk: device token (SEC-016) → shape/dtype checks → ``chunk_id`` recomputed (hashing spec
§5.2) → Ed25519 chunk signature (SEC-040) → one Postgres transaction that locks the stream row,
applies the idempotency rule on ``(stream_id, seq)``, runs the sanity checks (SEC-041), writes the
samples into the encrypted Zarr array at the committed offset, and records the chunk with its
original clock-offset and local-clock series (SEC-094). Acknowledgements say what is stored; they
carry no timing guarantee (SEC-093).

Mid-stream re-checks (M2-REVIEW F2, SEC-017): a ``StreamChunks`` call authenticates once, then
before each chunk checks the token ``exp`` (no I/O) and, at least every ``recheck_interval_s``
(60 s) of wall time or every ``recheck_every_chunks`` chunks (whichever comes first), re-reads the
device's ``revoked_at``. Either failure aborts the call with ``UNAUTHENTICATED`` and a
``stream.aborted`` audit event; the client reconnects with a fresh token and resumes from
``next_seq`` (``GetStreamState``). The check runs when a chunk arrives: an idle stream writes
nothing.

Crypto-shredded subjects (M2-REVIEW F1, SEC-034a): before writing a chunk the service checks the
subject's tombstone; a shredded subject's stream is aborted with ``FAILED_PRECONDITION`` and a
``stream.aborted`` audit event, and nothing (no chunk, no new ``subject_key`` row) is written.

Chunk rate (P7.7 R1, defence in depth for the 20 ms signed-chunk floor that nf-core enforces on
the device): a token bucket per stream (default 150 chunks/s, burst 300: 3x an honest live 20 ms
stream, so a backlog after an outage drains at about 2x real time; nfb-security; Settings
``stream_chunk_rate``/``stream_chunk_burst``, env ``NF_STREAM_CHUNK_RATE``/``_BURST``). Only a NEW
chunk (``seq == next_seq``, checked under the stream row lock) takes a token; a resent chunk that
is already stored never does, so a resume is never refused. A new chunk with no token left is
refused with ``RESOURCE_EXHAUSTED`` (the clients retry with backoff and resume from ``next_seq``)
and a ``stream.rate_limited`` audit event. The bucket lives in this process, on ``self.clock``.
Per-stream state (bucket, short-chunk window) idle for more than ``STATE_IDLE_S`` (10 min) is
dropped, so abandoned streams do not leak: a full bucket equals a fresh one, and an open short-chunk
window is written before its entry is dropped.

Short chunks (audit only, never refused: a refusal would break the resend of a short final
chunk): a chunk shorter than 20 ms at the registered ``sfreq`` is held as "pending" until the
stream's NEXT new chunk is stored; only then is it known not to be the final chunk and counted.
Counted chunks are aggregated per stream into a window that opens at the first count and is
emitted as ONE ``stream.short_chunk`` event (``count``, ``min_duration_ms``) when a chunk arrives
60 s or more after the window opened, or at ``FinishStream``. So while a stream is open there is
at most one event per minute; the final chunk before ``FinishStream`` is never counted. The state
is in-process: a window still open when a stream is abandoned (no chunk, no finish) is not written.
"""

from __future__ import annotations

import logging
import math
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import grpc
import numpy as np
from sqlalchemy import Engine, select

from nf_platform.audit import log as audit
from nf_platform.config import STREAM_CHUNK_BURST, STREAM_CHUNK_RATE
from nf_platform.db import models as m
from nf_platform.db.context import tenant_session
from nf_platform.ingest.recording_store import open_store, parse_ref
from nf_platform.ingest.stream import protocol as proto_rules
from nf_platform.ingest.stream import sanity, writer
from nf_platform.ingest.stream._proto import ingest_pb2 as pb
from nf_platform.ingest.stream._proto import ingest_pb2_grpc as pb_grpc
from nf_platform.storage.keyring import SubjectKeyUnavailable
from nf_platform.storage.runtime import Storage, service_principal

log = logging.getLogger(__name__)
SERVICE_ID = "svc:stream-ingest"
STREAM_SUSPECT = "stream.suspect"
STREAM_CONFLICT = "stream.conflict"
STREAM_ABORTED = "stream.aborted"
STREAM_RATE_LIMITED = "stream.rate_limited"
STREAM_SHORT_CHUNK = "stream.short_chunk"
RECHECK_INTERVAL_S = 60.0  # SEC-017: revocation reaches an open stream within 60 s
RECHECK_EVERY_CHUNKS = 500
CHUNK_RATE = STREAM_CHUNK_RATE  # new chunks per second per stream (token refill)
CHUNK_BURST = STREAM_CHUNK_BURST  # bucket size
MIN_CHUNK_S = 0.020  # nf-core MIN_CHUNK_MS (P7.7 R1)
SHORT_CHUNK_WINDOW_S = 60.0  # at most one stream.short_chunk event per stream per window
STATE_IDLE_S = 600.0  # drop per-stream state after this long without a chunk
EVICT_SWEEP_S = 60.0  # look for idle state at most this often


class _Conflict(Exception):
    """A different chunk arrives for an already committed seq (raised inside the transaction)."""


class _RateLimited(Exception):
    """A new chunk arrives with the stream's token bucket empty (raised inside the transaction)."""


@dataclass
class _Bucket:
    tokens: float
    t: float


@dataclass
class _ShortChunks:
    pending_ms: float | None = None  # last stored chunk, if short (may still be the final one)
    count: int = 0  # short non-final chunks in the open window
    min_ms: float = float("inf")
    window_start: float | None = None
    last: float = 0.0  # time of the stream's last stored chunk (idle eviction)
    tenant_id: str | None = None  # to write the open window if the entry is evicted
    device_id: str | None = None


class Abort(Exception):
    def __init__(self, code: grpc.StatusCode, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class DeviceAuth:
    tenant_id: str
    device_id: str
    stream_id: str
    public_key: bytes
    exp: int = 0  # token expiry (unix seconds); re-checked per chunk (SEC-017)


def _emit(
    type_: str,
    outcome: audit.Outcome,
    *,
    tenant_id: str | None,
    device_id: str | None,
    stream_id: str | None,
    **details: Any,
) -> None:
    audit.emit(
        audit.AuditEvent(
            type=type_,
            outcome=outcome,
            action="stream:ingest",
            tenant_id=tenant_id,
            actor_kind="device" if device_id else None,
            actor_id=device_id,
            auth_method="device_token",
            resource_type="stream",
            resource_id=stream_id,
            details=details,
        )
    )


class IngestServicer(pb_grpc.IngestServiceServicer):
    def __init__(
        self,
        storage: Storage,
        *,
        engine: Engine | None = None,
        clock: Callable[[], float] = time.time,
        recheck_interval_s: float = RECHECK_INTERVAL_S,
        recheck_every_chunks: int = RECHECK_EVERY_CHUNKS,
        chunk_rate: float = CHUNK_RATE,
        chunk_burst: int = CHUNK_BURST,
    ) -> None:
        self.storage = storage
        self.engine = engine
        self.clock = clock
        self.recheck_interval_s = float(recheck_interval_s)
        self.recheck_every_chunks = max(1, int(recheck_every_chunks))
        if not (math.isfinite(chunk_rate) and chunk_rate > 0) or int(chunk_burst) < 1:
            raise ValueError("chunk_rate must be finite and > 0, chunk_burst >= 1")
        self.chunk_rate = float(chunk_rate)
        self.chunk_burst = int(chunk_burst)
        self._live: dict[str, writer.LiveArrays] = {}
        self._buckets: dict[str, _Bucket] = {}
        self._short: dict[str, _ShortChunks] = {}
        self._last_sweep = clock()
        self._lock = threading.Lock()

    # ---------------------------------------------------------------- auth (SEC-016)
    def _svc(self, tenant_id: str):
        return tenant_session(service_principal(tenant_id, SERVICE_ID), engine=self.engine)

    def authenticate(self, context: grpc.ServicerContext) -> DeviceAuth:
        md = dict(context.invocation_metadata() or ())
        header = str(md.get("authorization", ""))
        scheme, _, token = header.partition(" ")
        claims = None
        try:
            if scheme != proto_rules.AUTH_SCHEME or not token:
                raise proto_rules.ProtocolError("missing device token")
            claims, payload, sig = proto_rules.parse_device_token(token.strip())
            uuid.UUID(claims.tenant_id), uuid.UUID(claims.device_id), uuid.UUID(claims.stream_id)
            with self._svc(claims.tenant_id) as s:
                dev = s.scalar(select(m.Device).where(m.Device.id == uuid.UUID(claims.device_id)))
                key = bytes(dev.public_key) if dev is not None and dev.revoked_at is None else None
            if key is None:
                raise proto_rules.ProtocolError("unknown or revoked device")
            proto_rules.verify_device_token(claims, payload, sig, key, now=self.clock())
        except (proto_rules.ProtocolError, ValueError) as e:
            _emit(
                audit.AUTH_FAILURE,
                "failure",
                tenant_id=None,
                device_id=None,
                stream_id=None,
                reason=str(e)[:200],
            )
            raise Abort(grpc.StatusCode.UNAUTHENTICATED, "invalid device token") from e
        _emit(
            audit.AUTH_SUCCESS,
            "success",
            tenant_id=claims.tenant_id,
            device_id=claims.device_id,
            stream_id=claims.stream_id,
        )
        return DeviceAuth(claims.tenant_id, claims.device_id, claims.stream_id, key, claims.exp)

    def _abort_stream(self, auth: DeviceAuth, code: grpc.StatusCode, reason: str) -> Abort:
        _emit(
            STREAM_ABORTED,
            "denied",
            tenant_id=auth.tenant_id,
            device_id=auth.device_id,
            stream_id=auth.stream_id,
            reason=reason,
        )
        with self._lock:
            self._live.pop(auth.stream_id, None)
        log.warning("stream aborted", extra={"stream_id": auth.stream_id})
        return Abort(code, reason)

    def recheck(self, auth: DeviceAuth, *, device: bool) -> None:
        """SEC-017: token expiry (always, no I/O) and device revocation (when ``device``)."""
        if auth.exp < self.clock() - proto_rules.CLOCK_LEEWAY_S:
            raise self._abort_stream(
                auth, grpc.StatusCode.UNAUTHENTICATED, proto_rules.MIDSTREAM_TOKEN_EXPIRED
            )
        if device:
            with self._svc(auth.tenant_id) as s:
                dev = s.scalar(select(m.Device).where(m.Device.id == uuid.UUID(auth.device_id)))
                ok = dev is not None and dev.revoked_at is None
            if not ok:
                raise self._abort_stream(
                    auth, grpc.StatusCode.UNAUTHENTICATED, "device revoked during the stream"
                )

    # ---------------------------------------------------------------- chunk rate / short chunks
    def _evict_idle(self, now: float) -> list[tuple[str, _ShortChunks]]:
        """Drop per-stream state idle for more than STATE_IDLE_S, at most once per EVICT_SWEEP_S.
        Call with the lock held. Returns evicted short-chunk windows that still need writing."""
        if now - self._last_sweep < EVICT_SWEEP_S:
            return []
        self._last_sweep = now
        for sid in [s for s, b in self._buckets.items() if now - b.t > STATE_IDLE_S]:
            del self._buckets[sid]
        evicted = []
        for sid in [s for s, sc in self._short.items() if now - sc.last > STATE_IDLE_S]:
            sc = self._short.pop(sid)
            if sc.count:
                evicted.append((sid, sc))
        return evicted

    def _write_evicted(self, evicted: list[tuple[str, _ShortChunks]]) -> None:
        for sid, sc in evicted:
            count, min_ms = self._take_short_window(sc)
            _emit(
                STREAM_SHORT_CHUNK,
                "success",
                tenant_id=sc.tenant_id,
                device_id=sc.device_id,
                stream_id=sid,
                count=count,
                min_duration_ms=round(min_ms, 3),
            )

    def _take_token(self, stream_id: str) -> bool:
        """Token bucket per stream: refill ``chunk_rate``/s up to ``chunk_burst``; take one."""
        now = self.clock()
        with self._lock:
            evicted = self._evict_idle(now)
            ok = self._take_token_locked(stream_id, now)
        self._write_evicted(evicted)
        return ok

    def _take_token_locked(self, stream_id: str, now: float) -> bool:
        b = self._buckets.get(stream_id)
        if b is None:
            b = self._buckets[stream_id] = _Bucket(float(self.chunk_burst), now)
        elapsed = max(0.0, now - b.t)  # a clock stepping back refills nothing
        b.tokens = min(float(self.chunk_burst), b.tokens + elapsed * self.chunk_rate)
        b.t = now
        if b.tokens < 1.0:
            return False
        b.tokens -= 1.0
        return True

    def _note_chunk(self, auth: DeviceAuth, n_samples: int, sfreq: float) -> None:
        """Audit-only short-chunk tracking for one stored NEW chunk (see the module docstring)."""
        now = self.clock()
        duration_ms = 1000.0 * n_samples / sfreq if sfreq > 0 else float("inf")
        emit = None
        with self._lock:
            evicted = self._evict_idle(now)
            sc = self._short.setdefault(auth.stream_id, _ShortChunks())
            sc.last, sc.tenant_id, sc.device_id = now, auth.tenant_id, auth.device_id
            if sc.pending_ms is not None:  # a chunk followed it: it was not the final chunk
                sc.count += 1
                sc.min_ms = min(sc.min_ms, sc.pending_ms)
                if sc.window_start is None:
                    sc.window_start = now
            short = duration_ms < 1000.0 * MIN_CHUNK_S * (1 - 1e-9)  # f64 tolerance, as nf-core
            sc.pending_ms = duration_ms if short else None
            if sc.count and now - sc.window_start >= SHORT_CHUNK_WINDOW_S:
                emit = self._take_short_window(sc)
        self._write_evicted(evicted)
        if emit is not None:
            self._emit_short(auth, *emit)

    @staticmethod
    def _take_short_window(sc: _ShortChunks) -> tuple[int, float]:
        out = (sc.count, sc.min_ms)
        sc.count, sc.min_ms, sc.window_start = 0, float("inf"), None
        return out

    def _emit_short(self, auth: DeviceAuth, count: int, min_ms: float) -> None:
        _emit(
            STREAM_SHORT_CHUNK,
            "success",
            tenant_id=auth.tenant_id,
            device_id=auth.device_id,
            stream_id=auth.stream_id,
            count=count,
            min_duration_ms=round(min_ms, 3),
        )

    def _end_stream_tracking(self, auth: DeviceAuth) -> None:
        """At FinishStream: write the open short-chunk window (the pending chunk was the final
        one, so it is not counted) and drop this stream's in-process state."""
        with self._lock:
            sc = self._short.pop(auth.stream_id, None)
            self._buckets.pop(auth.stream_id, None)
            emit = self._take_short_window(sc) if sc is not None and sc.count else None
        if emit is not None:
            self._emit_short(auth, *emit)

    def _check_stream_id(self, auth: DeviceAuth, stream_id: str) -> uuid.UUID:
        if stream_id != auth.stream_id:
            raise Abort(grpc.StatusCode.PERMISSION_DENIED, "token is bound to another stream")
        return uuid.UUID(stream_id)

    # ---------------------------------------------------------------- RPCs
    def StreamChunks(self, request_iterator, context):  # noqa: N802 (gRPC naming)
        try:
            auth = self.authenticate(context)
            accepted = duplicates = suspect = 0
            next_seq = None
            last_check, since_check = self.clock(), 0
            for msg in request_iterator:
                since_check += 1
                now = self.clock()
                due = (
                    since_check >= self.recheck_every_chunks
                    or now - last_check >= self.recheck_interval_s
                )
                self.recheck(auth, device=due)
                if due:
                    last_check, since_check = now, 0
                res, next_seq, is_suspect = self.commit(auth, msg)
                if res == "duplicate":
                    duplicates += 1
                else:
                    accepted += 1
                    suspect += int(is_suspect)
            if next_seq is None:
                next_seq = self._state(auth, auth.stream_id).next_seq
            return pb.StreamAck(
                stream_id=auth.stream_id,
                next_seq=next_seq,
                accepted=accepted,
                duplicates=duplicates,
                suspect=suspect,
            )
        except Abort as e:
            context.abort(e.code, e.detail)

    def GetStreamState(self, request, context):  # noqa: N802
        try:
            auth = self.authenticate(context)
            self._check_stream_id(auth, request.stream_id)
            return self._state(auth, request.stream_id)
        except Abort as e:
            context.abort(e.code, e.detail)

    def FinishStream(self, request, context):  # noqa: N802
        try:
            auth = self.authenticate(context)
            sid = self._check_stream_id(auth, request.stream_id)
            state = self.finish(auth, sid)
            self._end_stream_tracking(auth)
            return state
        except Abort as e:
            context.abort(e.code, e.detail)

    # ---------------------------------------------------------------- internals
    def _state(self, auth: DeviceAuth, stream_id: str) -> pb.StreamState:
        with self._svc(auth.tenant_id) as s:
            st = s.scalar(select(m.IngestStream).where(m.IngestStream.id == uuid.UUID(stream_id)))
            if st is None or str(st.device_id) != auth.device_id:
                raise Abort(grpc.StatusCode.NOT_FOUND, "stream not found")
            return pb.StreamState(
                stream_id=stream_id,
                next_seq=st.next_seq,
                n_samples=st.n_samples,
                state=st.state,
                suspect=st.suspect,
            )

    def _channels(self, s, st: m.IngestStream) -> list[m.Channel]:
        q = select(m.Channel).where(m.Channel.recording_id == st.recording_id)
        return list(s.scalars(q.order_by(m.Channel.index)))

    def _live_for(self, s, st: m.IngestStream, rec: m.Recording) -> writer.LiveArrays:
        key = str(st.id)
        with self._lock:
            live = self._live.get(key)
        if live is not None:
            return live
        prefix, _group = parse_ref(rec.zarr_ref)
        store = open_store(self.storage, str(st.tenant_id), str(st.subject_id), prefix)
        chans = self._channels(s, st)
        live = writer.open_live(
            store,
            sfreq=st.sfreq,
            dtype=st.dtype,
            ch_names=[c.name for c in chans],
            units=[c.units for c in chans],
            scale=[float(x) for x in st.ch_scale],
            offset=[float(x) for x in st.ch_offset],
            channels=[
                {
                    "name": c.name,
                    "units": c.units,
                    "sampling_rate": c.sampling_rate,
                    "modality": c.modality,
                    "nervous_system": c.nervous_system,
                    "derived_from_non_neural": c.derived_from_non_neural,
                    "device_ref": c.device_ref,
                }
                for c in chans
            ],
            meta={"source_format": "stream", "stream_id": key},
        )
        with self._lock:
            self._live[key] = live
        return live

    def commit(self, auth: DeviceAuth, msg: Any) -> tuple[str, int, bool]:
        """Store one chunk. Returns ("accepted" | "duplicate", next_seq, suspect)."""
        sid = self._check_stream_id(auth, msg.stream_id)
        try:
            samples = proto_rules.samples_from_bytes(
                bytes(msg.samples), msg.dtype, int(msg.n_samples), int(msg.n_channels)
            )
        except proto_rules.ProtocolError as e:
            raise Abort(grpc.StatusCode.INVALID_ARGUMENT, str(e)) from e
        ts = np.asarray(msg.lsl_timestamps, dtype=np.float64)
        if ts.shape != (msg.n_samples,):
            raise Abort(grpc.StatusCode.INVALID_ARGUMENT, "one LSL timestamp per sample required")
        cid = proto_rules.chunk_id_bytes(
            msg.dtype, [int(msg.n_samples), int(msg.n_channels)], bytes(msg.samples)
        )
        if cid != msg.chunk_id:
            raise Abort(grpc.StatusCode.DATA_LOSS, "chunk_id does not match the samples")
        try:
            sig_ok = proto_rules.verify_chunk_signature(msg, auth.public_key)
        except proto_rules.ProtocolError as e:
            raise Abort(grpc.StatusCode.INVALID_ARGUMENT, str(e)) from e
        if not sig_ok:
            _emit(
                audit.AUTH_FAILURE,
                "failure",
                tenant_id=auth.tenant_id,
                device_id=auth.device_id,
                stream_id=auth.stream_id,
                reason="bad chunk signature",
                seq=int(msg.seq),
            )
            raise Abort(grpc.StatusCode.UNAUTHENTICATED, "chunk signature does not verify")
        offsets = [v for c in msg.clock_offsets for v in (c.collection_time, c.offset)]
        local = [v for c in msg.local_clock for v in (c.lsl_time, c.monotonic_time)]
        reasons: list[str] = []
        stored: dict[str, float] = {}
        try:
            next_seq = self._commit_tx(
                auth, sid, msg, cid, samples, ts, offsets, local, reasons, stored
            )
        except SubjectKeyUnavailable:
            # SEC-034a: the subject was crypto-shredded (tombstoned) while the stream was open
            raise self._abort_stream(
                auth, grpc.StatusCode.FAILED_PRECONDITION, "subject is crypto-shredded"
            ) from None
        except _Conflict:
            _emit(
                STREAM_CONFLICT,
                "denied",
                tenant_id=auth.tenant_id,
                device_id=auth.device_id,
                stream_id=auth.stream_id,
                reason="different chunk for an already committed seq",
                seq=int(msg.seq),
            )
            log.warning("stream chunk conflict", extra={"stream_id": auth.stream_id})
            raise Abort(
                grpc.StatusCode.ALREADY_EXISTS, "a different chunk was committed for seq"
            ) from None
        except _RateLimited:
            limit = f"{self.chunk_rate:g} chunks/s, burst {self.chunk_burst}"
            _emit(
                STREAM_RATE_LIMITED,
                "denied",
                tenant_id=auth.tenant_id,
                device_id=auth.device_id,
                stream_id=auth.stream_id,
                reason=f"new chunk over the per-stream limit ({limit})",
                seq=int(msg.seq),
            )
            log.warning("stream chunk rate limited", extra={"stream_id": auth.stream_id})
            raise Abort(
                grpc.StatusCode.RESOURCE_EXHAUSTED,
                f"chunk rate over {limit}; resend from next_seq after a backoff",
            ) from None
        if next_seq < 0:
            return "duplicate", -next_seq - 1, False
        self._note_chunk(auth, int(msg.n_samples), stored["sfreq"])
        if reasons:
            _emit(
                STREAM_SUSPECT,
                "success",
                tenant_id=auth.tenant_id,
                device_id=auth.device_id,
                stream_id=auth.stream_id,
                reason="; ".join(reasons)[:200],
                seq=int(msg.seq),
            )
        return "accepted", next_seq, bool(reasons)

    def _commit_tx(
        self,
        auth: DeviceAuth,
        sid: uuid.UUID,
        msg: Any,
        cid: str,
        samples: np.ndarray,
        ts: np.ndarray,
        offsets: list[float],
        local: list[float],
        reasons: list[str],
        stored: dict[str, float],
    ) -> int:
        """The locked transaction. Returns next_seq, or -(next_seq + 1) for a duplicate. For a
        stored chunk, ``stored["sfreq"]`` is the stream's registered rate."""
        with self._svc(auth.tenant_id) as s:
            st = s.scalar(select(m.IngestStream).where(m.IngestStream.id == sid).with_for_update())
            if st is None or str(st.device_id) != auth.device_id:
                raise Abort(grpc.StatusCode.NOT_FOUND, "stream not found")
            if self.storage.keyring.is_shredded(str(st.tenant_id), str(st.subject_id)):
                raise SubjectKeyUnavailable("subject is crypto-shredded")  # SEC-034a
            if msg.seq < st.next_seq:
                prev = s.get(m.StreamChunk, (sid, int(msg.seq)))
                if prev is not None and prev.chunk_id == cid:
                    return -int(st.next_seq) - 1
                raise _Conflict()
            if st.state != "open":
                raise Abort(grpc.StatusCode.FAILED_PRECONDITION, "stream is finished")
            elif msg.seq > st.next_seq:
                raise Abort(
                    grpc.StatusCode.FAILED_PRECONDITION,
                    f"expected seq {st.next_seq}; resend from there",
                )
            elif msg.dtype != st.dtype or msg.n_channels != st.n_channels:
                raise Abort(
                    grpc.StatusCode.INVALID_ARGUMENT,
                    "dtype/channel count differ from the registered stream",
                )
            elif not self._take_token(auth.stream_id):  # new chunks only: resends never get here
                raise _RateLimited()
            else:
                stored["sfreq"] = float(st.sfreq)
                rec = s.scalar(select(m.Recording).where(m.Recording.id == st.recording_id))
                chans = self._channels(s, st)
                limits = [
                    sanity.ChannelLimit(c.modality, c.units, float(sc), float(of))
                    for c, sc, of in zip(chans, st.ch_scale, st.ch_offset, strict=True)
                ]
                reasons.extend(sanity.check_chunk(samples, ts, st.sfreq, st.t_last, limits))
                live = self._live_for(s, st, rec)
                start = int(st.n_samples)
                try:
                    st.capacity = writer.write_at(live, start, samples, ts)
                except Exception:
                    with self._lock:
                        self._live.pop(str(sid), None)
                    raise
                s.add(
                    m.StreamChunk(
                        tenant_id=st.tenant_id,
                        stream_id=sid,
                        seq=int(msg.seq),
                        chunk_id=cid,
                        sample_start=start,
                        n_samples=int(msg.n_samples),
                        t_first=float(ts[0]),
                        t_last=float(ts[-1]),
                        clock_offsets=offsets,
                        local_clock=local,
                    )
                )
                if st.t_first is None:
                    st.t_first = float(ts[0])
                if reasons:
                    st.suspect = True
                    t0 = st.t_first
                    a = max(0.0, float(ts[0]) - t0)
                    b = max(a + 1.0 / st.sfreq, float(ts[-1]) - t0 + 1.0 / st.sfreq)
                    s.add(
                        m.Segment(
                            tenant_id=st.tenant_id,
                            recording_id=st.recording_id,
                            start_s=a,
                            end_s=b,
                            zarr_ref=rec.zarr_ref,
                            quality="suspect",
                            reason="; ".join(reasons)[:500],
                        )
                    )
                st.t_last = max(float(ts[-1]), st.t_last if st.t_last is not None else -np.inf)
                st.n_samples = start + int(msg.n_samples)
                st.next_seq = int(msg.seq) + 1
                return int(st.next_seq)

    def finish(self, auth: DeviceAuth, sid: uuid.UUID) -> pb.StreamState:
        with self._svc(auth.tenant_id) as s:
            st = s.scalar(select(m.IngestStream).where(m.IngestStream.id == sid).with_for_update())
            if st is None or str(st.device_id) != auth.device_id:
                raise Abort(grpc.StatusCode.NOT_FOUND, "stream not found")
            if st.state == "open" and st.n_samples > 0:
                rec = s.scalar(select(m.Recording).where(m.Recording.id == st.recording_id))
                q = select(m.StreamChunk).where(m.StreamChunk.stream_id == sid)
                rows = list(s.scalars(q.order_by(m.StreamChunk.seq)))
                offsets = np.asarray([v for r in rows for v in r.clock_offsets]).reshape(-1, 2)
                local = np.asarray([v for r in rows for v in r.local_clock]).reshape(-1, 2)
                prefix, _group = parse_ref(rec.zarr_ref)
                store = open_store(self.storage, str(st.tenant_id), str(st.subject_id), prefix)
                writer.finish(
                    store,
                    int(st.n_samples),
                    offsets,
                    local,
                    {"stream_id": str(sid), "n_chunks": len(rows), "suspect": bool(st.suspect)},
                )
                with self._lock:
                    self._live.pop(str(sid), None)
                rec.duration_s = st.n_samples / st.sfreq
                s.add(
                    m.Segment(
                        tenant_id=st.tenant_id,
                        recording_id=st.recording_id,
                        start_s=0.0,
                        end_s=st.n_samples / st.sfreq,
                        zarr_ref=rec.zarr_ref,
                    )
                )
            if st.state == "open":
                st.state = "closed"
                st.closed_at = datetime.now(UTC)
            return pb.StreamState(
                stream_id=str(sid),
                next_seq=st.next_seq,
                n_samples=st.n_samples,
                state=st.state,
                suspect=st.suspect,
            )
