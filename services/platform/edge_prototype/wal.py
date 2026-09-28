"""Encrypted local write-ahead log for stream chunks (BUILD-GUIDE 2.7; SEC-037, SEC-093).

One file per chunk: ``<dir>/<seq:016d>.nfwal`` = ``"NFWAL1" | nonce (12) | AES-256-GCM(key,
nonce, record, aad = "nf.wal.v1" 0x00 stream_id 0x00 seq)``
where ``record`` is the serialized, already-signed ``neuroforge.ingest.v1.Chunk``. Files are written
atomically (temp + rename) so a crash never leaves a torn record; a record that fails to decrypt is
reported, never silently skipped. ``ack(next_seq)`` deletes every record below ``next_seq`` (the
server has stored them durably).

Key: 32 random bytes from a ``KeyProvider``. On Windows ``DpapiKeyProvider`` keeps the key sealed
with DPAPI (user scope) next to the WAL, so the plaintext key never touches the disk (SEC-037 "key
from the OS keystore"). macOS Keychain / libsecret are nf-core work (4.2); elsewhere the prototype
only offers ``EphemeralKeyProvider`` (key in memory: records cannot be recovered after a restart).
"""

from __future__ import annotations

import os
import re
import sys
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"NFWAL1"
NONCE_LEN = 12
AAD_TAG = b"nf.wal.v1"
_NAME = re.compile(r"^(\d{16})\.nfwal$")


class WalError(Exception):
    """A WAL record is unreadable (tampered, wrong key, torn). Never contains record bytes."""


class KeyProvider(Protocol):
    def key(self) -> bytes: ...


class EphemeralKeyProvider:
    """A random key held in memory only (tests; platforms without a supported keystore)."""

    def __init__(self) -> None:
        self._key = AESGCM.generate_key(bit_length=256)

    def key(self) -> bytes:
        return self._key


class DpapiKeyProvider:
    """Windows DPAPI (CryptProtectData, current-user scope): the WAL key is stored only in its
    DPAPI-sealed form at ``path``; created on first use."""

    def __init__(self, path: str | Path) -> None:
        if sys.platform != "win32":
            raise OSError("DPAPI is only available on Windows")
        self.path = Path(path)
        self._key: bytes | None = None

    def key(self) -> bytes:
        if self._key is None:
            if self.path.exists():
                self._key = _dpapi(self.path.read_bytes(), protect=False)
            else:
                k = AESGCM.generate_key(bit_length=256)
                self.path.parent.mkdir(parents=True, exist_ok=True)
                _atomic_write(self.path, _dpapi(k, protect=True), fsync=True)
                self._key = k
            if len(self._key) != 32:
                raise WalError("WAL key has the wrong length")
        return self._key


def _dpapi(data: bytes, *, protect: bool) -> bytes:  # pragma: no cover - Windows only
    import ctypes  # noqa: PLC0415
    from ctypes import wintypes  # noqa: PLC0415

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    buf = ctypes.create_string_buffer(data, len(data))
    blob_in = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = Blob()
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    ok = fn(
        ctypes.byref(blob_in),
        None,
        None,
        None,
        None,
        0x1,  # CRYPTPROTECT_UI_FORBIDDEN
        ctypes.byref(blob_out),
    )
    if not ok:
        raise WalError("DPAPI call failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(blob_out.pbData)


def _atomic_write(path: Path, data: bytes, *, fsync: bool) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("wb") as fh:
        fh.write(data)
        if fsync:
            fh.flush()
            os.fsync(fh.fileno())
    os.replace(tmp, path)


class WriteAheadLog:
    """Thread-safe: the acquisition thread appends, the sender thread reads and acks."""

    def __init__(
        self, directory: str | Path, stream_id: str, keys: KeyProvider, *, fsync: bool = True
    ) -> None:
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.stream_id = stream_id
        self._aead = AESGCM(keys.key())
        self._fsync = fsync
        self._lock = threading.Lock()
        self._seqs: set[int] = set(self._scan())
        self._new = threading.Condition(self._lock)

    def _scan(self) -> Iterator[int]:
        for p in self.dir.iterdir():
            m = _NAME.match(p.name)
            if m:
                yield int(m.group(1))

    def _path(self, seq: int) -> Path:
        return self.dir / f"{seq:016d}.nfwal"

    def _aad(self, seq: int) -> bytes:
        return AAD_TAG + b"\x00" + self.stream_id.encode() + b"\x00" + str(seq).encode()

    def append(self, seq: int, record: bytes) -> None:
        nonce = os.urandom(NONCE_LEN)
        blob = MAGIC + nonce + self._aead.encrypt(nonce, record, self._aad(seq))
        _atomic_write(self._path(seq), blob, fsync=self._fsync)
        with self._lock:
            self._seqs.add(seq)
            self._new.notify_all()

    def read(self, seq: int) -> bytes:
        blob = self._path(seq).read_bytes()
        if blob[: len(MAGIC)] != MAGIC or len(blob) < len(MAGIC) + NONCE_LEN + 16:
            raise WalError(f"WAL record {seq} is malformed")
        nonce = blob[len(MAGIC) : len(MAGIC) + NONCE_LEN]
        try:
            return self._aead.decrypt(nonce, blob[len(MAGIC) + NONCE_LEN :], self._aad(seq))
        except InvalidTag as e:
            raise WalError(f"WAL record {seq} does not authenticate") from e

    def pending(self, from_seq: int = 0) -> list[int]:
        with self._lock:
            return sorted(s for s in self._seqs if s >= from_seq)

    def max_seq(self) -> int | None:
        with self._lock:
            return max(self._seqs) if self._seqs else None

    def __len__(self) -> int:
        with self._lock:
            return len(self._seqs)

    def wait_for(self, seq: int, timeout: float) -> bool:
        """Block until record ``seq`` exists (or timeout)."""
        with self._new:
            return self._new.wait_for(lambda: seq in self._seqs, timeout)

    def ack(self, next_seq: int) -> int:
        """Delete every record with seq < next_seq. Returns how many were deleted."""
        with self._lock:
            done = sorted(s for s in self._seqs if s < next_seq)
        for s in done:
            self._path(s).unlink(missing_ok=True)
        with self._lock:
            self._seqs.difference_update(done)
        return len(done)
