"""2.6 with the S3 backend: real pre-signed multipart ``UploadPart`` URLs; the client PUTs parts
straight to the object store, the platform re-hashes and re-seals them under the subject DEK on
completion. Locally against moto; against MinIO in CI (``integration``, NF_TEST_S3_ENDPOINT)."""

from __future__ import annotations

import contextlib
import hashlib
import os
import uuid

import pytest
from nf_platform.ingest.uploads.backends import S3PartBackend

boto3 = pytest.importorskip("boto3")
requests = pytest.importorskip("requests")
pytestmark = pytest.mark.postgres
PART = 5 * 1024 * 1024  # S3's minimum part size (all but the last part)


@contextlib.contextmanager
def _moto():
    moto = pytest.importorskip("moto")
    with moto.mock_aws():
        yield boto3.client("s3", region_name="us-east-1")


@contextlib.contextmanager
def _minio():
    yield boto3.client(
        "s3",
        endpoint_url=os.environ["NF_TEST_S3_ENDPOINT"],
        aws_access_key_id=os.environ.get("NF_TEST_S3_ACCESS_KEY", "minioadmin"),
        aws_secret_access_key=os.environ.get("NF_TEST_S3_SECRET_KEY", "minioadmin"),
        region_name="us-east-1",
    )


@pytest.fixture(
    params=[
        pytest.param("moto"),
        pytest.param(
            "minio",
            marks=[
                pytest.mark.integration,
                pytest.mark.skipif(
                    not os.environ.get("NF_TEST_S3_ENDPOINT"), reason="CI-only: needs MinIO"
                ),
            ],
        ),
    ]
)
def s3_app(request, app):
    ctx = _moto() if request.param == "moto" else _minio()
    with ctx as s3:
        bucket = f"nf-staging-{uuid.uuid4().hex[:8]}"
        s3.create_bucket(Bucket=bucket)
        app.state.upload_backend = S3PartBackend(s3, bucket)
        yield s3, bucket


def _blob() -> bytes:
    return os.urandom(PART) + os.urandom(1000)  # 2 parts


def _start(client, h, tree, blob) -> dict:
    r = client.post(
        f"/v1/datasets/{tree['dataset_id']}/uploads",
        json={
            "session_id": tree["session_id"],
            "filename": "big.edf",
            "size_bytes": len(blob),
            "part_size": PART,
            "synthetic": True,
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_presigned_multipart_resume_and_verify(s3_app, client, as_role, tree, storage):
    s3, bucket = s3_app
    h = as_role("scientist")
    blob = _blob()
    up = _start(client, h, tree, blob)
    targets = up["parts"]
    assert [t["part_number"] for t in targets] == [1, 2]
    assert all(t["auth"] == "none" and t["expires_at"] for t in targets)
    # part 1 now; the "client restarts" and asks again: only part 2 is still wanted
    r = requests.put(targets[0]["url"], data=blob[:PART], timeout=30)
    assert r.status_code == 200, r.text
    again = client.get(f"/v1/uploads/{up['id']}", headers=h).json()
    assert [t["part_number"] for t in again["parts"]] == [2]
    r = requests.put(again["parts"][0]["url"], data=blob[PART:], timeout=30)
    assert r.status_code == 200, r.text
    sha = hashlib.sha256(blob).hexdigest()
    r = client.post(f"/v1/uploads/{up['id']}/complete", json={"sha256": sha}, headers=h)
    assert r.status_code == 202, r.text
    done = r.json()
    assert done["state"] == "uploaded" and done["server_sha256"] == sha
    # re-sealed as NFE1 parts in the raw bucket; the plaintext staging object is gone
    raw = [k for k in storage.objects.list("raw", "t/") if f"/u/{up['id']}/" in k]
    assert sorted(k.rsplit("/", 1)[-1] for k in raw) == [
        "manifest.json",
        "part-00001",
        "part-00002",
    ]
    sealed = storage.objects.get("raw", next(k for k in raw if k.endswith("part-00001")))
    assert sealed[:4] == b"NFE1" and blob[:64] not in sealed
    assert not s3.list_objects_v2(Bucket=bucket).get("Contents")


def test_presigned_hash_mismatch_rejects(s3_app, client, as_role, tree):
    h = as_role("scientist")
    blob = _blob()
    up = _start(client, h, tree, blob)
    for t, data in zip(up["parts"], (blob[:PART], blob[PART:]), strict=True):
        assert requests.put(t["url"], data=data, timeout=30).status_code == 200
    bad = hashlib.sha256(b"not it").hexdigest()
    r = client.post(f"/v1/uploads/{up['id']}/complete", json={"sha256": bad}, headers=h)
    assert r.status_code == 422 and r.json()["type"].endswith("hash-mismatch")
    assert client.get(f"/v1/uploads/{up['id']}", headers=h).json()["state"] == "rejected"
