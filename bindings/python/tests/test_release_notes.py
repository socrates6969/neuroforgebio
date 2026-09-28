"""SEC-134 release-notes template check: end-of-support date and update channel stay mandatory,
and the package metadata carries no publish configuration."""

from __future__ import annotations

import tomllib

from inprocess import REPO

T = REPO / "bindings/python/RELEASE-NOTES-TEMPLATE.md"


def test_template_states_end_of_support_and_update_channel():
    text = T.read_text("utf-8")
    for field in ("**End of support:**", "**Update channel:**", "**Release date:**", "SEC-134"):
        assert field in text, field
    assert "cosign verify-blob" in text and "gh attestation verify" in text


def test_wheels_workflow_has_no_publish_step():
    wf = (REPO / ".github/workflows/sdk-wheels.yml").read_text("utf-8")
    assert "workflow_dispatch" in wf
    for banned in ("pypa/gh-action-pypi-publish", "twine upload", "maturin publish", "uv publish"):
        assert banned not in wf
    meta = tomllib.loads((REPO / "bindings/python/pyproject.toml").read_text("utf-8"))
    assert meta["project"]["name"] == "neuroforge"
    assert meta["project"]["requires-python"] == ">=3.12"
