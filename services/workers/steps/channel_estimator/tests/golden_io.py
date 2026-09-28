"""Golden inputs: the digitised research data (pinned by SHA-256) and converters to nf.pf-map/v1.

The two files in ``tests/golden/`` are byte copies (LF line endings) of the research inputs in
``research/somatosensory/notes/published-derived/`` (vendored here so the tests do not depend on
the research workspace). Hashes are computed after CRLF -> LF normalisation, so the same pin
holds for the original CRLF files of the research workspace.

Run as a script to regenerate the package reference tables and the example maps::

    .venv/Scripts/python services/workers/steps/channel_estimator/tests/golden_io.py
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

PKG_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[5]
GOLDEN = Path(__file__).resolve().parent / "golden"
RESEARCH = REPO_ROOT / "research" / "somatosensory"
RESEARCH_DATA = RESEARCH / "notes" / "data"
RESEARCH_RESULTS = RESEARCH / "code" / "results"

PARTICIPANTS = ("C1", "P2", "P3")
# SHA-256 of the LF-normalised bytes. A changed file must fail loudly.
PINNED = {
    "greenspon2025_ed1_extraction.json": (
        "100f45ce6eb1530d9f4ba719006def3a7a9cae4f016d9d7ae45fbb020b4ecb69"
    ),
    "pf_per_electrode_greenspon2025.csv": (
        "25d26d8027e765e834f2f6d9f40dcf639fc1b4001ea40d7e1db65f2d72183bb8"
    ),
}
PINNED_RESULTS = {
    "p6_empirical_channels.json": (
        "e75539b7b3f93679a970376340e133d79578a7e68c68e7b2b831c9bf28adc7f3"
    ),
    "p6_per_participant.csv": "71c73994c6df9353db3601347140e4310cc52e084b62911278542d5924477fe6",
}
CITATION = (
    "Greenspon et al. 2025, Nature Biomedical Engineering, Extended Data Fig. 1 (PMC12176618), "
    "digitised (grade B); participants C1, P2, P3"
)


def lf_bytes(path: Path) -> bytes:
    """File bytes with CRLF normalised to LF."""
    return path.read_bytes().replace(b"\r\n", b"\n")


def lf_sha256(path: Path) -> str:
    """SHA-256 of :func:`lf_bytes`."""
    return hashlib.sha256(lf_bytes(path)).hexdigest()


def golden_text(name: str) -> str:
    """Text of a pinned golden input; raises if its hash changed."""
    path = GOLDEN / name
    digest = lf_sha256(path)
    if digest != PINNED[name]:
        raise AssertionError(f"{name} changed: sha256 {digest} != pinned {PINNED[name]}")
    return lf_bytes(path).decode("utf-8")


def research_results() -> dict[str, Any]:
    """The reviewed research JSON, read in place (hash pinned)."""
    path = RESEARCH_RESULTS / "p6_empirical_channels.json"
    digest = lf_sha256(path)
    if digest != PINNED_RESULTS["p6_empirical_channels.json"]:
        raise AssertionError(f"research result changed: {digest}")
    return json.loads(lf_bytes(path))


def greenspon_rows() -> list[dict[str, str]]:
    """Rows of the per-electrode CSV (all wired electrodes, file order)."""
    return list(csv.DictReader(io.StringIO(golden_text("pf_per_electrode_greenspon2025.csv"))))


def participant_document(part: str) -> dict[str, Any]:
    """nf.pf-map/v1 document of one participant (both arrays, all wired electrodes, file order)."""
    els = []
    for r in greenspon_rows():
        if r["participant"] != part:
            continue
        has_pf = r["has_PF"] == "1"
        els.append(
            {
                "electrode_id": str(int(r["electrode_channel"])),
                "array_id": r["array"],
                "has_pf": has_pf,
                "palm_segment": r["palm_segment"],
                "dorsum_segment": r["dors_segment"],
                "x_mm": float(r["x_mm"]),
                "y_mm": float(r["y_mm"]),
            }
        )
    return {"schema": "nf.pf-map/v1", "map_id": f"greenspon2025-{part}", "electrodes": els}


def reference_segments() -> dict[str, Any]:
    """The package segment table, built exactly as the research ``load_segments``."""
    d = json.loads(golden_text("greenspon2025_ed1_extraction.json"))
    segs = []
    for surf in ("palm", "dors"):
        for s in d["segments"][surf]:
            segs.append(
                {
                    "key": surf + ":" + s["label"],
                    "surface": surf,
                    "tag": s["label"],
                    "cx": s["cx"],
                    "cy": s["cy"],
                    "area_mm2": s["area_mm2"],
                }
            )
    keys = {s["key"] for s in segs}
    # The research falls back to CSV centroids for tags missing from the table; none are missing.
    for r in greenspon_rows():
        if r["has_PF"] != "1":
            continue
        for surf, tag in (("palm", r["palm_segment"]), ("dors", r["dors_segment"])):
            if tag and surf + ":" + tag not in keys:
                raise AssertionError(f"tag {surf}:{tag} missing from the segment table")
    return {
        "source": {
            "citation": CITATION,
            "file": "research/somatosensory/notes/published-derived/"
            "greenspon2025_ed1_extraction.json",
            "sha256_lf": PINNED["greenspon2025_ed1_extraction.json"],
        },
        "segments": segs,
    }


def reference_pooled() -> dict[str, Any]:
    """R1 dominant segment keys of all PF electrodes, C1 then P2 then P3 (research Null B order)."""
    rows = greenspon_rows()
    keys = []
    for part in PARTICIPANTS:
        for r in rows:
            if r["participant"] == part and r["has_PF"] == "1":
                p, d = r["palm_segment"], r["dors_segment"]
                keys.append(("palm:" + p) if p else ("dors:" + d))
    return {
        "source": {
            "citation": CITATION,
            "file": "research/somatosensory/notes/published-derived/"
            "pf_per_electrode_greenspon2025.csv",
            "sha256_lf": PINNED["pf_per_electrode_greenspon2025.csv"],
        },
        "participants": list(PARTICIPANTS),
        "keys": keys,
    }


def main() -> None:
    """Regenerate package reference tables and example maps (then run Prettier on them)."""
    ref_dir = PKG_ROOT / "nf_channel_estimator" / "reference_data"
    for name, doc in (
        ("greenspon2025_ed1_segments.json", reference_segments()),
        ("greenspon2025_pooled_dominant_segments.json", reference_pooled()),
    ):
        (ref_dir / name).write_text(
            json.dumps(doc, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
    for part in PARTICIPANTS:
        path = PKG_ROOT / "examples" / f"greenspon2025_{part}.pf-map.json"
        path.write_text(
            json.dumps(participant_document(part), indent=2) + "\n", encoding="utf-8", newline="\n"
        )
    import sys

    sys.path.insert(0, str(PKG_ROOT))
    from nf_channel_estimator.schema import input_schema, output_schema

    for name, doc in (("pf-map.v1", input_schema()), ("channel-estimate.v1", output_schema())):
        (PKG_ROOT / "schemas" / f"{name}.schema.json").write_text(
            json.dumps(doc, indent=2) + "\n", encoding="utf-8", newline="\n"
        )


if __name__ == "__main__":
    main()
