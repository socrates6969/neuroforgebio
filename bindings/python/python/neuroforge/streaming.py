"""Streaming to ``IngestService`` (device -> platform only; BUILD-GUIDE 2.7/4.2).

nf-core does the work: chunking, content IDs, Ed25519 signatures, device tokens, the encrypted
write-ahead buffer (SEC-037) and the resume-from-``next_seq`` sender. This module adds the gRPC
byte transport (``grpcio``, optional extra ``neuroforge[stream]``) and a small acquisition loop.

Timing (SEC-093): ``push`` only writes to the local buffer; the network runs on its own thread,
so a slow or unreachable server never blocks acquisition. Timestamps, clock offsets and local
clock pairs are stored exactly as given (SEC-094).
"""

from __future__ import annotations

import base64
import math
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from . import _native
from .client import Client, get_client

__all__ = [
    "DeviceKey",
    "GrpcTransport",
    "SampleSource",
    "Stream",
    "TransportError",
    "open_stream",
    "register_device",
    "run_acquisition",
]

DeviceKey = _native.DeviceKey
SERVICE = "/neuroforge.ingest.v1.IngestService/"


class TransportError(Exception):
    """A failed call; ``code`` is the gRPC status number (nf-core decides retry vs fatal)."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


def _is_loopback(target: str) -> bool:
    host = target.rsplit(":", 1)[0].strip("[]")
    return host in ("localhost", "::1") or host.startswith("127.")


class GrpcTransport:
    """Raw-bytes grpcio calls. TLS is required except for loopback targets (local testing)."""

    OPTIONS = (
        ("grpc.initial_reconnect_backoff_ms", 100),
        ("grpc.min_reconnect_backoff_ms", 100),
        ("grpc.max_reconnect_backoff_ms", 1000),
        ("grpc.max_send_message_length", 8 * 1024 * 1024),
        ("grpc.keepalive_time_ms", 10_000),
    )

    def __init__(self, target: str, *, credentials: Any = None) -> None:
        import grpc  # optional dependency

        self._grpc = grpc
        if credentials is None and _is_loopback(target):
            self._channel = grpc.insecure_channel(target, options=self.OPTIONS)
        else:
            self._channel = grpc.secure_channel(
                target, credentials or grpc.ssl_channel_credentials(), options=self.OPTIONS
            )
        self._state = self._channel.unary_unary(SERVICE + "GetStreamState")
        self._chunks = self._channel.stream_unary(SERVICE + "StreamChunks")
        self._finish = self._channel.unary_unary(SERVICE + "FinishStream")

    def _call(self, fn, arg, auth: str, timeout: float) -> bytes:
        try:
            return fn(arg, metadata=(("authorization", auth),), timeout=timeout)
        except self._grpc.RpcError as e:
            code = e.code() if hasattr(e, "code") else None
            num = code.value[0] if code is not None else 2
            raise TransportError(num, str(code)) from None

    def get_stream_state(self, request: bytes, auth: str, timeout: float) -> bytes:
        return self._call(self._state, request, auth, timeout)

    def stream_chunks(self, chunks: list[bytes], auth: str, timeout: float) -> bytes:
        return self._call(self._chunks, iter(chunks), auth, timeout)

    def finish_stream(self, request: bytes, auth: str, timeout: float) -> bytes:
        return self._call(self._finish, request, auth, timeout)

    def close(self) -> None:
        self._channel.close()


MIN_CHUNK_MS = 20.0
"""Shortest signed chunk of a regular-rate stream (nf-core ``MIN_CHUNK_MS``, P7.7 R1)."""


@dataclass
class Stream:
    """One open stream: an encrypted WAL, a chunk writer and a sender thread.

    A regular stream needs its nominal rate ``sfreq`` (Hz); chunks last ``chunk_ms``
    milliseconds (default 100, at least 20: nf-core signs per >= 20 ms chunk, never per packet).
    An explicit ``chunk_samples`` overrides ``chunk_ms`` and must also last >= 20 ms. The
    partial chunk written by ``drain``/``flush`` ends the stream: open a new one to continue.
    A stream without a nominal rate (e.g. event markers) passes ``irregular=True`` with
    ``chunk_samples`` and no ``sfreq``; it has no duration check.
    """

    stream_id: str
    tenant_id: str
    device_id: str
    key: Any
    transport: Any
    dtype: str
    n_channels: int
    wal_dir: Path
    sfreq: float | None = None
    chunk_ms: float = 100.0
    chunk_samples: int | None = None
    irregular: bool = False
    wal_key: bytes | None = None
    dpapi_key_path: Path | None = None
    fsync: bool = True
    batch_max: int = 50
    linger_s: float = 0.2
    call_timeout_s: float = 10.0
    backoff_s: tuple[float, float] = (0.05, 1.0)
    recording_id: str | None = None
    _thread: threading.Thread | None = field(default=None, init=False, repr=False)

    def _check_timing(self) -> None:
        if self.irregular:
            if self.sfreq is not None:
                raise ValueError("an irregular stream has no nominal rate: drop sfreq")
            if self.chunk_samples is None:
                raise ValueError("an irregular stream needs chunk_samples")
            return
        if self.sfreq is None:
            raise TypeError(
                "Stream() needs sfreq= (nominal rate in Hz); "
                "pass irregular=True with chunk_samples for a stream without one"
            )
        if isinstance(self.sfreq, bool):
            raise TypeError("sfreq must be a number (Hz)")
        self.sfreq = float(self.sfreq)
        if not math.isfinite(self.sfreq) or self.sfreq <= 0:
            raise ValueError(f"sfreq must be a finite positive rate in Hz, got {self.sfreq}")

    def __post_init__(self) -> None:
        self._check_timing()
        self.wal = _native.Wal(
            os.fspath(self.wal_dir),
            self.stream_id,
            self.wal_key,
            None if self.dpapi_key_path is None else os.fspath(self.dpapi_key_path),
            self.fsync,
        )
        if self.irregular:
            timing: dict[str, Any] = {}
        elif self.chunk_samples is not None:  # explicit length, checked against 20 ms
            timing = {"sfreq": self.sfreq}
        else:
            timing = {"sfreq": self.sfreq, "chunk_ms": float(self.chunk_ms)}
        self.writer = _native.StreamWriter(
            self.stream_id,
            self.dtype,
            self.n_channels,
            self.chunk_samples,
            self.key,
            self.wal,
            **timing,
        )
        self.chunk_samples = self.writer.chunk_samples
        self.sender = _native.Sender(
            self.tenant_id,
            self.device_id,
            self.stream_id,
            self.key,
            self.wal,
            self.batch_max,
            self.linger_s,
            self.call_timeout_s,
            self.backoff_s[0],
            self.backoff_s[1],
        )
        self._np_dtype = np.dtype(self.dtype).newbyteorder("<")

    # -- acquisition side (never blocks on the network)
    def push(self, samples: np.ndarray, timestamps: np.ndarray) -> int:
        """Append ``samples`` (n x n_channels) with one original timestamp per sample."""
        a = np.ascontiguousarray(samples, dtype=self._np_dtype)
        if a.ndim != 2 or a.shape[1] != self.n_channels:
            raise ValueError(f"samples must be (n, {self.n_channels})")
        ts = np.ascontiguousarray(timestamps, dtype="<f8")
        return self.writer.push(a.tobytes(), ts.tobytes())

    def add_clock_offset(self, collection_time: float, offset: float) -> None:
        self.writer.add_clock_offset(float(collection_time), float(offset))

    def add_local_clock(self, lsl_time: float, monotonic_time: float) -> None:
        self.writer.add_local_clock(float(lsl_time), float(monotonic_time))

    # -- sender side
    def start(self) -> Stream:
        if self._thread is None or not self._thread.is_alive():
            self.sender.reset()
            self._thread = threading.Thread(
                target=self.sender.run, args=(self.transport,), name="nf-send", daemon=True
            )
            self._thread.start()
        return self

    @property
    def stats(self) -> dict[str, Any]:
        return {"writer": self.writer.stats(), "sender": self.sender.stats(), "wal": len(self.wal)}

    def drain(self, timeout: float = 60.0) -> bool:
        """Flush the partial chunk and wait until the server acknowledged every record."""
        self.writer.flush()
        deadline = time.monotonic() + timeout
        while (
            len(self.wal) and time.monotonic() < deadline and self.sender.stats()["fatal"] is None
        ):
            time.sleep(0.02)
        self.stop()
        return len(self.wal) == 0

    def stop(self) -> None:
        self.sender.stop()
        if self._thread is not None:
            self._thread.join(timeout=30)

    def state(self) -> dict[str, Any]:
        return self.sender.state(self.transport)

    def finish(self) -> dict[str, Any]:
        """Close the stream on the server (it then builds the pyramid; no more chunks)."""
        return self.sender.finish(self.transport)


def register_device(name: str, key: Any, *, client: Client | None = None) -> str:
    """Register this device's public key (the private key never leaves nf-core)."""
    c = get_client(client)
    out = c.post(
        "/v1/devices", {"name": name, "public_key": base64.b64encode(key.public_key).decode()}
    )
    return out["id"]


def open_stream(
    *,
    device_id: str,
    key: Any,
    sfreq: float,
    channels: list[dict[str, Any]],
    dtype: str = "float32",
    label: str = "stream",
    session: str | None = None,
    wal_dir: str | os.PathLike[str] | None = None,
    synthetic: bool | None = None,
    client: Client | None = None,
    transport: Any = None,
    target: str | None = None,
    **kw: Any,
) -> Stream:
    """Open a stream through the REST API and return a started ``Stream``.

    The chunk writer uses the rate registered with the platform (echoed ``sfreq`` if the
    response carries one, else the value sent), so chunks are cut by time: ``chunk_ms=``
    (default 100, minimum 20) goes through ``**kw``."""
    c = get_client(client)
    sid = session or c.session
    if not sid:
        raise ValueError("no session: pass session= or configure(session=...)")
    target = target or c.ingest_target
    if transport is None and not target:
        raise ValueError("no ingest target: pass target= or configure(ingest_target=...)")
    out = c.post(
        f"/v1/sessions/{sid}/streams",
        {
            "label": label,
            "device_id": device_id,
            "sfreq": sfreq,
            "dtype": dtype,
            "channels": channels,
            "synthetic": c.synthetic if synthetic is None else synthetic,
        },
    )
    who = c.get("/v1/whoami")
    tenant = who.get("tenant_id") or who.get("tenant")
    wd = Path(wal_dir) if wal_dir else Path.home() / ".neuroforge" / "wal" / out["stream_id"]
    return Stream(
        stream_id=out["stream_id"],
        tenant_id=str(tenant),
        device_id=device_id,
        key=key,
        transport=transport or GrpcTransport(target),
        dtype=dtype,
        n_channels=len(channels),
        wal_dir=wd,
        sfreq=float(out.get("sfreq", sfreq)),
        recording_id=out["recording_id"],
        **kw,
    ).start()


class SampleSource(Protocol):
    """What ``run_acquisition`` reads from (an LSL inlet, a synthetic source)."""

    n_channels: int

    def pull_chunk(self, max_samples: int) -> tuple[np.ndarray, np.ndarray]: ...
    def time_correction(self) -> float: ...
    def local_clock(self) -> float: ...


def run_acquisition(
    source: SampleSource,
    stream: Stream,
    stop: threading.Event,
    *,
    offset_interval_s: float = 1.0,
    idle_s: float = 0.005,
    max_samples: int = 1000,
) -> dict[str, float]:
    """Pull from ``source`` into ``stream`` until ``stop`` is set, then drain the source once
    more. Captures a clock offset every ``offset_interval_s`` and a (local, monotonic) clock pair
    for every chunk. Returns acquisition stats (longest loop gap, SEC-093 check).

    Offsets and clock pairs travel with the next emitted chunk; a measurement taken after the
    last sample (no chunk follows) is not sent."""
    last_offset = -float("inf")
    last_iter = time.monotonic()
    max_gap = 0.0
    while True:
        now = time.monotonic()
        max_gap = max(max_gap, now - last_iter)
        last_iter = now
        stopping = stop.is_set()
        data, ts = source.pull_chunk(max_samples)
        lc = source.local_clock()
        if lc - last_offset >= offset_interval_s:
            tc_ex = getattr(source, "time_correction_ex", None)
            if tc_ex is not None:  # LSL inlet: keep the measurement's own collection time
                m = tc_ex()
                stream.add_clock_offset(m.collection_time, m.offset)
            else:
                stream.add_clock_offset(lc, source.time_correction())
            last_offset = lc
        if len(ts):
            if stream.writer.buffered_samples + len(ts) >= stream.chunk_samples:
                stream.add_local_clock(lc, time.monotonic())
            stream.push(data, ts)
        elif stopping:
            return {"max_acq_gap_s": max_gap}
        else:
            time.sleep(idle_s)
