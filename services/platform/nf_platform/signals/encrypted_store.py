"""A zarr v3 `Store` that keeps every key (metadata and chunks) as an NFE1 envelope in an
`ObjectStore`, sealed with the subject's DEK through the `Keyring` (BUILD-GUIDE 2.3 + 2.4).

One store instance is bound to (tenant_id, subject_id, prefix): Zarr data at rest is ciphertext,
and crypto-shredding the subject makes the arrays unreadable exactly like any other object.
Partial reads decrypt the whole object first (AEAD cannot authenticate a byte range), so the
layout avoids sharding and keeps chunks small enough to fetch whole.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable
from typing import Any

from zarr.abc.store import (
    ByteRequest,
    OffsetByteRequest,
    RangeByteRequest,
    Store,
    SuffixByteRequest,
)
from zarr.core.buffer import Buffer, BufferPrototype
from zarr.core.buffer.core import default_buffer_prototype

from nf_platform.storage.keyring import Keyring
from nf_platform.storage.objects import ObjectNotFound, ObjectStore

BUCKET = "zarr"


def _slice(data: bytes, byte_range: ByteRequest | None) -> bytes:
    if byte_range is None:
        return data
    if isinstance(byte_range, RangeByteRequest):
        return data[byte_range.start : byte_range.end]
    if isinstance(byte_range, OffsetByteRequest):
        return data[byte_range.offset :]
    if isinstance(byte_range, SuffixByteRequest):
        return data[-byte_range.suffix :] if byte_range.suffix else b""
    raise TypeError(f"unsupported byte range {byte_range!r}")


class EncryptedZarrStore(Store):
    supports_writes: bool = True
    supports_deletes: bool = True
    supports_listing: bool = True

    def __init__(
        self,
        objects: ObjectStore,
        keyring: Keyring,
        tenant_id: str,
        subject_id: str,
        prefix: str,
        *,
        object_version: int = 1,
        read_only: bool = False,
    ) -> None:
        super().__init__(read_only=read_only)
        if not prefix or prefix.startswith("/") or prefix.endswith("/"):
            raise ValueError("prefix must be a non-empty relative path without edge slashes")
        self._objects = objects
        self._keyring = keyring
        self._tenant = tenant_id
        self._subject = subject_id
        self._prefix = prefix
        self._version = object_version

    # -- helpers
    def _okey(self, key: str) -> str:
        return f"{self._prefix}/{key}"

    def _aad_key(self, key: str) -> str:
        return f"{BUCKET}/{self._okey(key)}"

    def _read(self, key: str) -> bytes | None:
        try:
            blob = self._objects.get(BUCKET, self._okey(key))
        except ObjectNotFound:
            return None
        return self._keyring.decrypt(
            self._tenant, self._subject, self._aad_key(key), self._version, blob
        )

    def _keys(self) -> list[str]:
        base = self._prefix + "/"
        return [k[len(base) :] for k in self._objects.list(BUCKET, base)]

    # -- Store API
    def with_read_only(self, read_only: bool = False) -> EncryptedZarrStore:
        return type(self)(
            self._objects,
            self._keyring,
            self._tenant,
            self._subject,
            self._prefix,
            object_version=self._version,
            read_only=read_only,
        )

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, EncryptedZarrStore)
            and other._objects is self._objects
            and other._prefix == self._prefix
            and other._tenant == self._tenant
            and other._subject == self._subject
            and other.read_only == self.read_only
        )

    def __repr__(self) -> str:
        return f"EncryptedZarrStore(prefix={self._prefix!r})"

    async def get(
        self,
        key: str,
        prototype: BufferPrototype | None = None,
        byte_range: ByteRequest | None = None,
    ) -> Buffer | None:
        if prototype is None:
            prototype = default_buffer_prototype()
        data = self._read(key)
        if data is None:
            return None
        return prototype.buffer.from_bytes(_slice(data, byte_range))

    async def get_partial_values(
        self,
        prototype: BufferPrototype,
        key_ranges: Iterable[tuple[str, ByteRequest | None]],
    ) -> list[Buffer | None]:
        return [await self.get(k, prototype, r) for k, r in key_ranges]

    async def exists(self, key: str) -> bool:
        exists = getattr(self._objects, "exists", None)
        if exists is not None:
            return bool(exists(BUCKET, self._okey(key)))
        try:
            self._objects.get(BUCKET, self._okey(key))
        except ObjectNotFound:
            return False
        return True

    async def set(self, key: str, value: Buffer, byte_range: Any = None) -> None:
        self._check_writable()
        if byte_range is not None:
            raise NotImplementedError("partial writes are not supported on encrypted objects")
        blob = self._keyring.encrypt(
            self._tenant, self._subject, self._aad_key(key), self._version, value.to_bytes()
        )
        self._objects.put(BUCKET, self._okey(key), blob)

    async def set_if_not_exists(self, key: str, value: Buffer) -> None:
        if not await self.exists(key):
            await self.set(key, value)

    async def delete(self, key: str) -> None:
        self._check_writable()
        self._objects.delete(BUCKET, self._okey(key))

    async def list(self) -> AsyncIterator[str]:
        for k in self._keys():
            yield k

    async def list_prefix(self, prefix: str) -> AsyncIterator[str]:
        for k in self._keys():
            if k.startswith(prefix):
                yield k

    async def list_dir(self, prefix: str) -> AsyncIterator[str]:
        prefix = prefix.rstrip("/")
        seen: set[str] = set()
        for k in self._keys():
            if prefix:
                if not k.startswith(prefix + "/"):
                    continue
                rest = k[len(prefix) + 1 :]
            else:
                rest = k
            head = rest.split("/", 1)[0]
            if head and head not in seen:
                seen.add(head)
                yield head
