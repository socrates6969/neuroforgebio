"""BIDS EEG (raw) import/export for EDF, BDF and BrainVision data files.

Import reads one `*_eeg.<ext>` file inside a BIDS dataset plus its sidecars (`_eeg.json`,
`_channels.tsv`, `_events.tsv`) and the subject's row of `participants.tsv`. The data itself goes
through the EDF/BrainVision converters. mne-bids and bids-validator are the CI reference tools
(`readers` extra); this module needs neither.

SEC-140: `participants.tsv` columns that hold direct identifiers (name, date of birth, MRN, ...)
are rejected unless the tenant runs in "identified" mode, in which case the values are moved to
`identifiers` and never written to the canonical copy or to exports.
"""

from __future__ import annotations

import csv
import io
import json
import math
import re
from pathlib import Path
from typing import Any

from nf_platform.ingest.convert.brainvision import read_brainvision, write_brainvision
from nf_platform.ingest.convert.edf import read_edf, write_edf
from nf_platform.ingest.convert.model import (
    CONVERTER_VERSION,
    DEFAULT_LIMITS,
    CorruptFileError,
    Event,
    FileTooLargeError,
    IdentifierPolicyError,
    Limits,
    SourceRecording,
    UnsupportedFormatError,
)

BIDS_VERSION = "1.9.0"
IDENTIFIER_COLUMNS = {
    "name",
    "first_name",
    "firstname",
    "last_name",
    "lastname",
    "surname",
    "full_name",
    "patient_name",
    "dob",
    "birthdate",
    "birth_date",
    "date_of_birth",
    "mrn",
    "medical_record_number",
    "address",
    "street",
    "email",
    "phone",
    "telephone",
    "ssn",
    "national_id",
    "personnummer",
}
_ENTITY_RE = re.compile(r"^(?P<ent>(?:[a-z]+-[a-zA-Z0-9]+_)+)eeg\.(?P<ext>edf|bdf|vhdr|set)$")
_EXT_FORMAT = {"edf": "edf", "bdf": "bdf", "vhdr": "brainvision"}
_BIDS_TYPES = {"EEG", "EOG", "ECG", "EMG", "MISC", "TRIG", "REF", "RESP", "GSR", "PPG", "TEMP"}
_MAX_SIDECAR = 4 * 1024 * 1024


def _read_small(p: Path) -> str:
    if p.stat().st_size > _MAX_SIDECAR:
        raise FileTooLargeError(f"{p.name} is too large for a sidecar")
    try:
        return p.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as e:
        raise CorruptFileError(f"{p.name} is not UTF-8") from e


def _json(p: Path) -> dict[str, Any]:
    try:
        obj = json.loads(_read_small(p))
    except json.JSONDecodeError as e:
        raise CorruptFileError(f"{p.name} is not valid JSON") from e
    if not isinstance(obj, dict):
        raise CorruptFileError(f"{p.name} must hold a JSON object")
    return obj


def _tsv(p: Path) -> list[dict[str, str]]:
    rows = list(csv.DictReader(io.StringIO(_read_small(p)), delimiter="\t"))
    for r in rows:
        if None in r or any(v is None for v in r.values()):
            raise CorruptFileError(f"{p.name}: ragged TSV row")
    return rows


def find_root(data_file: Path) -> Path:
    for parent in data_file.resolve().parents:
        if (parent / "dataset_description.json").is_file():
            return parent
    raise CorruptFileError("no dataset_description.json above the data file (not a BIDS dataset)")


def _entities(name: str) -> tuple[dict[str, str], str]:
    m = _ENTITY_RE.match(name)
    if not m:
        raise CorruptFileError(f"{name!r} is not a BIDS EEG data file name")
    ents = dict(e.split("-", 1) for e in m.group("ent").rstrip("_").split("_"))
    if "sub" not in ents or "task" not in ents:
        raise CorruptFileError("BIDS file name needs sub- and task- entities")
    if m.group("ext") == "set":
        raise UnsupportedFormatError("EEGLAB .set is not supported yet")
    return ents, _EXT_FORMAT[m.group("ext")]


def read_bids(
    data_file: str | Path,
    limits: Limits = DEFAULT_LIMITS,
    *,
    allow_identified: bool = False,
) -> SourceRecording:
    data_file = Path(data_file)
    root = find_root(data_file)
    resolved = data_file.resolve()
    if root not in resolved.parents:
        raise CorruptFileError("data file is outside the BIDS dataset")
    desc = _json(root / "dataset_description.json")
    if "BIDSVersion" not in desc or "Name" not in desc:
        raise CorruptFileError("dataset_description.json lacks Name/BIDSVersion")
    ents, data_format = _entities(data_file.name)
    rec = (
        read_brainvision(resolved, limits)
        if data_format == "brainvision"
        else read_edf(resolved, limits)
    )
    base = data_file.name.rsplit("_eeg.", 1)[0]
    folder = data_file.parent

    sidecar: dict[str, Any] = {}
    if (folder / f"{base}_eeg.json").is_file():
        sidecar = _json(folder / f"{base}_eeg.json")
        sf = sidecar.get("SamplingFrequency")
        if isinstance(sf, int | float) and not math.isclose(float(sf), rec.sfreq, rel_tol=1e-6):
            raise CorruptFileError("SamplingFrequency in _eeg.json does not match the data")

    ch_path = folder / f"{base}_channels.tsv"
    if ch_path.is_file():
        rows = _tsv(ch_path)
        by_name = {r.get("name", ""): r for r in rows}
        if set(by_name) != {c.name for c in rec.channels}:
            raise CorruptFileError("_channels.tsv names do not match the data file")
        for c in rec.channels:
            r = by_name[c.name]
            t = (r.get("type") or "EEG").upper()
            c.modality = t
            if r.get("units") and r["units"] != "n/a":
                c.unit = r["units"]
            if r.get("status"):
                c.extra.setdefault("bids", {})["status"] = r["status"]

    ev_path = folder / f"{base}_events.tsv"
    if ev_path.is_file():
        events = []
        for r in _tsv(ev_path):
            try:
                onset = float(r["onset"])
                dur = 0.0 if r.get("duration", "n/a") == "n/a" else float(r["duration"])
            except (KeyError, ValueError) as e:
                raise CorruptFileError("_events.tsv needs numeric onset/duration") from e
            label = r.get("trial_type") or r.get("value") or ""
            events.append(Event(onset, dur, label, kind="bids"))
        if len(events) > limits.max_events:
            raise FileTooLargeError("too many events")
        rec.events = events

    participant: dict[str, str] = {}
    identifiers = dict(rec.identifiers)
    pt = root / "participants.tsv"
    if pt.is_file():
        rows = _tsv(pt)
        cols = {c.lower() for c in (rows[0].keys() if rows else [])}
        bad = sorted(cols & IDENTIFIER_COLUMNS)
        if bad and not allow_identified:
            raise IdentifierPolicyError(
                f"participants.tsv has direct-identifier columns {bad}; rejected (SEC-140)"
            )
        for r in rows:
            if r.get("participant_id") == f"sub-{ents['sub']}":
                for k, v in r.items():
                    if k.lower() in IDENTIFIER_COLUMNS:
                        identifiers[f"bids_{k}"] = v
                    else:
                        participant[k] = v
    rec.identifiers = identifiers
    rec.meta["bids"] = {
        "entities": ents,
        "datatype": "eeg",
        "data_format": data_format,
        "eeg_json": sidecar,
        "participant": participant,
        "bids_version": desc.get("BIDSVersion"),
    }
    rec.source_format = "bids"
    return rec


def write_bids(root: str | Path, rec: SourceRecording) -> Path:
    """Write a minimal valid BIDS raw dataset holding this recording. Returns the data file."""
    root = Path(root)
    b = rec.meta.get("bids", {})
    ents = dict(b.get("entities") or {"sub": "01", "task": "nfexport"})
    data_format = b.get("data_format") or "edf"
    order = ["sub", "ses", "task", "acq", "run"]
    base = "_".join(f"{k}-{ents[k]}" for k in order if k in ents)
    folder = root / f"sub-{ents['sub']}"
    if "ses" in ents:
        folder = folder / f"ses-{ents['ses']}"
    folder = folder / "eeg"
    folder.mkdir(parents=True, exist_ok=True)

    (root / "dataset_description.json").write_text(
        json.dumps(
            {
                "Name": "nf-platform export",
                "BIDSVersion": BIDS_VERSION,
                "DatasetType": "raw",
                "GeneratedBy": [{"Name": "nf-platform", "Version": CONVERTER_VERSION}],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (root / "README").write_text(
        "Exported by nf-platform. Synthetic or licence-checked data only.\n", encoding="utf-8"
    )
    part = {k: v for k, v in (b.get("participant") or {}).items() if k != "participant_id"}
    part = {k: v for k, v in part.items() if k.lower() not in IDENTIFIER_COLUMNS}
    cols = ["participant_id", *part]
    (root / "participants.tsv").write_text(
        "\t".join(cols) + "\n" + "\t".join([f"sub-{ents['sub']}", *part.values()]) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    ext = {"edf": "edf", "bdf": "bdf", "brainvision": "vhdr"}[data_format]
    target = folder / f"{base}_eeg.{ext}"
    if data_format == "brainvision":
        write_brainvision(target, rec)
    else:
        write_edf(target, rec, bdf=data_format == "bdf")

    sc = dict(b.get("eeg_json") or {})
    sc.update(
        {
            "TaskName": sc.get("TaskName", ents["task"]),
            "SamplingFrequency": rec.sfreq,
            "PowerLineFrequency": sc.get("PowerLineFrequency", "n/a"),
            "SoftwareFilters": sc.get("SoftwareFilters", "n/a"),
            "EEGReference": sc.get("EEGReference", "n/a"),
            "RecordingDuration": rec.data.shape[1] / rec.sfreq,
        }
    )
    (folder / f"{base}_eeg.json").write_text(
        json.dumps(sc, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    lines = ["name\ttype\tunits"]
    for c in rec.channels:
        t = c.modality if c.modality in _BIDS_TYPES else "MISC"
        lines.append(f"{c.name}\t{t}\t{c.unit or 'n/a'}")
    (folder / f"{base}_channels.tsv").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )
    if rec.events:
        ev = ["onset\tduration\ttrial_type"]
        for e in sorted(rec.events, key=lambda e: e.onset_s):
            ev.append(f"{e.onset_s!r}\t{e.duration_s!r}\t{e.label or 'n/a'}")
        (folder / f"{base}_events.tsv").write_text(
            "\n".join(ev) + "\n", encoding="utf-8", newline="\n"
        )
    return target
