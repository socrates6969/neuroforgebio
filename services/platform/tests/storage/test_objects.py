"""ObjectStore implementations: LocalObjectStore, S3ObjectStore (moto locally, MinIO in CI)."""

from __future__ import annotations

import os
import uuid

import pytest
from nf_platform.storage import (
    BUCKETS,
    InvalidObjectKey,
    LocalObjectStore,
    ObjectNotFound,
    ObjectStore,
    WormViolation,
)
from nf_platform.storage.objects import S3ObjectStore


def _exercise(store) -> None:
    assert isinstance(store, ObjectStore)
    store.put("raw", "t1/a/b.bin", b"one", metadata={"nf-enc": "NFE1"})
    store.put("raw", "t1/a/c.bin", b"two")
    store.put("zarr", "rec/zarr.json", b"{}")
    assert store.get("raw", "t1/a/b.bin") == b"one"
    assert list(store.list("raw", "t1/a/")) == ["t1/a/b.bin", "t1/a/c.bin"]
    assert list(store.list("zarr", "")) == ["rec/zarr.json"]
    store.put("raw", "t1/a/b.bin", b"one-v2")
    assert store.get("raw", "t1/a/b.bin") == b"one-v2"
    store.delete("raw", "t1/a/b.bin")
    with pytest.raises(ObjectNotFound):
        store.get("raw", "t1/a/b.bin")
    store.put("audit", "2026/09/26/batch-1.json", b"audit")
    with pytest.raises(WormViolation):
        store.delete("audit", "2026/09/26/batch-1.json")
    if isinstance(store, LocalObjectStore):  # in S3 an overwrite is a new locked version
        with pytest.raises(WormViolation):
            store.put("audit", "2026/09/26/batch-1.json", b"rewrite")
    assert store.get("audit", "2026/09/26/batch-1.json") == b"audit"


def test_local_store(tmp_path):
    store = LocalObjectStore(tmp_path)
    assert {p.name for p in tmp_path.iterdir()} == set(BUCKETS)
    _exercise(store)
    assert store.get_metadata("raw", "t1/a/c.bin") == {}


@pytest.mark.parametrize(
    "bucket,key",
    [
        ("nope", "a"),
        ("raw", ""),
        ("raw", "../etc/passwd"),
        ("raw", "a/../../b"),
        ("raw", "/abs"),
        ("raw", "a//b"),
        ("raw", "a\\b"),
        ("raw", "C:x"),
        ("raw", "a\x00b"),
        ("raw", "x" * 1025),
    ],
)
def test_invalid_keys_rejected(tmp_path, bucket, key):
    store = LocalObjectStore(tmp_path)
    with pytest.raises(InvalidObjectKey):
        store.put(bucket, key, b"x")


def test_s3_store_with_moto():
    boto3 = pytest.importorskip("boto3")
    moto = pytest.importorskip("moto")
    with moto.mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        names = {b: f"nf-test-{b}" for b in BUCKETS}
        store = S3ObjectStore(client, names)
        store.ensure_buckets()
        _exercise(store)
        assert store.get_metadata("raw", "t1/a/c.bin") == {}
        lock = client.get_object_lock_configuration(Bucket="nf-test-audit")
        assert lock["ObjectLockConfiguration"]["ObjectLockEnabled"] == "Enabled"
        ver = client.get_bucket_versioning(Bucket="nf-test-raw")
        assert ver["Status"] == "Enabled"


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("NF_TEST_S3_ENDPOINT"), reason="CI-only: needs MinIO")
def test_s3_store_minio():
    import boto3

    client = boto3.client(
        "s3",
        endpoint_url=os.environ["NF_TEST_S3_ENDPOINT"],
        aws_access_key_id=os.environ.get("NF_TEST_S3_ACCESS_KEY", "minioadmin"),
        aws_secret_access_key=os.environ.get("NF_TEST_S3_SECRET_KEY", "minioadmin"),
        region_name="us-east-1",
    )
    suffix = uuid.uuid4().hex[:8]
    store = S3ObjectStore(client, {b: f"nf-it-{b}-{suffix}" for b in BUCKETS})
    store.ensure_buckets()
    _exercise(store)
