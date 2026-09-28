"""Governed model registry (BUILD-GUIDE 6.1-6.3; BLUEPRINT §3.7, §8.4; SEC-061, SEC-092,
SEC-143-SEC-145). Interface: M6-CONTRACTS §2.

- :func:`register_model` / :func:`register_version` (6.1): a version is a weights artifact stored
  encrypted as a derived object with its own data key, a training-set manifest of hashed subject
  IDs (computed from the provenance lineage of the training inputs, never trusted from the
  client), pipeline versions, a code commit, ``intended_use`` and ``use_restrictions``.
  Registering without a manifest fails. Training data use is policy-checked as ``model:train``
  (consent scope ``model_training`` for every contributing subject, SEC-146).
- :func:`request_deployment` (6.2): every request declares a context (jurisdiction, setting,
  purpose); prohibited combinations are refused, stored (``state='refused'`` + reasons) and
  audited. Control settings (SEC-092) are always refused.
- :func:`retrain_required` / :func:`taint` (6.3): read the M5 ``model_flag`` rows of the version's
  model node (written by the DeletionJob); :func:`deployments_blocked` applies the tenant policy
  recorded on each flag. :func:`request_retrain` queues ``registry.retrain``
  (:mod:`nf_platform.registry.retrain`).
- :func:`approve` / :func:`publish` (SEC-143): versions are private to the tenant; publication
  needs a card with a privacy-risk section, two approvers other than the publisher and the
  ``commercial_use`` consent scope of every training subject.
- Uploaded weights (AppSec M3): the platform cannot verify offline training, so the lineage of an
  ``upload`` version is the uploader's declaration. The manifest records ``weights_source``; the
  version needs a governance approver other than the uploader before it is deployed, and its
  publication approvers must be neither the publisher nor the uploader; ANY subject withdrawal in
  the tenant after its registration flags it (``governance.deletion``, reason
  :data:`UPLOAD_TAINT_REASON`). Withdrawal propagation is exact only for ``platform`` versions.

Not certified unlearning; not intended for real-time or safety-critical control.
"""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from nf_platform.audit import _canonical as cj
from nf_platform.audit import log as audit
from nf_platform.auth.authorize import effective_roles
from nf_platform.db import models as m
from nf_platform.db.context import Principal
from nf_platform.governance import derived, policy
from nf_platform.jobs import queue
from nf_platform.provenance import api as prov
from nf_platform.registry import manifest as mf
from nf_platform.registry import vocab, weights
from nf_platform.registry.card import ModelCard
from nf_platform.storage.runtime import Storage

log = logging.getLogger(__name__)

RETRAIN_KIND = "registry.retrain"
DEPLOYMENT_AUDIT = "registry.deployment"
CODE_COMMIT_RE = re.compile(r"^[0-9a-f]{7,64}$")
PV_ID_RE = re.compile(r"^pv:sha256:[0-9a-f]{64}$")
MODEL_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
MAX_INPUTS = 10_000
UPLOAD_TAINT_REASON = "unverifiable lineage (uploaded weights)"
LINEAGE_TAINT_REASON = "a training subject withdrew consent"


@dataclass(frozen=True)
class ObjectRef:
    """The weights of a version: EITHER a model derived object already on the platform (the
    output of a training job, e.g. ``derived.train_toy_model`` or SISA) OR uploaded bytes, which
    the registry seals under a new data key. Uploaded weights are accepted only as safetensors or
    ONNX (SEC-061) and are never deserialised."""

    derived_object_id: uuid.UUID | None = None
    data: bytes | None = None
    format: str | None = None  # "safetensors" | "onnx" for uploads


@dataclass(frozen=True)
class TrainingManifest:
    """What the version was trained on. ``input_node_ids`` are provenance entity ids (recordings,
    run artifacts, derived objects); the registry resolves every contributing subject through the
    lineage and hashes it (``manifest.subject_hash``). ``subject_hashes``, when given, must equal
    the computed set. ``shards`` maps subject hash -> shard index (SISA, 6.4)."""

    input_node_ids: tuple[uuid.UUID, ...]
    subject_hashes: tuple[str, ...] | None = None
    shards: Mapping[str, int] | None = None
    excluded_subject_hashes: tuple[str, ...] = ()
    recipe: str | None = None


@dataclass(frozen=True)
class DeploymentContext:
    jurisdiction: str  # "EU", an ISO 3166-1 alpha-2 code, or a subdivision such as "US-CO"
    setting: str  # vocabulary in registry.vocab.SETTINGS
    purpose: str
    exception_id: uuid.UUID | None = None  # documented medical/safety exception (Art. 5(1)(f))
    outputs: str = "labels"  # SEC-144: labels | coarse_scores
    rate_limit_per_minute: int = 60
    influences_behaviour: bool = False  # Art. 5(1)(a)
    extra: Mapping[str, str] = field(default_factory=dict)


class RegistryError(ValueError):
    def __init__(self, status: int, detail: str, code: str | None = None) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.code = code


@dataclass(frozen=True)
class Flag:
    """One consent-taint flag of a version (an M5 ``model_flag`` row)."""

    deletion_job_id: uuid.UUID
    created_at: datetime
    block_deployments: bool
    reason: str = LINEAGE_TAINT_REASON


# ---------------------------------------------------------------- helpers
def _tid(principal: Principal) -> uuid.UUID:
    return uuid.UUID(str(principal.tenant_id))


def _emit(
    principal: Principal,
    type_: str,
    outcome: audit.Outcome,
    action: str,
    resource_type: str,
    resource_id: Any,
    **details: Any,
) -> None:
    audit.emit(
        audit.AuditEvent(
            type=type_,
            outcome=outcome,
            action=action,
            tenant_id=str(principal.tenant_id),
            actor_kind=principal.kind,
            actor_id=principal.id,
            auth_method=principal.auth_method,
            resource_type=resource_type,
            resource_id=str(resource_id),
            details=details,
        )
    )


def card_digest(card: Mapping[str, Any]) -> str:
    return hashlib.sha256(cj.canonicalize(dict(card))).hexdigest()


def get_model(session: Session, model_id: uuid.UUID) -> m.Model:
    row = session.scalar(select(m.Model).where(m.Model.id == model_id))
    if row is None:
        raise RegistryError(404, "model")
    return row


def get_version(session: Session, model_id: uuid.UUID, number: int) -> m.ModelVersion:
    row = session.scalar(
        select(m.ModelVersion).where(
            m.ModelVersion.model_id == model_id, m.ModelVersion.version == number
        )
    )
    if row is None:
        raise RegistryError(404, "model version")
    return row


def _version_by_id(session: Session, version_id: uuid.UUID) -> m.ModelVersion:
    row = session.scalar(select(m.ModelVersion).where(m.ModelVersion.id == version_id))
    if row is None:
        raise RegistryError(404, "model version")
    return row


# ---------------------------------------------------------------- 6.1 models
def register_model(
    session: Session, principal: Principal, *, name: str, card: ModelCard
) -> m.Model:
    if not MODEL_NAME_RE.match(name):
        raise RegistryError(422, "model name: letters, digits, '.', '_' or '-' (max 128)")
    if session.scalar(select(m.Model.id).where(m.Model.name == name)) is not None:
        raise RegistryError(409, "a model with this name exists")
    doc = card.model_dump(mode="json")
    row = m.Model(
        id=uuid.uuid4(),
        tenant_id=_tid(principal),
        name=name,
        card=doc,
        card_sha256=card_digest(doc),
        created_by=principal.id,
    )
    session.add(row)
    session.flush()
    session.refresh(row)
    return row


def _resolve_pipelines(session: Session, refs: list[str]) -> list[str]:
    """``name@version`` labels or ``pv:sha256:...`` ids of published PipelineVersions -> pv ids."""
    out: list[str] = []
    for ref in refs:
        if PV_ID_RE.match(ref):
            pv = session.scalar(
                select(m.PipelineVersion.pv_id).where(m.PipelineVersion.pv_id == ref).limit(1)
            )
        elif "@" in ref:
            name, _, version = ref.rpartition("@")
            pv = session.scalar(
                select(m.PipelineVersion.pv_id).where(
                    m.PipelineVersion.name == name, m.PipelineVersion.version == version
                )
            )
        else:
            pv = None
        if pv is None:
            raise RegistryError(422, f"pipeline version {ref!r} is not published in this tenant")
        out.append(pv)
    return sorted(set(out))


def _seal_upload(
    session: Session,
    storage: Storage,
    principal: Principal,
    data: bytes,
    fmt: str,
    inputs: list[uuid.UUID],
) -> m.DerivedObject:
    """Uploaded weights (SEC-061: structure-checked, never deserialised) sealed as a model
    derived object with its own data key; provenance: ``model_registration`` used the declared
    inputs, the ``model`` entity wasDerivedFrom them (so a withdrawal reaches it, 5.5)."""
    tid = str(principal.tenant_id)
    oid = uuid.uuid4()
    ext = "safetensors" if fmt == "safetensors" else "onnx"
    key = f"t/{tid}/derived/{oid}/model.{ext}"
    wrapped, kek_id = derived.seal(storage, tid, str(oid), derived.MODEL_BUCKET, key, data)
    sha = hashlib.sha256(data).hexdigest()
    params = {"source": "upload", "weights_format": fmt, "n_inputs": len(inputs)}
    row = m.DerivedObject(
        id=oid,
        tenant_id=uuid.UUID(tid),
        kind="model",
        bucket=derived.MODEL_BUCKET,
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
        prov.NodeSpec(prov.ProvKind.ACTIVITY, "model_registration", None, None, dict(params)),
        prov.NodeSpec(
            prov.ProvKind.ENTITY, "model", str(oid), f"blob:sha256:{sha}", {"kind": "model"}
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


def _platform_weights(session: Session, oid: uuid.UUID, inputs: set[uuid.UUID]) -> m.DerivedObject:
    row = session.scalar(select(m.DerivedObject).where(m.DerivedObject.id == oid))
    if row is None or row.kind != "model" or row.node_id is None:
        raise RegistryError(422, "weights object: no model derived object with this id")
    if row.key_state != "active":
        raise RegistryError(422, "weights object: its data key was destroyed")
    if set(row.input_node_ids) != inputs:
        raise RegistryError(
            422,
            "training manifest: input_node_ids must equal the inputs the weights were derived from",
        )
    return row


def register_version(
    session: Session,
    principal: Principal,
    model_id: uuid.UUID,
    *,
    weights_object: ObjectRef,
    training_manifest: TrainingManifest | None,
    pipeline_version_ids: list[str],
    code_commit: str,
    intended_use: str,
    use_restrictions: list[str],
    parent_version_id: uuid.UUID | None = None,
    storage: Storage | None = None,
) -> m.ModelVersion:
    """Register a version (6.1). Raises RegistryError (4xx) or PolicyDenied (403)."""
    if training_manifest is None:
        raise RegistryError(422, "a training-set manifest is required", "manifest_required")
    inputs = list(dict.fromkeys(training_manifest.input_node_ids))
    if not inputs:
        raise RegistryError(422, "the training-set manifest lists no input", "manifest_required")
    if len(inputs) > MAX_INPUTS:
        raise RegistryError(422, f"at most {MAX_INPUTS} training inputs")
    model = get_model(session, model_id)
    if not CODE_COMMIT_RE.match(code_commit):
        raise RegistryError(422, "code_commit must be a hex git commit id (7-64 characters)")
    if not intended_use.strip():
        raise RegistryError(422, "intended_use is required")
    unknown = vocab.unknown_restrictions(use_restrictions)
    if unknown:
        raise RegistryError(422, f"unknown use restriction(s): {', '.join(unknown)}")
    restrictions = sorted(
        set(use_restrictions) | vocab.derived_restrictions(model.card.get("inferences", []))
    )
    parent = None
    if parent_version_id is not None:
        parent = _version_by_id(session, parent_version_id)
        if parent.model_id != model.id:
            raise RegistryError(422, "parent version belongs to another model")
    for nid in inputs:
        n = prov.get_node(session, nid)
        if n is None or n.kind is not prov.ProvKind.ENTITY:
            raise RegistryError(422, "training manifest: an input node is not an entity here")
    pv_ids = _resolve_pipelines(session, list(pipeline_version_ids))

    # SEC-146: every contributing subject holds model_training (fails closed)
    policy.check(
        principal,
        "model:train",
        policy.Resource("model", str(principal.tenant_id), str(model.id), node_ids=tuple(inputs)),
        session=session,
    )
    subjects, recs = mf.training_subjects(session, inputs)
    tid = str(principal.tenant_id)
    hashes = {mf.subject_hash(tid, s) for s in subjects}
    if not hashes:
        raise RegistryError(422, "no training subject could be resolved from the inputs")
    if (
        training_manifest.subject_hashes is not None
        and set(training_manifest.subject_hashes) != hashes
    ):
        raise RegistryError(
            422, "training manifest: subject_hashes differ from the subjects of the inputs"
        )
    shards = dict(training_manifest.shards or {})
    if shards and set(shards) != hashes:
        raise RegistryError(422, "training manifest: shards must assign exactly the subjects")
    excluded = set(training_manifest.excluded_subject_hashes)
    if excluded & hashes:
        raise RegistryError(
            422,
            "training manifest: an excluded subject still contributes to the inputs",
            "excluded_subject_present",
        )

    if weights_object.derived_object_id is not None:
        if weights_object.data is not None:
            raise RegistryError(422, "weights: give a derived object id OR uploaded data")
        obj = _platform_weights(session, weights_object.derived_object_id, set(inputs))
        fmt = str(obj.params.get("weights_format") or f"platform/{obj.params.get('algorithm')}")
    elif weights_object.data is not None:
        if storage is None:
            raise RegistryError(500, "no object storage configured")
        try:
            fmt = weights.check(weights_object.data, weights_object.format)
        except weights.WeightsError as e:
            raise RegistryError(422, str(e), "weights_rejected") from e
        obj = _seal_upload(session, storage, principal, weights_object.data, fmt, inputs)
    else:
        raise RegistryError(422, "weights are required")
    source = "platform" if weights_object.derived_object_id is not None else "upload"

    number = (
        session.scalar(
            select(func.max(m.ModelVersion.version)).where(m.ModelVersion.model_id == model.id)
        )
        or 0
    ) + 1
    recipe = training_manifest.recipe
    doc, digest = mf.build(
        tenant_id=tid,
        input_node_ids=inputs,
        subject_hashes=hashes,
        n_source_recordings=len(recs),
        shards=shards or None,
        excluded_subject_hashes=excluded,
        pipeline_version_ids=pv_ids,
        code_commit=code_commit,
        recipe=recipe,
        parent_version_id=parent.id if parent else None,
        weights_source=source,
    )
    row = m.ModelVersion(
        id=uuid.uuid4(),
        tenant_id=_tid(principal),
        model_id=model.id,
        version=number,
        derived_object_id=obj.id,
        weights_format=fmt,
        weights_sha256=obj.sha256,
        prov_node_id=obj.node_id,
        manifest=doc,
        manifest_sha256=digest,
        pipeline_version_ids=pv_ids,
        code_commit=code_commit,
        intended_use=vocab.with_control_statement(intended_use),
        use_restrictions=restrictions,
        recipe=recipe,
        parent_version_id=parent.id if parent else None,
        created_by=principal.id,
    )
    session.add(row)
    session.flush()
    session.refresh(row)
    return row


def weights_source(session: Session, version: m.ModelVersion) -> str:
    """``platform`` or ``upload`` (AppSec M3). Manifests written before the amendment carry no
    ``weights_source``: the weights object's ``params.source`` decides (set by ``_seal_upload``).
    """
    src = (version.manifest or {}).get("weights_source")
    if src in mf.WEIGHTS_SOURCES:
        return str(src)
    params = session.scalar(
        select(m.DerivedObject.params).where(m.DerivedObject.id == version.derived_object_id)
    )
    return "upload" if (params or {}).get("source") == "upload" else "platform"


# ---------------------------------------------------------------- 6.3 taint
def taint(session: Session, version: m.ModelVersion) -> list[Flag]:
    rows = list(
        session.scalars(
            select(m.ModelFlag)
            .where(m.ModelFlag.model_node_id == version.prov_node_id)
            .order_by(m.ModelFlag.created_at, m.ModelFlag.deletion_job_id)
        )
    )
    if not rows:
        return []
    upload_only: set[uuid.UUID] = set()
    if weights_source(session, version) == "upload":
        # a flag whose withdrawn subject is not in the declared lineage exists only because the
        # lineage is unverifiable
        declared = set((version.manifest or {}).get("subjects") or ())
        jobs = session.execute(
            select(m.DeletionJob.id, m.DeletionJob.subject_id).where(
                m.DeletionJob.id.in_([r.deletion_job_id for r in rows])
            )
        ).all()
        upload_only = {
            j for j, sid in jobs if mf.subject_hash(version.tenant_id, sid) not in declared
        }
    return [
        Flag(
            r.deletion_job_id,
            r.created_at,
            r.block_deployments,
            UPLOAD_TAINT_REASON if r.deletion_job_id in upload_only else LINEAGE_TAINT_REASON,
        )
        for r in rows
    ]


def _second_approvers(session: Session, version: m.ModelVersion, *, exclude: set[str]) -> set[str]:
    """Governance approvers of ``version`` other than ``exclude`` (four-eyes)."""
    return {
        a.approver_id
        for a in approvals(session, version)
        if a.approver_id not in exclude and set(a.approver_roles) & policy.APPROVER_ROLES
    }


def retrain_required(session: Session, version_id: uuid.UUID) -> bool:
    return bool(taint(session, _version_by_id(session, version_id)))


def deployments_blocked(session: Session, version: m.ModelVersion) -> bool:
    return any(f.block_deployments for f in taint(session, version))


def withdrawn_subject_hashes(session: Session, version: m.ModelVersion) -> set[str]:
    """Hashes of the subjects whose withdrawal flagged this version (their DeletionJobs)."""
    job_ids = [f.deletion_job_id for f in taint(session, version)]
    if not job_ids:
        return set()
    sids = session.scalars(select(m.DeletionJob.subject_id).where(m.DeletionJob.id.in_(job_ids)))
    return {mf.subject_hash(version.tenant_id, s) for s in sids}


# ---------------------------------------------------------------- 6.2 deployments
def _exception_view(row: m.ModelUseException) -> vocab.ExceptionView:
    return vocab.ExceptionView(
        model_id=str(row.model_id),
        basis=row.basis,
        jurisdiction=row.jurisdiction,
        setting=row.setting,
        evidence_ref=row.evidence_ref,
    )


def validate_context(context: DeploymentContext) -> None:
    if not vocab.JURISDICTION_RE.match(context.jurisdiction):
        raise RegistryError(422, "jurisdiction: 'EU', an ISO 3166-1 alpha-2 code or e.g. 'US-CO'")
    if context.setting not in vocab.SETTINGS:
        raise RegistryError(422, f"setting: one of {', '.join(sorted(vocab.SETTINGS))}")
    if context.outputs not in vocab.OUTPUTS:
        raise RegistryError(422, f"outputs: one of {', '.join(vocab.OUTPUTS)}")
    if not 1 <= context.rate_limit_per_minute <= vocab.RATE_LIMIT_MAX:
        raise RegistryError(422, f"rate_limit_per_minute: 1..{vocab.RATE_LIMIT_MAX}")
    if not context.purpose.strip():
        raise RegistryError(422, "purpose is required")


def context_doc(context: DeploymentContext) -> dict[str, Any]:
    return {
        "jurisdiction": context.jurisdiction,
        "setting": context.setting,
        "purpose": context.purpose,
        "exception_id": None if context.exception_id is None else str(context.exception_id),
        "outputs": context.outputs,
        "rate_limit_per_minute": context.rate_limit_per_minute,
        "influences_behaviour": context.influences_behaviour,
        "extra": dict(context.extra),
    }


def request_deployment(
    session: Session, principal: Principal, version_id: uuid.UUID, *, context: DeploymentContext
) -> m.ModelDeployment:
    """Evaluate a deployment request (6.2). The row is stored either way (``approved`` or
    ``refused`` + reason codes) and the decision is audited; a refusal is returned, not raised,
    so the caller can commit it before answering."""
    validate_context(context)
    version = _version_by_id(session, version_id)
    model = get_model(session, version.model_id)
    exc = None
    if context.exception_id is not None:
        exc = session.scalar(
            select(m.ModelUseException).where(m.ModelUseException.id == context.exception_id)
        )
    reasons = vocab.evaluate(
        version.use_restrictions,
        model_id=str(model.id),
        jurisdiction=context.jurisdiction,
        setting=context.setting,
        outputs=context.outputs,
        influences_behaviour=context.influences_behaviour,
        exception=None if exc is None else _exception_view(exc),
    )
    if context.exception_id is not None and exc is None and vocab.R_EXCEPTION not in reasons:
        reasons.append(vocab.R_EXCEPTION)
    if deployments_blocked(session, version):
        reasons.append(vocab.R_RETRAIN)
    # AppSec M3: an uploaded (self-declared lineage) version needs a second person's approval
    if weights_source(session, version) == "upload" and not _second_approvers(
        session, version, exclude={version.created_by}
    ):
        reasons.append(vocab.R_UPLOAD_APPROVAL)
    row = m.ModelDeployment(
        id=uuid.uuid4(),
        tenant_id=_tid(principal),
        model_id=model.id,
        version_id=version.id,
        jurisdiction=context.jurisdiction,
        setting=context.setting,
        purpose=context.purpose,
        context=context_doc(context),
        exception_id=None if exc is None else exc.id,
        state="refused" if reasons else "approved",
        reasons=reasons,
        requested_by=principal.id,
    )
    session.add(row)
    session.flush()
    session.refresh(row)
    if reasons:
        _emit(
            principal,
            DEPLOYMENT_AUDIT,
            "denied",
            "model:deploy",
            "model_deployment",
            row.id,
            decision="refused",
            reason=",".join(reasons),
            policy=context.setting,
        )
    else:
        _emit(
            principal,
            DEPLOYMENT_AUDIT,
            "success",
            "model:deploy",
            "model_deployment",
            row.id,
            decision="approved",
            policy=context.setting,
        )
    return row


def effective_state(session: Session, dep: m.ModelDeployment, blocked: bool | None = None) -> str:
    """``approved`` deployments become ``blocked`` once the version is tainted and the tenant
    policy blocks deployments (6.3)."""
    if dep.state != "approved":
        return dep.state
    if blocked is None:
        blocked = deployments_blocked(session, _version_by_id(session, dep.version_id))
    return "blocked" if blocked else "approved"


def record_exception(
    session: Session,
    principal: Principal,
    model_id: uuid.UUID,
    *,
    basis: str,
    jurisdiction: str,
    setting: str,
    justification: str,
    evidence_ref: str,
) -> m.ModelUseException:
    """A documented medical or safety exception (Art. 5(1)(f)). It never lifts SEC-092."""
    model = get_model(session, model_id)
    if basis not in m.EXCEPTION_BASES:
        raise RegistryError(422, "basis: medical or safety")
    if not vocab.JURISDICTION_RE.match(jurisdiction):
        raise RegistryError(422, "jurisdiction: 'EU', an ISO 3166-1 alpha-2 code or e.g. 'US-CO'")
    if setting not in vocab.ART_5_1_F_SETTINGS:
        raise RegistryError(422, "an exception applies to the workplace or education setting")
    if not justification.strip() or not evidence_ref.strip():
        raise RegistryError(422, "justification and evidence_ref are required")
    row = m.ModelUseException(
        id=uuid.uuid4(),
        tenant_id=_tid(principal),
        model_id=model.id,
        basis=basis,
        jurisdiction=jurisdiction,
        setting=setting,
        justification=justification,
        evidence_ref=evidence_ref,
        recorded_by=principal.id,
    )
    session.add(row)
    session.flush()
    session.refresh(row)
    return row


# ---------------------------------------------------------------- SEC-143 publication
def approve(session: Session, principal: Principal, version: m.ModelVersion) -> m.ModelApproval:
    """Record the caller's approval of a version's publication (idempotent)."""
    row = session.get(m.ModelApproval, (_tid(principal), version.id, principal.id))
    if row is not None:
        return row
    row = m.ModelApproval(
        tenant_id=_tid(principal),
        version_id=version.id,
        approver_id=principal.id,
        approver_roles=sorted(effective_roles(principal)),
    )
    session.add(row)
    session.flush()
    session.refresh(row)
    return row


def approvals(session: Session, version: m.ModelVersion) -> list[m.ModelApproval]:
    return list(
        session.scalars(
            select(m.ModelApproval)
            .where(m.ModelApproval.version_id == version.id)
            .order_by(m.ModelApproval.created_at, m.ModelApproval.approver_id)
        )
    )


def publish(session: Session, principal: Principal, version: m.ModelVersion) -> m.ModelVersion:
    """SEC-143: private by default; publication needs the card's privacy-risk section, four-eyes
    approval and ``commercial_use`` consent of every training subject; a tainted version is never
    published (the final taint check runs under the version's row lock, shared with the taint
    writer ``governance.deletion.flag_models``)."""
    if version.visibility == "published":
        return version
    model = get_model(session, version.model_id)
    if not model.card.get("privacy_risk"):
        raise RegistryError(
            422,
            "publication needs a model card with a privacy-risk section (membership inference "
            "on a held-out split, SEC-143)",
            "privacy_risk_required",
        )
    if taint(session, version):
        raise RegistryError(409, "the version is retrain_required", vocab.R_RETRAIN)
    policy.check(
        principal,
        "model:publish",
        policy.Resource(
            "model",
            str(principal.tenant_id),
            str(model.id),
            node_ids=tuple(uuid.UUID(i) for i in version.manifest["inputs"]),
        ),
        session=session,
        approvals=[
            policy.Approval(a.approver_id, frozenset(a.approver_roles))
            for a in approvals(session, version)
        ],
    )
    exclude = {principal.id}
    if weights_source(session, version) == "upload":
        exclude.add(version.created_by)  # AppSec M3: the uploader's approval does not count
    if len(_second_approvers(session, version, exclude=exclude)) < 2:
        raise RegistryError(
            403,
            "four-eyes approval required: two approvers with a governance role other than the "
            "publisher (and, for uploaded weights, the uploader) (SEC-143, SEC-024)",
            "four_eyes_required",
        )
    # BUG-HUNT M3: a withdrawal may have flagged the version since the taint read above. Lock the
    # version row (every taint writer, ``deletion.flag_models``, takes the same row lock before it
    # inserts a model_flag) and re-read the taint under it: a flag committed before this point is
    # seen, and a writer arriving later waits for this transaction, so it cannot slip in between.
    session.refresh(version, with_for_update=True)
    if version.visibility == "published":
        return version
    if taint(session, version):
        raise RegistryError(409, "the version is retrain_required", vocab.R_RETRAIN)
    version.visibility = "published"
    version.published_at = datetime.now(UTC)
    version.published_by = principal.id
    session.flush()
    return version


# ---------------------------------------------------------------- 6.3 retrain requests
def _active_retrain(session: Session, version_id: uuid.UUID) -> m.ModelRetrain | None:
    return session.scalar(
        select(m.ModelRetrain).where(
            m.ModelRetrain.version_id == version_id,
            m.ModelRetrain.state.in_(m.RETRAIN_ACTIVE_STATES),
        )
    )


def request_retrain(
    session: Session, principal: Principal, version: m.ModelVersion, *, recipe: str | None
) -> tuple[m.ModelRetrain, bool]:
    """Queue ``registry.retrain`` for ``version``: every subject whose withdrawal flagged it (and
    every subject the parent already excluded) is excluded. One active retrain per version.
    Returns (row, created)."""
    from nf_platform.registry import retrain

    name = recipe or version.recipe or retrain.DEFAULT_RECIPE
    if not retrain.known_recipe(name):
        raise RegistryError(422, f"unknown retrain recipe {name!r}")
    excluded = set(version.manifest.get("excluded_subjects") or ()) | withdrawn_subject_hashes(
        session, version
    )
    inputs = [uuid.UUID(i) for i in version.manifest["inputs"]]
    # SEC-146 at request time: every subject that will remain in the training data holds
    # model_training (the worker's recipe checks its actual inputs again).
    subjects, _recs = mf.training_subjects(session, inputs)
    tid = str(principal.tenant_id)
    remaining = tuple(sorted(s for s in subjects if mf.subject_hash(tid, s) not in excluded))
    if not remaining:
        raise RegistryError(409, "no training subject remains after the exclusions")
    policy.check(
        principal,
        "model:train",
        policy.Resource("model", tid, str(version.model_id), subject_ids=remaining),
        session=session,
    )
    active = _active_retrain(session, version.id)
    if active is not None:
        return active, False
    rid = uuid.uuid4()
    try:
        # The job and the row in one savepoint: when a concurrent request won the race, the
        # partial unique index uq_model_retrain_active (0013m6_retrain_active) refuses the row and
        # the rollback takes this request's job with it (no orphan registry.retrain job).
        with session.begin_nested():
            job_id = queue.enqueue(
                session,
                RETRAIN_KIND,
                {"retrain_id": str(rid), "recipe": name},
                dedupe_key=str(rid),
                max_attempts=3,
                created_by=principal.id,
            )
            row = m.ModelRetrain(
                id=rid,
                tenant_id=_tid(principal),
                version_id=version.id,
                job_id=job_id,
                state="queued",
                excluded_subject_hashes=sorted(excluded),
                input_node_ids=inputs,
                requested_by=principal.id,
            )
            session.add(row)
            session.flush()
    except IntegrityError as e:
        if "uq_model_retrain_active" not in str(e.orig):
            raise
        # READ COMMITTED: this statement sees the winner's committed row -> the sequential answer.
        active = _active_retrain(session, version.id)
        if active is not None:
            return active, False
        raise RegistryError(
            409, "a concurrent retrain request for this version is being processed; retry"
        ) from e
    session.refresh(row)
    return row, True


def lineage_subjects(session: Session, version: m.ModelVersion) -> set[str]:
    """Hashed subjects reached by the lineage of the version's model node (the proof: a retrained
    version's lineage does not reach an excluded subject)."""
    subjects = policy.subjects_of_recordings(
        session, policy.source_recordings(session, [version.prov_node_id])
    )
    return {mf.subject_hash(version.tenant_id, s) for s in subjects}
