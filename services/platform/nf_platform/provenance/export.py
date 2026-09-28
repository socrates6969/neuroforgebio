"""PROV-JSON and OpenLineage export of a lineage graph (BUILD-GUIDE 3.7; BLUEPRINT §3.6).

- PROV-JSON (W3C member submission "PROV-JSON", https://www.w3.org/submissions/prov-json/): one
  ``entity``/``activity``/``agent`` per node, identified as ``nfnode:<uuid>`` (``urn:uuid:``),
  and one relation per edge (``used``, ``wasGeneratedBy``, ``wasDerivedFrom``, ``wasAttributedTo``,
  ``wasAssociatedWith``, ``wasInformedBy``) with the PROV-DM attribute names. Node attributes are
  kept as ``nf:*`` string attributes; ``nf:attrs`` is their canonical JSON (NF-CJSON).
- OpenLineage (spec 2-0-2, https://openlineage.io/spec/2-0-2/OpenLineage.json): one ``COMPLETE``
  RunEvent per activity in the graph. ``runId`` = the activity's node UUID, ``job`` = the activity
  type plus its associated agent (converter / PipelineVersion), ``inputs`` = entities it ``used``,
  ``outputs`` = entities that ``wasGeneratedBy`` it (the API first adds every activity's direct
  inputs/outputs with ``api.with_activity_io``). Namespace ``nf/<tenant id>``.

Only ids, hashes, types and the (non-identifying) node attributes are exported.
"""

from __future__ import annotations

from typing import Any

from nf_platform.audit import _canonical as cj
from nf_platform.provenance.api import EdgeType, Graph, GraphNode, ProvKind

PROV_NS = "http://www.w3.org/ns/prov#"
NF_NS = "urn:nf:prov:"
NODE_NS = "urn:uuid:"
OPENLINEAGE_SCHEMA_URL = "https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/RunEvent"
PRODUCER = "urn:nf:platform:provenance"

# relation -> (PROV-JSON section, attribute for src, attribute for dst)
_REL_ATTRS: dict[EdgeType, tuple[str, str, str]] = {
    EdgeType.USED: ("used", "prov:activity", "prov:entity"),
    EdgeType.WAS_GENERATED_BY: ("wasGeneratedBy", "prov:entity", "prov:activity"),
    EdgeType.WAS_DERIVED_FROM: ("wasDerivedFrom", "prov:generatedEntity", "prov:usedEntity"),
    EdgeType.WAS_ATTRIBUTED_TO: ("wasAttributedTo", "prov:entity", "prov:agent"),
    EdgeType.WAS_ASSOCIATED_WITH: ("wasAssociatedWith", "prov:activity", "prov:agent"),
    EdgeType.WAS_INFORMED_BY: ("wasInformedBy", "prov:informed", "prov:informant"),
}


def _qn(node_id: Any) -> str:
    return f"nfnode:{node_id}"


def _node_attrs(n: GraphNode) -> dict[str, Any]:
    a: dict[str, Any] = {
        "prov:type": {"$": f"nf:{n.type}", "type": "prov:QUALIFIED_NAME"},
        "prov:label": n.type,
        "nf:nodeHash": n.node_hash,
        "nf:batchSeq": n.batch_seq,
    }
    if n.ref_id is not None:
        a["nf:ref"] = n.ref_id
    if n.content_hash is not None:
        a["nf:content"] = n.content_hash
    if n.attrs:
        a["nf:attrs"] = cj.canonicalize(n.attrs).decode("utf-8")
    return a


def to_prov_json(g: Graph) -> dict[str, Any]:
    doc: dict[str, Any] = {"prefix": {"prov": PROV_NS, "nf": NF_NS, "nfnode": NODE_NS}}
    section = {ProvKind.ENTITY: "entity", ProvKind.ACTIVITY: "activity", ProvKind.AGENT: "agent"}
    for n in g.nodes:
        doc.setdefault(section[n.kind], {})[_qn(n.id)] = _node_attrs(n)
    for i, e in enumerate(g.edges):
        name, a_src, a_dst = _REL_ATTRS[e.rel]
        doc.setdefault(name, {})[f"_:r{i}"] = {a_src: _qn(e.src), a_dst: _qn(e.dst)}
    return doc


def _ol_time(n: GraphNode) -> str:
    return n.created_at.astimezone().isoformat().replace("+00:00", "Z")


def _dataset(ns: str, n: GraphNode) -> dict[str, Any]:
    return {"namespace": ns, "name": f"{n.type}/{n.ref_id or n.id}"}


def to_openlineage(g: Graph, *, tenant_id: str) -> list[dict[str, Any]]:
    """One OpenLineage RunEvent per activity node of the graph (edges limited to the graph)."""
    ns = f"nf/{tenant_id}"
    by_id = {n.id: n for n in g.nodes}
    inputs: dict[Any, list[GraphNode]] = {}
    outputs: dict[Any, list[GraphNode]] = {}
    agents: dict[Any, list[GraphNode]] = {}
    for e in g.edges:
        if e.rel is EdgeType.USED:
            inputs.setdefault(e.src, []).append(by_id[e.dst])
        elif e.rel is EdgeType.WAS_GENERATED_BY:
            outputs.setdefault(e.dst, []).append(by_id[e.src])
        elif e.rel is EdgeType.WAS_ASSOCIATED_WITH:
            agents.setdefault(e.src, []).append(by_id[e.dst])
    events = []
    for n in g.nodes:
        if n.kind is not ProvKind.ACTIVITY:
            continue
        job = n.type
        for a in sorted(agents.get(n.id, []), key=lambda x: str(x.id)):
            job += f":{a.ref_id or a.id}"
        events.append(
            {
                "eventType": "COMPLETE",
                "eventTime": _ol_time(n),
                "producer": PRODUCER,
                "schemaURL": OPENLINEAGE_SCHEMA_URL,
                "run": {"runId": str(n.id)},
                "job": {"namespace": ns, "name": job},
                "inputs": [_dataset(ns, x) for x in sorted(inputs.get(n.id, []), key=_key)],
                "outputs": [_dataset(ns, x) for x in sorted(outputs.get(n.id, []), key=_key)],
            }
        )
    return events


def _key(n: GraphNode) -> str:
    return str(n.id)
