"""KMS protocol, an in-memory `LocalKms` for dev/tests, and an AWS KMS adapter.

The KMS holds the tenant KEKs (one KMS key per tenant: SEC-021/SEC-023). Data keys are generated
by the KMS and returned twice: in plaintext (used, never stored) and wrapped under the KEK with an
*encryption context* that binds the wrap to `tenant_id` + `subject_id`. Unwrapping with a
different context fails, like AWS KMS `EncryptionContext`.

`LocalKms` wraps with AES-256-GCM (the context is the AAD) from the `cryptography` package
(SEC-032: vetted library, no custom primitives). Key material lives only in process memory and is
never logged or included in `repr`.
"""

from __future__ import annotations

import json
import logging
import os
import struct
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, runtime_checkable

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

log = logging.getLogger(__name__)

_WRAP_MAGIC = b"NFLK1"
MIN_DELETION_WINDOW = timedelta(days=7)  # AWS KMS minimum PendingWindowInDays


class KmsError(Exception):
    """Base class for KMS errors (never carries key material)."""


class KmsKeyUnavailable(KmsError):
    """The key (or key version) is disabled, pending deletion, or destroyed."""


def canonical_context(context: dict[str, str]) -> bytes:
    """Deterministic byte encoding of an encryption context (sorted keys, no whitespace)."""
    for k, v in context.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise KmsError("encryption context keys and values must be strings")
    return json.dumps(context, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


@runtime_checkable
class Kms(Protocol):
    def generate_data_key(self, key_id: str, context: dict[str, str]) -> tuple[bytes, bytes]:
        """Return (plaintext 32-byte data key, wrapped data key)."""
        ...

    def decrypt(self, key_id: str, wrapped: bytes, context: dict[str, str]) -> bytes: ...

    def schedule_key_deletion(self, key_id: str) -> None: ...


@runtime_checkable
class RotatingKms(Kms, Protocol):
    """Optional KMS capabilities used for KEK rotation (SEC-033)."""

    def current_version(self, key_id: str) -> int: ...

    def rotate_key(self, key_id: str) -> int: ...

    def re_encrypt(self, key_id: str, wrapped: bytes, context: dict[str, str]) -> bytes: ...

    def disable_key_version(self, key_id: str, version: int) -> None: ...


@dataclass
class _LocalKey:
    versions: dict[int, bytes] = field(default_factory=dict, repr=False)
    current: int = 0
    disabled: set[int] = field(default_factory=set)
    deletion_due: datetime | None = None


class LocalKms:
    """In-memory mock KMS. Each key has numbered versions (rotation keeps old versions for decrypt
    until they are disabled). `schedule_key_deletion` makes the key unusable at once (as AWS does
    while a key is pending deletion) and destroys the material after the waiting period via
    `purge_expired()` (SEC-123: no instant deletion outside the waiting period)."""

    def __init__(self, *, deletion_window: timedelta = MIN_DELETION_WINDOW) -> None:
        if deletion_window < MIN_DELETION_WINDOW:
            raise KmsError("deletion window must be at least 7 days (SEC-123)")
        self._keys: dict[str, _LocalKey] = {}
        self._lock = threading.Lock()
        self._deletion_window = deletion_window

    def __repr__(self) -> str:
        return f"LocalKms(keys={len(self._keys)})"

    # -- key management
    def create_key(self, key_id: str) -> None:
        with self._lock:
            if key_id not in self._keys:
                self._keys[key_id] = _LocalKey(versions={1: AESGCM.generate_key(256)}, current=1)
                log.info("kms key created", extra={"kms_key_id": key_id})

    def _key(self, key_id: str) -> _LocalKey:
        k = self._keys.get(key_id)
        if k is None:
            raise KmsKeyUnavailable(f"unknown KMS key {key_id!r}")
        if k.deletion_due is not None:
            raise KmsKeyUnavailable(f"KMS key {key_id!r} is pending deletion or destroyed")
        return k

    def current_version(self, key_id: str) -> int:
        with self._lock:
            return self._key(key_id).current

    def rotate_key(self, key_id: str) -> int:
        with self._lock:
            k = self._key(key_id)
            k.current += 1
            k.versions[k.current] = AESGCM.generate_key(256)
            log.info("kms key rotated", extra={"kms_key_id": key_id, "kek_version": k.current})
            return k.current

    def disable_key_version(self, key_id: str, version: int) -> None:
        with self._lock:
            k = self._key(key_id)
            if version == k.current:
                raise KmsError("cannot disable the current key version")
            k.disabled.add(version)

    def schedule_key_deletion(self, key_id: str) -> None:
        with self._lock:
            k = self._keys.get(key_id)
            if k is None:
                raise KmsKeyUnavailable(f"unknown KMS key {key_id!r}")
            k.deletion_due = datetime.now(UTC) + self._deletion_window
            log.warning("kms key scheduled for deletion", extra={"kms_key_id": key_id})

    def purge_expired(self, now: datetime | None = None) -> int:
        """Destroy key material whose waiting period has passed. Returns keys destroyed."""
        now = now or datetime.now(UTC)
        n = 0
        with self._lock:
            for k in self._keys.values():
                if k.deletion_due is not None and k.deletion_due <= now and k.versions:
                    k.versions.clear()
                    n += 1
        return n

    # -- crypto
    def _wrap(self, key_id: str, k: _LocalKey, version: int, pt: bytes, ctx: bytes) -> bytes:
        nonce = os.urandom(12)
        aad = _WRAP_MAGIC + key_id.encode() + b"\x00" + ctx
        ct = AESGCM(k.versions[version]).encrypt(nonce, pt, aad)
        return _WRAP_MAGIC + struct.pack(">I", version) + nonce + ct

    def generate_data_key(self, key_id: str, context: dict[str, str]) -> tuple[bytes, bytes]:
        ctx = canonical_context(context)
        with self._lock:
            k = self._key(key_id)
            pt = AESGCM.generate_key(256)
            return pt, self._wrap(key_id, k, k.current, pt, ctx)

    def decrypt(self, key_id: str, wrapped: bytes, context: dict[str, str]) -> bytes:
        ctx = canonical_context(context)
        if len(wrapped) < len(_WRAP_MAGIC) + 4 + 12 + 16 or not wrapped.startswith(_WRAP_MAGIC):
            raise KmsError("malformed wrapped key")
        (version,) = struct.unpack(">I", wrapped[5:9])
        with self._lock:
            k = self._key(key_id)
            if version in k.disabled:
                raise KmsKeyUnavailable(f"KMS key {key_id!r} version {version} is disabled")
            kek = k.versions.get(version)
            if kek is None:
                raise KmsKeyUnavailable(f"KMS key {key_id!r} version {version} does not exist")
        nonce, ct = wrapped[9:21], wrapped[21:]
        aad = _WRAP_MAGIC + key_id.encode() + b"\x00" + ctx
        try:
            return AESGCM(kek).decrypt(nonce, ct, aad)
        except InvalidTag as e:
            raise KmsError("unwrap failed (wrong key, context or corrupted blob)") from e

    def re_encrypt(self, key_id: str, wrapped: bytes, context: dict[str, str]) -> bytes:
        pt = self.decrypt(key_id, wrapped, context)
        with self._lock:
            k = self._key(key_id)
            return self._wrap(key_id, k, k.current, pt, canonical_context(context))

    def wrapped_version(self, wrapped: bytes) -> int:
        return struct.unpack(">I", wrapped[5:9])[0]

    def _material_for_tests(self, key_id: str) -> list[bytes]:
        """Test hook only (log-scan test): all key versions' material."""
        return list(self._keys[key_id].versions.values())


class AwsKms:
    """AWS KMS adapter (boto3 `kms` client). Rotation is AWS-managed (yearly automatic rotation
    keeps the same key id; SEC-033), so `current_version` is always 1 here and old backing keys
    stay usable for decrypt as AWS guarantees. Tested with moto; real AWS is never called in tests.
    """

    def __init__(self, client: Any, *, pending_window_days: int = 7) -> None:
        if pending_window_days < 7:
            raise KmsError("pending window must be at least 7 days (SEC-123)")
        self._kms = client
        self._window = pending_window_days

    def generate_data_key(self, key_id: str, context: dict[str, str]) -> tuple[bytes, bytes]:
        canonical_context(context)
        try:
            r = self._kms.generate_data_key(
                KeyId=key_id, KeySpec="AES_256", EncryptionContext=context
            )
        except self._kms.exceptions.ClientError as e:
            raise KmsKeyUnavailable(f"generate_data_key failed: {_aws_code(e)}") from None
        return r["Plaintext"], r["CiphertextBlob"]

    def decrypt(self, key_id: str, wrapped: bytes, context: dict[str, str]) -> bytes:
        canonical_context(context)
        try:
            r = self._kms.decrypt(CiphertextBlob=wrapped, KeyId=key_id, EncryptionContext=context)
        except self._kms.exceptions.ClientError as e:
            raise KmsKeyUnavailable(f"decrypt failed: {_aws_code(e)}") from None
        return r["Plaintext"]

    def schedule_key_deletion(self, key_id: str) -> None:
        self._kms.schedule_key_deletion(KeyId=key_id, PendingWindowInDays=self._window)

    def current_version(self, key_id: str) -> int:
        return 1


def _aws_code(e: Any) -> str:
    try:
        return str(e.response["Error"]["Code"])
    except (AttributeError, KeyError, TypeError):
        return type(e).__name__
