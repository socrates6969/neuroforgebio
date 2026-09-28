"""Tenant KEK -> per-subject DEK envelope encryption (SEC-031..034, SEC-038).

Envelope format v1 (all integers big-endian):

    "NFE1" (4) | header_len u16 | header (canonical JSON) | nonce (12) | ciphertext || tag (16)

The header records `alg`, `kek_id`, `kek_version`, `dek_version` and the format version `v`
(crypto-agility, SEC-038). The AEAD associated data is

    magic | header_len | header | 0x00 | canonical JSON {object_key, subject_id, tenant_id, version}

so a blob only decrypts for the tenant, subject, object key and object version it was written for
(SEC-031), and any change to the header is detected as well.

Nonces are 96-bit random values from `os.urandom` per encryption. Each DEK's encryption count is
tracked in the KeyStore and the DEK is replaced by a new version before 2**32 encryptions
(NIST SP 800-38D §8.3 limit for random nonces; SEC-033).

Crypto-shred (SEC-034): `shred_subject` deletes every wrapped DEK of the subject from the KeyStore
and drops cached plaintext DEKs. Ciphertext anywhere (primary store, replicas, backups) can then no
longer be decrypted. The subject stays tombstoned (SEC-034a): a later `encrypt` for it raises
`SubjectKeyUnavailable` instead of minting a new DEK. Caveat recorded for D4: database backups
that still contain the wrapped DEK row must expire (or be excluded) for the shred to be complete
in *all* copies.
"""

from __future__ import annotations

import json
import logging
import os
import struct
import threading
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from nf_platform.storage.kms import Kms, KmsError, RotatingKms

log = logging.getLogger(__name__)

MAGIC = b"NFE1"
FORMAT_VERSION = 1
NONCE_LEN = 12
TAG_LEN = 16
MAX_HEADER_LEN = 1024
MAX_ENCRYPTIONS_PER_DEK = 2**32

# Algorithm registry: the envelope `alg` is config-driven (SEC-038). Only vetted AEADs.
ALGORITHMS: dict[str, Callable[[bytes], AESGCM]] = {"AES-256-GCM": AESGCM}
DEFAULT_ALG = "AES-256-GCM"


class KeyringError(Exception):
    """Base class; messages never include key material or plaintext."""


class DecryptionError(KeyringError):
    """Authentication failed: wrong tenant/subject/object key/version, or tampered data."""


class SubjectKeyUnavailable(KeyringError):
    """No wrapped DEK exists for this subject/version (e.g. crypto-shredded) or KMS refused it."""


class EnvelopeFormatError(DecryptionError):
    """The blob is not a valid envelope."""


@dataclass(frozen=True)
class WrappedDek:
    tenant_id: str
    subject_id: str
    dek_version: int
    kek_id: str
    kek_version: int
    wrapped: bytes = field(repr=False)
    alg: str = DEFAULT_ALG
    state: str = "active"  # active | retired | shredded
    encryption_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@runtime_checkable
class KeyStore(Protocol):
    """Persistence for wrapped DEKs (table `subject_key`, owned by m2-core)."""

    def get_wrapped(
        self, tenant_id: str, subject_id: str, dek_version: int | None = None
    ) -> WrappedDek | None: ...

    def put_wrapped(self, rec: WrappedDek) -> None: ...

    def list_wrapped(self, tenant_id: str, subject_id: str) -> list[WrappedDek]: ...

    def list_tenant(self, tenant_id: str) -> list[WrappedDek]: ...

    def delete_subject(self, tenant_id: str, subject_id: str) -> int: ...

    def bump_count(self, tenant_id: str, subject_id: str, dek_version: int, n: int = 1) -> int: ...


def is_shredded(keystore: KeyStore, tenant_id: str, subject_id: str) -> bool:
    """SEC-034a: has this subject ever been crypto-shredded (tombstoned)? Uses the store's own
    ``is_shredded`` when it has one, else looks for a ``shredded`` row."""
    fn = getattr(keystore, "is_shredded", None)
    if fn is not None:
        return bool(fn(tenant_id, subject_id))
    return any(r.state == "shredded" for r in keystore.list_wrapped(tenant_id, subject_id))


class InMemoryKeyStore:
    """Dict-backed KeyStore for tests and local dev."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str, int], WrappedDek] = {}
        self._shredded: set[tuple[str, str]] = set()  # SEC-034a tombstones
        self._lock = threading.Lock()

    def is_shredded(self, tenant_id: str, subject_id: str) -> bool:
        with self._lock:
            return (tenant_id, subject_id) in self._shredded

    def get_wrapped(
        self, tenant_id: str, subject_id: str, dek_version: int | None = None
    ) -> WrappedDek | None:
        with self._lock:
            if dek_version is not None:
                return self._rows.get((tenant_id, subject_id, dek_version))
            active = [
                r
                for (t, s, _v), r in self._rows.items()
                if t == tenant_id and s == subject_id and r.state == "active"
            ]
            return max(active, key=lambda r: r.dek_version) if active else None

    def put_wrapped(self, rec: WrappedDek) -> None:
        with self._lock:
            self._rows[(rec.tenant_id, rec.subject_id, rec.dek_version)] = rec

    def list_wrapped(self, tenant_id: str, subject_id: str) -> list[WrappedDek]:
        with self._lock:
            return sorted(
                (r for (t, s, _), r in self._rows.items() if t == tenant_id and s == subject_id),
                key=lambda r: r.dek_version,
            )

    def list_tenant(self, tenant_id: str) -> list[WrappedDek]:
        with self._lock:
            return [r for (t, _s, _v), r in self._rows.items() if t == tenant_id]

    def delete_subject(self, tenant_id: str, subject_id: str) -> int:
        with self._lock:
            keys = [k for k in self._rows if k[0] == tenant_id and k[1] == subject_id]
            for k in keys:
                del self._rows[k]
            self._shredded.add((tenant_id, subject_id))
            return len(keys)

    def bump_count(self, tenant_id: str, subject_id: str, dek_version: int, n: int = 1) -> int:
        with self._lock:
            key = (tenant_id, subject_id, dek_version)
            rec = self._rows[key]
            rec = replace(rec, encryption_count=rec.encryption_count + n)
            self._rows[key] = rec
            return rec.encryption_count


@dataclass(frozen=True)
class EnvelopeHeader:
    alg: str
    kek_id: str
    kek_version: int
    dek_version: int
    v: int = FORMAT_VERSION

    def encode(self) -> bytes:
        return _cjson(
            {
                "alg": self.alg,
                "dek_version": self.dek_version,
                "kek_id": self.kek_id,
                "kek_version": self.kek_version,
                "v": self.v,
            }
        )


def _cjson(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _aad(prefix: bytes, tenant_id: str, subject_id: str, object_key: str, version: int) -> bytes:
    binding = _cjson(
        {
            "object_key": object_key,
            "subject_id": subject_id,
            "tenant_id": tenant_id,
            "version": int(version),
        }
    )
    return prefix + b"\x00" + binding


def parse_header(blob: bytes) -> tuple[EnvelopeHeader, bytes, bytes, bytes]:
    """Split an envelope into (header, header prefix bytes, nonce, ciphertext+tag)."""
    if len(blob) < 6 or blob[:4] != MAGIC:
        raise EnvelopeFormatError("not an NFE1 envelope")
    (hlen,) = struct.unpack(">H", blob[4:6])
    if hlen == 0 or hlen > MAX_HEADER_LEN or len(blob) < 6 + hlen + NONCE_LEN + TAG_LEN:
        raise EnvelopeFormatError("envelope header length out of range")
    raw = blob[6 : 6 + hlen]
    try:
        h = json.loads(raw)
        header = EnvelopeHeader(
            alg=str(h["alg"]),
            kek_id=str(h["kek_id"]),
            kek_version=int(h["kek_version"]),
            dek_version=int(h["dek_version"]),
            v=int(h["v"]),
        )
    except (ValueError, KeyError, TypeError) as e:
        raise EnvelopeFormatError("envelope header is not valid") from e
    if header.v != FORMAT_VERSION:
        raise EnvelopeFormatError(f"unsupported envelope format v{header.v}")
    if header.alg not in ALGORITHMS:
        raise EnvelopeFormatError(f"unsupported algorithm {header.alg!r}")
    body = blob[6 + hlen :]
    return header, blob[: 6 + hlen], body[:NONCE_LEN], body[NONCE_LEN:]


def default_kek_id(tenant_id: str) -> str:
    return f"nf/tenant/{tenant_id}"


class Keyring:
    """Envelope encryption with one KMS key per tenant and one DEK per subject (+ DEK versions)."""

    def __init__(
        self,
        kms: Kms,
        keystore: KeyStore,
        *,
        kek_id_for: Callable[[str], str] = default_kek_id,
        alg: str = DEFAULT_ALG,
        max_encryptions_per_dek: int = MAX_ENCRYPTIONS_PER_DEK,
        cache_deks: bool = True,
    ) -> None:
        if alg not in ALGORITHMS:
            raise KeyringError(f"unsupported algorithm {alg!r}")
        self._kms = kms
        self._ks = keystore
        self._kek_id_for = kek_id_for
        self._alg = alg
        self._max = max_encryptions_per_dek
        self._cache_enabled = cache_deks
        self._cache: dict[tuple[str, str, int], bytes] = {}
        self._lock = threading.RLock()

    def __repr__(self) -> str:
        return f"Keyring(alg={self._alg!r}, cached_deks={len(self._cache)})"

    @property
    def kms(self) -> Kms:
        """The KMS holding the tenant KEKs (startup checks refuse an in-memory one in prod)."""
        return self._kms

    # -- for objects that belong to no single subject (m5: group averages, models), which carry
    # their own KMS-wrapped data key under the same tenant KEK
    def new_data_key(self, tenant_id: str, context: dict[str, str]) -> tuple[bytes, bytes, str]:
        """(plaintext DEK, wrapped DEK, kek_id) under the tenant KEK, bound to ``context``."""
        kek_id = self._kek_id_for(tenant_id)
        create = getattr(self._kms, "create_key", None)
        if create is not None:
            create(kek_id)
        try:
            pt, wrapped = self._kms.generate_data_key(kek_id, {"tenant_id": tenant_id, **context})
        except KmsError as e:
            raise SubjectKeyUnavailable(f"KMS refused a data key: {e}") from e
        return pt, wrapped, kek_id

    def unwrap_data_key(
        self, tenant_id: str, kek_id: str, wrapped: bytes, context: dict[str, str]
    ) -> bytes:
        try:
            return self._kms.decrypt(kek_id, wrapped, {"tenant_id": tenant_id, **context})
        except KmsError as e:
            raise SubjectKeyUnavailable(f"KMS could not unwrap the data key: {e}") from e

    # -- DEK lifecycle
    @staticmethod
    def _context(tenant_id: str, subject_id: str) -> dict[str, str]:
        return {"tenant_id": tenant_id, "subject_id": subject_id}

    def _kek_version(self, kek_id: str) -> int:
        cv = getattr(self._kms, "current_version", None)
        return int(cv(kek_id)) if cv else 1

    def _new_dek(
        self, tenant_id: str, subject_id: str, dek_version: int
    ) -> tuple[WrappedDek, bytes]:
        kek_id = self._kek_id_for(tenant_id)
        create = getattr(self._kms, "create_key", None)
        if create is not None:
            create(kek_id)
        try:
            pt, wrapped = self._kms.generate_data_key(kek_id, self._context(tenant_id, subject_id))
        except KmsError as e:
            raise SubjectKeyUnavailable(f"KMS refused a data key: {e}") from e
        rec = WrappedDek(
            tenant_id=tenant_id,
            subject_id=subject_id,
            dek_version=dek_version,
            kek_id=kek_id,
            kek_version=self._kek_version(kek_id),
            wrapped=wrapped,
            alg=self._alg,
        )
        self._ks.put_wrapped(rec)
        log.info("subject dek created", extra={"tenant_id": tenant_id, "dek_version": dek_version})
        return rec, pt

    def _unwrap(self, rec: WrappedDek) -> bytes:
        ck = (rec.tenant_id, rec.subject_id, rec.dek_version)
        if self._cache_enabled and ck in self._cache:
            return self._cache[ck]
        try:
            pt = self._kms.decrypt(
                rec.kek_id, rec.wrapped, self._context(rec.tenant_id, rec.subject_id)
            )
        except KmsError as e:
            raise SubjectKeyUnavailable(f"KMS could not unwrap the subject key: {e}") from e
        if self._cache_enabled:
            self._cache[ck] = pt
        return pt

    def _active(self, tenant_id: str, subject_id: str) -> tuple[WrappedDek, bytes]:
        rec = self._ks.get_wrapped(tenant_id, subject_id)
        if rec is None:
            if is_shredded(self._ks, tenant_id, subject_id):
                # SEC-034a: a shredded subject is tombstoned; no new DEK is ever minted for it.
                raise SubjectKeyUnavailable("subject is crypto-shredded; no new key is issued")
            existing = self._ks.list_wrapped(tenant_id, subject_id)
            next_v = max((r.dek_version for r in existing), default=0) + 1
            return self._new_dek(tenant_id, subject_id, next_v)
        if rec.encryption_count >= self._max:
            self._ks.put_wrapped(replace(rec, state="retired"))
            log.info(
                "subject dek retired (encryption limit)",
                extra={"tenant_id": tenant_id, "dek_version": rec.dek_version},
            )
            return self._new_dek(tenant_id, subject_id, rec.dek_version + 1)
        return rec, self._unwrap(rec)

    def is_shredded(self, tenant_id: str, subject_id: str) -> bool:
        """SEC-034a: is the subject tombstoned? (Asks the KeyStore, never the cache.)"""
        return is_shredded(self._ks, tenant_id, subject_id)

    # -- public API (M2-CONTRACTS §3)
    def encrypt(
        self, tenant_id: str, subject_id: str, object_key: str, version: int, plaintext: bytes
    ) -> bytes:
        _check_ids(tenant_id, subject_id, object_key)
        with self._lock:
            rec, dek = self._active(tenant_id, subject_id)
            self._ks.bump_count(tenant_id, subject_id, rec.dek_version)
        header = EnvelopeHeader(
            alg=rec.alg, kek_id=rec.kek_id, kek_version=rec.kek_version, dek_version=rec.dek_version
        ).encode()
        prefix = MAGIC + struct.pack(">H", len(header)) + header
        nonce = os.urandom(NONCE_LEN)
        ct = ALGORITHMS[rec.alg](dek).encrypt(
            nonce, bytes(plaintext), _aad(prefix, tenant_id, subject_id, object_key, version)
        )
        return prefix + nonce + ct

    def decrypt(
        self, tenant_id: str, subject_id: str, object_key: str, version: int, blob: bytes
    ) -> bytes:
        _check_ids(tenant_id, subject_id, object_key)
        header, prefix, nonce, ct = parse_header(bytes(blob))
        rec = self._ks.get_wrapped(tenant_id, subject_id, header.dek_version)
        if rec is None or rec.state == "shredded":
            raise SubjectKeyUnavailable("no key for this subject (shredded or never created)")
        dek = self._unwrap(rec)
        try:
            return ALGORITHMS[header.alg](dek).decrypt(
                nonce, ct, _aad(prefix, tenant_id, subject_id, object_key, version)
            )
        except InvalidTag as e:
            raise DecryptionError("authentication failed (wrong binding or tampered data)") from e

    def shred_subject(self, tenant_id: str, subject_id: str) -> int:
        """Crypto-shred: destroy every wrapped DEK of the subject. Returns the number destroyed."""
        with self._lock:
            n = self._ks.delete_subject(tenant_id, subject_id)
            for ck in [k for k in self._cache if k[0] == tenant_id and k[1] == subject_id]:
                del self._cache[ck]
        log.warning("subject keys shredded", extra={"tenant_id": tenant_id, "dek_count": n})
        return n

    def rotate_tenant_kek(self, tenant_id: str) -> int:
        """SEC-033: rotate the tenant KEK, re-wrap every DEK of the tenant (no data rewrite), then
        disable the old KEK version. Returns the number of DEKs re-wrapped."""
        if not isinstance(self._kms, RotatingKms):
            raise KeyringError("this KMS rotates keys itself (e.g. AWS automatic rotation)")
        kek_id = self._kek_id_for(tenant_id)
        with self._lock:
            old = self._kms.current_version(kek_id)
            new = self._kms.rotate_key(kek_id)
            n = 0
            for rec in self._ks.list_tenant(tenant_id):
                wrapped = self._kms.re_encrypt(
                    kek_id, rec.wrapped, self._context(rec.tenant_id, rec.subject_id)
                )
                self._ks.put_wrapped(replace(rec, wrapped=wrapped, kek_version=new))
                n += 1
            self._kms.disable_key_version(kek_id, old)
            self._cache = {k: v for k, v in self._cache.items() if k[0] != tenant_id}
        log.info(
            "tenant kek rotated", extra={"tenant_id": tenant_id, "kek_version": new, "rewrapped": n}
        )
        return n


def _check_ids(tenant_id: str, subject_id: str, object_key: str) -> None:
    for name, v in (
        ("tenant_id", tenant_id),
        ("subject_id", subject_id),
        ("object_key", object_key),
    ):
        if not isinstance(v, str) or not v:
            raise KeyringError(f"{name} must be a non-empty string")
