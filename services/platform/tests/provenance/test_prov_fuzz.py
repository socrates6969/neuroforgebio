"""3.1 acceptance: graph fuzz test. Random DAGs of up to 10k nodes (seeded) are written through
``record()`` in several batches; ``lineage()`` up/down, bounded and unbounded, must equal a
reference in-memory BFS (same node set, same minimum depth, same traversed edges). The whole chain
then verifies."""

from __future__ import annotations

import random
import uuid
from collections import deque

import pytest
from nf_platform.db.context import tenant_session
from nf_platform.provenance.api import (
    REL_KINDS,
    EdgeType,
    NodeSpec,
    ProvKind,
    lineage,
    record,
    verify_chain,
)
from prov_helpers import principal

pytestmark = pytest.mark.postgres

E, A, G = ProvKind.ENTITY, ProvKind.ACTIVITY, ProvKind.AGENT
REL_FOR = {kinds: rel for rel, kinds in REL_KINDS.items()}  # (src kind, dst kind) -> relation


def random_dag(
    n: int, rng: random.Random
) -> tuple[list[ProvKind], list[tuple[int, EdgeType, int]]]:
    """Nodes 0..n-1 in creation order; every edge points from a newer to an older node. Targets
    are drawn from a window of recent nodes (long chains) plus occasional far jumps (wide DAGs)."""
    kinds = [rng.choices((E, A, G), weights=(6, 3, 1))[0] for _ in range(n)]
    edges: list[tuple[int, EdgeType, int]] = []
    for i in range(1, n):
        if kinds[i] is G:
            continue  # agents have no outgoing relation in our set
        targets = set()
        for _ in range(rng.choice((0, 1, 1, 2, 2, 3))):
            j = i - 1 - int(rng.random() * min(i, 30)) if rng.random() < 0.85 else rng.randrange(i)
            targets.add(j)
        for j in sorted(targets):
            rel = REL_FOR.get((kinds[i], kinds[j]))
            if rel is not None:
                edges.append((i, rel, j))
    return kinds, edges


def write_graph(engine, tenant, kinds, edges, batch: int) -> list[uuid.UUID]:
    """Insert via record() in batches of ``batch`` nodes; edges into earlier batches use UUIDs."""
    p = principal(tenant)
    ids: list[uuid.UUID] = []
    by_src: dict[int, list[tuple[int, EdgeType, int]]] = {}
    for e in edges:
        by_src.setdefault(e[0], []).append(e)
    for start in range(0, len(kinds), batch):
        stop = min(start + batch, len(kinds))
        nodes = [
            NodeSpec(k, f"t{k.value[:3]}", None, None, {"i": i})
            for i, k in zip(range(start, stop), kinds[start:stop], strict=True)
        ]
        call_edges = []
        for s in range(start, stop):
            for _, rel, d in by_src.get(s, ()):
                call_edges.append((s - start, rel, d - start if d >= start else ids[d]))
        with tenant_session(p, engine=engine) as sess:
            ids += record(sess, p, nodes, call_edges).node_ids
    return ids


def reference(n, edges, root, direction, depth):
    adj: dict[int, list[int]] = {}
    for s, _, d in edges:
        a, b = (s, d) if direction == "up" else (d, s)
        adj.setdefault(a, []).append(b)
    dist = {root: 0}
    q = deque([root])
    while q:
        u = q.popleft()
        if depth is not None and dist[u] >= depth:
            continue
        for v in adj.get(u, ()):
            if v not in dist:
                dist[v] = dist[u] + 1
                q.append(v)
    expanded = {u for u, d in dist.items() if depth is None or d < depth}
    trav = {(s, rel, d) for s, rel, d in edges if (s if direction == "up" else d) in expanded}
    return dist, trav


@pytest.mark.parametrize(
    ("seed", "n", "batch"),
    [(1, 40, 7), (2, 300, 64), (3, 1500, 500), (4, 10_000, 2_500)],
    ids=["n40", "n300", "n1500", "n10k"],
)
def test_lineage_matches_reference(engine, tenants, seed, n, batch):
    rng = random.Random(seed)
    kinds, edges = random_dag(n, rng)
    ids = write_graph(engine, tenants.a, kinds, edges, batch)
    index = {u: i for i, u in enumerate(ids)}
    roots = rng.sample(range(n), min(n, 12))
    p = principal(tenants.a)
    biggest = 0
    with tenant_session(p, engine=engine) as s:
        for root in roots:
            for direction in ("up", "down"):
                for depth in (None, 0, 1, rng.randint(2, 6)):
                    g = lineage(s, ids[root], direction, depth)
                    want_dist, want_edges = reference(n, edges, root, direction, depth)
                    got_dist = {index[x.id]: x.depth for x in g.nodes}
                    assert got_dist == want_dist, (seed, root, direction, depth)
                    got_edges = {(index[e.src], e.rel, index[e.dst]) for e in g.edges}
                    assert got_edges == want_edges, (seed, root, direction, depth)
                    assert not g.truncated
                    biggest = max(biggest, len(g.nodes))
        res = verify_chain(s, tenants.a)
    if n >= 1500:  # the fuzz exercises real traversals, not only leaves
        assert biggest > 200, biggest
    assert res.ok, res.errors[:5]
    assert res.nodes == n and res.edges == len(edges)


def test_truncation_keeps_shallow_nodes(engine, tenants):
    rng = random.Random(9)
    kinds, edges = random_dag(400, rng)
    ids = write_graph(engine, tenants.a, kinds, edges, 400)
    p = principal(tenants.a)
    with tenant_session(p, engine=engine) as s:
        root = next(i for i in range(399, 0, -1) if len(lineage(s, ids[i], "up", None).nodes) > 30)
        full = lineage(s, ids[root], "up", 50)
        cut = lineage(s, ids[root], "up", 50, max_nodes=10)
    assert cut.truncated and len(cut.nodes) == 10
    assert max(x.depth for x in cut.nodes) <= sorted(x.depth for x in full.nodes)[10]
