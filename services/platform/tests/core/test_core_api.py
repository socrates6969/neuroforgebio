"""API basics: health, whoami, metadata read/create, problem+json errors."""

from __future__ import annotations

import uuid

from conftest import bearer


def test_health_is_public(client):
    r = client.get("/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_whoami(client, as_role, tenants):
    r = client.get("/v1/whoami", headers=as_role("scientist"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["tenant_id"] == tenants.a
    assert body["roles"] == ["scientist"]
    assert body["kind"] == "user"


def test_tree_roundtrip(client, as_role, tree):
    h = as_role("viewer")
    r = client.get(f"/v1/recordings/{tree['recording_id']}", headers=h)
    assert r.status_code == 200, r.text
    rec = r.json()
    assert [c["name"] for c in rec["channels"]] == ["Cz", "EMG1"]
    cz, emg = rec["channels"]
    assert (cz["modality"], cz["nervous_system"], cz["derived_from_non_neural"]) == (
        "EEG",
        "central",
        False,
    )
    assert emg["nervous_system"] == "peripheral"  # m5-ledger 5.1: the EMG modality default
    assert emg["sampling_rate"] == 1000.0
    for path, key in (
        ("/v1/projects", "project_id"),
        (f"/v1/projects/{tree['project_id']}/datasets", "dataset_id"),
        (f"/v1/datasets/{tree['dataset_id']}/subjects", "subject_id"),
        (f"/v1/subjects/{tree['subject_id']}/sessions", "session_id"),
        (f"/v1/sessions/{tree['session_id']}/recordings", "recording_id"),
    ):
        r = client.get(path, headers=h)
        assert r.status_code == 200, (path, r.text)
        assert [x["id"] for x in r.json()] == [tree[key]]


def test_problem_json_404(client, as_role):
    r = client.get(f"/v1/projects/{uuid.uuid4()}", headers=as_role("viewer"))
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert body["status"] == 404 and body["title"] == "Not Found" and "type" in body


def test_problem_json_401_has_www_authenticate(client):
    r = client.get("/v1/projects")
    assert r.status_code == 401
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.headers["www-authenticate"].startswith("Bearer")


def test_problem_json_422_does_not_echo_input(client, as_role, tree):
    secretish = "nfb_live_should_not_echo"
    r = client.post(
        f"/v1/sessions/{tree['session_id']}/recordings",
        json={"label": "x", "channels": [{"name": secretish, "modality": "PSYCHIC"}]},
        headers=as_role("scientist"),
    )
    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/problem+json")
    assert secretish not in r.text


def test_unknown_modality_rejected(client, as_role, tree):
    r = client.post(
        f"/v1/sessions/{tree['session_id']}/recordings",
        json={
            "label": "x",
            "channels": [{"name": "a", "modality": "XYZ", "sampling_rate": 1, "units": "V"}],
        },
        headers=as_role("scientist"),
    )
    assert r.status_code == 422


def test_duplicate_subject_label_is_409(client, as_role, tree):
    h = as_role("scientist")
    r = client.post(
        f"/v1/datasets/{tree['dataset_id']}/subjects", json={"label": "sub-01"}, headers=h
    )
    assert r.status_code == 409
    assert r.headers["content-type"].startswith("application/problem+json")


def test_create_under_missing_parent_is_404(client, as_role):
    r = client.post(
        f"/v1/projects/{uuid.uuid4()}/datasets", json={"name": "d"}, headers=as_role("owner")
    )
    assert r.status_code == 404


def test_malformed_bearer_is_401(client):
    for h in ({"Authorization": "Basic abc"}, bearer("not-a-jwt"), bearer("nfb_live_x")):
        assert client.get("/v1/whoami", headers=h).status_code == 401
