"""3.3 acceptance: killing a worker mid-run leads to a retry by another worker after the lease
expires, with no duplicate outputs.

A real worker process claims the run, stages the first step's outputs and is then killed
(TerminateProcess / SIGKILL: no cleanup, no goodbye). A second worker reaps the expired lease,
retries, removes the dead attempt's staged objects, and publishes exactly one set of outputs with
one provenance activity.
"""

from __future__ import annotations

import os
import pickle
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from jobs_helpers import (
    TEST_LIBRARY,
    artifact_rows,
    job_row,
    pipeline_doc,
    publish,
    start_run,
    step,
    wait_for,
)
from nf_platform.db.context import tenant_session
from nf_platform.provenance import api as prov
from nf_platform.storage.runtime import service_principal
from sqlalchemy import text

pytestmark = pytest.mark.postgres
HERE = Path(__file__).resolve().parent


def test_killed_worker_is_retried_by_another_without_duplicate_outputs(
    client, as_role, synth_rec, worker, engine, storage, tenants, db_url, tmp_path
):
    h = as_role("scientist")
    hold = tmp_path / "hold"
    hold.write_text("x")
    doc = pipeline_doc(
        "killable",
        [
            step("bandpass", "nf_steps.filter@1", {"l_freq": 1.0, "h_freq": 40.0}),
            step("hold", f"{TEST_LIBRARY}.sleep@1", {"seconds": 120.0, "hold_file": str(hold)}),
            step("bads", "nf_steps.bad_channels@1"),
        ],
    )
    run = start_run(client, h, publish(client, h, doc), synth_rec["recording_id"])
    with engine.begin() as c:  # no retry backoff in the test (the lease expiry is the wait)
        c.execute(
            text("UPDATE job SET backoff_s = 0 WHERE id = (SELECT job_id FROM run WHERE id = :r)"),
            {"r": run["id"]},
        )

    kms_file = tmp_path / "kms.pkl"
    kms_file.write_bytes(pickle.dumps(storage.keyring._kms._keys))  # test-only key hand-over
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(HERE), *sys.path])}
    proc = subprocess.Popen(
        [
            sys.executable,
            str(HERE / "jobs_worker_proc.py"),
            db_url,
            str(storage.objects.root),
            str(kms_file),
            str(tmp_path),
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        # the first worker is mid-run: step 1 staged, step 2 holding
        wait_for(lambda: len(artifact_rows(engine, run["id"])) >= 2, timeout_s=120)
        dead = job_row(engine, run["id"])
        assert dead["state"] == "running" and dead["worker_id"] == "killable-worker"
        dead_token = dead["lease_token"]
        proc.kill()
        proc.wait(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=30)
    staged_dead = artifact_rows(engine, run["id"])
    assert {a["attempt_token"] for a in staged_dead} == {dead_token}
    prefix = f"t/{tenants.a}/runs/{run['id']}/"
    dead_objects = set(storage.objects.list("artifacts", prefix))
    assert dead_objects, "the dead attempt left staged objects behind"

    hold.unlink()  # the retry should not wait
    # another worker: nothing to claim until the dead worker's lease expires (2 s), then a retry
    wait_for(lambda: worker.run_once() is not None, timeout_s=30, every_s=0.5)

    out = client.get(f"/v1/runs/{run['id']}", headers=h).json()
    assert out["state"] == "succeeded", out["error"]
    jr = job_row(engine, run["id"])
    assert jr["attempts"] == 2 and jr["state"] == "succeeded"
    assert out["record"]["execution"]["worker_id"] != "killable-worker"

    # exactly one output per (step, file): no duplicates, all from the retry, all visible
    rows = artifact_rows(engine, run["id"])
    keys = [(r["step"], r["name"]) for r in rows]
    assert len(keys) == len(set(keys)) == 6
    assert all(r["visible_at"] is not None for r in rows)
    assert all(r["attempt_token"] != dead_token for r in rows)
    assert len(out["artifacts"]) == 6
    # the dead attempt's staged objects are gone; the store holds exactly the published ones
    assert set(storage.objects.list("artifacts", prefix)) == {r["object_key"] for r in rows}
    assert not (dead_objects & {r["object_key"] for r in rows})

    # one run activity in the provenance graph, generating the six artifacts
    svc = service_principal(tenants.a, "svc:test")
    with tenant_session(svc, engine=engine) as s:
        act = prov.find_node(s, prov.ProvKind.ACTIVITY, "run", run["id"])
        assert act == uuid.UUID(out["prov_activity_id"])
        down = prov.lineage(s, act, "down", 1)
        assert len([n for n in down.nodes if n.type == "artifact"]) == 6
    with engine.connect() as c:
        n = c.execute(
            text("SELECT count(*) FROM prov_node WHERE type = 'run' AND ref_id = :r"),
            {"r": run["id"]},
        ).scalar_one()
    assert n == 1
