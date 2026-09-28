"""Multi-subject derived objects: group averages and (toy) trained models (BUILD-GUIDE 5.5 test
scaffolding; the model registry itself is M6).

A group average mixes several subjects' data, so it cannot be sealed with one subject's DEK. Each
derived object gets its own data key under the tenant KEK (``Keyring.new_data_key``), wrapped and
stored in ``derived_object.wrapped_dek``. Destroying that key (``shred``) makes every copy of the
object unreadable, backups included, exactly like a subject crypto-shred.

Every creation goes through ``policy.check`` (``aggregate:create`` needs ``processing``,
``model:train`` needs ``model_training`` for EVERY contributing subject, SEC-146) and is recorded
in the provenance graph: ``<activity> used <inputs>``, ``<output> wasGeneratedBy <activity>``,
``<output> wasDerivedFrom <inputs>``.

Envelope: ``"NFD1" | nonce(12) | AES-256-GCM(ciphertext||tag)``; AAD = ``"NFD1" 0x00`` + canonical
JSON ``{bucket, key, object_id, tenant_id}``.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import uuid
from datetime import UTC, datetime
from typing import Any

import numpy as np
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.orm import Session

from nf_platform.audit import _canonical as cj
from nf_platform.db import models as m
from nf_platform.db.context import Principal
from nf_platform.governance import policy
from nf_platform.provenance import api as prov
from nf_platform.storage.keyring import SubjectKeyUnavailable
from nf_platform.storage.runtime import Storage

MAGIC = b"NFD1"
NONCE = 12
ARTIFACT_BUCKET = "artifacts"
MODEL_BUCKET = "models"


class DerivedError(ValueError):
    pass


def _aad(tenant_id: str, obj_id: str, bucket: str, key: str) -> bytes:
    return (
        MAGIC
        + b"\x00"
        + cj.canonicalize(
            {"bucket": bucket, "key": key, "object_id": obj_id, "tenant_id": tenant_id}
        )
    )


def _ctx(obj_id: str) -> dict[str, str]:
    return {"derived_object_id": obj_id}


def seal(
    storage: Storage, tenant_id: str, obj_id: str, bucket: str, key: str, data: bytes
) -> tuple[bytes, str]:
    """Encrypt + store ``data``; returns (wrapped DEK, kek_id)."""
    dek, wrapped, kek_id = storage.keyring.new_data_key(tenant_id, _ctx(obj_id))
    nonce = os.urandom(NONCE)
    ct = AESGCM(dek).encrypt(nonce, data, _aad(tenant_id, obj_id, bucket, key))
    storage.objects.put(bucket, key, MAGIC + nonce + ct, metadata={"nf-enc": "NFD1"})
    return wrapped, kek_id


def open_blob(storage: Storage, row: m.DerivedObject, blob: bytes) -> bytes:
    """Decrypt one copy of a derived object (a backup copy works the same way)."""
    if row.key_state != "active" or row.wrapped_dek is None:
        raise SubjectKeyUnavailable("the data key of this derived object was destroyed")
    if blob[:4] != MAGIC or len(blob) < 4 + NONCE + 16:
        raise DerivedError("not an NFD1 envelope")
    tid, oid = str(row.tenant_id), str(row.id)
    dek = storage.keyring.unwrap_data_key(tid, row.kek_id, bytes(row.wrapped_dek), _ctx(oid))
    try:
        return AESGCM(dek).decrypt(
            blob[4 : 4 + NONCE], blob[4 + NONCE :], _aad(tid, oid, row.bucket, row.object_key)
        )
    except InvalidTag as e:
        raise DerivedError("authentication failed") from e


def read(storage: Storage, row: m.DerivedObject) -> bytes:
    return open_blob(storage, row, storage.objects.get(row.bucket, row.object_key))


def shred(session: Session, row: m.DerivedObject) -> None:
    """Destroy the derived object's data key (tombstone; the row stays for the audit trail)."""
    row.wrapped_dek = None
    row.key_state = "shredded"
    row.shredded_at = datetime.now(UTC)
    session.flush()


# ---------------------------------------------------------------- reading inputs
def _artifact_subject(session: Session, art: m.RunArtifact) -> uuid.UUID:
    return session.execute(
        select(m.Session_.subject_id)
        .join(m.Recording, m.Recording.session_id == m.Session_.id)
        .join(m.Run, m.Run.recording_id == m.Recording.id)
        .where(m.Run.id == art.run_id)
    ).scalar_one()


def read_node(session: Session, storage: Storage, node_id: uuid.UUID) -> bytes:
    """Plaintext bytes of an entity: a run artifact (subject key) or a derived object."""
    n = prov.get_node(session, node_id)
    if n is None:
        raise DerivedError("input node not found")
    if n.type == "artifact" and n.ref_id:
        art = session.scalar(select(m.RunArtifact).where(m.RunArtifact.id == uuid.UUID(n.ref_id)))
        if art is None or art.visible_at is None:
            raise DerivedError("input artifact not found or not visible")
        blob = storage.objects.get(art.bucket, art.object_key)
        sid = _artifact_subject(session, art)
        return storage.keyring.decrypt(
            str(art.tenant_id), str(sid), f"{art.bucket}/{art.object_key}", 1, blob
        )
    row = session.scalar(select(m.DerivedObject).where(m.DerivedObject.node_id == node_id))
    if row is None:
        raise DerivedError("input node has no readable content")
    return read(storage, row)


def _npy(data: bytes) -> np.ndarray:
    return np.lib.format.read_array(io.BytesIO(data), allow_pickle=False)


def _to_npy(a: np.ndarray) -> bytes:
    buf = io.BytesIO()
    np.lib.format.write_array(buf, np.ascontiguousarray(a), allow_pickle=False)
    return buf.getvalue()


# ---------------------------------------------------------------- creation
def _record(
    session: Session,
    principal: Principal,
    *,
    kind: str,
    activity_type: str,
    entity_type: str,
    inputs: list[uuid.UUID],
    data: bytes,
    bucket: str,
    filename: str,
    storage: Storage,
    params: dict[str, Any],
) -> m.DerivedObject:
    tid = str(principal.tenant_id)
    oid = uuid.uuid4()
    key = f"t/{tid}/derived/{oid}/{filename}"
    wrapped, kek_id = seal(storage, tid, str(oid), bucket, key, data)
    sha = hashlib.sha256(data).hexdigest()
    row = m.DerivedObject(
        id=oid,
        tenant_id=uuid.UUID(tid),
        kind=kind,
        bucket=bucket,
        object_key=key,
        sha256=sha,
        size_bytes=len(data),
        kek_id=kek_id,
        wrapped_dek=wrapped,
        key_state="active",
        input_node_ids=list(inputs),
        params=params,
        created_by=principal.id,
    )
    session.add(row)
    session.flush()
    nodes = [
        prov.NodeSpec(prov.ProvKind.ACTIVITY, activity_type, None, None, dict(params)),
        prov.NodeSpec(
            prov.ProvKind.ENTITY, entity_type, str(oid), f"blob:sha256:{sha}", {"kind": kind}
        ),
    ]
    edges: list[tuple[prov.NodeRef, prov.EdgeType, prov.NodeRef]] = []
    for i in inputs:
        edges.append((0, prov.EdgeType.USED, i))
        edges.append((1, prov.EdgeType.WAS_DERIVED_FROM, i))
    edges.append((1, prov.EdgeType.WAS_GENERATED_BY, 0))
    commit = prov.record(session, principal, nodes, edges)
    row.node_id = commit.node_ids[1]
    session.flush()
    return row


def create_group_average(
    session: Session,
    storage: Storage,
    principal: Principal,
    inputs: list[uuid.UUID],
    *,
    extra: dict[str, Any] | None = None,
) -> m.DerivedObject:
    """Element-wise mean of the inputs' arrays (``.npy`` artifacts of equal shape)."""
    if not inputs:
        raise DerivedError("a group average needs at least one input")
    policy.check(
        principal,
        "aggregate:create",
        policy.Resource("aggregate", str(principal.tenant_id), node_ids=tuple(inputs)),
        session=session,
    )
    arrays = [_npy(read_node(session, storage, i)) for i in inputs]
    if len({a.shape for a in arrays}) != 1:
        raise DerivedError("inputs of a group average must have the same shape")
    mean = np.mean(np.stack([a.astype(np.float64) for a in arrays]), axis=0)
    params = {"method": "mean", "n_inputs": len(inputs), **(extra or {})}
    return _record(
        session,
        principal,
        kind="group_average",
        activity_type="aggregate",
        entity_type="group_average",
        inputs=inputs,
        data=_to_npy(mean),
        bucket=ARTIFACT_BUCKET,
        filename="data.npy",
        storage=storage,
        params=params,
    )


def train_toy_model(
    session: Session,
    storage: Storage,
    principal: Principal,
    inputs: list[uuid.UUID],
    *,
    name: str = "toy",
) -> m.DerivedObject:
    """A deliberately trivial "model" (per-row mean and standard deviation of the inputs), enough
    to exercise the training policy (SEC-146) and deletion propagation. Not a real model."""
    policy.check(
        principal,
        "model:train",
        policy.Resource("model", str(principal.tenant_id), node_ids=tuple(inputs)),
        session=session,
    )
    arrays = [_npy(read_node(session, storage, i)).astype(np.float64) for i in inputs]
    flat = np.concatenate([a.reshape(a.shape[0], -1) for a in arrays], axis=1)
    weights = {
        "schema": "nf.toy-model/v1",
        "mean": [round(float(x), 9) for x in flat.mean(axis=1)],
        "std": [round(float(x), 9) for x in flat.std(axis=1)],
    }
    return _record(
        session,
        principal,
        kind="model",
        activity_type="training",
        entity_type="model",
        inputs=inputs,
        data=json.dumps(weights, sort_keys=True).encode(),
        bucket=MODEL_BUCKET,
        filename="model.json",
        storage=storage,
        params={"name": name, "algorithm": "toy-mean-std", "n_inputs": len(inputs)},
    )
