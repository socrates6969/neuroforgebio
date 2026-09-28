"""5.8 acceptance: FDA Evidence Kit v0 (a scaffold, not a submission).

- every requirement ID in docs/requirements has >= 1 linked (existing) test, or is flagged;
- the package regenerates byte-identically from the same inputs (API and builder);
- two-tenant isolation; authorize + policy.check + audit on the route;
- results come from CI JUnit XML; SBOM included when supplied, else "SBOM attached in CI";
- known anomalies = the open issues of docs/hive/M*-REPORT.md; SOUP versions from manifests;
- labelled "scaffold, not a submission"; regulatory texts named, never quoted, marked UNVERIFIED.
"""

from __future__ import annotations

import hashlib
import io
import json
import tomllib
import zipfile
from pathlib import Path

import pytest
from nf_platform.evidence import kit
from nf_platform.governance import policy
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[4]
SBOM_FIXTURE = REPO / "tools" / "sbom-props" / "test" / "fixtures" / "sbom-1.6.cdx.json"
URL = "/v1/exports/fda-evidence"

JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="4">
<testcase classname="services.platform.tests.core.test_core_authz_matrix"
 name="test_matrix[owner]"/>
<testcase classname="services.platform.tests.core.test_core_authz_matrix"
 name="test_matrix[viewer]"/>
<testcase classname="services.platform.tests.core.test_core_oidc" name="test_wrong_signing_key">
<failure message="boom"/></testcase>
<testcase classname="services.platform.tests.ingest.test_uploads" name="test_sec071_synthetic_only">
<skipped message="ci-only"/></testcase>
</testsuite></testsuites>
"""


def _unzip(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return {i.filename: z.read(i) for i in z.infolist()}


def _inputs(tmp_path: Path, **kw) -> kit.KitInputs:
    j = tmp_path / "junit.xml"
    j.write_text(JUNIT, encoding="utf-8")
    return kit.KitInputs(repo_root=REPO, junit=(j,), **kw)


# ---------------------------------------------------------------- requirements
def test_every_requirement_has_a_linked_test_or_is_flagged():
    reqs = kit.load_requirements(REPO)
    assert len(reqs) >= 20
    missing = [(r.id, t) for r in reqs for t in r.tests if not kit.linked_test_exists(REPO, t)]
    assert missing == [], "linked tests must exist"
    for r in reqs:
        assert r.tests or r.flag, r.id
    matrix, _, flagged = kit.traceability(kit.KitInputs(repo_root=REPO))
    assert set(flagged) == {r.id for r in reqs if not r.tests}
    assert {"REQ-SEC-104", "REQ-SEC-110"} <= set(flagged)
    for row in matrix["requirements"]:
        assert row["tests"] or row["flag"], row["id"]


def test_requirement_without_test_or_flag_is_refused(tmp_path):
    root = tmp_path
    (root / "docs" / "requirements").mkdir(parents=True)
    (root / "docs" / "requirements" / "x.yaml").write_text(
        "schema: nf.requirements/v1\nrequirements:\n  - id: REQ-X\n    title: t\n    tests: []\n"
    )
    with pytest.raises(kit.EvidenceError, match="linked test or a flag"):
        kit.load_requirements(root)


def test_dangling_test_link_is_flagged(tmp_path):
    root = tmp_path
    (root / "docs" / "requirements").mkdir(parents=True)
    (root / "docs" / "requirements" / "x.yaml").write_text(
        "schema: nf.requirements/v1\nrequirements:\n  - id: REQ-X\n    title: t\n"
        "    tests: [services/nope/test_nope.py::test_gone]\n"
    )
    matrix, _, flagged = kit.traceability(kit.KitInputs(repo_root=root))
    assert flagged == ["REQ-X"]
    assert "linked test not found" in matrix["requirements"][0]["flag"]


def test_results_come_from_ci_junit(tmp_path):
    matrix, csv_bytes, _ = kit.traceability(_inputs(tmp_path))
    res = {t["test"]: t["result"] for r in matrix["requirements"] for t in r["tests"]}
    p = "services/platform/tests/"
    assert res[p + "core/test_core_authz_matrix.py::test_matrix"] == "passed"
    assert res[p + "core/test_core_oidc.py::test_wrong_signing_key"] == "failed"
    assert res[p + "ingest/test_uploads.py::test_sec071_synthetic_only"] == "skipped"
    assert (
        res[p + "core/test_core_audit.py::test_every_data_read_route_emits_an_event"] == "not run"
    )
    assert csv_bytes.startswith(b"requirement,title,source,test,result,flag\n")
    no_ci, _, _ = kit.traceability(kit.KitInputs(repo_root=REPO))
    first = no_ci["requirements"][0]["tests"][0]["result"]
    assert first.startswith("no CI results supplied")


# ---------------------------------------------------------------- contents
def test_known_anomalies_are_the_report_open_issues():
    items = kit.known_anomalies(REPO)
    reports = {i["report"] for i in items}
    assert {"M2-REPORT.md", "M3-REPORT.md"} <= reports
    m2 = [i for i in items if i["report"] == "M2-REPORT.md"]
    assert [i["item"] for i in m2] == list(range(1, len(m2) + 1))
    assert m2[0]["text"].startswith("**No job queue yet.**")
    assert all(i["section"].lower().startswith("open issues") for i in items)


def test_soup_versions_come_from_the_manifests():
    soup = {c["id"]: c for c in kit.soup_entries(REPO)}
    # read from the crate manifest, not pinned here: the version moves with SDK releases (M4)
    cargo = tomllib.loads((REPO / "core" / "nf-core" / "Cargo.toml").read_text(encoding="utf-8"))
    assert soup["nf-core"]["version"] == cargo["package"]["version"]
    assert soup["nf-steps"]["version"] == "1.0.0"
    assert soup["nf-runner"]["version"] == "0.1.0"
    reqs = {r.id for r in kit.load_requirements(REPO)}
    for c in soup.values():
        assert set(c["requirements"]) <= reqs


def test_sbom_included_when_supplied_else_attached_in_ci(tmp_path):
    prov = {"prefix": {}}
    with_sbom, _ = kit.build(
        _inputs(tmp_path, sbom=SBOM_FIXTURE), tenant_id="t", node_id="n", prov_json=prov
    )
    files = _unzip(with_sbom)
    assert json.loads(files["fda-evidence-kit/sbom/sbom.cdx.json"])["bomFormat"] == "CycloneDX"
    without, _ = kit.build(_inputs(tmp_path), tenant_id="t", node_id="n", prov_json=prov)
    note = _unzip(without)["fda-evidence-kit/sbom/SBOM-ATTACHED-IN-CI.txt"].decode()
    assert note.startswith("SBOM attached in CI.")


def test_labelled_scaffold_and_regulatory_texts_only_named(tmp_path):
    data, _ = kit.build(_inputs(tmp_path), tenant_id="t", node_id="n", prov_json={})
    files = _unzip(data)
    labelled = [
        "README.txt",
        "manifest.json",
        "traceability/matrix.json",
        "release-notes/known-anomalies.md",
        "release-notes/known-anomalies.json",
        "soup/soup.json",
        "sbom/SBOM-ATTACHED-IN-CI.txt",
    ]
    for name in labelled:
        assert kit.LABEL.encode() in files["fda-evidence-kit/" + name], name
    readme = files["fda-evidence-kit/README.txt"].decode()
    assert "IEC 62304" in readme and readme.count("UNVERIFIED") >= 3
    assert "is not a regulatory" in readme
    man = json.loads(files["fda-evidence-kit/manifest.json"])
    for name, digest in man["files"].items():
        assert hashlib.sha256(files["fda-evidence-kit/" + name]).hexdigest() == digest


def test_builder_is_deterministic_and_input_sensitive(tmp_path):
    prov = {"entity": {"nfnode:1": {"prov:label": "recording"}}}
    a, _ = kit.build(_inputs(tmp_path), tenant_id="t", node_id="n", prov_json=prov)
    b, _ = kit.build(_inputs(tmp_path), tenant_id="t", node_id="n", prov_json=prov)
    assert a == b
    with zipfile.ZipFile(io.BytesIO(a)) as z:
        infos = z.infolist()
    assert [i.filename for i in infos] == sorted(i.filename for i in infos)
    assert {i.date_time for i in infos} == {kit.ZIP_DATE}
    assert {i.external_attr for i in infos} == {0o100644 << 16}
    c, _ = kit.build(_inputs(tmp_path, release="1.2.3"), tenant_id="t", node_id="n", prov_json=prov)
    assert c != a


# ---------------------------------------------------------------- the route
def _post(client, h, node_id, **kw):
    return client.post(URL, json={"node_id": node_id, **kw}, headers=h)


def test_kit_regenerates_byte_identically(app, client, as_role, tree, tmp_path):
    app.state.evidence_inputs = _inputs(tmp_path, sbom=SBOM_FIXTURE)
    h = as_role("auditor")
    r1 = _post(client, h, tree["node_id"], release="0.1.0")
    r2 = _post(client, h, tree["node_id"], release="0.1.0")
    assert r1.status_code == 200, r1.text
    assert r1.headers["content-type"] == "application/zip"
    assert r1.headers["x-nf-label"] == "scaffold-not-a-submission"
    assert r1.content == r2.content
    files = _unzip(r1.content)
    prov = json.loads(files["fda-evidence-kit/provenance/prov.json"])
    assert f"nfnode:{tree['node_id']}" in json.dumps(prov)
    man = json.loads(files["fda-evidence-kit/manifest.json"])
    assert man["release"] == "0.1.0" and man["provenance_root"] == tree["node_id"]


def test_two_tenant_isolation(app, client, as_role, tree, tenants, tmp_path):
    app.state.evidence_inputs = _inputs(tmp_path)
    # tenant B cannot export tenant A's node: 404 (no existence leak)
    r = _post(client, as_role("owner", tenant=tenants.b), tree["node_id"])
    assert r.status_code == 404, r.text
    r = _post(client, as_role("owner"), tree["node_id"])
    assert r.status_code == 200
    man = json.loads(_unzip(r.content)["fda-evidence-kit/manifest.json"])
    assert man["tenant_id"] == tenants.a


def test_export_is_audited_and_policy_checked(
    app, client, as_role, tree, engine, tmp_path, monkeypatch
):
    app.state.evidence_inputs = _inputs(tmp_path)
    calls = []
    real = policy.check

    def spy(principal, action, resource, **kw):
        calls.append((action, resource.type, resource.node_ids))
        return real(principal, action, resource, **kw)

    monkeypatch.setattr(policy, "check", spy)
    r = _post(client, as_role("data-steward"), tree["node_id"])
    assert r.status_code == 200, r.text
    assert calls and calls[-1][0] == "evidence:export"
    digest = hashlib.sha256(r.content).hexdigest()
    with engine.connect() as c:
        row = c.execute(
            text(
                "SELECT details FROM audit_event WHERE type = 'data.export' "
                "AND action = 'evidence:export' ORDER BY seq DESC LIMIT 1"
            )
        ).one()
    assert row.details["format"] == "fda-evidence-kit-v0"
    assert row.details["sha256"] == digest
    # roles outside the compliance set, and API keys, are refused
    assert _post(client, as_role("scientist"), tree["node_id"]).status_code == 403
    key = client.post(
        "/v1/api-keys",
        json={"name": "k", "roles": ["viewer"], "scopes": ["metadata:read", "data:read"]},
        headers=as_role("owner"),
    ).json()["key"]
    r = client.post(
        URL, json={"node_id": tree["node_id"]}, headers={"Authorization": f"Bearer {key}"}
    )
    assert r.status_code == 403
