"""Runner for the planned multiverse study (BUILD-GUIDE 3.9): "How preprocessing choices change
decoding results". Status: Planned / in preparation. Nothing here publishes anything.

Stages (``python research/multiverse/run_study.py <stage> ...``):

- ``validate``  (local OK)  study.json + datasets.json + the base PipelineVersion. Placeholders
  (``status: "todo"``, accession ``null``) are allowed; a filled entry must carry a well-formed
  accession AND a recorded licence (SPDX id, URL, who verified it and when). IDs are never invented.
- ``fetch``     (CI ONLY)   downloads the manifest's datasets from OpenNeuro (public S3 bucket) or
  DANDI (public API) and writes ``files.json`` (path, size, sha256 per file) as the input manifest.
  Refuses unless ``CI=true`` and ``NF_STUDY_ALLOW_DOWNLOAD=true``, and refuses TODO entries.
- ``ingest``    (CI ONLY)   NOT BUILT YET: mapping the chosen dataset's file format onto the M2
  upload/convert API is decided when the dataset is chosen. Exits 3.
- ``sweep``     (CI ONLY)   POSTs the study grid to ``/v1/sweeps`` of a running platform
  (``NF_API_URL``, ``NF_API_TOKEN``) for the ingested recordings, polls until complete and saves the
  report JSON (every number carries run IDs and provenance node IDs).
- ``render``    (local OK)  turns a sweep report into the website figure pipeline format
  (``packages/figures`` manifest: pinned result file + heatmap plot spec). Output goes to an
  artifact directory, never into ``packages/figures/manifests`` (publishing is owner-gated).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
STUDY = HERE / "study.json"
DATASETS = HERE / "datasets.json"
STATUS_LABEL = "Planned / in preparation"
ACCESSION_RE = {
    "openneuro": re.compile(r"^ds\d{6}$"),
    "dandi": re.compile(r"^\d{6}$"),
}
SPDX_RE = re.compile(r"^[A-Za-z0-9.+-]{2,64}$")
OPENNEURO_S3 = "https://s3.amazonaws.com/openneuro.org"
DANDI_API = "https://api.dandiarchive.org/api"
MAX_DOWNLOAD_BYTES = 20 * 1024**3


class StudyError(Exception):
    pass


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- validate
def validate_dataset(d: dict[str, Any]) -> list[str]:
    key = d.get("key", "?")
    errs = []
    status = d.get("status")
    if status not in ("todo", "selected"):
        errs.append(f"{key}: status must be 'todo' or 'selected'")
    if status == "todo":
        if d.get("accession") is not None:
            errs.append(f"{key}: a TODO entry must not carry an accession")
        return errs
    repo = d.get("repository")
    if repo not in ACCESSION_RE:
        errs.append(f"{key}: repository must be one of {sorted(ACCESSION_RE)}")
    elif not ACCESSION_RE[repo].match(str(d.get("accession") or "")):
        errs.append(f"{key}: accession {d.get('accession')!r} is not a well-formed {repo} ID")
    if not d.get("version"):
        errs.append(f"{key}: version is required (downloads are pinned to a version)")
    lic = d.get("licence") or {}
    if not SPDX_RE.match(str(lic.get("spdx") or "")):
        errs.append(f"{key}: licence.spdx is required")
    for f in ("url", "verified_by", "verified_at"):
        if not lic.get(f):
            errs.append(f"{key}: licence.{f} is required (record who checked the licence, when)")
    if not d.get("citation"):
        errs.append(f"{key}: citation is required")
    return errs


def validate(study_path: Path = STUDY, datasets_path: Path = DATASETS) -> list[str]:
    errs: list[str] = []
    study = load(study_path)
    if study.get("schema") != "nf.multiverse-study/v1":
        errs.append("study: schema must be nf.multiverse-study/v1")
    if study.get("status_label") != STATUS_LABEL and study.get("status") == "planned":
        errs.append(f"study: status_label must be {STATUS_LABEL!r} while planned")
    if (study.get("publication") or {}).get("published") is not False:
        errs.append("study: publication.published must stay false (owner-gated)")
    grid = study.get("grid") or {}
    if not grid:
        errs.append("study: empty grid")
    base = load(REPO / study["base_pipeline"])
    steps = {s["name"]: s for s in base.get("steps", [])}
    for factor in grid:
        step, _, param = factor.rpartition(".")
        if step not in steps or param not in steps[step].get("params", {}):
            errs.append(f"study: grid factor {factor!r} is not a parameter of the base pipeline")
    if study.get("metric", {}).get("step") not in steps:
        errs.append("study: metric step is not in the base pipeline")
    try:  # full PipelineVersion validation when the platform package is importable
        from nf_platform.pipelines.spec import PipelineError, parse_spec  # noqa: PLC0415

        try:
            parse_spec(base)
        except PipelineError as e:
            errs.append(f"base pipeline: {e}")
    except ImportError:
        pass
    manifest = load(datasets_path)
    if manifest.get("schema") != "nf.multiverse-datasets/v1":
        errs.append("datasets: schema must be nf.multiverse-datasets/v1")
    for d in manifest.get("datasets", []):
        errs.extend(validate_dataset(d))
    return errs


# ---------------------------------------------------------------- fetch (CI only)
def _download_allowed() -> None:
    if os.environ.get("CI") != "true" or os.environ.get("NF_STUDY_ALLOW_DOWNLOAD") != "true":
        raise StudyError(
            "fetch is CI-only: set CI=true and NF_STUDY_ALLOW_DOWNLOAD=true in the dispatch-only "
            "workflow (.github/workflows/multiverse-study.yml); never download locally"
        )


def _get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as r:  # noqa: S310 - https only, fixed hosts
        return r.read()


def _openneuro_files(accession: str) -> list[tuple[str, str]]:
    """(relative path, https URL) for every object of ``accession`` (S3 ListObjectsV2 paging)."""
    out, token = [], None
    ns = "{http://s3.amazonaws.com/doc/2006-03-01/}"
    while True:
        q = {"list-type": "2", "prefix": f"{accession}/"}
        if token:
            q["continuation-token"] = token
        root = ET.fromstring(_get(f"{OPENNEURO_S3}?{urllib.parse.urlencode(q)}"))  # noqa: S314
        for c in root.iter(f"{ns}Contents"):
            key = c.findtext(f"{ns}Key") or ""
            if key and not key.endswith("/"):
                out.append((key[len(accession) + 1 :], f"{OPENNEURO_S3}/{urllib.parse.quote(key)}"))
        if (root.findtext(f"{ns}IsTruncated") or "false") != "true":
            return out
        token = root.findtext(f"{ns}NextContinuationToken")


def _dandi_files(accession: str, version: str) -> list[tuple[str, str]]:
    out = []
    url = f"{DANDI_API}/dandisets/{accession}/versions/{version}/assets/?page_size=200"
    while url:
        page = json.loads(_get(url))
        for a in page.get("results", []):
            out.append((a["path"], f"{DANDI_API}/assets/{a['asset_id']}/download/"))
        url = page.get("next")
    return out


def fetch(dest: Path, datasets_path: Path = DATASETS) -> Path:
    _download_allowed()
    manifest = load(datasets_path)
    todo = [d.get("key") for d in manifest["datasets"] if d.get("status") != "selected"]
    if todo:
        raise StudyError(f"datasets not selected yet (TODO placeholders): {todo}")
    errs = [e for d in manifest["datasets"] for e in validate_dataset(d)]
    if errs:
        raise StudyError("; ".join(errs))
    files = []
    total = 0
    for d in manifest["datasets"]:
        if d["repository"] == "openneuro":
            listing = _openneuro_files(d["accession"])
        else:
            listing = _dandi_files(d["accession"], d["version"])
        for rel, url in listing:
            target = dest / d["key"] / rel
            if not target.resolve().is_relative_to((dest / d["key"]).resolve()):
                raise StudyError(f"unsafe path in listing: {rel!r}")
            target.parent.mkdir(parents=True, exist_ok=True)
            blob = _get(url)
            total += len(blob)
            if total > MAX_DOWNLOAD_BYTES:
                raise StudyError("download exceeds the study's size cap")
            target.write_bytes(blob)
            files.append(
                {
                    "dataset": d["key"],
                    "path": rel,
                    "size": len(blob),
                    "sha256": hashlib.sha256(blob).hexdigest(),
                }
            )
    out = dest / "files.json"
    out.write_bytes(
        json.dumps({"datasets": manifest["datasets"], "files": files}, indent=2).encode()
    )
    return out


# ---------------------------------------------------------------- sweep (CI only)
def _api(method: str, url: str, token: str, body: dict | None = None) -> dict[str, Any]:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method)  # noqa: S310
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310
        return json.loads(r.read())


def sweep_request(study: dict[str, Any], pipeline_ref: str, recording_ids: list[str]) -> dict:
    return {
        "name": study["id"],
        "pipeline": pipeline_ref,
        "recording_ids": recording_ids,
        "grid": study["grid"],
        "metric": study["metric"],
    }


def run_sweep(recordings: Path, out: Path, poll_s: float = 10.0, timeout_s: float = 6 * 3600):
    if os.environ.get("CI") != "true":
        raise StudyError("sweep is CI-only (it runs against the CI platform instance)")
    api, token = os.environ["NF_API_URL"].rstrip("/"), os.environ["NF_API_TOKEN"]
    study = load(STUDY)
    base = load(REPO / study["base_pipeline"])
    pub = _api("POST", f"{api}/v1/pipelines", token, base)
    rec_ids = load(recordings)["recording_ids"]
    sw = _api("POST", f"{api}/v1/sweeps", token, sweep_request(study, pub["ref"], rec_ids))
    deadline = time.monotonic() + timeout_s
    while True:
        rep = _api("GET", f"{api}/v1/sweeps/{sw['id']}/report", token)
        if rep["complete"] or time.monotonic() > deadline:
            break
        time.sleep(poll_s)
    out.mkdir(parents=True, exist_ok=True)
    (out / "sweep-report.json").write_bytes(json.dumps(rep, indent=2, sort_keys=True).encode())
    return rep


# ---------------------------------------------------------------- render (local OK)
def sha256_text_file(path: Path) -> str:
    """Same rule as packages/figures manifest.ts: text files hashed with CRLF -> LF."""
    buf = path.read_bytes()
    if b"\0" not in buf:
        buf = buf.replace(b"\r\n", b"\n")
    return hashlib.sha256(buf).hexdigest()


def _label(v: Any) -> str:
    if isinstance(v, list) and len(v) == 1:
        v = v[0]
    return json.dumps(v, separators=(",", ":"))


def _repo_path(p: Path) -> str:
    """Repo-relative POSIX path when inside the checkout (CI), else absolute."""
    try:
        return p.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(p.resolve())


def _commit() -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def render(report: dict[str, Any], out: Path, *, synthetic: bool = False) -> Path:
    """Write ``results.json`` (heatmap table: first factor = rows, second = columns, any further
    factors averaged in; every cell lists its run IDs) and ``<paper>.figures.json``."""
    out = out.resolve()
    forbidden = (REPO / "packages").resolve()
    if out.is_relative_to(forbidden):
        raise StudyError("render output must not go into packages/ (publishing is owner-gated)")
    factors = report["factors"]
    if not factors:
        raise StudyError("report has no factors")
    rows_f = factors[0]
    cols_f = factors[1] if len(factors) > 1 else None
    table: dict[str, dict[str, Any]] = {}
    for rv in rows_f["values"]:
        for cv in cols_f["values"] if cols_f else [None]:
            cells = [
                c
                for c in report["cells"]
                if c["value"] is not None
                and c["params"][rows_f["name"]] == rv
                and (cols_f is None or c["params"][cols_f["name"]] == cv)
            ]
            vals = [c["value"] for c in cells]
            table[f"{_label(rv)}|{_label(cv) if cols_f else 'all'}"] = {
                "mean": sum(vals) / len(vals) if vals else None,
                "n": len(vals),
                "run_ids": [c["run_id"] for c in cells],
                "prov_node_ids": [c["prov_node_id"] for c in cells],
            }
    study = load(STUDY)
    results = {
        "study": study["id"],
        "status": STATUS_LABEL,
        "synthetic": synthetic,
        "sweep_id": report["sweep_id"],
        "pipeline_version_id": report["pipeline_version_id"],
        "metric": report["metric"],
        "heatmap": table,
    }
    out.mkdir(parents=True, exist_ok=True)
    res_path = out / "results.json"
    res_path.write_bytes((json.dumps(results, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    script = Path(__file__).resolve()
    manifest = {
        "paper": study["id"],
        "generatedBy": "research/multiverse/run_study.py render (from a /v1/sweeps report).",
        "figures": [
            {
                "id": f"{study['id']}-heatmap",
                "status": "preliminary",
                "result": {"path": _repo_path(res_path), "sha256": sha256_text_file(res_path)},
                "script": {
                    "path": _repo_path(script),
                    "sha256": sha256_text_file(script),
                    "commit": _commit(),
                },
                "plot": {
                    "kind": "heatmap",
                    "base": ["heatmap"],
                    "key": "{row}|{col}",
                    "field": "mean",
                    "rows": {
                        "values": [_label(v) for v in rows_f["values"]],
                        "label": rows_f["name"],
                    },
                    "cols": {
                        "values": [_label(v) for v in cols_f["values"]] if cols_f else ["all"],
                        "label": cols_f["name"] if cols_f else "",
                    },
                    "value": {"label": report["metric"]["name"]},
                },
                "notes": f"{STATUS_LABEL}. Not published (owner-gated). "
                + ("SYNTHETIC test input, not a result." if synthetic else "")
                + " Every cell lists its run IDs in results.json.",
            }
        ],
    }
    man_path = out / f"{study['id']}.figures.json"
    man_path.write_bytes((json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
    return man_path


# ---------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="stage", required=True)
    sub.add_parser("validate")
    f = sub.add_parser("fetch")
    f.add_argument("--out", type=Path, required=True)
    sub.add_parser("ingest")
    s = sub.add_parser("sweep")
    s.add_argument("--recordings", type=Path, required=True)
    s.add_argument("--out", type=Path, required=True)
    r = sub.add_parser("render")
    r.add_argument("--report", type=Path, required=True)
    r.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    try:
        if args.stage == "validate":
            errs = validate()
            for e in errs:
                print(f"error: {e}", file=sys.stderr)
            print("ok" if not errs else f"{len(errs)} error(s)")
            return 1 if errs else 0
        if args.stage == "fetch":
            print(fetch(args.out))
            return 0
        if args.stage == "ingest":
            print(
                "ingest is not built yet: the dataset's format -> M2 upload/convert mapping is "
                "decided when a dataset is selected (research/multiverse/README.md)",
                file=sys.stderr,
            )
            return 3
        if args.stage == "sweep":
            run_sweep(args.recordings, args.out)
            return 0
        if args.stage == "render":
            print(render(load(args.report), args.out))
            return 0
    except StudyError as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
