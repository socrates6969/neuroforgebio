"""Provenance graph API (M3-CONTRACTS §2; BUILD-GUIDE 3.1; BLUEPRINT §3.6; SEC-043).

All calls run inside the caller's tenant session (``tenant_session``), so RLS applies to every
statement; nodes of another tenant are simply not found.

Graph rules (append-only and acyclic by construction):

- ``record(session, principal, nodes, edges)`` inserts ``nodes`` and ``edges`` and appends ONE
  hash-chained, Ed25519-signed batch to the tenant's chain, atomically (same transaction).
- An edge is ``(src, rel, dst)`` in PROV direction (effect → cause). ``src`` must be an ``int``
  index into ``nodes`` (a node created by this call). ``dst`` is either an index smaller than
  ``src`` or the ``uuid.UUID`` of an existing node. So new nodes only point at older nodes and no
  cycle can ever form.
- Relations and the node kinds they connect (W3C PROV-DM): ``used`` activity→entity,
  ``wasGeneratedBy`` entity→activity, ``wasDerivedFrom`` entity→entity, ``wasAttributedTo``
  entity→agent, ``wasAssociatedWith`` activity→agent, ``wasInformedBy`` activity→activity.
- ``(kind, type, ref_id)`` is unique per tenant when ``ref_id`` is set (one node per recording,
  upload, run, PipelineVersion...). Use :func:`find_node` to link to it.
- ``attrs`` must be non-identifying (ids, hashes, versions, parameters). They are hashed and signed,
  and cannot be edited later.

Lineage ``up`` = ancestry (follow src → dst), ``down`` = descendants (dst → src).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from sqlalchemy import bindparam, insert, select, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Session

from nf_platform.audit import _canonical as cj
from nf_platform.db import models as m
from nf_platform.db.context import Principal
from nf_platform.provenance import chain, signing


class ProvKind(StrEnum):
    ENTITY = "entity"
    ACTIVITY = "activity"
    AGENT = "agent"


class EdgeType(StrEnum):
    USED = "used"
    WAS_GENERATED_BY = "wasGeneratedBy"
    WAS_DERIVED_FROM = "wasDerivedFrom"
    WAS_ATTRIBUTED_TO = "wasAttributedTo"
    WAS_ASSOCIATED_WITH = "wasAssociatedWith"
    WAS_INFORMED_BY = "wasInformedBy"


# (src kind, dst kind) each relation connects (PROV-DM).
REL_KINDS: dict[EdgeType, tuple[ProvKind, ProvKind]] = {
    EdgeType.USED: (ProvKind.ACTIVITY, ProvKind.ENTITY),
    EdgeType.WAS_GENERATED_BY: (ProvKind.ENTITY, ProvKind.ACTIVITY),
    EdgeType.WAS_DERIVED_FROM: (ProvKind.ENTITY, ProvKind.ENTITY),
    EdgeType.WAS_ATTRIBUTED_TO: (ProvKind.ENTITY, ProvKind.AGENT),
    EdgeType.WAS_ASSOCIATED_WITH: (ProvKind.ACTIVITY, ProvKind.AGENT),
    EdgeType.WAS_INFORMED_BY: (ProvKind.ACTIVITY, ProvKind.ACTIVITY),
}
TYPE_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
CONTENT_RE = re.compile(m.CONTENT_ID_RE)
MAX_REF_LEN = 500
MAX_ATTRS_BYTES = 16 * 1024
# Advisory-lock class for "append to this tenant's provenance chain" (serialises seq allocation).
_LOCK_CLASS = 0x4E460003


class ProvError(ValueError):
    """Invalid nodes/edges passed to :func:`record` (a caller bug or bad input)."""


class NodeNotFound(LookupError):
    pass


@dataclass(frozen=True)
class NodeSpec:
    kind: ProvKind
    type: str
    ref_id: str | None = None
    content_hash: str | None = None
    attrs: dict[str, Any] = field(default_factory=dict)


NodeRef = int | uuid.UUID  # int: index into this call's ``nodes``; UUID: an existing node


@dataclass(frozen=True)
class ProvCommit:
    batch_seq: int
    batch_id: str  # provb:sha256:... (the hash-chain link of this batch)
    node_ids: list[uuid.UUID]  # same order as ``nodes``
    edge_count: int


@dataclass(frozen=True)
class GraphNode:
    id: uuid.UUID
    kind: ProvKind
    type: str
    ref_id: str | None
    content_hash: str | None
    node_hash: str
    attrs: dict[str, Any]
    batch_seq: int
    created_at: datetime
    depth: int = 0


@dataclass(frozen=True)
class GraphEdge:
    src: uuid.UUID
    rel: EdgeType
    dst: uuid.UUID


@dataclass(frozen=True)
class Graph:
    root: uuid.UUID
    direction: Literal["up", "down"]
    depth: int | None
    nodes: list[GraphNode]  # root first, then by (depth, id)
    edges: list[GraphEdge]
    truncated: bool = False


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    tenant_id: str
    batches: int
    nodes: int
    edges: int
    head: str | None
    errors: list[str]


# ---------------------------------------------------------------- record
def _check_node(i: int, n: NodeSpec) -> dict[str, Any]:
    try:
        kind = ProvKind(n.kind)
    except ValueError as e:
        raise ProvError(f"node {i}: unknown kind {n.kind!r}") from e
    if not isinstance(n.type, str) or not TYPE_RE.match(n.type):
        raise ProvError(f"node {i}: type must match {TYPE_RE.pattern}")
    if n.ref_id is not None and (not isinstance(n.ref_id, str) or not 0 < len(n.ref_id) <= 500):
        raise ProvError(f"node {i}: ref_id must be a string of 1..{MAX_REF_LEN} characters")
    if n.content_hash is not None and not CONTENT_RE.match(str(n.content_hash)):
        raise ProvError(f"node {i}: content_hash must be a content ID (blob|pv|chunk|provb)")
    if not isinstance(n.attrs, dict):
        raise ProvError(f"node {i}: attrs must be an object")
    try:
        size = len(cj.canonicalize(n.attrs))
    except cj.CanonicalError as e:
        raise ProvError(f"node {i}: attrs are not canonical JSON ({e})") from e
    if size > MAX_ATTRS_BYTES:
        raise ProvError(f"node {i}: attrs exceed {MAX_ATTRS_BYTES} bytes")
    return {"kind": kind, "type": n.type, "ref_id": n.ref_id, "content_hash": n.content_hash}


def _session_tenant(session: Session, principal: Principal) -> uuid.UUID:
    tid = uuid.UUID(str(principal.tenant_id))
    st = session.info.get("tenant_id")
    if st is not None and st != tid:
        raise ProvError("session and principal belong to different tenants")
    return tid


def record(
    session: Session,
    principal: Principal,
    nodes: list[NodeSpec],
    edges: list[tuple[NodeRef, EdgeType, NodeRef]],
) -> ProvCommit:
    """Insert ``nodes`` + ``edges`` and append one signed batch to the tenant's chain."""
    if not nodes:
        raise ProvError("a provenance batch needs at least one new node")
    tid = _session_tenant(session, principal)
    checked = [_check_node(i, n) for i, n in enumerate(nodes)]
    ids = [uuid.uuid4() for _ in nodes]

    # existing endpoints (RLS: another tenant's node is "not found")
    existing = {d for _, _, d in edges if isinstance(d, uuid.UUID)}
    kinds_existing: dict[uuid.UUID, ProvKind] = {}
    if existing:
        rows = session.execute(
            select(m.ProvNode.id, m.ProvNode.kind).where(m.ProvNode.id.in_(existing))
        ).all()
        kinds_existing = {r.id: ProvKind(r.kind) for r in rows}
        missing = existing - set(kinds_existing)
        if missing:
            raise NodeNotFound(f"edge target(s) not found: {sorted(map(str, missing))[:5]}")

    edge_rows: list[tuple[uuid.UUID, EdgeType, uuid.UUID]] = []
    seen: set[tuple[uuid.UUID, str, uuid.UUID]] = set()
    for j, (s, rel, d) in enumerate(edges):
        try:
            rel = EdgeType(rel)
        except ValueError as e:
            raise ProvError(f"edge {j}: unknown relation {rel!r}") from e
        if isinstance(s, bool) or not isinstance(s, int) or not 0 <= s < len(nodes):
            raise ProvError(f"edge {j}: src must be an index into this call's nodes")
        if isinstance(d, uuid.UUID):
            dst_id, dst_kind = d, kinds_existing[d]
        elif isinstance(d, int) and not isinstance(d, bool) and 0 <= d < s:
            dst_id, dst_kind = ids[d], checked[d]["kind"]
        else:
            raise ProvError(
                f"edge {j}: dst must be an index smaller than src or an existing node UUID"
            )
        want_src, want_dst = REL_KINDS[rel]
        if checked[s]["kind"] != want_src or dst_kind != want_dst:
            raise ProvError(
                f"edge {j}: {rel.value} connects {want_src.value} -> {want_dst.value}, "
                f"got {checked[s]['kind'].value} -> {dst_kind.value}"
            )
        key = (ids[s], rel.value, dst_id)
        if key in seen:
            raise ProvError(f"edge {j}: duplicate edge")
        seen.add(key)
        edge_rows.append((ids[s], rel, dst_id))

    # serialise appends to this tenant's chain, then read the head
    session.execute(
        text("SELECT pg_advisory_xact_lock(:c, hashtext(:t))"), {"c": _LOCK_CLASS, "t": str(tid)}
    )
    head = session.execute(
        select(m.ProvBatch.seq, m.ProvBatch.batch_id)
        .where(m.ProvBatch.tenant_id == tid)
        .order_by(m.ProvBatch.seq.desc())
        .limit(1)
    ).first()
    seq = 0 if head is None else head.seq + 1
    prev = None if head is None else head.batch_id
    created = chain.now_ms()

    node_values, records = [], []
    for i, (n, c) in enumerate(zip(nodes, checked, strict=True)):
        rec = chain.node_record(
            str(ids[i]), c["kind"].value, c["type"], c["ref_id"], c["content_hash"], n.attrs
        )
        records.append(rec)
        node_values.append(
            {
                "id": ids[i],
                "tenant_id": tid,
                "kind": c["kind"].value,
                "type": c["type"],
                "ref_id": c["ref_id"],
                "content_hash": c["content_hash"],
                "attrs": n.attrs,
                "node_hash": chain.node_hash(rec),
                "batch_seq": seq,
                "ord": i,
            }
        )
    edge_values = []
    for j, (s_id, rel, d_id) in enumerate(edge_rows):
        records.append(chain.edge_record(str(s_id), rel.value, str(d_id)))
        edge_values.append(
            {
                "tenant_id": tid,
                "src": s_id,
                "rel": rel.value,
                "dst": d_id,
                "batch_seq": seq,
                "ord": j,
            }
        )
    doc = chain.batch_doc(str(tid), seq, prev, chain.ts(created), records)
    bid = chain.batch_id(doc)
    kr = signing.keyring()
    session.execute(
        insert(m.ProvBatch).values(
            tenant_id=tid,
            seq=seq,
            batch_id=bid,
            prev_id=prev,
            created_at=created,
            n_records=len(records),
            key_id=kr.signer.key_id,
            signature=kr.signer.sign(bid.encode("ascii")),
        )
    )
    session.execute(insert(m.ProvNode), node_values)
    if edge_values:
        session.execute(insert(m.ProvEdge), edge_values)
    return ProvCommit(batch_seq=seq, batch_id=bid, node_ids=ids, edge_count=len(edge_values))


# ---------------------------------------------------------------- reads
_NODE_COLS = (
    m.ProvNode.id,
    m.ProvNode.kind,
    m.ProvNode.type,
    m.ProvNode.ref_id,
    m.ProvNode.content_hash,
    m.ProvNode.node_hash,
    m.ProvNode.attrs,
    m.ProvNode.batch_seq,
    m.ProvNode.created_at,
)


def _gnode(r: Any, depth: int = 0) -> GraphNode:
    return GraphNode(
        id=r.id,
        kind=ProvKind(r.kind),
        type=r.type,
        ref_id=r.ref_id,
        content_hash=r.content_hash,
        node_hash=r.node_hash,
        attrs=r.attrs or {},
        batch_seq=r.batch_seq,
        created_at=r.created_at,
        depth=depth,
    )


def get_node(session: Session, node_id: uuid.UUID) -> GraphNode | None:
    r = session.execute(select(*_NODE_COLS).where(m.ProvNode.id == node_id)).first()
    return None if r is None else _gnode(r)


def find_node(session: Session, kind: ProvKind | str, type_: str, ref_id: str) -> uuid.UUID | None:
    """The node of a platform object (unique per tenant), e.g. ``(ENTITY, "recording", rid)``."""
    return session.scalar(
        select(m.ProvNode.id).where(
            m.ProvNode.kind == str(ProvKind(kind)),
            m.ProvNode.type == type_,
            m.ProvNode.ref_id == ref_id,
        )
    )


def neighbours(
    session: Session, node_id: uuid.UUID, limit: int = 200
) -> tuple[list[GraphEdge], list[GraphEdge]]:
    """(outgoing, incoming) edges of one node, at most ``limit`` each."""
    out_rows = session.execute(
        select(m.ProvEdge.src, m.ProvEdge.rel, m.ProvEdge.dst)
        .where(m.ProvEdge.src == node_id)
        .order_by(m.ProvEdge.rel, m.ProvEdge.dst)
        .limit(limit)
    ).all()
    in_rows = session.execute(
        select(m.ProvEdge.src, m.ProvEdge.rel, m.ProvEdge.dst)
        .where(m.ProvEdge.dst == node_id)
        .order_by(m.ProvEdge.rel, m.ProvEdge.src)
        .limit(limit)
    ).all()
    return (
        [GraphEdge(r.src, EdgeType(r.rel), r.dst) for r in out_rows],
        [GraphEdge(r.src, EdgeType(r.rel), r.dst) for r in in_rows],
    )


# Recursive CTEs. ``up`` follows src -> dst, ``down`` dst -> src. UNION (not UNION ALL) makes each
# (node) resp. (node, depth) row appear once, so DAGs with many paths stay bounded.
_WALK_BOUNDED = """
WITH RECURSIVE walk(id, depth) AS (
    SELECT n.id, 0 FROM prov_node n WHERE n.id = :root
  UNION
    SELECT e.{nxt}, w.depth + 1 FROM walk w JOIN prov_edge e ON e.{cur} = w.id
    WHERE w.depth < :maxd
)
SELECT id, min(depth) AS depth FROM walk GROUP BY id ORDER BY min(depth), id LIMIT :cap
"""
_WALK_ALL = """
WITH RECURSIVE walk(id) AS (
    SELECT n.id FROM prov_node n WHERE n.id = :root
  UNION
    SELECT e.{nxt} FROM walk w JOIN prov_edge e ON e.{cur} = w.id
)
SELECT id FROM walk LIMIT :cap
"""
_EDGES = "SELECT src, rel, dst FROM prov_edge WHERE {cur} = ANY(:ids)"
_IDS = bindparam("ids", type_=ARRAY(UUID(as_uuid=True)))


def lineage(
    session: Session,
    node_id: uuid.UUID,
    direction: Literal["up", "down"],
    depth: int | None,
    *,
    max_nodes: int = 100_000,
) -> Graph:
    """Ancestors (``up``) or descendants (``down``) of ``node_id`` up to ``depth`` hops (``None``:
    unbounded), with every edge traversed. At most ``max_nodes`` nodes (``truncated`` is set when
    more exist; shallow nodes are kept first for a bounded depth)."""
    if direction not in ("up", "down"):
        raise ValueError("direction must be 'up' or 'down'")
    if depth is not None and depth < 0:
        raise ValueError("depth must be >= 0")
    cur, nxt = ("src", "dst") if direction == "up" else ("dst", "src")
    cap = max_nodes + 1
    if depth is not None:
        rows = session.execute(
            text(_WALK_BOUNDED.format(cur=cur, nxt=nxt)),
            {"root": node_id, "maxd": depth, "cap": cap},
        ).all()
        depths = {r.id: r.depth for r in rows}
    else:
        rows = session.execute(
            text(_WALK_ALL.format(cur=cur, nxt=nxt)), {"root": node_id, "cap": cap}
        ).all()
        depths = {r.id: -1 for r in rows}
    if not depths:
        raise NodeNotFound(str(node_id))
    truncated = len(depths) > max_nodes
    if truncated:
        keep = list(depths)[:max_nodes]
        depths = {k: depths[k] for k in keep}
    expand = [k for k, d in depths.items() if depth is None or d < depth]
    edges: list[GraphEdge] = []
    if expand:
        for r in session.execute(
            text(_EDGES.format(cur=cur)).bindparams(_IDS), {"ids": expand}
        ).all():
            if r.src in depths and r.dst in depths:
                edges.append(GraphEdge(r.src, EdgeType(r.rel), r.dst))
    if depth is None:  # BFS over the fetched edges for the minimum hop count
        depths = _bfs_depths(node_id, edges, direction)
    node_rows = session.execute(select(*_NODE_COLS).where(m.ProvNode.id.in_(list(depths)))).all()
    nodes = sorted((_gnode(r, depths[r.id]) for r in node_rows), key=lambda n: (n.depth, str(n.id)))
    return Graph(
        root=node_id,
        direction=direction,
        depth=depth,
        nodes=nodes,
        edges=sorted(edges, key=lambda e: (str(e.src), e.rel.value, str(e.dst))),
        truncated=truncated,
    )


def _bfs_depths(root: uuid.UUID, edges: list[GraphEdge], direction: str) -> dict[uuid.UUID, int]:
    adj: dict[uuid.UUID, list[uuid.UUID]] = {}
    for e in edges:
        a, b = (e.src, e.dst) if direction == "up" else (e.dst, e.src)
        adj.setdefault(a, []).append(b)
    depths = {root: 0}
    frontier = [root]
    while frontier:
        nxt = []
        for u in frontier:
            for v in adj.get(u, ()):
                if v not in depths:
                    depths[v] = depths[u] + 1
                    nxt.append(v)
        frontier = nxt
    return depths


def with_activity_io(session: Session, g: Graph) -> Graph:
    """``g`` plus, for every activity in it, its direct ``used`` inputs, ``wasGeneratedBy``
    outputs and ``wasAssociatedWith`` agents (one hop, even outside the lineage direction). An
    OpenLineage run event needs all of them. Added nodes get depth -1."""
    acts = [n.id for n in g.nodes if n.kind is ProvKind.ACTIVITY]
    if not acts:
        return g
    rows = session.execute(
        text(
            "SELECT src, rel, dst FROM prov_edge WHERE "
            "(src = ANY(:ids) AND rel IN ('used', 'wasAssociatedWith')) OR "
            "(dst = ANY(:ids) AND rel = 'wasGeneratedBy')"
        ).bindparams(_IDS),
        {"ids": acts},
    ).all()
    have = {n.id for n in g.nodes}
    edges = {(e.src, e.rel, e.dst) for e in g.edges}
    new_edges = [GraphEdge(r.src, EdgeType(r.rel), r.dst) for r in rows]
    missing = {x for e in new_edges for x in (e.src, e.dst)} - have
    extra = []
    if missing:
        extra = [
            _gnode(r, -1)
            for r in session.execute(select(*_NODE_COLS).where(m.ProvNode.id.in_(missing))).all()
        ]
    return Graph(
        root=g.root,
        direction=g.direction,
        depth=g.depth,
        nodes=g.nodes + sorted(extra, key=lambda n: str(n.id)),
        edges=g.edges + [e for e in new_edges if (e.src, e.rel, e.dst) not in edges],
        truncated=g.truncated,
    )


# ---------------------------------------------------------------- verification (SEC-043)
def chain_head(session: Session) -> tuple[int, str] | None:
    r = session.execute(
        select(m.ProvBatch.seq, m.ProvBatch.batch_id).order_by(m.ProvBatch.seq.desc()).limit(1)
    ).first()
    return None if r is None else (r.seq, r.batch_id)


def verify_chain(
    session: Session,
    tenant_id: str,
    *,
    expected_head: str | None = None,
    keyring: signing.Keyring | None = None,
) -> VerifyResult:
    """Recompute every node hash and batch ID of the tenant's chain from the rows, check the
    ``prev`` links, the Ed25519 signatures (trusted keys only) and, if given, the expected head (an
    anchored head also catches a removed or rewritten LAST batch)."""
    tid = uuid.UUID(str(tenant_id))
    kr = keyring or signing.keyring()
    errors: list[str] = []
    batches = (
        session.execute(
            select(m.ProvBatch).where(m.ProvBatch.tenant_id == tid).order_by(m.ProvBatch.seq)
        )
        .scalars()
        .all()
    )
    node_rows = session.execute(
        select(*_NODE_COLS, m.ProvNode.ord)
        .where(m.ProvNode.tenant_id == tid)
        .order_by(m.ProvNode.batch_seq, m.ProvNode.ord)
    ).all()
    edge_rows = session.execute(
        select(m.ProvEdge.src, m.ProvEdge.rel, m.ProvEdge.dst, m.ProvEdge.batch_seq)
        .where(m.ProvEdge.tenant_id == tid)
        .order_by(m.ProvEdge.batch_seq, m.ProvEdge.ord)
    ).all()
    recs: dict[int, list[dict[str, Any]]] = {}
    for r in node_rows:
        rec = chain.node_record(str(r.id), r.kind, r.type, r.ref_id, r.content_hash, r.attrs or {})
        if chain.node_hash(rec) != r.node_hash:
            errors.append(f"node {r.id}: content does not match its node hash")
        recs.setdefault(r.batch_seq, []).append(rec)
    edge_recs: dict[int, list[dict[str, Any]]] = {}
    for r in edge_rows:
        edge_recs.setdefault(r.batch_seq, []).append(
            chain.edge_record(str(r.src), r.rel, str(r.dst))
        )
    known = {b.seq for b in batches}
    for s in sorted((set(recs) | set(edge_recs)) - known):
        errors.append(f"rows reference missing batch {s}")
    prev: str | None = None
    for i, b in enumerate(batches):
        if b.seq != i:
            errors.append(f"batch {i}: sequence gap (found seq {b.seq})")
        records = recs.get(b.seq, []) + edge_recs.get(b.seq, [])
        if len(records) != b.n_records:
            errors.append(f"batch {b.seq}: {len(records)} records, expected {b.n_records}")
        if b.prev_id != prev:
            errors.append(f"batch {b.seq}: prev does not match the previous batch id")
        try:
            doc = chain.batch_doc(str(tid), b.seq, b.prev_id, chain.ts(b.created_at), records)
            bid = chain.batch_id(doc)
        except chain.ChainError as e:
            errors.append(f"batch {b.seq}: {e}")
            bid = None
        if bid != b.batch_id:
            errors.append(f"batch {b.seq}: recomputed id does not match the stored id")
        if not kr.verify(b.key_id, b.batch_id.encode("ascii"), bytes(b.signature)):
            errors.append(f"batch {b.seq}: signature invalid or key {b.key_id!r} not trusted")
        prev = b.batch_id
    head = batches[-1].batch_id if batches else None
    if expected_head is not None and expected_head not in {b.batch_id for b in batches}:
        errors.append("anchored head is not in the chain")
    return VerifyResult(
        ok=not errors,
        tenant_id=str(tid),
        batches=len(batches),
        nodes=len(node_rows),
        edges=len(edge_rows),
        head=head,
        errors=errors,
    )
