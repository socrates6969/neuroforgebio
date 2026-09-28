"""Metadata schema v1 (BUILD-GUIDE 2.1, BLUEPRINT §3.2).

Tenant ─< Project ─< Dataset ─< Subject ─< Session ─< Recording ─< Channel
                                                     Recording ─< Segment
plus key/object metadata for storage (2.3, m2-data), API keys (2.2) and the audit log (2.8).

Every table except ``tenant`` carries ``tenant_id`` (``audit_batch``: ``tenant_scope``) so one RLS
policy shape covers all of them. Child → parent foreign keys are composite ``(tenant_id,
parent_id)``, so a row can never
point at a parent in another tenant. The DDL lives in the Alembic migrations; a test checks that
these models and the migrated schema do not drift apart.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Double,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Channel governance attributes (BLUEPRINT §3.2). Extending a list needs a migration (constraint
# change).
MODALITIES = (
    "EEG",
    "iEEG",
    "ECoG",
    "SEEG",
    "LFP",
    "spikes",
    "MEG",
    "EMG",
    "ENG",
    "EOG",
    "ECG",
    "fNIRS",
    "other",
)
NERVOUS_SYSTEMS = ("central", "peripheral", "unknown")
BUCKETS = ("raw", "zarr", "artifacts", "models", "audit")
KEY_STATES = ("active", "retired", "disabled")
DEK_STATES = ("active", "retired", "shredded")
RECORDING_STATES = ("active", "quarantined")
SEGMENT_QUALITY = ("ok", "suspect")
# 2.6 upload lifecycle: open (parts arriving) -> uploaded (hash verified, queued for the worker)
# -> processing -> done | failed; a hash/size mismatch at completion -> rejected.
UPLOAD_STATES = ("open", "uploaded", "processing", "done", "rejected", "failed")
STREAM_STATES = ("open", "closed")


def _in(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


def _tenant_fk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id", ondelete="RESTRICT"), nullable=False
    )


class TenantScoped:
    """Mixin: rows belong to exactly one tenant via ``tenant_id`` (RLS + app-level filter)."""

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id", ondelete="RESTRICT"), nullable=False
    )


class Tenant(Base):
    __tablename__ = "tenant"
    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()
    # SEC-071: a synthetic-only tenant accepts only uploads/streams that carry the synthetic marker.
    synthetic_only: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    # 5.7: the tenant holds PHI; its data may only be placed on BAA-listed services
    # (nf_platform.placement, infra/policy/phi-services.json).
    phi: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")


class Project(TenantScoped, Base):
    __tablename__ = "project"
    __table_args__ = (UniqueConstraint("tenant_id", "id", name="uq_project_tenant_id_id"),)
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()


class Dataset(TenantScoped, Base):
    __tablename__ = "dataset"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_dataset_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "project_id"],
            ["project.tenant_id", "project.id"],
            name="fk_dataset_project",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()


class Subject(TenantScoped, Base):
    """A pseudonymous participant. ``label`` is the study code, never a name (SEC-147: not
    logged)."""

    __tablename__ = "subject"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_subject_tenant_id_id"),
        UniqueConstraint("tenant_id", "dataset_id", "label", name="uq_subject_dataset_label"),
        ForeignKeyConstraint(
            ["tenant_id", "dataset_id"],
            ["dataset.tenant_id", "dataset.id"],
            name="fk_subject_dataset",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()


class Session_(TenantScoped, Base):
    """A recording session (named ``Session_`` to avoid clashing with the SQLAlchemy Session)."""

    __tablename__ = "session"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_session_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "subject_id"],
            ["subject.tenant_id", "subject.id"],
            name="fk_session_subject",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()


class Recording(TenantScoped, Base):
    __tablename__ = "recording"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_recording_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "session_id"],
            ["session.tenant_id", "session.id"],
            name="fk_recording_session",
            ondelete="RESTRICT",
        ),
        CheckConstraint(_in("state", RECORDING_STATES), name="state"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    source_format: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    duration_s: Mapped[float | None] = mapped_column(Double)
    # Where the canonical signal lives: "zarr:<prefix>#<group>" (bucket zarr, subject-keyed; 2.4).
    zarr_ref: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()


class Channel(TenantScoped, Base):
    """One channel with the governance attributes classification needs (BLUEPRINT §3.2)."""

    __tablename__ = "channel"
    __table_args__ = (
        UniqueConstraint("tenant_id", "recording_id", "index", name="uq_channel_recording_index"),
        ForeignKeyConstraint(
            ["tenant_id", "recording_id"],
            ["recording.tenant_id", "recording.id"],
            name="fk_channel_recording",
            ondelete="CASCADE",
        ),
        CheckConstraint(_in("modality", MODALITIES), name="modality"),
        CheckConstraint(_in("nervous_system", NERVOUS_SYSTEMS), name="nervous_system"),
        CheckConstraint("sampling_rate > 0", name="sampling_rate"),
        CheckConstraint('"index" >= 0', name="index"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    recording_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    modality: Mapped[str] = mapped_column(Text, nullable=False)
    nervous_system: Mapped[str] = mapped_column(Text, nullable=False, server_default="unknown")
    derived_from_non_neural: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    sampling_rate: Mapped[float] = mapped_column(Double, nullable=False)
    units: Mapped[str] = mapped_column(Text, nullable=False)
    device_ref: Mapped[str | None] = mapped_column(Text)


class Segment(TenantScoped, Base):
    """A time range of a recording, pointing at its Zarr array (2.4)."""

    __tablename__ = "segment"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "recording_id"],
            ["recording.tenant_id", "recording.id"],
            name="fk_segment_recording",
            ondelete="CASCADE",
        ),
        CheckConstraint("start_s >= 0 AND end_s > start_s", name="range"),
        CheckConstraint(_in("quality", SEGMENT_QUALITY), name="quality"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    recording_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    start_s: Mapped[float] = mapped_column(Double, nullable=False)
    end_s: Mapped[float] = mapped_column(Double, nullable=False)
    zarr_ref: Mapped[str | None] = mapped_column(Text)
    # SEC-041: stream sanity-check violations mark a segment 'suspect' (data kept, never dropped).
    quality: Mapped[str] = mapped_column(Text, nullable=False, server_default="ok")
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()


# ---------------------------------------------------------------- keys and objects (2.3, specified
# by m2-data)
class TenantKey(TenantScoped, Base):
    """One row per tenant KEK version (the KEK itself lives in KMS)."""

    __tablename__ = "tenant_key"
    __table_args__ = (CheckConstraint(_in("state", KEY_STATES), name="state"),)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id", ondelete="RESTRICT"), primary_key=True
    )
    kek_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    kek_id: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    created_at: Mapped[datetime] = _created_at()
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SubjectKey(TenantScoped, Base):
    """Wrapped per-subject data keys. ``wrapped_dek`` is KMS ciphertext, never the plaintext DEK.

    Crypto-shred either deletes the row or sets ``wrapped_dek`` NULL + ``state='shredded'``
    (tombstone).
    """

    __tablename__ = "subject_key"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "subject_id"],
            ["subject.tenant_id", "subject.id"],
            name="fk_subject_key_subject",
            ondelete="RESTRICT",
        ),
        CheckConstraint(_in("state", DEK_STATES), name="state"),
        CheckConstraint(
            "(state = 'shredded') OR (wrapped_dek IS NOT NULL)", name="wrapped_unless_shredded"
        ),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id", ondelete="RESTRICT"), primary_key=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    dek_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    kek_id: Mapped[str] = mapped_column(Text, nullable=False)
    kek_version: Mapped[int] = mapped_column(Integer, nullable=False)
    wrapped_dek: Mapped[bytes | None] = mapped_column(LargeBinary)
    alg: Mapped[str] = mapped_column(Text, nullable=False, server_default="AES-256-GCM")
    encryption_count: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    created_at: Mapped[datetime] = _created_at()
    shredded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StoredObject(TenantScoped, Base):
    """Metadata of one encrypted object in object storage. ``sha256`` is of the PLAINTEXT."""

    __tablename__ = "stored_object"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "bucket", "object_key", "object_version", name="uq_stored_object_key"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "subject_id"],
            ["subject.tenant_id", "subject.id"],
            name="fk_stored_object_subject",
            ondelete="RESTRICT",
        ),
        CheckConstraint(_in("bucket", BUCKETS), name="bucket"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    bucket: Mapped[str] = mapped_column(Text, nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    object_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ciphertext_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    dek_version: Mapped[int | None] = mapped_column(Integer)
    kek_id: Mapped[str | None] = mapped_column(Text)
    kek_version: Mapped[int | None] = mapped_column(Integer)
    alg: Mapped[str] = mapped_column(Text, nullable=False, server_default="AES-256-GCM")
    content_type: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()


# ---------------------------------------------------------------- auth (2.2)
class ApiKey(TenantScoped, Base):
    """Hashed API key (SEC-014). The secret is never stored: only HMAC-SHA-256(pepper, key)."""

    __tablename__ = "api_key"
    __table_args__ = (
        UniqueConstraint("public_id", name="uq_api_key_public_id"),
        CheckConstraint("octet_length(key_hash) = 32", name="key_hash_len"),
        CheckConstraint("expires_at > created_at", name="expiry"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    public_id: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    key_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    pepper_version: Mapped[str] = mapped_column(Text, nullable=False)
    roles: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    created_at: Mapped[datetime] = _created_at()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------- uploads, devices, streams (2.6,
# 2.7; m2-stream)
class Upload(TenantScoped, Base):
    """One upload session (2.6). Parts are envelope-encrypted objects in the ``raw`` bucket and are
    immutable once the upload is completed (SEC-042: the raw original is never rewritten)."""

    __tablename__ = "upload"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_upload_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "dataset_id"],
            ["dataset.tenant_id", "dataset.id"],
            name="fk_upload_dataset",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "session_id"],
            ["session.tenant_id", "session.id"],
            name="fk_upload_session",
            ondelete="RESTRICT",
        ),
        CheckConstraint(_in("state", UPLOAD_STATES), name="state"),
        CheckConstraint("size_bytes > 0 AND part_size > 0", name="sizes"),
        CheckConstraint(
            "client_sha256 IS NULL OR client_sha256 ~ '^[0-9a-f]{64}$'", name="client_sha256"
        ),
        CheckConstraint(
            "server_sha256 IS NULL OR server_sha256 ~ '^[0-9a-f]{64}$'", name="server_sha256"
        ),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    part_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    backend: Mapped[str] = mapped_column(Text, nullable=False, server_default="local")
    backend_ref: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default="open")
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    client_sha256: Mapped[str | None] = mapped_column(String(64))
    server_sha256: Mapped[str | None] = mapped_column(String(64))
    raw_prefix: Mapped[str] = mapped_column(Text, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    recording_ids: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UploadPart(TenantScoped, Base):
    __tablename__ = "upload_part"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "upload_id"],
            ["upload.tenant_id", "upload.id"],
            name="fk_upload_part_upload",
            ondelete="CASCADE",
        ),
        CheckConstraint("part_number >= 1 AND part_number <= 10000", name="part_number"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id", ondelete="RESTRICT"), nullable=False
    )
    upload_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    part_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = _created_at()


class Device(TenantScoped, Base):
    """A registered edge device (SEC-016): its Ed25519 public key. The private key is generated on
    the device and never leaves it; device tokens and stream chunks are verified against it."""

    __tablename__ = "device"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_device_tenant_id_id"),
        CheckConstraint("octet_length(public_key) = 32", name="public_key_len"),
        CheckConstraint("alg = 'Ed25519'", name="alg"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    alg: Mapped[str] = mapped_column(Text, nullable=False, server_default="Ed25519")
    public_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IngestStream(TenantScoped, Base):
    """One device -> platform stream into one recording (2.7). ``next_seq``/``n_samples`` are the
    committed high-water marks that make StreamChunks idempotent on (stream_id, seq)."""

    __tablename__ = "ingest_stream"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_ingest_stream_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "recording_id"],
            ["recording.tenant_id", "recording.id"],
            name="fk_ingest_stream_recording",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "device_id"],
            ["device.tenant_id", "device.id"],
            name="fk_ingest_stream_device",
            ondelete="RESTRICT",
        ),
        CheckConstraint(_in("state", STREAM_STATES), name="state"),
        CheckConstraint("sfreq > 0 AND n_channels > 0", name="shape"),
        CheckConstraint("next_seq >= 0 AND n_samples >= 0 AND capacity >= 0", name="counters"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    recording_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    sfreq: Mapped[float] = mapped_column(Double, nullable=False)
    n_channels: Mapped[int] = mapped_column(Integer, nullable=False)
    dtype: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default="open")
    next_seq: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    n_samples: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    capacity: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    # Per-channel scale/offset: physical = stored * scale + offset (used by SEC-041 range checks).
    ch_scale: Mapped[list[float]] = mapped_column(ARRAY(Double), nullable=False)
    ch_offset: Mapped[list[float]] = mapped_column(ARRAY(Double), nullable=False)
    t_first: Mapped[float | None] = mapped_column(Double)
    t_last: Mapped[float | None] = mapped_column(Double)
    suspect: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StreamChunk(TenantScoped, Base):
    """One committed chunk. The original LSL clock-offset pairs and local monotonic-clock samples
    are kept as sent (SEC-094) and copied into the Zarr group when the stream is closed."""

    __tablename__ = "stream_chunk"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "stream_id"],
            ["ingest_stream.tenant_id", "ingest_stream.id"],
            name="fk_stream_chunk_ingest_stream",
            ondelete="CASCADE",
        ),
        CheckConstraint("chunk_id ~ '^chunk:sha256:[0-9a-f]{64}$'", name="chunk_id"),
        CheckConstraint("seq >= 0 AND sample_start >= 0 AND n_samples > 0", name="counters"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id", ondelete="RESTRICT"), nullable=False
    )
    stream_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    seq: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chunk_id: Mapped[str] = mapped_column(Text, nullable=False)
    sample_start: Mapped[int] = mapped_column(BigInteger, nullable=False)
    n_samples: Mapped[int] = mapped_column(Integer, nullable=False)
    t_first: Mapped[float] = mapped_column(Double, nullable=False)
    t_last: Mapped[float] = mapped_column(Double, nullable=False)
    clock_offsets: Mapped[list[float]] = mapped_column(
        ARRAY(Double), nullable=False, server_default="{}"
    )
    local_clock: Mapped[list[float]] = mapped_column(
        ARRAY(Double), nullable=False, server_default="{}"
    )
    received_at: Mapped[datetime] = _created_at()


class ProvenanceRecord(TenantScoped, Base):
    """``raw --convert@version--> recording`` records (2.5/2.6) until the M3 provenance graph
    ingests them. The payload is non-identifying (hashes, ids, converter/reader versions)."""

    __tablename__ = "provenance_record"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = _created_at()


# ---------------------------------------------------------------- provenance graph + pipelines (M3
# 3.1, 3.2; m3-prov). Append-only: UPDATE/DELETE/TRUNCATE raise (trigger, migration 0003), nf_app
# holds SELECT + INSERT only. Integrity: per-node hash + hash-chained, Ed25519-signed batches.
PROV_KINDS = ("entity", "activity", "agent")
PROV_RELS = (
    "used",
    "wasGeneratedBy",
    "wasDerivedFrom",
    "wasAttributedTo",
    "wasAssociatedWith",
    "wasInformedBy",
)
CONTENT_ID_RE = "^(blob|pv|chunk|provb):sha256:[0-9a-f]{64}$"


class ProvBatch(TenantScoped, Base):
    """One batch of the per-tenant provenance hash chain (docs/spec/hashing.md §5.3, kind
    ``provb``). The records are rebuilt from ``prov_node``/``prov_edge`` rows (``batch_seq``,
    ``ord``); ``signature`` is Ed25519 over the ASCII ``batch_id`` by key ``key_id``."""

    __tablename__ = "prov_batch"
    __table_args__ = (
        UniqueConstraint("batch_id", name="uq_prov_batch_batch_id"),
        CheckConstraint("seq >= 0", name="seq"),
        CheckConstraint("batch_id ~ '^provb:sha256:[0-9a-f]{64}$'", name="batch_id"),
        CheckConstraint("(seq = 0) = (prev_id IS NULL)", name="prev"),
        CheckConstraint("octet_length(signature) = 64", name="signature_len"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id", ondelete="RESTRICT"), primary_key=True
    )
    seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(Text, nullable=False)
    prev_id: Mapped[str | None] = mapped_column(Text)
    # Millisecond precision (the hashed ``created_at`` string is rebuilt from it).
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    n_records: Mapped[int] = mapped_column(Integer, nullable=False)
    key_id: Mapped[str] = mapped_column(Text, nullable=False)
    signature: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)


class ProvNode(TenantScoped, Base):
    """A PROV entity, activity or agent. ``ref_id`` points at the platform object (recording id,
    upload id, run id, PipelineVersion id...), ``content_hash`` is the content ID of its bytes when
    it has any, ``node_hash`` the SHA-256 of the node's canonical record (tag ``nf.prov-node.v1``).
    ``attrs`` are non-identifying (ids, hashes, versions, parameters; never names or signal
    data)."""

    __tablename__ = "prov_node"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_prov_node_tenant_id_id"),
        UniqueConstraint("tenant_id", "batch_seq", "ord", name="uq_prov_node_batch_ord"),
        ForeignKeyConstraint(
            ["tenant_id", "batch_seq"],
            ["prov_batch.tenant_id", "prov_batch.seq"],
            name="fk_prov_node_prov_batch",
            ondelete="RESTRICT",
        ),
        CheckConstraint(_in("kind", PROV_KINDS), name="kind"),
        CheckConstraint(
            f"content_hash IS NULL OR content_hash ~ '{CONTENT_ID_RE}'", name="content_hash"
        ),
        CheckConstraint("node_hash ~ '^[0-9a-f]{64}$'", name="node_hash"),
        Index(
            "uq_prov_node_ref",
            "tenant_id",
            "kind",
            "type",
            "ref_id",
            unique=True,
            postgresql_where=text("ref_id IS NOT NULL"),
        ),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    ref_id: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(Text)
    attrs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    node_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    batch_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    ord: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = _created_at()


class ProvEdge(TenantScoped, Base):
    """``src rel dst`` in PROV direction (effect → cause): entity wasGeneratedBy activity, activity
    used entity, ... Lineage "up" follows src → dst, "down" dst → src."""

    __tablename__ = "prov_edge"
    __table_args__ = (
        UniqueConstraint("tenant_id", "batch_seq", "ord", name="uq_prov_edge_batch_ord"),
        ForeignKeyConstraint(
            ["tenant_id", "src"],
            ["prov_node.tenant_id", "prov_node.id"],
            name="fk_prov_edge_src",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "dst"],
            ["prov_node.tenant_id", "prov_node.id"],
            name="fk_prov_edge_dst",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "batch_seq"],
            ["prov_batch.tenant_id", "prov_batch.seq"],
            name="fk_prov_edge_prov_batch",
            ondelete="RESTRICT",
        ),
        CheckConstraint(_in("rel", PROV_RELS), name="rel"),
        CheckConstraint("src <> dst", name="no_self_loop"),
        Index("ix_prov_edge_dst", "dst"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id", ondelete="RESTRICT"), nullable=False
    )
    src: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    rel: Mapped[str] = mapped_column(Text, primary_key=True)
    dst: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    batch_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    ord: Mapped[int] = mapped_column(Integer, nullable=False)


class PipelineVersion(TenantScoped, Base):
    """A published, immutable PipelineVersion (3.2; SEC-044). ``pv_id`` is its content ID
    (docs/spec/hashing.md §5.1); ``name@version`` is a label that resolves to it. ``spec`` is the
    full document including ``meta`` (``meta`` is not hashed)."""

    __tablename__ = "pipeline_version"
    __table_args__ = (
        CheckConstraint("pv_id ~ '^pv:sha256:[0-9a-f]{64}$'", name="pv_id"),
        Index("ix_pipeline_version_pv_id", "tenant_id", "pv_id"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id", ondelete="RESTRICT"), primary_key=True
    )
    name: Mapped[str] = mapped_column(Text, primary_key=True)
    version: Mapped[str] = mapped_column(Text, primary_key=True)
    pv_id: Mapped[str] = mapped_column(Text, nullable=False)
    spec: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()


# ---------------------------------------------------------------- job queue + runs (3.3; m3-exec)
JOB_STATES = ("queued", "running", "succeeded", "failed", "cancelled")
RUN_STATES = ("queued", "running", "succeeded", "failed", "cancelled")


class Job(TenantScoped, Base):
    """One queued unit of work (Postgres ``SKIP LOCKED`` queue, migration 0004). ``lease_token`` is
    the fencing token of the current attempt: only its holder may heartbeat, stage or finish."""

    __tablename__ = "job"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_job_tenant_id_id"),
        UniqueConstraint("tenant_id", "kind", "dedupe_key", name="uq_job_dedupe"),
        CheckConstraint(_in("state", JOB_STATES), name="state"),
        CheckConstraint("kind ~ '^[a-z][a-z0-9_.-]{0,63}$'", name="kind"),
        CheckConstraint(
            "max_attempts >= 1 AND attempts >= 0 AND timeout_s > 0 AND backoff_s >= 0",
            name="limits",
        ),
        CheckConstraint(
            "(state = 'running') = (lease_token IS NOT NULL AND lease_expires_at IS NOT NULL)",
            name="lease",
        ),
        Index("ix_job_claim", "state", "run_after"),
        Index("ix_job_lease", "state", "lease_expires_at"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default="queued")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3")
    timeout_s: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3600")
    backoff_s: Mapped[float] = mapped_column(Double, nullable=False, server_default="5")
    run_after: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    lease_token: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker_id: Mapped[str | None] = mapped_column(Text)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    dedupe_key: Mapped[str | None] = mapped_column(Text)
    last_error: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Run(TenantScoped, Base):
    """One pipeline run: PipelineVersion + input recording. ``record`` is the run record (every
    resolved parameter incl. defaults, seed, thread pins, library versions; BLUEPRINT §3.5)."""

    __tablename__ = "run"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_run_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "recording_id"],
            ["recording.tenant_id", "recording.id"],
            name="fk_run_recording",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "job_id"],
            ["job.tenant_id", "job.id"],
            name="fk_run_job",
            ondelete="RESTRICT",
        ),
        CheckConstraint(_in("state", RUN_STATES), name="state"),
        CheckConstraint(
            "pipeline_version_id ~ '^pv:sha256:[0-9a-f]{64}$'", name="pipeline_version_id"
        ),
        CheckConstraint("state <> 'succeeded' OR prov_batch_id IS NOT NULL", name="provenance"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    pipeline_version_id: Mapped[str] = mapped_column(Text, nullable=False)
    pipeline_ref: Mapped[str] = mapped_column(Text, nullable=False)
    recording_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default="queued")
    seed: Mapped[int | None] = mapped_column(BigInteger)
    record: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    error: Mapped[str | None] = mapped_column(Text)
    prov_activity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    prov_batch_id: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RunArtifact(TenantScoped, Base):
    """One output file of a run (encrypted, ``artifacts`` bucket). Staged with ``visible_at`` NULL;
    visible only once the run's provenance commit succeeded (same transaction)."""

    __tablename__ = "run_artifact"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "run_id"],
            ["run.tenant_id", "run.id"],
            name="fk_run_artifact_run",
            ondelete="CASCADE",
        ),
        UniqueConstraint("tenant_id", "run_id", "step", "name", name="uq_run_artifact_output"),
        CheckConstraint("bucket = 'artifacts'", name="bucket"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256"),
        CheckConstraint("visible_at IS NULL OR prov_node_id IS NOT NULL", name="provenance"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    step: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    bucket: Mapped[str] = mapped_column(Text, nullable=False, server_default="artifacts")
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    attempt_token: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    visible_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    prov_node_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = _created_at()


# ---------------------------------------------------------------- M5 compliance ledger (m5-ledger;
# migrations 0005m5_governance, 0006m5_consent, 0007m5_deletion)
CONSENT_SCOPES = ("collection", "processing", "sharing", "model_training", "commercial_use")
CONSENT_KINDS = ("grant", "withdraw")
AGGREGATE_POLICIES = ("rerun", "tombstone")
ARTIFACT_STATUSES = ("deleted", "stale", "tombstoned", "superseded")
DERIVED_KINDS = ("group_average", "model")
DELETION_STATES = ("queued", "running", "succeeded", "failed")


class ArtifactGovernance(TenantScoped, Base):
    """5.1: a data steward's explicit governance attributes for one derived artifact (a provenance
    entity). Without a row the artifact inherits the strictest attributes of its inputs."""

    __tablename__ = "artifact_governance"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "node_id"],
            ["prov_node.tenant_id", "prov_node.id"],
            name="fk_artifact_governance_prov_node",
            ondelete="RESTRICT",
        ),
        CheckConstraint(_in("nervous_system", NERVOUS_SYSTEMS), name="nervous_system"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id", ondelete="RESTRICT"), primary_key=True
    )
    node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    modalities: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    nervous_system: Mapped[str] = mapped_column(Text, nullable=False)
    derived_from_non_neural: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TenantPolicy(TenantScoped, Base):
    """Per-tenant governance settings (5.5): what a withdrawal does to multi-subject aggregates."""

    __tablename__ = "tenant_policy"
    __table_args__ = (
        CheckConstraint(_in("aggregate_on_withdrawal", AGGREGATE_POLICIES), name="aggregate"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id", ondelete="RESTRICT"), primary_key=True
    )
    aggregate_on_withdrawal: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="rerun"
    )
    block_deployments_on_retrain: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DataExport(TenantScoped, Base):
    """An export that left the platform (append-only). A withdrawal cannot recall it; the
    DeletionJob lists it for the customer's follow-up (BLUEPRINT §8.4)."""

    __tablename__ = "data_export"
    __table_args__ = (UniqueConstraint("tenant_id", "id", name="uq_data_export_tenant_id_id"),)
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    node_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False)
    subject_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False)
    destination: Mapped[str] = mapped_column(Text, nullable=False)
    format: Mapped[str | None] = mapped_column(Text)
    exported_by: Mapped[str] = mapped_column(Text, nullable=False)
    exported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ConsentDocument(TenantScoped, Base):
    """A versioned consent document, identified by the SHA-256 of its bytes (append-only)."""

    __tablename__ = "consent_document"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_consent_document_tenant_id_id"),
        UniqueConstraint("tenant_id", "name", "version", name="uq_consent_document_version"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    uri: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()


class ConsentRecord(TenantScoped, Base):
    """One consent ledger entry (5.3; BLUEPRINT §8.3): append-only (trigger + grants), hash-chained
    per tenant (``record_hash`` over the canonical record incl. ``prev_hash``)."""

    __tablename__ = "consent_record"
    __table_args__ = (
        UniqueConstraint("id", name="uq_consent_record_id"),
        ForeignKeyConstraint(
            ["tenant_id", "subject_id"],
            ["subject.tenant_id", "subject.id"],
            name="fk_consent_record_subject",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "document_id"],
            ["consent_document.tenant_id", "consent_document.id"],
            name="fk_consent_record_consent_document",
            ondelete="RESTRICT",
        ),
        CheckConstraint(_in("kind", CONSENT_KINDS), name="kind"),
        CheckConstraint(
            "scopes <@ ARRAY[" + ", ".join(f"'{s}'" for s in CONSENT_SCOPES) + "]::text[]",
            name="scopes",
        ),
        CheckConstraint("kind = 'withdraw' OR document_id IS NOT NULL", name="document"),
        CheckConstraint("seq >= 0 AND (seq = 0) = (prev_hash IS NULL)", name="prev"),
        CheckConstraint("record_hash ~ '^[0-9a-f]{64}$'", name="record_hash"),
        Index("ix_consent_record_subject", "tenant_id", "subject_id", "seq"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id", ondelete="RESTRICT"), primary_key=True
    )
    seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    document_sha256: Mapped[str | None] = mapped_column(String(64))
    jurisdiction_basis: Mapped[str | None] = mapped_column(Text)
    collector_id: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_ref: Mapped[str | None] = mapped_column(Text)
    # Millisecond precision (the hashed timestamp string is rebuilt from it).
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    prev_hash: Mapped[str | None] = mapped_column(String(64))
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class DeletionJob(TenantScoped, Base):
    """A subject withdrawal (5.5; BLUEPRINT §8.4) and, when done, its signed certificate."""

    __tablename__ = "deletion_job"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_deletion_job_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "subject_id"],
            ["subject.tenant_id", "subject.id"],
            name="fk_deletion_job_subject",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "job_id"],
            ["job.tenant_id", "job.id"],
            name="fk_deletion_job_job",
            ondelete="RESTRICT",
        ),
        CheckConstraint(_in("state", DELETION_STATES), name="state"),
        CheckConstraint(_in("aggregate_policy", AGGREGATE_POLICIES), name="aggregate"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default="queued")
    aggregate_policy: Mapped[str] = mapped_column(Text, nullable=False)
    requested_by: Mapped[str] = mapped_column(Text, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_s: Mapped[float | None] = mapped_column(Double)
    certificate: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)


class DerivedObject(TenantScoped, Base):
    """A multi-subject derived object (group average, trained model). It cannot live under one
    subject's key, so it has its own KMS-wrapped data key (``wrapped_dek``); destroying that key
    (``key_state='shredded'``) makes every copy unreadable, like a subject shred."""

    __tablename__ = "derived_object"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_derived_object_tenant_id_id"),
        CheckConstraint(_in("kind", DERIVED_KINDS), name="kind"),
        CheckConstraint("bucket IN ('artifacts', 'models')", name="bucket"),
        CheckConstraint("key_state IN ('active', 'shredded')", name="key_state"),
        CheckConstraint(
            "(key_state = 'shredded') OR (wrapped_dek IS NOT NULL)", name="wrapped_unless_shredded"
        ),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    node_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    bucket: Mapped[str] = mapped_column(Text, nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    kek_id: Mapped[str] = mapped_column(Text, nullable=False)
    wrapped_dek: Mapped[bytes | None] = mapped_column(LargeBinary)
    key_state: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    input_node_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False
    )
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()
    shredded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ArtifactStatus(TenantScoped, Base):
    """What a DeletionJob did to a provenance entity (the graph itself is append-only)."""

    __tablename__ = "artifact_status"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "node_id"],
            ["prov_node.tenant_id", "prov_node.id"],
            name="fk_artifact_status_prov_node",
            ondelete="RESTRICT",
        ),
        CheckConstraint(_in("status", ARTIFACT_STATUSES), name="status"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id", ondelete="RESTRICT"), primary_key=True
    )
    node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    deletion_job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    replaced_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ModelFlag(TenantScoped, Base):
    """Hook for the model registry (M6): a model whose training data lost a subject."""

    __tablename__ = "model_flag"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "model_node_id"],
            ["prov_node.tenant_id", "prov_node.id"],
            name="fk_model_flag_prov_node",
            ondelete="RESTRICT",
        ),
        CheckConstraint("flag = 'retrain_required'", name="flag"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id", ondelete="RESTRICT"), primary_key=True
    )
    model_node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    deletion_job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    flag: Mapped[str] = mapped_column(Text, nullable=False, server_default="retrain_required")
    block_deployments: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = _created_at()


# ---------------------------------------------------------------- audit (2.8)
class AuditEvent(Base):
    """Append-only audit event (UPDATE/DELETE blocked by trigger and grants). ``seq`` is monotonic
    (SEC-103).

    ``tenant_id`` is NULL for events that cannot be tied to a tenant (for example a malformed
    token). It is not a foreign key: audit records must outlive tenant deletion.
    """

    __tablename__ = "audit_event"
    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    type: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    actor_kind: Mapped[str | None] = mapped_column(Text)
    actor_id: Mapped[str | None] = mapped_column(Text)
    auth_method: Mapped[str | None] = mapped_column(Text)
    resource_type: Mapped[str | None] = mapped_column(Text)
    resource_id: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")


class AuditBatch(Base):
    """One hourly batch of a per-tenant hash chain; the batch object itself is in the ``audit``
    bucket."""

    __tablename__ = "audit_batch"
    tenant_scope: Mapped[str] = mapped_column(Text, primary_key=True)
    seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    prev_id: Mapped[str | None] = mapped_column(Text)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    first_event_seq: Mapped[int | None] = mapped_column(BigInteger)
    last_event_seq: Mapped[int | None] = mapped_column(BigInteger)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()


# ---------------------------------------------------------------- sweeps (3.6; m3-sweeps)
class Sweep(TenantScoped, Base):
    """A multiverse sweep: a parameter grid over a published PipelineVersion (migration 0005).
    ``spec`` is the normalized request (grid, metric, recordings). Every grid point is itself a
    published, content-addressed PipelineVersion (see ``nf_platform.sweeps``)."""

    __tablename__ = "sweep"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_sweep_tenant_id_id"),
        CheckConstraint(
            "pipeline_version_id ~ '^pv:sha256:[0-9a-f]{64}$'", name="pipeline_version_id"
        ),
        CheckConstraint("n_variants >= 1 AND n_runs >= 1", name="counts"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    pipeline_ref: Mapped[str] = mapped_column(Text, nullable=False)
    pipeline_version_id: Mapped[str] = mapped_column(Text, nullable=False)
    spec: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    metric_step: Mapped[str] = mapped_column(Text, nullable=False)
    metric_key: Mapped[str] = mapped_column(Text, nullable=False)
    n_variants: Mapped[int] = mapped_column(Integer, nullable=False)
    n_runs: Mapped[int] = mapped_column(Integer, nullable=False)
    prov_node_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()


class SweepRun(TenantScoped, Base):
    """One cell of a sweep: grid point ``variant`` (its own PipelineVersion) on one recording."""

    __tablename__ = "sweep_run"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "sweep_id"],
            ["sweep.tenant_id", "sweep.id"],
            name="fk_sweep_run_sweep",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "run_id"],
            ["run.tenant_id", "run.id"],
            name="fk_sweep_run_run",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("tenant_id", "run_id", name="uq_sweep_run_run"),
        CheckConstraint("variant >= 0", name="variant"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id", ondelete="RESTRICT"), primary_key=True
    )
    sweep_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    variant: Mapped[int] = mapped_column(Integer, primary_key=True)
    recording_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    pipeline_ref: Mapped[str] = mapped_column(Text, nullable=False)
    pipeline_version_id: Mapped[str] = mapped_column(Text, nullable=False)


# ---------------------------------------------------------------- M4: quotas, webhooks (0010m4)
WEBHOOK_EVENT_TYPES = ("run.finished",)
WEBHOOK_DELIVERY_STATES = ("pending", "delivered", "failed")


class TenantQuota(Base):
    """Per-tenant quota overrides (4.8, SEC-075). Written by provisioning only (the API role may
    only read it); a NULL limit means the platform default from ``Settings``."""

    __tablename__ = "tenant_quota"
    __table_args__ = (
        CheckConstraint(
            "(max_storage_bytes IS NULL OR max_storage_bytes >= 0) AND "
            "(max_active_runs IS NULL OR max_active_runs >= 0)",
            name="limits",
        ),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id", ondelete="RESTRICT"), primary_key=True
    )
    max_storage_bytes: Mapped[int | None] = mapped_column(BigInteger)
    max_active_runs: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class WebhookEndpoint(TenantScoped, Base):
    """A customer webhook target (4.6). ``url`` passed the SSRF check (SEC-076) when it was
    registered and is re-checked (resolve once, pin the address) on every delivery."""

    __tablename__ = "webhook_endpoint"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_webhook_endpoint_tenant_id_id"),
        CheckConstraint("url LIKE 'https://%'", name="https"),
        CheckConstraint("cardinality(event_types) >= 1", name="event_types"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    url: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    event_types: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WebhookKey(TenantScoped, Base):
    """One HMAC-SHA-256 signing key version of an endpoint (SEC-045), stored AES-GCM-encrypted.
    During a rotation the previous version keeps signing until ``expires_at`` (overlap)."""

    __tablename__ = "webhook_key"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "endpoint_id"],
            ["webhook_endpoint.tenant_id", "webhook_endpoint.id"],
            name="fk_webhook_key_endpoint",
            ondelete="CASCADE",
        ),
        CheckConstraint("version >= 1", name="version"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id", ondelete="RESTRICT"), primary_key=True
    )
    endpoint_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    key_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    wrap_version: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WebhookDelivery(TenantScoped, Base):
    """One event to one endpoint, retried with exponential backoff until delivered or out of
    attempts. ``payload`` is the exact JSON body that is signed and sent."""

    __tablename__ = "webhook_delivery"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "endpoint_id"],
            ["webhook_endpoint.tenant_id", "webhook_endpoint.id"],
            name="fk_webhook_delivery_endpoint",
            ondelete="CASCADE",
        ),
        UniqueConstraint("tenant_id", "endpoint_id", "event_id", name="uq_webhook_delivery_event"),
        CheckConstraint(_in("state", WEBHOOK_DELIVERY_STATES), name="state"),
        CheckConstraint("attempts >= 0", name="attempts"),
        Index("ix_webhook_delivery_due", "state", "next_attempt_at"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    endpoint_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_status: Mapped[int | None] = mapped_column(Integer)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------- model registry (M6; m6-registry)
MODEL_VISIBILITY = ("private", "published")
DEPLOYMENT_STATES = ("approved", "refused")
EXCEPTION_BASES = ("medical", "safety")
RETRAIN_STATES = ("queued", "running", "succeeded", "failed", "external")
RETRAIN_ACTIVE_STATES = ("queued", "running")  # at most one per version (0013m6_retrain_active)


def _fk(table: str, cols: list[str], ref: str, name: str, ondelete: str = "RESTRICT"):
    return ForeignKeyConstraint(
        ["tenant_id", *cols],
        [f"{ref}.tenant_id", f"{ref}.id"],
        name=f"fk_{table}_{name}",
        ondelete=ondelete,
    )


class Model(TenantScoped, Base):
    """A registered model (6.1): name + model card (``nf.model-card/v1``). Private to its tenant
    (SEC-143); its versions carry weights, training provenance and restrictions."""

    __tablename__ = "model"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_model_tenant_id_id"),
        UniqueConstraint("tenant_id", "name", name="uq_model_tenant_id_name"),
        CheckConstraint("card_sha256 ~ '^[0-9a-f]{64}$'", name="card_sha256"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    card: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    card_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()


class ModelVersion(TenantScoped, Base):
    """One version: encrypted weights (a ``derived_object`` with its own data key), the model's
    provenance entity node (the ``model_flag`` hook keys on it), the training manifest of hashed
    subject IDs, pipeline versions, code commit, intended use and use restrictions."""

    __tablename__ = "model_version"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_model_version_tenant_id_id"),
        UniqueConstraint("tenant_id", "model_id", "version", name="uq_model_version_number"),
        UniqueConstraint("tenant_id", "prov_node_id", name="uq_model_version_prov_node"),
        UniqueConstraint("tenant_id", "derived_object_id", name="uq_model_version_derived_object"),
        _fk("model_version", ["model_id"], "model", "model"),
        _fk("model_version", ["derived_object_id"], "derived_object", "derived_object"),
        _fk("model_version", ["prov_node_id"], "prov_node", "prov_node"),
        _fk("model_version", ["parent_version_id"], "model_version", "parent"),
        CheckConstraint("version >= 1", name="version"),
        CheckConstraint("weights_sha256 ~ '^[0-9a-f]{64}$'", name="weights_sha256"),
        CheckConstraint("manifest_sha256 ~ '^[0-9a-f]{64}$'", name="manifest_sha256"),
        CheckConstraint("code_commit ~ '^[0-9a-f]{7,64}$'", name="code_commit"),
        CheckConstraint(_in("visibility", MODEL_VISIBILITY), name="visibility"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    model_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    derived_object_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    weights_format: Mapped[str] = mapped_column(Text, nullable=False)
    weights_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    prov_node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    pipeline_version_ids: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    code_commit: Mapped[str] = mapped_column(Text, nullable=False)
    intended_use: Mapped[str] = mapped_column(Text, nullable=False)
    use_restrictions: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    recipe: Mapped[str | None] = mapped_column(Text)
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    visibility: Mapped[str] = mapped_column(Text, nullable=False, server_default="private")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()


class ModelApproval(TenantScoped, Base):
    """Four-eyes approval of a version's publication (SEC-143, SEC-024)."""

    __tablename__ = "model_approval"
    __table_args__ = (_fk("model_approval", ["version_id"], "model_version", "version"),)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id", ondelete="RESTRICT"), primary_key=True
    )
    version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    approver_id: Mapped[str] = mapped_column(Text, primary_key=True)
    approver_roles: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    created_at: Mapped[datetime] = _created_at()


class ModelUseException(TenantScoped, Base):
    """A documented medical or safety exception (EU AI Act Art. 5(1)(f)) for one model, setting
    and jurisdiction. ``evidence_ref`` points at the documentation."""

    __tablename__ = "model_use_exception"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_model_use_exception_tenant_id_id"),
        _fk("model_use_exception", ["model_id"], "model", "model"),
        CheckConstraint(_in("basis", EXCEPTION_BASES), name="basis"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    model_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    basis: Mapped[str] = mapped_column(Text, nullable=False)
    jurisdiction: Mapped[str] = mapped_column(Text, nullable=False)
    setting: Mapped[str] = mapped_column(Text, nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_ref: Mapped[str] = mapped_column(Text, nullable=False)
    recorded_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()


class ModelDeployment(TenantScoped, Base):
    """A deployment request with its declared context (6.2). Refused requests are kept
    (``state='refused'`` + ``reasons``) next to the audit event. Append-only."""

    __tablename__ = "model_deployment"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_model_deployment_tenant_id_id"),
        _fk("model_deployment", ["model_id"], "model", "model"),
        _fk("model_deployment", ["version_id"], "model_version", "version"),
        _fk("model_deployment", ["exception_id"], "model_use_exception", "exception"),
        CheckConstraint(_in("state", DEPLOYMENT_STATES), name="state"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    model_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    jurisdiction: Mapped[str] = mapped_column(Text, nullable=False)
    setting: Mapped[str] = mapped_column(Text, nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    exception_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    state: Mapped[str] = mapped_column(Text, nullable=False)
    reasons: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    requested_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()


class ModelRetrain(TenantScoped, Base):
    """A retrain of a tainted version on the 3.3 queue (6.3): the job excludes every withdrawn
    subject; the new version's manifest and provenance prove it."""

    __tablename__ = "model_retrain"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_model_retrain_tenant_id_id"),
        _fk("model_retrain", ["version_id"], "model_version", "version"),
        _fk("model_retrain", ["new_version_id"], "model_version", "new_version"),
        _fk("model_retrain", ["job_id"], "job", "job"),
        CheckConstraint(_in("state", RETRAIN_STATES), name="state"),
        Index(
            "uq_model_retrain_active",
            "tenant_id",
            "version_id",
            unique=True,
            postgresql_where=text(_in("state", RETRAIN_ACTIVE_STATES)),
        ),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant_fk()
    version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default="queued")
    new_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    excluded_subject_hashes: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    input_node_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False
    )
    requested_by: Mapped[str] = mapped_column(Text, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)


class ModelVersionSbom(TenantScoped, Base):
    """The CycloneDX SBOM of the container a model version runs in (6.5; m6-sisa). The SOUP export
    lists every component. One per version; re-attaching replaces it (audited)."""

    __tablename__ = "model_version_sbom"
    __table_args__ = (
        _fk("model_version_sbom", ["version_id"], "model_version", "version"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256"),
        CheckConstraint("component_count >= 0", name="component_count"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id", ondelete="RESTRICT"), primary_key=True
    )
    version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    sbom: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    spec_version: Mapped[str] = mapped_column(Text, nullable=False)
    component_count: Mapped[int] = mapped_column(Integer, nullable=False)
    attached_by: Mapped[str] = mapped_column(Text, nullable=False)
    attached_at: Mapped[datetime] = _created_at()


# Tables with RLS and the column that holds the tenant (used by the migration and the isolation
# tests).
TENANT_COLUMN: dict[str, str] = {
    "tenant": "id",
    "project": "tenant_id",
    "dataset": "tenant_id",
    "subject": "tenant_id",
    "session": "tenant_id",
    "recording": "tenant_id",
    "channel": "tenant_id",
    "segment": "tenant_id",
    "tenant_key": "tenant_id",
    "subject_key": "tenant_id",
    "stored_object": "tenant_id",
    "api_key": "tenant_id",
    "upload": "tenant_id",
    "upload_part": "tenant_id",
    "device": "tenant_id",
    "ingest_stream": "tenant_id",
    "stream_chunk": "tenant_id",
    "provenance_record": "tenant_id",
    "prov_batch": "tenant_id",
    "prov_node": "tenant_id",
    "prov_edge": "tenant_id",
    "pipeline_version": "tenant_id",
    "job": "tenant_id",
    "run": "tenant_id",
    "run_artifact": "tenant_id",
    # m5-ledger (M5)
    "artifact_governance": "tenant_id",
    "tenant_policy": "tenant_id",
    "data_export": "tenant_id",
    "consent_document": "tenant_id",
    "consent_record": "tenant_id",
    "deletion_job": "tenant_id",
    "derived_object": "tenant_id",
    "artifact_status": "tenant_id",
    "model_flag": "tenant_id",
    "sweep": "tenant_id",
    "sweep_run": "tenant_id",
    # m6-registry (M6)
    "model": "tenant_id",
    "model_version": "tenant_id",
    "model_approval": "tenant_id",
    "model_use_exception": "tenant_id",
    "model_deployment": "tenant_id",
    "model_retrain": "tenant_id",
    "model_version_sbom": "tenant_id",  # m6-sisa (6.5)
    # m4-api (0010m4)
    "tenant_quota": "tenant_id",
    "webhook_endpoint": "tenant_id",
    "webhook_key": "tenant_id",
    "webhook_delivery": "tenant_id",
    "audit_event": "tenant_id",
    "audit_batch": "tenant_scope",
}


# ---------------------------------------------------------------- M4 4.7: public site (0011m4)
# The early-access sign-up list is not tenant data: it lives in its own schema ``site`` with its
# own metadata (not ``Base``), read/written only by the ``nf_site`` role. OWNER-GATED: the table
# exists, but the route is mounted only when ``Settings.early_access_enabled`` is true.
EARLY_ACCESS_ROLES = ("researcher", "engineer", "clinician", "founder", "student", "other")


class SiteBase(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING, schema="site")


class EarlyAccessSignup(SiteBase):
    """Minimal fields only (SEC-159): e-mail, role, optional organisation. No neural or health
    fields. ``confirm_hash`` = SHA-256 of the double-opt-in token (the token is only e-mailed)."""

    __tablename__ = "early_access_signup"
    __table_args__ = (
        UniqueConstraint("email", name="uq_early_access_signup_email"),
        UniqueConstraint("confirm_hash", name="uq_early_access_signup_confirm_hash"),
        CheckConstraint(_in("role", EARLY_ACCESS_ROLES), name="role"),
        CheckConstraint("octet_length(confirm_hash) = 32", name="confirm_hash_len"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    organisation: Mapped[str | None] = mapped_column(Text)
    confirm_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = _created_at()
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
