"""Ingest (2.6 uploads, 2.7 streams): upload sessions + parts, devices, ingest streams + committed
chunks, provenance records; recording.zarr_ref, segment quality (SEC-041), tenant.synthetic_only
(SEC-071). Every new table gets forced RLS with the same tenant policy as 0001.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

APP = "nf_app"
NEW_TABLES = (
    "upload",
    "upload_part",
    "device",
    "ingest_stream",
    "stream_chunk",
    "provenance_record",
)


def _uuid(name: str, **kw) -> sa.Column:
    return sa.Column(name, pg.UUID(as_uuid=True), **kw)


def _ts(name: str, **kw) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), **kw)


def _created(name: str = "created_at") -> sa.Column:
    return _ts(name, nullable=False, server_default=sa.func.now())


def _tenant_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["tenant_id"], ["tenant.id"], name=f"fk_{table}_tenant_id_tenant", ondelete="RESTRICT"
    )


def _parent_fk(table: str, parent: str, col: str, ondelete: str = "RESTRICT"):
    return sa.ForeignKeyConstraint(
        ["tenant_id", col],
        [f"{parent}.tenant_id", f"{parent}.id"],
        name=f"fk_{table}_{parent}",
        ondelete=ondelete,
    )


def _in(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    # ---------------------------------------------------------------- columns on 0001 tables
    op.add_column(
        "tenant",
        sa.Column("synthetic_only", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column("recording", sa.Column("zarr_ref", sa.Text()))
    op.add_column("segment", sa.Column("quality", sa.Text(), nullable=False, server_default="ok"))
    op.add_column("segment", sa.Column("reason", sa.Text()))
    op.create_check_constraint("ck_segment_quality", "segment", _in("quality", ("ok", "suspect")))

    # ---------------------------------------------------------------- uploads (2.6)
    op.create_table(
        "upload",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        _uuid("dataset_id", nullable=False),
        _uuid("session_id", nullable=False),
        _uuid("subject_id", nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("part_size", sa.BigInteger(), nullable=False),
        sa.Column("backend", sa.Text(), nullable=False, server_default="local"),
        sa.Column("backend_ref", sa.Text()),
        sa.Column("state", sa.Text(), nullable=False, server_default="open"),
        sa.Column("synthetic", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("client_sha256", sa.String(64)),
        sa.Column("server_sha256", sa.String(64)),
        sa.Column("raw_prefix", sa.Text(), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("recording_ids", pg.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_by", sa.Text(), nullable=False),
        _created(),
        _ts("completed_at"),
        sa.PrimaryKeyConstraint("id", name="pk_upload"),
        _tenant_fk("upload"),
        _parent_fk("upload", "dataset", "dataset_id"),
        _parent_fk("upload", "session", "session_id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_upload_tenant_id_id"),
        sa.CheckConstraint(
            _in("state", ("open", "uploaded", "processing", "done", "rejected", "failed")),
            name="ck_upload_state",
        ),
        sa.CheckConstraint("size_bytes > 0 AND part_size > 0", name="ck_upload_sizes"),
        sa.CheckConstraint(
            "client_sha256 IS NULL OR client_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_upload_client_sha256",
        ),
        sa.CheckConstraint(
            "server_sha256 IS NULL OR server_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_upload_server_sha256",
        ),
    )
    op.create_table(
        "upload_part",
        _uuid("tenant_id", nullable=False),
        _uuid("upload_id", nullable=False),
        sa.Column("part_number", sa.Integer(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        _created(),
        sa.PrimaryKeyConstraint("upload_id", "part_number", name="pk_upload_part"),
        _tenant_fk("upload_part"),
        _parent_fk("upload_part", "upload", "upload_id", ondelete="CASCADE"),
        sa.CheckConstraint(
            "part_number >= 1 AND part_number <= 10000", name="ck_upload_part_part_number"
        ),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_upload_part_sha256"),
    )

    # ---------------------------------------------------------------- devices + streams (2.7)
    op.create_table(
        "device",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("alg", sa.Text(), nullable=False, server_default="Ed25519"),
        sa.Column("public_key", sa.LargeBinary(), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        _created(),
        _ts("revoked_at"),
        sa.PrimaryKeyConstraint("id", name="pk_device"),
        _tenant_fk("device"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_device_tenant_id_id"),
        sa.CheckConstraint("octet_length(public_key) = 32", name="ck_device_public_key_len"),
        sa.CheckConstraint("alg = 'Ed25519'", name="ck_device_alg"),
    )
    op.create_table(
        "ingest_stream",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        _uuid("recording_id", nullable=False),
        _uuid("subject_id", nullable=False),
        _uuid("device_id", nullable=False),
        sa.Column("sfreq", sa.Double(), nullable=False),
        sa.Column("n_channels", sa.Integer(), nullable=False),
        sa.Column("dtype", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False, server_default="open"),
        sa.Column("next_seq", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("n_samples", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("capacity", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("ch_scale", pg.ARRAY(sa.Double()), nullable=False),
        sa.Column("ch_offset", pg.ARRAY(sa.Double()), nullable=False),
        sa.Column("t_first", sa.Double()),
        sa.Column("t_last", sa.Double()),
        sa.Column("suspect", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("synthetic", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_by", sa.Text(), nullable=False),
        _created(),
        _ts("closed_at"),
        sa.PrimaryKeyConstraint("id", name="pk_ingest_stream"),
        _tenant_fk("ingest_stream"),
        _parent_fk("ingest_stream", "recording", "recording_id"),
        _parent_fk("ingest_stream", "device", "device_id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_ingest_stream_tenant_id_id"),
        sa.CheckConstraint(_in("state", ("open", "closed")), name="ck_ingest_stream_state"),
        sa.CheckConstraint("sfreq > 0 AND n_channels > 0", name="ck_ingest_stream_shape"),
        sa.CheckConstraint(
            "next_seq >= 0 AND n_samples >= 0 AND capacity >= 0",
            name="ck_ingest_stream_counters",
        ),
    )
    op.create_table(
        "stream_chunk",
        _uuid("tenant_id", nullable=False),
        _uuid("stream_id", nullable=False),
        sa.Column("seq", sa.BigInteger(), nullable=False),
        sa.Column("chunk_id", sa.Text(), nullable=False),
        sa.Column("sample_start", sa.BigInteger(), nullable=False),
        sa.Column("n_samples", sa.Integer(), nullable=False),
        sa.Column("t_first", sa.Double(), nullable=False),
        sa.Column("t_last", sa.Double(), nullable=False),
        sa.Column("clock_offsets", pg.ARRAY(sa.Double()), nullable=False, server_default="{}"),
        sa.Column("local_clock", pg.ARRAY(sa.Double()), nullable=False, server_default="{}"),
        _created("received_at"),
        sa.PrimaryKeyConstraint("stream_id", "seq", name="pk_stream_chunk"),
        _tenant_fk("stream_chunk"),
        _parent_fk("stream_chunk", "ingest_stream", "stream_id", ondelete="CASCADE"),
        sa.CheckConstraint(
            "chunk_id ~ '^chunk:sha256:[0-9a-f]{64}$'", name="ck_stream_chunk_chunk_id"
        ),
        sa.CheckConstraint(
            "seq >= 0 AND sample_start >= 0 AND n_samples > 0", name="ck_stream_chunk_counters"
        ),
    )
    op.create_table(
        "provenance_record",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("payload", pg.JSONB(), nullable=False),
        _created(),
        sa.PrimaryKeyConstraint("id", name="pk_provenance_record"),
        _tenant_fk("provenance_record"),
    )

    # ---------------------------------------------------------------- grants + RLS (SEC-021)
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {', '.join(NEW_TABLES)} TO {APP}")
    for t in NEW_TABLES:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {t} TO {APP} "
            "USING (tenant_id = nf_current_tenant()) WITH CHECK (tenant_id = nf_current_tenant())"
        )


def downgrade() -> None:
    for t in reversed(NEW_TABLES):
        op.drop_table(t)
    op.drop_constraint("ck_segment_quality", "segment", type_="check")
    op.drop_column("segment", "reason")
    op.drop_column("segment", "quality")
    op.drop_column("recording", "zarr_ref")
    op.drop_column("tenant", "synthetic_only")
