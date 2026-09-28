//! Encrypted write-ahead buffer for stream chunks (SEC-037, SEC-093). Byte-compatible with the
//! 2.7 prototype (`services/platform/edge_prototype/wal.py`):
//!
//! `<dir>/<seq:016>.nfwal` = `"NFWAL1" | nonce (12) | AES-256-GCM(key, nonce, record,
//! aad = "nf.wal.v1" 0x00 stream_id 0x00 <seq decimal>)`
//!
//! Files are written atomically (temp + rename, optional fsync of the file and of the directory).
//! A record that fails to authenticate is an error, never skipped. `ack(next_seq)` deletes every
//! record below `next_seq`.
//!
//! Sequence high-water mark (H4): before `ack` deletes records, `<dir>/next_seq.hwm` (decimal
//! ASCII) records the next seq this WAL would assign, so a drained WAL that is reopened resumes
//! numbering where it stopped instead of restarting at 0 (which would collide with seqs the server
//! already committed and let the next ack delete new, never-sent records). [`Wal::next_seq`] is
//! `max(hwm file, highest record + 1)`. The file is not secret; a tampered value can only make the
//! writer skip seqs (the server then rejects the gap), never delete a record.

use std::collections::BTreeSet;
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::{Condvar, Mutex};
use std::time::{Duration, Instant};

use aes_gcm::aead::{Aead, KeyInit, Payload};
use aes_gcm::{Aes256Gcm, Nonce};

use super::keystore::{KeyError, KeyProvider};

pub const MAGIC: &[u8] = b"NFWAL1";
pub const NONCE_LEN: usize = 12;
pub const AAD_TAG: &[u8] = crate::ids_v2::TAG_WAL.as_bytes();
/// File (inside the WAL directory) holding the persisted sequence high-water mark.
pub const HWM_FILE: &str = "next_seq.hwm";

#[derive(Debug)]
pub enum WalError {
    Io(std::io::Error),
    Key(KeyError),
    /// Record unreadable (tampered, wrong key, torn). Never carries record bytes.
    Corrupt(u64),
}

impl std::fmt::Display for WalError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Io(e) => write!(f, "WAL io: {e}"),
            Self::Key(e) => write!(f, "WAL key: {e}"),
            Self::Corrupt(s) => write!(f, "WAL record {s} does not authenticate"),
        }
    }
}
impl std::error::Error for WalError {}
impl From<std::io::Error> for WalError {
    fn from(e: std::io::Error) -> Self {
        Self::Io(e)
    }
}

fn parse_name(name: &str) -> Option<u64> {
    let stem = name.strip_suffix(".nfwal")?;
    (stem.len() == 16 && stem.bytes().all(|c| c.is_ascii_digit())).then(|| stem.parse().ok())?
}

/// Thread-safe: the acquisition thread appends, the sender thread reads and acks.
pub struct Wal {
    dir: PathBuf,
    stream_id: String,
    aead: Aes256Gcm,
    fsync: bool,
    seqs: Mutex<BTreeSet<u64>>,
    /// Next seq this WAL would assign: max(persisted hwm, highest record ever appended + 1).
    hwm: Mutex<Hwm>,
    new: Condvar,
}

#[derive(Debug, Clone, Copy)]
struct Hwm {
    next: u64,
    persisted: u64,
}

fn read_hwm(dir: &Path) -> Result<u64, WalError> {
    match fs::read_to_string(dir.join(HWM_FILE)) {
        Ok(t) => t.trim().parse().map_err(|_| {
            WalError::Io(std::io::Error::new(
                std::io::ErrorKind::InvalidData,
                format!("{HWM_FILE} is not a decimal seq"),
            ))
        }),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(0),
        Err(e) => Err(e.into()),
    }
}

impl Wal {
    pub fn open(
        dir: impl AsRef<Path>,
        stream_id: &str,
        keys: &dyn KeyProvider,
        fsync: bool,
    ) -> Result<Self, WalError> {
        let dir = dir.as_ref().to_path_buf();
        fs::create_dir_all(&dir)?;
        let key = keys.key().map_err(WalError::Key)?;
        let aead = Aes256Gcm::new_from_slice(key.as_ref()).expect("32-byte key");
        let mut seqs = BTreeSet::new();
        for e in fs::read_dir(&dir)? {
            let e = e?;
            if let Some(s) = e.file_name().to_str().and_then(parse_name) {
                seqs.insert(s);
            }
        }
        let persisted = read_hwm(&dir)?;
        let next = seqs.last().map_or(0, |s| s + 1).max(persisted);
        Ok(Self {
            dir,
            stream_id: stream_id.to_owned(),
            aead,
            fsync,
            seqs: Mutex::new(seqs),
            hwm: Mutex::new(Hwm { next, persisted }),
            new: Condvar::new(),
        })
    }

    pub fn dir(&self) -> &Path {
        &self.dir
    }

    fn path(&self, seq: u64) -> PathBuf {
        self.dir.join(format!("{seq:016}.nfwal"))
    }

    fn aad(&self, seq: u64) -> Vec<u8> {
        crate::ids_v2::wal_aad(&self.stream_id, seq)
    }

    pub fn append(&self, seq: u64, record: &[u8]) -> Result<(), WalError> {
        let mut nonce = [0u8; NONCE_LEN];
        getrandom::getrandom(&mut nonce)
            .map_err(|e| WalError::Io(std::io::Error::other(e.to_string())))?;
        let aad = self.aad(seq);
        let ct = self
            .aead
            .encrypt(
                Nonce::from_slice(&nonce),
                Payload {
                    msg: record,
                    aad: &aad,
                },
            )
            .map_err(|_| WalError::Corrupt(seq))?;
        let mut blob = Vec::with_capacity(MAGIC.len() + NONCE_LEN + ct.len());
        blob.extend_from_slice(MAGIC);
        blob.extend_from_slice(&nonce);
        blob.extend_from_slice(&ct);
        let p = self.path(seq);
        let tmp = p.with_extension("nfwal.tmp");
        {
            let mut f = fs::File::create(&tmp)?;
            f.write_all(&blob)?;
            if self.fsync {
                f.sync_all()?;
            }
        }
        fs::rename(&tmp, &p)?;
        if self.fsync {
            crate::durable::sync_dir(&self.dir)?;
        }
        {
            let mut h = self.hwm.lock().expect("wal hwm lock");
            h.next = h.next.max(seq.saturating_add(1));
        }
        let mut s = self.seqs.lock().expect("wal lock");
        s.insert(seq);
        self.new.notify_all();
        Ok(())
    }

    pub fn read(&self, seq: u64) -> Result<Vec<u8>, WalError> {
        let blob = fs::read(self.path(seq))?;
        if blob.len() < MAGIC.len() + NONCE_LEN + 16 || &blob[..MAGIC.len()] != MAGIC {
            return Err(WalError::Corrupt(seq));
        }
        let nonce = &blob[MAGIC.len()..MAGIC.len() + NONCE_LEN];
        let aad = self.aad(seq);
        self.aead
            .decrypt(
                Nonce::from_slice(nonce),
                Payload {
                    msg: &blob[MAGIC.len() + NONCE_LEN..],
                    aad: &aad,
                },
            )
            .map_err(|_| WalError::Corrupt(seq))
    }

    /// Pending seqs `>= from_seq`, ascending.
    pub fn pending(&self, from_seq: u64) -> Vec<u64> {
        self.seqs
            .lock()
            .expect("wal lock")
            .range(from_seq..)
            .copied()
            .collect()
    }

    pub fn max_seq(&self) -> Option<u64> {
        self.seqs.lock().expect("wal lock").last().copied()
    }

    /// The next seq a writer should use: past every record this WAL ever held, including records
    /// already acked and deleted (persisted high-water mark, H4).
    pub fn next_seq(&self) -> u64 {
        self.hwm.lock().expect("wal hwm lock").next
    }

    fn persist_hwm(&self) -> Result<(), WalError> {
        let mut h = self.hwm.lock().expect("wal hwm lock");
        if h.persisted >= h.next {
            return Ok(());
        }
        let p = self.dir.join(HWM_FILE);
        let tmp = self.dir.join(format!("{HWM_FILE}.tmp"));
        let text = h.next.to_string();
        if self.fsync {
            crate::durable::write_atomic(&p, &tmp, text.as_bytes())?;
        } else {
            fs::write(&tmp, text.as_bytes())?;
            fs::rename(&tmp, &p)?;
        }
        h.persisted = h.next;
        Ok(())
    }

    pub fn len(&self) -> usize {
        self.seqs.lock().expect("wal lock").len()
    }

    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// Block until record `seq` exists or `timeout` passes.
    pub fn wait_for(&self, seq: u64, timeout: Duration) -> bool {
        let deadline = Instant::now() + timeout;
        let mut s = self.seqs.lock().expect("wal lock");
        while !s.contains(&seq) {
            let now = Instant::now();
            if now >= deadline {
                return false;
            }
            s = self
                .new
                .wait_timeout(s, deadline - now)
                .expect("wal lock")
                .0;
        }
        true
    }

    /// Delete every record with `seq < next_seq`; returns how many were deleted. The sequence
    /// high-water mark is persisted first, so numbering survives the WAL becoming empty.
    pub fn ack(&self, next_seq: u64) -> Result<usize, WalError> {
        let done: Vec<u64> = self
            .seqs
            .lock()
            .expect("wal lock")
            .range(..next_seq)
            .copied()
            .collect();
        if !done.is_empty() {
            self.persist_hwm()?;
        }
        for s in &done {
            match fs::remove_file(self.path(*s)) {
                Ok(()) => {}
                Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
                Err(e) => return Err(e.into()),
            }
        }
        let mut set = self.seqs.lock().expect("wal lock");
        for s in &done {
            set.remove(s);
        }
        Ok(done.len())
    }
}
