"""3.3 acceptance: runs through the queue and the in-process worker.

- a run's outputs are invisible until its provenance commit succeeds (fault injection: the
  provenance commit fails -> the outputs stay staged and unlisted; the retry publishes exactly one
  set);
- the run record carries every resolved parameter (defaults included), the seed, thread pins and
  library versions;
- cancel, tenant isolation (A cannot see, run on or cancel B's objects), quarantine, non-explicit
  parameters, and M2's upload conversion moved onto the queue.
"""

from __future__ import annotations

import hashlib
import threading
import uuid

import numpy as np
import pytest
from jobs_helpers import (
    TEST_LIBRARY,
    artifact_rows,
    job_row,
    make_due,
    pipeline_doc,
    publish,
    quick_doc,
    start_run,
    step,
    wait_for,
)
from nf_platform.db.context import tenant_session
from nf_platform.jobs import runs
from nf_platform.provenance import api as prov
from nf_platform.storage.runtime import service_principal
from nf_steps import Signal, signal
from nf_steps.pipeline import run_chain, step_calls
from nf_synth.generate import SynthParams, generate
from nf_synth.writers import write_edf
from sqlalchemy import text

pytestmark = pytest.mark.postgres


def _get(client, h, run_id):
    r = client.get(f"/v1/runs/{run_id}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _decrypt(storage, tenant, subject, key: str) -> bytes:
    blob = storage.objects.get("artifacts", key)
    return storage.keyring.decrypt(tenant, subject, f"artifacts/{key}", 1, blob)


def test_run_end_to_end_with_record_and_provenance(
    client, as_role, synth_rec, worker, engine, storage, tenants, tree
):
    from nf_runner.steprunner import SubprocessRunner

    worker.runner = SubprocessRunner()  # pinned threads in a fresh interpreter per step
    h = as_role("scientist")
    ref = publish(client, h, quick_doc())
    run = start_run(client, h, ref, synth_rec["recording_id"])
    assert run["state"] == "queued" and run["artifacts"] == []
    assert worker.run_once() is not None
    out = _get(client, h, run["id"])
    assert out["state"] == "succeeded", out["error"]
    names = {(a["step"], a["name"]) for a in out["artifacts"]}
    assert names == {(s, f) for s in ("bandpass", "bads", "bandpower") for f in signal.FILES}

    # run record: every parameter with its default, the seed, thread pins, library versions
    rec = out["record"]
    doc = quick_doc()
    assert [s["params"] for s in rec["steps"]] == [s["params"] for s in doc["steps"]]
    ex = rec["execution"]
    assert [s["params"] for s in ex["steps"]] == [s["params"] for s in doc["steps"]]
    assert ex["environment"]["mne"] and ex["environment"]["threads"]["OMP_NUM_THREADS"] == "1"
    assert rec["seed"] == out["seed"] == 1
    assert ex["steps"][1]["info"]["detected"] == ["C3"]  # synthetic ground truth: bad channel

    # outputs are encrypted with the subject key and equal an in-process run of the same chain
    arts = {(a["step"], a["name"]): a for a in artifact_rows(engine, run["id"])}
    key = arts[("bandpower", signal.DATA_FILE)]["object_key"]
    raw = storage.objects.get("artifacts", key)
    assert raw[:4] == b"NFE1"
    got = signal.from_files(
        {
            f: _decrypt(
                storage, tenants.a, tree["subject_id"], arts[("bandpower", f)]["object_key"]
            )
            for f in signal.FILES
        }
    )
    truth = synth_rec["truth"]
    sig = Signal(
        "raw",
        synth_rec["data"],
        float(truth["sfreq"]),
        list(truth["channels"]),
        ["eeg"] * 8,
        events=[[e["sample"], e["code"]] for e in truth["events"]],
    )
    ref_out = run_chain(step_calls(doc), sig, 1)[-1][1].signal
    np.testing.assert_allclose(got.data, ref_out.data, rtol=1e-6)

    # provenance: the run used the recording, was associated with the PipelineVersion, and
    # generated every artifact
    svc = service_principal(tenants.a, "svc:test")
    with tenant_session(svc, engine=engine) as s:
        g = prov.lineage(s, uuid.UUID(out["prov_activity_id"]), "up", 1)
        kinds = {(n.kind.value, n.type) for n in g.nodes}
        assert ("entity", "recording") in kinds and ("agent", "pipeline_version") in kinds
        down = prov.lineage(s, uuid.UUID(out["prov_activity_id"]), "down", 1)
        assert len([n for n in down.nodes if n.type == "artifact"]) == 6
        assert prov.verify_chain(s, tenants.a).ok


def test_outputs_invisible_until_provenance_commit_succeeds(
    client, as_role, synth_rec, worker, engine, monkeypatch
):
    """Fault injection: the provenance commit fails after every output was staged."""
    h = as_role("scientist")
    run = start_run(client, h, publish(client, h, quick_doc()), synth_rec["recording_id"])

    def broken_record(*a, **k):
        raise RuntimeError("injected provenance failure")

    monkeypatch.setattr(runs.prov, "record", broken_record)
    worker.run_once()
    staged = artifact_rows(engine, run["id"])
    assert len(staged) == 6, "every output was written and staged"
    assert all(a["visible_at"] is None for a in staged)
    out = _get(client, h, run["id"])
    assert out["artifacts"] == [] and out["state"] == "queued"
    assert "injected provenance failure" in out["error"]
    assert out["prov_batch_id"] is None
    with engine.connect() as c:  # no provenance of the run exists either
        n = c.execute(
            text("SELECT count(*) FROM prov_node WHERE type = 'run' AND ref_id = :r"),
            {"r": run["id"]},
        ).scalar_one()
    assert n == 0
    first_token = staged[0]["attempt_token"]

    # the fault is gone: the retry publishes exactly one set of outputs
    monkeypatch.undo()
    make_due(engine, run["id"])
    worker.run_once()
    out = _get(client, h, run["id"])
    assert out["state"] == "succeeded" and len(out["artifacts"]) == 6
    rows = artifact_rows(engine, run["id"])
    assert len(rows) == 6 and all(r["visible_at"] is not None for r in rows)
    assert all(r["attempt_token"] != first_token for r in rows)
    assert job_row(engine, run["id"])["attempts"] == 2


def test_cancel_queued_and_running_runs(client, as_role, synth_rec, worker, engine, tmp_path):
    h = as_role("scientist")
    ref = publish(client, h, quick_doc())
    queued = start_run(client, h, ref, synth_rec["recording_id"])
    r = client.post(f"/v1/runs/{queued['id']}/cancel", headers=h)
    assert r.status_code == 202 and r.json()["state"] == "cancelled"
    assert worker.run_once() is None  # nothing left to claim

    hold = tmp_path / "hold"
    hold.write_text("x")
    slow = pipeline_doc(
        "slow",
        [
            step("bandpass", "nf_steps.filter@1", {"l_freq": 1.0, "h_freq": 40.0}),
            step("hold", f"{TEST_LIBRARY}.sleep@1", {"seconds": 30.0, "hold_file": str(hold)}),
            step("bads", "nf_steps.bad_channels@1"),
        ],
    )
    running = start_run(client, h, publish(client, h, slow), synth_rec["recording_id"])
    t = threading.Thread(target=worker.run_once)
    t.start()
    wait_for(lambda: len(artifact_rows(engine, running["id"])) >= 2)
    r = client.post(f"/v1/runs/{running['id']}/cancel", headers=h)
    assert r.status_code == 202
    assert r.json()["state"] == "running" and r.json()["cancel_requested"] is True
    # an in-process step is not interruptible: the worker stops at the next step boundary
    hold.unlink()
    wait_for(lambda: _get(client, h, running["id"])["state"] == "cancelled", timeout_s=20)
    t.join(timeout=30)
    out = _get(client, h, running["id"])
    assert out["artifacts"] == []  # a cancelled run publishes nothing
    assert job_row(engine, running["id"])["state"] == "cancelled"


def test_tenant_isolation_on_runs(client, as_role, synth_rec, tenants, worker, engine):
    h_a, h_b = as_role("scientist"), as_role("owner", tenant=tenants.b)
    ref = publish(client, h_a, quick_doc())
    run = start_run(client, h_a, ref, synth_rec["recording_id"])
    assert client.get(f"/v1/runs/{run['id']}", headers=h_b).status_code == 404
    assert client.post(f"/v1/runs/{run['id']}/cancel", headers=h_b).status_code == 404
    # B cannot run A's pipeline (per-tenant) nor on A's recording (even with its own pipeline)
    body = {"pipeline": ref, "recording_id": synth_rec["recording_id"]}
    assert client.post("/v1/runs", json=body, headers=h_b).status_code == 404
    publish(client, h_b, quick_doc())
    assert client.post("/v1/runs", json=body, headers=h_b).status_code == 404
    # RLS: B's DB role sees none of A's queue/run rows
    with engine.begin() as c:
        c.execute(text("SET LOCAL ROLE nf_app"))
        c.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": tenants.b})
        for t in ("job", "run", "run_artifact"):
            assert c.execute(text(f"SELECT count(*) FROM {t}")).scalar_one() == 0, t
    # the worker runs A's job in A's tenant only
    worker.run_once()
    assert _get(client, h_a, run["id"])["state"] == "succeeded"


def test_quarantined_recording_cannot_be_run(client, as_role, synth_rec, engine):
    h = as_role("owner")
    ref = publish(client, h, quick_doc())
    with engine.begin() as c:
        c.execute(
            text("UPDATE recording SET state = 'quarantined' WHERE id = :i"),
            {"i": synth_rec["recording_id"]},
        )
    body = {"pipeline": ref, "recording_id": synth_rec["recording_id"]}
    r = client.post("/v1/runs", json=body, headers=h)
    assert r.status_code == 409 and r.json()["type"].endswith("quarantined")


def test_non_explicit_parameters_are_refused_by_the_worker(
    client, as_role, synth_rec, worker, engine
):
    h = as_role("scientist")
    doc = quick_doc("implicit")
    doc["steps"][0]["params"] = {"l_freq": 1.0, "h_freq": 40.0}  # defaults left out
    run = start_run(client, h, publish(client, h, doc), synth_rec["recording_id"])
    worker.run_once()
    out = _get(client, h, run["id"])
    assert out["state"] == "failed" and "not fully explicit" in out["error"]
    assert job_row(engine, run["id"])["attempts"] == 1  # not retried: same result every time


def test_step_error_is_not_retried_and_publishes_nothing(
    client, as_role, synth_rec, worker, engine
):
    h = as_role("scientist")
    doc = pipeline_doc(
        "broken", [step("bandpass", "nf_steps.filter@1"), step("x", f"{TEST_LIBRARY}.fail@1")]
    )
    run = start_run(client, h, publish(client, h, doc), synth_rec["recording_id"])
    worker.run_once()
    out = _get(client, h, run["id"])
    assert out["state"] == "failed" and "deliberate step error" in out["error"]
    assert out["artifacts"] == []
    assert all(a["visible_at"] is None for a in artifact_rows(engine, run["id"]))


def test_upload_conversion_runs_on_the_queue(
    client, as_role, tree, worker, engine, tenants, storage
):
    """M2's process_pending is replaced by a queued ``ingest.upload`` job per completed upload."""
    h = as_role("scientist")
    r = client.post(f"/v1/runs/{tree['run_id']}/cancel", headers=as_role("owner"))
    assert r.json()["state"] == "cancelled"  # the tree fixture's run: not this test's job
    data, truth = generate(SynthParams(seed=2))
    path = worker.workdir / "rec.edf"
    write_edf(path, data, truth)
    body = path.read_bytes()
    r = client.post(
        f"/v1/datasets/{tree['dataset_id']}/uploads",
        json={
            "session_id": tree["session_id"],
            "filename": "rec.edf",
            "size_bytes": len(body),
            "synthetic": True,
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    up = r.json()
    part = up["part_size"]
    for i in range(0, len(body), part):
        rr = client.put(
            f"/v1/uploads/{up['id']}/parts/{i // part + 1}", content=body[i : i + part], headers=h
        )
        assert rr.status_code == 200, rr.text
    sha = hashlib.sha256(body).hexdigest()
    for _ in range(2):  # a repeated complete call does not queue a second job
        rr = client.post(f"/v1/uploads/{up['id']}/complete", json={"sha256": sha}, headers=h)
        assert rr.status_code == 202, rr.text
    with engine.connect() as c:
        jobs = c.execute(
            text(
                "SELECT id, state FROM job WHERE kind = 'ingest.upload' "
                "AND payload->>'upload_id' = :u"
            ),
            {"u": up["id"]},
        ).all()
    assert len(jobs) == 1 and jobs[0].state == "queued"
    assert worker.run_once() is not None
    st = client.get(f"/v1/uploads/{up['id']}", headers=h).json()
    assert st["state"] == "done", st
    with engine.connect() as c:
        j = c.execute(
            text("SELECT state, result FROM job WHERE id = :i"), {"i": jobs[0].id}
        ).first()
    assert j.state == "succeeded" and len(j.result["recording_ids"]) == 1
