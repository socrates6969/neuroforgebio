"""Lineage traversal benchmark (BUILD-GUIDE 3.1: "traversal p95 latency on a 100k-node synthetic
graph is measured and recorded; a target is set from that measurement").

Synthetic graph shaped like the platform's provenance (not a random graph): per ingested raw file
``raw_file -> convert -> recording`` (converter agent shared), 5 pipeline runs per recording (each
``used`` the recording, ``wasAssociatedWith`` one of 20 shared PipelineVersion agents, generated 3
artifacts), one report per recording ``wasDerivedFrom`` each run's first artifact, and reports
chained in groups of 10 (``wasDerivedFrom`` the previous report). 24 nodes and ~34 edges per raw
file; ``n_nodes=100_000`` gives 4,167 raw files.

Rows are bulk-loaded with COPY as the database owner (one placeholder batch; node hashes are not
meaningful, so do not run verify_chain on it). Queries run through ``tenant_session`` as the app
role (RLS on), i.e. what an API request pays minus HTTP.

Run: ``python -m nf_platform.provenance.bench --url <superuser url> [--nodes 100000]``.
"""

from __future__ import annotations

import argparse
import math
import random
import statistics
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, create_engine, text

from nf_platform.db.context import Principal, tenant_session
from nf_platform.provenance import api

PER_UNIT = 24
RUNS, OUTS, PVS, CHAIN = 5, 3, 20, 10


@dataclass
class SynthGraph:
    tenant_id: str
    n_nodes: int
    n_edges: int
    raws: list[uuid.UUID]
    artifacts: list[uuid.UUID]
    reports: list[uuid.UUID]
    pvs: list[uuid.UUID]


def build(engine: Engine, tenant_id: str, n_nodes: int, seed: int = 0) -> SynthGraph:
    """Create the synthetic graph for ``tenant_id`` (which must exist)."""
    rng = random.Random(seed)
    units = math.ceil(n_nodes / PER_UNIT)
    nodes: list[tuple[uuid.UUID, str, str, str | None]] = []
    edges: list[tuple[uuid.UUID, str, uuid.UUID]] = []

    def node(kind: str, type_: str, ref: str | None = None) -> uuid.UUID:
        u = uuid.UUID(int=rng.getrandbits(128), version=4)
        nodes.append((u, kind, type_, ref))
        return u

    converter = node("agent", "software", "nf-convert@bench")
    pvs = [node("agent", "pipeline_version", f"pv-bench-{i}") for i in range(PVS)]
    raws, arts, reports = [], [], []
    prev_report = None
    for u in range(units):
        raw = node("entity", "raw_file", f"raw-{u}")
        conv = node("activity", "convert")
        rec = node("entity", "recording", f"rec-{u}")
        edges += [
            (conv, "used", raw),
            (conv, "wasAssociatedWith", converter),
            (rec, "wasGeneratedBy", conv),
            (rec, "wasDerivedFrom", raw),
        ]
        firsts = []
        for r in range(RUNS):
            run = node("activity", "run")
            edges += [(run, "used", rec), (run, "wasAssociatedWith", pvs[(u + r) % PVS])]
            for o in range(OUTS):
                a = node("entity", "artifact")
                edges.append((a, "wasGeneratedBy", run))
                arts.append(a)
                if o == 0:
                    firsts.append(a)
        report = node("entity", "report")
        edges += [(report, "wasDerivedFrom", a) for a in firsts]
        if prev_report is not None and u % CHAIN:
            edges.append((report, "wasDerivedFrom", prev_report))
        prev_report = report
        raws.append(raw)
        reports.append(report)

    tid = uuid.UUID(tenant_id)
    raw_conn = engine.raw_connection()
    try:
        cur = raw_conn.cursor()
        cur.execute(
            "INSERT INTO prov_batch (tenant_id, seq, batch_id, prev_id, created_at, n_records, "
            "key_id, signature) VALUES (%s, 0, %s, NULL, %s, %s, 'bench', %s)",
            (
                tid,
                "provb:sha256:" + "0" * 64,
                datetime.now(UTC),
                len(nodes) + len(edges),
                b"\0" * 64,
            ),
        )
        with cur.copy(
            "COPY prov_node (id, tenant_id, kind, type, ref_id, node_hash, batch_seq, ord) "
            "FROM STDIN"
        ) as cp:
            for i, (u, kind, type_, ref) in enumerate(nodes):
                cp.write_row((u, tid, kind, type_, ref, "0" * 64, 0, i))
        with cur.copy("COPY prov_edge (tenant_id, src, rel, dst, batch_seq, ord) FROM STDIN") as cp:
            for i, (s, rel, d) in enumerate(edges):
                cp.write_row((tid, s, rel, d, 0, i))
        cur.execute("ANALYZE prov_node")
        cur.execute("ANALYZE prov_edge")
        raw_conn.commit()
    finally:
        raw_conn.close()
    return SynthGraph(tenant_id, len(nodes), len(edges), raws, arts, reports, pvs)


def _pct(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, max(0, math.ceil(q * len(xs)) - 1))]


def measure(
    engine: Engine, g: SynthGraph, *, samples: int = 200, seed: int = 1
) -> dict[str, dict[str, Any]]:
    """p50/p95/max latency (ms) and result sizes of the benchmark queries."""
    rng = random.Random(seed)
    p = Principal("svc:bench", g.tenant_id, frozenset(), frozenset(), "service", False)
    cases = {
        "up_artifact_unbounded": (g.artifacts, "up", None),
        "down_raw_unbounded": (g.raws, "down", None),
        "up_report_unbounded": (g.reports, "up", None),
        "up_artifact_depth3": (g.artifacts, "up", 3),
        "down_pv_agent_depth2": (g.pvs, "down", 2),
    }
    out: dict[str, dict[str, Any]] = {}
    for name, (pool, direction, depth) in cases.items():
        n = min(samples, 40) if name.startswith("down_pv") else samples
        times, sizes = [], []
        for _ in range(3):  # warm-up
            with tenant_session(p, engine=engine) as s:
                api.lineage(s, rng.choice(pool), direction, depth)
        for _ in range(n):
            root = rng.choice(pool)
            t0 = time.perf_counter()
            with tenant_session(p, engine=engine) as s:
                res = api.lineage(s, root, direction, depth)
            times.append((time.perf_counter() - t0) * 1000)
            sizes.append(len(res.nodes))
        out[name] = {
            "samples": n,
            "p50_ms": round(statistics.median(times), 2),
            "p95_ms": round(_pct(times, 0.95), 2),
            "max_ms": round(max(times), 2),
            "nodes_median": int(statistics.median(sizes)),
            "nodes_max": max(sizes),
        }
    return out


def main() -> None:  # pragma: no cover - manual tool
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True, help="superuser URL of a migrated database")
    ap.add_argument("--nodes", type=int, default=100_000)
    ap.add_argument("--samples", type=int, default=200)
    args = ap.parse_args()
    eng = create_engine(args.url)
    tid = str(uuid.uuid4())
    with eng.begin() as c:
        c.execute(text("INSERT INTO tenant (id, name) VALUES (:i, 'bench')"), {"i": tid})
    t0 = time.perf_counter()
    g = build(eng, tid, args.nodes)
    print(f"built {g.n_nodes} nodes / {g.n_edges} edges in {time.perf_counter() - t0:.1f}s")  # noqa: T201
    for k, v in measure(eng, g, samples=args.samples).items():
        print(k, v)  # noqa: T201


if __name__ == "__main__":  # pragma: no cover
    main()
