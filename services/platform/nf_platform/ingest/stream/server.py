"""gRPC server for ``neuroforge.ingest.v1.IngestService``.

Dev run (local storage; TLS terminates at the edge proxy in deployments, BLUEPRINT §7):

    NF_DATABASE_URL=... NF_OBJECT_ROOT=... python -m nf_platform.ingest.stream.server --port 50051

With NF_ENVIRONMENT=prod the server refuses to start unless storage is S3 + AWS KMS
(``storage_from_env``: NF_S3_BUCKET_PREFIX, NF_KMS_BACKEND=aws).
"""

from __future__ import annotations

import argparse
import os
from concurrent import futures

import grpc
from sqlalchemy import Engine

from nf_platform.audit import log as audit
from nf_platform.config import environment_from_env, stream_chunk_limits_from_env
from nf_platform.db.context import configure_engine
from nf_platform.ingest.stream._proto import ingest_pb2_grpc as pb_grpc
from nf_platform.ingest.stream.service import IngestServicer
from nf_platform.storage.runtime import Storage, required_storage_from_env

MAX_MESSAGE_BYTES = 8 * 1024 * 1024


def build_server(
    servicer: IngestServicer, address: str = "127.0.0.1:0", *, workers: int = 8
) -> tuple[grpc.Server, int]:
    """Create (not start) a server; returns (server, bound port)."""
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=workers),
        options=[
            ("grpc.max_receive_message_length", MAX_MESSAGE_BYTES),
            ("grpc.max_send_message_length", 1024 * 1024),
        ],
    )
    pb_grpc.add_IngestServiceServicer_to_server(servicer, server)
    port = server.add_insecure_port(address)
    if port == 0:
        raise RuntimeError(f"cannot bind {address}")
    return server, port


def serve(
    storage: Storage,
    *,
    engine: Engine | None,
    address: str,
    chunk_rate: float | None = None,
    chunk_burst: int | None = None,
) -> None:
    """Run the server. The per-stream chunk limit defaults to NF_STREAM_CHUNK_RATE/_BURST."""
    env_rate, env_burst = stream_chunk_limits_from_env()
    servicer = IngestServicer(
        storage,
        engine=engine,
        chunk_rate=env_rate if chunk_rate is None else chunk_rate,
        chunk_burst=env_burst if chunk_burst is None else chunk_burst,
    )
    server, port = build_server(servicer, address)
    server.start()
    print(f"ingest gRPC listening on port {port}", flush=True)  # noqa: T201
    server.wait_for_termination()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=50051)
    args = ap.parse_args()
    eng = configure_engine(os.environ["NF_DATABASE_URL"])
    audit.configure(audit.PostgresAuditSink(eng))
    # Fails closed in prod unless S3 + AWS KMS are configured (NR-H1).
    storage = required_storage_from_env(environment_from_env(), engine=eng)
    serve(storage, engine=eng, address=f"{args.host}:{args.port}")


if __name__ == "__main__":
    main()
