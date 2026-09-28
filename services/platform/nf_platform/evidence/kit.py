"""FDA Evidence Kit v0 (BUILD-GUIDE 5.8; BLUEPRINT §8.6; market/new-ideas.md #2).

**A scaffold, not a submission.** The kit is a zip of:

- ``traceability/``: requirement -> test -> result matrix. Requirements come from
  ``docs/requirements/*.yaml``; results from CI test metadata (JUnit XML, pytest ``--junitxml``);
  a requirement without a linked test is listed as flagged;
- ``sbom/``: the CycloneDX SBOM (from ``tools/sbom-props``) when one is supplied, else a note that
  the SBOM is attached to the CI build;
- ``release-notes/``: known anomalies = the open issues of ``docs/hive/M*-REPORT.md``;
- ``provenance/``: the PROV-JSON lineage export (3.7) of the chosen dataset/model node;
- ``soup/``: SOUP/OTS entries for our own components (``docs/requirements/soup.yaml``, versions
  from their manifests).

Deterministic: the same inputs give the same bytes (sorted entries, fixed timestamps and
permissions, canonical JSON, no wall-clock time, LF line endings).

Regulatory texts are referenced by name only. IEC 62304 and the full FDA cybersecurity guidance
were not opened in our research (BLUEPRINT §8.6), so they are marked UNVERIFIED and nothing is
quoted from them.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import tomllib
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

KIT_SCHEMA = "nf.fda-evidence-kit/v0"
LABEL = "SCAFFOLD, NOT A SUBMISSION"
ROOT = "fda-evidence-kit/"
ZIP_DATE = (1980, 1, 1, 0, 0, 0)
REQ_SCHEMA = "nf.requirements/v1"
SOUP_SCHEMA = "nf.soup/v1"
REFERENCES = (
    {
        "name": 'FDA "Content of Premarket Submissions for Device Software Functions" (Jun 2023), '
        "Enhanced Documentation Level",
        "status": "named in market/regulation.md §4 via the FDA BCI guidance update note; the "
        "guidance text itself was not opened: UNVERIFIED",
    },
    {
        "name": 'FDA "Cybersecurity in Medical Devices: Quality Management System Considerations '
        'and Content of Premarket Submissions" (Feb 2026)',
        "status": "full text, including SBOM expectations, not read (BLUEPRINT §8.6): UNVERIFIED",
    },
    {
        "name": "IEC 62304 (medical device software life cycle)",
        "status": "not opened (BLUEPRINT §8.6); IEC 62304-style structure is a plan to verify with "
        "a regulatory consultant: UNVERIFIED",
    },
)


class EvidenceError(ValueError):
    """Invalid requirement/SOUP inputs."""


@dataclass(frozen=True)
class KitInputs:
    """Everything the kit is built from. ``repo_root`` holds ``docs/requirements``, the reports
    and the component manifests (in a deployment: the release's source tree baked into the image by
    CI). ``junit`` and ``sbom`` are CI artefacts; without them the kit says so."""

    repo_root: Path
    junit: tuple[Path, ...] = ()
    sbom: Path | None = None
    release: str = "unreleased"


@dataclass
class Requirement:
    id: str
    title: str
    source: str
    tests: list[str]
    flag: str | None
    file: str


@dataclass
class Kit:
    files: dict[str, bytes] = field(default_factory=dict)
    flagged: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- canonical encodings
def _json(obj: Any) -> bytes:
    return (json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _text(s: str) -> bytes:
    return (s.replace("\r\n", "\n").rstrip("\n") + "\n").encode("utf-8")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------- requirements
def load_requirements(root: Path) -> list[Requirement]:
    out: list[Requirement] = []
    seen: set[str] = set()
    for f in sorted((root / "docs" / "requirements").glob("*.yaml")):
        doc = yaml.safe_load(f.read_text(encoding="utf-8"))
        if not isinstance(doc, dict) or doc.get("schema") != REQ_SCHEMA:
            continue  # other schemas (soup.yaml) live next to the requirements
        for i, r in enumerate(doc.get("requirements") or ()):
            where = f"{f.name}: requirements[{i}]"
            if not isinstance(r, dict) or not r.get("id") or not r.get("title"):
                raise EvidenceError(f"{where}: id and title are required")
            rid = str(r["id"])
            if rid in seen:
                raise EvidenceError(f"{where}: duplicate id {rid}")
            seen.add(rid)
            tests = [str(t) for t in r.get("tests") or ()]
            flag = r.get("flag")
            if not tests and not flag:
                raise EvidenceError(f"{where}: {rid} needs a linked test or a flag")
            out.append(
                Requirement(rid, str(r["title"]), str(r.get("source") or ""), tests, flag, f.name)
            )
    if not out:
        raise EvidenceError("no requirements found in docs/requirements")
    return out


def linked_test_exists(root: Path, test_id: str) -> bool:
    """Static check that a linked test exists (pytest function or node:test name)."""
    if test_id.startswith("node:"):
        path, _, name = test_id[5:].partition("::")
        p = root / path
        return bool(name) and p.is_file() and f"test('{name}'" in p.read_text(encoding="utf-8")
    path, _, name = test_id.partition("::")
    p = root / path
    if not name or not p.is_file():
        return False
    func = name.split("::")[-1].split("[")[0]
    return (
        re.search(rf"^\s*(?:async\s+)?def {re.escape(func)}\(", p.read_text("utf-8"), re.M)
        is not None
    )


# ---------------------------------------------------------------- CI results (JUnit XML)
def _case_ids(case: ET.Element) -> tuple[str, str]:
    """(pytest-style node id, bare name) of a JUnit testcase. pytest writes classname
    ``services.platform.tests.core.test_x`` (or ``...test_x.TestClass``) and name ``test_y[p]``."""
    cls = case.get("classname", "")
    name = case.get("name", "")
    base = name.split("[")[0]
    parts = cls.split(".")
    # module path = the dotted parts up to the first one starting with "test_"
    mod: list[str] = []
    rest: list[str] = []
    for i, p in enumerate(parts):
        mod.append(p)
        if p.startswith("test_"):
            rest = parts[i + 1 :]
            break
    node = "/".join(mod) + ".py::" + "::".join([*rest, base])
    return node, name


def load_results(paths: tuple[Path, ...]) -> dict[str, list[str]]:
    """test id -> outcomes (passed/failed/skipped) over all its parametrizations."""
    res: dict[str, list[str]] = {}
    for p in sorted(paths, key=str):
        tree = ET.parse(p)  # noqa: S314 - CI artefact of our own build, not user input
        for case in tree.iter("testcase"):
            if case.find("failure") is not None or case.find("error") is not None:
                outcome = "failed"
            elif case.find("skipped") is not None:
                outcome = "skipped"
            else:
                outcome = "passed"
            node, name = _case_ids(case)
            res.setdefault(node, []).append(outcome)
            res.setdefault(f"name:{name}", []).append(outcome)
    return res


def _result(test_id: str, results: dict[str, list[str]] | None) -> str:
    if results is None:
        return "no CI results supplied (attach the CI JUnit XML)"
    if test_id.startswith("node:"):
        outs = results.get("name:" + test_id.partition("::")[2])
    else:
        outs = results.get(test_id.split("[")[0])
    if not outs:
        return "not run"
    if "failed" in outs:
        return "failed"
    if all(o == "skipped" for o in outs):
        return "skipped"
    return "passed"


def traceability(inputs: KitInputs) -> tuple[dict[str, Any], bytes, list[str]]:
    reqs = load_requirements(inputs.repo_root)
    results = load_results(inputs.junit) if inputs.junit else None
    rows = []
    flagged = []
    for r in reqs:
        missing = [t for t in r.tests if not linked_test_exists(inputs.repo_root, t)]
        linked = [t for t in r.tests if t not in missing]
        flag = r.flag
        if not linked:
            flag = flag or "no linked test"
        if missing:
            flag = "; ".join(filter(None, [flag, "linked test not found: " + ", ".join(missing)]))
        if flag:
            flagged.append(r.id)
        rows.append(
            {
                "id": r.id,
                "title": r.title,
                "source": r.source,
                "file": r.file,
                "tests": [{"test": t, "result": _result(t, results)} for t in linked],
                "flag": flag,
            }
        )
    matrix = {
        "label": LABEL,
        "schema": "nf.traceability/v0",
        "results_source": "JUnit XML from CI" if results is not None else None,
        "requirements": rows,
        "flagged": flagged,
    }
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["requirement", "title", "source", "test", "result", "flag"])
    for row in rows:
        for t in row["tests"] or [{"test": "", "result": ""}]:
            w.writerow(
                [row["id"], row["title"], row["source"], t["test"], t["result"], row["flag"] or ""]
            )
    return matrix, buf.getvalue().encode("utf-8"), flagged


# ---------------------------------------------------------------- release notes
_ITEM = re.compile(r"^(\d+)\.\s+(.*)")


def known_anomalies(root: Path) -> list[dict[str, Any]]:
    """Open issues of every ``docs/hive/M*-REPORT.md`` (the numbered items of each section whose
    heading starts with "Open issues"), in file order."""
    out: list[dict[str, Any]] = []
    for f in sorted((root / "docs" / "hive").glob("M*-REPORT.md")):
        section = None
        item: dict[str, Any] | None = None
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                section = line[3:].strip() if line[3:].lower().startswith("open issues") else None
                item = None
                continue
            if section is None:
                continue
            m = _ITEM.match(line)
            if m:
                item = {"report": f.name, "section": section, "item": int(m[1]), "text": m[2]}
                out.append(item)
            elif item is not None and line.strip():
                item["text"] += " " + line.strip()
    return out


def release_notes(inputs: KitInputs, anomalies: list[dict[str, Any]]) -> bytes:
    lines = [
        f"# Release notes: {inputs.release} ({LABEL})",
        "",
        "Known anomalies: the open issues recorded in the milestone reports "
        "(docs/hive/M*-REPORT.md), verbatim.",
        "",
    ]
    for a in anomalies:
        lines.append(f"- [{a['report']} #{a['item']}] {a['text']}")
    if not anomalies:
        lines.append("- none recorded")
    return _text("\n".join(lines))


# ---------------------------------------------------------------- SOUP
def _version(root: Path, manifest: str) -> str:
    p = root / manifest
    try:
        doc = tomllib.loads(p.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return "unknown"
    v = (doc.get("package") or {}).get("version") or (doc.get("project") or {}).get("version")
    return str(v) if v else "unknown"


def soup_entries(root: Path) -> list[dict[str, Any]]:
    doc = yaml.safe_load((root / "docs" / "requirements" / "soup.yaml").read_text("utf-8"))
    if not isinstance(doc, dict) or doc.get("schema") != SOUP_SCHEMA:
        raise EvidenceError(f"soup.yaml: schema must be {SOUP_SCHEMA}")
    out = []
    for c in doc.get("components") or ():
        out.append(
            {
                "id": str(c["id"]),
                "name": str(c["name"]),
                "version": _version(root, str(c["manifest"])),
                "manifest": str(c["manifest"]),
                "purpose": " ".join(str(c.get("purpose") or "").split()),
                "support_level": str(c.get("support_level") or "unknown"),
                "requirements": [str(x) for x in c.get("requirements") or ()],
                "known_anomalies": str(c.get("known_anomalies") or ""),
            }
        )
    return out


# ---------------------------------------------------------------- the kit
def _readme(
    inputs: KitInputs, tenant_id: str, node_id: str, flagged: list[str], sbom: bool
) -> bytes:
    refs = "\n".join(f"- {r['name']}: {r['status']}" for r in REFERENCES)
    sbom_line = (
        "CycloneDX SBOM (tools/sbom-props)" if sbom else "SBOM attached in CI (not generated here)"
    )
    return _text(
        f"""FDA EVIDENCE KIT v0 -- {LABEL}

This package is a documentation scaffold generated by the platform. It is not a regulatory
submission, it has not been reviewed by a regulatory consultant (owner action), and it makes no
claim that any product meets any regulation.

Release: {inputs.release}
Tenant: {tenant_id}
Provenance root node: {node_id}

Contents
- traceability/matrix.json, matrix.csv: requirement -> test -> result (docs/requirements/*.yaml;
  results from CI JUnit XML when supplied). Flagged requirements: {", ".join(flagged) or "none"}.
- sbom/: {sbom_line}.
- release-notes/known-anomalies.md, .json: open issues from the milestone reports.
- provenance/prov.json: PROV-JSON lineage (ancestry) of the chosen dataset/model node.
- soup/soup.json: SOUP/OTS entries for our components (third-party components: see the SBOM).
- manifest.json: SHA-256 of every other file in the kit.

Referenced by name only (nothing quoted):
{refs}
"""
    )


def build(
    inputs: KitInputs, *, tenant_id: str, node_id: str, prov_json: dict[str, Any]
) -> tuple[bytes, Kit]:
    """Build the kit. Returns (zip bytes, contents). Same inputs -> same bytes."""
    kit = Kit()
    matrix, matrix_csv, flagged = traceability(inputs)
    kit.flagged = flagged
    kit.files["traceability/matrix.json"] = _json(matrix)
    kit.files["traceability/matrix.csv"] = matrix_csv
    if inputs.sbom is not None and inputs.sbom.is_file():
        bom = json.loads(inputs.sbom.read_text(encoding="utf-8"))
        kit.files["sbom/sbom.cdx.json"] = _json(bom)
    else:
        kit.files["sbom/SBOM-ATTACHED-IN-CI.txt"] = _text(
            "SBOM attached in CI. The CycloneDX SBOM (with nfb:supportLevel and nfb:endOfSupport "
            "properties, tools/sbom-props) is produced by the CI build and attached to it; it was "
            f"not supplied to this kit generation. {LABEL}."
        )
    anomalies = known_anomalies(inputs.repo_root)
    kit.files["release-notes/known-anomalies.json"] = _json({"label": LABEL, "items": anomalies})
    kit.files["release-notes/known-anomalies.md"] = release_notes(inputs, anomalies)
    kit.files["provenance/prov.json"] = _json(prov_json)
    kit.files["soup/soup.json"] = _json(
        {"label": LABEL, "schema": "nf.soup/v1", "components": soup_entries(inputs.repo_root)}
    )
    has_sbom = "sbom/sbom.cdx.json" in kit.files
    kit.files["README.txt"] = _readme(inputs, tenant_id, node_id, flagged, has_sbom)
    manifest = {
        "schema": KIT_SCHEMA,
        "label": LABEL,
        "release": inputs.release,
        "tenant_id": tenant_id,
        "provenance_root": node_id,
        "references": list(REFERENCES),
        "files": {name: _sha(data) for name, data in sorted(kit.files.items())},
    }
    kit.files["manifest.json"] = _json(manifest)
    return zip_bytes(kit.files), kit


def zip_bytes(files: dict[str, bytes]) -> bytes:
    """Deterministic zip: sorted names, fixed timestamps, permissions and creator system."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(ROOT + name, date_time=ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            z.writestr(info, files[name], compresslevel=9)
    return buf.getvalue()


def default_root() -> Path:
    return Path(__file__).resolve().parents[4]


def inputs_from_env(environ: dict[str, str] | None = None) -> KitInputs:
    """``NF_EVIDENCE_ROOT`` (source tree; default: this checkout), ``NF_EVIDENCE_JUNIT`` (JUnit XML
    paths, ``os.pathsep``-separated), ``NF_EVIDENCE_SBOM`` (CycloneDX JSON), ``NF_RELEASE``."""
    import os

    env = os.environ if environ is None else environ
    junit = tuple(Path(p) for p in env.get("NF_EVIDENCE_JUNIT", "").split(os.pathsep) if p)
    sbom = env.get("NF_EVIDENCE_SBOM")
    return KitInputs(
        repo_root=Path(env.get("NF_EVIDENCE_ROOT") or default_root()),
        junit=junit,
        sbom=Path(sbom) if sbom else None,
        release=env.get("NF_RELEASE") or "unreleased",
    )
