"""2.3 acceptance: envelope crypto, AAD binding, nonce uniqueness, crypto-shred, rotation, logs."""

from __future__ import annotations

import base64
import json
import logging
import shutil
import struct

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from nf_platform.storage import (
    DecryptionError,
    InMemoryKeyStore,
    Keyring,
    LocalKms,
    LocalObjectStore,
    SubjectKeyUnavailable,
    parse_header,
)
from nf_platform.storage.encrypted import EncryptedObjectStore
from nf_platform.storage.keyring import MAGIC, EnvelopeFormatError
from nf_platform.storage.kms import KmsError, KmsKeyUnavailable

PLAINTEXT = b"synthetic signal chunk " * 64


@pytest.fixture
def kms() -> LocalKms:
    return LocalKms()


@pytest.fixture
def keystore() -> InMemoryKeyStore:
    return InMemoryKeyStore()


@pytest.fixture
def keyring(kms, keystore) -> Keyring:
    return Keyring(kms, keystore)


@pytest.fixture
def enc_store(tmp_path, keyring) -> EncryptedObjectStore:
    return EncryptedObjectStore(LocalObjectStore(tmp_path / "primary"), keyring)


def test_roundtrip_and_header_fields(keyring):
    blob = keyring.encrypt("t1", "s1", "raw/a.edf", 1, PLAINTEXT)
    assert keyring.decrypt("t1", "s1", "raw/a.edf", 1, blob) == PLAINTEXT
    header, *_ = parse_header(blob)
    # SEC-038: every envelope records alg, kek_id and kek_version.
    assert header.alg == "AES-256-GCM"
    assert header.kek_id == "nf/tenant/t1"
    assert header.kek_version == 1
    assert header.dek_version == 1
    assert blob.startswith(MAGIC)
    hlen = struct.unpack(">H", blob[4:6])[0]
    assert set(json.loads(blob[6 : 6 + hlen])) == {
        "alg",
        "dek_version",
        "kek_id",
        "kek_version",
        "v",
    }


def test_object_read_without_key_is_ciphertext(enc_store, tmp_path):
    meta = enc_store.put("t1", "s1", "raw", "sub-1/rec.edf", PLAINTEXT)
    on_disk = (tmp_path / "primary" / "raw" / "sub-1" / "rec.edf").read_bytes()
    raw = enc_store.objects.get("raw", "sub-1/rec.edf")
    assert on_disk == raw
    assert PLAINTEXT not in raw
    assert b"synthetic signal chunk" not in raw
    assert meta.size_bytes == len(PLAINTEXT) and meta.ciphertext_size == len(raw)
    assert enc_store.get("t1", "s1", "raw", "sub-1/rec.edf") == PLAINTEXT


@pytest.mark.parametrize(
    "binding",
    [
        ("t2", "s1", "raw/a", 1),  # other tenant
        ("t1", "s2", "raw/a", 1),  # other subject
        ("t1", "s1", "raw/b", 1),  # other object key
        ("t1", "s1", "raw/a", 2),  # other object version
    ],
)
def test_tampered_aad_fails(keyring, binding):
    keyring.encrypt("t2", "s1", "x", 1, b"x")  # t2 has keys too, so the failure is the AAD/KEK
    keyring.encrypt("t1", "s2", "x", 1, b"x")
    blob = keyring.encrypt("t1", "s1", "raw/a", 1, PLAINTEXT)
    with pytest.raises((DecryptionError, SubjectKeyUnavailable)):
        keyring.decrypt(*binding, blob)


def test_tampered_ciphertext_and_header_fail(keyring):
    blob = bytearray(keyring.encrypt("t1", "s1", "raw/a", 1, PLAINTEXT))
    for pos in (len(blob) - 1, len(blob) - 20, 6 + 4, 3):
        bad = bytearray(blob)
        bad[pos] ^= 0x01
        with pytest.raises(DecryptionError):
            keyring.decrypt("t1", "s1", "raw/a", 1, bytes(bad))
    with pytest.raises(DecryptionError):
        keyring.decrypt("t1", "s1", "raw/a", 1, bytes(blob[:-1]))
    with pytest.raises(EnvelopeFormatError):
        keyring.decrypt("t1", "s1", "raw/a", 1, b"garbage")


def test_header_alg_swap_detected(keyring):
    blob = keyring.encrypt("t1", "s1", "raw/a", 1, PLAINTEXT)
    header, prefix, nonce, ct = parse_header(blob)
    # Re-encode the header with a different kek_version (same length) -> AAD mismatch.
    forged = prefix.replace(b'"kek_version":1', b'"kek_version":2')
    assert forged != prefix
    with pytest.raises(DecryptionError):
        keyring.decrypt("t1", "s1", "raw/a", 1, forged + nonce + ct)


@settings(
    max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(st.lists(st.binary(max_size=64), min_size=50, max_size=200))
def test_nonce_uniqueness_property(keyring, payloads):
    seen: set[bytes] = set()
    total = 0
    for i, p in enumerate(payloads):
        blob = keyring.encrypt("t1", "s1", f"obj/{i}", 1, p)
        _, _, nonce, _ = parse_header(blob)
        assert len(nonce) == 12
        seen.add(nonce)
        total += 1
    assert len(seen) == total


def test_nonce_unique_for_identical_inputs(keyring):
    blobs = {keyring.encrypt("t1", "s1", "same", 1, b"same") for _ in range(2000)}
    assert len(blobs) == 2000


def test_dek_rekeyed_at_encryption_limit(kms, keystore):
    kr = Keyring(kms, keystore, max_encryptions_per_dek=3)
    blobs = [kr.encrypt("t1", "s1", f"k{i}", 1, b"d") for i in range(7)]
    versions = [parse_header(b)[0].dek_version for b in blobs]
    assert versions == [1, 1, 1, 2, 2, 2, 3]
    for i, b in enumerate(blobs):  # retired DEKs still decrypt old data
        assert kr.decrypt("t1", "s1", f"k{i}", 1, b) == b"d"


def test_per_tenant_kms_keys_and_context_binding(kms, keystore, keyring):
    keyring.encrypt("tA", "s1", "k", 1, b"a")
    keyring.encrypt("tB", "s1", "k", 1, b"b")
    ra = keystore.get_wrapped("tA", "s1")
    rb = keystore.get_wrapped("tB", "s1")
    assert ra.kek_id != rb.kek_id  # one KMS key per tenant
    # Tenant B's KEK cannot unwrap tenant A's DEK, and the context must match exactly.
    with pytest.raises(KmsError):
        kms.decrypt(rb.kek_id, ra.wrapped, {"tenant_id": "tA", "subject_id": "s1"})
    with pytest.raises(KmsError):
        kms.decrypt(ra.kek_id, ra.wrapped, {"tenant_id": "tA", "subject_id": "s2"})


def test_crypto_shred_primary_and_backup(tmp_path, kms, keystore):
    keyring = Keyring(kms, keystore)
    primary = LocalObjectStore(tmp_path / "primary")
    enc = EncryptedObjectStore(primary, keyring)
    objs = {
        ("s-shred", "raw", "sub-a/rec.edf"): b"A" * 5000,
        ("s-shred", "zarr", "rec-a/data/0/c/0/0"): b"B" * 3000,
        ("s-keep", "raw", "sub-b/rec.edf"): b"C" * 5000,
    }
    for (subj, bucket, key), data in objs.items():
        enc.put("t1", subj, bucket, key, data)

    # Backup copy made BEFORE the shred (e.g. a replica or a snapshot of the bucket).
    shutil.copytree(tmp_path / "primary", tmp_path / "backup")
    backup = EncryptedObjectStore(LocalObjectStore(tmp_path / "backup"), keyring)
    for (subj, bucket, key), data in objs.items():
        assert backup.get("t1", subj, bucket, key) == data

    assert keyring.shred_subject("t1", "s-shred") == 1
    assert keystore.list_wrapped("t1", "s-shred") == []

    for store in (enc, backup):
        for (subj, bucket, key), data in objs.items():
            if subj == "s-shred":
                with pytest.raises(SubjectKeyUnavailable):
                    store.get("t1", subj, bucket, key)
                assert data not in store.objects.get(bucket, key)
            else:
                assert store.get("t1", subj, bucket, key) == data

    # A fresh Keyring (no cache) over the same KeyStore also cannot decrypt.
    fresh = EncryptedObjectStore(LocalObjectStore(tmp_path / "backup"), Keyring(kms, keystore))
    with pytest.raises(SubjectKeyUnavailable):
        fresh.get("t1", "s-shred", "raw", "sub-a/rec.edf")
    # SEC-034a (M2-REVIEW F1, m5-ledger): a shredded subject is tombstoned. A new write for it is
    # refused (no new DEK is ever minted), and the old data stays unreadable.
    with pytest.raises(SubjectKeyUnavailable):
        enc.put("t1", "s-shred", "raw", "sub-a/new.edf", b"new")
    assert keystore.list_wrapped("t1", "s-shred") == []
    with pytest.raises((SubjectKeyUnavailable, DecryptionError)):
        enc.get("t1", "s-shred", "raw", "sub-a/rec.edf")


def test_kek_rotation_rewraps_without_rewrite(kms, keystore, keyring):
    blobs = {s: keyring.encrypt("t1", s, "k", 1, s.encode()) for s in ("s1", "s2", "s3")}
    old = {s: keystore.get_wrapped("t1", s) for s in blobs}
    assert keyring.rotate_tenant_kek("t1") == 3
    fresh = Keyring(kms, keystore)  # no cached DEKs
    for s, b in blobs.items():
        assert fresh.decrypt("t1", s, "k", 1, b) == s.encode()
        assert keystore.get_wrapped("t1", s).kek_version == 2
    # The old KEK version is disabled: an old wrapped DEK no longer unwraps.
    with pytest.raises(KmsKeyUnavailable):
        kms.decrypt("nf/tenant/t1", old["s1"].wrapped, {"tenant_id": "t1", "subject_id": "s1"})
    # New objects record the new KEK version in their header.
    assert parse_header(fresh.encrypt("t1", "s1", "k2", 1, b"x"))[0].kek_version == 2


def test_kms_deletion_waiting_period(kms):
    from datetime import UTC, datetime, timedelta

    kms.create_key("k")
    pt, wrapped = kms.generate_data_key("k", {"a": "b"})
    kms.schedule_key_deletion("k")
    with pytest.raises(KmsKeyUnavailable):
        kms.decrypt("k", wrapped, {"a": "b"})
    assert kms.purge_expired(datetime.now(UTC) + timedelta(days=1)) == 0  # still in window
    assert kms.purge_expired(datetime.now(UTC) + timedelta(days=8)) == 1
    with pytest.raises(KmsError):
        LocalKms(deletion_window=timedelta(days=1))


class _Collect(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        extras = {
            k: v for k, v in record.__dict__.items() if k not in logging.makeLogRecord({}).__dict__
        }
        self.lines.append(f"{record.getMessage()} {extras!r} {record.exc_text or ''}")


def _forms(key: bytes) -> list[str]:
    return [
        key.hex(),
        key.hex().upper(),
        base64.b64encode(key).decode(),
        base64.urlsafe_b64encode(key).decode(),
        base64.b64encode(key).decode().rstrip("="),
        repr(key)[2:-1],
        key.decode("latin-1"),
    ]


def test_keys_never_logged(tmp_path, kms, keystore):
    handler = _Collect()
    root = logging.getLogger()
    old_level = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    try:
        keyring = Keyring(kms, keystore)
        enc = EncryptedObjectStore(LocalObjectStore(tmp_path / "p"), keyring)
        for s in ("s1", "s2"):
            enc.put("t1", s, "raw", f"{s}/f", PLAINTEXT)
            enc.get("t1", s, "raw", f"{s}/f")
        keyring.rotate_tenant_kek("t1")
        errors = []
        try:
            keyring.decrypt("t1", "s1", "raw/other", 1, enc.objects.get("raw", "s1/f"))
        except DecryptionError as e:
            errors.append(repr(e) + str(e))
        deks = [
            kms.decrypt(r.kek_id, r.wrapped, {"tenant_id": "t1", "subject_id": r.subject_id})
            for r in keystore.list_tenant("t1")
        ]
        keyring.shred_subject("t1", "s1")
        try:
            enc.get("t1", "s1", "raw", "s1/f")
        except SubjectKeyUnavailable as e:
            errors.append(repr(e) + str(e))
            logging.getLogger("nf_platform.test").exception("expected failure")
        texts = handler.lines + errors + [repr(keyring), repr(kms)]
        texts += [repr(r) for r in keystore.list_tenant("t1")]
    finally:
        root.removeHandler(handler)
        root.setLevel(old_level)

    assert handler.lines, "the log-scan test must actually capture log records"
    secrets = deks + kms._material_for_tests("nf/tenant/t1")
    assert len(secrets) >= 4
    blob = "\n".join(texts)
    for key in secrets:
        for form in _forms(key):
            assert form not in blob
