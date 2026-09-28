"""Helpers for the gRPC stream tests: an in-process IngestService on 127.0.0.1, a device key
registered through the REST API, an open stream, and chunk builders."""

from __future__ import annotations

import base64
import contextlib
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import grpc
import numpy as np
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from nf_platform.ingest.stream import protocol as rules
from nf_platform.ingest.stream._proto import ingest_pb2 as pb
from nf_platform.ingest.stream._proto import ingest_pb2_grpc as pb_grpc
from nf_platform.ingest.stream.server import build_server
from nf_platform.ingest.stream.service import IngestServicer


def pub_b64(key: Ed25519PrivateKey) -> str:
    return base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()


@dataclass
class StreamEnv:
    tenant_id: str
    device_id: str
    stream_id: str
    recording_id: str
    key: Ed25519PrivateKey
    target: str
    servicer: IngestServicer
    server: grpc.Server
    channel: grpc.Channel
    stub: Any
    n_channels: int
    sfreq: float
    dtype: str
    extra: dict = field(default_factory=dict)

    def token(self, key: Ed25519PrivateKey | None = None, **kw: Any) -> tuple[tuple[str, str]]:
        ids = {
            "tenant_id": self.tenant_id,
            "device_id": self.device_id,
            "stream_id": self.stream_id,
            **kw,
        }
        tok = rules.make_device_token(key or self.key, **ids)
        return (("authorization", f"{rules.AUTH_SCHEME} {tok}"),)

    def chunk(
        self,
        seq: int,
        data: np.ndarray,
        t0: float,
        *,
        key: Ed25519PrivateKey | None = None,
        stream_id: str | None = None,
        offsets: list[tuple[float, float]] | None = None,
        ts: np.ndarray | None = None,
    ) -> pb.Chunk:
        raw = rules.samples_to_bytes(data, self.dtype)
        n = data.shape[0]
        stamps = ts if ts is not None else t0 + np.arange(n) / self.sfreq
        msg = pb.Chunk(
            stream_id=stream_id or self.stream_id,
            seq=seq,
            n_samples=n,
            n_channels=data.shape[1],
            dtype=self.dtype,
            samples=raw,
            lsl_timestamps=[float(x) for x in stamps],
            clock_offsets=[
                pb.ClockOffset(collection_time=a, offset=b) for a, b in (offsets or [(t0, 0.001)])
            ],
            local_clock=[pb.LocalClockSample(lsl_time=float(stamps[-1]), monotonic_time=t0 + 7)],
            chunk_id=rules.chunk_id_bytes(self.dtype, list(data.shape), raw),
        )
        rules.sign_chunk(msg, key or self.key)
        return msg

    def send(self, chunks: list[pb.Chunk], **kw: Any) -> pb.StreamAck:
        md = kw.pop("metadata", None) or self.token()
        return self.stub.StreamChunks(iter(chunks), metadata=md, timeout=30, **kw)

    def state(self) -> pb.StreamState:
        return self.stub.GetStreamState(
            pb.StreamStateRequest(stream_id=self.stream_id), metadata=self.token(), timeout=30
        )

    def finish(self) -> pb.StreamState:
        return self.stub.FinishStream(
            pb.FinishStreamRequest(stream_id=self.stream_id), metadata=self.token(), timeout=60
        )

    def close(self) -> None:
        self.channel.close()
        self.server.stop(grace=None).wait(5)


def open_stream_env(
    client,
    h_owner: dict,
    tree: dict,
    tenant_id: str,
    storage,
    engine,
    *,
    n_channels: int = 4,
    sfreq: float = 1000.0,
    dtype: str = "float32",
    servicer_cls: type[IngestServicer] = IngestServicer,
    port: int | None = None,
) -> StreamEnv:
    key = Ed25519PrivateKey.generate()
    r = client.post(
        "/v1/devices", json={"name": "lab-pc", "public_key": pub_b64(key)}, headers=h_owner
    )
    assert r.status_code == 201, r.text
    device_id = r.json()["id"]
    body = {
        "label": "live",
        "device_id": device_id,
        "sfreq": sfreq,
        "dtype": dtype,
        "channels": [
            {"name": f"EEG{i:03d}", "modality": "EEG", "nervous_system": "central", "units": "uV"}
            for i in range(n_channels)
        ],
        "synthetic": True,
    }
    r = client.post(f"/v1/sessions/{tree['session_id']}/streams", json=body, headers=h_owner)
    assert r.status_code == 201, r.text
    out = r.json()
    servicer = servicer_cls(storage, engine=engine)
    server, bound = build_server(servicer, f"127.0.0.1:{port or 0}")
    server.start()
    target = f"127.0.0.1:{bound}"
    channel = grpc.insecure_channel(target)
    return StreamEnv(
        tenant_id=tenant_id,
        device_id=device_id,
        stream_id=out["stream_id"],
        recording_id=out["recording_id"],
        key=key,
        target=target,
        servicer=servicer,
        server=server,
        channel=channel,
        stub=pb_grpc.IngestServiceStub(channel),
        n_channels=n_channels,
        sfreq=sfreq,
        dtype=dtype,
        extra={"open": out},
    )


class CuttableProxy:
    """A TCP proxy between the edge client and the gRPC server that can drop the network:
    ``cut(seconds)`` closes every live connection and refuses new ones for that long."""

    def __init__(self, upstream: str) -> None:
        host, port = upstream.rsplit(":", 1)
        self.upstream = (host, int(port))
        self._ls = socket.socket()
        self._ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._ls.bind(("127.0.0.1", 0))
        self._ls.listen(16)
        self.address = f"127.0.0.1:{self._ls.getsockname()[1]}"
        self._down_until = 0.0
        self._conns: list[socket.socket] = []
        self._lock = threading.Lock()
        self._stop = False
        self.cuts = 0
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self) -> None:
        while not self._stop:
            try:
                c, _ = self._ls.accept()
            except OSError:
                return
            if time.monotonic() < self._down_until:
                c.close()
                continue
            try:
                u = socket.create_connection(self.upstream, timeout=5)
            except OSError:
                c.close()
                continue
            with self._lock:
                self._conns += [c, u]
            threading.Thread(target=self._pump, args=(c, u), daemon=True).start()
            threading.Thread(target=self._pump, args=(u, c), daemon=True).start()

    @staticmethod
    def _pump(src: socket.socket, dst: socket.socket) -> None:
        try:
            while True:
                b = src.recv(65536)
                if not b:
                    break
                dst.sendall(b)
        except OSError:
            pass
        finally:
            for s in (src, dst):
                with contextlib.suppress(OSError):
                    s.close()

    def cut(self, seconds: float) -> None:
        self.cuts += 1
        self._down_until = time.monotonic() + seconds
        with self._lock:
            conns, self._conns = self._conns, []
        for s in conns:
            with contextlib.suppress(OSError):
                s.shutdown(socket.SHUT_RDWR)
            with contextlib.suppress(OSError):
                s.close()

    def close(self) -> None:
        self._stop = True
        self.cut(0)
        self._ls.close()
