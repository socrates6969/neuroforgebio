"""Retraining after a consent withdrawal (BUILD-GUIDE 6.3; BLUEPRINT §8.4): the ``registry.retrain``
job on the 3.3 queue.

``POST /v1/models/{model_id}/versions/{version}/retrain`` (:func:`service.request_retrain`) queues a
job that excludes every subject whose withdrawal flagged the version (plus every subject the parent
already excluded). The worker (:func:`execute`) runs a pluggable **recipe**, which trains a new
``model`` derived object without those subjects, then registers it as a new version
(``parent_version_id`` = the old one) through :func:`service.register_version`. Registration
recomputes the training subjects from the provenance lineage of the new weights and refuses the
version if an excluded subject still contributes; the manifest records ``excluded_subjects`` and
the parent. That is the proof of exclusion. The old version stays flagged (M5 ``model_flag`` rows
are never cleared) and, when the tenant policy blocks deployments, stays blocked.

Recipes: ``fn(session, storage, principal, inputs, *, parent, excluded) -> DerivedObject``.

- ``toy`` (built in): follows each input to its current revision (a group average that the
  DeletionJob re-ran without the subject is replaced by the new one; a tombstoned or deleted input
  is dropped), drops every input that still reaches an excluded subject, and retrains
  ``governance.derived.train_toy_model`` on the rest.
- ``sisa`` (6.4, m6-sisa): resolved lazily from ``nf_train.platform`` (``retrain_recipe`` +
  ``manifest_for``), so the worker needs no start-up registration.

We do not claim certified unlearning: the guarantee is "retrained without the subject; here is the
provenance proof".
"""

from __future__ import annotations

import importlib
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from nf_platform.audit import log as audit
from nf_platform.db import models as m
from nf_platform.db.context import Principal, tenant_session
from nf_platform.governance import derived, policy
from nf_platform.registry import manifest as mf
from nf_platform.registry import service
from nf_platform.storage.runtime import Storage, service_principal

log = logging.getLogger(__name__)
JOB_KIND = service.RETRAIN_KIND
SERVICE_ID = "svc:registry-retrain"
DEFAULT_RECIPE = "toy"

Recipe = Callable[..., m.DerivedObject]
ManifestFn = Callable[[m.DerivedObject], Any]


class RetrainError(ValueError):
    """A retrain that cannot succeed (not retryable)."""


@dataclass(frozen=True)
class _Entry:
    train: Recipe
    manifest: ManifestFn | None = None


_RECIPES: dict[str, _Entry] = {}
# name -> (module, recipe attribute, manifest attribute); imported on first use
_LAZY: dict[str, tuple[str, str, str | None]] = {
    "sisa": ("nf_train.platform", "retrain_recipe", "manifest_for"),
}


def register_recipe(name: str, fn: Recipe, *, manifest: ManifestFn | None = None) -> None:
    """``manifest(row)`` -> ``service.TrainingManifest`` of a new weights object (optional; the
    default is the object's ``input_node_ids`` with no shards)."""
    _RECIPES[name] = _Entry(fn, manifest)


def known_recipe(name: str) -> bool:
    return name in _RECIPES or name in _LAZY


def recipe(name: str) -> _Entry:
    if name not in _RECIPES and name in _LAZY:
        mod_name, fn_name, man_name = _LAZY[name]
        try:
            mod = importlib.import_module(mod_name)
        except ImportError as e:
            raise RetrainError(f"retrain recipe {name!r} is not installed in this worker") from e
        register_recipe(
            name, getattr(mod, fn_name), manifest=getattr(mod, man_name) if man_name else None
        )
    if name not in _RECIPES:
        raise RetrainError(f"unknown retrain recipe {name!r}")
    return _RECIPES[name]


# ---------------------------------------------------------------- the built-in toy recipe
def current_revision(session: Session, tenant_id: str, node_id: uuid.UUID) -> uuid.UUID | None:
    """The node that now stands for ``node_id``: itself, the re-run that superseded it (5.5), or
    None when the DeletionJob tombstoned or deleted it."""
    seen: set[uuid.UUID] = set()
    nid: uuid.UUID | None = node_id
    while nid is not None and nid not in seen:
        seen.add(nid)
        st = session.get(m.ArtifactStatus, (uuid.UUID(str(tenant_id)), nid))
        if st is None or st.status == "stale":
            return nid
        if st.status == "superseded":
            nid = st.replaced_by
            continue
        return None  # tombstoned / deleted
    return None


def node_subject_hashes(session: Session, tenant_id: str, node_id: uuid.UUID) -> set[str]:
    subs = policy.subjects_of_recordings(session, policy.source_recordings(session, [node_id]))
    return {mf.subject_hash(tenant_id, s) for s in subs}


def toy_recipe(
    session: Session,
    storage: Storage,
    principal: Principal,
    inputs: list[uuid.UUID],
    *,
    parent: m.ModelVersion,
    excluded: set[str],
) -> m.DerivedObject:
    tid = str(principal.tenant_id)
    keep: list[uuid.UUID] = []
    for nid in inputs:
        cur = current_revision(session, tid, nid)
        if cur is None or cur in keep:
            continue
        subs = node_subject_hashes(session, tid, cur)
        if subs and not subs & excluded:
            keep.append(cur)
    if not keep:
        raise RetrainError("no training input remains once the excluded subjects are removed")
    return derived.train_toy_model(
        session, storage, principal, keep, name=f"retrain-of-{parent.id}"
    )


register_recipe(DEFAULT_RECIPE, toy_recipe)


# ---------------------------------------------------------------- the job body
def _audit(tid: str, retrain_id: uuid.UUID, outcome: audit.Outcome, **d: Any) -> None:
    audit.emit(
        audit.AuditEvent(
            type=audit.DATA_CREATE if outcome == "success" else "registry.retrain",
            outcome=outcome,
            action="model:train",
            tenant_id=tid,
            actor_kind="service",
            actor_id=SERVICE_ID,
            auth_method="service",
            resource_type="model_retrain",
            resource_id=str(retrain_id),
            details=d,
        )
    )


def _manifest(entry: _Entry, row: m.DerivedObject, recipe_name: str, excluded: set[str]):
    base = entry.manifest(row) if entry.manifest else None
    return service.TrainingManifest(
        input_node_ids=tuple(base.input_node_ids if base else row.input_node_ids),
        shards=base.shards if base else None,
        excluded_subject_hashes=tuple(
            sorted(excluded | set(base.excluded_subject_hashes if base else ()))
        ),
        recipe=recipe_name,
    )


def execute(
    engine: Engine | None, storage: Storage, tenant_id: str, retrain_id: uuid.UUID
) -> dict[str, Any]:
    """Run (or finish) one retrain. Returns the job result. Raises RetrainError (not retryable)."""
    tid = str(tenant_id)
    svc = service_principal(tid, SERVICE_ID)
    with tenant_session(svc, engine=engine) as s:
        rt = s.scalar(select(m.ModelRetrain).where(m.ModelRetrain.id == retrain_id))
        if rt is None:
            raise RetrainError("retrain not found")
        if rt.state == "succeeded" and rt.new_version_id is not None:
            return {"retrain_id": str(rt.id), "new_version_id": str(rt.new_version_id)}
        rt.state = "running"
    try:
        with tenant_session(svc, engine=engine) as s:
            rt = s.scalar(select(m.ModelRetrain).where(m.ModelRetrain.id == retrain_id))
            parent = s.scalar(select(m.ModelVersion).where(m.ModelVersion.id == rt.version_id))
            job = s.scalar(select(m.Job).where(m.Job.id == rt.job_id)) if rt.job_id else None
            name = (job.payload.get("recipe") if job else None) or parent.recipe or DEFAULT_RECIPE
            entry = recipe(name)
            excluded = set(rt.excluded_subject_hashes)
            new_obj = entry.train(
                s, storage, svc, list(rt.input_node_ids), parent=parent, excluded=excluded
            )
            version = service.register_version(
                s,
                svc,
                parent.model_id,
                weights_object=service.ObjectRef(derived_object_id=new_obj.id),
                training_manifest=_manifest(entry, new_obj, name, excluded),
                pipeline_version_ids=list(parent.pipeline_version_ids),
                code_commit=parent.code_commit,
                intended_use=parent.intended_use,
                use_restrictions=list(parent.use_restrictions),
                parent_version_id=parent.id,
            )
            rt.state = "succeeded"
            rt.new_version_id = version.id
            rt.finished_at = datetime.now(UTC)
            out = {
                "retrain_id": str(rt.id),
                "new_version_id": str(version.id),
                "version": version.version,
            }
            n_excluded = len(excluded)
    except (RetrainError, service.RegistryError, policy.PolicyDenied, derived.DerivedError) as e:
        detail = getattr(e, "detail", None) or str(e)
        mark_failed(engine, tid, retrain_id, detail)
        _audit(tid, retrain_id, "failure", reason=detail[:200])
        raise RetrainError(detail) from e
    _audit(tid, retrain_id, "success", count=n_excluded, phase="retrained")
    return out


def mark_failed(engine: Engine | None, tenant_id: str, retrain_id: uuid.UUID, error: str) -> None:
    svc = service_principal(str(tenant_id), SERVICE_ID)
    with tenant_session(svc, engine=engine) as s:
        rt = s.scalar(select(m.ModelRetrain).where(m.ModelRetrain.id == retrain_id))
        if rt is not None and rt.state != "succeeded":
            rt.state = "failed"
            rt.error = error[:500]
            rt.finished_at = datetime.now(UTC)
