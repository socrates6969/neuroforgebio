"""SOUP/OTS export per model version (BUILD-GUIDE 6.5; BLUEPRINT §3.7, §8.6; SEC-092, SEC-083).

A deterministic JSON document for a customer whose product is a device and who embeds one of our
model versions as SOUP/OTS software:

- ``model`` / ``version``: identity, code commit, pipeline versions, weights digest, lineage;
- ``intended_use``, ``use_restrictions`` and the fixed statement
  "Not intended for real-time or safety-critical control." (SEC-092);
- ``dependencies``: **every** component of the model's container SBOM (CycloneDX JSON, nested
  components flattened) when one is attached, with ``nfb:supportLevel`` / ``nfb:endOfSupport``
  (SEC-083 vocabulary; ``unknown`` when the SBOM lacks them); otherwise our own Python
  dependencies with the versions pinned in ``uv.lock``, labelled as such;
- ``known_anomalies``: the model's open ``retrain_required`` flags plus the open issues of the
  milestone reports (the same source as the 5.8 evidence kit);
- ``test_evidence``: requirement -> test -> result rows in the 5.8 traceability format
  (``nf.traceability/v0``) for the requirements of the components involved;
- ``training``: algorithm and, for a SISA model, the shard/slice counts (never hashed subject IDs)
  with the statement that SISA is not certified unlearning.

Byte-identical regeneration: canonical JSON (sorted keys, 2-space indent, LF), sorted lists, no
wall-clock time: every timestamp comes from the database rows.

**A scaffold, not a submission**, like the evidence kit; regulatory texts are referenced by name
only (``nf_platform.evidence.kit.REFERENCES``).
"""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nf_platform.evidence import kit

SCHEMA = "nf.model-soup/v1"
LABEL = kit.LABEL
CONTROL_STATEMENT = "Not intended for real-time or safety-critical control."
SISA_STATEMENT = (
    "Trained with SISA sharding (Bourtoule et al., arXiv:1912.03817) so that a withdrawal "
    "retrains only the affected shard. This is NOT certified unlearning."
)
SUPPORT_LEVEL = "nfb:supportLevel"
END_OF_SUPPORT = "nfb:endOfSupport"
# Our components whose Python dependencies a model version runs with when no container SBOM is
# attached (the training/inference code path of a registry model).
DEFAULT_MANIFESTS = (
    "services/platform/pyproject.toml",
    "services/workers/steps/nf_train/pyproject.toml",
)
# soup.yaml components involved in producing / serving a registry model
MODEL_COMPONENTS = ("nf-platform", "nf-runner", "nf-steps", "nf-train")
MODEL_REQUIREMENT_PREFIXES = ("REQ-MODEL-", "REQ-SISA-", "REQ-SOUP-")


class SoupError(ValueError):
    pass


@dataclass(frozen=True)
class SoupInputs:
    """Everything the document is built from (all from the database and the release tree)."""

    model: Mapping[str, Any]
    version: Mapping[str, Any]
    retrain_flags: tuple[Mapping[str, Any], ...] = ()
    sbom: Mapping[str, Any] | None = None
    sbom_sha256: str | None = None
    repo_root: Path = field(default_factory=kit.default_root)
    junit: tuple[Path, ...] = ()
    release: str = "unreleased"


def dumps(doc: Any) -> bytes:
    return (json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


# ---------------------------------------------------------------- dependencies
def _props(c: Mapping[str, Any]) -> dict[str, str]:
    return {
        str(p.get("name")): str(p.get("value"))
        for p in c.get("properties") or ()
        if isinstance(p, Mapping) and p.get("name")
    }


def _licenses(c: Mapping[str, Any]) -> list[str]:
    out = []
    for lic in c.get("licenses") or ():
        if not isinstance(lic, Mapping):
            continue
        if lic.get("expression"):
            out.append(str(lic["expression"]))
        inner = lic.get("license")
        if isinstance(inner, Mapping):
            out.append(str(inner.get("id") or inner.get("name") or ""))
    return sorted(x for x in out if x)


def _walk(components: Iterable[Any], parent: str | None) -> Iterable[tuple[Mapping, str | None]]:
    for c in components or ():
        if not isinstance(c, Mapping):
            raise SoupError("SBOM component is not an object")
        yield c, parent
        ref = str(c.get("bom-ref") or c.get("purl") or c.get("name") or "")
        yield from _walk(c.get("components") or (), ref)


def sbom_dependencies(bom: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Every component of a CycloneDX JSON SBOM (nested ones included), sorted."""
    if bom.get("bomFormat") != "CycloneDX":
        raise SoupError("the attached SBOM is not CycloneDX JSON")
    out = []
    for c, parent in _walk(bom.get("components") or (), None):
        if not c.get("name"):
            raise SoupError("SBOM component without a name")
        props = _props(c)
        supplier = c.get("supplier")
        out.append(
            {
                "bom_ref": str(c.get("bom-ref") or c.get("purl") or ""),
                "type": str(c.get("type") or "library"),
                "group": str(c.get("group") or ""),
                "name": str(c["name"]),
                "version": str(c.get("version") or "unknown"),
                "purl": str(c.get("purl") or ""),
                "licenses": _licenses(c),
                "supplier": str(supplier.get("name") or "")
                if isinstance(supplier, Mapping)
                else "",
                "support_level": props.get(SUPPORT_LEVEL, "unknown"),
                "end_of_support": props.get(END_OF_SUPPORT, "unknown"),
                "parent": parent or "",
                "source": "container-sbom",
            }
        )
    return sorted(out, key=lambda d: (d["name"], d["version"], d["purl"], d["bom_ref"]))


_REQ_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)(\[[^\]]*\])?")


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def lock_versions(root: Path) -> dict[str, str]:
    try:
        lock = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    return {_norm(p["name"]): str(p.get("version") or "") for p in lock.get("package") or ()}


def python_dependencies(root: Path, manifests: Iterable[str] = DEFAULT_MANIFESTS) -> list[dict]:
    """Our declared runtime Python dependencies with the versions pinned in ``uv.lock``."""
    locked = lock_versions(root)
    seen: dict[str, dict[str, Any]] = {}
    for mf in manifests:
        try:
            doc = tomllib.loads((root / mf).read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            continue
        for spec in (doc.get("project") or {}).get("dependencies") or ():
            m = _REQ_NAME.match(str(spec))
            if not m:
                continue
            name = _norm(m[1])
            if name.startswith("nf-"):
                continue  # our own components: listed under "components"
            d = seen.setdefault(
                name,
                {
                    "bom_ref": "",
                    "type": "library",
                    "group": "",
                    "name": name,
                    "version": locked.get(name) or "unknown",
                    "purl": f"pkg:pypi/{name}@{locked[name]}" if locked.get(name) else "",
                    "licenses": [],
                    "supplier": "",
                    "support_level": "unknown",
                    "end_of_support": "unknown",
                    "parent": "",
                    "source": "uv.lock",
                    "declared_in": [],
                    "specifiers": [],
                },
            )
            d["declared_in"] = sorted({*d["declared_in"], mf})
            d["specifiers"] = sorted({*d["specifiers"], str(spec).strip()})
    return sorted(seen.values(), key=lambda d: d["name"])


# ---------------------------------------------------------------- evidence
def _components(root: Path) -> list[dict[str, Any]]:
    try:
        entries = kit.soup_entries(root)
    except (OSError, kit.EvidenceError):
        return []
    return [e for e in entries if e["id"] in MODEL_COMPONENTS]


def evidence_rows(inputs: SoupInputs, components: list[dict[str, Any]]) -> dict[str, Any]:
    matrix, _csv, _flagged = kit.traceability(
        kit.KitInputs(inputs.repo_root, inputs.junit, None, inputs.release)
    )
    wanted = {r for c in components for r in c["requirements"]}
    rows = [
        r
        for r in matrix["requirements"]
        if r["id"] in wanted or r["id"].startswith(MODEL_REQUIREMENT_PREFIXES)
    ]
    return {
        "format": matrix["schema"],
        "results_source": matrix["results_source"],
        "requirements": rows,
        "flagged": sorted(r["id"] for r in rows if r["flag"]),
        "full_matrix": "POST /v1/exports/fda-evidence (traceability/matrix.json)",
    }


def _training(version: Mapping[str, Any]) -> dict[str, Any]:
    t = dict(version.get("training") or {})
    out: dict[str, Any] = {
        "algorithm": str(t.get("algorithm") or "unknown"),
        "subject_count": t.get("subject_count"),
        "statement": "Training-set manifest of hashed subject IDs is held in the registry; "
        "no subject identifiers are included in this export.",
    }
    if t.get("weights_source") is not None:  # AppSec M3
        out["weights_source"] = str(t["weights_source"])
        if t["weights_source"] == "upload":
            out["lineage_statement"] = (
                "Uploaded weights: the training lineage is the uploader's declaration and is not "
                "verified by the platform; any subject withdrawal in the tenant after registration "
                "flags this version."
            )
    if t.get("sisa"):
        s = t["sisa"]
        out["sisa"] = {
            "shards": s.get("shards"),
            "slices": s.get("slices"),
            "withdrawn_subjects": s.get("withdrawn_subjects", 0),
            "statement": SISA_STATEMENT,
        }
    return out


def build(inputs: SoupInputs) -> bytes:
    """The SOUP document (bytes). Same inputs -> same bytes."""
    v, mdl = inputs.version, inputs.model
    if inputs.sbom is not None:
        deps = sbom_dependencies(inputs.sbom)
        meta = inputs.sbom.get("metadata") or {}
        sub = meta.get("component") if isinstance(meta, Mapping) else None
        dep_source = {
            "kind": "container-sbom",
            "format": f"CycloneDX {inputs.sbom.get('specVersion', '?')}",
            "sha256": inputs.sbom_sha256 or hashlib.sha256(dumps(dict(inputs.sbom))).hexdigest(),
            "subject": {
                "name": str(sub.get("name") or ""),
                "version": str(sub.get("version") or ""),
                "bom_ref": str(sub.get("bom-ref") or ""),
            }
            if isinstance(sub, Mapping)
            else None,
            "component_count": len(deps),
        }
    else:
        deps = python_dependencies(inputs.repo_root)
        dep_source = {
            "kind": "python-lock",
            "note": "No container SBOM is attached to this model version; listed are our declared "
            "Python runtime dependencies with the versions pinned in uv.lock (transitive "
            "dependencies: see the CI SBOM).",
            "manifests": list(DEFAULT_MANIFESTS),
            "component_count": len(deps),
        }
    components = _components(inputs.repo_root)
    anomalies = [
        {
            "source": "registry",
            "text": f"retrain_required: {f.get('reason') or 'a training subject withdrew consent'} "
            f"(deletion job {f.get('deletion_job_id')}, flagged {f.get('created_at')}, "
            f"deployments {'blocked' if f.get('block_deployments') else 'not blocked'}).",
        }
        for f in sorted(inputs.retrain_flags, key=lambda f: str(f.get("deletion_job_id")))
    ] + [
        {"source": f"{a['report']} #{a['item']}", "text": a["text"]}
        for a in kit.known_anomalies(inputs.repo_root)
    ]
    doc = {
        "schema": SCHEMA,
        "label": LABEL,
        "release": inputs.release,
        "statement": CONTROL_STATEMENT,
        "model": {
            "id": str(mdl.get("id")),
            "name": str(mdl.get("name") or ""),
            "card": mdl.get("card") or {},
        },
        "version": {
            k: v.get(k)
            for k in (
                "id",
                "version",
                "created_at",
                "code_commit",
                "pipeline_version_ids",
                "weights_sha256",
                "parent_version_id",
                "prov_node_id",
            )
        },
        "intended_use": str(v.get("intended_use") or ""),
        "use_restrictions": sorted(str(x) for x in v.get("use_restrictions") or ()),
        "prohibited_contexts": [
            "actuator_control",
            "closed_loop_stimulation",
            "neuromodulation_control",
        ],
        "retrain_required": bool(inputs.retrain_flags),
        "training": _training(v),
        "dependencies": {"source": dep_source, "components": deps},
        "components": components,
        "known_anomalies": anomalies,
        "test_evidence": evidence_rows(inputs, components),
        "references": list(kit.REFERENCES),
    }
    return dumps(doc)
