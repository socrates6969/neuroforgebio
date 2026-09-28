"""SISA on the platform (BUILD-GUIDE 6.4): checkpoints as encrypted derived objects, provenance,
policy, and the registry's ``sisa`` retrain recipe.

Worker-side glue between the pure core (``nf_train.sisa``) and ``nf_platform`` (never its API
layer; ``services/workers/.importlinter``).

**Inputs.** Each training input is a single-subject run artifact (``.npy``) holding the subject's
feature table as ``(n_features + 1, n_epochs)``: one row per feature, the last row the class label
(``nf_train.toydata.encode``; ``scale`` divides the feature rows). The subject of every input is
resolved through the provenance lineage (``policy.source_recordings``) and hashed with the
registry's ``subject_hash``; the SISA assignment works on those hashes only.

**Checkpoints.** Every ``(shard, slice)`` checkpoint is a ``derived_object`` (bucket ``models``,
its own data key, ``params.role = "sisa_checkpoint"``) and a provenance entity of type
``model_checkpoint`` that ``wasDerivedFrom`` the inputs it was trained on and the previous
checkpoint of its shard. A withdrawal's DeletionJob therefore reaches exactly the checkpoints
that contain the subject (it marks them ``stale``), and the model (flagged ``retrain_required``).

**Ensemble.** The model is a ``derived_object`` of kind ``model`` (type ``model``) derived from the
data inputs and the final checkpoint of every shard. Its ``params`` hold the SISA manifest
(config, hashed subject -> [shard, slice], checkpoint object ids), the input nodes per hashed
subject, and, after a retrain, the checkpoint audit (which checkpoints were read, written and
destroyed).

**Retrain** (:func:`retrain_recipe`, registered as recipe ``"sisa"``): only the shards holding a
withdrawn subject are retrained, from the last checkpoint before the subject's slice; the
superseded checkpoints are crypto-shredded (their data keys destroyed, a WORM shred-ledger entry
written so a restore re-applies it, SEC-124) and marked ``superseded``.

Not certified unlearning; not for real-time or safety-critical control.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

import numpy as np
from nf_platform.audit import _canonical as cj
from nf_platform.audit import log as audit
from nf_platform.db import models as m
from nf_platform.db.context import Principal
from nf_platform.governance import derived, policy
from nf_platform.provenance import api as prov
from nf_platform.registry.manifest import subject_hash
from nf_platform.storage.objects import ObjectNotFound, WormViolation
from nf_platform.storage.runtime import Storage
from sqlalchemy import select
from sqlalchemy.orm import Session

from nf_train import sisa, toydata

RECIPE = "sisa"
ALGORITHM = "sisa-logreg"
CHECKPOINT_TYPE = "model_checkpoint"
CHECKPOINT_ROLE = "sisa_checkpoint"
MODEL_KIND = "model"
AUDIT_BUCKET = "audit"
DEFAULT_SCALE = 1000.0


class SisaPlatformError(ValueError):
    pass


# ---------------------------------------------------------------- inputs
def subjects_of_inputs(
    session: Session, tenant_id: str, node_ids: Iterable[uuid.UUID]
) -> dict[str, list[uuid.UUID]]:
    """hashed subject -> its input nodes. Every input must come from exactly one subject."""
    out: dict[str, list[uuid.UUID]] = {}
    for nid in node_ids:
        subs = policy.subjects_of_recordings(session, policy.source_recordings(session, [nid]))
        if len(subs) != 1:
            raise SisaPlatformError(
                "every SISA training input must be a single-subject artifact "
                f"(node {nid} has {len(subs)} subjects)"
            )
        out.setdefault(subject_hash(tenant_id, next(iter(subs))), []).append(nid)
    return {h: sorted(v, key=str) for h, v in sorted(out.items())}


def _npy(data: bytes) -> np.ndarray:
    return np.lib.format.read_array(io.BytesIO(data), allow_pickle=False)


def loader(
    session: Session,
    storage: Storage,
    inputs: dict[str, list[uuid.UUID]],
    scale: float,
    reads: list[str],
) -> sisa.Loader:
    def load(hids: list[str]) -> sisa.SubjectData:
        out = {}
        for h in hids:
            xs, ys = [], []
            for nid in inputs[h]:
                x, y = toydata.decode(_npy(derived.read_node(session, storage, nid)), scale)
                xs.append(x)
                ys.append(y)
            out[h] = (np.concatenate(xs), np.concatenate(ys))
            reads.append(h)
        return out

    return load


# ---------------------------------------------------------------- checkpoint store
class DerivedCheckpointStore:
    """``sisa.CheckpointStore`` over encrypted derived objects + provenance."""

    def __init__(
        self,
        session: Session,
        storage: Storage,
        principal: Principal,
        inputs: dict[str, list[uuid.UUID]],
    ) -> None:
        self.s = session
        self.storage = storage
        self.principal = principal
        self.tid = str(principal.tenant_id)
        self.inputs = inputs
        self.last: dict[int, uuid.UUID] = {}  # shard -> node of its latest checkpoint
        self.nodes: dict[str, uuid.UUID] = {}  # ref -> node
        self.written: dict[tuple[int, int], uuid.UUID] = {}  # (shard, slice) -> new node
        self.discarded: list[str] = []

    def _row(self, ref: str) -> m.DerivedObject:
        row = self.s.scalar(select(m.DerivedObject).where(m.DerivedObject.id == uuid.UUID(ref)))
        if row is None or row.params.get("role") != CHECKPOINT_ROLE:
            raise sisa.SisaError(f"checkpoint {ref} not found")
        return row

    def put(self, shard: int, slice_: int, data: bytes, subjects: list[str]) -> str:
        used = sorted({n for h in subjects for n in self.inputs[h]}, key=str)
        prev = self.last.get(shard) if slice_ > 0 else None
        derived_from = used + ([prev] if prev is not None else [])
        oid = uuid.uuid4()
        key = f"t/{self.tid}/derived/{oid}/checkpoint.json"
        wrapped, kek_id = derived.seal(self.storage, self.tid, str(oid), "models", key, data)
        sha = hashlib.sha256(data).hexdigest()
        params = {
            "role": CHECKPOINT_ROLE,
            "shard": shard,
            "slice": slice_,
            "subjects": len(subjects),
        }
        row = m.DerivedObject(
            id=oid,
            tenant_id=uuid.UUID(self.tid),
            kind=MODEL_KIND,
            bucket="models",
            object_key=key,
            sha256=sha,
            size_bytes=len(data),
            kek_id=kek_id,
            wrapped_dek=wrapped,
            key_state="active",
            input_node_ids=derived_from,
            params=params,
            created_by=self.principal.id,
        )
        self.s.add(row)
        self.s.flush()
        nodes = [
            prov.NodeSpec(prov.ProvKind.ACTIVITY, "sisa_slice_training", None, None, dict(params)),
            prov.NodeSpec(
                prov.ProvKind.ENTITY,
                CHECKPOINT_TYPE,
                str(oid),
                f"blob:sha256:{sha}",
                {"kind": CHECKPOINT_ROLE, "shard": shard, "slice": slice_},
            ),
        ]
        edges: list[tuple[prov.NodeRef, prov.EdgeType, prov.NodeRef]] = []
        for i in derived_from:
            edges.append((0, prov.EdgeType.USED, i))
            edges.append((1, prov.EdgeType.WAS_DERIVED_FROM, i))
        edges.append((1, prov.EdgeType.WAS_GENERATED_BY, 0))
        commit = prov.record(self.s, self.principal, nodes, edges)
        row.node_id = commit.node_ids[1]
        self.s.flush()
        ref = str(oid)
        self.last[shard] = row.node_id
        self.nodes[ref] = row.node_id
        self.written[(shard, slice_)] = row.node_id
        return ref

    def get(self, ref: str) -> bytes:
        row = self._row(ref)
        data = derived.read(self.storage, row)
        self.last[int(row.params["shard"])] = row.node_id
        self.nodes[ref] = row.node_id
        return data

    def node_of(self, ref: str) -> uuid.UUID:
        if ref not in self.nodes:
            self.nodes[ref] = self._row(ref).node_id
        return self.nodes[ref]

    def discard(self, ref: str) -> None:
        """Crypto-shred a superseded checkpoint (SEC-034 style) and record it for restores."""
        row = self._row(ref)
        if row.key_state != "shredded":
            with contextlib.suppress(ObjectNotFound):
                self.storage.objects.delete(row.bucket, row.object_key)
            derived.shred(self.s, row)
            with contextlib.suppress(WormViolation):
                self.storage.objects.put(
                    AUDIT_BUCKET,
                    f"shred-ledger/{self.tid}/derived-{row.id}.json",
                    cj.canonicalize(
                        {
                            "schema": "nf.shred-ledger/v1",
                            "tenant": self.tid,
                            "derived_object": str(row.id),
                            "reason": "sisa checkpoint superseded by a retrain",
                            "at": datetime.now(UTC).isoformat(timespec="milliseconds"),
                        }
                    ),
                )
        if row.node_id is not None:
            st = self.s.get(m.ArtifactStatus, (uuid.UUID(self.tid), row.node_id))
            st = st or m.ArtifactStatus(tenant_id=uuid.UUID(self.tid), node_id=row.node_id)
            st.status = "superseded"
            st.replaced_by = self.written.get((int(row.params["shard"]), int(row.params["slice"])))
            st.updated_at = datetime.now(UTC)
            self.s.merge(st)
        self.discarded.append(ref)


# ---------------------------------------------------------------- ensemble object
def _seal_model(
    session: Session,
    storage: Storage,
    principal: Principal,
    result: sisa.TrainResult,
    store: DerivedCheckpointStore,
    inputs: dict[str, list[uuid.UUID]],
    extra: dict[str, Any],
) -> m.DerivedObject:
    tid = str(principal.tenant_id)
    data = result.model.to_bytes()
    oid = uuid.uuid4()
    key = f"t/{tid}/derived/{oid}/model.json"
    wrapped, kek_id = derived.seal(storage, tid, str(oid), "models", key, data)
    sha = hashlib.sha256(data).hexdigest()
    cfg = result.manifest["config"]
    finals = [
        store.node_of(result.manifest["checkpoints"][f"{k}/{cfg['slices'] - 1}"])
        for k in range(cfg["shards"])
    ]
    data_inputs = sorted({n for ns in inputs.values() for n in ns}, key=str)
    params = {
        "algorithm": ALGORITHM,
        "recipe": RECIPE,
        "sisa": result.manifest,
        "inputs": {h: [str(n) for n in ns] for h, ns in sorted(inputs.items())},
        "scale": extra.pop("scale"),
        **extra,
    }
    row = m.DerivedObject(
        id=oid,
        tenant_id=uuid.UUID(tid),
        kind=MODEL_KIND,
        bucket="models",
        object_key=key,
        sha256=sha,
        size_bytes=len(data),
        kek_id=kek_id,
        wrapped_dek=wrapped,
        key_state="active",
        input_node_ids=data_inputs,
        params=params,
        created_by=principal.id,
    )
    session.add(row)
    session.flush()
    attrs = {
        "algorithm": ALGORITHM,
        "shards": cfg["shards"],
        "slices": cfg["slices"],
        "seed": cfg["seed"],
        "subjects": len(inputs),
    }
    nodes = [
        prov.NodeSpec(prov.ProvKind.ACTIVITY, "training", None, None, attrs),
        prov.NodeSpec(
            prov.ProvKind.ENTITY, "model", str(oid), f"blob:sha256:{sha}", {"kind": "model"}
        ),
    ]
    edges: list[tuple[prov.NodeRef, prov.EdgeType, prov.NodeRef]] = []
    for i in data_inputs + finals:
        edges.append((0, prov.EdgeType.USED, i))
        edges.append((1, prov.EdgeType.WAS_DERIVED_FROM, i))
    edges.append((1, prov.EdgeType.WAS_GENERATED_BY, 0))
    commit = prov.record(session, principal, nodes, edges)
    row.node_id = commit.node_ids[1]
    session.flush()
    return row


def _audit(principal: Principal, row: m.DerivedObject, phase: str, count: int) -> None:
    audit.emit(
        audit.AuditEvent(
            type=audit.DATA_CREATE,
            outcome="success",
            action="model:train",
            tenant_id=str(principal.tenant_id),
            actor_kind=principal.kind,
            actor_id=principal.id,
            auth_method=principal.auth_method,
            resource_type="derived_object",
            resource_id=str(row.id),
            details={"phase": phase, "count": count, "method": ALGORITHM},
        )
    )


def _policy(session: Session, principal: Principal, nodes: list[uuid.UUID]) -> None:
    policy.check(
        principal,
        "model:train",
        policy.Resource("model", str(principal.tenant_id), node_ids=tuple(nodes)),
        session=session,
    )


def train_sisa(
    session: Session,
    storage: Storage,
    principal: Principal,
    input_node_ids: Iterable[uuid.UUID],
    cfg: sisa.SisaConfig,
    *,
    scale: float = DEFAULT_SCALE,
) -> m.DerivedObject:
    """Full SISA training on single-subject inputs; returns the ensemble's derived object. Register
    it with ``registry.service.register_version(weights_object=ObjectRef(derived_object_id=row.id),
    training_manifest=manifest_for(row))``."""
    nodes = sorted(set(input_node_ids), key=str)
    if not nodes:
        raise SisaPlatformError("no training inputs")
    _policy(session, principal, nodes)  # SEC-146: model_training consent of every subject
    inputs = subjects_of_inputs(session, str(principal.tenant_id), nodes)
    reads: list[str] = []
    data = loader(session, storage, inputs, scale, reads)(sorted(inputs))
    store = DerivedCheckpointStore(session, storage, principal, inputs)
    result = sisa.train(cfg, data, store)
    row = _seal_model(session, storage, principal, result, store, inputs, {"scale": scale})
    _audit(principal, row, "sisa_train", len(result.manifest["checkpoints"]))
    return row


def manifest_for(row: m.DerivedObject) -> Any:
    """The registry TrainingManifest of a SISA ensemble object."""
    from nf_platform.registry.service import TrainingManifest

    man = row.params["sisa"]
    return TrainingManifest(
        input_node_ids=tuple(row.input_node_ids),
        shards={h: int(kr[0]) for h, kr in man["assignment"].items()},
        excluded_subject_hashes=tuple(man.get("withdrawn") or ()),
        recipe=RECIPE,
    )


def load_model(storage: Storage, row: m.DerivedObject) -> sisa.SisaModel:
    return sisa.SisaModel.from_doc(json.loads(derived.read(storage, row)))


def retrain_without(
    session: Session,
    storage: Storage,
    principal: Principal,
    parent_row: m.DerivedObject,
    excluded: Iterable[str],
) -> tuple[m.DerivedObject, dict[str, Any]]:
    """Retrain only the affected shards of a SISA ensemble without the ``excluded`` hashed
    subjects. Returns (new ensemble object, checkpoint audit)."""
    if parent_row.params.get("recipe") != RECIPE:
        raise SisaPlatformError("not a SISA model")
    man = parent_row.params["sisa"]
    gone = sorted(set(excluded) & set(man["assignment"]))
    if not gone:
        raise SisaPlatformError("none of the excluded subjects is in the training manifest")
    all_inputs = {h: [uuid.UUID(n) for n in ns] for h, ns in parent_row.params["inputs"].items()}
    inputs = {h: ns for h, ns in all_inputs.items() if h not in set(gone)}
    remaining_nodes = sorted({n for ns in inputs.values() for n in ns}, key=str)
    if remaining_nodes:
        _policy(session, principal, remaining_nodes)
    scale = float(parent_row.params.get("scale", DEFAULT_SCALE))
    reads: list[str] = []
    store = DerivedCheckpointStore(session, storage, principal, inputs)
    audited = sisa.AuditedStore(store)
    previous = load_model(storage, parent_row)
    result = sisa.retrain_without(
        man, gone, loader(session, storage, inputs, scale, reads), audited, previous
    )
    checkpoint_audit = {
        "read": sorted([e.shard, e.slice] for e in audited.log if e.op == "read"),
        "written": sorted([e.shard, e.slice] for e in audited.log if e.op == "write"),
        "discarded": sorted([e.shard, e.slice] for e in audited.log if e.op == "discard"),
        "shards_retrained": result.retrained_shards,
        "subjects_loaded": len(set(reads)),
        "withdrawn": len(gone),
    }
    row = _seal_model(
        session,
        storage,
        principal,
        result,
        store,
        inputs,
        {"scale": scale, "parent": str(parent_row.id), "checkpoint_audit": checkpoint_audit},
    )
    _audit(principal, row, "sisa_retrain", len(checkpoint_audit["written"]))
    return row, checkpoint_audit


def retrain_recipe(
    session: Session,
    storage: Storage,
    principal: Principal,
    inputs: list[uuid.UUID],
    *,
    parent: m.ModelVersion,
    excluded: set[str],
) -> m.DerivedObject:
    """``registry.retrain`` recipe ``"sisa"``: the parent version's ensemble, retrained without the
    excluded (hashed) subjects. ``inputs`` (the registry's remaining input nodes) is not needed:
    the ensemble records its inputs per hashed subject."""
    row = session.scalar(
        select(m.DerivedObject).where(m.DerivedObject.id == parent.derived_object_id)
    )
    if row is None:
        raise SisaPlatformError("the parent version's weights object is missing")
    new, _audit_doc = retrain_without(session, storage, principal, row, excluded)
    return new
