"""A real worker PROCESS for the kill test (tests only).

    python jobs_worker_proc.py <database url> <object root> <kms key file> <workdir>

The dev ``LocalKms`` keeps its keys in process memory, so the test hands this process a copy of its
key material (a pickle in the test's tmp dir) to read the same encrypted recording. Everything else
is the production worker: the Postgres queue, leases, heartbeats, the in-process step runner.
"""

from __future__ import annotations

import os
import pickle
import sys

for k, v in {"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}.items():
    os.environ.setdefault(k, v)


def main() -> int:
    db_url, root, kms_file, workdir = sys.argv[1:5]
    from nf_platform.storage.keyring import Keyring
    from nf_platform.storage.kms import LocalKms
    from nf_platform.storage.objects import LocalObjectStore
    from nf_platform.storage.runtime import Storage, service_session_for
    from nf_platform.storage.sql_keystore import SqlKeyStore
    from nf_runner.steprunner import InProcessRunner
    from nf_runner.worker import Worker
    from sqlalchemy import create_engine

    engine = create_engine(db_url, pool_size=2, max_overflow=2)
    kms = LocalKms()
    with open(kms_file, "rb") as fh:
        kms._keys = pickle.load(fh)  # test-only: share the parent's dev KMS keys
    storage = Storage(
        objects=LocalObjectStore(root),
        keyring=Keyring(kms, SqlKeyStore(service_session_for(engine))),
    )
    worker = Worker(
        engine=engine,
        storage=storage,
        runner=InProcessRunner(extra_libraries=("nf_jobs_teststeps",)),
        extra_libraries=("nf_jobs_teststeps",),
        lease_s=2.0,
        heartbeat_s=0.5,
        workdir=workdir,
        worker_id="killable-worker",
    )
    print("worker ready", flush=True)  # noqa: T201
    worker.run_once()
    return 0


if __name__ == "__main__":
    sys.exit(main())
