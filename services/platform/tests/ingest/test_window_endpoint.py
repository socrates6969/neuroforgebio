"""2.4 endpoint ``GET /v1/recordings/{id}/data``: authorize() + tenant session + audit, decrypts
through the Keyring, documented response format, window-size limits, quarantine (2.6), BOLA."""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest
from conftest import TREE_SIGNAL
from nf_platform.ingest import recording_store as rs
from nf_platform.ingest.stream.protocol import chunk_id_bytes, samples_to_bytes
from sqlalchemy import text

pytestmark = pytest.mark.postgres
SFREQ = 256.0  # the tree fixture's signal: 2 ch x 4096 samples, int16, units uV


def _url(tree, **q):
    qs = "&".join(f"{k}={v}" for k, v in {"start": 0, "end": 1, **q}.items())
    return f"/v1/recordings/{tree['recording_id']}/data?{qs}"


def test_json_window_equals_source_exactly(client, as_role, tree):
    r = client.get(_url(tree, start=0.5, end=1.25), headers=as_role("scientist"))
    assert r.status_code == 200, r.text
    body = r.json()
    i0, i1 = int(0.5 * SFREQ), int(1.25 * SFREQ)
    assert body["shape"] == [2, i1 - i0]
    assert body["channels"] == ["Cz", "EMG1"]
    assert body["dtype"] == "int16" and body["kind"] == "samples" and body["level"] == 0
    assert body["start_index"] == i0 and body["start_s"] == pytest.approx(0.5)
    assert body["units"] == ["uV", "uV"] and body["scale"] == [1.0, 1.0]
    assert body["order"] == "C" and body["byte_order"] == "little"
    got = np.asarray(body["data"], dtype=np.int16)
    np.testing.assert_array_equal(got, TREE_SIGNAL[:, i0:i1])
    # the chunk id lets a client verify what it got (hashing spec v1 §5.2)
    cid = chunk_id_bytes("int16", [2, i1 - i0], samples_to_bytes(got, "int16"))
    assert body["chunk_id"] == cid == r.headers["x-nf-chunk-id"]


def test_binary_window_channel_subset_and_pyramid(client, as_role, tree):
    h = as_role("viewer")
    r = client.get(_url(tree, channels="EMG1", format="binary"), headers=h)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith(rs.WINDOW_MEDIA_TYPE)
    header, data = rs.decode_binary(r.content)
    assert header["channels"] == ["EMG1"]
    np.testing.assert_array_equal(data, TREE_SIGNAL[1:2, :256])
    # by index, and level 1 = block mean over 4 samples (float32)
    r = client.get(_url(tree, channels="0", level=1, end=2, format="binary"), headers=h)
    header, data = rs.decode_binary(r.content)
    assert header["level"] == 1 and header["decimation"] == 4 and header["kind"] == "mean"
    ref = TREE_SIGNAL[0, :512].astype(np.float64).reshape(-1, 4).mean(axis=1)
    np.testing.assert_allclose(data[0], ref, rtol=0, atol=1e-3)
    r = client.get(_url(tree, level=1, kind="max", format="binary"), headers=h)
    _, data = rs.decode_binary(r.content)
    np.testing.assert_array_equal(data, TREE_SIGNAL[:, :256].reshape(2, -1, 4).max(axis=2))


@pytest.mark.parametrize(
    "q",
    [
        {"start": 1, "end": 1},
        {"start": 2, "end": 1},
        {"start": -1, "end": 1},
        {"channels": "Fp1"},
        {"channels": "Cz,Cz"},
        {"level": 9},
        {"format": "xml"},
        {"kind": "median"},
    ],
)
def test_bad_requests_are_422(client, as_role, tree, q):
    r = client.get(_url(tree, **q), headers=as_role("scientist"))
    assert r.status_code == 422, (q, r.text)
    assert r.headers["content-type"].startswith("application/problem+json")


def test_window_size_limits(app, client, as_role, tree):
    h = as_role("scientist")
    app.state.settings = dataclasses.replace(
        app.state.settings, window_max_values=600, window_json_max_values=300
    )
    r = client.get(_url(tree, end=2, format="binary"), headers=h)  # 2 x 512 = 1024 values
    assert r.status_code == 422 and r.json()["type"].endswith("window-too-large")
    assert r.json()["max_values"] == 600
    assert client.get(_url(tree, end=1, format="binary"), headers=h).status_code == 200  # 512
    r = client.get(_url(tree, end=1, format="json"), headers=h)  # 512 > json cap 300
    assert r.status_code == 422 and r.json()["max_values"] == 300
    # a pyramid level makes the same time span fit
    assert client.get(_url(tree, end=2, level=1, format="json"), headers=h).status_code == 200


def test_window_read_is_audited(client, as_role, tree, audit_events):
    r = client.get(_url(tree, format="binary"), headers=as_role("scientist"))
    assert r.status_code == 200
    evs = audit_events(request_id=r.headers["x-request-id"])
    reads = [e for e in evs if e["type"] == "data.read"]
    assert len(reads) == 1
    ev = reads[0]
    assert ev["resource_type"] == "recording_data" and ev["resource_id"] == tree["recording_id"]
    assert ev["action"] == "signal:read" and ev["details"]["count"] == 2 * 256
    assert ev["details"]["format"] == "binary"


def test_other_tenant_gets_404_and_nothing_is_decrypted(client, as_role, tenants, tree):
    """BOLA: B's owner, and B's API-less roles, cannot read A's signal."""
    for role in ("owner", "scientist", "data-steward"):
        r = client.get(_url(tree), headers=as_role(role, tenant=tenants.b))
        assert r.status_code == 404, role


def test_signal_is_ciphertext_at_rest(storage, tree, tenants):
    keys = list(storage.objects.list("zarr", f"t/{tenants.a}/"))
    assert keys, "the tree signal was written to the zarr bucket"
    for k in keys:
        blob = storage.objects.get("zarr", k)
        assert blob[:4] == b"NFE1", k
        assert b'"nf_signal"' not in blob and b'"ch_names"' not in blob


def test_quarantined_recording_scientist_403_steward_200(
    client, as_role, tree, engine, audit_events
):
    with engine.begin() as c:
        c.execute(
            text("UPDATE recording SET state = 'quarantined' WHERE id = :i"),
            {"i": tree["recording_id"]},
        )
    sci, steward = as_role("scientist"), as_role("data-steward")
    for path in (_url(tree), f"/v1/recordings/{tree['recording_id']}"):
        r = client.get(path, headers=sci)
        assert r.status_code == 403, path
        denied = audit_events(request_id=r.headers["x-request-id"], type_="authz.denied")
        assert denied and denied[-1]["resource_id"] == tree["recording_id"]
        assert client.get(path, headers=steward).status_code == 200, path
    # lists hide it from the scientist, show it to the steward
    lst = f"/v1/sessions/{tree['session_id']}/recordings"
    assert client.get(lst, headers=sci).json() == []
    assert [x["id"] for x in client.get(lst, headers=steward).json()] == [tree["recording_id"]]


def test_crypto_shredded_subject_is_410(client, as_role, tree, storage, tenants):
    storage.keyring.shred_subject(tenants.a, tree["subject_id"])
    r = client.get(_url(tree), headers=as_role("scientist"))
    assert r.status_code == 410 and r.json()["type"].endswith("gone")


def test_recording_without_signal_is_404(client, as_role, tree, engine):
    with engine.begin() as c:
        c.execute(
            text("UPDATE recording SET zarr_ref = NULL WHERE id = :i"), {"i": tree["recording_id"]}
        )
    assert client.get(_url(tree), headers=as_role("scientist")).status_code == 404
