"""Helpers for the 3.6 sweep tests (uniquely named module so it never collides with another test
directory's helpers)."""

from __future__ import annotations

from typing import Any

from nf_platform.ingest import recording_store as rs
from nf_platform.signals.zarr_store import write_recording
from nf_steps import get_step
from nf_steps.pipelines import ENTRYPOINT, PLACEHOLDER_IMAGE
from sqlalchemy import text
from sweeps_planted import Planted, generate

# Epoch = exactly the 1 s burst window after each event (128 samples at 128 Hz).
EPOCH_TMAX = 127 / 128
BANDS = [["theta", 4.0, 8.0], ["alpha", 8.0, 13.0], ["beta", 13.0, 30.0]]

PLANTED_STEPS: list[tuple[str, str, dict[str, Any]]] = [
    ("notch", "nf_steps.notch@1", {"freqs": [50.0]}),
    ("filter", "nf_steps.filter@1", {"l_freq": 1.0, "h_freq": 40.0}),
    (
        "epochs",
        "nf_steps.epochs@1",
        {"event_codes": [1, 2], "tmin": 0.0, "tmax": EPOCH_TMAX, "baseline": None},
    ),
    (
        "bandpower",
        "nf_steps.band_power@1",
        {"bands": BANDS, "n_fft": 128, "n_per_seg": 128, "n_overlap": 0},
    ),
    ("decode", "nf_steps.decode_lda@1", {}),
]


def step(name: str, ref: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    st = get_step(ref)
    return {
        "name": name,
        "step": ref,
        "image": PLACEHOLDER_IMAGE,
        "entrypoint": list(ENTRYPOINT),
        "params": st.resolve(params or {}),
        "tolerance": st.tolerance_doc(),
    }


def planted_pipeline(name: str = "planted-decode", version: str = "1.0.0") -> dict[str, Any]:
    return {
        "schema": "nf.pipeline-version/v1",
        "meta": {"name": name, "version": version},
        "steps": [step(n, r, p) for n, r, p in PLANTED_STEPS],
        "seed": 1,
    }


def publish(client, h, doc) -> str:
    r = client.post("/v1/pipelines", json=doc, headers=h)
    assert r.status_code in (200, 201), r.text
    return r.json()["ref"]


def make_planted_recording(
    client, h, tree, storage, engine, tenant_id: str, p: Planted | None = None
) -> dict[str, Any]:
    p = p or Planted()
    data, truth = generate(p)
    chans = [
        {"name": n, "modality": "EEG", "sampling_rate": float(p.sfreq), "units": "uV"}
        for n in truth["channels"]
    ]
    r = client.post(
        f"/v1/sessions/{tree['session_id']}/recordings",
        json={"label": f"planted-{p.seed}", "channels": chans},
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
        store, "signal", data, float(p.sfreq), truth["channels"], "uV", meta={"events": events}
    )
    with engine.begin() as c:
        c.execute(
            text("UPDATE recording SET zarr_ref = :z WHERE id = :i"),
            {"z": rs.make_ref(prefix, "signal"), "i": rid},
        )
    return {"recording_id": rid, "data": data, "truth": truth, "planted": p}


def drain(worker, limit: int = 100) -> int:
    """Run queued jobs until none is due; returns how many ran."""
    n = 0
    while n < limit and worker.run_once() is not None:
        n += 1
    return n


def sweep_body(ref: str, recording_ids: list[str], grid: dict[str, list[Any]], **kw) -> dict:
    return {
        "pipeline": ref,
        "recording_ids": recording_ids,
        "grid": grid,
        "metric": {"step": "decode", "key": "accuracy"},
        **kw,
    }
