"""3.1 acceptance (MEASUREMENT, not a pass/fail target): lineage traversal latency on a synthetic
provenance graph. The default run uses 10k nodes (fast, local); ``NF_PROV_BENCH_NODES=100000`` (set
in CI, or by hand) runs the 100k-node graph. Numbers are printed and written to
``$NF_PROV_BENCH_OUT`` (JSON) when set; the recorded figures live in the M3 report."""

from __future__ import annotations

import json
import os

import pytest
from nf_platform.db.context import tenant_session
from nf_platform.provenance import bench
from nf_platform.provenance.api import lineage
from prov_helpers import principal

pytestmark = pytest.mark.postgres


def test_traversal_latency_is_measured(engine, tenants, capsys):
    n = int(os.environ.get("NF_PROV_BENCH_NODES", "10000"))
    g = bench.build(engine, tenants.a, n)
    assert g.n_nodes >= n
    res = bench.measure(engine, g, samples=int(os.environ.get("NF_PROV_BENCH_SAMPLES", "100")))
    # shape sanity: the queries return what the graph promises
    assert res["up_artifact_unbounded"]["nodes_median"] == 7  # art, run, rec, conv, raw, 2 agents
    assert res["down_raw_unbounded"]["nodes_max"] >= 1 + 2 + bench.RUNS * (1 + bench.OUTS)
    # RLS: another tenant sees nothing of it
    with tenant_session(principal(tenants.b), engine=engine) as s, pytest.raises(LookupError):
        lineage(s, g.raws[0], "down", None)
    report = {"n_nodes": g.n_nodes, "n_edges": g.n_edges, "queries": res}
    with capsys.disabled():
        print("\nprovenance traversal benchmark:", json.dumps(report, indent=1))  # noqa: T201
    out = os.environ.get("NF_PROV_BENCH_OUT")
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=1)
