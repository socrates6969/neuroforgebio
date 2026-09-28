"""SEC-064: zip uploads (BIDS / BrainVision bundles) are unpacked with traversal and zip-bomb
limits; nothing outside the destination is ever written."""

from __future__ import annotations

import stat
import zipfile
from pathlib import Path

import pytest
from nf_platform.ingest.uploads.archive import ArchiveLimits, UnsafeArchiveError, safe_extract


def _zip(path: Path, entries: list[tuple[str | zipfile.ZipInfo, bytes]], **kw) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, **kw) as zf:
        for name, data in entries:
            zf.writestr(name, data)
    return path


def test_regular_bundle_extracts(tmp_path):
    z = _zip(
        tmp_path / "ok.zip",
        [("ds/dataset_description.json", b"{}"), ("ds/sub-01/a.edf", b"x" * 10)],
    )
    out = safe_extract(z, tmp_path / "out")
    assert sorted(p.relative_to(tmp_path / "out").as_posix() for p in out) == [
        "ds/dataset_description.json",
        "ds/sub-01/a.edf",
    ]


@pytest.mark.parametrize(
    "name",
    [
        "../evil.txt",
        "a/../../evil.txt",
        "/etc/evil.txt",
        "C:/evil.txt",
        "..\\evil.txt",
        "a\\..\\..\\e",
    ],
)
def test_path_traversal_is_refused(tmp_path, name):
    z = _zip(tmp_path / "t.zip", [(name, b"x")])
    with pytest.raises(UnsafeArchiveError):
        safe_extract(z, tmp_path / "out")
    assert not (tmp_path / "evil.txt").exists()


def test_symlink_entry_is_refused(tmp_path):
    info = zipfile.ZipInfo("link")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    z = _zip(tmp_path / "l.zip", [(info, b"/etc/passwd")])
    with pytest.raises(UnsafeArchiveError, match="symlink"):
        safe_extract(z, tmp_path / "out")


def test_zip_bomb_ratio_and_total_size(tmp_path):
    z = _zip(tmp_path / "b.zip", [("zeros.bin", b"\x00" * (8 * 1024 * 1024))])
    with pytest.raises(UnsafeArchiveError, match="ratio"):
        safe_extract(z, tmp_path / "out")
    z2 = _zip(tmp_path / "c.zip", [(f"f{i}", bytes(range(256)) * 8) for i in range(4)])
    with pytest.raises(UnsafeArchiveError, match="size limit"):
        safe_extract(z2, tmp_path / "out", ArchiveLimits(max_total_bytes=4096))
    with pytest.raises(UnsafeArchiveError, match="too large"):
        safe_extract(z2, tmp_path / "out", ArchiveLimits(max_entry_bytes=1000))


def test_entry_count_duplicates_and_garbage(tmp_path):
    z = _zip(tmp_path / "n.zip", [(f"f{i}", b"x") for i in range(20)])
    with pytest.raises(UnsafeArchiveError, match="too many"):
        safe_extract(z, tmp_path / "out", ArchiveLimits(max_entries=10))
    z = _zip(tmp_path / "d.zip", [("A.edf", b"1"), ("a.edf", b"2")])
    with pytest.raises(UnsafeArchiveError, match="duplicate"):
        safe_extract(z, tmp_path / "out")
    junk = tmp_path / "junk.zip"
    junk.write_bytes(b"PK\x03\x04 not really a zip")
    with pytest.raises(UnsafeArchiveError):
        safe_extract(junk, tmp_path / "out")


def test_encrypted_entries_are_refused(tmp_path):
    z = _zip(tmp_path / "e.zip", [("a.edf", b"x")])
    raw = bytearray(z.read_bytes())
    # set the "encrypted" general-purpose flag bit in the local and central headers
    for sig in (b"PK\x03\x04", b"PK\x01\x02"):
        i = raw.find(sig)
        off = i + (6 if sig == b"PK\x03\x04" else 8)
        raw[off] |= 0x1
    z.write_bytes(bytes(raw))
    with pytest.raises(UnsafeArchiveError, match="encrypted"):
        safe_extract(z, tmp_path / "out")
