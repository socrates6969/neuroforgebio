"""3.1: M2's ingest provenance (raw --convert@version--> recording) lands in the graph, in the same
transaction as the recording rows, as one signed batch; lineage over the API walks it."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from nf_platform.db.context import tenant_session
from nf_platform.ingest.convert.model import CONVERTER_NAME, CONVERTER_VERSION
from nf_platform.ingest.uploads import worker
from nf_platform.provenance import api as prov
from nf_platform.storage.runtime import service_principal
from nf_synth.generate import SynthParams, generate
from nf_synth.writers import write_edf

pytestmark = pytest.mark.postgres
PART = 8 * 1024


@pytest.fixture(scope="module")
def edf_bytes(tmp_path_factory) -> bytes:
    data, truth = generate(SynthParams(seed=5, n_channels=4, sfreq=256, duration_s=14))
    return Path(write_edf(tmp_path_factory.mktemp("edf") / "x.edf", data, truth)).read_bytes()


def _upload(client, h, tree, blob: bytes) -> str:
    body = {
        "session_id": tree["session_id"],
        "filename": "rec.edf",
        "size_bytes": len(blob),
        "part_size": PART,
        "synthetic": True,
    }
    r = client.post(f"/v1/datasets/{tree['dataset_id']}/uploads", json=body, headers=h)
    assert r.status_code == 201, r.text
    uid = r.json()["id"]
    for n, i in enumerate(range(0, len(blob), PART), start=1):
        r = client.put(f"/v1/uploads/{uid}/parts/{n}", content=blob[i : i + PART], headers=h)
        assert r.status_code == 200
    r = client.post(
        f"/v1/uploads/{uid}/complete",
        json={"sha256": hashlib.sha256(blob).hexdigest()},
        headers=h,
    )
    assert r.status_code == 202, r.text
    return uid


def test_upload_worker_records_the_graph(
    client, as_role, tree, edf_bytes, storage, engine, tenants, prov_keys
):
    h = as_role("scientist")
    uid = _upload(client, h, tree, edf_bytes)
    (rid,) = worker.process_upload(storage, tenants.a, uid, engine=engine)
    converter = f"{CONVERTER_NAME}@{CONVERTER_VERSION}"
    with tenant_session(service_principal(tenants.a), engine=engine) as s:
        rec = prov.find_node(s, prov.ProvKind.ENTITY, "recording", rid)
        raw = prov.find_node(s, prov.ProvKind.ENTITY, "raw_file", uid)
        agent = prov.find_node(s, prov.ProvKind.AGENT, "software", converter)
        assert rec and raw and agent
        raw_node = prov.get_node(s, raw)
        assert raw_node.content_hash == "blob:sha256:" + hashlib.sha256(edf_bytes).hexdigest()
        up = prov.lineage(s, rec, "up", None)
        kinds = {(n.type, n.depth) for n in up.nodes}
        assert kinds == {("recording", 0), ("convert", 1), ("raw_file", 1), ("software", 2)}
        rels = {e.rel for e in up.edges}
        assert rels == {
            prov.EdgeType.WAS_GENERATED_BY,
            prov.EdgeType.WAS_DERIVED_FROM,
            prov.EdgeType.USED,
            prov.EdgeType.WAS_ASSOCIATED_WITH,
        }
        act = next(n for n in up.nodes if n.type == "convert")
        assert act.attrs["converter"] == converter and act.attrs["source_format"] == "edf"
        assert prov.verify_chain(s, tenants.a).ok
    # the recording is quarantined (M2 stub) but its lineage (ids/hashes only) is readable
    steward = as_role("data-steward")
    r = client.get(f"/v1/provenance/{rec}/lineage?direction=up", headers=steward)
    assert r.status_code == 200 and len(r.json()["nodes"]) == 4
    # a second upload reuses the converter agent node (unique per tenant)
    uid2 = _upload(client, h, tree, edf_bytes)
    (rid2,) = worker.process_upload(storage, tenants.a, uid2, engine=engine)
    with tenant_session(service_principal(tenants.a), engine=engine) as s:
        rec2 = prov.find_node(s, prov.ProvKind.ENTITY, "recording", rid2)
        up2 = prov.lineage(s, rec2, "up", None)
        assert agent in {n.id for n in up2.nodes}
        down = prov.lineage(s, agent, "down", None)
        assert {rec, rec2} <= {n.id for n in down.nodes}
