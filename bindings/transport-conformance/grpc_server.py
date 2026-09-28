"""Local gRPC ingest test server for CABI-M1 case 10 (HTTP/2 cases). NOT RUN YET: needs grpcio in a
dedicated test venv (requirements-grpc-test.txt), which waits for the owner's install OK.

Started by run_conformance.py --grpc (with NF_GRPC_PYTHON = that venv's python) after tls_server.py:
it reuses the run's `good` certificate, binds 127.0.0.1 only on free ports in 47000-47099, prints one
JSON line with its ports, and stops when stdin closes (or after --max-lifetime seconds).

Only grpcio: generic byte handlers plus a small protobuf codec for the five ingest messages
(proto/ingest/v1/ingest.proto), so neither `protobuf` nor generated stubs are needed.
The event log records the method and whether an NFDevice authorization was PRESENT, never its value.

Servers (one port each):
  grpc_good    GetStreamState / StreamChunks / FinishStream behave like a minimal ingest edge
  grpc_slow    every call sleeps --slow-s before answering (deadline case)
  grpc_big     answers with a StreamState > 1 MiB (reply cap case: library + transport cap 1 MiB)
  grpc_denied  every call ends PERMISSION_DENIED (trailers-only error case)
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import time
from concurrent import futures
from pathlib import Path

import grpc  # test-only dependency (requirements-grpc-test.txt)

HOST = "127.0.0.1"
PORT_MIN, PORT_MAX = 47000, 47099
SERVICE = "neuroforge.ingest.v1.IngestService"


# ---------------------------------------------------------------- minimal protobuf codec
def _varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _field_varint(no: int, v: int) -> bytes:
    return _varint(no << 3) + _varint(v) if v else b""


def _field_bytes(no: int, b: bytes) -> bytes:
    return _varint((no << 3) | 2) + _varint(len(b)) + b if b else b""


def decode(msg: bytes) -> dict[int, list]:
    """Fields of a protobuf message: {field_no: [values]} (varints as int, length-delimited as bytes)."""
    fields: dict[int, list] = {}
    i = 0

    def read_varint() -> int:
        nonlocal i
        shift = result = 0
        while True:
            b = msg[i]
            i += 1
            result |= (b & 0x7F) << shift
            if not b & 0x80:
                return result
            shift += 7

    while i < len(msg):
        key = read_varint()
        no, wt = key >> 3, key & 7
        if wt == 0:
            val: object = read_varint()
        elif wt == 2:
            n = read_varint()
            val = msg[i:i + n]
            i += n
        elif wt == 1:
            val = msg[i:i + 8]
            i += 8
        elif wt == 5:
            val = msg[i:i + 4]
            i += 4
        else:
            raise ValueError(f"unsupported wire type {wt}")
        fields.setdefault(no, []).append(val)
    return fields


def stream_state(stream_id: str, next_seq: int, n_samples: int, state: str) -> bytes:
    return (_field_bytes(1, stream_id.encode()) + _field_varint(2, next_seq) + _field_varint(3, n_samples)
            + _field_bytes(4, state.encode()))


def stream_ack(stream_id: str, next_seq: int, accepted: int) -> bytes:
    return _field_bytes(1, stream_id.encode()) + _field_varint(2, next_seq) + _field_varint(3, accepted)


# ---------------------------------------------------------------- servers
class Events:
    def __init__(self, path: Path) -> None:
        self._path, self._lock = path, threading.Lock()
        path.write_text("", encoding="utf-8")

    def add(self, **fields: object) -> None:
        with self._lock, self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(fields, sort_keys=True) + "\n")


class Store:
    """Per-stream high-water mark of the grpc_good edge (idempotent on seq, like the real one)."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.next_seq: dict[str, int] = {}
        self.samples: dict[str, int] = {}
        self.closed: set[str] = set()


def _log(events: Events, listener: str, method: str, context: grpc.ServicerContext) -> None:
    md = {k.lower(): v for k, v in context.invocation_metadata()}
    auth = md.get("authorization")
    events.add(listener=listener, method=method, authorization_present=auth is not None,
               nfdevice_present=isinstance(auth, str) and auth.startswith("NFDevice "))


def make_handler(listener: str, behaviour: str, events: Events, store: Store, slow_s: float) -> grpc.GenericRpcHandler:
    def before(method: str, context: grpc.ServicerContext) -> None:
        _log(events, listener, method, context)
        if behaviour == "slow":
            time.sleep(slow_s)
        if behaviour == "denied":
            # CR/LF inside the message: the client must neutralise it (nfb-security hardening check)
            context.abort(grpc.StatusCode.PERMISSION_DENIED, "denied by the conformance test server\r\nInjected: 1")

    def get_state(request: bytes, context: grpc.ServicerContext) -> bytes:
        before("GetStreamState", context)
        sid = decode(request).get(1, [b""])[0].decode()
        if behaviour == "big":
            return stream_state("x" * (1536 * 1024), 0, 0, "open")  # > 1 MiB reply
        with store.lock:
            state = "closed" if sid in store.closed else "open"
            return stream_state(sid, store.next_seq.get(sid, 0), store.samples.get(sid, 0), state)

    def stream_chunks(request_iterator, context: grpc.ServicerContext) -> bytes:
        before("StreamChunks", context)
        sid, accepted = "", 0
        for raw in request_iterator:
            f = decode(raw)
            sid = f.get(1, [b""])[0].decode()
            seq = f.get(2, [0])[0]
            n = f.get(3, [0])[0]
            with store.lock:
                if seq == store.next_seq.get(sid, 0):  # in order: accept; duplicates are ignored
                    store.next_seq[sid] = seq + 1
                    store.samples[sid] = store.samples.get(sid, 0) + n
                    accepted += 1
        with store.lock:
            return stream_ack(sid, store.next_seq.get(sid, 0), accepted)

    def finish(request: bytes, context: grpc.ServicerContext) -> bytes:
        before("FinishStream", context)
        sid = decode(request).get(1, [b""])[0].decode()
        with store.lock:
            store.closed.add(sid)
            return stream_state(sid, store.next_seq.get(sid, 0), store.samples.get(sid, 0), "closed")

    return grpc.method_handlers_generic_handler(SERVICE, {
        "GetStreamState": grpc.unary_unary_rpc_method_handler(get_state),
        "StreamChunks": grpc.stream_unary_rpc_method_handler(stream_chunks),
        "FinishStream": grpc.unary_unary_rpc_method_handler(finish),
    })


def _free_port(used: set[int]) -> int:
    for p in range(PORT_MIN, PORT_MAX + 1):
        if p in used:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((HOST, p))
            except OSError:
                continue
        used.add(p)
        return p
    raise RuntimeError(f"no free port in {PORT_MIN}-{PORT_MAX}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cert", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--events", required=True, type=Path)
    ap.add_argument("--slow-s", type=float, default=5.0)
    ap.add_argument("--max-lifetime", type=float, default=150.0)
    ap.add_argument("--exclude", default="", help="comma-separated ports reserved by tls_server.py (never take them)")
    a = ap.parse_args()

    creds = grpc.ssl_server_credentials([(Path(a.key).read_bytes(), Path(a.cert).read_bytes())])
    used = {int(p) for p in a.exclude.split(",") if p}
    events, store = Events(a.events), Store()
    servers, ports = [], {}
    for name, behaviour in (("grpc_good", "good"), ("grpc_slow", "slow"), ("grpc_big", "big"), ("grpc_denied", "denied")):
        port = _free_port(used)
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
        server.add_generic_rpc_handlers((make_handler(name, behaviour, events, store, a.slow_s),))
        bound = server.add_secure_port(f"{HOST}:{port}", creds)  # 127.0.0.1 only
        if bound != port:
            raise RuntimeError(f"{name}: bound {bound}, expected {port}")
        server.start()
        servers.append(server)
        ports[name] = port
    try:
        print(json.dumps({"grpc_ports": ports, "grpc_bound": {n: [HOST, p] for n, p in ports.items()},
                          "grpc_events": str(a.events)}), flush=True)
        done = threading.Event()
        threading.Thread(target=lambda: (sys.stdin.read(), done.set()), daemon=True).start()
        done.wait(a.max_lifetime)
    finally:
        for s in servers:
            s.stop(grace=None).wait(5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
