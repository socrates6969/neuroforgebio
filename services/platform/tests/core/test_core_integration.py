"""CI-only (docker-compose.ci.yml): audit batches in an Object-Lock bucket on S3/MinIO (2.8,
SEC-101, SEC-105).

Skipped locally: needs NF_TEST_S3_ENDPOINT (MinIO) - the dev PC does not run Docker (RAM).
"""

from __future__ import annotations

import os
import uuid

import pytest
from nf_platform.audit import chain
from sqlalchemy import text

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("NF_TEST_S3_ENDPOINT"),
        reason="CI-only: needs the S3/MinIO service of services/platform/docker-compose.ci.yml",
    ),
]


@pytest.fixture
def s3_store():
    boto3 = pytest.importorskip("boto3")
    objects = pytest.importorskip("nf_platform.storage.objects")
    client = boto3.client(
        "s3",
        endpoint_url=os.environ["NF_TEST_S3_ENDPOINT"],
        aws_access_key_id=os.environ.get("NF_TEST_S3_ACCESS_KEY", "minioadmin"),
        aws_secret_access_key=os.environ.get("NF_TEST_S3_SECRET_KEY", "minioadmin"),
        region_name="us-east-1",
    )
    suffix = uuid.uuid4().hex[:8]
    names = {b: f"nf-core-{b}-{suffix}" for b in objects.BUCKETS}
    store = objects.S3ObjectStore(client, names, audit_retention_days=1)
    store.ensure_buckets()
    return client, names["audit"], store


def test_audit_batches_in_object_lock_bucket(engine, client, as_role, tenants, s3_store):
    s3, audit_bucket, store = s3_store
    client.get("/v1/whoami", headers=as_role("viewer"))
    with engine.begin() as c:
        c.execute(text("ALTER TABLE audit_event DISABLE TRIGGER audit_event_append_only"))
        c.execute(text("UPDATE audit_event SET ts = ts - interval '2 hours'"))
        c.execute(text("ALTER TABLE audit_event ENABLE TRIGGER audit_event_append_only"))
    results = chain.AuditBatcher(engine, store).run()
    res = next(r for r in results if r.scope == tenants.a)
    head = chain.chain_head(engine, tenants.a)
    assert chain.verify_stored_chain(store, tenants.a, expected_head=head) == [head]
    # the locked version cannot be deleted (COMPLIANCE retention)
    versions = s3.list_object_versions(Bucket=audit_bucket, Prefix=res.object_key)["Versions"]
    with pytest.raises(s3.exceptions.ClientError):
        s3.delete_object(
            Bucket=audit_bucket, Key=res.object_key, VersionId=versions[0]["VersionId"]
        )
    # an overwrite creates a new version that breaks verification against the DB head
    s3.put_object(Bucket=audit_bucket, Key=res.object_key, Body=b'{"schema":"forged"}')
    with pytest.raises(chain.AuditChainError):
        chain.verify_stored_chain(store, tenants.a, expected_head=head)
