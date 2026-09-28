"""Read the pinned MC_RTT training NWB (DANDI 000129) with h5py. Raw files stay outside the repo."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np

DANDISET = "000129"
VERSION = "0.241017.1444"
ASSET_ID = "2ae6bf3c-788b-4ece-8c01-4b4a5680b25b"
ASSET_PATH = "sub-Indy/sub-Indy_desc-train_behavior+ecephys.nwb"
FILE_NAME = "sub-Indy_desc-train_behavior+ecephys.nwb"
SIZE_BYTES = 49_764_168
# dandi:sha2-256 from api.dandiarchive.org/api/assets/<ASSET_ID>/ (checked against the download).
SHA256 = "2f78db62bd4d68b9bc737444f72bc2dfe475d7390dd7a54848aaf6a6a6ba8da5"
DOWNLOAD_URL = f"https://api.dandiarchive.org/api/assets/{ASSET_ID}/download/"
DOI = f"10.48324/dandi.{DANDISET}/{VERSION}"
LICENCE = "CC-BY-4.0"
CITATION = (
    "O'Doherty, Joseph (2024) MC_RTT: macaque motor cortex spiking activity during self-paced "
    f"reaching (Version {VERSION}) [Data set]. DANDI archive. https://doi.org/{DOI}"
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class Session:
    spike_times: list[np.ndarray]  # seconds, one array per unit
    unit_electrode: np.ndarray  # electrode id (1..96) each unit was sorted from
    rate_hz: float  # behaviour sampling rate
    cursor_mm: np.ndarray  # (S, 2)
    finger_vel_mm_s: np.ndarray  # (S, 2)
    target_mm: np.ndarray  # (S, 2)


def load(path: Path, verify: bool = True) -> Session:
    import h5py  # only the offline pipeline needs it, not the unit tests

    if verify:
        got = sha256_file(path)
        if got != SHA256:
            raise ValueError(f"{path}: sha256 {got} != pinned {SHA256}")
    with h5py.File(path, "r") as f:
        st = f["units/spike_times"][:]
        idx = f["units/spike_times_index"][:].astype(np.int64)
        starts = np.concatenate([[0], idx[:-1]])
        spikes = [st[a:b] for a, b in zip(starts, idx, strict=True)]
        # units/electrodes is a DynamicTableRegion: row indices into the electrodes table.
        e_index = f["units/electrodes_index"][:].astype(np.int64)
        if not np.array_equal(e_index, np.arange(1, len(idx) + 1)):
            raise ValueError("expected exactly one electrode per unit")
        unit_electrode = f["general/extracellular_ephys/electrodes/id"][:][f["units/electrodes"][:]]
        beh = f["processing/behavior"]
        rate = float(beh["cursor_pos/starting_time"].attrs["rate"])
        for k in ("cursor_pos", "finger_vel", "target_pos"):
            if float(beh[f"{k}/starting_time"][()]) != 0.0:
                raise ValueError(f"{k}: expected starting_time 0")
        return Session(
            spike_times=spikes,
            unit_electrode=unit_electrode,
            rate_hz=rate,
            cursor_mm=beh["cursor_pos/data"][:],
            finger_vel_mm_s=beh["finger_vel/data"][:],
            target_mm=beh["target_pos/data"][:],
        )
