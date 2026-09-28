"""ObjectStore protocol and implementations (M2-CONTRACTS §3).

- `LocalObjectStore`: filesystem, used by tests and local dev.
- `S3ObjectStore`: boto3 against S3 or MinIO. Unit-tested with moto; the MinIO run is CI-only
  (`@pytest.mark.integration`).

Objects handed to a store are expected to be ciphertext already (see `keyring.Keyring`); the
store itself never sees keys. The `audit` bucket is write-once (WORM): in S3 it is an Object Lock
bucket; `LocalObjectStore` refuses overwrites and deletes there so the behaviour is testable.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

BUCKETS = ("raw", "zarr", "artifacts", "models", "audit")
WORM_BUCKETS = frozenset({"audit"})
MAX_KEY_LEN = 1024
_KEY_RE = re.compile(r"^[A-Za-z0-9._\-=/+]+$")


class ObjectStoreError(Exception):
    """Base class for object-store errors."""


class ObjectNotFound(ObjectStoreError, KeyError):
    def __str__(self) -> str:  # KeyError quotes its message; keep it readable
        return str(self.args[0]) if self.args else "object not found"


class InvalidObjectKey(ObjectStoreError, ValueError):
    pass


class WormViolation(ObjectStoreError):
    """Overwrite or delete attempted on a write-once (object-lock) bucket."""


def validate_key(bucket: str, key: str) -> None:
    """Reject unknown buckets and keys that could escape a prefix (path traversal)."""
    if bucket not in BUCKETS:
        raise InvalidObjectKey(f"unknown bucket {bucket!r}; expected one of {BUCKETS}")
    if not key or len(key) > MAX_KEY_LEN:
        raise InvalidObjectKey("object key must be 1..1024 characters")
    if not _KEY_RE.match(key):
        raise InvalidObjectKey("object key contains characters outside [A-Za-z0-9._-=/+]")
    if key.startswith("/") or key.endswith("/") or "//" in key:
        raise InvalidObjectKey("object key must not start/end with '/' or contain '//'")
    if any(part in (".", "..") for part in key.split("/")):
        raise InvalidObjectKey("object key must not contain '.' or '..' segments")


@runtime_checkable
class ObjectStore(Protocol):
    def put(
        self, bucket: str, key: str, data: bytes, *, metadata: dict[str, str] | None = None
    ) -> None: ...

    def get(self, bucket: str, key: str) -> bytes: ...

    def delete(self, bucket: str, key: str) -> None: ...

    def list(self, bucket: str, prefix: str) -> Iterator[str]: ...


class LocalObjectStore:
    """Filesystem store: `<root>/<bucket>/<key>`; metadata in `<root>/_meta/<bucket>/<key>.json`.

    Writes are atomic (temp file + os.replace). Not for production use.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        for b in BUCKETS:
            (self.root / b).mkdir(parents=True, exist_ok=True)

    def _path(self, bucket: str, key: str) -> Path:
        validate_key(bucket, key)
        return self.root / bucket / Path(*key.split("/"))

    def _meta_path(self, bucket: str, key: str) -> Path:
        return (
            self.root
            / "_meta"
            / bucket
            / Path(*key.split("/")).with_name(key.rsplit("/", 1)[-1] + ".json")
        )

    def put(
        self, bucket: str, key: str, data: bytes, *, metadata: dict[str, str] | None = None
    ) -> None:
        path = self._path(bucket, key)
        if bucket in WORM_BUCKETS and path.exists():
            raise WormViolation(f"{bucket}/{key} is write-once")
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(path, bytes(data))
        if metadata:
            mp = self._meta_path(bucket, key)
            mp.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(mp, json.dumps(metadata, sort_keys=True).encode())

    def get(self, bucket: str, key: str) -> bytes:
        path = self._path(bucket, key)
        try:
            return path.read_bytes()
        except (FileNotFoundError, IsADirectoryError, PermissionError) as e:
            raise ObjectNotFound(f"{bucket}/{key}") from e

    def get_metadata(self, bucket: str, key: str) -> dict[str, str]:
        if not self.exists(bucket, key):
            raise ObjectNotFound(f"{bucket}/{key}")
        mp = self._meta_path(bucket, key)
        return json.loads(mp.read_text()) if mp.exists() else {}

    def exists(self, bucket: str, key: str) -> bool:
        return self._path(bucket, key).is_file()

    def delete(self, bucket: str, key: str) -> None:
        path = self._path(bucket, key)
        if bucket in WORM_BUCKETS:
            raise WormViolation(f"{bucket}/{key} is write-once")
        path.unlink(missing_ok=True)
        self._meta_path(bucket, key).unlink(missing_ok=True)

    def list(self, bucket: str, prefix: str) -> Iterator[str]:
        if bucket not in BUCKETS:
            raise InvalidObjectKey(f"unknown bucket {bucket!r}")
        base = self.root / bucket
        keys = []
        for dirpath, _dirs, files in os.walk(base):
            for f in files:
                if f.endswith(".nftmp"):
                    continue
                rel = (Path(dirpath) / f).relative_to(base).as_posix()
                if rel.startswith(prefix):
                    keys.append(rel)
        yield from sorted(keys)


def _atomic_write(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".nftmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


class S3ObjectStore:
    """S3 / MinIO implementation (boto3).

    `bucket_names` maps the logical buckets (`raw`, `zarr`, ...) to physical bucket names, e.g.
    `{"raw": "nf-prod-eu-raw", ...}`. Versioning on every bucket and Object Lock (COMPLIANCE) on
    `audit` are bucket configuration (SEC-121); `ensure_buckets()` sets them for tests/dev.
    """

    def __init__(
        self,
        client: Any,
        bucket_names: dict[str, str] | None = None,
        *,
        audit_retention_days: int = 3650,
    ) -> None:
        self._s3 = client
        self._names = {b: (bucket_names or {}).get(b, b) for b in BUCKETS}
        self._audit_retention = timedelta(days=audit_retention_days)

    def ensure_buckets(self) -> None:
        existing = {b["Name"] for b in self._s3.list_buckets().get("Buckets", [])}
        for logical, name in self._names.items():
            if name in existing:
                continue
            if logical in WORM_BUCKETS:
                self._s3.create_bucket(Bucket=name, ObjectLockEnabledForBucket=True)
            else:
                self._s3.create_bucket(Bucket=name)
            self._s3.put_bucket_versioning(
                Bucket=name, VersioningConfiguration={"Status": "Enabled"}
            )

    def put(
        self, bucket: str, key: str, data: bytes, *, metadata: dict[str, str] | None = None
    ) -> None:
        validate_key(bucket, key)
        kwargs: dict[str, Any] = {
            "Bucket": self._names[bucket],
            "Key": key,
            "Body": bytes(data),
            "Metadata": dict(metadata or {}),
        }
        if bucket in WORM_BUCKETS:
            kwargs["ObjectLockMode"] = "COMPLIANCE"
            kwargs["ObjectLockRetainUntilDate"] = datetime.now(UTC) + self._audit_retention
        self._s3.put_object(**kwargs)

    def get(self, bucket: str, key: str) -> bytes:
        validate_key(bucket, key)
        try:
            resp = self._s3.get_object(Bucket=self._names[bucket], Key=key)
        except self._s3.exceptions.NoSuchKey as e:
            raise ObjectNotFound(f"{bucket}/{key}") from e
        return resp["Body"].read()

    def get_metadata(self, bucket: str, key: str) -> dict[str, str]:
        validate_key(bucket, key)
        try:
            resp = self._s3.head_object(Bucket=self._names[bucket], Key=key)
        except self._s3.exceptions.ClientError as e:
            raise ObjectNotFound(f"{bucket}/{key}") from e
        return dict(resp.get("Metadata", {}))

    def exists(self, bucket: str, key: str) -> bool:
        try:
            self.get_metadata(bucket, key)
        except ObjectNotFound:
            return False
        return True

    def delete(self, bucket: str, key: str) -> None:
        validate_key(bucket, key)
        if bucket in WORM_BUCKETS:
            raise WormViolation(f"{bucket}/{key} is write-once")
        self._s3.delete_object(Bucket=self._names[bucket], Key=key)

    def list(self, bucket: str, prefix: str) -> Iterator[str]:
        if bucket not in BUCKETS:
            raise InvalidObjectKey(f"unknown bucket {bucket!r}")
        pager = self._s3.get_paginator("list_objects_v2")
        for page in pager.paginate(Bucket=self._names[bucket], Prefix=prefix):
            for obj in page.get("Contents", []):
                yield obj["Key"]
