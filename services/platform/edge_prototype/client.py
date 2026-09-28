"""``EdgeClient``: source → encrypted WAL → ``IngestService.StreamChunks`` (BUILD-GUIDE 2.7).

Two threads, decoupled only through the WAL:

- acquisition: pulls samples from the source, cuts fixed-size chunks, attaches the original LSL
  timestamps, the clock-offset series and local-clock pairs (SEC-094), hashes (hashing spec v1
  §5.2) and signs (SEC-040) each chunk and appends it to the WAL. It never touches the network, so
  a stalled or unreachable server cannot block acquisition (SEC-093).
- sender: asks the server for its committed ``next_seq`` (``GetStreamState``), drops acknowledged
  WAL records, and replays the rest in one ``StreamChunks`` call per batch. Any error (cut
  connection, stall past the deadline, restart) → back off, re-sync, resend. The server is
  idempotent on ``(stream_id, seq)``, so overlapping resends are harmless.

The only things sent are chunks and state queries for this device's own stream: nothing flows
towards acquisition hardware (SEC-090).
"""

from __future__ import annotations

import logging
import math
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field

import grpc
import numpy as np
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from nf_platform.ingest.stream import protocol as rules
from nf_platform.ingest.stream._proto import ingest_pb2 as pb
from nf_platform.ingest.stream._proto import ingest_pb2_grpc as pb_grpc

from edge_prototype.source import Source
from edge_prototype.wal import WriteAheadLog

log = logging.getLogger(__name__)

MIN_CHUNK_S = 0.020  # shortest chunk of a regular-rate stream (P7.7 R1, nf-core MIN_CHUNK_MS)

# Errors after which resending the same bytes can never succeed: stop and report.
FATAL = {
    grpc.StatusCode.UNAUTHENTICATED,
    grpc.StatusCode.PERMISSION_DENIED,
    grpc.StatusCode.INVALID_ARGUMENT,
    grpc.StatusCode.ALREADY_EXISTS,
    grpc.StatusCode.DATA_LOSS,
    grpc.StatusCode.NOT_FOUND,
}
CHANNEL_OPTIONS = [
    ("grpc.initial_reconnect_backoff_ms", 100),
    ("grpc.min_reconnect_backoff_ms", 100),
    ("grpc.max_reconnect_backoff_ms", 1000),
    ("grpc.max_send_message_length", 8 * 1024 * 1024),
    ("grpc.keepalive_time_ms", 10_000),
]


@dataclass
class ClientStats:
    chunks_acquired: int = 0
    samples_acquired: int = 0
    chunks_acked: int = 0
    calls: int = 0
    rpc_errors: int = 0
    wal_peak: int = 0
    max_acq_gap_s: float = 0.0  # longest pause between two acquisition-loop iterations
    fatal: str | None = None
    errors: list[str] = field(default_factory=list)


class EdgeClient:
    def __init__(
        self,
        source: Source,
        target: str,
        *,
        device_key: Ed25519PrivateKey,
        tenant_id: str,
        device_id: str,
        stream_id: str,
        wal: WriteAheadLog,
        chunk_samples: int = 100,
        batch_max: int = 50,
        linger_s: float = 0.2,
        call_timeout_s: float = 10.0,
        offset_interval_s: float = 1.0,
        backoff_s: tuple[float, float] = (0.05, 1.0),
        channel_credentials: grpc.ChannelCredentials | None = None,
    ) -> None:
        self.source = source
        self.target = target
        self._key = device_key
        self.tenant_id, self.device_id, self.stream_id = tenant_id, device_id, stream_id
        self.wal = wal
        self.chunk_samples = int(chunk_samples)
        if self.chunk_samples < 1:
            raise ValueError("chunk_samples must be >= 1")
        # P7.7 R1: sign per >= 20 ms chunk, never per packet (nf-core MIN_CHUNK_MS). Streams
        # without a nominal rate (LSL nominal_srate 0, e.g. markers) have no duration: exempt.
        sfreq = float(source.info.sfreq)
        if sfreq > 0 and self.chunk_samples / sfreq < MIN_CHUNK_S * (1 - 1e-9):
            raise ValueError(
                f"chunk of {self.chunk_samples} samples at {sfreq:g} Hz is "
                f"{1000 * self.chunk_samples / sfreq:.3f} ms, shorter than 20 ms: use at least "
                f"{math.ceil(round(MIN_CHUNK_S * sfreq, 9))} samples per chunk"
            )
        self.batch_max = int(batch_max)
        self.linger_s = linger_s
        self.call_timeout_s = call_timeout_s
        self.offset_interval_s = offset_interval_s
        self.backoff_s = backoff_s
        self.stats = ClientStats()
        last = wal.max_seq()
        self._seq = 0 if last is None else last + 1
        self._stop_acq = threading.Event()
        self._stop_send = threading.Event()
        self._acq: threading.Thread | None = None
        self._snd: threading.Thread | None = None
        if channel_credentials is None:
            # Local prototype only; deployments terminate TLS at the edge proxy (BLUEPRINT §7).
            self._channel = grpc.insecure_channel(target, options=CHANNEL_OPTIONS)
        else:
            self._channel = grpc.secure_channel(target, channel_credentials, CHANNEL_OPTIONS)
        self._stub = pb_grpc.IngestServiceStub(self._channel)
        self.next_seq_acked = 0

    # ---------------------------------------------------------------- lifecycle
    def start(self) -> None:
        self._acq = threading.Thread(target=self._acquire_loop, name="nf-acquire", daemon=True)
        self._snd = threading.Thread(target=self._send_loop, name="nf-send", daemon=True)
        self._acq.start()
        self._snd.start()

    def stop_acquisition(self) -> None:
        self._stop_acq.set()
        if self._acq is not None:
            self._acq.join()

    def drain(self, timeout: float = 60.0) -> bool:
        """Stop acquiring, then wait until every WAL record is acknowledged."""
        self.stop_acquisition()
        deadline = time.monotonic() + timeout
        while len(self.wal) and time.monotonic() < deadline and self.stats.fatal is None:
            time.sleep(0.02)
        self._stop_send.set()
        if self._snd is not None:
            self._snd.join(timeout=max(0.1, deadline - time.monotonic()))
        return len(self.wal) == 0

    def finish(self) -> pb.StreamState:
        return self._stub.FinishStream(
            pb.FinishStreamRequest(stream_id=self.stream_id),
            metadata=self._metadata(),
            timeout=self.call_timeout_s * 6,
        )

    def close(self) -> None:
        self._stop_acq.set()
        self._stop_send.set()
        self._channel.close()

    # ---------------------------------------------------------------- acquisition
    def _metadata(self) -> tuple[tuple[str, str], ...]:
        token = rules.make_device_token(
            self._key,
            tenant_id=self.tenant_id,
            device_id=self.device_id,
            stream_id=self.stream_id,
        )
        return (("authorization", f"{rules.AUTH_SCHEME} {token}"),)

    def make_chunk(
        self,
        seq: int,
        samples: np.ndarray,
        ts: np.ndarray,
        offsets: list[tuple[float, float]],
        local: list[tuple[float, float]],
    ) -> pb.Chunk:
        info = self.source.info
        raw = rules.samples_to_bytes(samples, info.dtype)
        msg = pb.Chunk(
            stream_id=self.stream_id,
            seq=seq,
            n_samples=samples.shape[0],
            n_channels=info.n_channels,
            dtype=info.dtype,
            samples=raw,
            lsl_timestamps=[float(x) for x in ts],
            clock_offsets=[pb.ClockOffset(collection_time=a, offset=b) for a, b in offsets],
            local_clock=[pb.LocalClockSample(lsl_time=a, monotonic_time=b) for a, b in local],
            chunk_id=rules.chunk_id_bytes(info.dtype, list(samples.shape), raw),
        )
        rules.sign_chunk(msg, self._key)
        return msg

    def _emit(self, samples, ts, offsets, local) -> None:
        msg = self.make_chunk(self._seq, samples, ts, offsets, local)
        self.wal.append(self._seq, msg.SerializeToString())
        self._seq += 1
        self.stats.chunks_acquired += 1
        self.stats.samples_acquired += samples.shape[0]
        self.stats.wal_peak = max(self.stats.wal_peak, len(self.wal))

    def _acquire_loop(self) -> None:
        info = self.source.info
        bufs: list[np.ndarray] = []
        tss: list[np.ndarray] = []
        have = 0
        offsets: list[tuple[float, float]] = []
        last_offset = -np.inf
        idle = min(0.02, max(0.001, self.chunk_samples / info.sfreq / 4))
        last_iter = time.monotonic()
        try:
            while True:
                now_m = time.monotonic()
                self.stats.max_acq_gap_s = max(self.stats.max_acq_gap_s, now_m - last_iter)
                last_iter = now_m
                stopping = self._stop_acq.is_set()
                data, ts = self.source.pull_chunk(self.chunk_samples - have)
                if len(ts):
                    bufs.append(data)
                    tss.append(ts)
                    have += len(ts)
                lc = self.source.local_clock()
                if lc - last_offset >= self.offset_interval_s:
                    offsets.append((lc, self.source.time_correction()))
                    last_offset = lc
                if have >= self.chunk_samples or (stopping and have):
                    self._emit(
                        np.concatenate(bufs),
                        np.concatenate(tss),
                        offsets,
                        [(lc, time.monotonic())],
                    )
                    bufs, tss, have, offsets = [], [], 0, []
                    continue
                if stopping:
                    return
                if not len(ts):
                    time.sleep(idle)
        except Exception as e:  # noqa: BLE001 - surface, never die silently
            log.exception("acquisition failed")
            self.stats.fatal = f"acquisition: {type(e).__name__}"

    # ---------------------------------------------------------------- sending
    def _batch(self, first: int) -> Iterator[pb.Chunk]:
        seq = first
        for _ in range(self.batch_max):
            if not self.wal.wait_for(seq, self.linger_s):
                return
            yield pb.Chunk.FromString(self.wal.read(seq))
            seq += 1

    def _send_loop(self) -> None:
        next_seq: int | None = None
        backoff = self.backoff_s[0]
        while not self._stop_send.is_set():  # set by drain() (WAL empty or timeout) / close()
            try:
                if next_seq is None:
                    st = self._stub.GetStreamState(
                        pb.StreamStateRequest(stream_id=self.stream_id),
                        metadata=self._metadata(),
                        timeout=self.call_timeout_s,
                    )
                    next_seq = int(st.next_seq)
                    self.wal.ack(next_seq)
                if not self.wal.pending(next_seq):
                    self.wal.wait_for(next_seq, 0.1)
                    continue
                self.stats.calls += 1
                ack = self._stub.StreamChunks(
                    self._batch(next_seq), metadata=self._metadata(), timeout=self.call_timeout_s
                )
                self.stats.chunks_acked += int(ack.next_seq) - next_seq
                next_seq = int(ack.next_seq)
                self.next_seq_acked = next_seq
                self.wal.ack(next_seq)
                backoff = self.backoff_s[0]
            except grpc.RpcError as e:
                code = e.code() if hasattr(e, "code") else None
                self.stats.rpc_errors += 1
                if len(self.stats.errors) < 50:
                    self.stats.errors.append(str(code))
                details = e.details() if hasattr(e, "details") else ""
                # SEC-017: a token that expired mid-call is not fatal: the next call carries a
                # fresh token (``_metadata``) and resumes from the server's next_seq.
                expired = (
                    code == grpc.StatusCode.UNAUTHENTICATED
                    and details == rules.MIDSTREAM_TOKEN_EXPIRED
                )
                if code in FATAL and not expired:
                    self.stats.fatal = f"{code}: {e.details() if hasattr(e, 'details') else ''}"
                    log.error("stream rejected by the server", extra={"code": str(code)})
                    return
                next_seq = None  # re-sync from the server's committed state
                self._stop_send.wait(backoff)
                backoff = min(self.backoff_s[1], backoff * 2)
