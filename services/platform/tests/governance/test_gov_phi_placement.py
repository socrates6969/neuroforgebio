"""5.7 acceptance: phi=true tenants cannot be placed on services that are not BAA-listed.

- the listed services are exactly the ones market/regulation.md §3 names (no invented list);
- IaC (static, local): every env module is mapped to services and declared to the phi-guard module;
  the guard's rule, evaluated on the env's services, rejects phi=true on non-listed services. The
  real `tofu validate/test` runs are CI-only (infra workflow; tofu is not installed locally);
- platform (real Postgres): a phi=true tenant is refused (403, audited) on uploads, streams and runs
  unless every placed service is listed; phi=false tenants are unaffected; tenant B unaffected;
- the website keeps "BAA ... (planned)".
"""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path

import pytest
from nf_platform import placement
from nf_platform.config import Placement
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[4]
POLICY_FILE = REPO / "infra" / "policy" / "phi-services.json"
REGULATION = (REPO / "market" / "regulation.md").read_text(encoding="utf-8")
LISTED = Placement(storage="aws_s3", database="aws_timestream", compute="aws_sagemaker_ai")


def _doc() -> dict:
    return json.loads(POLICY_FILE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- the list itself
def test_listed_services_come_from_regulation_md_section_3():
    doc = _doc()
    sec3 = REGULATION.split("## 3.")[1].split("## 4.")[0]
    assert doc["source"]["doc"] == "market/regulation.md §3"
    assert doc["source"]["quote"] in sec3, "quote must be verbatim from §3"
    assert "175+" in doc["source"]["quote"]
    named = {s["cited_as"] for s in doc["baa_covered"]}
    assert named == {"S3", "Timestream", "SageMaker AI"}
    for s in doc["baa_covered"]:
        assert s["cited_as"] in doc["source"]["quote"]
    assert "No provider BAA is signed" in doc["status"]
    assert not re.search(r"(?i)hipaa[- ]?compliant|\bcertified\b", json.dumps(doc))


def test_policy_parses_and_every_listed_service_is_in_the_catalog():
    pol = placement.parse_policy(_doc())
    assert pol.covered == {"aws_s3", "aws_timestream", "aws_sagemaker_ai"}
    with pytest.raises(ValueError):
        placement.parse_policy({**_doc(), "baa_covered": [{"id": "aws_everything"}]})


# ---------------------------------------------------------------- IaC (static)
MODULE_BLOCK = re.compile(r'module\s+"([^"]+)"\s*\{(.*?)\n\}', re.S)


def _env_modules(env: Path) -> dict[str, str]:
    """module label -> module directory name, for every module block of an env."""
    out = {}
    for tf in env.glob("*.tf"):
        for label, body in MODULE_BLOCK.findall(tf.read_text(encoding="utf-8")):
            src = re.search(r'source\s*=\s*"([^"]+)"', body).group(1)
            out[label] = src.rstrip("/").split("/")[-1]
    return out


def _guard_modules_used(env: Path) -> list[str]:
    body = dict(MODULE_BLOCK.findall((env / "main.tf").read_text(encoding="utf-8")))["phi_guard"]
    return re.findall(r'"([^"]+)"', re.search(r"modules_used\s*=\s*\[(.*?)\]", body, re.S)[1])


ENVS = sorted(p for p in (REPO / "infra" / "envs").iterdir() if p.is_dir())


@pytest.mark.parametrize("env", ENVS, ids=[e.name for e in ENVS])
def test_every_env_declares_its_modules_to_the_phi_guard(env):
    mods = _env_modules(env)
    assert mods.get("phi_guard") == "phi-guard", f"{env.name}: no phi_guard module"
    used = {d for label, d in mods.items() if label != "phi_guard"}
    assert set(_guard_modules_used(env)) == used, f"{env.name}: modules_used out of date"


def test_every_infra_module_maps_to_catalog_services():
    doc = _doc()
    modules = {p.name for p in (REPO / "infra" / "modules").iterdir() if p.is_dir()}
    assert modules - {"phi-guard"} <= set(doc["iac_modules"]), "unmapped infra module"
    for svcs in doc["iac_modules"].values():
        assert set(svcs) <= set(doc["catalog"])


def test_guard_module_reads_the_same_policy_and_fails_phi_on_non_listed():
    tf = (REPO / "infra" / "modules" / "phi-guard" / "main.tf").read_text(encoding="utf-8")
    assert "../../policy/phi-services.json" in tf
    assert re.search(r"condition\s*=\s*!var\.phi \|\| length\(local\.not_listed\) == 0", tf)
    tests = (REPO / "infra" / "modules" / "phi-guard" / "tests" / "guard.tftest.hcl").read_text()
    assert "expect_failures = [terraform_data.guard]" in tests
    wf = (REPO / ".github" / "workflows" / "infra.yml").read_text(encoding="utf-8")
    assert "tofu -chdir=infra/modules/phi-guard test" in wf


@pytest.mark.parametrize("env", ENVS, ids=[e.name for e in ENVS])
def test_phi_true_cannot_be_placed_on_the_env_services(env):
    """The guard rule (same data, same logic as the tofu module) on this env's services."""
    pol = placement.load_policy(POLICY_FILE)
    services = sorted({s for m in _guard_modules_used(env) for s in pol.iac_modules[m]})
    bad = placement.violations(True, services, pol)
    assert bad, "an env with non-listed services must reject phi=true"
    assert {"aws_rds_postgres", "aws_ecs_fargate"} <= set(bad)
    assert "aws_s3" not in bad
    assert placement.violations(False, services, pol) == []
    assert placement.violations(True, ["aws_s3", "aws_timestream", "aws_sagemaker_ai"], pol) == []


def test_every_catalog_service_outside_the_list_is_rejected_for_phi():
    pol = placement.load_policy(POLICY_FILE)
    for svc in pol.catalog:
        assert (placement.violations(True, [svc], pol) == []) == (svc in pol.covered), svc


# ---------------------------------------------------------------- platform (API)
pytestmark_pg = pytest.mark.postgres


def _set_phi(engine, tenant_id: str, phi: bool) -> None:
    with engine.begin() as c:  # superuser provisioning, as in the tenants fixture
        c.execute(text("UPDATE tenant SET phi = :p WHERE id = :i"), {"p": phi, "i": tenant_id})


def _upload_body(ids):
    return {
        "session_id": ids["session_id"],
        "filename": "x.edf",
        "size_bytes": 32,
        "synthetic": True,
    }


@pytestmark_pg
def test_phi_tenant_is_refused_on_non_listed_services(app, client, as_role, tree, engine, tenants):
    h = as_role("owner")
    _set_phi(engine, tenants.a, True)
    # default dev placement (local services) -> refused, audited
    r = client.post(
        f"/v1/datasets/{tree['dataset_id']}/uploads", json=_upload_body(tree), headers=h
    )
    assert r.status_code == 403, r.text
    assert "BAA-listed" in r.json()["detail"]
    r = client.post(
        "/v1/runs",
        json={"pipeline": tree["pipeline_ref"], "recording_id": tree["recording_id"]},
        headers=h,
    )
    assert r.status_code == 403, r.text
    with engine.connect() as c:
        n = c.execute(
            text("SELECT count(*) FROM audit_event WHERE type = 'authz.denied' AND action = :a"),
            {"a": "phi:placement"},
        ).scalar()
    assert n >= 2
    # one non-listed role (RDS) is enough to refuse
    app.state.settings = dataclasses.replace(
        app.state.settings, placement=dataclasses.replace(LISTED, database="aws_rds_postgres")
    )
    r = client.post(
        f"/v1/datasets/{tree['dataset_id']}/uploads", json=_upload_body(tree), headers=h
    )
    assert r.status_code == 403
    assert "aws_rds_postgres" in r.json()["detail"]
    # every placed service listed -> the placement guard passes
    app.state.settings = dataclasses.replace(app.state.settings, placement=LISTED)
    r = client.post(
        f"/v1/datasets/{tree['dataset_id']}/uploads", json=_upload_body(tree), headers=h
    )
    assert r.status_code == 201, r.text
    r = client.post(
        "/v1/runs",
        json={"pipeline": tree["pipeline_ref"], "recording_id": tree["recording_id"]},
        headers=h,
    )
    assert r.status_code == 202, r.text


@pytestmark_pg
def test_non_phi_tenants_are_unaffected(client, as_role, tree, engine, tenants):
    _set_phi(engine, tenants.b, True)  # tenant B's flag must not leak into tenant A
    r = client.post(
        f"/v1/datasets/{tree['dataset_id']}/uploads",
        json=_upload_body(tree),
        headers=as_role("owner"),
    )
    assert r.status_code == 201, r.text


@pytestmark_pg
def test_placement_fails_closed_on_a_broken_policy(
    client, as_role, tree, engine, tenants, monkeypatch
):
    _set_phi(engine, tenants.a, True)

    def boom(*a, **k):
        raise OSError("policy file unreadable")

    monkeypatch.setattr(placement, "load_policy", boom)
    r = client.post(
        f"/v1/datasets/{tree['dataset_id']}/uploads",
        json=_upload_body(tree),
        headers=as_role("owner"),
    )
    assert r.status_code == 403
    assert "could not be evaluated" in r.json()["detail"]


# ---------------------------------------------------------------- website wording
def _baa_strings(node, planned=False):
    """(string, planned) for every string mentioning BAA; ``planned`` = its object carries a
    planned/roadmap status."""
    if isinstance(node, dict):
        st = json.dumps(node.get("status", ""))
        planned = planned or bool(re.search(r"planned|roadmap", st))
        for v in node.values():
            yield from _baa_strings(v, planned)
    elif isinstance(node, list):
        for v in node:
            yield from _baa_strings(v, planned)
    elif isinstance(node, str) and re.search(r"\bBAA\b", node):
        yield node, planned


def test_website_keeps_baa_planned():
    """BUILD-GUIDE 5.7: the site keeps "BAA (planned)" until the owner signs a provider BAA."""
    hits = 0
    for f in (REPO / "packages" / "content" / "content").rglob("*.json"):
        for s, planned in _baa_strings(json.loads(f.read_text(encoding="utf-8"))):
            hits += 1
            assert planned or re.search(r"\(planned\)|roadmap", s), f"{f.name}: {s!r}"
    assert hits >= 3


# ---------------------------------------------------------------- draft policies
DRAFTS = ("risk-analysis.md", "incident-response.md", "access-review.md", "workforce-training.md")


@pytest.mark.parametrize("name", DRAFTS)
def test_draft_policies_are_marked_draft_and_pending_counsel(name):
    doc = (REPO / "docs" / "compliance" / name).read_text(encoding="utf-8")
    head = "\n".join(doc.splitlines()[:5])
    assert "DRAFT" in head and "Not legal advice" in head
    assert "No claim of HIPAA compliance" in head
    assert "Delivered to counsel: pending (owner action)" in head
    assert not re.search(r"(?i)\b(?:hipaa[- ]?compliant|certified|we are compliant)\b", doc)


def test_pack_index_lists_every_draft_and_the_delivery_record():
    idx = (REPO / "docs" / "compliance" / "README.md").read_text(encoding="utf-8")
    for name in DRAFTS:
        assert f"]({name})" in idx
    assert "| draft v0.1 | pending (owner action) |" in idx
    for s in _doc()["baa_covered"]:
        assert f"`{s['id']}`" in idx
