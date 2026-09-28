"""Where a recording's canonical signal lives, and window reads for the data endpoint (2.4).

``recording.zarr_ref`` = ``zarr:<prefix>#<group>``: the Zarr hierarchy under ``<prefix>`` in the
``zarr`` bucket, sealed with the subject's DEK (``EncryptedZarrStore``), group ``<group>``.
Prefixes: ``t/<tenant>/s/<subject>/u/<upload>`` (file uploads) and
``t/<tenant>/s/<subject>/r/<recording>`` (streams).

Window response (``GET /v1/recordings/{id}/data``), format ``nf-window/1``:

- Header fields (JSON object): ``channels``, ``units``, ``scale``, ``offset`` (physical =
  stored * scale + offset), ``dtype``, ``shape`` = [n_channels, n_samples], ``order`` "C",
  ``byte_order`` "little", ``level``, ``decimation``, ``kind`` ("samples" at level 0, else the
  pyramid reduction mean/min/max), ``sfreq`` (of that level), ``start_index`` and ``start_s``
  (time of the first returned sample; sample i of level k starts at i * decimation / sfreq_0),
  ``chunk_id`` (hashing spec v1 §5.2 over the returned array, so a client can verify it; also
  sent as the ``X-NF-Chunk-Id`` response header).
- ``format=json`` (default): the header fields plus ``data`` (nested list, channel-major).
  Limited to ``window_json_max_values`` values.
- ``format=binary``: media type ``application/vnd.nf.window.v1``, bytes
  ``"NFW1" | u32 LE header length | header (UTF-8 JSON) | data`` (little-endian, C order, shape
  as in the header). Limited to ``window_max_values`` values.

Windows are half-open ``[start, end)`` in seconds from the first sample. A request over the limit
is refused with 422 ``window-too-large`` before any chunk is decrypted.
"""

from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass
from typing import Any

import numpy as np

from nf_platform.ingest.errors import IngestError
from nf_platform.ingest.stream.protocol import chunk_id_bytes, samples_to_bytes
from nf_platform.signals.encrypted_store import EncryptedZarrStore
from nf_platform.signals.zarr_store import SignalError, open_recording, read_window
from nf_platform.storage.keyring import SubjectKeyUnavailable
from nf_platform.storage.runtime import Storage

REF_SCHEME = "zarr:"
WINDOW_MAGIC = b"NFW1"
WINDOW_MEDIA_TYPE = "application/vnd.nf.window.v1"


def make_ref(prefix: str, group: str) -> str:
    return f"{REF_SCHEME}{prefix}#{group}"


def parse_ref(ref: str) -> tuple[str, str]:
    if not ref.startswith(REF_SCHEME) or "#" not in ref:
        raise ValueError("not a zarr ref")
    prefix, group = ref[len(REF_SCHEME) :].split("#", 1)
    if not prefix or not group:
        raise ValueError("not a zarr ref")
    return prefix, group


def upload_prefix(tenant_id: str, subject_id: str, upload_id: str) -> str:
    return f"t/{tenant_id}/s/{subject_id}/u/{upload_id}"


def stream_prefix(tenant_id: str, subject_id: str, recording_id: str) -> str:
    return f"t/{tenant_id}/s/{subject_id}/r/{recording_id}"


def open_store(
    storage: Storage, tenant_id: str, subject_id: str, prefix: str, *, read_only: bool = False
) -> EncryptedZarrStore:
    return EncryptedZarrStore(
        storage.objects,
        storage.keyring,
        str(tenant_id),
        str(subject_id),
        prefix,
        read_only=read_only,
    )


@dataclass(frozen=True)
class Window:
    data: np.ndarray  # (n_channels, n_samples), stored dtype (level 0) or pyramid dtype
    header: dict[str, Any]

    @property
    def n_values(self) -> int:
        return int(self.data.size)


def _parse_channels(spec: str | None, names: list[str]) -> list[int] | None:
    if spec is None or spec == "":
        return None
    out: list[int] = []
    for tok in spec.split(","):
        tok = tok.strip()
        if tok in names:
            out.append(names.index(tok))
        elif tok.isdigit() and int(tok) < len(names):
            out.append(int(tok))
        else:
            raise IngestError(422, "invalid-request", "Invalid request", "unknown channel")
    if len(out) != len(set(out)):
        raise IngestError(422, "invalid-request", "Invalid request", "duplicate channel")
    return out


def read_window_for(
    storage: Storage,
    tenant_id: str,
    subject_id: str,
    ref: str,
    *,
    start_s: float,
    end_s: float,
    channels: str | None,
    level: int,
    kind: str,
    max_values: int,
    max_json_values: int | None = None,
    fmt: str = "binary",
) -> Window:
    """Validate the request against the layout, enforce the size limit, then decrypt + read."""
    prefix, group = parse_ref(ref)
    store = open_store(storage, tenant_id, subject_id, prefix, read_only=True)
    try:
        info = open_recording(store, group)
    except SignalError as e:
        raise IngestError(404, "not-found", "Not Found", "recording data not found") from e
    except SubjectKeyUnavailable as e:  # crypto-shredded (2.3): the data is gone for good
        raise IngestError(410, "gone", "Gone", "the subject's data has been erased") from e
    sig = info.signal
    levels = sig["pyramid"]["levels"]
    if not 0 <= level < len(levels):
        raise IngestError(
            422, "invalid-request", "Invalid request", f"level must be in 0..{len(levels) - 1}"
        )
    if not (math.isfinite(start_s) and math.isfinite(end_s)) or not 0 <= start_s < end_s:
        raise IngestError(422, "invalid-request", "Invalid request", "need 0 <= start < end")
    names = list(sig["ch_names"])
    idx = _parse_channels(channels, names)
    lv = levels[level]
    sf_k, n_k = float(lv["sfreq"]), int(lv["n_samples"])
    i0 = min(n_k, max(0, math.ceil(start_s * sf_k - 1e-9)))
    i1 = min(n_k, max(i0, math.ceil(end_s * sf_k - 1e-9)))
    n_ch = len(names) if idx is None else len(idx)
    if fmt == "json" and max_json_values is not None:
        max_values = min(max_values, max_json_values)
    if (i1 - i0) * n_ch > max_values:
        raise IngestError(
            422,
            "window-too-large",
            "Window too large",
            f"at most {max_values} values (samples x channels) per request; use a pyramid level "
            "or a shorter window",
            extra={"max_values": max_values},
        )
    try:
        data = read_window(store, group, start_s, end_s, idx, level, kind=kind)  # type: ignore[arg-type]
    except SignalError as e:
        raise IngestError(422, "invalid-request", "Invalid request", str(e)) from e
    except SubjectKeyUnavailable as e:
        raise IngestError(410, "gone", "Gone", "the subject's data has been erased") from e
    sel = list(range(len(names))) if idx is None else idx
    header = {
        "byte_order": "little",
        "channels": [names[i] for i in sel],
        "decimation": int(lv["decimation"]),
        "dtype": data.dtype.name,
        "kind": "samples" if level == 0 else kind,
        "level": level,
        "offset": [float(sig["offset"][i]) for i in sel],
        "order": "C",
        "physical": "stored * scale + offset",
        "scale": [float(sig["scale"][i]) for i in sel],
        "sfreq": sf_k,
        "shape": [int(data.shape[0]), int(data.shape[1])],
        "start_index": int(i0),
        "start_s": i0 / sf_k,
        "units": [sig["units"][i] for i in sel],
    }
    header["chunk_id"] = chunk_id_bytes(
        data.dtype.name, header["shape"], samples_to_bytes(data, data.dtype.name)
    )
    return Window(data=data, header=header)


def encode_binary(w: Window) -> bytes:
    """``NFW1`` | u32 LE header length | header (UTF-8 JSON) | data (LE, C order)."""
    head = json.dumps(w.header, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return (
        WINDOW_MAGIC
        + struct.pack("<I", len(head))
        + head
        + samples_to_bytes(w.data, w.data.dtype.name)
    )


def decode_binary(blob: bytes) -> tuple[dict[str, Any], np.ndarray]:
    if blob[:4] != WINDOW_MAGIC:
        raise ValueError("not an NFW1 window")
    (hlen,) = struct.unpack("<I", blob[4:8])
    header = json.loads(blob[8 : 8 + hlen])
    dt = np.dtype(header["dtype"]).newbyteorder("<")
    data = np.frombuffer(blob[8 + hlen :], dtype=dt).reshape(header["shape"])
    return header, data.astype(header["dtype"])


def to_json(w: Window) -> dict[str, Any]:
    return {**w.header, "data": w.data.tolist()}
