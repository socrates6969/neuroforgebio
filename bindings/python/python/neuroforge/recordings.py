"""Recordings: ``nf.open`` a local file or a platform recording.

A local file is hashed client-side by nf-core (``blob:sha256``); on upload the platform hashes it
again and rejects the upload if the two differ (BLUEPRINT §3.3, step 2.6).
"""

from __future__ import annotations

import builtins
import json
import os
import struct
import time
import uuid
from pathlib import Path
from typing import Any

import numpy as np

from . import canonical
from .client import Client, NfApiError, get_client

__all__ = ["LocalFile", "RemoteRecording", "open"]

WINDOW_MAGIC = b"NFW1"


def _is_uuid(s: str) -> bool:
    try:
        uuid.UUID(s)
    except ValueError:
        return False
    return True


def open(
    source: str | os.PathLike[str], *, client: Client | None = None
) -> LocalFile | RemoteRecording:  # noqa: A001
    """Open a local recording file (EDF/BDF/XDF/NWB/...) or a platform recording by ID."""
    p = Path(os.fspath(source))
    if p.is_file():
        return LocalFile(p.resolve(), client=client)
    if isinstance(source, str) and _is_uuid(source):
        return RemoteRecording(source, client=client)
    raise FileNotFoundError(f"no such file, and not a recording ID: {source}")


class LocalFile:
    """A recording file on this machine. Upload happens on first use by the platform."""

    def __init__(self, path: Path, *, client: Client | None = None) -> None:
        self.path = path
        self._client = client
        self._blob: tuple[str, int] | None = None
        self.remote: RemoteRecording | None = None
        self.upload_id: str | None = None

    def __repr__(self) -> str:
        return f"LocalFile({str(self.path)!r})"

    @property
    def filename(self) -> str:
        return self.path.name

    @property
    def blob_id(self) -> str:
        """``blob:sha256:<hex>`` of the file bytes (computed by nf-core, streamed)."""
        if self._blob is None:
            self._blob = canonical.blob_id_file(self.path)
        return self._blob[0]

    @property
    def size(self) -> int:
        if self._blob is None:
            self._blob = canonical.blob_id_file(self.path)
        return self._blob[1]

    def upload(
        self,
        session: str | None = None,
        *,
        synthetic: bool | None = None,
        timeout: float = 600.0,
        client: Client | None = None,
    ) -> RemoteRecording:
        """Upload into ``session`` (default: the client's session), wait for conversion and
        return the platform recording. ``synthetic=True`` marks synthetic or licence-checked
        public data (SEC-071); default: the client's ``synthetic`` setting."""
        if self.remote is not None:
            return self.remote
        c = get_client(client or self._client)
        sid = session or c.session
        if not sid:
            raise ValueError("no session: pass session= or configure(session=...) / NF_SESSION")
        sess = c.get(f"/v1/sessions/{sid}")
        subject = c.get(f"/v1/subjects/{sess['subject_id']}")
        up = c.post(
            f"/v1/datasets/{subject['dataset_id']}/uploads",
            {
                "session_id": sid,
                "filename": self.filename,
                "size_bytes": self.size,
                "synthetic": c.synthetic if synthetic is None else synthetic,
            },
        )
        self.upload_id = up["id"]
        part_size = int(up["part_size"])
        with builtins.open(self.path, "rb") as fh:
            for t in up["parts"]:
                fh.seek((int(t["part_number"]) - 1) * part_size)
                data = fh.read(part_size)
                if t.get("auth") == "none" and "://" in t["url"]:
                    c.put_presigned(t["url"], data)
                else:
                    c.put_bytes(t["url"], data)
        sha_hex = self.blob_id.split(":")[-1]
        c.post(f"/v1/uploads/{self.upload_id}/complete", {"sha256": sha_hex})
        deadline = time.monotonic() + timeout
        while True:
            st = c.get(f"/v1/uploads/{self.upload_id}")
            if st["recording_ids"]:
                self.remote = RemoteRecording(st["recording_ids"][0], client=c)
                return self.remote
            if st["state"] in ("rejected", "failed"):
                raise NfApiError("upload", 0, f"upload {st['state']}: {st.get('error')}", None)
            if time.monotonic() > deadline:
                raise TimeoutError(f"upload {self.upload_id} not converted after {timeout} s")
            time.sleep(c.poll_interval)

    def to_mne(self, preload: bool = True):
        """Read the file with MNE (``pip install neuroforge[mne]``)."""
        from .mne_interop import read_raw

        return read_raw(self.path, preload=preload)


class RemoteRecording:
    """A recording on the platform."""

    def __init__(self, recording_id: str, *, client: Client | None = None) -> None:
        self.id = str(recording_id)
        self._client = client

    def __repr__(self) -> str:
        return f"RemoteRecording({self.id!r})"

    def info(self) -> dict[str, Any]:
        return get_client(self._client).get(f"/v1/recordings/{self.id}")

    def read(
        self,
        start: float,
        end: float,
        *,
        channels: list[str] | None = None,
        level: int = 0,
        kind: str = "mean",
        physical: bool = False,
    ) -> tuple[dict[str, Any], np.ndarray]:
        """Samples ``[start, end)`` seconds as ``(header, array[channels, samples])``
        (``nf-window/1`` binary). ``physical=True`` applies each channel's scale/offset."""
        c = get_client(self._client)
        q: dict[str, Any] = {
            "start": start,
            "end": end,
            "level": level,
            "kind": kind,
            "format": "binary",
        }
        if channels:
            q["channels"] = ",".join(channels)
        _, _, blob = c.request(
            "GET",
            f"/v1/recordings/{self.id}/data",
            query=q,
            headers={"accept": "application/vnd.nf.window.v1"},
        )
        header, data = decode_window(blob)
        if physical:
            scale = np.asarray(header.get("scale", [1.0] * data.shape[0]), dtype=np.float64)[
                :, None
            ]
            offset = np.asarray(header.get("offset", [0.0] * data.shape[0]), dtype=np.float64)[
                :, None
            ]
            data = data.astype(np.float64) * scale + offset
        return header, data

    def to_mne(self, start: float = 0.0, end: float | None = None):
        """An ``mne.io.RawArray`` of ``[start, end)`` in physical units (volts for µV/mV/V)."""
        from .mne_interop import raw_from_window

        info = self.info()
        stop = end if end is not None else (info.get("duration_s") or 0.0) + 1.0
        header, data = self.read(start, stop, physical=True)
        return raw_from_window(header, data)


def decode_window(blob: bytes) -> tuple[dict[str, Any], np.ndarray]:
    """Decode ``NFW1 | u32 LE header length | JSON header | LE samples``."""
    if blob[:4] != WINDOW_MAGIC:
        raise ValueError("not an nf-window/1 binary response")
    (hlen,) = struct.unpack("<I", blob[4:8])
    header = json.loads(blob[8 : 8 + hlen])
    dt = np.dtype(header["dtype"]).newbyteorder("<")
    data = np.frombuffer(blob[8 + hlen :], dtype=dt).reshape(header["shape"])
    return header, data.astype(header["dtype"])
