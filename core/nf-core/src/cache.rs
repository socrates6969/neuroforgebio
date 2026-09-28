//! Content-addressed local chunk cache.
//!
//! An entry is stored under its chunk ID (hashing spec §5.2) as `<root>/<2 hex>/<64 hex>.nfchunk`
//! = canonical chunk header, `0x0A`, raw little-endian data. On every read the ID is recomputed;
//! a corrupted or tampered entry is deleted and reported as a miss, never returned. The cache is
//! bounded by `max_bytes`; the least recently used entries (file modification time, refreshed on
//! read) are evicted first.
//!
//! The cache holds signal data, so it lives in a per-user directory chosen by the caller (the
//! Python binding uses the platform's per-user cache dir); it is not a substitute for the
//! encrypted write-ahead buffer, which holds data that has not reached the server yet.

use std::fs;
use std::path::{Path, PathBuf};
use std::time::SystemTime;

use crate::ids::{self, Dtype, TAG_CHUNK};
use crate::sha256::{Sha256, to_hex};

#[derive(Debug)]
pub struct ChunkCache {
    root: PathBuf,
    max_bytes: u64,
}

/// A cached chunk (decoded, little-endian).
#[derive(Debug, Clone, PartialEq)]
pub struct CachedChunk {
    pub dtype: Dtype,
    pub shape: Vec<u64>,
    pub data: Vec<u8>,
}

fn io_other(msg: &str) -> std::io::Error {
    std::io::Error::other(msg.to_owned())
}

impl ChunkCache {
    pub fn open(root: impl Into<PathBuf>, max_bytes: u64) -> std::io::Result<Self> {
        let root = root.into();
        fs::create_dir_all(&root)?;
        Ok(Self { root, max_bytes })
    }

    fn path(&self, id: &str) -> std::io::Result<PathBuf> {
        let (kind, hex) = ids::parse_id(id).map_err(|_| io_other("not a chunk id"))?;
        if kind != "chunk" {
            return Err(io_other("not a chunk id"));
        }
        Ok(self.root.join(&hex[..2]).join(format!("{hex}.nfchunk")))
    }

    /// Store a chunk; returns its ID.
    pub fn put(&self, dtype: Dtype, shape: &[u64], data: &[u8]) -> std::io::Result<String> {
        let id = ids::chunk_id(dtype, shape, data).map_err(|e| io_other(&e.to_string()))?;
        let p = self.path(&id)?;
        if !p.exists() {
            fs::create_dir_all(p.parent().expect("parent"))?;
            let mut body = ids::chunk_header(dtype, shape).map_err(|e| io_other(&e.to_string()))?;
            body.push(b'\n');
            body.extend_from_slice(data);
            let tmp = p.with_extension("tmp");
            fs::write(&tmp, &body)?;
            fs::rename(&tmp, &p)?;
        }
        self.evict()?;
        Ok(id)
    }

    /// Fetch and verify a chunk. `Ok(None)` on a miss or a failed verification (entry removed).
    pub fn get(&self, id: &str) -> std::io::Result<Option<CachedChunk>> {
        let p = self.path(id)?;
        let body = match fs::read(&p) {
            Ok(b) => b,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(None),
            Err(e) => return Err(e),
        };
        let mut h = Sha256::new();
        h.update(TAG_CHUNK.as_bytes());
        h.update(&[0]);
        h.update(&body);
        let (_, want) = ids::parse_id(id).expect("checked");
        let parsed = (to_hex(&h.finalize()) == want)
            .then(|| parse_entry(&body))
            .flatten();
        match parsed {
            Some(c) => {
                if let Ok(f) = fs::File::options().append(true).open(&p) {
                    let _ = f.set_modified(SystemTime::now());
                }
                Ok(Some(c))
            }
            None => {
                let _ = fs::remove_file(&p);
                Ok(None)
            }
        }
    }

    fn entries(&self) -> std::io::Result<Vec<(PathBuf, u64, SystemTime)>> {
        let mut out = Vec::new();
        for d in fs::read_dir(&self.root)? {
            let d = d?;
            if !d.file_type()?.is_dir() {
                continue;
            }
            for f in fs::read_dir(d.path())? {
                let f = f?;
                if f.path().extension().and_then(|e| e.to_str()) == Some("nfchunk") {
                    let m = f.metadata()?;
                    out.push((
                        f.path(),
                        m.len(),
                        m.modified().unwrap_or(SystemTime::UNIX_EPOCH),
                    ));
                }
            }
        }
        Ok(out)
    }

    /// Total bytes currently cached.
    pub fn size(&self) -> std::io::Result<u64> {
        Ok(self.entries()?.iter().map(|e| e.1).sum())
    }

    fn evict(&self) -> std::io::Result<()> {
        let es = self.entries()?;
        self.evict_entries(es)
    }

    fn evict_entries(&self, mut es: Vec<(PathBuf, u64, SystemTime)>) -> std::io::Result<()> {
        let mut total: u64 = es.iter().map(|e| e.1).sum();
        if total <= self.max_bytes {
            return Ok(());
        }
        es.sort_by_key(|e| e.2);
        for (p, len, _) in es {
            if total <= self.max_bytes {
                break;
            }
            // another process sharing the directory may have evicted it already (M10)
            match fs::remove_file(&p) {
                Ok(()) => {}
                Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
                Err(e) => return Err(e),
            }
            total -= len;
        }
        Ok(())
    }

    pub fn root(&self) -> &Path {
        &self.root
    }
}

fn parse_entry(body: &[u8]) -> Option<CachedChunk> {
    let nl = body.iter().position(|b| *b == b'\n')?;
    let header: serde_json::Value = serde_json::from_slice(&body[..nl]).ok()?;
    let dtype = Dtype::parse(header["dtype"].as_str()?).ok()?;
    let shape: Vec<u64> = serde_json::from_value(header["shape"].clone()).ok()?;
    Some(CachedChunk {
        dtype,
        shape,
        data: body[nl + 1..].to_vec(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tmp(name: &str) -> PathBuf {
        let p = std::env::temp_dir().join(format!("nfcore-cache-{name}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&p);
        p
    }

    #[test]
    fn put_get_verify_evict() {
        let root = tmp("a");
        let c = ChunkCache::open(&root, 64).unwrap();
        let id = c
            .put(Dtype::Int16, &[2, 2], &[1, 0, 2, 0, 3, 0, 4, 0])
            .unwrap();
        assert_eq!(
            id,
            ids::chunk_id(Dtype::Int16, &[2, 2], &[1, 0, 2, 0, 3, 0, 4, 0]).unwrap()
        );
        let got = c.get(&id).unwrap().unwrap();
        assert_eq!(
            (got.dtype, got.shape.clone(), got.data.len()),
            (Dtype::Int16, vec![2, 2], 8)
        );
        // tamper -> miss + removed
        let p = c.path(&id).unwrap();
        let mut b = fs::read(&p).unwrap();
        *b.last_mut().unwrap() ^= 1;
        fs::write(&p, b).unwrap();
        assert!(c.get(&id).unwrap().is_none());
        assert!(!p.exists());
        // eviction keeps the total under max_bytes
        for i in 0..10u8 {
            c.put(Dtype::Uint8, &[16], &[i; 16]).unwrap();
        }
        assert!(c.size().unwrap() <= 64);
        assert!(c.get("blob:sha256:".to_owned().as_str()).is_err());
        let _ = fs::remove_dir_all(&root);
    }

    /// M10: an entry removed by a concurrent evictor (listed, then gone) must not fail eviction,
    /// and so must not fail the `put` whose write already succeeded.
    #[test]
    fn evict_tolerates_concurrently_removed_entries() {
        let root = tmp("m10");
        let c = ChunkCache::open(&root, 10_000).unwrap();
        for i in 0..3u8 {
            c.put(Dtype::Uint8, &[8], &[i; 8]).unwrap();
        }
        let listed = c.entries().unwrap();
        assert_eq!(listed.len(), 3);
        // another process evicts everything between our listing and our removals
        for (p, _, _) in &listed {
            fs::remove_file(p).unwrap();
        }
        // sizes inflated so eviction must try to remove every (already gone) entry
        let stale: Vec<_> = listed.into_iter().map(|(p, _, t)| (p, 10_000, t)).collect();
        c.evict_entries(stale).unwrap();
        // and a put that triggers eviction still succeeds
        let id = c.put(Dtype::Uint8, &[8], &[9; 8]).unwrap();
        assert!(c.get(&id).unwrap().is_some());
        let _ = fs::remove_dir_all(&root);
    }
}
