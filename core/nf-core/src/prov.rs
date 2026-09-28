//! Offline provenance recorder: a local hash chain of provenance batches (hashing spec §5.3)
//! that works without a network and is synced to the platform later.
//!
//! Storage: `<dir>/<chain>.provchain.jsonl`, one canonical batch per line (append-only, fsynced),
//! and `<dir>/<chain>.synced` holding the highest seq the platform has acknowledged. On open the
//! whole chain is re-verified: an edited, reordered or truncated-in-the-middle file is an error,
//! never silently accepted.
//!
//! The local chain is its own chain (its `tenant` field is the chain name chosen by the caller,
//! e.g. `local:<device>`); the platform records the synced batches as imported entities with the
//! local batch IDs, so lineage stays checkable end to end. The platform endpoint for the upload is
//! designed, not built (see `docs/hive/inbox/m4-api.md`); [`ProvRecorder::sync`] takes the upload
//! function as a parameter.

use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use crate::cjson::{self, CanonError, Value};
use crate::ids;
use crate::model::{PROV_RELATIONS, ProvRecord};

#[derive(Debug)]
pub enum ProvError {
    Io(std::io::Error),
    Canon(CanonError),
    Invalid(String),
    Sync(String),
}

impl std::fmt::Display for ProvError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Io(e) => write!(f, "provenance io: {e}"),
            Self::Canon(e) => write!(f, "provenance chain: {e}"),
            Self::Invalid(m) => write!(f, "provenance: {m}"),
            Self::Sync(m) => write!(f, "provenance sync: {m}"),
        }
    }
}
impl std::error::Error for ProvError {}
impl From<std::io::Error> for ProvError {
    fn from(e: std::io::Error) -> Self {
        Self::Io(e)
    }
}
impl From<CanonError> for ProvError {
    fn from(e: CanonError) -> Self {
        Self::Canon(e)
    }
}

type Result<T> = std::result::Result<T, ProvError>;

/// `upload(canonical_batch_bytes, batch_id)` used by [`ProvRecorder::sync`].
pub type UploadFn<'a> = dyn FnMut(&[u8], &str) -> std::result::Result<(), String> + 'a;

/// UTC `YYYY-MM-DDTHH:MM:SS.sssZ` for a time since the Unix epoch (hashing spec §6).
pub fn format_timestamp_ms(t: SystemTime) -> String {
    let ms = t
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as i64)
        .unwrap_or(0);
    let (days, rem) = (ms.div_euclid(86_400_000), ms.rem_euclid(86_400_000));
    // civil-from-days (H. Hinnant), valid for the proleptic Gregorian calendar
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = yoe + era * 400 + i64::from(m <= 2);
    format!(
        "{y:04}-{m:02}-{d:02}T{:02}:{:02}:{:02}.{:03}Z",
        rem / 3_600_000,
        rem / 60_000 % 60,
        rem / 1000 % 60,
        rem % 1000
    )
}

/// One stored batch.
#[derive(Debug, Clone, PartialEq)]
pub struct Batch {
    pub seq: u64,
    pub id: String,
    pub value: Value,
}

#[derive(Debug)]
pub struct ProvRecorder {
    chain: String,
    log: PathBuf,
    synced_path: PathBuf,
    batches: Vec<Batch>,
    synced: Option<u64>,
}

fn validate_records(records: &[ProvRecord]) -> Result<()> {
    if records.is_empty() {
        return Err(ProvError::Invalid(
            "a batch needs at least one record".into(),
        ));
    }
    for r in records {
        if let ProvRecord::Edge { rel, .. } = r
            && !PROV_RELATIONS.contains(&rel.as_str())
        {
            return Err(ProvError::Invalid(format!("unknown relation {rel}")));
        }
    }
    Ok(())
}

impl ProvRecorder {
    /// Open (or create) the chain `chain` in `dir` and verify it.
    pub fn open(dir: impl AsRef<Path>, chain: &str) -> Result<Self> {
        if chain.is_empty()
            || !chain
                .chars()
                .all(|c| c.is_ascii_alphanumeric() || "-_.:".contains(c))
        {
            return Err(ProvError::Invalid("chain name: use [A-Za-z0-9-_.:]".into()));
        }
        let dir = dir.as_ref();
        fs::create_dir_all(dir)?;
        let safe = chain.replace(':', "_");
        let log = dir.join(format!("{safe}.provchain.jsonl"));
        let synced_path = dir.join(format!("{safe}.synced"));
        let mut values = Vec::new();
        if log.exists() {
            let text = fs::read_to_string(&log)?;
            for (i, line) in text.lines().enumerate() {
                if line.is_empty() {
                    continue;
                }
                let v = cjson::parse(line)
                    .map_err(|e| ProvError::Invalid(format!("line {}: {e}", i + 1)))?;
                if cjson::to_canonical(&v)? != line.as_bytes() {
                    return Err(ProvError::Invalid(format!("line {}: not canonical", i + 1)));
                }
                if v.get("tenant").and_then(Value::as_str) != Some(chain) {
                    return Err(ProvError::Invalid(format!(
                        "line {}: belongs to another chain",
                        i + 1
                    )));
                }
                values.push(v);
            }
        }
        let ids = ids::verify_chain(&values)?;
        let batches = values
            .into_iter()
            .zip(ids)
            .enumerate()
            .map(|(i, (value, id))| Batch {
                seq: i as u64,
                id,
                value,
            })
            .collect::<Vec<_>>();
        let synced = match fs::read_to_string(&synced_path) {
            Ok(s) => {
                let n: u64 = s
                    .trim()
                    .parse()
                    .map_err(|_| ProvError::Invalid("bad synced marker".into()))?;
                if n as usize >= batches.len() {
                    return Err(ProvError::Invalid(
                        "synced marker beyond the chain head".into(),
                    ));
                }
                Some(n)
            }
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => None,
            Err(e) => return Err(e.into()),
        };
        Ok(Self {
            chain: chain.to_owned(),
            log,
            synced_path,
            batches,
            synced,
        })
    }

    pub fn chain(&self) -> &str {
        &self.chain
    }
    pub fn len(&self) -> usize {
        self.batches.len()
    }
    pub fn is_empty(&self) -> bool {
        self.batches.is_empty()
    }
    pub fn head(&self) -> Option<&Batch> {
        self.batches.last()
    }
    pub fn batches(&self) -> &[Batch] {
        &self.batches
    }

    /// Append one batch of records now.
    pub fn record(&mut self, records: &[ProvRecord]) -> Result<Batch> {
        self.record_at(records, SystemTime::now())
    }

    /// Append one batch with an explicit creation time (tests, replays).
    pub fn record_at(&mut self, records: &[ProvRecord], at: SystemTime) -> Result<Batch> {
        validate_records(records)?;
        let seq = self.batches.len() as u64;
        let prev = self
            .head()
            .map(|b| Value::String(b.id.clone()))
            .unwrap_or(Value::Null);
        let recs = records
            .iter()
            .map(|r| {
                let j = serde_json::to_value(r).map_err(|e| ProvError::Invalid(e.to_string()))?;
                Ok(cjson::from_serde(&j)?)
            })
            .collect::<Result<Vec<_>>>()?;
        let value = Value::obj([
            ("schema", Value::str(ids::PROVB_SCHEMA)),
            ("tenant", Value::str(self.chain.clone())),
            ("seq", Value::Int(seq as i64)),
            ("prev", prev),
            ("created_at", Value::str(format_timestamp_ms(at))),
            ("records", Value::Array(recs)),
        ]);
        let id = ids::prov_batch_id(&value)?;
        let mut line = cjson::to_canonical(&value)?;
        line.push(b'\n');
        let mut f = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.log)?;
        f.write_all(&line)?;
        f.sync_all()?;
        let b = Batch { seq, id, value };
        self.batches.push(b.clone());
        Ok(b)
    }

    /// Batches the platform has not acknowledged yet, in order.
    pub fn pending(&self) -> &[Batch] {
        let from = self.synced.map_or(0, |s| s as usize + 1);
        &self.batches[from..]
    }

    pub fn synced_seq(&self) -> Option<u64> {
        self.synced
    }

    pub fn mark_synced(&mut self, seq: u64) -> Result<()> {
        if seq as usize >= self.batches.len() {
            return Err(ProvError::Invalid("seq beyond the chain head".into()));
        }
        if self.synced.is_some_and(|s| s >= seq) {
            return Ok(());
        }
        let tmp = self.synced_path.with_extension("tmp");
        crate::durable::write_atomic(&self.synced_path, &tmp, seq.to_string().as_bytes())?;
        self.synced = Some(seq);
        Ok(())
    }

    /// Upload pending batches in order with `upload(canonical_bytes, id)`; stops at the first
    /// failure (already uploaded batches stay marked). Returns how many were synced.
    pub fn sync(&mut self, upload: &mut UploadFn<'_>) -> Result<usize> {
        let pending: Vec<Batch> = self.pending().to_vec();
        let mut n = 0;
        for b in pending {
            let bytes = cjson::to_canonical(&b.value)?;
            upload(&bytes, &b.id).map_err(ProvError::Sync)?;
            self.mark_synced(b.seq)?;
            n += 1;
        }
        Ok(n)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Duration;

    fn dir(name: &str) -> PathBuf {
        let p = std::env::temp_dir().join(format!("nfcore-prov-{name}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&p);
        p
    }

    #[test]
    fn timestamps() {
        assert_eq!(format_timestamp_ms(UNIX_EPOCH), "1970-01-01T00:00:00.000Z");
        let t = UNIX_EPOCH + Duration::from_millis(1_790_424_001_234);
        assert_eq!(format_timestamp_ms(t), "2026-09-26T12:00:01.234Z");
        let leap = UNIX_EPOCH + Duration::from_secs(951_782_400); // 2000-02-29
        assert_eq!(format_timestamp_ms(leap), "2000-02-29T00:00:00.000Z");
    }

    #[test]
    fn chain_append_reopen_tamper_sync() {
        let d = dir("a");
        let recs = [
            ProvRecord::Entity {
                id: "e1".into(),
                label: "raw".into(),
                content: Some(ids::blob_id(b"x")),
            },
            ProvRecord::Activity {
                id: "a1".into(),
                label: "ingest".into(),
            },
            ProvRecord::Edge {
                rel: "wasGeneratedBy".into(),
                from: "e1".into(),
                to: "a1".into(),
            },
        ];
        let mut r = ProvRecorder::open(&d, "local:dev-1").unwrap();
        let b0 = r.record(&recs).unwrap();
        let b1 = r.record(&recs[1..2]).unwrap();
        assert_eq!(b1.value.get("prev"), Some(&Value::String(b0.id.clone())));
        assert!(r.record(&[]).is_err());
        let bad = [ProvRecord::Edge {
            rel: "controls".into(),
            from: "a".into(),
            to: "b".into(),
        }];
        assert!(r.record(&bad).is_err());
        drop(r);

        let mut r = ProvRecorder::open(&d, "local:dev-1").unwrap();
        assert_eq!(r.len(), 2);
        assert_eq!(r.pending().len(), 2);
        let mut sent = vec![];
        let n = r
            .sync(&mut |bytes, id| {
                sent.push((bytes.to_vec(), id.to_owned()));
                if sent.len() == 2 {
                    Err("offline".into())
                } else {
                    Ok(())
                }
            })
            .unwrap_err();
        assert!(matches!(n, ProvError::Sync(_)));
        assert_eq!(r.synced_seq(), Some(0));
        assert_eq!(sent[0].1, b0.id);
        drop(r);
        assert_eq!(
            ProvRecorder::open(&d, "local:dev-1")
                .unwrap()
                .pending()
                .len(),
            1
        );

        // editing an earlier batch breaks the chain on the next open
        let log = d.join("local_dev-1.provchain.jsonl");
        let text = fs::read_to_string(&log)
            .unwrap()
            .replacen("ingest", "ingesT", 1);
        fs::write(&log, text).unwrap();
        assert!(ProvRecorder::open(&d, "local:dev-1").is_err());
        let _ = fs::remove_dir_all(&d);
    }
}
