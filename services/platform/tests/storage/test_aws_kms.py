"""AwsKms adapter + Keyring against moto's KMS mock (no real AWS call is ever made)."""

from __future__ import annotations

import pytest
from nf_platform.storage import InMemoryKeyStore, Keyring, SubjectKeyUnavailable
from nf_platform.storage.kms import AwsKms, KmsKeyUnavailable

boto3 = pytest.importorskip("boto3")
moto = pytest.importorskip("moto")


@pytest.fixture
def aws(monkeypatch):
    for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        monkeypatch.setenv(k, "testing")
    with moto.mock_aws():
        yield boto3.client("kms", region_name="eu-west-1")


def test_keyring_with_aws_kms(aws):
    keys = {t: aws.create_key(Description=f"tenant {t}")["KeyMetadata"]["KeyId"] for t in "AB"}
    kms = AwsKms(aws)
    store = InMemoryKeyStore()
    kr = Keyring(kms, store, kek_id_for=lambda t: keys[t])
    blob = kr.encrypt("A", "s1", "raw/x", 1, b"payload")
    assert Keyring(kms, store, kek_id_for=lambda t: keys[t]).decrypt(
        "A", "s1", "raw/x", 1, blob
    ) == (b"payload")
    rec = store.get_wrapped("A", "s1")
    # Encryption context mismatch is refused by KMS.
    with pytest.raises(KmsKeyUnavailable):
        kms.decrypt(keys["A"], rec.wrapped, {"tenant_id": "A", "subject_id": "other"})
    kr.shred_subject("A", "s1")
    with pytest.raises(SubjectKeyUnavailable):
        kr.decrypt("A", "s1", "raw/x", 1, blob)


def test_pending_window_minimum(aws):
    from nf_platform.storage.kms import KmsError

    with pytest.raises(KmsError):
        AwsKms(aws, pending_window_days=1)
