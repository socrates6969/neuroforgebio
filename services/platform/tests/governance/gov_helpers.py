"""Helpers for the m5-ledger tests (uniquely named so it never collides with another directory's
helpers)."""

from __future__ import annotations

import uuid
from typing import Any

import numpy as np
from nf_platform.db.context import Principal
from nf_platform.ingest import recording_store as rs
from nf_platform.signals.zarr_store import write_recording
from nf_steps import get_step
from nf_steps.pipelines import ENTRYPOINT, PLACEHOLDER_IMAGE
from sqlalchemy import text

TEST_LIBRARY = "nf_gov_teststeps"
ALL_SCOPES = ("collection", "processing", "sharing", "model_training", "commercial_use")
EEG = {"name": "Cz", "modality": "EEG", "sampling_rate": 256.0, "units": "uV"}
EMG = {"name": "EMG1", "modality": "EMG", "sampling_rate": 256.0, "units": "uV"}


def principal(tenant_id: str, *roles: str, pid: str | None = None) -> Principal:
    return Principal(
        id=pid or f"user-{'-'.join(roles) or 'none'}",
        tenant_id=str(tenant_id),
        roles=frozenset(roles),
        scopes=frozenset(),
        kind="user",
        mfa_phr=True,
    )


def post(client, path: str, body: dict[str, Any], h, status: int = 201) -> dict[str, Any]:
    r = client.post(path, json=body, headers=h)
    assert r.status_code == status, (path, r.status_code, r.text)
    return r.json()


def consent_doc(client, h) -> str:
    r = client.post(
        "/v1/consent-documents",
        json={"name": "gov-consent", "version": "1", "sha256": "ef" * 32},
        headers=h,
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def make_subject(client, h, dataset_id: str, label: str, scopes=ALL_SCOPES) -> dict[str, str]:
    sid = post(client, f"/v1/datasets/{dataset_id}/subjects", {"label": label}, h)["id"]
    if scopes:
        doc = consent_doc(client, h)
        post(
            client,
            f"/v1/subjects/{sid}/consents",
            {"kind": "grant", "scopes": list(scopes), "document_id": doc},
            h,
        )
    ses = post(client, f"/v1/subjects/{sid}/sessions", {"label": "ses-1"}, h)["id"]
    return {"subject_id": sid, "session_id": ses}


def make_recording(
    client,
    h,
    session_id: str,
    *,
    storage,
    engine,
    tenant_id: str,
    subject_id: str,
    channels=(EEG, EMG),
    data: np.ndarray | None = None,
    label: str | None = None,
) -> str:
    rid = post(
        client,
        f"/v1/sessions/{session_id}/recordings",
        {"label": label or f"r-{uuid.uuid4().hex[:6]}", "channels": list(channels)},
        h,
    )["id"]
    if data is not None:
        prefix = rs.stream_prefix(tenant_id, subject_id, rid)
        store = rs.open_store(storage, tenant_id, subject_id, prefix)
        names = [c["name"] for c in channels]
        write_recording(store, "signal", data, 256.0, names, ["uV"] * len(names))
        with engine.begin() as c:
            c.execute(
                text("UPDATE recording SET zarr_ref = :z WHERE id = :i"),
                {"z": rs.make_ref(prefix, "signal"), "i": rid},
            )
    return rid


def signal(seed: int, n_ch: int = 2, n: int = 512) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(-500, 500, size=(n_ch, n), dtype=np.int16)


def pass_pipeline(name: str = "gov-pass") -> dict[str, Any]:
    st = get_step(f"{TEST_LIBRARY}.passthrough@1", (TEST_LIBRARY,))
    return {
        "schema": "nf.pipeline-version/v1",
        "meta": {"name": name, "version": "1.0.0"},
        "steps": [
            {
                "name": "copy",
                "step": f"{TEST_LIBRARY}.passthrough@1",
                "image": PLACEHOLDER_IMAGE,
                "entrypoint": list(ENTRYPOINT),
                "params": st.resolve({}),
                "tolerance": st.tolerance_doc(),
            }
        ],
        "seed": 7,
    }


def publish(client, h, doc) -> str:
    r = client.post("/v1/pipelines", json=doc, headers=h)
    assert r.status_code in (200, 201), r.text
    return r.json()["ref"]


def audit_rows(engine, **where) -> list[dict[str, Any]]:
    sql = "SELECT row_to_json(e) FROM audit_event e"
    if where:
        sql += " WHERE " + " AND ".join(f"{k} = :{k}" for k in where)
    with engine.connect() as c:
        return [r[0] for r in c.execute(text(sql + " ORDER BY seq"), where)]
