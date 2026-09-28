"""Helpers for the 3.3 tests (uniquely named module so it never collides with another test
directory's ``conftest``)."""

from __future__ import annotations

import time
import uuid
from typing import Any

from nf_platform.ingest import recording_store as rs
from nf_platform.signals.zarr_store import write_recording
from nf_steps import get_step
from nf_steps.pipelines import ENTRYPOINT, PLACEHOLDER_IMAGE
from nf_synth.generate import SynthParams, generate
from sqlalchemy import text

TEST_LIBRARY = "nf_jobs_teststeps"


def make_synth_recording(client, h, tree, storage, engine, tenant_id: str, seed: int = 1):
    data, truth = generate(SynthParams(seed=seed))
    names = list(truth["channels"])
    chans = [
        {"name": n, "modality": "EEG", "sampling_rate": float(truth["sfreq"]), "units": "uV"}
        for n in names
    ]
    r = client.post(
        f"/v1/sessions/{tree['session_id']}/recordings",
        json={"label": f"synth-{seed}", "channels": chans},
        headers=h,
    )
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    prefix = rs.stream_prefix(tenant_id, tree["subject_id"], rid)
    store = rs.open_store(storage, tenant_id, tree["subject_id"], prefix)
    events = [
        {"onset_s": e["onset_s"], "duration_s": 0.0, "label": e["label"], "kind": "marker"}
        for e in truth["events"]
    ]
    write_recording(
        store, "signal", data, float(truth["sfreq"]), names, "uV", meta={"events": events}
    )
    with engine.begin() as c:
        c.execute(
            text("UPDATE recording SET zarr_ref = :z WHERE id = :i"),
            {"z": rs.make_ref(prefix, "signal"), "i": rid},
        )
    return {"recording_id": rid, "data": data, "truth": truth}


def step(name: str, ref: str, params: dict[str, Any] | None = None, tolerance=None):
    st = get_step(ref, (TEST_LIBRARY,))
    return {
        "name": name,
        "step": ref,
        "image": PLACEHOLDER_IMAGE,
        "entrypoint": list(ENTRYPOINT),
        "params": st.resolve(params or {}),
        "tolerance": tolerance or st.tolerance_doc(),
    }


def pipeline_doc(name: str, steps: list[dict[str, Any]], *, seed: int = 1, version="1.0.0"):
    return {
        "schema": "nf.pipeline-version/v1",
        "meta": {"name": name, "version": version},
        "steps": steps,
        "seed": seed,
    }


QUICK_STEPS = [
    ("bandpass", "nf_steps.filter@1", {"l_freq": 1.0, "h_freq": 40.0}),
    ("bads", "nf_steps.bad_channels@1", {}),
    ("bandpower", "nf_steps.band_power@1", {"n_per_seg": 256, "n_overlap": 128}),
]


def quick_doc(name: str = "quick", **kw) -> dict[str, Any]:
    return pipeline_doc(name, [step(n, r, p) for n, r, p in QUICK_STEPS], **kw)


def publish(client, h, doc) -> str:
    r = client.post("/v1/pipelines", json=doc, headers=h)
    assert r.status_code in (200, 201), r.text
    return r.json()["ref"]


def start_run(client, h, ref: str, recording_id: str) -> dict[str, Any]:
    r = client.post("/v1/runs", json={"pipeline": ref, "recording_id": recording_id}, headers=h)
    assert r.status_code == 202, r.text
    return r.json()


def job_row(engine, run_id: str) -> dict[str, Any]:
    with engine.connect() as c:
        row = c.execute(
            text("SELECT j.* FROM job j JOIN run r ON r.job_id = j.id WHERE r.id = :r"),
            {"r": run_id},
        ).first()
    return dict(row._mapping)


def artifact_rows(engine, run_id: str) -> list[dict[str, Any]]:
    with engine.connect() as c:
        rows = c.execute(
            text("SELECT * FROM run_artifact WHERE run_id = :r ORDER BY step, name"),
            {"r": run_id},
        ).all()
    return [dict(r._mapping) for r in rows]


def make_due(engine, run_id: str) -> None:
    """Skip the retry backoff (tests only)."""
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE job SET run_after = now() - interval '1 second' "
                "WHERE id = (SELECT job_id FROM run WHERE id = :r)"
            ),
            {"r": run_id},
        )


def wait_for(pred, timeout_s: float = 60.0, every_s: float = 0.1):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        v = pred()
        if v:
            return v
        time.sleep(every_s)
    raise AssertionError("condition not reached in time")


def uid() -> str:
    return str(uuid.uuid4())
