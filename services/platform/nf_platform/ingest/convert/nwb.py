"""NWB (HDF5) import/export of `ElectricalSeries` via pynwb (CI-only: pynwb is in the `readers`
extra, not installed on the dev PC). Raw stored values are kept with NWB's
`conversion`/`offset`/`channel_conversion` as scale/offset, so the round trip is exact.

SEC-141: `Subject` fields other than the pseudonymous `subject_id`, and the file-level
experimenter/institution/lab fields, go to `identifiers` and are never exported.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from nf_platform.ingest.convert.model import (
    DEFAULT_LIMITS,
    Channel,
    FileTooLargeError,
    Limits,
    MissingDependencyError,
    SourceRecording,
    UnsupportedFormatError,
)


def _pynwb():
    try:
        import pynwb  # noqa: PLC0415 - optional, CI-only dependency

        return pynwb
    except ImportError as e:
        raise MissingDependencyError("pynwb is not installed (CI-only reader)") from e


def read_nwb(path: str | Path, limits: Limits = DEFAULT_LIMITS) -> list[SourceRecording]:
    pynwb = _pynwb()
    path = Path(path)
    if path.stat().st_size > limits.max_file_bytes:
        raise FileTooLargeError("NWB file exceeds the size limit")
    recs = []
    with pynwb.NWBHDF5IO(str(path), "r") as io:
        nwb = io.read()
        identifiers: dict[str, str] = {}
        subj = nwb.subject
        if subj is not None:
            for k in ("date_of_birth", "description", "genotype", "strain", "weight"):
                v = getattr(subj, k, None)
                if v:
                    identifiers[f"nwb_subject_{k}"] = str(v)
        for k in ("experimenter", "institution", "lab"):
            v = getattr(nwb, k, None)
            if v:
                identifiers[f"nwb_{k}"] = str(v)
        start = nwb.session_start_time.isoformat() if nwb.session_start_time else None
        for name, obj in nwb.acquisition.items():
            if type(obj).__name__ != "ElectricalSeries":
                continue
            data = np.asarray(obj.data[:])
            if data.ndim == 1:
                data = data[:, None]
            n, n_ch = data.shape
            if n > limits.max_samples_per_channel or n_ch > limits.max_channels:
                raise FileTooLargeError("ElectricalSeries too large")
            ts = None
            if obj.rate is not None:
                sfreq = float(obj.rate)
            else:
                ts = np.asarray(obj.timestamps[:], dtype=np.float64)
                span = float(ts[-1] - ts[0]) if len(ts) > 1 else 0.0
                sfreq = (len(ts) - 1) / span if span > 0 else 1.0
            conv = float(obj.conversion)
            chconv = (
                np.asarray(obj.channel_conversion[:], dtype=np.float64)
                if obj.channel_conversion is not None
                else np.ones(n_ch)
            )
            table = obj.electrodes.table
            idx = list(obj.electrodes.data[:])
            cols = table.colnames
            labels = []
            for j, row in enumerate(idx):
                if "label" in cols:
                    labels.append(str(table["label"][row]))
                else:
                    labels.append(f"{table['location'][row]}-{j + 1}")
            chans = [
                Channel(
                    name=labels[j],
                    unit=obj.unit,
                    modality="EPHYS",
                    scale=conv * float(chconv[j]),
                    offset=float(getattr(obj, "offset", 0.0) or 0.0),
                    extra={"nwb": {"location": str(table["location"][idx[j]])}},
                )
                for j in range(n_ch)
            ]
            recs.append(
                SourceRecording(
                    data=np.ascontiguousarray(data.T),
                    sfreq=sfreq,
                    channels=chans,
                    source_format="nwb",
                    start_time=start,
                    timestamps=ts,
                    meta={
                        "nwb": {
                            "series_name": name,
                            "starting_time": float(obj.starting_time or 0.0),
                            "subject_id": getattr(subj, "subject_id", None) if subj else None,
                        }
                    },
                    identifiers=dict(identifiers),
                )
            )
    if not recs:
        raise UnsupportedFormatError("no ElectricalSeries in the NWB acquisition group")
    for r in recs:
        r.validate(limits)
    return recs


def write_nwb(path: str | Path, recs: list[SourceRecording]) -> Path:
    pynwb = _pynwb()
    from pynwb.ecephys import ElectricalSeries  # noqa: PLC0415
    from pynwb.file import Subject  # noqa: PLC0415

    path = Path(path)
    first = recs[0]
    start = (
        datetime.fromisoformat(first.start_time)
        if first.start_time
        else datetime(1970, 1, 1, tzinfo=UTC)
    )
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    nwb = pynwb.NWBFile(
        session_description="nf-platform export",
        identifier=str(uuid.uuid4()),
        session_start_time=start,
    )
    sid = first.meta.get("nwb", {}).get("subject_id")
    if sid:
        nwb.subject = Subject(subject_id=str(sid))
    dev = nwb.create_device(name="nf-platform")
    grp = nwb.create_electrode_group(
        name="electrodes", description="exported", location="unknown", device=dev
    )
    nwb.add_electrode_column(name="label", description="channel label")
    offset = 0
    for i, rec in enumerate(recs):
        for c in rec.channels:
            loc = c.extra.get("nwb", {}).get("location", "unknown")
            nwb.add_electrode(group=grp, location=loc, label=c.name)
        region = nwb.create_electrode_table_region(
            list(range(offset, offset + len(rec.channels))), "channels"
        )
        offset += len(rec.channels)
        scales = np.array([c.scale for c in rec.channels], dtype=np.float64)
        offs = {c.offset for c in rec.channels}
        if len(offs) > 1:
            raise UnsupportedFormatError("NWB needs one offset per series")
        kw: dict[str, Any] = {}
        if rec.timestamps is not None:
            kw["timestamps"] = rec.timestamps
        else:
            kw["rate"] = rec.sfreq
            kw["starting_time"] = rec.meta.get("nwb", {}).get("starting_time", 0.0)
        nwb.add_acquisition(
            ElectricalSeries(
                name=rec.meta.get("nwb", {}).get("series_name") or f"ElectricalSeries{i}",
                data=np.ascontiguousarray(rec.data.T),
                electrodes=region,
                conversion=1.0,
                channel_conversion=scales,
                offset=offs.pop(),
                **kw,
            )
        )
    with pynwb.NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)
    return path
