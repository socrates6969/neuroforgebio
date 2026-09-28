"""Ingest worker for completed uploads (2.5 + 2.6). Runs in the worker process, never in the API
(SEC-060: import-linter forbids ``api`` → ``ingest.convert``, directly or indirectly).

For one upload in state ``uploaded``: reassemble the raw original from its sealed parts into a
private temp dir, unpack zip bundles safely (SEC-064), run the matching converter (m2-data's) into
canonical encrypted Zarr, create one Recording per converted signal with the default channel
governance attributes, write the provenance record ``raw --convert@version--> recording`` (the
legacy ``provenance_record`` row AND, in the same transaction, the M3 provenance graph: raw_file
entity, convert activity, converter agent, recording entities; one signed batch), ask the
consent-policy hook for the initial state (default stub: ``quarantined``), and audit the result.

Dispatching (which upload runs where, retries, time limits) is the M3 job queue (step 3.3); M2
exposes ``process_upload`` for one upload and ``process_pending`` for one tenant.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, select

from nf_platform.audit import _canonical as cj
from nf_platform.audit import log as audit
from nf_platform.db import models as m
from nf_platform.db.context import tenant_session
from nf_platform.ingest.convert import (
    CONVERTER_VERSION,
    ConversionError,
    Limits,
    convert_file,
    detect_format,
)
from nf_platform.ingest.convert.model import DEFAULT_LIMITS
from nf_platform.ingest.policy import ConsentPolicy, StubConsentPolicy, initial_state
from nf_platform.ingest.recording_store import make_ref, open_store
from nf_platform.ingest.uploads.archive import (
    DEFAULT_ARCHIVE_LIMITS,
    ArchiveLimits,
    UnsafeArchiveError,
    safe_extract,
)
from nf_platform.ingest.uploads.backends import manifest_key
from nf_platform.ingest.uploads.service import iter_original
from nf_platform.provenance import api as prov
from nf_platform.storage.runtime import Storage, service_principal

log = logging.getLogger(__name__)
WORKER_ID = "svc:ingest-worker"
_DB_MODALITIES = {x.upper(): x for x in m.MODALITIES}


def _db_modality(modality: str) -> str:
    return _DB_MODALITIES.get(str(modality).upper(), "other")


def _find_sources(root: Path) -> list[tuple[Path, str]]:
    """Recordings inside an extracted bundle: a BIDS dataset (``*_eeg.*`` under a directory with
    dataset_description.json) or loose EDF/BDF/BrainVision/XDF/NWB files."""
    files = sorted(p for p in root.rglob("*") if p.is_file())
    if any(p.name == "dataset_description.json" for p in files):
        eeg = [
            p for p in files if "_eeg." in p.name and p.suffix.lower() in (".edf", ".bdf", ".vhdr")
        ]
        return [(p, "bids") for p in eeg]
    out = []
    for p in files:
        if p.suffix.lower() in (".edf", ".bdf", ".vhdr", ".xdf", ".nwb"):
            out.append((p, detect_format(p)))
    return out


def _emit(tenant_id: str, type_: str, outcome: audit.Outcome, upload_id: str, **details) -> None:
    audit.emit(
        audit.AuditEvent(
            type=type_,
            outcome=outcome,
            action="upload:process",
            tenant_id=tenant_id,
            actor_kind="service",
            actor_id=WORKER_ID,
            auth_method="service",
            resource_type="upload",
            resource_id=upload_id,
            details=details,
        )
    )


def process_upload(
    storage: Storage,
    tenant_id: str,
    upload_id: str,
    *,
    engine: Engine | None = None,
    policy: ConsentPolicy | None = None,
    limits: Limits = DEFAULT_LIMITS,
    archive_limits: ArchiveLimits = DEFAULT_ARCHIVE_LIMITS,
    workdir: str | Path | None = None,
) -> list[str]:
    """Convert one ``uploaded`` upload. Returns the new recording ids ([] if not processable)."""
    policy = policy or StubConsentPolicy()
    svc = service_principal(tenant_id, WORKER_ID)
    uid = uuid.UUID(str(upload_id))
    with tenant_session(svc, engine=engine) as s:
        up = s.scalar(select(m.Upload).where(m.Upload.id == uid).with_for_update())
        if up is None or up.state != "uploaded":
            return []
        up.state = "processing"
        snap = {
            "subject_id": str(up.subject_id),
            "session_id": up.session_id,
            "filename": up.filename,
            "raw_prefix": up.raw_prefix,
            "size_bytes": int(up.size_bytes),
            "part_size": int(up.part_size),
            "sha256": up.server_sha256,
            "created_by": up.created_by,
        }
    tmp = Path(tempfile.mkdtemp(prefix="nf-ingest-", dir=workdir))
    try:
        try:
            recs = _convert(storage, tenant_id, snap, tmp, limits, archive_limits)
        except (ConversionError, UnsafeArchiveError) as e:
            _fail(tenant_id, uid, engine, f"{type(e).__name__}: {e}")
            return []
        except Exception as e:  # noqa: BLE001 - a crash must mark the upload failed, not hang it
            log.exception("ingest worker failure", extra={"upload_id": str(upload_id)})
            _fail(tenant_id, uid, engine, f"internal error ({type(e).__name__})")
            return []
        ids = _record(storage, tenant_id, uid, snap, recs, engine, policy)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    _emit(tenant_id, audit.DATA_CREATE, "success", str(upload_id), count=len(ids))
    return ids


def _convert(
    storage: Storage,
    tenant_id: str,
    snap: dict[str, Any],
    tmp: Path,
    limits: Limits,
    archive_limits: ArchiveLimits,
) -> list[tuple[Any, str]]:
    raw = tmp / "original" / snap["filename"]
    raw.parent.mkdir(parents=True)
    total = 0
    parts = iter_original(
        storage,
        tenant_id,
        snap["subject_id"],
        snap["raw_prefix"],
        snap["size_bytes"],
        snap["part_size"],
    )
    with raw.open("wb") as fh:
        for block in parts:
            total += len(block)
            if total > limits.max_file_bytes:
                raise ConversionError("upload exceeds the converter size limit")
            fh.write(block)
    if raw.suffix.lower() == ".zip":
        try:
            safe_extract(raw, tmp / "bundle", archive_limits)
        except UnsafeArchiveError:
            raise
        except Exception as e:  # noqa: BLE001 - CRC errors etc. are archive errors
            raise UnsafeArchiveError(f"cannot extract archive ({type(e).__name__})") from e
        sources = _find_sources(tmp / "bundle")
    else:
        sources = [(raw, detect_format(raw))]
    if not sources:
        raise ConversionError("no recording found in the upload")
    prefix = snap["raw_prefix"]  # same prefix as the raw original, in the zarr bucket
    store = open_store(storage, tenant_id, snap["subject_id"], prefix)
    out = []
    for i, (path, fmt) in enumerate(sources):
        group = f"rec{i}"
        res = convert_file(
            path,
            store,
            group,
            fmt=fmt,
            limits=limits,
            raw_object_key=f"raw/{manifest_key(snap['raw_prefix'])}",
        )
        out.append((res, prefix))
    return out


def _record(
    storage: Storage,
    tenant_id: str,
    uid: uuid.UUID,
    snap: dict[str, Any],
    results: list[tuple[Any, str]],
    engine: Engine | None,
    policy: ConsentPolicy,
) -> list[str]:
    tid = uuid.UUID(tenant_id)
    ids: list[str] = []
    graph: list[tuple[Any, list[str]]] = []
    with tenant_session(service_principal(tenant_id, WORKER_ID), engine=engine) as s:
        up = s.scalar(select(m.Upload).where(m.Upload.id == uid).with_for_update())
        for res, prefix in results:
            rec_ids = []
            for group, ref, chans in zip(res.recording_ids, res.refs, res.channels, strict=True):
                rid = uuid.uuid4()
                n, _ = ref.shape
                rec = m.Recording(
                    id=rid,
                    tenant_id=tid,
                    session_id=snap["session_id"],
                    label=f"{snap['filename']}#{group}"[:200],
                    source_format=res.provenance.source_format,
                    state=initial_state(policy, tenant_id, snap["subject_id"], str(rid)),
                    duration_s=n / ref.sfreq,
                    zarr_ref=make_ref(prefix, group),
                    created_by=snap["created_by"],
                )
                s.add(rec)
                s.flush()
                for i, a in enumerate(chans):
                    s.add(
                        m.Channel(
                            tenant_id=tid,
                            recording_id=rid,
                            index=i,
                            name=str(a["name"])[:100],
                            modality=_db_modality(a.get("modality", "other")),
                            nervous_system=a.get("nervous_system", "unknown"),
                            derived_from_non_neural=bool(a.get("derived_from_non_neural", False)),
                            sampling_rate=float(a["sampling_rate"]),
                            units=str(a.get("units") or "")[:20] or "n/a",
                            device_ref=a.get("device_ref"),
                        )
                    )
                s.add(
                    m.Segment(
                        tenant_id=tid,
                        recording_id=rid,
                        start_s=0.0,
                        end_s=max(n / ref.sfreq, 1e-9),
                        zarr_ref=rec.zarr_ref,
                    )
                )
                rec_ids.append(str(rid))
            payload = res.provenance.to_dict()
            payload["entity_in"]["upload"] = {
                "id": str(uid),
                "blob_id": f"blob:sha256:{snap['sha256']}",
            }
            payload["entities_out"] = [
                {"kind": "recording", "id": r, "zarr_group": g}
                for r, g in zip(rec_ids, res.recording_ids, strict=True)
            ]
            payload["converter_version"] = CONVERTER_VERSION
            s.add(m.ProvenanceRecord(tenant_id=tid, kind="convert", payload=payload))
            graph.append((res.provenance, rec_ids))
            ids += rec_ids
        _record_graph(s, tenant_id, uid, snap, graph)
        up.state = "done"
        up.recording_ids = ids
        up.error = None
    return ids


def _hashable(v: Any) -> Any:
    """``v`` if it is canonical JSON (hashable into the provenance chain), else a marker."""
    try:
        cj.canonicalize(v)
    except cj.CanonicalError:
        return {"unhashable": True}
    return v


def _record_graph(
    s, tenant_id: str, uid: uuid.UUID, snap: dict[str, Any], graph: list[tuple[Any, list[str]]]
) -> prov.ProvCommit:
    """M3 provenance graph (3.1) for one upload: ``raw_file`` (ref = upload id, content = blob id)
    <-used- ``convert`` activity -generated-> ``recording`` entities (also wasDerivedFrom the raw
    file); the activity wasAssociatedWith the converter (agent ``software``, ref = name@version)."""
    E, A = prov.ProvKind.ENTITY, prov.ProvKind.ACTIVITY
    svc = service_principal(tenant_id, WORKER_ID)
    nodes = [
        prov.NodeSpec(
            E,
            "raw_file",
            str(uid),
            f"blob:sha256:{snap['sha256']}",
            {"size_bytes": snap["size_bytes"]},
        )
    ]
    edges: list[tuple[prov.NodeRef, prov.EdgeType, prov.NodeRef]] = []
    agents: dict[str, prov.NodeRef] = {}
    for p, rec_ids in graph:
        if p.converter not in agents:
            existing = prov.find_node(s, prov.ProvKind.AGENT, "software", p.converter)
            if existing is None:
                nodes.append(prov.NodeSpec(prov.ProvKind.AGENT, "software", p.converter))
                agents[p.converter] = len(nodes) - 1
            else:
                agents[p.converter] = existing
        act = len(nodes)
        nodes.append(
            prov.NodeSpec(
                A,
                "convert",
                None,
                None,
                {
                    "converter": p.converter,
                    "reader": p.reader,
                    "source_format": p.source_format,
                    "params": _hashable(p.params),
                    "started_at": p.started_at,
                    "ended_at": p.ended_at,
                },
            )
        )
        edges += [
            (act, prov.EdgeType.USED, 0),
            (act, prov.EdgeType.WAS_ASSOCIATED_WITH, agents[p.converter]),
        ]
        for rid in rec_ids:
            nodes.append(prov.NodeSpec(E, "recording", rid))
            i = len(nodes) - 1
            edges += [
                (i, prov.EdgeType.WAS_GENERATED_BY, act),
                (i, prov.EdgeType.WAS_DERIVED_FROM, 0),
            ]
    return prov.record(s, svc, nodes, edges)


def _fail(tenant_id: str, uid: uuid.UUID, engine: Engine | None, reason: str) -> None:
    with tenant_session(service_principal(tenant_id, WORKER_ID), engine=engine) as s:
        up = s.get(m.Upload, uid)
        if up is not None:
            up.state = "failed"
            up.error = reason[:500]
    _emit(tenant_id, audit.DATA_CREATE, "failure", str(uid), reason=reason[:200])


def process_pending(
    storage: Storage, tenant_id: str, *, engine: Engine | None = None, **kw: Any
) -> dict[str, list[str]]:
    """Run every ``uploaded`` upload of one tenant (M2 stand-in for the M3 job queue)."""
    with tenant_session(service_principal(tenant_id, WORKER_ID), engine=engine) as s:
        q = select(m.Upload.id).where(m.Upload.state == "uploaded").order_by(m.Upload.created_at)
        pending = [str(x) for x in s.scalars(q)]
    return {u: process_upload(storage, tenant_id, u, engine=engine, **kw) for u in pending}


def main() -> None:
    """``python -m nf_platform.ingest.uploads.worker --tenant <id>`` (dev stand-in for the M3
    queue). Needs NF_DATABASE_URL, storage (``storage_from_env``: NF_OBJECT_ROOT in dev, S3 + AWS
    KMS in prod; refused in prod otherwise) and a KMS shared with the API process: the dev
    ``LocalKms`` lives in one process's memory, so in dev run the worker in the API process's test
    harness instead."""
    import argparse  # noqa: PLC0415
    import os  # noqa: PLC0415

    from nf_platform.config import environment_from_env  # noqa: PLC0415
    from nf_platform.db.context import configure_engine  # noqa: PLC0415
    from nf_platform.storage.runtime import required_storage_from_env  # noqa: PLC0415

    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", required=True)
    args = ap.parse_args()
    eng = configure_engine(os.environ["NF_DATABASE_URL"])
    audit.configure(audit.PostgresAuditSink(eng))
    # Fails closed in prod unless S3 + AWS KMS are configured (NR-H1).
    storage = required_storage_from_env(environment_from_env(), engine=eng)
    for upload_id, ids in process_pending(storage, args.tenant, engine=eng).items():
        print(f"{upload_id}: {len(ids)} recording(s)", flush=True)  # noqa: T201


if __name__ == "__main__":
    main()
