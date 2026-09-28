"""3.9 scaffold (research/multiverse): the study definition validates, the dataset manifest holds
only TODO placeholders (no invented accession IDs or licences), downloads are CI-only, the
renderer produces the packages/figures manifest format without publishing anything, and the
workflow is dispatch-only. No network access in any of these tests."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[4]
STUDY_DIR = REPO / "research" / "multiverse"


@pytest.fixture(scope="module")
def rs():
    spec = importlib.util.spec_from_file_location(
        "nf_multiverse_run_study", STUDY_DIR / "run_study.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["nf_multiverse_run_study"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import urllib.request

    def boom(*a, **k):
        raise AssertionError("network access in a local test")

    monkeypatch.setattr(urllib.request, "urlopen", boom)


def test_study_and_manifest_validate(rs):
    assert rs.validate() == []
    study = json.loads((STUDY_DIR / "study.json").read_text(encoding="utf-8"))
    assert study["status_label"] == "Planned / in preparation"
    assert study["publication"]["published"] is False


def test_manifest_has_only_placeholders(rs):
    """Nothing invented: every entry is a TODO with no accession, version, DOI or licence."""
    m = json.loads((STUDY_DIR / "datasets.json").read_text(encoding="utf-8"))
    assert m["datasets"]
    for d in m["datasets"]:
        assert d["status"] == "todo"
        assert d["accession"] is d["version"] is d["doi"] is d["url"] is None
        assert all(v is None for v in d["licence"].values())


def _selected(**kw):
    d = {
        "key": "x",
        "status": "selected",
        "repository": "openneuro",
        "accession": "ds123456",
        "version": "1.0.0",
        "citation": "c",
        "licence": {
            "spdx": "CC0-1.0",
            "url": "https://example.invalid/licence",
            "verified_by": "scientist",
            "verified_at": "2026-01-01",
        },
    }
    d.update(kw)
    return d


def test_selected_entries_need_a_wellformed_accession_and_a_recorded_licence(rs):
    assert rs.validate_dataset(_selected()) == []
    assert rs.validate_dataset(_selected(repository="dandi", accession="000123")) == []
    assert rs.validate_dataset(_selected(accession="ds12")), "malformed OpenNeuro ID"
    assert rs.validate_dataset(_selected(repository="figshare")), "unknown repository"
    assert rs.validate_dataset(_selected(version=None)), "unpinned version"
    for f in ("spdx", "url", "verified_by", "verified_at"):
        lic = {**_selected()["licence"], f: None}
        assert rs.validate_dataset(_selected(licence=lic)), f
    assert rs.validate_dataset({"key": "t", "status": "todo", "accession": "ds000001"})


def test_fetch_is_ci_only_and_refuses_placeholders(rs, tmp_path, monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("NF_STUDY_ALLOW_DOWNLOAD", raising=False)
    assert rs.main(["fetch", "--out", str(tmp_path)]) == 2
    monkeypatch.setenv("CI", "true")
    assert rs.main(["fetch", "--out", str(tmp_path)]) == 2  # still needs the explicit opt-in
    monkeypatch.setenv("NF_STUDY_ALLOW_DOWNLOAD", "true")
    with pytest.raises(rs.StudyError, match="TODO"):
        rs.fetch(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_ingest_is_not_built_and_sweep_is_ci_only(rs, tmp_path, monkeypatch):
    assert rs.main(["ingest"]) == 3
    monkeypatch.delenv("CI", raising=False)
    rec = tmp_path / "recordings.json"
    rec.write_text('{"recording_ids": []}')
    assert rs.main(["sweep", "--recordings", str(rec), "--out", str(tmp_path / "o")]) == 2


def _synthetic_report():
    """A SYNTHETIC report shaped like GET /v1/sweeps/{id}/report (made-up IDs; not a result)."""
    cells = []
    k = 0
    for lf in (0.1, 1.0):
        for notch in ([50.0], [60.0]):
            for rec in ("r1", "r2"):
                k += 1
                cells.append(
                    {
                        "run_id": f"run-{k}",
                        "prov_node_id": f"node-{k}",
                        "params": {"filter.l_freq": lf, "notch.freqs": notch},
                        "value": 0.5 + 0.1 * (lf > 0.5) + 0.01 * (rec == "r2"),
                    }
                )
    cells.append({**cells[0], "run_id": "run-failed", "value": None})
    return {
        "sweep_id": "sweep-1",
        "pipeline_version_id": "pv:sha256:" + "0" * 64,
        "metric": {"name": "decode.accuracy"},
        "factors": [
            {"name": "filter.l_freq", "values": [0.1, 1.0]},
            {"name": "notch.freqs", "values": [[50.0], [60.0]]},
        ],
        "cells": cells,
    }


def test_render_writes_the_figures_manifest_format_outside_packages(rs, tmp_path):
    man_path = rs.render(_synthetic_report(), tmp_path / "fig", synthetic=True)
    man = json.loads(man_path.read_text(encoding="utf-8"))
    (fig,) = man["figures"]
    assert fig["status"] == "preliminary"  # the only status packages/figures accepts
    assert "Planned / in preparation" in fig["notes"] and "SYNTHETIC" in fig["notes"]
    res = Path(fig["result"]["path"])
    res = res if res.is_absolute() else REPO / res
    assert fig["result"]["sha256"] == hashlib.sha256(res.read_bytes()).hexdigest()
    assert fig["script"]["path"] == "research/multiverse/run_study.py"
    plot = fig["plot"]
    assert plot["kind"] == "heatmap" and plot["key"] == "{row}|{col}" and plot["field"] == "mean"
    assert plot["rows"]["values"] == ["0.1", "1.0"] and plot["cols"]["values"] == ["50.0", "60.0"]
    table = json.loads(res.read_text(encoding="utf-8"))["heatmap"]
    for row in plot["rows"]["values"]:
        for col in plot["cols"]["values"]:
            cell = table[f"{row}|{col}"]
            assert cell["n"] == 2 and len(cell["run_ids"]) == 2  # every number -> its runs
            assert "run-failed" not in cell["run_ids"]
    assert table["1.0|50.0"]["mean"] == pytest.approx(0.605)
    with pytest.raises(rs.StudyError, match="packages"):
        rs.render(_synthetic_report(), REPO / "packages" / "figures" / "manifests")


def test_workflow_is_dispatch_only_pinned_and_locked():
    wf = (REPO / ".github" / "workflows" / "multiverse-study.yml").read_text(encoding="utf-8")
    on = wf.split("\non:\n", 1)[1].split("\n\n", 1)[0]
    assert "workflow_dispatch" in on
    assert all(t not in on for t in ("push", "pull_request", "schedule", "workflow_run"))
    for line in wf.splitlines():
        if "uses:" in line:
            ref = line.split("@", 1)[1].split()[0]
            assert len(ref) == 40 and all(c in "0123456789abcdef" for c in ref), line
    assert "uv sync --locked" in wf
    assert "confirm_download" in wf
