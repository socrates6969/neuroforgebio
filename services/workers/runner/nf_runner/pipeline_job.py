"""One ``pipeline.run`` job attempt (BUILD-GUIDE 3.3; lifecycle in ``nf_platform.jobs.runs``).

1. start the attempt (tenant session; lease fenced) and delete every staging object of earlier
   attempts of this run (rows AND orphans a dead worker wrote before it could record them);
2. read the input recording (encrypted Zarr) as float64 physical units;
3. run each step through the configured step runner; encrypt each output with the subject's key
   and write it under this attempt's staging prefix, then record it (invisible);
4. finalize: provenance commit, then visibility, then state -- one transaction.

Outputs are encrypted with the recording's subject key, so crypto-shredding a subject also makes
its derived artifacts unreadable (BLUEPRINT §8.4).
"""

from __future__ import annotations

import contextlib
import hashlib
import logging
import re
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from nf_platform.db.context import tenant_session
from nf_platform.governance import policy as gpolicy
from nf_platform.ingest import recording_store as rs
from nf_platform.jobs import queue, runs
from nf_platform.signals.zarr_store import open_recording, read_window
from nf_platform.storage.objects import ObjectNotFound
from nf_platform.storage.runtime import service_principal
from nf_steps import Signal, StepError, signal
from nf_steps.pipeline import step_calls

from nf_runner.steprunner import StepFailed

if TYPE_CHECKING:
    from nf_runner.worker import Lease, Worker

log = logging.getLogger(__name__)
WORKER_PRINCIPAL = "svc:pipeline-worker"
OUTPUT_FILES = (signal.DATA_FILE, signal.META_FILE)
_CODE_RE = re.compile(r"(\d+)\s*$")


def _events(meta: dict[str, Any], sfreq: float, n: int) -> tuple[list[list[int]], dict[str, int]]:
    """Recording annotations -> [[sample, code]] (code = trailing integer of the label, e.g.
    ``stim/1`` -> 1; labels without one are not epoching events)."""
    out, codes = [], {}
    for e in meta.get("events") or []:
        m = _CODE_RE.search(str(e.get("label", "")))
        if not m:
            continue
        sample = round(float(e["onset_s"]) * sfreq)
        if 0 <= sample < n:
            out.append([sample, int(m.group(1))])
            codes[str(e.get("label"))] = int(m.group(1))
    return sorted(out), codes


def load_signal(worker: Worker, tenant_id: str, inp: runs.RunInput) -> tuple[Signal, dict]:
    prefix, group = rs.parse_ref(inp.zarr_ref)
    store = rs.open_store(worker.storage, tenant_id, inp.subject_id, prefix, read_only=True)
    info = open_recording(store, group)
    n, sf = info.n_samples, info.sfreq
    data = read_window(store, group, 0.0, (n + 1) / sf, physical=True)
    names = info.ch_names
    types = inp.ch_types if len(inp.ch_types) == len(names) else ["eeg"] * len(names)
    events, codes = _events(dict(info.attrs.get("meta") or {}), sf, n)
    sig = Signal("raw", data, sf, names, types, events=events)
    return sig, {"event_codes": codes, "n_samples": n, "sfreq": sf}


def _clean_staging(worker: Worker, tenant_id: str, run_id: uuid.UUID, keep: str, keys) -> int:
    """Delete staging objects of other attempts (recorded ones and unrecorded orphans)."""
    objs = worker.storage.objects
    prefix = f"t/{tenant_id}/runs/{run_id}/"
    doomed = set(keys) | {
        k for k in objs.list(runs.ARTIFACT_BUCKET, prefix) if not k.startswith(keep + "/")
    }
    for k in sorted(doomed):
        with contextlib.suppress(ObjectNotFound):
            objs.delete(runs.ARTIFACT_BUCKET, k)
    return len(doomed)


def execute(worker: Worker, job: queue.Job, lease: Lease) -> None:
    """Run one attempt. Raises StepFailed/StepStopped/RunError/LeaseLost for the worker to map."""
    run_id = uuid.UUID(job.payload["run_id"])
    tid = job.tenant_id
    svc = service_principal(tid, WORKER_PRINCIPAL)
    t0 = time.monotonic()
    with tenant_session(svc, engine=worker.engine) as s:
        run, stale = runs.start_attempt(s, run_id, job)
        inp = runs.run_input(s, run)
        # 5.4: consent may have changed since the run was requested (e.g. a withdrawal): the run
        # start is policy-checked again here (consent `processing` + classification).
        try:
            gpolicy.check(
                svc,
                "run:execute",
                gpolicy.Resource("run", tid, str(run_id), recording_id=run.recording_id),
                session=s,
            )
        except gpolicy.PolicyDenied as e:
            raise StepFailed(f"policy: {e.reason}", retryable=False) from e
        record = dict(run.record)
        seed = run.seed
    token_prefix = runs.artifact_prefix(tid, run_id, job.lease_token)
    removed = _clean_staging(worker, tid, run_id, token_prefix, stale)

    try:
        calls = step_calls({"steps": record["steps"]}, worker.extra_libraries)
    except StepError as e:  # unknown/unlisted step or bad parameters: the same on every retry
        raise StepFailed(str(e), retryable=False) from e
    for call, doc in zip(calls, record["steps"], strict=True):
        if call.params != doc.get("params"):
            raise StepFailed(
                f"step {call.id}: published parameters are not fully explicit "
                "(the library resolves different values)",
                retryable=False,
            )
    sig, input_info = load_signal(worker, tid, inp)
    tmp = Path(tempfile.mkdtemp(prefix="nf-run-", dir=worker.workdir))
    try:
        in_dir = tmp / "00-input"
        input_hashes = signal.write(sig, in_dir)
        steps_done: list[dict[str, Any]] = []
        env: dict[str, Any] = {}
        cur = in_dir
        for i, call in enumerate(calls, start=1):
            if lease.should_stop():
                lease.raise_stop()
            out_dir = tmp / f"{i:02d}-{call.id}"
            remaining = max(1.0, job.timeout_s - (time.monotonic() - t0))
            rec = worker.runner.run(
                call, seed, cur, out_dir, timeout_s=remaining, should_stop=lease.should_stop
            )
            for fname in OUTPUT_FILES:
                blob = (out_dir / fname).read_bytes()
                key = runs.artifact_key(tid, run_id, job.lease_token, call.id, fname)
                sealed = worker.storage.keyring.encrypt(
                    tid, inp.subject_id, f"{runs.ARTIFACT_BUCKET}/{key}", 1, blob
                )
                worker.storage.objects.put(
                    runs.ARTIFACT_BUCKET,
                    key,
                    sealed,
                    metadata={"nf-enc": "NFE1", "nf-version": "1"},
                )
                with tenant_session(svc, engine=worker.engine) as s:
                    runs.stage_artifact(
                        s,
                        run_id,
                        job,
                        step=call.id,
                        name=fname,
                        object_key=key,
                        sha256=hashlib.sha256(blob).hexdigest(),
                        size_bytes=len(blob),
                    )
            steps_done.append(
                {
                    "name": call.id,
                    "step": call.step,
                    "params": rec["params"],
                    "seed": rec.get("seed"),
                    "tolerance": call.tolerance,
                    "info": rec.get("info", {}),
                    "outputs": rec.get("outputs", {}),
                }
            )
            env = rec.get("environment", env)
            cur = out_dir
        if lease.should_stop():
            lease.raise_stop()
        execution = {
            "attempt": job.attempts,
            "worker_id": worker.worker_id,
            "runner": worker.runner.name,
            "input": {**input_info, "files_sha256": input_hashes},
            "environment": env,
            "steps": steps_done,
            "staging_objects_removed": removed,
        }
        with tenant_session(svc, engine=worker.engine) as s:
            runs.finalize(s, svc, run_id, job, execution)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
