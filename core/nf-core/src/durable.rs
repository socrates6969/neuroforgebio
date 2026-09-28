//! Crash-durability helpers for the temp-file + rename pattern (M8).
//!
//! `fsync(file)` makes the bytes durable, but the directory entry created by `rename` lives in
//! the parent directory, which needs its own sync or a power loss can undo the rename (Linux
//! ext4/xfs, macOS APFS). [`sync_dir`] does that on Unix.
//!
//! Windows: std cannot open a directory for flushing (it needs `FILE_FLAG_BACKUP_SEMANTICS` and
//! `FlushFileBuffers` on a directory handle is not supported for regular callers), and NTFS
//! journals the metadata of a rename itself, so [`sync_dir`] is a documented best-effort no-op
//! there.

use std::path::Path;

/// Flush the directory `dir` so entries created/renamed in it survive a crash (Unix); no-op on
/// other platforms (see the module docs).
#[cfg(unix)]
pub fn sync_dir(dir: &Path) -> std::io::Result<()> {
    std::fs::File::open(dir)?.sync_all()
}

/// Flush the directory `dir` so entries created/renamed in it survive a crash (Unix); no-op on
/// other platforms (see the module docs).
#[cfg(not(unix))]
pub fn sync_dir(_dir: &Path) -> std::io::Result<()> {
    Ok(())
}

/// Sync the parent directory of `path` (after renaming something to `path`).
pub fn sync_parent(path: &Path) -> std::io::Result<()> {
    match path.parent() {
        Some(d) if !d.as_os_str().is_empty() => sync_dir(d),
        _ => sync_dir(Path::new(".")),
    }
}

/// Write `bytes` to `path` atomically: temp file, fsync, rename, fsync of the parent directory.
pub fn write_atomic(path: &Path, tmp: &Path, bytes: &[u8]) -> std::io::Result<()> {
    use std::io::Write;
    {
        let mut f = std::fs::File::create(tmp)?;
        f.write_all(bytes)?;
        f.sync_all()?;
    }
    std::fs::rename(tmp, path)?;
    sync_parent(path)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn write_atomic_replaces_and_syncs() {
        let d = std::env::temp_dir().join(format!("nfcore-durable-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&d);
        std::fs::create_dir_all(&d).unwrap();
        let p = d.join("f");
        write_atomic(&p, &d.join("f.tmp"), b"one").unwrap();
        write_atomic(&p, &d.join("f.tmp"), b"two").unwrap();
        assert_eq!(std::fs::read(&p).unwrap(), b"two");
        assert!(!d.join("f.tmp").exists());
        // the directory sync itself succeeds (real on Unix, a no-op elsewhere)
        sync_dir(&d).unwrap();
        sync_parent(&p).unwrap();
        let _ = std::fs::remove_dir_all(&d);
    }
}
