"""Safe extraction of uploaded zip archives (BIDS / BrainVision bundles) — SEC-064.

Refuses path traversal (absolute paths, drive letters, ``..``, backslash tricks), symlinks and
special files, encrypted entries, duplicate names, too many entries, and zip bombs: the declared
sizes are checked first (total, per entry, compression ratio), and the bytes actually written are
counted again during extraction, so a lying header cannot exceed the limits either.
Runs in the ingest worker only (never in the API process, SEC-060).
"""

from __future__ import annotations

import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from nf_platform.ingest.convert.model import ConversionError


class UnsafeArchiveError(ConversionError):
    """The archive violates a safety limit; nothing from it is used."""


@dataclass(frozen=True)
class ArchiveLimits:
    max_entries: int = 10_000
    max_total_bytes: int = 8 * 1024**3
    max_entry_bytes: int = 4 * 1024**3
    max_ratio: float = 200.0
    max_depth: int = 16
    max_name_len: int = 255


DEFAULT_ARCHIVE_LIMITS = ArchiveLimits()
_BLOCK = 1024 * 1024


def _safe_name(raw: str, limits: ArchiveLimits) -> PurePosixPath | None:
    """Return the relative path of a file entry, None for a directory entry; raise if unsafe."""
    if "\x00" in raw or len(raw) > 4096:
        raise UnsafeArchiveError("entry name is invalid")
    name = raw.replace("\\", "/")
    if name.startswith("/") or (len(name) > 1 and name[1] == ":"):
        raise UnsafeArchiveError("absolute path in archive")
    parts = [p for p in name.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise UnsafeArchiveError("path traversal in archive")
    if len(parts) > limits.max_depth or any(len(p) > limits.max_name_len for p in parts):
        raise UnsafeArchiveError("archive path too deep or too long")
    if name.endswith("/"):
        return None
    if not parts:
        raise UnsafeArchiveError("empty entry name")
    return PurePosixPath(*parts)


def _is_link_or_special(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0xFFFF
    kind = stat.S_IFMT(mode)
    if kind == 0:  # no file-type bits (DOS-made archives, Python's writestr): a plain entry
        return False
    return kind not in (stat.S_IFREG, stat.S_IFDIR)


def safe_extract(
    zip_path: str | Path, dest: str | Path, limits: ArchiveLimits = DEFAULT_ARCHIVE_LIMITS
) -> list[Path]:
    """Extract every regular file of ``zip_path`` under ``dest``; returns the written paths."""
    dest = Path(dest).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    try:
        zf = zipfile.ZipFile(zip_path)
    except (zipfile.BadZipFile, OSError) as e:
        raise UnsafeArchiveError("not a valid zip archive") from e
    with zf:
        infos = zf.infolist()
        if len(infos) > limits.max_entries:
            raise UnsafeArchiveError("too many entries in archive")
        plan: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
        seen: set[str] = set()
        declared = 0
        for info in infos:
            rel = _safe_name(info.filename, limits)
            if info.flag_bits & 0x1:
                raise UnsafeArchiveError("encrypted archive entries are not accepted")
            if _is_link_or_special(info):
                raise UnsafeArchiveError("symlinks and special files are not accepted")
            if rel is None:
                continue
            key = rel.as_posix().lower()
            if key in seen:
                raise UnsafeArchiveError("duplicate entry name in archive")
            seen.add(key)
            if info.file_size > limits.max_entry_bytes:
                raise UnsafeArchiveError("archive entry too large")
            declared += info.file_size
            if declared > limits.max_total_bytes:
                raise UnsafeArchiveError("archive expands beyond the size limit")
            if info.file_size > 1024 * 1024 and info.file_size > limits.max_ratio * max(
                1, info.compress_size
            ):
                raise UnsafeArchiveError("archive compression ratio too high (zip bomb)")
            plan.append((info, rel))
        written: list[Path] = []
        total = 0
        for info, rel in plan:
            out = (dest / Path(*rel.parts)).resolve()
            if dest not in out.parents:
                raise UnsafeArchiveError("path traversal in archive")
            out.parent.mkdir(parents=True, exist_ok=True)
            n = 0
            with zf.open(info) as src, out.open("wb") as fh:
                while True:
                    block = src.read(_BLOCK)
                    if not block:
                        break
                    n += len(block)
                    total += len(block)
                    if n > info.file_size or n > limits.max_entry_bytes:
                        raise UnsafeArchiveError("archive entry larger than declared")
                    if total > limits.max_total_bytes:
                        raise UnsafeArchiveError("archive expands beyond the size limit")
                    fh.write(block)
            written.append(out)
        return written
