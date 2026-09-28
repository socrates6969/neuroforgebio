"""BUILD-GUIDE 4.5: every code block of the docs quickstarts runs against the in-process platform
(the same runner CI uses: tools/doc-snippets/run.py; staging is CI-only)."""

from __future__ import annotations

import importlib.util
import sys

import pytest
from inprocess import REPO

pytestmark = pytest.mark.postgres


def _runner():
    spec = importlib.util.spec_from_file_location(
        "nf_doc_runner", REPO / "tools/doc-snippets/run.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["nf_doc_runner"] = mod  # dataclasses need the module registered
    spec.loader.exec_module(mod)
    return mod


def test_every_quickstart_block_runs(stack, tmp_path):
    run = _runner()
    pages = run.quickstarts()
    assert [p for p, _ in pages] == ["file-ingest", "pipeline-run", "streaming", "lineage-export"]
    assert sum(len(b) for _, b in pages) >= 12
    failures = run.run_quickstarts(lambda: run.configure_inprocess(stack), tmp_path)
    assert failures == []
