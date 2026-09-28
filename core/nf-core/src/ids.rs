//! Content IDs (`docs/spec/hashing.md` §4-§5): `<kind>:sha256:<64 hex>`.

use std::io::Read;

use crate::cjson::{self, CanonError, Value};
use crate::sha256::{Sha256, sha256, to_hex};

pub const TAG_PIPELINE_VERSION: &str = "nf.pipeline-version.v1";
pub const TAG_CHUNK: &str = "nf.chunk.v1";
pub const TAG_PROV_BATCH: &str = "nf.prov-batch.v1";
pub const PV_SCHEMA: &str = "nf.pipeline-version/v1";
pub const PROVB_SCHEMA: &str = "nf.prov-batch/v1";

type Result<T> = std::result::Result<T, CanonError>;

fn invalid(msg: impl Into<String>) -> CanonError {
    CanonError::Invalid(msg.into())
}

/// `TAG || 0x00 || payload` (domain separation, §4).
pub fn tagged_preimage(tag: &str, payload: &[u8]) -> Vec<u8> {
    let mut v = Vec::with_capacity(tag.len() + 1 + payload.len());
    v.extend_from_slice(tag.as_bytes());
    v.push(0);
    v.extend_from_slice(payload);
    v
}

pub fn make_id(kind: &str, digest: &[u8; 32]) -> String {
    format!("{kind}:sha256:{}", to_hex(digest))
}

/// Split and validate an ID: `^(blob|pv|chunk|provb):sha256:[0-9a-f]{64}$`.
pub fn parse_id(id: &str) -> Result<(&str, &str)> {
    let mut it = id.splitn(3, ':');
    let (kind, alg, hex) = (it.next(), it.next(), it.next());
    match (kind, alg, hex) {
        (Some(k @ ("blob" | "pv" | "chunk" | "provb")), Some("sha256"), Some(h))
            if h.len() == 64 && h.bytes().all(|c| matches!(c, b'0'..=b'9' | b'a'..=b'f')) =>
        {
            Ok((k, h))
        }
        _ => Err(invalid(format!("malformed id: {id:?}"))),
    }
}

pub fn is_valid_id(id: &str) -> bool {
    parse_id(id).is_ok()
}

// ---------------------------------------------------------------- blob
/// `blob:sha256:<hex>` of raw bytes (equals `sha256sum`).
pub fn blob_id(data: &[u8]) -> String {
    make_id("blob", &sha256(data))
}

/// Streaming blob ID of a reader (files larger than memory). Returns (id, bytes read).
pub fn blob_id_reader(mut r: impl Read) -> std::io::Result<(String, u64)> {
    let mut h = Sha256::new();
    let mut buf = vec![0u8; 1 << 16];
    let mut n = 0u64;
    loop {
        let k = r.read(&mut buf)?;
        if k == 0 {
            break;
        }
        h.update(&buf[..k]);
        n += k as u64;
    }
    Ok((make_id("blob", &h.finalize()), n))
}

// ---------------------------------------------------------------- pipeline version
fn pinned_image(s: &str) -> bool {
    match s.split_once("@sha256:") {
        Some((name, hex)) => {
            !name.is_empty()
                && !name.contains('@')
                && !name.chars().any(char::is_whitespace)
                && hex.len() == 64
                && hex.bytes().all(|c| matches!(c, b'0'..=b'9' | b'a'..=b'f'))
        }
        None => false,
    }
}

/// Canonical payload of a PipelineVersion: the spec without its top-level `meta` (§5.1).
pub fn pipeline_version_payload(spec: &Value) -> Result<Vec<u8>> {
    let Value::Object(members) = spec else {
        return Err(invalid("pipeline version must be an object"));
    };
    if spec.get("schema").and_then(Value::as_str) != Some(PV_SCHEMA) {
        return Err(invalid("schema must be nf.pipeline-version/v1"));
    }
    let steps = match spec.get("steps") {
        None => &[][..],
        Some(Value::Array(steps)) => steps.as_slice(),
        // a malformed `steps` must not skip the pinned-image check (M7)
        Some(_) => return Err(invalid("steps must be an array")),
    };
    for (i, step) in steps.iter().enumerate() {
        let image = step.get("image").and_then(Value::as_str).unwrap_or("");
        if !pinned_image(image) {
            return Err(invalid(format!(
                "step {i}: image must be pinned by digest (name@sha256:...)"
            )));
        }
    }
    let hashed: Vec<(String, Value)> = members
        .iter()
        .filter(|(k, _)| k != "meta")
        .cloned()
        .collect();
    cjson::to_canonical(&Value::Object(hashed))
}

pub fn pipeline_version_id(spec: &Value) -> Result<String> {
    let pre = tagged_preimage(TAG_PIPELINE_VERSION, &pipeline_version_payload(spec)?);
    Ok(make_id("pv", &sha256(&pre)))
}

// ---------------------------------------------------------------- chunk
/// Element types of a chunk (§5.2). Always little-endian, C order.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Dtype {
    Int8,
    Uint8,
    Int16,
    Uint16,
    Int32,
    Uint32,
    Int64,
    Float32,
    Float64,
}

impl Dtype {
    pub const ALL: [Dtype; 9] = [
        Dtype::Int8,
        Dtype::Uint8,
        Dtype::Int16,
        Dtype::Uint16,
        Dtype::Int32,
        Dtype::Uint32,
        Dtype::Int64,
        Dtype::Float32,
        Dtype::Float64,
    ];
    pub fn name(self) -> &'static str {
        match self {
            Dtype::Int8 => "int8",
            Dtype::Uint8 => "uint8",
            Dtype::Int16 => "int16",
            Dtype::Uint16 => "uint16",
            Dtype::Int32 => "int32",
            Dtype::Uint32 => "uint32",
            Dtype::Int64 => "int64",
            Dtype::Float32 => "float32",
            Dtype::Float64 => "float64",
        }
    }
    pub fn itemsize(self) -> usize {
        match self {
            Dtype::Int8 | Dtype::Uint8 => 1,
            Dtype::Int16 | Dtype::Uint16 => 2,
            Dtype::Int32 | Dtype::Uint32 | Dtype::Float32 => 4,
            Dtype::Int64 | Dtype::Float64 => 8,
        }
    }
    pub fn parse(s: &str) -> Result<Dtype> {
        Dtype::ALL
            .into_iter()
            .find(|d| d.name() == s)
            .ok_or_else(|| invalid(format!("unsupported dtype {s}")))
    }
    pub fn is_float(self) -> bool {
        matches!(self, Dtype::Float32 | Dtype::Float64)
    }
}

/// Canonical chunk header `{"dtype":..,"order":"C","shape":[..]}`.
pub fn chunk_header(dtype: Dtype, shape: &[u64]) -> Result<Vec<u8>> {
    let shape_v = Value::Array(
        shape
            .iter()
            .map(|&d| {
                i64::try_from(d)
                    .ok()
                    .filter(|d| *d <= cjson::MAX_SAFE_INT)
                    .map(Value::Int)
                    .ok_or(CanonError::UnsafeInteger)
            })
            .collect::<Result<_>>()?,
    );
    cjson::to_canonical(&Value::obj([
        ("dtype", Value::str(dtype.name())),
        ("order", Value::str("C")),
        ("shape", shape_v),
    ]))
}

fn checked_len(dtype: Dtype, shape: &[u64]) -> Result<usize> {
    shape
        .iter()
        .try_fold(dtype.itemsize() as u64, |acc, &d| acc.checked_mul(d))
        .and_then(|n| usize::try_from(n).ok())
        .ok_or_else(|| invalid("chunk shape overflows"))
}

/// `nf.chunk.v1 0x00 header 0x0A data`.
pub fn chunk_preimage(dtype: Dtype, shape: &[u64], data: &[u8]) -> Result<Vec<u8>> {
    if checked_len(dtype, shape)? != data.len() {
        return Err(invalid("data length does not match dtype and shape"));
    }
    let mut payload = chunk_header(dtype, shape)?;
    payload.push(b'\n');
    payload.extend_from_slice(data);
    Ok(tagged_preimage(TAG_CHUNK, &payload))
}

/// `chunk:sha256:<hex>` of little-endian C-order `data` with `shape` (§5.2). Streams the data
/// through the hash (no copy of the samples).
pub fn chunk_id(dtype: Dtype, shape: &[u64], data: &[u8]) -> Result<String> {
    if checked_len(dtype, shape)? != data.len() {
        return Err(invalid("data length does not match dtype and shape"));
    }
    let mut h = Sha256::new();
    h.update(TAG_CHUNK.as_bytes());
    h.update(&[0]);
    h.update(&chunk_header(dtype, shape)?);
    h.update(b"\n");
    h.update(data);
    Ok(make_id("chunk", &h.finalize()))
}

// ---------------------------------------------------------------- provenance batch
pub(crate) fn is_ms_timestamp(s: &str) -> bool {
    // YYYY-MM-DDTHH:MM:SS.sssZ
    let b = s.as_bytes();
    b.len() == 24
        && b.iter().enumerate().all(|(i, c)| match i {
            4 | 7 => *c == b'-',
            10 => *c == b'T',
            13 | 16 => *c == b':',
            19 => *c == b'.',
            23 => *c == b'Z',
            _ => c.is_ascii_digit(),
        })
}

pub fn prov_batch_payload(batch: &Value) -> Result<Vec<u8>> {
    if !matches!(batch, Value::Object(_)) {
        return Err(invalid("batch must be an object"));
    }
    if batch.get("schema").and_then(Value::as_str) != Some(PROVB_SCHEMA) {
        return Err(invalid("schema must be nf.prov-batch/v1"));
    }
    let seq = match batch.get("seq") {
        Some(Value::Int(n)) if *n >= 0 => *n,
        _ => return Err(invalid("seq must be a non-negative integer")),
    };
    let prev = batch.get("prev").unwrap_or(&Value::Null);
    match prev {
        Value::Null if seq == 0 => {}
        Value::String(p) if seq != 0 => {
            if parse_id(p)?.0 != "provb" {
                return Err(invalid("prev must be a provb id"));
            }
        }
        _ => return Err(invalid("prev must be null exactly when seq == 0")),
    }
    let ts = batch
        .get("created_at")
        .and_then(Value::as_str)
        .unwrap_or("");
    if !is_ms_timestamp(ts) {
        return Err(invalid("created_at must be YYYY-MM-DDTHH:MM:SS.sssZ"));
    }
    cjson::to_canonical(batch)
}

pub fn prov_batch_id(batch: &Value) -> Result<String> {
    let pre = tagged_preimage(TAG_PROV_BATCH, &prov_batch_payload(batch)?);
    Ok(make_id("provb", &sha256(&pre)))
}

/// Recompute every batch ID in order and check the `seq`/`prev` links (§5.3).
pub fn verify_chain(batches: &[Value]) -> Result<Vec<String>> {
    let mut ids: Vec<String> = Vec::with_capacity(batches.len());
    for (i, b) in batches.iter().enumerate() {
        if b.get("seq") != Some(&Value::Int(i as i64)) {
            return Err(invalid(format!("batch {i}: seq does not equal {i}")));
        }
        let expect_prev = ids
            .last()
            .map(|s| Value::String(s.clone()))
            .unwrap_or(Value::Null);
        if b.get("prev").unwrap_or(&Value::Null) != &expect_prev {
            return Err(invalid(format!(
                "batch {i}: prev does not match previous batch id"
            )));
        }
        ids.push(prov_batch_id(b)?);
    }
    Ok(ids)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn id_parsing() {
        let id = blob_id(b"hello\n");
        assert!(is_valid_id(&id));
        assert!(!is_valid_id("blob:sha256:ABC"));
        assert!(!is_valid_id(&id.replace("blob", "file")));
        let (id2, n) = blob_id_reader(&b"hello\n"[..]).unwrap();
        assert_eq!((id2, n), (id, 6));
    }

    #[test]
    fn pinned_images() {
        let h = "ab".repeat(32);
        assert!(pinned_image(&format!("ghcr.io/x/y@sha256:{h}")));
        assert!(!pinned_image("ghcr.io/x/y:latest"));
        assert!(!pinned_image(&format!("@sha256:{h}")));
        assert!(!pinned_image(&format!("a b@sha256:{h}")));
    }

    /// M7: a present-but-malformed `steps` must be rejected, not skip the pinned-image check.
    #[test]
    fn non_array_steps_rejected() {
        let h = "ab".repeat(32);
        let spec = |steps: &str| {
            cjson::parse(&format!(r#"{{"schema":"{PV_SCHEMA}","name":"p"{steps}}}"#)).unwrap()
        };
        for bad in [
            r#","steps":{}"#,
            r#","steps":"x""#,
            r#","steps":null"#,
            r#","steps":1"#,
            r#","steps":{"image":"x:latest"}"#,
        ] {
            assert!(
                matches!(pipeline_version_id(&spec(bad)), Err(CanonError::Invalid(_))),
                "{bad}"
            );
        }
        assert!(pipeline_version_id(&spec("")).is_ok());
        assert!(pipeline_version_id(&spec(r#","steps":[]"#)).is_ok());
        let pinned = format!(r#","steps":[{{"image":"ghcr.io/x/y@sha256:{h}"}}]"#);
        assert!(pipeline_version_id(&spec(&pinned)).is_ok());
        assert!(pipeline_version_id(&spec(r#","steps":[{"image":"x:latest"}]"#)).is_err());
    }

    #[test]
    fn chunk_length_checked() {
        assert!(chunk_id(Dtype::Int16, &[2, 2], &[0; 7]).is_err());
        assert!(chunk_id(Dtype::Int16, &[u64::MAX, 4], &[]).is_err());
        let a = chunk_id(Dtype::Int16, &[4], &[0; 8]).unwrap();
        let b = chunk_id(Dtype::Int16, &[2, 2], &[0; 8]).unwrap();
        assert_ne!(a, b);
        let pre = chunk_preimage(Dtype::Int16, &[4], &[0; 8]).unwrap();
        assert_eq!(a, make_id("chunk", &sha256(&pre)));
    }

    #[test]
    fn timestamps() {
        assert!(is_ms_timestamp("2026-09-26T12:00:00.000Z"));
        assert!(!is_ms_timestamp("2026-09-26T12:00:00Z"));
        assert!(!is_ms_timestamp("2026-09-26T12:00:00.000+00:00"));
    }
}
