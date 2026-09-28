"""Release guard: third-party figure data (greenspon2025_*, CC BY-NC-ND 4.0) never ships.

Builds the real sdist and wheel from a copy of the source tree (setuptools, no build isolation,
no network) and fails if any ``greenspon2025`` file is inside either artifact. See
THIRD_PARTY_NOTICE.md and legal/data-agreements/figure-data-memo.md. Also checks that the
estimator degrades cleanly when the reference tables are absent, which is how an installed
package runs.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest
from nf_channel_estimator.estimate import EstimateParams, estimate
from nf_channel_estimator.pfmap import load_map
from nf_channel_estimator.reference import REFERENCE_UNAVAILABLE, load_reference
from nf_channel_estimator.schema import output_schema
from test_ce_io_schema_cli import validate

PKG_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = "greenspon2025"


def artifact_members(path: Path) -> list[str]:
    """File names inside a wheel (.whl) or sdist (.tar.gz)."""
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as z:
            return z.namelist()
    with tarfile.open(path) as t:
        return t.getnames()


def forbidden_members(path: Path) -> list[str]:
    return [m for m in artifact_members(path) if FORBIDDEN in m.rsplit("/", 1)[-1]]


def test_scanner_detects_a_planted_file(tmp_path: Path) -> None:
    """Negative control: the scanner itself finds third-party data in an artifact."""
    whl = tmp_path / "x-0.0.0-py3-none-any.whl"
    with zipfile.ZipFile(whl, "w") as z:
        z.writestr("nf_channel_estimator/reference_data/greenspon2025_ed1_segments.json", "{}")
        z.writestr("nf_channel_estimator/__init__.py", "")
    assert forbidden_members(whl) == [
        "nf_channel_estimator/reference_data/greenspon2025_ed1_segments.json"
    ]


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    src = tmp_path_factory.mktemp("src") / "channel_estimator"
    shutil.copytree(
        PKG_ROOT, src, ignore=shutil.ignore_patterns("__pycache__", "*.egg-info", "build")
    )
    assert list(src.rglob(f"{FORBIDDEN}*")), "the copied source tree should contain the data"
    out = src / "dist"
    code = (
        "from setuptools import build_meta as b;"
        "print(b.build_sdist('dist'));print(b.build_wheel('dist'))"
    )
    r = subprocess.run(
        [sys.executable, "-c", code], cwd=src, capture_output=True, text=True, timeout=300
    )
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    sdist = next(out.glob("*.tar.gz"))
    wheel = next(out.glob("*.whl"))
    return {"sdist": sdist, "wheel": wheel}


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
def test_artifact_contains_no_third_party_data(built: dict[str, Path], kind: str) -> None:
    members = artifact_members(built[kind])
    assert any(m.endswith("nf_channel_estimator/estimate.py") for m in members), members
    assert forbidden_members(built[kind]) == [], f"{kind} ships third-party data"


def test_estimate_without_reference_tables(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Installed-package behaviour: counts and attrition work; nulls and relabelling are skipped."""
    empty = tmp_path / "no-reference"
    empty.mkdir()
    assert load_reference(str(empty)) is None
    pf_map = load_map(PKG_ROOT / "examples" / "greenspon2025_C1.pf-map.json")
    params = EstimateParams(relabel=True, null_draws=200, relabel_draws=50)
    full = estimate(pf_map, params).to_dict()
    bare = estimate(pf_map, params, reference_dir=str(empty)).to_dict()
    assert bare["channel_counts"] == full["channel_counts"]
    assert bare["attrition"] == full["attrition"]
    assert bare["diversity"] == full["diversity"]
    assert bare["clustering"] == {"status": "skipped", "reason": REFERENCE_UNAVAILABLE}
    assert bare["relabelling"] == {"status": "skipped", "reason": REFERENCE_UNAVAILABLE}
    assert bare["provenance"]["reference_data"] == {"status": "not_installed"}
    validate(json.loads(json.dumps(bare)), output_schema())
