"""MinIO is a CI-only test double (M2-REVIEW MinIO decision; docs/security/object-storage.md).

Production object storage is the cloud provider's S3 (D4) with Object Lock for the WORM audit
bucket. `bitnamilegacy/minio` may appear only in the CI compose file, pinned by digest, and is
listed in the SBOM as nfb:supportLevel=unmaintained. This test fails if any other compose,
container or infrastructure file references MinIO.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CI_COMPOSE = ROOT / "services" / "platform" / "docker-compose.ci.yml"
# Directories that never hold deployable configuration (dependencies, caches, VCS).
SKIP_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "target",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".terraform",
    "dist",
    "build",
}
# Infrastructure/deployment trees: every file in them is deployable configuration.
DEPLOY_DIRS = {"infra", "deploy", "deployments", "k8s", "kubernetes", "helm", "charts", "terraform"}
DEPLOY_FILE = re.compile(
    r"(^|[-_.])compose([-_.].*)?\.ya?ml$|^Dockerfile|\.dockerfile$|\.tf$|\.tfvars(\.\w+)?$|\.hcl$",
    re.IGNORECASE,
)


def _walk(root: Path) -> list[Path]:
    out: list[Path] = []
    for p in root.iterdir():
        if p.is_dir():
            if p.name not in SKIP_DIRS:
                out.extend(_walk(p))
        else:
            out.append(p)
    return out


def _deploy_files() -> list[Path]:
    files = []
    for p in _walk(ROOT):
        rel = p.relative_to(ROOT)
        in_deploy_dir = any(part in DEPLOY_DIRS for part in rel.parts[:-1])
        if in_deploy_dir or DEPLOY_FILE.search(p.name):
            files.append(p)
    return files


def test_scan_sees_the_known_deploy_files() -> None:
    names = {p.relative_to(ROOT).as_posix() for p in _deploy_files()}
    assert "services/platform/docker-compose.ci.yml" in names
    assert "infra/modules/bucket/main.tf" in names  # the production S3 bucket module


def test_no_minio_outside_the_ci_compose_file() -> None:
    offenders = [
        p.relative_to(ROOT).as_posix()
        for p in _deploy_files()
        if p != CI_COMPOSE and "minio" in p.read_text(encoding="utf-8", errors="replace").lower()
    ]
    # see docs/security/object-storage.md
    assert offenders == [], f"MinIO referenced outside CI: {offenders}"


def test_ci_compose_marks_minio_ci_only_and_pins_it_by_digest() -> None:
    text = CI_COMPOSE.read_text(encoding="utf-8")
    assert "name: nf-platform-ci" in text
    images = re.findall(r"^\s*image:\s*(\S+)", text, re.MULTILINE)
    minio = [i for i in images if "minio" in i.lower()]
    assert minio and all(re.fullmatch(r"bitnamilegacy/minio@sha256:[0-9a-f]{64}", i) for i in minio)
    assert all("@sha256:" in i for i in images)  # every CI image is digest-pinned


def test_sbom_lists_minio_as_unmaintained_ci_only() -> None:
    levels = json.loads((ROOT / "security" / "support-levels.json").read_text(encoding="utf-8"))
    assert levels["components"]["bitnamilegacy/minio"]["supportLevel"] == "unmaintained"
    sbom = json.loads((ROOT / "security" / "sbom-ci-images.json").read_text(encoding="utf-8"))
    comp = next(c for c in sbom["components"] if c["name"] == "bitnamilegacy/minio")
    props = {p["name"]: p["value"] for p in comp["properties"]}
    assert props["nfb:scope"] == "ci-only"
    digest = re.search(r"bitnamilegacy/minio@(sha256:[0-9a-f]{64})", CI_COMPOSE.read_text("utf-8"))
    assert digest and digest.group(1).replace(":", "%3A") in comp["purl"]
