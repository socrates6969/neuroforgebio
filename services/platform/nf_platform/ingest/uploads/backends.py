"""Where upload parts go (2.6).

- ``LocalPartBackend`` (dev, tests): the part "URL" is the platform's own route
  ``PUT /v1/uploads/{id}/parts/{n}`` (the signed-URL shim). The API encrypts each part with the
  subject's DEK before it reaches the object store, so plaintext never lands on disk.
- ``S3PartBackend`` (CI-only test against MinIO): a real S3 multipart upload with pre-signed
  ``UploadPart`` URLs. The client sends parts straight to S3 (server-side encryption at the bucket);
  on completion the platform streams the object once to hash it and re-seals it part by part under
  the subject's DEK (the same layout as the local backend), then deletes the staging object.

After completion both backends leave the same immutable raw original (SEC-042):
``raw/<raw_prefix>/part-00001 .. part-N`` (NFE1 envelopes) + ``raw/<raw_prefix>/manifest.json``.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

PART_KEY = "{prefix}/part-{n:05d}"
MANIFEST_KEY = "{prefix}/manifest.json"


def part_key(prefix: str, n: int) -> str:
    return PART_KEY.format(prefix=prefix, n=n)


def manifest_key(prefix: str) -> str:
    return MANIFEST_KEY.format(prefix=prefix)


@dataclass(frozen=True)
class PartTarget:
    part_number: int
    method: str
    url: str
    expires_at: datetime | None = None
    # "bearer": send the platform credential (local shim); "none": the URL is pre-signed.
    auth: str = "bearer"


class PartBackend(Protocol):
    name: str

    def start(self, upload_id: str, raw_prefix: str) -> str | None:
        """Begin a multipart upload; returns a backend reference (S3 UploadId) or None."""
        ...

    def targets(
        self, upload_id: str, raw_prefix: str, backend_ref: str | None, part_numbers: list[int]
    ) -> list[PartTarget]: ...


class LocalPartBackend:
    name = "local"

    def start(self, upload_id: str, raw_prefix: str) -> str | None:
        return None

    def targets(
        self, upload_id: str, raw_prefix: str, backend_ref: str | None, part_numbers: list[int]
    ) -> list[PartTarget]:
        return [PartTarget(n, "PUT", f"/v1/uploads/{upload_id}/parts/{n}") for n in part_numbers]


class S3PartBackend:
    """Pre-signed S3 multipart upload (CI-only test: MinIO in docker-compose.ci.yml)."""

    name = "s3"

    def __init__(
        self, client: Any, bucket: str, *, staging_prefix: str = "staging", ttl_s: int = 3600
    ) -> None:
        self._s3 = client
        self.bucket = bucket
        self.staging_prefix = staging_prefix
        self.ttl_s = ttl_s

    def staging_key(self, raw_prefix: str) -> str:
        return f"{self.staging_prefix}/{raw_prefix}/object"

    def start(self, upload_id: str, raw_prefix: str) -> str | None:
        resp = self._s3.create_multipart_upload(
            Bucket=self.bucket, Key=self.staging_key(raw_prefix), ServerSideEncryption="AES256"
        )
        return str(resp["UploadId"])

    def targets(
        self, upload_id: str, raw_prefix: str, backend_ref: str | None, part_numbers: list[int]
    ) -> list[PartTarget]:
        exp = datetime.now(UTC) + timedelta(seconds=self.ttl_s)
        out = []
        for n in part_numbers:
            url = self._s3.generate_presigned_url(
                "upload_part",
                Params={
                    "Bucket": self.bucket,
                    "Key": self.staging_key(raw_prefix),
                    "UploadId": backend_ref,
                    "PartNumber": n,
                },
                ExpiresIn=self.ttl_s,
            )
            out.append(PartTarget(n, "PUT", url, exp, auth="none"))
        return out

    def uploaded_parts(self, raw_prefix: str, backend_ref: str) -> list[dict[str, Any]]:
        parts: list[dict[str, Any]] = []
        kw: dict[str, Any] = {
            "Bucket": self.bucket,
            "Key": self.staging_key(raw_prefix),
            "UploadId": backend_ref,
        }
        while True:
            resp = self._s3.list_parts(**kw)
            parts += [
                {"PartNumber": p["PartNumber"], "ETag": p["ETag"], "Size": p["Size"]}
                for p in resp.get("Parts", [])
            ]
            if not resp.get("IsTruncated"):
                return parts
            kw["PartNumberMarker"] = resp["NextPartNumberMarker"]

    def complete(self, raw_prefix: str, backend_ref: str) -> None:
        parts = self.uploaded_parts(raw_prefix, backend_ref)
        self._s3.complete_multipart_upload(
            Bucket=self.bucket,
            Key=self.staging_key(raw_prefix),
            UploadId=backend_ref,
            MultipartUpload={
                "Parts": [{"PartNumber": p["PartNumber"], "ETag": p["ETag"]} for p in parts]
            },
        )

    def read_staged(self, raw_prefix: str, block: int) -> Iterator[bytes]:
        body = self._s3.get_object(Bucket=self.bucket, Key=self.staging_key(raw_prefix))["Body"]
        while True:
            b = body.read(block)
            if not b:
                return
            yield b

    def discard(self, raw_prefix: str, backend_ref: str | None) -> None:
        if backend_ref:
            # Already completed multipart uploads cannot be aborted: delete the object instead.
            with contextlib.suppress(Exception):
                self._s3.abort_multipart_upload(
                    Bucket=self.bucket, Key=self.staging_key(raw_prefix), UploadId=backend_ref
                )
        self._s3.delete_object(Bucket=self.bucket, Key=self.staging_key(raw_prefix))
