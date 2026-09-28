"""2.1 acceptance / SEC-021: with two tenants, every table queried under tenant A's DB role returns
zero rows of tenant B (RLS), plus the app-level check (ORM filter, write guard, API returns 404 for
B's
objects)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from nf_platform.db import models as m
from nf_platform.db.context import Principal, TenantViolation, tenant_session
from nf_platform.db.models import TENANT_COLUMN
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, ProgrammingError

pytestmark = pytest.mark.postgres


def _seed_tenant(c, tid: str) -> None:
    """One row in every tenant table for ``tid`` (as the superuser = provisioning path)."""
    ids = {
        k: str(uuid.uuid4())
        for k in (
            "p",
            "d",
            "s",
            "se",
            "r",
            "ch",
            "sg",
            "o",
            "k",
            "e",
            "u",
            "dv",
            "st",
            "pr",
            "pn1",
            "pn2",
            "jb",
            "rn",
            "ra",
            "sw",
        )
    }
    now = datetime.now(UTC)
    ins = [
        ("project", {"id": ids["p"], "tenant_id": tid, "name": "p", "created_by": "u"}),
        (
            "dataset",
            {
                "id": ids["d"],
                "tenant_id": tid,
                "project_id": ids["p"],
                "name": "d",
                "created_by": "u",
            },
        ),
        (
            "subject",
            {
                "id": ids["s"],
                "tenant_id": tid,
                "dataset_id": ids["d"],
                "label": "s",
                "created_by": "u",
            },
        ),
        (
            "session",
            {
                "id": ids["se"],
                "tenant_id": tid,
                "subject_id": ids["s"],
                "label": "x",
                "created_by": "u",
            },
        ),
        (
            "recording",
            {
                "id": ids["r"],
                "tenant_id": tid,
                "session_id": ids["se"],
                "label": "r",
                "created_by": "u",
            },
        ),
        (
            "channel",
            {
                "id": ids["ch"],
                "tenant_id": tid,
                "recording_id": ids["r"],
                "index": 0,
                "name": "Cz",
                "modality": "EEG",
                "sampling_rate": 256.0,
                "units": "uV",
            },
        ),
        (
            "segment",
            {"id": ids["sg"], "tenant_id": tid, "recording_id": ids["r"], "start_s": 0, "end_s": 1},
        ),
        ("tenant_key", {"tenant_id": tid, "kek_version": 1, "kek_id": "kms:local:1"}),
        (
            "subject_key",
            {
                "tenant_id": tid,
                "subject_id": ids["s"],
                "dek_version": 1,
                "kek_id": "kms:local:1",
                "kek_version": 1,
                "wrapped_dek": b"\x01" * 40,
            },
        ),
        (
            "stored_object",
            {
                "id": ids["o"],
                "tenant_id": tid,
                "subject_id": ids["s"],
                "bucket": "raw",
                "object_key": f"{tid}/x.edf",
                "sha256": "0" * 64,
                "size_bytes": 1,
                "ciphertext_size": 29,
            },
        ),
        (
            "api_key",
            {
                "id": ids["k"],
                "tenant_id": tid,
                "public_id": uuid.uuid4().hex[:16],
                "owner_id": "u",
                "name": "k",
                "key_hash": b"\x02" * 32,
                "pepper_version": "p1",
                "roles": ["viewer"],
                "scopes": ["metadata:read"],
                "expires_at": now + timedelta(days=1),
            },
        ),
        (
            "audit_event",
            {"id": ids["e"], "tenant_id": tid, "type": "data.read", "outcome": "success"},
        ),
        (
            "audit_batch",
            {
                "tenant_scope": tid,
                "seq": 0,
                "batch_id": f"auditb:sha256:{uuid.uuid4().hex * 2}",
                "period_start": now,
                "period_end": now,
                # AppSec M2: a batch must cover the scope's events (continuity trigger); the
                # tenant's one audit_event row is inserted just before this row
                "first_event_seq": _tenant_event_seq,
                "last_event_seq": _tenant_event_seq,
                "event_count": 1,
                "object_key": f"chain/{tid}/000000000000.json",
            },
        ),
        # m2-stream tables (2.6 uploads, 2.7 streams)
        (
            "upload",
            {
                "id": ids["u"],
                "tenant_id": tid,
                "dataset_id": ids["d"],
                "session_id": ids["se"],
                "subject_id": ids["s"],
                "filename": "x.edf",
                "size_bytes": 1,
                "part_size": 1,
                "raw_prefix": f"t/{tid}/u",
                "created_by": "u",
            },
        ),
        (
            "upload_part",
            {
                "tenant_id": tid,
                "upload_id": ids["u"],
                "part_number": 1,
                "size_bytes": 1,
                "sha256": "0" * 64,
            },
        ),
        (
            "device",
            {
                "id": ids["dv"],
                "tenant_id": tid,
                "name": "d",
                "public_key": b"\x03" * 32,
                "created_by": "u",
            },
        ),
        (
            "ingest_stream",
            {
                "id": ids["st"],
                "tenant_id": tid,
                "recording_id": ids["r"],
                "subject_id": ids["s"],
                "device_id": ids["dv"],
                "sfreq": 1000.0,
                "n_channels": 1,
                "dtype": "float32",
                "ch_scale": [1.0],
                "ch_offset": [0.0],
                "created_by": "u",
            },
        ),
        (
            "stream_chunk",
            {
                "tenant_id": tid,
                "stream_id": ids["st"],
                "seq": 0,
                "chunk_id": "chunk:sha256:" + "0" * 64,
                "sample_start": 0,
                "n_samples": 1,
                "t_first": 0.0,
                "t_last": 0.0,
            },
        ),
        (
            "provenance_record",
            {"id": ids["pr"], "tenant_id": tid, "kind": "convert", "payload": "{}"},
        ),
        # m3-prov (0003): provenance graph + published pipelines
        (
            "prov_batch",
            {
                "tenant_id": tid,
                "seq": 0,
                "batch_id": "provb:sha256:" + uuid.uuid4().hex * 2,
                "created_at": now,
                "n_records": 2,
                "key_id": "k",
                "signature": b"\0" * 64,
            },
        ),
        *(
            (
                "prov_node",
                {
                    "id": ids[k],
                    "tenant_id": tid,
                    "kind": "entity",
                    "type": "x",
                    "node_hash": "0" * 64,
                    "batch_seq": 0,
                    "ord": i,
                },
            )
            for i, k in enumerate(("pn1", "pn2"))
        ),
        (
            "prov_edge",
            {
                "tenant_id": tid,
                "src": ids["pn2"],
                "rel": "wasDerivedFrom",
                "dst": ids["pn1"],
                "batch_seq": 0,
                "ord": 0,
            },
        ),
        (
            "pipeline_version",
            {
                "tenant_id": tid,
                "name": "p",
                "version": "1.0.0",
                "pv_id": "pv:sha256:" + "0" * 64,
                "spec": "{}",
                "created_by": "u",
            },
        ),
    ]
    # m3-exec tables (3.3 job queue + runs)
    ins += [
        (
            "job",
            {"id": ids["jb"], "tenant_id": tid, "kind": "pipeline.run", "created_by": "u"},
        ),
        (
            "run",
            {
                "id": ids["rn"],
                "tenant_id": tid,
                "pipeline_version_id": "pv:sha256:" + "0" * 64,
                "pipeline_ref": "p@1.0.0",
                "recording_id": ids["r"],
                "job_id": ids["jb"],
                "record": "{}",
                "created_by": "u",
            },
        ),
        (
            "run_artifact",
            {
                "id": ids["ra"],
                "tenant_id": tid,
                "run_id": ids["rn"],
                "step": "s",
                "name": "signal.npy",
                "object_key": f"t/{tid}/runs/x",
                "sha256": "0" * 64,
                "size_bytes": 1,
                "attempt_token": ids["jb"],
            },
        ),
    ]
    # m5-ledger tables (M5: governance attributes, consent ledger, deletion propagation)
    m5 = {k: str(uuid.uuid4()) for k in ("cd", "cr", "dj", "do", "dx")}
    ins += [
        (
            "artifact_governance",
            {
                "tenant_id": tid,
                "node_id": ids["pn2"],
                "nervous_system": "central",
                "derived_from_non_neural": False,
                "updated_by": "u",
            },
        ),
        ("tenant_policy", {"tenant_id": tid, "updated_by": "u"}),
        (
            "data_export",
            {
                "id": m5["dx"],
                "tenant_id": tid,
                "node_ids": [ids["pn2"]],
                "subject_ids": [ids["s"]],
                "destination": "partner",
                "exported_by": "u",
            },
        ),
        (
            "consent_document",
            {
                "id": m5["cd"],
                "tenant_id": tid,
                "name": "c",
                "version": "1",
                "sha256": "0" * 64,
                "created_by": "u",
            },
        ),
        (
            "consent_record",
            {
                "tenant_id": tid,
                "seq": 0,
                "id": m5["cr"],
                "subject_id": ids["s"],
                "kind": "grant",
                "scopes": ["processing"],
                "document_id": m5["cd"],
                "collector_id": "u",
                "recorded_at": now,
                "record_hash": "0" * 64,
            },
        ),
        (
            "deletion_job",
            {
                "id": m5["dj"],
                "tenant_id": tid,
                "subject_id": ids["s"],
                "job_id": ids["jb"],
                "aggregate_policy": "rerun",
                "requested_by": "u",
            },
        ),
        (
            "derived_object",
            {
                "id": m5["do"],
                "tenant_id": tid,
                "node_id": ids["pn2"],
                "kind": "group_average",
                "bucket": "artifacts",
                "object_key": f"t/{tid}/derived/x",
                "sha256": "0" * 64,
                "size_bytes": 1,
                "kek_id": "k",
                "wrapped_dek": b"w",
                "input_node_ids": [ids["pn1"]],
                "created_by": "u",
            },
        ),
        (
            "artifact_status",
            {
                "tenant_id": tid,
                "node_id": ids["pn2"],
                "status": "stale",
                "deletion_job_id": m5["dj"],
            },
        ),
        (
            "model_flag",
            {
                "tenant_id": tid,
                "model_node_id": ids["pn2"],
                "deletion_job_id": m5["dj"],
                "block_deployments": True,
            },
        ),
    ]
    # m3-sweeps tables (3.6 sweeps)
    ins += [
        (
            "sweep",
            {
                "id": ids["sw"],
                "tenant_id": tid,
                "name": "s",
                "pipeline_ref": "p@1.0.0",
                "pipeline_version_id": "pv:sha256:" + "0" * 64,
                "spec": "{}",
                "metric_step": "decode",
                "metric_key": "accuracy",
                "n_variants": 1,
                "n_runs": 1,
                "created_by": "u",
            },
        ),
        (
            "sweep_run",
            {
                "tenant_id": tid,
                "sweep_id": ids["sw"],
                "variant": 0,
                "recording_id": ids["r"],
                "run_id": ids["rn"],
                "params": "{}",
                "pipeline_ref": "p@1.0.0",
                "pipeline_version_id": "pv:sha256:" + "0" * 64,
            },
        ),
    ]
    # m6-registry tables (M6 model registry)
    m6 = {k: str(uuid.uuid4()) for k in ("md", "mv", "mx", "dp", "rt")}
    ins += [
        (
            "model",
            {
                "id": m6["md"],
                "tenant_id": tid,
                "name": "m",
                "card": "{}",
                "card_sha256": "0" * 64,
                "created_by": "u",
            },
        ),
        (
            "model_version",
            {
                "id": m6["mv"],
                "tenant_id": tid,
                "model_id": m6["md"],
                "version": 1,
                "derived_object_id": m5["do"],
                "weights_format": "safetensors",
                "weights_sha256": "0" * 64,
                "prov_node_id": ids["pn2"],
                "manifest": "{}",
                "manifest_sha256": "0" * 64,
                "pipeline_version_ids": [],
                "code_commit": "0" * 40,
                "intended_use": "x",
                "use_restrictions": [],
                "created_by": "u",
            },
        ),
        (
            "model_approval",
            {"tenant_id": tid, "version_id": m6["mv"], "approver_id": "a", "approver_roles": []},
        ),
        (
            "model_use_exception",
            {
                "id": m6["mx"],
                "tenant_id": tid,
                "model_id": m6["md"],
                "basis": "medical",
                "jurisdiction": "EU",
                "setting": "workplace",
                "justification": "j",
                "evidence_ref": "e",
                "recorded_by": "u",
            },
        ),
        (
            "model_deployment",
            {
                "id": m6["dp"],
                "tenant_id": tid,
                "model_id": m6["md"],
                "version_id": m6["mv"],
                "jurisdiction": "EU",
                "setting": "research",
                "purpose": "p",
                "context": "{}",
                "state": "approved",
                "reasons": [],
                "requested_by": "u",
            },
        ),
        (
            "model_retrain",
            {
                "id": m6["rt"],
                "tenant_id": tid,
                "version_id": m6["mv"],
                "job_id": ids["jb"],
                "excluded_subject_hashes": [],
                "input_node_ids": [],
                "requested_by": "u",
            },
        ),
        # m6-sisa (6.5)
        (
            "model_version_sbom",
            {
                "tenant_id": tid,
                "version_id": m6["mv"],
                "sbom": "{}",
                "sha256": "0" * 64,
                "spec_version": "1.6",
                "component_count": 0,
                "attached_by": "u",
            },
        ),
    ]
    # m4-api tables (0010m4: quotas, webhooks)
    wh = str(uuid.uuid4())
    ins += [
        ("tenant_quota", {"tenant_id": tid, "max_storage_bytes": 1, "max_active_runs": 1}),
        (
            "webhook_endpoint",
            {
                "id": wh,
                "tenant_id": tid,
                "url": "https://hooks.example.com/x",
                "event_types": ["run.finished"],
                "created_by": "u",
            },
        ),
        (
            "webhook_key",
            {
                "tenant_id": tid,
                "endpoint_id": wh,
                "version": 1,
                "key_ciphertext": bytes(44),
                "wrap_version": "p1",
            },
        ),
        (
            "webhook_delivery",
            {
                "id": str(uuid.uuid4()),
                "tenant_id": tid,
                "endpoint_id": wh,
                "event_id": str(uuid.uuid4()),
                "event_type": "run.finished",
                "payload": "{}",
            },
        ),
    ]
    assert {t for t, _ in ins} | {"tenant"} == set(TENANT_COLUMN), "seed every table"
    for table, row in ins:
        row = {k: (v(c, tid) if callable(v) else v) for k, v in row.items()}
        cols = ", ".join(f'"{k}"' for k in row)
        vals = ", ".join(f":{k}" for k in row)
        c.execute(text(f"INSERT INTO {table} ({cols}) VALUES ({vals})"), row)


def _tenant_event_seq(c, tid: str) -> int:
    return c.execute(
        text("SELECT max(seq) FROM audit_event WHERE tenant_id = :t"), {"t": tid}
    ).scalar()


@pytest.fixture
def seeded(engine, tenants):
    with engine.begin() as c:
        _seed_tenant(c, tenants.a)
        _seed_tenant(c, tenants.b)
    return tenants


def _count_as(engine, tenant: str | None, table: str, where_tenant: str | None = None) -> int:
    col = TENANT_COLUMN[table]
    with engine.begin() as c:
        c.execute(text("SET LOCAL ROLE nf_app"))
        if tenant is not None:
            c.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": tenant})
        sql = f"SELECT count(*) FROM {table}"
        params = {}
        if where_tenant is not None:
            sql += f" WHERE {col}::text = :w"
            params = {"w": where_tenant}
        return c.execute(text(sql), params).scalar_one()


@pytest.mark.parametrize("table", sorted(TENANT_COLUMN))
def test_rls_hides_other_tenant_rows(engine, seeded, table):
    a, b = seeded.a, seeded.b
    # superuser sees both tenants' rows (the seed worked) ...
    with engine.connect() as c:
        col = TENANT_COLUMN[table]
        total_b = c.execute(
            text(f"SELECT count(*) FROM {table} WHERE {col}::text = :b"), {"b": b}
        ).scalar_one()
    assert total_b >= 1
    # ... tenant A's role sees none of B's, and its own.
    assert _count_as(engine, a, table, where_tenant=b) == 0
    assert _count_as(engine, a, table) == _count_as(engine, a, table, where_tenant=a) >= 1
    # no tenant set: fail closed, zero rows
    assert _count_as(engine, None, table) == 0


def test_rls_blocks_writes_into_other_tenant(engine, seeded):
    with engine.begin() as c:
        c.execute(text("SET LOCAL ROLE nf_app"))
        c.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": seeded.a})
        with (
            pytest.raises(ProgrammingError, match="row-level security"),
            c.begin_nested(),
        ):
            c.execute(
                text(
                    "INSERT INTO project (id, tenant_id, name, created_by) "
                    "VALUES (:i, :t, 'x', 'u')"
                ),
                {"i": str(uuid.uuid4()), "t": seeded.b},
            )
        # UPDATE/DELETE of B's rows touch nothing
        assert c.execute(text("UPDATE project SET name='pwn'")).rowcount == 1  # only A's own row
        assert (
            c.execute(
                text("DELETE FROM segment WHERE tenant_id::text = :b"), {"b": seeded.b}
            ).rowcount
            == 0
        )


def test_app_role_cannot_escape_audit_append_only(engine, seeded):
    with engine.begin() as c:
        c.execute(text("SET LOCAL ROLE nf_app"))
        c.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": seeded.a})
        with pytest.raises(DBAPIError):
            c.execute(text("DELETE FROM audit_event"))


def test_app_level_filter_and_write_guard(engine, seeded):
    pa = Principal("u", seeded.a, frozenset({"viewer"}), frozenset(), "user", False)
    with tenant_session(pa, engine=engine) as s:
        rows = s.scalars(select(m.Project)).all()
        assert rows and all(str(r.tenant_id) == seeded.a for r in rows)
    with pytest.raises(TenantViolation), tenant_session(pa, engine=engine) as s:
        s.add(m.Project(tenant_id=uuid.UUID(seeded.b), name="x", created_by="u"))
        s.flush()


def test_api_other_tenant_objects_are_404(client, as_role, tenants, tree):
    """BOLA: tenant B's principal cannot read or create under tenant A's objects via any id
    route."""
    h_b = as_role("owner", tenant=tenants.b)
    for path in (
        f"/v1/projects/{tree['project_id']}",
        f"/v1/projects/{tree['project_id']}/datasets",
        f"/v1/datasets/{tree['dataset_id']}",
        f"/v1/datasets/{tree['dataset_id']}/subjects",
        f"/v1/subjects/{tree['subject_id']}",
        f"/v1/subjects/{tree['subject_id']}/sessions",
        f"/v1/sessions/{tree['session_id']}",
        f"/v1/sessions/{tree['session_id']}/recordings",
        f"/v1/recordings/{tree['recording_id']}",
        f"/v1/recordings/{tree['recording_id']}/data?start=0&end=1",  # 2.4 window read
        f"/v1/uploads/{tree['upload_id']}",  # 2.6
    ):
        assert client.get(path, headers=h_b).status_code == 404, path
    # 2.6 / 2.7 writes under A's objects
    for path, body in (
        (
            f"/v1/datasets/{tree['dataset_id']}/uploads",
            {
                "session_id": tree["session_id"],
                "filename": "x.edf",
                "size_bytes": 1,
                "synthetic": True,
            },
        ),
        (f"/v1/uploads/{tree['upload_id']}/complete", {"sha256": "0" * 64}),
    ):
        assert client.post(path, json=body, headers=h_b).status_code == 404, path
    r = client.put(f"/v1/uploads/{tree['upload_id']}/parts/1", content=b"x" * 32, headers=h_b)
    assert r.status_code == 404
    assert client.get("/v1/projects", headers=h_b).json() == []
    r = client.post(f"/v1/projects/{tree['project_id']}/datasets", json={"name": "x"}, headers=h_b)
    assert r.status_code == 404
