"""The single policy-enforcement function (BUILD-GUIDE 5.4; BLUEPRINT §8.3; SEC-024, SEC-026,
SEC-142, SEC-146).

``check(principal, action, resource)`` combines, in this order:

1. **RBAC**: ``auth.authorize`` (deny by default, tenant check, API-key scopes). Service
   principals (the workers) hold no role; they may only perform ``SERVICE_ACTIONS``, whose RBAC
   check happened when the job was requested.
2. **Quarantine** (replaces the M2 stub gate): a quarantined recording is visible only to
   ``QUARANTINE_READERS``, who may read it for review regardless of consent (audited obligation
   ``quarantine_review``). Every other data action on it is denied.
3. **Consent scope**: every subject whose data the resource contains must currently hold the
   scopes ``ACTION_SCOPES[action]`` (processing for reads and runs, sharing for exports,
   model_training for training (SEC-146), commercial_use for publication). No record, a
   withdrawal or a missing scope is a denial with a clear message (no subject identifiers).
4. **Classification**: the resource's governance attributes are classified with the current
   RuleSet. Raw export of signals is a classified action even when pseudonymised (SEC-142) and
   needs four-eyes approval (SEC-024): two approvers with a governance role, neither the
   requester. Flags of matched rules (e.g. CA ``limit_use``) are returned as obligations.

Fail closed (SEC-026): any exception other than an authorization decision becomes a
``PolicyDenied`` whose message reveals no internals.

``LedgerConsentPolicy`` answers the ingest hook (``ingest.policy.ConsentPolicy``): a new recording
is ``active`` only when its subject holds collection and processing, else ``quarantined``.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable
from contextlib import nullcontext
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from nf_platform.auth.authorize import (
    Forbidden,
    ResourceRef,
    Unauthorized,
    authorize,
    effective_roles,
    may_read_quarantined,
)
from nf_platform.db import models as m
from nf_platform.db.context import Principal, tenant_session
from nf_platform.governance import attributes, consent, rules
from nf_platform.provenance import api as prov

log = logging.getLogger(__name__)

# action -> consent scopes every contributing subject must hold
ACTION_SCOPES: dict[str, tuple[str, ...]] = {
    "recording:read": (),
    "signal:read": ("processing",),
    "run:create": ("processing",),
    "run:execute": ("processing",),
    "aggregate:create": ("processing",),
    "provenance:export": (),
    "signal:export": ("sharing",),
    "model:train": ("model_training",),
    "model:publish": ("commercial_use",),
    # 6.5 (m6-sisa): the SOUP export names the version, its SBOM and hashes; no subject data
    "model:soup-export": (),
    # 5.8: the evidence kit exports provenance ids/hashes like provenance:export
    "evidence:export": (),
}
# The data-touching actions (route-enumeration test: every route with one of these calls check).
DATA_ACTIONS = frozenset(ACTION_SCOPES)
# Performed by workers (service principals) on behalf of an earlier, authorized request.
SERVICE_ACTIONS = frozenset({"run:execute", "aggregate:create", "model:train", "signal:read"})
# Actions on a quarantined recording that its reviewers may perform (review, no consent needed).
QUARANTINE_REVIEW_ACTIONS = frozenset({"recording:read", "signal:read"})
FOUR_EYES_ACTIONS = frozenset({"signal:export"})
APPROVER_ROLES = attributes.GOVERNANCE_WRITERS
GENERIC_DENIAL = "access denied: the policy could not be evaluated"


class PolicyDenied(Forbidden):
    """A policy decision (403). Subclasses Forbidden, so the API maps it to problem+json."""


@dataclass(frozen=True)
class Resource:
    """What the action touches. ``subject_ids`` are resolved from ``recording_id`` / ``node_ids``
    when not given (lineage up to the source recordings)."""

    type: str
    tenant_id: str
    id: str | None = None
    recording_id: uuid.UUID | None = None
    node_ids: tuple[uuid.UUID, ...] = ()
    subject_ids: tuple[uuid.UUID, ...] = ()


@dataclass(frozen=True)
class Approval:
    approver_id: str
    roles: frozenset[str]


@dataclass(frozen=True)
class Decision:
    allowed: bool
    action: str
    obligations: tuple[str, ...] = ()
    classification: dict[str, Any] | None = None
    subjects: int = 0
    reasons: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------- resolution helpers
def _recording_subject(session: Session, recording_id: uuid.UUID) -> tuple[m.Recording, uuid.UUID]:
    rec = session.scalar(select(m.Recording).where(m.Recording.id == recording_id))
    if rec is None:
        raise PolicyDenied("resource not found or not accessible")
    sid = session.scalar(select(m.Session_.subject_id).where(m.Session_.id == rec.session_id))
    return rec, sid


def source_recordings(session: Session, node_ids: Iterable[uuid.UUID]) -> set[uuid.UUID]:
    """Recording ids at the root of the given entities' ancestry."""
    out: set[uuid.UUID] = set()
    for nid in node_ids:
        g = prov.lineage(session, nid, "up", None)
        for n in g.nodes:
            if n.type == "recording" and n.kind is prov.ProvKind.ENTITY and n.ref_id:
                out.add(uuid.UUID(n.ref_id))
    return out


def subjects_of_recordings(session: Session, recording_ids: Iterable[uuid.UUID]) -> set[uuid.UUID]:
    ids = list(recording_ids)
    if not ids:
        return set()
    rows = session.execute(
        select(m.Session_.subject_id)
        .join(m.Recording, m.Recording.session_id == m.Session_.id)
        .where(m.Recording.id.in_(ids))
    ).all()
    return {r.subject_id for r in rows}


def _attributes(session: Session, res: Resource, rec_ids: set[uuid.UUID]) -> dict[str, Any] | None:
    parts = [attributes.recording_attributes(session, r) for r in sorted(rec_ids)]
    for nid in res.node_ids:
        n = prov.get_node(session, nid)
        if n is not None and n.kind is prov.ProvKind.ENTITY:
            parts.append(attributes.node_attributes(session, nid))
    return attributes.strictest(parts)


def _check_four_eyes(principal: Principal, approvals: Iterable[Approval]) -> None:
    ok = {
        a.approver_id
        for a in approvals
        if a.approver_id != principal.id and a.roles & APPROVER_ROLES
    }
    if len(ok) < 2:
        raise PolicyDenied(
            "four-eyes approval required: raw export of classified data needs two approvers "
            "other than the requester (SEC-024)"
        )


# ---------------------------------------------------------------- the policy function
def _evaluate(
    principal: Principal,
    action: str,
    res: Resource,
    session: Session,
    approvals: tuple[Approval, ...],
) -> Decision:
    if action not in ACTION_SCOPES:
        raise PolicyDenied("unknown action")
    # 1. RBAC
    if principal.kind == "service":
        if action not in SERVICE_ACTIONS or principal.tenant_id != res.tenant_id:
            raise PolicyDenied("action not available to this service")
    else:
        authorize(principal, action, ResourceRef(type=res.type, tenant_id=res.tenant_id, id=res.id))
    obligations: list[str] = []

    # 2. subjects and quarantine
    rec_ids: set[uuid.UUID] = set()
    subjects: set[uuid.UUID] = {uuid.UUID(str(s)) for s in res.subject_ids}
    if res.recording_id is not None:
        rec, sid = _recording_subject(session, res.recording_id)
        rec_ids.add(rec.id)
        subjects.add(sid)
        if rec.state == "quarantined":
            if (
                principal.kind != "service"
                and may_read_quarantined(principal)
                and (action in QUARANTINE_REVIEW_ACTIONS)
            ):
                return Decision(True, action, ("quarantine_review",), None, len(subjects))
            raise PolicyDenied("recording is quarantined until the consent policy allows access")
    if res.node_ids:
        srcs = source_recordings(session, res.node_ids)
        rec_ids |= srcs
        subjects |= subjects_of_recordings(session, srcs)

    # 3. consent scope for every contributing subject
    need = ACTION_SCOPES[action]
    if need:
        if not subjects:
            raise PolicyDenied("no subject could be resolved for this resource; access denied")
        held = consent.current_scopes(session, subjects)
        for scope in need:
            missing = [s for s, sc in held.items() if scope not in sc]
            if missing:
                raise PolicyDenied(
                    f"consent scope '{scope}' is missing for {len(missing)} of {len(held)} "
                    "subject(s) whose data this uses"
                )

    # 4. classification
    classification = None
    if rec_ids or res.node_ids:
        attrs = _attributes(session, res, rec_ids)
        if attrs is not None:
            classification = rules.classify(
                {
                    "nervous_system": attrs["nervous_system"],
                    "derived_from_non_neural": attrs["derived_from_non_neural"],
                    "modality": attrs["modalities"],
                }
            )
            obligations += classification["flags"]
            if attrs["needs_review"]:
                obligations.append("attributes_need_review")
    if action in FOUR_EYES_ACTIONS:
        # SEC-142: raw or minimally processed signals are identifying, so their export is always
        # a classified action, whatever the RuleSet says.
        _check_four_eyes(principal, approvals)
        obligations.append("four_eyes_approved")
    return Decision(True, action, tuple(sorted(set(obligations))), classification, len(subjects))


def check(
    principal: Principal | None,
    action: str,
    resource: Resource,
    *,
    session: Session | None = None,
    approvals: Iterable[Approval] = (),
) -> Decision:
    """Allow (returns the Decision) or raise Unauthorized/Forbidden/PolicyDenied. Fails closed."""
    if principal is None:
        raise Unauthorized("authentication required")
    try:
        ctx = nullcontext(session) if session is not None else tenant_session(principal)
        with ctx as s:
            return _evaluate(principal, action, resource, s, tuple(approvals))
    except (Forbidden, Unauthorized):
        raise
    except Exception:  # noqa: BLE001 - SEC-026: fail closed, reveal nothing
        log.error("policy evaluation failed; denied", extra={"action": action})
        raise PolicyDenied(GENERIC_DENIAL) from None


def approvals_from(principals: Iterable[Principal]) -> tuple[Approval, ...]:
    return tuple(Approval(p.id, effective_roles(p)) for p in principals)


# ---------------------------------------------------------------- ingest hook
class LedgerConsentPolicy:
    """``ingest.policy.ConsentPolicy`` backed by the consent ledger: a new recording is active only
    when its subject holds ``collection`` and ``processing``; otherwise quarantined. Any error
    quarantines (fail closed)."""

    REQUIRED = frozenset({"collection", "processing"})

    def __init__(self, engine: Engine | None = None) -> None:
        self.engine = engine

    def decide(self, tenant_id: str, subject_id: str, recording_id: str) -> str:
        try:
            svc = Principal(
                "svc:consent-policy", str(tenant_id), frozenset(), frozenset(), "service", False
            )
            with tenant_session(svc, engine=self.engine) as s:
                held = consent.current_scopes(s, [uuid.UUID(str(subject_id))])
            scopes = held.get(uuid.UUID(str(subject_id)), frozenset())
            return "allow" if scopes >= self.REQUIRED else "quarantine"
        except Exception:  # noqa: BLE001 - fail closed
            log.error("consent policy lookup failed; quarantining", extra={"tenant_id": tenant_id})
            return "quarantine"
