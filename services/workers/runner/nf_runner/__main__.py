"""``python -m nf_runner`` -- run a worker against the platform database.

Environment: ``NF_DATABASE_URL`` (a login role that may ``SET ROLE nf_worker`` and ``nf_app``),
``NF_OBJECT_ROOT`` (dev object store; in prod ``NF_S3_BUCKET_PREFIX`` + ``NF_KMS_BACKEND=aws``, see
``storage_from_env``, anything else is refused at startup). The dev ``LocalKms`` keeps keys in
process memory, so a separate dev worker cannot decrypt data written by another process; tests run
workers with a shared key set, deployments use the cloud KMS.
"""

from __future__ import annotations

import os

# Thread pins BEFORE numpy/BLAS load (determinism, BLUEPRINT §3.5); same values as
# nf_steps.PINNED_ENV (a test asserts they match).
EARLY_PINS = {
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
    "PYTHONHASHSEED": "0",
}
for _k, _v in EARLY_PINS.items():
    os.environ.setdefault(_k, _v)

import argparse  # noqa: E402
import logging  # noqa: E402
import sys  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    from nf_platform.audit import log as audit  # noqa: PLC0415
    from nf_platform.config import environment_from_env  # noqa: PLC0415
    from nf_platform.db.context import configure_engine  # noqa: PLC0415
    from nf_platform.storage.runtime import required_storage_from_env  # noqa: PLC0415

    from nf_runner.steprunner import CosignVerifier, make_runner  # noqa: PLC0415
    from nf_runner.worker import DEFAULT_KINDS, Worker  # noqa: PLC0415

    ap = argparse.ArgumentParser(prog="nf-worker")
    ap.add_argument("--kinds", default=",".join(DEFAULT_KINDS))
    ap.add_argument(
        "--runner", choices=("inprocess", "subprocess", "container"), default="subprocess"
    )
    ap.add_argument("--cosign-key", help="public key for step image signatures (container runner)")
    ap.add_argument("--lease-s", type=float, default=30.0)
    ap.add_argument("--heartbeat-s", type=float, default=10.0)
    ap.add_argument("--once", action="store_true", help="process at most one job, then exit")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    eng = configure_engine(os.environ["NF_DATABASE_URL"])
    audit.configure(audit.PostgresAuditSink(eng))
    verifier = CosignVerifier(args.cosign_key) if args.cosign_key else None
    worker = Worker(
        engine=eng,
        # Fails closed in prod unless S3 + AWS KMS are configured (NR-H1).
        storage=required_storage_from_env(environment_from_env(), engine=eng),
        runner=make_runner(args.runner, verifier=verifier),
        kinds=tuple(k for k in args.kinds.split(",") if k),
        lease_s=args.lease_s,
        heartbeat_s=args.heartbeat_s,
    )
    if args.once:
        worker.run_once()
    else:
        worker.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
