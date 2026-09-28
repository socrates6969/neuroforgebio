"""Input: a per-electrode projected-field (PF) map (schema ``nf.pf-map/v1``), as JSON or CSV.

JSON form::

    {
      "schema": "nf.pf-map/v1",
      "map_id": "example-1",                       # optional
      "electrodes": [
        {"electrode_id": "33", "array_id": "LateralSensory", "has_pf": true,
         "palm_segment": "D2d-pu+D2d-pr", "dorsum_segment": "", "x_mm": 0.0, "y_mm": 0.0}
      ]
    }

CSV form: a header row with ``electrode_id,array_id`` and any of
``has_pf,palm_segment,dorsum_segment,x_mm,y_mm`` (one row per electrode, same meaning; ``has_pf``
is ``1/0/true/false``, empty = true).

Segment tags use the hand-segment vocabulary of the digitised Greenspon 2025 Extended Data Fig. 1
(e.g. ``D2m-u+D2m-r``, ``P3-mcp``, ``P-dr``, ``W``). The labelling rules only read the tag prefix
(``Dk`` = digit k, ``W`` = wrist, anything else = palm or dorsum of the hand), so other tags are
accepted; tags outside the reference table only disable the relabelling check and are listed in the
output. The R1 dominant segment is derived (palm tag if set, else dorsum tag). An optional
``dominant_segment`` field (``palm:<tag>`` / ``dors:<tag>``) is checked against that derivation.
"""

from __future__ import annotations

import csv
import io
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ._canonical import CanonicalError, canonicalize, parse, sha256_hex
from .labels import dominant_segment

SCHEMA_ID = "nf.pf-map/v1"
MAX_ELECTRODES = 4096
TAG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+\-]{0,63}$")
ID_RE = re.compile(r"^[^\x00-\x1f]{1,128}$")
ELECTRODE_FIELDS = (
    "electrode_id",
    "array_id",
    "has_pf",
    "palm_segment",
    "dorsum_segment",
    "x_mm",
    "y_mm",
    "dominant_segment",
)
TOP_FIELDS = ("schema", "map_id", "electrodes")


class PFMapError(ValueError):
    """The input map is malformed or violates the schema. The message names the offending field."""


class PFMapReadError(PFMapError):
    """The input could not be read or parsed at all (I/O error, JSON/CSV syntax)."""


@dataclass(frozen=True)
class Electrode:
    """One wired electrode of the map."""

    electrode_id: str
    array_id: str
    has_pf: bool
    palm_segment: str
    dorsum_segment: str
    x_mm: float | None = None
    y_mm: float | None = None

    @property
    def dominant_segment(self) -> str:
        """R1 dominant segment key (``palm:<tag>`` if the palm tag is set, else ``dors:<tag>``)."""
        return dominant_segment(self.palm_segment, self.dorsum_segment)


@dataclass(frozen=True)
class PFMap:
    """A validated PF map. Electrode order is kept (it fixes the random-draw order)."""

    electrodes: tuple[Electrode, ...]
    map_id: str | None = None

    @property
    def pf_electrodes(self) -> tuple[Electrode, ...]:
        """Electrodes with a projected field (the only ones that can form channels)."""
        return tuple(e for e in self.electrodes if e.has_pf)

    def normalised(self) -> dict[str, Any]:
        """The document that is hashed (defaults written out; JSON and CSV give the same)."""
        els = []
        for e in self.electrodes:
            d: dict[str, Any] = {
                "electrode_id": e.electrode_id,
                "array_id": e.array_id,
                "has_pf": e.has_pf,
                "palm_segment": e.palm_segment,
                "dorsum_segment": e.dorsum_segment,
            }
            if e.x_mm is not None:
                d["x_mm"] = e.x_mm
                d["y_mm"] = e.y_mm
            els.append(d)
        return {"schema": SCHEMA_ID, "map_id": self.map_id, "electrodes": els}

    def sha256(self) -> str:
        """SHA-256 of the NF-CJSON v1 bytes of :meth:`normalised` (docs/spec/hashing.md)."""
        return sha256_hex(canonicalize(self.normalised()))


def _err(where: str, msg: str) -> PFMapError:
    return PFMapError(f"{where}: {msg}")


def _str_field(d: dict[str, Any], key: str, where: str, required: bool) -> str:
    if key not in d or d[key] is None:
        if required:
            raise _err(where, f"'{key}' is required")
        return ""
    v = d[key]
    if not isinstance(v, str):
        raise _err(where, f"'{key}' must be a string, got {type(v).__name__}")
    return v.strip()


def _num_field(d: dict[str, Any], key: str, where: str) -> float | None:
    if key not in d or d[key] is None or d[key] == "":
        return None
    v = d[key]
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise _err(where, f"'{key}' must be a number, got {type(v).__name__}")
    if not math.isfinite(v):
        raise _err(where, f"'{key}' must be finite")
    return float(v)


def _electrode(d: Any, i: int) -> Electrode:
    where = f"electrodes[{i}]"
    if not isinstance(d, dict):
        raise _err(where, "must be an object")
    unknown = sorted(set(d) - set(ELECTRODE_FIELDS))
    if unknown:
        raise _err(where, f"unknown field(s) {unknown}; allowed: {list(ELECTRODE_FIELDS)}")
    eid = _str_field(d, "electrode_id", where, required=True)
    aid = _str_field(d, "array_id", where, required=True)
    for key, val in (("electrode_id", eid), ("array_id", aid)):
        if not ID_RE.match(val):
            raise _err(where, f"'{key}' must be 1-128 printable characters")
    has_pf = d.get("has_pf", True)
    if has_pf is None:
        has_pf = True
    if not isinstance(has_pf, bool):
        raise _err(where, "'has_pf' must be true or false")
    palm = _str_field(d, "palm_segment", where, required=False)
    dors = _str_field(d, "dorsum_segment", where, required=False)
    for key, tag in (("palm_segment", palm), ("dorsum_segment", dors)):
        if tag and not TAG_RE.match(tag):
            raise _err(where, f"'{key}' {tag!r} is not a segment tag (letters, digits, '+', '-')")
    if has_pf and not (palm or dors):
        raise _err(where, "a PF electrode needs a palm_segment or a dorsum_segment")
    if not has_pf and (palm or dors):
        raise _err(where, "has_pf is false but segment labels are set")
    x = _num_field(d, "x_mm", where)
    y = _num_field(d, "y_mm", where)
    if (x is None) != (y is None):
        raise _err(where, "give both x_mm and y_mm or neither")
    e = Electrode(eid, aid, has_pf, palm, dors, x, y)
    dom = d.get("dominant_segment")
    if dom not in (None, ""):
        if not has_pf:
            raise _err(where, "dominant_segment is set on an electrode without a PF")
        if dom != e.dominant_segment:
            raise _err(
                where,
                f"dominant_segment {dom!r} disagrees with the palm-first rule "
                f"({e.dominant_segment!r})",
            )
    return e


def from_document(doc: Any) -> PFMap:
    """Validate a parsed JSON document and build a :class:`PFMap`."""
    if not isinstance(doc, dict):
        raise _err("$", "the map must be a JSON object")
    unknown = sorted(set(doc) - set(TOP_FIELDS))
    if unknown:
        raise _err("$", f"unknown field(s) {unknown}; allowed: {list(TOP_FIELDS)}")
    if doc.get("schema") != SCHEMA_ID:
        raise _err("$.schema", f"must be {SCHEMA_ID!r}, got {doc.get('schema')!r}")
    map_id = doc.get("map_id")
    if map_id is not None and (not isinstance(map_id, str) or not ID_RE.match(map_id)):
        raise _err("$.map_id", "must be a string of 1-128 printable characters or null")
    els = doc.get("electrodes")
    if not isinstance(els, list):
        raise _err("$.electrodes", "must be an array")
    if len(els) > MAX_ELECTRODES:
        raise _err("$.electrodes", f"at most {MAX_ELECTRODES} electrodes")
    out = tuple(_electrode(d, i) for i, d in enumerate(els))
    seen: set[tuple[str, str]] = set()
    for i, e in enumerate(out):
        k = (e.array_id, e.electrode_id)
        if k in seen:
            raise _err(
                f"electrodes[{i}]", f"duplicate electrode {e.electrode_id!r} in {e.array_id!r}"
            )
        seen.add(k)
    return PFMap(out, map_id)


def _csv_bool(v: str, where: str) -> bool:
    s = v.strip().lower()
    if s in ("", "1", "true", "yes"):
        return True
    if s in ("0", "false", "no"):
        return False
    raise _err(where, f"'has_pf' must be 1/0/true/false, got {v!r}")


def _csv_num(v: str, key: str, where: str) -> float | None:
    s = v.strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError as exc:
        raise _err(where, f"'{key}' must be a number, got {v!r}") from exc


def from_csv_text(text: str, map_id: str | None = None) -> PFMap:
    """Parse the CSV form (header row required) into a :class:`PFMap`."""
    reader = csv.DictReader(io.StringIO(text))
    header = reader.fieldnames or []
    missing = [c for c in ("electrode_id", "array_id") if c not in header]
    if missing:
        raise _err("csv header", f"missing column(s) {missing}")
    unknown = sorted(set(header) - set(ELECTRODE_FIELDS))
    if unknown:
        raise _err("csv header", f"unknown column(s) {unknown}; allowed: {list(ELECTRODE_FIELDS)}")
    els = []
    for i, row in enumerate(reader):
        where = f"csv row {i + 2}"
        if None in row:
            raise _err(where, "more fields than header columns")
        d: dict[str, Any] = {k: (v if v is not None else "") for k, v in row.items()}
        if "has_pf" in d:
            d["has_pf"] = _csv_bool(d["has_pf"], where)
        for key in ("x_mm", "y_mm"):
            if key in d:
                d[key] = _csv_num(d[key], key, where)
        els.append(d)
    doc: dict[str, Any] = {"schema": SCHEMA_ID, "electrodes": els}
    if map_id is not None:
        doc["map_id"] = map_id
    return from_document(doc)


def from_json_text(text: str) -> PFMap:
    """Parse the JSON form strictly (duplicate keys, NaN and Infinity are rejected)."""
    try:
        doc = parse(text)
    except (CanonicalError, json.JSONDecodeError) as exc:
        raise PFMapReadError(f"invalid JSON: {exc}") from exc
    return from_document(doc)


def load_map(path: str | Path, fmt: str = "auto") -> PFMap:
    """Load a map from a ``.json`` or ``.csv`` file (``fmt`` = ``auto`` | ``json`` | ``csv``)."""
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise PFMapReadError(f"cannot read {p}: {exc}") from exc
    kind = fmt if fmt != "auto" else ("csv" if p.suffix.lower() == ".csv" else "json")
    if kind == "csv":
        try:
            return from_csv_text(text)
        except csv.Error as exc:
            raise PFMapReadError(f"invalid CSV: {exc}") from exc
    if kind == "json":
        return from_json_text(text)
    raise PFMapError(f"unknown format {fmt!r} (use auto, json or csv)")
