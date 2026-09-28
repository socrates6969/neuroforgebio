"""Channel and artifact governance attributes (BUILD-GUIDE 5.1; BLUEPRINT §3.2, §8.2; SEC-022).

``nervous_system``, ``modality`` and ``derived_from_non_neural`` drive classification, because the
state definitions differ on exactly these points (``market/regulation.md`` §1).

- **Modality defaults**: a new channel without explicit values gets the default of its modality.
  The defaults are a starting point for review, not a legal judgement. ``unknown`` means a steward
  must decide; classification then reports ``needs_review``.
- **Who may write**: only ``owner``/``admin``/``data-steward`` (``GOVERNANCE_WRITERS``, SEC-022).
  Other roles may create channels only with the modality defaults.
- **Artifacts** inherit the strictest attributes of their inputs through the provenance lineage,
  unless a steward stored an explicit value for that artifact (``artifact_governance``). Strictest
  per attribute: ``nervous_system`` central > peripheral > unknown (and ``needs_review`` when any
  input is unknown); ``derived_from_non_neural`` is true only when EVERY input is; the modalities
  are the union.

Every change is returned as a list of ``{field, old, new, ...}`` records; the API layer audits
each call (``governance.attributes`` event).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from nf_platform.auth.authorize import Forbidden, effective_roles
from nf_platform.db import models as m
from nf_platform.db.context import Principal
from nf_platform.provenance import api as prov

GOVERNANCE_WRITERS = frozenset({"owner", "admin", "data-steward"})
FIELDS = ("modality", "nervous_system", "derived_from_non_neural")
NS_RANK = {"unknown": 0, "peripheral": 1, "central": 2}

# modality -> (nervous_system, derived_from_non_neural). A default, reviewed by a steward.
MODALITY_DEFAULTS: dict[str, tuple[str, bool]] = {
    "EEG": ("central", False),
    "iEEG": ("central", False),
    "ECoG": ("central", False),
    "SEEG": ("central", False),
    "LFP": ("central", False),
    "spikes": ("central", False),
    "MEG": ("central", False),
    "EMG": ("peripheral", False),
    "ENG": ("peripheral", False),
    # Not a measurement of nervous-system activity by default; a steward decides.
    "EOG": ("unknown", False),
    "ECG": ("unknown", False),
    "fNIRS": ("unknown", False),
    "other": ("unknown", False),
}
assert set(MODALITY_DEFAULTS) == set(m.MODALITIES)


class GovernanceError(ValueError):
    """Invalid governance input (422) or a missing object (404, ``not_found=True``)."""

    def __init__(self, detail: str, *, not_found: bool = False) -> None:
        super().__init__(detail)
        self.detail = detail
        self.not_found = not_found


def may_write(principal: Principal) -> bool:
    return bool(effective_roles(principal) & GOVERNANCE_WRITERS)


def require_writer(principal: Principal) -> None:
    if not may_write(principal):
        raise Forbidden("governance attributes are writable only by data-steward or admin")


def defaults_for(modality: str) -> tuple[str, bool]:
    return MODALITY_DEFAULTS.get(modality, ("unknown", False))


def resolve_initial(
    principal: Principal | None,
    modality: str,
    nervous_system: str | None,
    derived_from_non_neural: bool | None,
) -> tuple[str, bool]:
    """Attributes for a NEW channel: explicit values, else the modality default. A non-writer may
    only confirm the default (SEC-022); anything else raises Forbidden. ``principal=None`` is an
    internal writer (converters in the worker), which records what the file says."""
    ns_d, dfnn_d = defaults_for(modality)
    ns = ns_d if nervous_system is None else nervous_system
    dfnn = dfnn_d if derived_from_non_neural is None else derived_from_non_neural
    if principal is not None and (ns, dfnn) != (ns_d, dfnn_d) and not may_write(principal):
        raise Forbidden(
            "governance attributes differ from the modality default; only data-steward or admin "
            "may set them"
        )
    return ns, dfnn


def _check_values(values: dict[str, Any]) -> dict[str, Any]:
    bad = set(values) - set(FIELDS)
    if bad:
        raise GovernanceError(f"unknown governance field(s): {sorted(bad)}")
    out = {k: v for k, v in values.items() if v is not None}
    if not out:
        raise GovernanceError("nothing to change")
    if "modality" in out and out["modality"] not in m.MODALITIES:
        raise GovernanceError("unknown modality")
    if "nervous_system" in out and out["nervous_system"] not in m.NERVOUS_SYSTEMS:
        raise GovernanceError("nervous_system must be central, peripheral or unknown")
    if "derived_from_non_neural" in out and not isinstance(out["derived_from_non_neural"], bool):
        raise GovernanceError("derived_from_non_neural must be a boolean")
    return out


def _apply(ch: m.Channel, values: dict[str, Any]) -> list[dict[str, Any]]:
    changes = []
    for f in FIELDS:
        if f in values and getattr(ch, f) != values[f]:
            changes.append(
                {
                    "recording_id": str(ch.recording_id),
                    "index": ch.index,
                    "field": f,
                    "old": getattr(ch, f),
                    "new": values[f],
                }
            )
            setattr(ch, f, values[f])
    return changes


def update_channels(
    session: Session,
    principal: Principal,
    recording_id: uuid.UUID,
    edits: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Per-channel edits of one recording: ``[{"index": i, <field>: value, ...}]``."""
    require_writer(principal)
    chans = {
        c.index: c
        for c in session.scalars(select(m.Channel).where(m.Channel.recording_id == recording_id))
    }
    if not chans:
        raise GovernanceError("recording has no channels", not_found=True)
    changes: list[dict[str, Any]] = []
    for e in edits:
        e = dict(e)
        idx = e.pop("index", None)
        if idx not in chans:
            raise GovernanceError(f"no channel with index {idx!r}")
        changes += _apply(chans[idx], _check_values(e))
    session.flush()
    return changes


def bulk_update(
    session: Session,
    principal: Principal,
    recording_ids: list[uuid.UUID],
    values: dict[str, Any],
    *,
    modality: str | None = None,
) -> list[dict[str, Any]]:
    """Bulk editor: set ``values`` on every channel of ``recording_ids`` (optionally only those of
    ``modality``). Recordings of another tenant are simply not found (RLS)."""
    require_writer(principal)
    vals = _check_values(values)
    q = select(m.Channel).where(m.Channel.recording_id.in_(recording_ids))
    if modality is not None:
        q = q.where(m.Channel.modality == modality)
    found = session.scalars(q.order_by(m.Channel.recording_id, m.Channel.index)).all()
    have = {c.recording_id for c in found}
    if modality is None and set(recording_ids) - have:
        raise GovernanceError("recording not found or without channels", not_found=True)
    changes: list[dict[str, Any]] = []
    for ch in found:
        changes += _apply(ch, vals)
    session.flush()
    return changes


# ---------------------------------------------------------------- strictest inheritance
def strictest(attrs: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    items = [a for a in attrs if a is not None]
    if not items:
        return None
    ns = max((a["nervous_system"] for a in items), key=lambda v: NS_RANK[v])
    mods: set[str] = set()
    for a in items:
        mods |= set(a.get("modalities") or ([a["modality"]] if a.get("modality") else []))
    return {
        "nervous_system": ns,
        "derived_from_non_neural": all(a["derived_from_non_neural"] for a in items),
        "modalities": sorted(mods),
        "needs_review": any(
            a["nervous_system"] == "unknown" or a.get("needs_review") for a in items
        ),
    }


def channel_attrs(ch: m.Channel) -> dict[str, Any]:
    return {
        "nervous_system": ch.nervous_system,
        "derived_from_non_neural": ch.derived_from_non_neural,
        "modalities": [ch.modality],
        "needs_review": ch.nervous_system == "unknown",
    }


def recording_attributes(session: Session, recording_id: uuid.UUID | str) -> dict[str, Any] | None:
    chans = session.scalars(
        select(m.Channel).where(m.Channel.recording_id == uuid.UUID(str(recording_id)))
    ).all()
    return strictest(channel_attrs(c) for c in chans)


def _override(row: m.ArtifactGovernance) -> dict[str, Any]:
    return {
        "nervous_system": row.nervous_system,
        "derived_from_non_neural": row.derived_from_non_neural,
        "modalities": sorted(row.modalities or []),
        "needs_review": row.nervous_system == "unknown",
    }


def node_attributes(session: Session, node_id: uuid.UUID) -> dict[str, Any]:
    """Effective attributes of a provenance entity: its explicit override, else the strictest of
    its inputs (recursively; a ``recording`` node takes its channels). ``source`` says which."""
    g = prov.lineage(session, node_id, "up", None)
    nodes = {n.id: n for n in g.nodes}
    overrides = {
        r.node_id: r
        for r in session.scalars(
            select(m.ArtifactGovernance).where(m.ArtifactGovernance.node_id.in_(list(nodes)))
        )
    }
    parents: dict[uuid.UUID, set[uuid.UUID]] = {}
    used: dict[uuid.UUID, set[uuid.UUID]] = {}
    gen_by: dict[uuid.UUID, set[uuid.UUID]] = {}
    for e in g.edges:
        if e.rel is prov.EdgeType.WAS_DERIVED_FROM:
            parents.setdefault(e.src, set()).add(e.dst)
        elif e.rel is prov.EdgeType.USED:
            used.setdefault(e.src, set()).add(e.dst)
        elif e.rel is prov.EdgeType.WAS_GENERATED_BY:
            gen_by.setdefault(e.src, set()).add(e.dst)
    for ent, acts in gen_by.items():
        for a in acts:
            parents.setdefault(ent, set()).update(used.get(a, set()))

    memo: dict[uuid.UUID, dict[str, Any] | None] = {}

    def attrs(nid: uuid.UUID, stack: frozenset[uuid.UUID]) -> dict[str, Any] | None:
        if nid in memo:
            return memo[nid]
        n = nodes.get(nid)
        if n is None or nid in stack or n.kind is not prov.ProvKind.ENTITY:
            return None
        if nid in overrides:
            out = _override(overrides[nid])
        elif n.type == "recording" and n.ref_id:
            out = recording_attributes(session, n.ref_id)
        else:
            out = strictest(attrs(p, stack | {nid}) for p in sorted(parents.get(nid, ())))
        memo[nid] = out
        return out

    root = nodes.get(node_id)
    if root is None or root.kind is not prov.ProvKind.ENTITY:
        raise GovernanceError("node is not an entity", not_found=root is None)
    eff = attrs(node_id, frozenset())
    source = (
        "explicit"
        if node_id in overrides
        else "channels"
        if root.type == "recording"
        else "inherited"
    )
    if eff is None:
        eff = {
            "nervous_system": "unknown",
            "derived_from_non_neural": False,
            "modalities": [],
            "needs_review": True,
        }
        source = "none"
    return {**eff, "source": source}


def set_node_attributes(
    session: Session,
    principal: Principal,
    node_id: uuid.UUID,
    values: dict[str, Any],
    reason: str | None,
) -> list[dict[str, Any]]:
    """Store explicit attributes for a derived artifact (not a recording: its channels are the
    source of truth). Returns the field changes against the previous effective values."""
    require_writer(principal)
    n = prov.get_node(session, node_id)
    if n is None:
        raise GovernanceError("provenance node", not_found=True)
    if n.kind is not prov.ProvKind.ENTITY or n.type == "recording":
        raise GovernanceError("explicit attributes apply to derived artifacts; edit the channels")
    before = node_attributes(session, node_id)
    ns = values.get("nervous_system", before["nervous_system"])
    dfnn = values.get("derived_from_non_neural", before["derived_from_non_neural"])
    mods = values.get("modalities", before["modalities"])
    _check_values({"nervous_system": ns, "derived_from_non_neural": dfnn})
    if any(x not in m.MODALITIES for x in mods):
        raise GovernanceError("unknown modality")
    row = session.get(m.ArtifactGovernance, (uuid.UUID(str(principal.tenant_id)), node_id))
    if row is None:
        row = m.ArtifactGovernance(tenant_id=uuid.UUID(str(principal.tenant_id)), node_id=node_id)
        session.add(row)
    row.nervous_system = ns
    row.derived_from_non_neural = dfnn
    row.modalities = sorted(set(mods))
    row.reason = reason
    row.updated_by = principal.id
    row.updated_at = datetime.now(UTC)
    session.flush()
    after = {"nervous_system": ns, "derived_from_non_neural": dfnn, "modalities": sorted(set(mods))}
    return [
        {"node_id": str(node_id), "field": f, "old": before[f], "new": after[f]}
        for f in ("nervous_system", "derived_from_non_neural", "modalities")
        if before[f] != after[f]
    ]
