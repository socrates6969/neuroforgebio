"""Workers import nf_platform but never its API layer; the step library is standalone
(services/workers/.importlinter)."""

from __future__ import annotations

from pathlib import Path

from importlinter.cli import lint_imports

CONFIG = Path(__file__).resolve().parents[2] / ".importlinter"


def test_worker_import_contracts_kept():
    assert CONFIG.is_file()
    assert lint_imports(config_filename=str(CONFIG)) == 0
