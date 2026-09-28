"""2.1 acceptance: import-linter module boundaries hold (services/platform/.importlinter)."""

from __future__ import annotations

from pathlib import Path

from importlinter.cli import lint_imports

CONFIG = Path(__file__).resolve().parents[2] / ".importlinter"


def test_import_linter_contracts_kept():
    assert CONFIG.is_file()
    assert lint_imports(config_filename=str(CONFIG)) == 0


def test_layers_cover_every_top_level_module():
    """A new top-level package must be placed in the layer contract deliberately."""
    pkg = Path(__file__).resolve().parents[2] / "nf_platform"
    modules = {
        p.stem if p.is_file() else p.name for p in pkg.iterdir() if not p.name.startswith("_")
    }
    modules = {m for m in modules if (pkg / m).is_dir() or (pkg / f"{m}.py").is_file()}
    known = {"api", "ingest", "signals", "storage", "auth", "audit", "db", "governance", "registry"}
    known |= {"provenance", "pipelines"}  # m3-prov (M3 3.1, 3.2)
    known |= {"jobs"}  # m3-exec (M3 3.3): queue + runs, the layer between api and the middle
    known |= {"sweeps"}  # m3-sweeps (M3 3.6): multiverse sweeps, between api and jobs
    known |= {"webhooks", "limits", "site"}  # m4-api (M4 4.6, 4.8, 4.7): below jobs, above ingest
    known |= {"app", "config"}  # composition root + settings, covered by forbidden contracts
    known |= {"evidence", "placement"}  # m5-evidence (M5 5.8 kit, 5.7 PHI guard), governance level
    assert modules <= known, f"place these in .importlinter: {sorted(modules - known)}"
