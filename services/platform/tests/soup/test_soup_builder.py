"""6.5 SOUP/OTS document per model version: the builder (no database).

Acceptance: the export includes every dependency in the model's container SBOM. Locally that SBOM
is a fixture (``fixtures/model-container.cdx.json``); in CI the real CycloneDX SBOM built by the
``security`` job is checked by :func:`test_soup_ci_sbom_every_component_is_exported`
(``NF_MODEL_SBOM``; skipped when unset).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from nf_platform.registry import soup

REPO = Path(__file__).resolve().parents[4]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "model-container.cdx.json"

MODEL = {"id": "11111111-1111-4111-8111-111111111111", "name": "toy-decoder", "card": {"a": 1}}
VERSION = {
    "id": "22222222-2222-4222-8222-222222222222",
    "version": 2,
    "created_at": "2026-09-26T10:00:00+00:00",
    "code_commit": "75c5f39",
    "pipeline_version_ids": ["p@1"],
    "weights_sha256": "ab" * 32,
    "parent_version_id": None,
    "prov_node_id": "33333333-3333-4333-8333-333333333333",
    "intended_use": "Research decoding of synthetic band-power features.",
    "use_restrictions": ["research_only", "no_clinical_decision"],
    "training": {
        "algorithm": "sisa-logreg",
        "subject_count": 7,
        "sisa": {"shards": 3, "slices": 2, "withdrawn_subjects": 1},
    },
}


def _expected(bom: dict[str, Any]) -> set[tuple[str, str, str]]:
    """Every component of a CycloneDX document, nested ones included (independent walker)."""
    out: set[tuple[str, str, str]] = set()
    stack = list(bom.get("components") or [])
    while stack:
        c = stack.pop()
        out.add((c["name"], str(c.get("version") or "unknown"), str(c.get("purl") or "")))
        stack.extend(c.get("components") or [])
    return out


def _doc(**kw) -> dict[str, Any]:
    inputs = soup.SoupInputs(model=MODEL, version=VERSION, repo_root=REPO, **kw)
    return json.loads(soup.build(inputs))


def test_soup_every_container_sbom_component_is_exported():
    bom = json.loads(FIXTURE.read_text("utf-8"))
    doc = _doc(sbom=bom, sbom_sha256="cd" * 32)
    got = {(d["name"], d["version"], d["purl"]) for d in doc["dependencies"]["components"]}
    want = _expected(bom)
    assert len(want) == 9  # nested OS packages and cffi included
    assert want <= got and len(got) == len(want)
    src = doc["dependencies"]["source"]
    assert src["kind"] == "container-sbom" and src["component_count"] == 9
    assert src["sha256"] == "cd" * 32
    assert src["subject"]["name"] == "nf-train-worker"
    by = {d["name"]: d for d in doc["dependencies"]["components"]}
    assert by["openssl"]["support_level"] == "maintained"
    assert by["openssl"]["end_of_support"] == "2026-06-30"
    assert by["openssl"]["parent"] == "os:debian@12.11"
    assert by["legacy-unmaintained-lib"]["support_level"] == "unmaintained"
    assert by["sqlalchemy"]["support_level"] == "unknown"
    assert by["numpy"]["licenses"] == ["BSD-3-Clause"]
    assert by["numpy"]["supplier"] == "NumPy Developers"


def test_soup_repo_sbom_fixture_every_component_is_exported():
    """The 5.8 SBOM fixture (another shape: npm, nested) is covered too."""
    bom = json.loads((REPO / "tools/sbom-props/test/fixtures/sbom-1.6.cdx.json").read_text("utf-8"))
    doc = _doc(sbom=bom)
    got = {(d["name"], d["version"], d["purl"]) for d in doc["dependencies"]["components"]}
    assert _expected(bom) == got


@pytest.mark.skipif(not os.environ.get("NF_MODEL_SBOM"), reason="CI only: NF_MODEL_SBOM unset")
def test_soup_ci_sbom_every_component_is_exported():
    """CI (job security): the real CycloneDX SBOM of the build (NF_MODEL_SBOM)."""
    bom = json.loads(Path(os.environ["NF_MODEL_SBOM"]).read_text("utf-8"))
    doc = _doc(sbom=bom)
    got = {(d["name"], d["version"], d["purl"]) for d in doc["dependencies"]["components"]}
    want = _expected(bom)
    assert want and want <= got
    assert doc["dependencies"]["source"]["component_count"] == len(
        doc["dependencies"]["components"]
    )


def test_soup_required_sections_and_statements():
    doc = _doc(sbom=json.loads(FIXTURE.read_text("utf-8")))
    assert doc["schema"] == soup.SCHEMA
    assert doc["label"] == "SCAFFOLD, NOT A SUBMISSION"
    # SEC-092
    assert "not intended for real-time or safety-critical control" in doc["statement"].lower()
    assert doc["intended_use"] == VERSION["intended_use"]
    assert doc["use_restrictions"] == ["no_clinical_decision", "research_only"]
    assert {"actuator_control", "closed_loop_stimulation", "neuromodulation_control"} == set(
        doc["prohibited_contexts"]
    )
    assert doc["version"]["code_commit"] == "75c5f39"
    assert doc["version"]["weights_sha256"] == "ab" * 32
    # versions of our own components come from their manifests (5.8 builder)
    comps = {c["id"]: c for c in doc["components"]}
    assert comps["nf-train"]["version"] == "0.1.0"
    assert "not intended for real-time or safety-critical control" in (
        comps["nf-train"]["purpose"].lower()
    )
    # test evidence in the 5.8 traceability format, incl. this step's requirements
    ev = doc["test_evidence"]
    assert ev["format"] == "nf.traceability/v0"
    ids = {r["id"] for r in ev["requirements"]}
    assert {"REQ-SISA-001", "REQ-SISA-002", "REQ-SOUP-001"} <= ids
    # known anomalies: the milestone reports' open issues
    assert all({"source", "text"} <= set(a) for a in doc["known_anomalies"])


def test_soup_sisa_training_block_states_not_certified_unlearning_and_no_subject_ids():
    raw = soup.build(soup.SoupInputs(model=MODEL, version=VERSION, repo_root=REPO))
    doc = json.loads(raw)
    s = doc["training"]["sisa"]
    assert (s["shards"], s["slices"], s["withdrawn_subjects"]) == (3, 2, 1)
    assert "NOT certified unlearning" in s["statement"]
    assert "arXiv:1912.03817" in s["statement"]
    assert doc["training"]["subject_count"] == 7
    assert b"nf.training-subject" not in raw


def test_soup_retrain_flags_are_known_anomalies():
    flags = (
        {
            "deletion_job_id": "dj-2",
            "created_at": "2026-09-26T11:00:00+00:00",
            "block_deployments": True,
        },
        {
            "deletion_job_id": "dj-1",
            "created_at": "2026-09-26T10:00:00+00:00",
            "block_deployments": False,
        },
    )
    doc = _doc(retrain_flags=flags)
    assert doc["retrain_required"] is True
    reg = [a for a in doc["known_anomalies"] if a["source"] == "registry"]
    assert [("dj-1" in a["text"], "dj-2" in a["text"]) for a in reg] == [
        (True, False),
        (False, True),
    ]
    assert "deployments blocked" in reg[1]["text"]
    assert _doc()["retrain_required"] is False


def test_soup_without_container_sbom_lists_locked_python_dependencies():
    doc = _doc()
    src = doc["dependencies"]["source"]
    assert src["kind"] == "python-lock" and "No container SBOM" in src["note"]
    by = {d["name"]: d for d in doc["dependencies"]["components"]}
    assert "numpy" in by and by["numpy"]["version"] not in ("", "unknown")
    assert by["numpy"]["purl"].startswith("pkg:pypi/numpy@")
    assert not any(n.startswith("nf-") for n in by)


def test_soup_regeneration_is_byte_identical():
    bom = json.loads(FIXTURE.read_text("utf-8"))
    a = soup.build(soup.SoupInputs(model=MODEL, version=VERSION, sbom=bom, repo_root=REPO))
    b = soup.build(soup.SoupInputs(model=MODEL, version=VERSION, sbom=bom, repo_root=REPO))
    assert a == b and a.endswith(b"\n")


@pytest.mark.parametrize(
    "bad",
    [
        {"bomFormat": "SPDX", "components": []},
        {"bomFormat": "CycloneDX", "components": [{"version": "1"}]},
        {"bomFormat": "CycloneDX", "components": ["x"]},
    ],
)
def test_soup_malformed_sbom_is_refused(bad):
    with pytest.raises(soup.SoupError):
        soup.build(soup.SoupInputs(model=MODEL, version=VERSION, sbom=bad, repo_root=REPO))
