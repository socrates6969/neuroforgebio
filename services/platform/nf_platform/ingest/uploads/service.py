"""Upload sessions (BUILD-GUIDE 2.6; SEC-042, SEC-071).

Lifecycle: ``open`` (parts arrive, any part may be re-sent: resumable) → ``complete`` with the
client's SHA-256 → the server hashes the reassembled bytes itself; equal → ``uploaded`` (queued for
the ingest worker, raw original now immutable), different → ``rejected`` (parts deleted). The
worker moves it to ``processing`` → ``done``/``failed``.

Only the creator writes to an upload; the creator and the tenant's data managers can read its
status. Everything runs inside the caller's tenant session (RLS + app filter).
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from nf_platform.auth.authorize import effective_roles
from nf_platform.config import Settings
from nf_platform.db import models as m
from nf_platform.db.context import Principal
from nf_platform.ingest.errors import IngestError, conflict, invalid, too_large
from nf_platform.ingest.recording_store import upload_prefix
from nf_platform.ingest.uploads.backends import (
    LocalPartBackend,
    PartBackend,
    PartTarget,
    S3PartBackend,
    manifest_key,
    part_key,
)
from nf_platform.storage.keyring import DecryptionError, SubjectKeyUnavailable, parse_header
from nf_platform.storage.objects import ObjectNotFound
from nf_platform.storage.runtime import Storage

ALLOWED_EXT = {".edf": "edf", ".bdf": "bdf", ".xdf": "xdf", ".nwb": "nwb", ".zip": "zip"}
FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_PARTS = 10_000
UPLOAD_MANAGERS = frozenset({"owner", "admin", "data-steward"})
MANIFEST_SCHEMA = "nf.upload-manifest/v1"


@dataclass(frozen=True)
class UploadRequest:
    session_id: uuid.UUID
    filename: str
    size_bytes: int
    part_size: int | None = None
    synthetic: bool = False


def _tid(p: Principal) -> uuid.UUID:
    return uuid.UUID(p.tenant_id)


def n_parts(upload: m.Upload) -> int:
    return math.ceil(upload.size_bytes / upload.part_size)


def expected_part_size(upload: m.Upload, n: int) -> int:
    last = n_parts(upload)
    if n < last:
        return int(upload.part_size)
    return int(upload.size_bytes - (last - 1) * upload.part_size)


def _require_synthetic(s: Session, p: Principal, synthetic: bool, settings: Settings) -> None:
    """SEC-071: dev/staging, and any tenant flagged synthetic_only, accept synthetic data only."""
    tenant = s.get(m.Tenant, _tid(p))
    synthetic_only = settings.environment != "prod" or tenant is None or tenant.synthetic_only
    if synthetic_only and not synthetic:
        raise IngestError(
            403,
            "synthetic-only",
            "Forbidden",
            "this environment/tenant accepts only synthetic data: set synthetic=true for "
            "synthetic or licence-checked public fixtures",
        )


def require_synthetic(s: Session, p: Principal, synthetic: bool, settings: Settings) -> None:
    _require_synthetic(s, p, synthetic, settings)


def create(
    s: Session,
    p: Principal,
    dataset_id: uuid.UUID,
    req: UploadRequest,
    settings: Settings,
    backend: PartBackend,
) -> m.Upload:
    ds = s.scalar(select(m.Dataset).where(m.Dataset.id == dataset_id))
    if ds is None:
        raise IngestError(404, "not-found", "Not Found", "dataset not found")
    sess = s.scalar(select(m.Session_).where(m.Session_.id == req.session_id))
    subj = s.scalar(select(m.Subject).where(m.Subject.id == sess.subject_id)) if sess else None
    if sess is None or subj is None or subj.dataset_id != ds.id:
        raise IngestError(404, "not-found", "Not Found", "session not found in this dataset")
    _require_synthetic(s, p, req.synthetic, settings)
    if not FILENAME_RE.match(req.filename):
        raise invalid("filename must be a plain name of [A-Za-z0-9._-] (no paths)")
    ext = "." + req.filename.rsplit(".", 1)[-1].lower() if "." in req.filename else ""
    if ext not in ALLOWED_EXT:
        raise invalid(f"file type not accepted; allowed: {sorted(ALLOWED_EXT)}")
    if req.size_bytes < 1:
        raise invalid("size_bytes must be positive")
    if req.size_bytes > settings.upload_max_bytes:
        raise too_large("upload exceeds the size limit", max_bytes=settings.upload_max_bytes)
    part_size = req.part_size or max(settings.upload_part_min, 8 * 1024 * 1024)
    part_size = min(part_size, settings.upload_part_max)
    if not settings.upload_part_min <= part_size <= settings.upload_part_max:
        raise invalid(
            "part_size out of range",
            min_part_size=settings.upload_part_min,
            max_part_size=settings.upload_part_max,
        )
    if math.ceil(req.size_bytes / part_size) > MAX_PARTS:
        raise invalid("too many parts; use a larger part_size")
    uid = uuid.uuid4()
    prefix = upload_prefix(p.tenant_id, str(subj.id), str(uid))
    row = m.Upload(
        id=uid,
        tenant_id=_tid(p),
        dataset_id=ds.id,
        session_id=sess.id,
        subject_id=subj.id,
        filename=req.filename,
        size_bytes=req.size_bytes,
        part_size=part_size,
        backend=backend.name,
        synthetic=req.synthetic,
        raw_prefix=prefix,
        created_by=p.id,
    )
    row.backend_ref = backend.start(str(uid), prefix)
    s.add(row)
    s.flush()
    s.refresh(row)
    return row


def get_visible(s: Session, p: Principal, upload_id: uuid.UUID, *, write: bool) -> m.Upload:
    row = s.scalar(select(m.Upload).where(m.Upload.id == upload_id))
    managers = bool(effective_roles(p) & UPLOAD_MANAGERS)
    if row is None or (row.created_by != p.id and (write or not managers)):
        raise IngestError(404, "not-found", "Not Found", "upload not found")
    return row


def received_parts(s: Session, upload: m.Upload) -> list[m.UploadPart]:
    q = select(m.UploadPart).where(m.UploadPart.upload_id == upload.id)
    return list(s.scalars(q.order_by(m.UploadPart.part_number)))


def targets(upload: m.Upload, backend: PartBackend, s: Session) -> list[PartTarget]:
    if upload.state != "open":
        return []
    have = {r.part_number for r in received_parts(s, upload)}
    if isinstance(backend, S3PartBackend) and upload.backend == "s3" and upload.backend_ref:
        # parts go straight to S3: ask S3 which ones it already holds (resumable)
        have |= {
            int(p["PartNumber"])
            for p in backend.uploaded_parts(upload.raw_prefix, upload.backend_ref)
            if int(p["Size"]) == expected_part_size(upload, int(p["PartNumber"]))
        }
    missing = [n for n in range(1, n_parts(upload) + 1) if n not in have]
    return backend.targets(str(upload.id), upload.raw_prefix, upload.backend_ref, missing)


def put_part(
    s: Session, storage: Storage, p: Principal, upload_id: uuid.UUID, n: int, data: bytes
) -> m.UploadPart:
    """Local shim for a pre-signed part PUT: seal the part under the subject DEK and record it.
    Re-sending a part while the upload is open replaces it (resumable, idempotent)."""
    up = get_visible(s, p, upload_id, write=True)
    if up.backend != "local":
        raise conflict("parts of this upload go to the pre-signed object-store URLs")
    if up.state != "open":
        raise conflict("upload is no longer open; its raw original is immutable")
    if not 1 <= n <= n_parts(up):
        raise invalid(f"part_number must be in 1..{n_parts(up)}")
    want = expected_part_size(up, n)
    if len(data) != want:
        raise invalid(f"part {n} must be exactly {want} bytes", expected_bytes=want)
    key = part_key(up.raw_prefix, n)
    blob = storage.keyring.encrypt(p.tenant_id, str(up.subject_id), f"raw/{key}", 1, data)
    storage.objects.put("raw", key, blob, metadata={"nf-enc": "NFE1", "nf-version": "1"})
    digest = hashlib.sha256(data).hexdigest()
    row = s.get(m.UploadPart, (up.id, n))
    if row is None:
        row = m.UploadPart(tenant_id=up.tenant_id, upload_id=up.id, part_number=n)
        s.add(row)
    row.size_bytes = len(data)
    row.sha256 = digest
    row.created_at = datetime.now(UTC)
    s.flush()
    return row


def _stored_object(up: m.Upload, key: str, plain: bytes, blob: bytes) -> m.StoredObject:
    h, *_ = parse_header(blob)
    return m.StoredObject(
        tenant_id=up.tenant_id,
        subject_id=up.subject_id,
        bucket="raw",
        object_key=key,
        object_version=1,
        sha256=hashlib.sha256(plain).hexdigest(),
        size_bytes=len(plain),
        ciphertext_size=len(blob),
        dek_version=h.dek_version,
        kek_id=h.kek_id,
        kek_version=h.kek_version,
        alg=h.alg,
        content_type="application/octet-stream",
    )


def _read_part(storage: Storage, up: m.Upload, n: int) -> tuple[bytes, bytes]:
    key = part_key(up.raw_prefix, n)
    blob = storage.objects.get("raw", key)
    plain = storage.keyring.decrypt(str(up.tenant_id), str(up.subject_id), f"raw/{key}", 1, blob)
    return plain, blob


def iter_original(
    storage: Storage,
    tenant_id: str,
    subject_id: str,
    raw_prefix: str,
    size_bytes: int,
    part_size: int,
) -> Iterator[bytes]:
    """The raw original's bytes, part by part (decrypted; never all in memory)."""
    for n in range(1, math.ceil(size_bytes / part_size) + 1):
        key = part_key(raw_prefix, n)
        blob = storage.objects.get("raw", key)
        yield storage.keyring.decrypt(str(tenant_id), str(subject_id), f"raw/{key}", 1, blob)


def _discard(s: Session, storage: Storage, up: m.Upload, backend: PartBackend) -> None:
    for n in range(1, n_parts(up) + 1):
        storage.objects.delete("raw", part_key(up.raw_prefix, n))
    s.execute(delete(m.UploadPart).where(m.UploadPart.upload_id == up.id))
    if isinstance(backend, S3PartBackend):
        backend.discard(up.raw_prefix, up.backend_ref)


def _seal_from_s3(s: Session, storage: Storage, up: m.Upload, backend: S3PartBackend) -> None:
    """Complete the S3 multipart upload, then re-seal the staged object as NFE1 parts."""
    backend.complete(up.raw_prefix, str(up.backend_ref))
    total = 0
    for n, block in enumerate(backend.read_staged(up.raw_prefix, int(up.part_size)), start=1):
        total += len(block)
        if n > n_parts(up) or total > up.size_bytes:
            break
        key = part_key(up.raw_prefix, n)
        blob = storage.keyring.encrypt(
            str(up.tenant_id), str(up.subject_id), f"raw/{key}", 1, block
        )
        storage.objects.put("raw", key, blob, metadata={"nf-enc": "NFE1", "nf-version": "1"})
        s.merge(
            m.UploadPart(
                tenant_id=up.tenant_id,
                upload_id=up.id,
                part_number=n,
                size_bytes=len(block),
                sha256=hashlib.sha256(block).hexdigest(),
            )
        )
    s.flush()


def complete(
    s: Session,
    storage: Storage,
    p: Principal,
    upload_id: uuid.UUID,
    client_sha256: str,
    backend: PartBackend,
) -> m.Upload:
    """Verify the SHA-256 server-side (SEC-042). Returns the upload in state ``uploaded``; raises
    ``IngestError`` 422 ``hash-mismatch`` (upload rejected) or 409 (missing parts / not open)."""
    sha = client_sha256.strip().lower()
    if not SHA256_RE.match(sha):
        raise invalid("sha256 must be 64 hex characters")
    up = get_visible(s, p, upload_id, write=True)
    if up.state in ("uploaded", "processing", "done") and up.client_sha256 == sha:
        return up  # idempotent retry of a completed upload
    if up.state != "open":
        raise conflict(f"upload is {up.state}")
    if isinstance(backend, S3PartBackend) and up.backend == "s3":
        _seal_from_s3(s, storage, up, backend)
    parts = {r.part_number: r for r in received_parts(s, up)}
    missing = [
        n
        for n in range(1, n_parts(up) + 1)
        if n not in parts or parts[n].size_bytes != expected_part_size(up, n)
    ]
    if missing:
        raise conflict("parts missing or incomplete", missing_parts=missing[:100])
    h = hashlib.sha256()
    objects: list[m.StoredObject] = []
    for n in range(1, n_parts(up) + 1):
        try:
            plain, blob = _read_part(storage, up, n)
        except (ObjectNotFound, DecryptionError, SubjectKeyUnavailable) as e:
            raise conflict(f"part {n} is unreadable; upload it again") from e
        if hashlib.sha256(plain).hexdigest() != parts[n].sha256:
            raise conflict(f"part {n} changed after upload; upload it again")
        h.update(plain)
        objects.append(_stored_object(up, part_key(up.raw_prefix, n), plain, blob))
    server_sha = h.hexdigest()
    up.client_sha256 = sha
    up.server_sha256 = server_sha
    up.completed_at = datetime.now(UTC)
    if server_sha != sha:
        up.state = "rejected"
        up.error = "sha256 mismatch"
        _discard(s, storage, up, backend)
        s.flush()
        return up
    manifest = json.dumps(
        {
            "schema": MANIFEST_SCHEMA,
            "upload_id": str(up.id),
            "filename": up.filename,
            "size_bytes": int(up.size_bytes),
            "part_size": int(up.part_size),
            "blob_id": f"blob:sha256:{server_sha}",
            "parts": [
                {"n": n, "size": parts[n].size_bytes, "sha256": parts[n].sha256}
                for n in sorted(parts)
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    mkey = manifest_key(up.raw_prefix)
    mblob = storage.keyring.encrypt(p.tenant_id, str(up.subject_id), f"raw/{mkey}", 1, manifest)
    storage.objects.put("raw", mkey, mblob, metadata={"nf-enc": "NFE1", "nf-version": "1"})
    objects.append(_stored_object(up, mkey, manifest, mblob))
    s.add_all(objects)
    if isinstance(backend, S3PartBackend) and up.backend == "s3":
        backend.discard(up.raw_prefix, None)  # plaintext staging object is gone
    up.state = "uploaded"
    s.flush()
    return up


def status(s: Session, up: m.Upload, backend: PartBackend) -> dict[str, Any]:
    got = received_parts(s, up)
    return {
        "id": up.id,
        "dataset_id": up.dataset_id,
        "session_id": up.session_id,
        "filename": up.filename,
        "size_bytes": up.size_bytes,
        "part_size": up.part_size,
        "n_parts": n_parts(up),
        "state": up.state,
        "synthetic": up.synthetic,
        "received_parts": [
            {"part_number": r.part_number, "size_bytes": r.size_bytes, "sha256": r.sha256}
            for r in got
        ],
        "parts": [t.__dict__ for t in targets(up, backend, s)],
        "server_sha256": up.server_sha256,
        "error": up.error,
        "recording_ids": list(up.recording_ids or []),
        "created_at": up.created_at,
        "completed_at": up.completed_at,
    }


def default_backend() -> PartBackend:
    return LocalPartBackend()
