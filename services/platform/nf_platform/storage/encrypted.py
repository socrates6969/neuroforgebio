"""Client-side encrypted object access: every object is sealed with its subject's DEK before it is
handed to the ObjectStore (BUILD-GUIDE 2.3). The AAD binds tenant, subject, `<bucket>/<key>` and
the object version, so a blob copied to another key, subject or tenant does not decrypt."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from nf_platform.storage.keyring import Keyring, parse_header
from nf_platform.storage.objects import ObjectStore


@dataclass(frozen=True)
class StoredObject:
    """Row shape for `stored_object` (m2-core's table)."""

    tenant_id: str
    subject_id: str
    bucket: str
    object_key: str
    object_version: int
    sha256: str  # of the plaintext
    size_bytes: int
    ciphertext_size: int
    dek_version: int
    kek_id: str
    kek_version: int
    alg: str


class EncryptedObjectStore:
    def __init__(self, objects: ObjectStore, keyring: Keyring) -> None:
        self.objects = objects
        self.keyring = keyring

    def put(
        self,
        tenant_id: str,
        subject_id: str,
        bucket: str,
        key: str,
        data: bytes,
        *,
        version: int = 1,
    ) -> StoredObject:
        blob = self.keyring.encrypt(tenant_id, subject_id, f"{bucket}/{key}", version, data)
        header, *_ = parse_header(blob)
        # Only non-identifying metadata travels with the object (no subject id, no key material).
        self.objects.put(
            bucket,
            key,
            blob,
            metadata={"nf-enc": "NFE1", "nf-version": str(version)},
        )
        return StoredObject(
            tenant_id=tenant_id,
            subject_id=subject_id,
            bucket=bucket,
            object_key=key,
            object_version=version,
            sha256=hashlib.sha256(data).hexdigest(),
            size_bytes=len(data),
            ciphertext_size=len(blob),
            dek_version=header.dek_version,
            kek_id=header.kek_id,
            kek_version=header.kek_version,
            alg=header.alg,
        )

    def get(
        self, tenant_id: str, subject_id: str, bucket: str, key: str, *, version: int = 1
    ) -> bytes:
        blob = self.objects.get(bucket, key)
        return self.keyring.decrypt(tenant_id, subject_id, f"{bucket}/{key}", version, blob)
