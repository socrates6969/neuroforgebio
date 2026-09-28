"""2.6 upload sessions: pre-signed multipart (local shim), resumable, server-side SHA-256 check,
size limits, SEC-071 synthetic-only guard, quarantine, and the worker that converts the raw
original with m2-data's converters into encrypted Zarr + provenance + channel defaults."""

from __future__ import annotations

import dataclasses
import hashlib
import io
import zipfile
from pathlib import Path

import numpy as np
import pytest
from nf_platform.db import models as m
from nf_platform.db.context import tenant_session
from nf_platform.ingest import recording_store as rs
from nf_platform.ingest.policy import (
    AllowAllPolicy,
    Quarantined,
    StubConsentPolicy,
    assert_processable,
    initial_state,
)
from nf_platform.ingest.uploads import worker
from nf_platform.ingest.uploads.backends import part_key
from nf_platform.storage.runtime import service_principal
from nf_synth.generate import SynthParams, generate
from nf_synth.writers import write_edf
from sqlalchemy import select, text

pytestmark = pytest.mark.postgres
PART = 8 * 1024


@pytest.fixture(scope="module")
def edf_bytes(tmp_path_factory) -> bytes:
    data, truth = generate(SynthParams(seed=11, n_channels=4, sfreq=256, duration_s=14))
    p = write_edf(tmp_path_factory.mktemp("edf") / "sub-01_task-rest.edf", data, truth)
    return Path(p).read_bytes()


def _create(client, h, tree, blob: bytes, filename="rec.edf", **kw):
    body = {
        "session_id": tree["session_id"],
        "filename": filename,
        "size_bytes": len(blob),
        "part_size": PART,
        "synthetic": True,
        **kw,
    }
    return client.post(f"/v1/datasets/{tree['dataset_id']}/uploads", json=body, headers=h)


def _parts(blob: bytes, size: int = PART) -> list[bytes]:
    return [blob[i : i + size] for i in range(0, len(blob), size)]


def _put(client, h, uid, n, data):
    return client.put(f"/v1/uploads/{uid}/parts/{n}", content=data, headers=h)


def _upload(client, h, tree, blob, filename="rec.edf") -> str:
    r = _create(client, h, tree, blob, filename)
    assert r.status_code == 201, r.text
    uid = r.json()["id"]
    for n, part in enumerate(_parts(blob), start=1):
        assert _put(client, h, uid, n, part).status_code == 200
    r = client.post(
        f"/v1/uploads/{uid}/complete",
        json={"sha256": hashlib.sha256(blob).hexdigest()},
        headers=h,
    )
    assert r.status_code == 202, r.text
    assert r.json()["state"] == "uploaded"
    return uid


# ---------------------------------------------------------------- sessions, parts, hashes
def test_create_returns_presigned_part_targets(client, as_role, tree, edf_bytes):
    r = _create(client, as_role("scientist"), tree, edf_bytes)
    assert r.status_code == 201, r.text
    up = r.json()
    n = len(_parts(edf_bytes))
    assert up["state"] == "open" and up["n_parts"] == n and up["part_size"] == PART
    assert [p["part_number"] for p in up["parts"]] == list(range(1, n + 1))
    assert up["parts"][0]["url"] == f"/v1/uploads/{up['id']}/parts/1"
    assert up["parts"][0]["method"] == "PUT" and up["parts"][0]["auth"] == "bearer"


def test_hash_mismatch_rejects_the_upload(client, as_role, tree, edf_bytes, audit_events, storage):
    h = as_role("scientist")
    uid = _create(client, h, tree, edf_bytes).json()["id"]
    for n, part in enumerate(_parts(edf_bytes), start=1):
        assert _put(client, h, uid, n, part).status_code == 200
    wrong = hashlib.sha256(edf_bytes + b"x").hexdigest()
    r = client.post(f"/v1/uploads/{uid}/complete", json={"sha256": wrong}, headers=h)
    assert r.status_code == 422, r.text
    assert r.json()["type"].endswith("hash-mismatch")
    assert r.json()["server_sha256"] == hashlib.sha256(edf_bytes).hexdigest()
    st = client.get(f"/v1/uploads/{uid}", headers=h).json()
    assert st["state"] == "rejected" and st["received_parts"] == [] and st["parts"] == []
    assert not list(storage.objects.list("raw", st["id"]))  # parts deleted
    fails = [
        e for e in audit_events(request_id=r.headers["x-request-id"]) if e["outcome"] == "failure"
    ]
    assert fails and fails[0]["details"]["reason"] == "sha256 mismatch"
    # rejected is final: no more parts, no second completion
    assert _put(client, h, uid, 1, _parts(edf_bytes)[0]).status_code == 409
    right = hashlib.sha256(edf_bytes).hexdigest()
    assert (
        client.post(f"/v1/uploads/{uid}/complete", json={"sha256": right}, headers=h).status_code
        == 409
    )


def test_resumed_multipart_upload(client, as_role, tree, edf_bytes):
    """Parts arrive out of order, one is missing at the first completion attempt, one is re-sent;
    the client resumes from the status (received parts + hashes, remaining targets)."""
    h = as_role("scientist")
    parts = _parts(edf_bytes)
    assert len(parts) >= 3
    uid = _create(client, h, tree, edf_bytes).json()["id"]
    assert _put(client, h, uid, 3, parts[2]).status_code == 200
    assert _put(client, h, uid, 1, parts[0]).status_code == 200
    sha = hashlib.sha256(edf_bytes).hexdigest()
    r = client.post(f"/v1/uploads/{uid}/complete", json={"sha256": sha}, headers=h)
    assert r.status_code == 409 and 2 in r.json()["missing_parts"]
    # "client restart": ask the server what it has
    st = client.get(f"/v1/uploads/{uid}", headers=h).json()
    have = {p["part_number"]: p["sha256"] for p in st["received_parts"]}
    assert have == {
        1: hashlib.sha256(parts[0]).hexdigest(),
        3: hashlib.sha256(parts[2]).hexdigest(),
    }
    todo = [p["part_number"] for p in st["parts"]]
    assert 1 not in todo and 3 not in todo and 2 in todo
    for n in todo:
        assert _put(client, h, uid, n, parts[n - 1]).status_code == 200
    assert _put(client, h, uid, 1, parts[0]).status_code == 200  # re-sent part: idempotent
    r = client.post(f"/v1/uploads/{uid}/complete", json={"sha256": sha}, headers=h)
    assert r.status_code == 202 and r.json()["server_sha256"] == sha
    # a retried completion is idempotent; parts are now immutable (SEC-042)
    r2 = client.post(f"/v1/uploads/{uid}/complete", json={"sha256": sha}, headers=h)
    assert r2.status_code == 202
    assert _put(client, h, uid, 1, parts[0]).status_code == 409


def test_part_and_upload_size_limits(app, client, as_role, tree, edf_bytes):
    h = as_role("scientist")
    uid = _create(client, h, tree, edf_bytes).json()["id"]
    assert _put(client, h, uid, 1, b"short").status_code == 422  # must be exactly part_size
    assert _put(client, h, uid, 99, b"x" * PART).status_code == 422  # beyond n_parts
    app.state.settings = dataclasses.replace(
        app.state.settings, upload_max_bytes=len(edf_bytes) - 1, upload_part_max=PART
    )
    r = _create(client, h, tree, edf_bytes)
    assert r.status_code == 413 and r.json()["max_bytes"] == len(edf_bytes) - 1
    r = _put(client, h, uid, 1, b"x" * (PART + 1))
    assert r.status_code == 413


@pytest.mark.parametrize(
    ("kw", "status"),
    [
        ({"filename": "../../etc/passwd.edf"}, 422),
        ({"filename": "rec.exe"}, 422),
        ({"filename": "C:rec.edf"}, 422),
        ({"size_bytes": 0}, 422),
        ({"part_size": 1}, 422),  # below the minimum part size
    ],
)
def test_create_validation(client, as_role, tree, kw, status):
    body = {
        "session_id": tree["session_id"],
        "filename": "rec.edf",
        "size_bytes": 100,
        "synthetic": True,
        **kw,
    }
    r = client.post(
        f"/v1/datasets/{tree['dataset_id']}/uploads", json=body, headers=as_role("scientist")
    )
    assert r.status_code == status, r.text


def test_session_must_belong_to_the_dataset(client, as_role, tree):
    h = as_role("owner")
    other = client.post(
        f"/v1/projects/{tree['project_id']}/datasets", json={"name": "d2"}, headers=h
    )
    r = client.post(
        f"/v1/datasets/{other.json()['id']}/uploads",
        json={
            "session_id": tree["session_id"],
            "filename": "a.edf",
            "size_bytes": 5,
            "synthetic": True,
        },
        headers=h,
    )
    assert r.status_code == 404


def test_sec071_synthetic_only(app, client, as_role, tree, engine, tenants, edf_bytes):
    h = as_role("scientist")
    r = _create(client, h, tree, edf_bytes, synthetic=False)
    assert r.status_code == 403 and r.json()["type"].endswith("synthetic-only")
    # prod + a tenant flagged synthetic_only (the default) still refuses
    app.state.settings = dataclasses.replace(app.state.settings, environment="prod")
    assert _create(client, h, tree, edf_bytes, synthetic=False).status_code == 403
    with engine.begin() as c:
        c.execute(text("UPDATE tenant SET synthetic_only = false WHERE id = :t"), {"t": tenants.a})
    assert _create(client, h, tree, edf_bytes, synthetic=False).status_code == 201


def test_uploads_are_private_to_their_creator(client, as_role, tree, edf_bytes):
    a = as_role("scientist", sub="sci-a")
    b = as_role("scientist", sub="sci-b")
    uid = _create(client, a, tree, edf_bytes).json()["id"]
    assert client.get(f"/v1/uploads/{uid}", headers=b).status_code == 404
    assert _put(client, b, uid, 1, _parts(edf_bytes)[0]).status_code == 404
    # the data steward may inspect it (not write)
    steward = as_role("data-steward")
    assert client.get(f"/v1/uploads/{uid}", headers=steward).status_code == 200
    assert _put(client, steward, uid, 1, _parts(edf_bytes)[0]).status_code == 404


def test_raw_parts_are_sealed_under_the_subject_dek(
    client, as_role, tree, edf_bytes, storage, engine
):
    h = as_role("scientist")
    uid = _upload(client, h, tree, edf_bytes)
    with engine.connect() as c:
        prefix = c.execute(text("SELECT raw_prefix FROM upload WHERE id = :u"), {"u": uid}).scalar()
        objs = c.execute(
            text(
                "SELECT object_key, sha256, size_bytes FROM stored_object WHERE object_key LIKE :p"
            ),
            {"p": prefix + "/%"},
        ).all()
    blob = storage.objects.get("raw", part_key(prefix, 1))
    assert blob[:4] == b"NFE1" and _parts(edf_bytes)[0][:64] not in blob
    names = sorted(o.object_key.rsplit("/", 1)[-1] for o in objs)
    assert names[-1] == f"part-{len(_parts(edf_bytes)):05d}" and "manifest.json" in names


# ---------------------------------------------------------------- worker: convert + quarantine
def test_worker_converts_writes_provenance_and_quarantines(
    client, as_role, tree, edf_bytes, storage, engine, tenants, audit_events
):
    h = as_role("scientist")
    uid = _upload(client, h, tree, edf_bytes)
    ids = worker.process_upload(storage, tenants.a, uid, engine=engine)
    assert len(ids) == 1
    rid = ids[0]
    st = client.get(f"/v1/uploads/{uid}", headers=h).json()
    assert st["state"] == "done" and st["recording_ids"] == ids
    # M2 consent stub: quarantined → scientist 403 everywhere, data-steward sees and reads it
    assert client.get(f"/v1/recordings/{rid}", headers=h).status_code == 403
    assert client.get(f"/v1/recordings/{rid}/data?start=0&end=1", headers=h).status_code == 403
    steward = as_role("data-steward")
    rec = client.get(f"/v1/recordings/{rid}", headers=steward)
    assert rec.status_code == 200 and rec.json()["state"] == "quarantined"
    r = client.get(f"/v1/recordings/{rid}/data?start=0&end=2&format=binary", headers=steward)
    assert r.status_code == 200
    header, data = rs.decode_binary(r.content)
    assert header["shape"] == [4, 512] and header["sfreq"] == 256.0
    # the window is the EDF's digital samples, bit-exact
    from nf_platform.ingest.convert import read_source

    tmp = Path(storage.objects.root) / "check.edf"  # type: ignore[attr-defined]
    tmp.write_bytes(edf_bytes)
    src = read_source(tmp, "edf")[0]
    np.testing.assert_array_equal(data, src.data[:, :512])
    with tenant_session(service_principal(tenants.a), engine=engine) as s:
        chans = s.scalars(select(m.Channel).where(m.Channel.recording_id == rid)).all()
        assert len(chans) == 4
        assert all(c.modality == "EEG" and c.nervous_system == "central" for c in chans)
        prov = s.scalars(select(m.ProvenanceRecord)).all()
        assert len(prov) == 1
        p = prov[0].payload
        assert (
            p["entity_in"]["upload"]["blob_id"]
            == "blob:sha256:" + hashlib.sha256(edf_bytes).hexdigest()
        )
        assert p["entity_in"]["sha256"] == hashlib.sha256(edf_bytes).hexdigest()
        assert p["activity"]["type"] == "convert" and p["converter_version"]
        assert p["entities_out"][0]["id"] == rid
        seg = s.scalars(select(m.Segment).where(m.Segment.recording_id == rid)).one()
        assert seg.end_s == pytest.approx(14.0)
    evs = [e for e in audit_events(type_="data.create") if e["resource_id"] == uid]
    assert any(e["actor_id"] == worker.WORKER_ID and e["outcome"] == "success" for e in evs)
    # processing is idempotent: a second run does nothing
    assert worker.process_upload(storage, tenants.a, uid, engine=engine) == []


def test_worker_allow_policy_makes_recordings_active(
    client, as_role, tree, edf_bytes, storage, engine, tenants
):
    h = as_role("scientist")
    uid = _upload(client, h, tree, edf_bytes)
    (rid,) = worker.process_upload(storage, tenants.a, uid, engine=engine, policy=AllowAllPolicy())
    assert client.get(f"/v1/recordings/{rid}/data?start=0&end=1", headers=h).status_code == 200


def test_worker_zip_bundle_and_corrupt_input(
    client, as_role, tree, edf_bytes, storage, engine, tenants
):
    h = as_role("scientist")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bundle/a.edf", edf_bytes)
        zf.writestr("bundle/README.txt", "synthetic")
    uid = _upload(client, h, tree, buf.getvalue(), filename="bundle.zip")
    res = worker.process_pending(storage, tenants.a, engine=engine)
    assert len(res[uid]) == 1, client.get(f"/v1/uploads/{uid}", headers=h).json()["error"]
    # a corrupt EDF fails cleanly: upload 'failed', no recording, the raw original is kept
    bad = b"0       " + b"\x00" * 300
    uid2 = _upload(client, h, tree, bad, filename="bad.edf")
    assert worker.process_upload(storage, tenants.a, uid2, engine=engine) == []
    st = client.get(f"/v1/uploads/{uid2}", headers=h).json()
    assert st["state"] == "failed" and st["error"]
    # zip traversal is refused by the worker (SEC-064)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../escape.edf", edf_bytes)
    uid3 = _upload(client, h, tree, buf.getvalue(), filename="evil.zip")
    assert worker.process_upload(storage, tenants.a, uid3, engine=engine) == []
    st = client.get(f"/v1/uploads/{uid3}", headers=h).json()
    assert st["state"] == "failed" and "traversal" in st["error"]


def test_policy_hook_fails_closed():
    class Weird:
        def decide(self, *a):
            return "maybe"

    assert initial_state(StubConsentPolicy(), "t", "s", "r") == "quarantined"
    assert initial_state(AllowAllPolicy(), "t", "s", "r") == "active"
    assert initial_state(Weird(), "t", "s", "r") == "quarantined"
    assert_processable("active")
    with pytest.raises(Quarantined):
        assert_processable("quarantined")
