//! Hashing spec v2 registrations (`docs/spec/hashing.md` §8-§10), mirroring the stdlib reference
//! `spec/reference/python/nf_ids_v2.py`; conformance is checked against
//! `spec/test-vectors/ids-v2.json` (`tests/vectors_v2.rs`).
//!
//! Every hash here uses the v1 §4 construction `SHA-256(TAG || 0x00 || payload)` with NF-CJSON v1
//! payloads ([`crate::cjson`]), except where the spec says otherwise (the §9.6 raw preimage, the
//! untagged signatures of §10.3-§10.5 and the §10.6 WAL associated data).
//!
//! Byte builders (preimages, signed parts, AAD) are always available. Signature verification uses
//! Ed25519 from `ed25519-dalek`, which is behind the `stream` feature, so the `verify_*`
//! functions exist only with that feature.
//!
//! Set rules implemented exactly as the reference does them (§9.3, §9.7): consent `scopes` and the
//! manifest `subjects`, `excluded_subjects` and `pipeline_version_ids` are de-duplicated and sorted
//! by code point *as given* (NFC is applied afterwards by NF-CJSON, as in Python); manifest
//! `inputs` are first folded to the lowercase canonical UUID form. Note that [`cjson::parse`]
//! already NFC-normalises strings, so values parsed with it are de-duplicated in NFC form.

use std::collections::{BTreeMap, BTreeSet};

use crate::cjson::{self, CanonError, Value};
use crate::ids::{is_ms_timestamp, make_id, parse_id, tagged_preimage};
use crate::sha256::{Sha256, sha256, to_hex};

// ---------------------------------------------------------------- registry (§8)
/// Hash tags (§8.1).
pub const TAG_AUDIT_BATCH: &str = "nf.audit-batch.v1";
pub const TAG_PROV_NODE: &str = "nf.prov-node.v1";
pub const TAG_CONSENT_RECORD: &str = "nf.consent-record.v1";
pub const TAG_RULESET: &str = "nf.ruleset.v1";
pub const TAG_SWEEP_VARIANT: &str = "nf.sweep-variant.v1";
pub const TAG_TRAINING_SUBJECT: &str = "nf.training-subject.v1";
pub const TAG_TRAINING_MANIFEST: &str = "nf.training-manifest.v1";
/// Signature tags (§8.2).
pub const TAG_STREAM_CHUNK: &str = "nf.stream-chunk.v1";
pub const TAG_DEVICE_TOKEN: &str = "nf.device-token.v1";
/// AEAD associated-data tag of the edge WAL (§8.4).
pub const TAG_WAL: &str = "nf.wal.v1";

pub const KIND_AUDIT_BATCH: &str = "auditb";

pub const SCHEMA_AUDIT_BATCH: &str = "nf.audit-batch/v1";
pub const SCHEMA_CONSENT_RECORD: &str = "nf.consent-record/v1";
pub const SCHEMA_PROV_ANCHOR: &str = "nf.prov-anchor/v1";
pub const SCHEMA_CONSENT_ANCHOR: &str = "nf.consent-anchor/v1";
pub const SCHEMA_DELETION_CERT: &str = "nf.deletion-certificate/v1";
pub const SCHEMA_TRAINING_MANIFEST: &str = "nf.training-manifest/v1";

pub const DEVICE_TOKEN_PREFIX: &str = "nfd1";
pub const DEVICE_TOKEN_AUDIENCE: &str = "nf-ingest/v1";
/// Longest accepted device token (characters), as in the platform parser.
pub const MAX_DEVICE_TOKEN_LEN: usize = 2048;
pub const MAX_TOKEN_LIFETIME_S: i64 = 600;
pub const CLOCK_LEEWAY_S: i64 = 30;

type Result<T> = std::result::Result<T, CanonError>;

fn invalid(msg: impl Into<String>) -> CanonError {
    CanonError::Invalid(msg.into())
}

fn tagged_hex(tag: &str, payload: &[u8]) -> String {
    to_hex(&sha256(&tagged_preimage(tag, payload)))
}

fn is_lower_hex(s: &str, len: usize) -> bool {
    s.len() == len && s.bytes().all(|c| matches!(c, b'0'..=b'9' | b'a'..=b'f'))
}

/// A bare digest: `^[0-9a-f]{64}$` (§8.5).
pub fn is_digest(s: &str) -> bool {
    is_lower_hex(s, 64)
}

/// Split and validate a v2 ID: `^(blob|pv|chunk|provb|auditb):sha256:[0-9a-f]{64}$` (§8.5).
pub fn parse_id_v2(id: &str) -> Result<(&str, &str)> {
    if let Some(h) = id.strip_prefix("auditb:sha256:") {
        if is_digest(h) {
            return Ok((KIND_AUDIT_BATCH, h));
        }
        return Err(invalid(format!("malformed id: {id:?}")));
    }
    parse_id(id)
}

fn object(v: &Value, what: &str) -> Result<()> {
    match v {
        Value::Object(_) => Ok(()),
        _ => Err(invalid(format!("{what} must be an object"))),
    }
}

fn require_schema(v: &Value, schema: &str) -> Result<()> {
    if v.get("schema").and_then(Value::as_str) == Some(schema) {
        Ok(())
    } else {
        Err(invalid(format!("schema must be {schema}")))
    }
}

/// `seq == 0` as the reference compares it (an integral zero).
fn seq_is_zero(v: &Value) -> bool {
    match v.get("seq") {
        Some(Value::Int(0)) => true,
        Some(Value::Float(f)) => *f == 0.0,
        _ => false,
    }
}

fn without_member(v: &Value, key: &str) -> Value {
    match v {
        Value::Object(m) => Value::Object(m.iter().filter(|(k, _)| k != key).cloned().collect()),
        other => other.clone(),
    }
}

fn sorted_unique<I, S>(items: I) -> Vec<String>
where
    I: IntoIterator<Item = S>,
    S: Into<String>,
{
    items
        .into_iter()
        .map(Into::into)
        .collect::<BTreeSet<String>>()
        .into_iter()
        .collect()
}

fn str_array(v: Vec<String>) -> Value {
    Value::Array(v.into_iter().map(Value::String).collect())
}

fn opt_str(v: &Option<String>) -> Value {
    v.as_ref().map_or(Value::Null, |s| Value::String(s.clone()))
}

// ---------------------------------------------------------------- §9.1 audit batch (auditb)
/// Validated NF-CJSON payload of an audit batch (same rules as `provb`, v1 §5.3).
pub fn audit_batch_payload(batch: &Value) -> Result<Vec<u8>> {
    object(batch, "audit batch")?;
    require_schema(batch, SCHEMA_AUDIT_BATCH)?;
    let seq = match batch.get("seq") {
        Some(Value::Int(n)) if *n >= 0 => *n,
        _ => return Err(invalid("seq must be a non-negative integer")),
    };
    match batch.get("prev").unwrap_or(&Value::Null) {
        Value::Null if seq == 0 => {}
        Value::String(p) if seq != 0 => {
            if !p.strip_prefix("auditb:sha256:").is_some_and(is_digest) {
                return Err(invalid("prev must be an auditb id"));
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

/// `auditb:sha256:<hex>` of an audit batch.
pub fn audit_batch_id(batch: &Value) -> Result<String> {
    let pre = tagged_preimage(TAG_AUDIT_BATCH, &audit_batch_payload(batch)?);
    Ok(make_id(KIND_AUDIT_BATCH, &sha256(&pre)))
}

/// Recompute every audit batch ID in order and check the `seq`/`prev` links.
pub fn verify_audit_chain(batches: &[Value]) -> Result<Vec<String>> {
    let mut ids: Vec<String> = Vec::with_capacity(batches.len());
    for (i, b) in batches.iter().enumerate() {
        if b.get("seq") != Some(&Value::Int(i as i64)) {
            return Err(invalid(format!("batch {i}: seq does not equal {i}")));
        }
        let expect = ids.last().map_or(Value::Null, |s| Value::String(s.clone()));
        if b.get("prev").unwrap_or(&Value::Null) != &expect {
            return Err(invalid(format!(
                "batch {i}: prev does not match previous batch id"
            )));
        }
        ids.push(audit_batch_id(b)?);
    }
    Ok(ids)
}

// ---------------------------------------------------------------- §9.2 provenance node hash
/// Node record as `provenance/chain.py` `node_record` builds it: `ref` and `content` omitted
/// when absent, `attrs` when absent, null or an empty object.
pub fn prov_node_record(
    node_id: &str,
    kind: &str,
    label: &str,
    reference: Option<&str>,
    content: Option<&str>,
    attrs: Option<&Value>,
) -> Value {
    let mut m: Vec<(String, Value)> = vec![
        ("type".into(), Value::str(kind)),
        ("id".into(), Value::str(node_id)),
        ("label".into(), Value::str(label)),
    ];
    if let Some(r) = reference {
        m.push(("ref".into(), Value::str(r)));
    }
    if let Some(c) = content {
        m.push(("content".into(), Value::str(c)));
    }
    match attrs {
        None | Some(Value::Null) => {}
        Some(Value::Object(o)) if o.is_empty() => {}
        Some(a) => m.push(("attrs".into(), a.clone())),
    }
    Value::Object(m)
}

/// Bare 64-hex digest of a node record (`prov_node.node_hash`).
pub fn prov_node_hash(record: &Value) -> Result<String> {
    Ok(tagged_hex(TAG_PROV_NODE, &cjson::to_canonical(record)?))
}

// ---------------------------------------------------------------- §9.3 consent record hash
/// A copy of the record with `scopes` de-duplicated and sorted (§9.3).
pub fn canonical_consent_record(record: &Value) -> Result<Value> {
    let Value::Object(members) = record else {
        return Err(invalid("consent record must be an object"));
    };
    let scopes = match record.get("scopes") {
        Some(Value::Array(a)) => a
            .iter()
            .map(|x| x.as_str().map(str::to_owned))
            .collect::<Option<Vec<String>>>(),
        _ => None,
    }
    .ok_or_else(|| invalid("scopes must be an array of strings"))?;
    let canon = str_array(sorted_unique(scopes));
    Ok(Value::Object(
        members
            .iter()
            .map(|(k, v)| {
                let v = if k == "scopes" {
                    canon.clone()
                } else {
                    v.clone()
                };
                (k.clone(), v)
            })
            .collect(),
    ))
}

/// NF-CJSON payload of the canonical consent record (validated).
pub fn consent_record_payload(record: &Value) -> Result<Vec<u8>> {
    object(record, "consent record")?;
    require_schema(record, SCHEMA_CONSENT_RECORD)?;
    let prev = record.get("prev").unwrap_or(&Value::Null);
    if seq_is_zero(record) != (*prev == Value::Null) {
        return Err(invalid("prev must be null exactly when seq == 0"));
    }
    if *prev != Value::Null && !prev.as_str().is_some_and(is_digest) {
        return Err(invalid("prev must be a 64-hex record hash"));
    }
    cjson::to_canonical(&canonical_consent_record(record)?)
}

/// Bare 64-hex `record_hash`; equal scope sets give equal hashes.
pub fn consent_record_hash(record: &Value) -> Result<String> {
    Ok(tagged_hex(
        TAG_CONSENT_RECORD,
        &consent_record_payload(record)?,
    ))
}

/// Recompute every consent record hash in order and check the `seq`/`prev` links.
pub fn verify_consent_chain(records: &[Value]) -> Result<Vec<String>> {
    let mut hashes: Vec<String> = Vec::with_capacity(records.len());
    for (i, r) in records.iter().enumerate() {
        let expect = hashes
            .last()
            .map_or(Value::Null, |s| Value::String(s.clone()));
        if r.get("seq") != Some(&Value::Int(i as i64))
            || r.get("prev").unwrap_or(&Value::Null) != &expect
        {
            return Err(invalid(format!("record {i}: seq/prev link broken")));
        }
        hashes.push(consent_record_hash(r)?);
    }
    Ok(hashes)
}

// ---------------------------------------------------------------- §9.4 RuleSet content hash
/// Bare 64-hex digest over the canonical ARRAY of public rule objects (manifest order).
pub fn ruleset_content_sha256(public_rules: &Value) -> Result<String> {
    if !matches!(public_rules, Value::Array(_)) {
        return Err(invalid("public rules must be an array"));
    }
    Ok(tagged_hex(TAG_RULESET, &cjson::to_canonical(public_rules)?))
}

// ---------------------------------------------------------------- §9.5 sweep variant label
/// NF-CJSON `{"base", "params"}` (the base must be a v1 ID).
pub fn sweep_variant_payload(base_pv_id: &str, params: &Value) -> Result<Vec<u8>> {
    parse_id(base_pv_id)?;
    cjson::to_canonical(&Value::obj([
        ("base", Value::str(base_pv_id)),
        ("params", params.clone()),
    ]))
}

/// First 12 hex (48 bits) of the tagged digest; a label, not an ID.
pub fn sweep_variant_label(base_pv_id: &str, params: &Value) -> Result<String> {
    let mut h = tagged_hex(
        TAG_SWEEP_VARIANT,
        &sweep_variant_payload(base_pv_id, params)?,
    );
    h.truncate(12);
    Ok(h)
}

// ---------------------------------------------------------------- §9.6 training subject hash
/// The 36-character lowercase hyphenated UUID form; upper-case hex is folded to lower case.
pub fn canonical_uuid(value: &str) -> Result<String> {
    let v = value.to_ascii_lowercase();
    let b = v.as_bytes();
    let ok = b.len() == 36
        && b.iter().enumerate().all(|(i, c)| match i {
            8 | 13 | 18 | 23 => *c == b'-',
            _ => matches!(c, b'0'..=b'9' | b'a'..=b'f'),
        });
    if ok {
        Ok(v)
    } else {
        Err(invalid(format!("not a hyphenated UUID: {value:?}")))
    }
}

/// `nf.training-subject.v1 0x00 tenant-uuid 0x00 subject-uuid` (raw ASCII, not NF-CJSON).
pub fn training_subject_preimage(tenant_id: &str, subject_id: &str) -> Result<Vec<u8>> {
    let mut payload = canonical_uuid(tenant_id)?.into_bytes();
    payload.push(0);
    payload.extend_from_slice(canonical_uuid(subject_id)?.as_bytes());
    Ok(tagged_preimage(TAG_TRAINING_SUBJECT, &payload))
}

/// Bare 64-hex training subject hash.
pub fn training_subject_hash(tenant_id: &str, subject_id: &str) -> Result<String> {
    Ok(to_hex(&sha256(&training_subject_preimage(
        tenant_id, subject_id,
    )?)))
}

// ---------------------------------------------------------------- §9.7 training manifest digest
/// Inputs of `registry/manifest.py` `build` (argument names as in the reference).
#[derive(Debug, Clone, Default, PartialEq)]
pub struct TrainingManifestArgs {
    /// Written as given (§11 item 9): pass the canonical lowercase form.
    pub tenant_id: String,
    pub input_node_ids: Vec<String>,
    pub subject_hashes: Vec<String>,
    pub n_source_recordings: i64,
    pub shards: Option<BTreeMap<String, i64>>,
    pub excluded_subject_hashes: Vec<String>,
    pub pipeline_version_ids: Vec<String>,
    pub code_commit: String,
    pub recipe: Option<String>,
    pub parent_version_id: Option<String>,
    /// §9.7 amendment (AppSec M3, additive): `"platform"` or `"upload"`; `None` = member absent
    /// (manifests built before the amendment keep their digests).
    pub weights_source: Option<String>,
}

/// The manifest document as the registry builds it (sets de-duplicated and sorted, inputs
/// folded to lowercase UUIDs first).
pub fn training_manifest(a: &TrainingManifestArgs) -> Result<Value> {
    let subjects = sorted_unique(a.subject_hashes.iter().cloned());
    let shard_keys = a.shards.iter().flat_map(|m| m.keys());
    if !subjects
        .iter()
        .chain(a.excluded_subject_hashes.iter())
        .chain(shard_keys)
        .all(|h| is_digest(h))
    {
        return Err(invalid("subject hashes are 64 lowercase hex"));
    }
    let inputs = sorted_unique(
        a.input_node_ids
            .iter()
            .map(|i| canonical_uuid(i))
            .collect::<Result<Vec<String>>>()?,
    );
    let n_subjects = subjects.len() as i64;
    let mut doc: Vec<(String, Value)> = vec![
        ("schema".into(), Value::str(SCHEMA_TRAINING_MANIFEST)),
        ("tenant".into(), Value::str(a.tenant_id.clone())),
        ("inputs".into(), str_array(inputs)),
        ("subjects".into(), str_array(subjects)),
        ("n_subjects".into(), Value::Int(n_subjects)),
        (
            "n_source_recordings".into(),
            Value::Int(a.n_source_recordings),
        ),
        (
            "excluded_subjects".into(),
            str_array(sorted_unique(a.excluded_subject_hashes.iter().cloned())),
        ),
        (
            "pipeline_version_ids".into(),
            str_array(sorted_unique(a.pipeline_version_ids.iter().cloned())),
        ),
        ("code_commit".into(), Value::str(a.code_commit.clone())),
        ("recipe".into(), opt_str(&a.recipe)),
        ("parent_version".into(), opt_str(&a.parent_version_id)),
    ];
    if let Some(sh) = a.shards.as_ref().filter(|m| !m.is_empty()) {
        doc.push((
            "shards".into(),
            Value::Object(
                sh.iter()
                    .map(|(k, v)| (k.clone(), Value::Int(*v)))
                    .collect(),
            ),
        ));
    }
    if let Some(ws) = &a.weights_source {
        if ws != "platform" && ws != "upload" {
            return Err(invalid("weights_source is platform or upload"));
        }
        doc.push(("weights_source".into(), Value::str(ws.clone())));
    }
    Ok(Value::Object(doc))
}

/// Bare 64-hex digest of a manifest document (`model_version.manifest_sha256`).
pub fn training_manifest_digest(doc: &Value) -> Result<String> {
    require_schema(doc, SCHEMA_TRAINING_MANIFEST)?;
    Ok(tagged_hex(
        TAG_TRAINING_MANIFEST,
        &cjson::to_canonical(doc)?,
    ))
}

// ---------------------------------------------------------------- §10.1 stream chunk signature
/// Untagged SHA-256 over float64-LE timestamps, then offset pairs, then local-clock pairs.
pub fn timing_sha256(ts: &[f64], offsets: &[(f64, f64)], local: &[(f64, f64)]) -> String {
    let mut h = Sha256::new();
    let all = ts
        .iter()
        .copied()
        .chain(offsets.iter().flat_map(|(a, b)| [*a, *b]))
        .chain(local.iter().flat_map(|(a, b)| [*a, *b]));
    for v in all {
        h.update(&v.to_le_bytes());
    }
    to_hex(&h.finalize())
}

/// The fields of a chunk that its signature covers.
#[derive(Debug, Clone, Copy)]
pub struct StreamChunkFields<'a> {
    pub stream_id: &'a str,
    pub seq: u64,
    pub n_samples: u32,
    pub n_channels: u32,
    pub chunk_id: &'a str,
    pub lsl_timestamps: &'a [f64],
    /// `(collection_time, offset)` pairs.
    pub clock_offsets: &'a [(f64, f64)],
    /// `(lsl_time, monotonic_time)` pairs.
    pub local_clock: &'a [(f64, f64)],
}

/// The signing body (§10.1).
pub fn stream_chunk_body(c: &StreamChunkFields<'_>) -> Result<Value> {
    let seq = i64::try_from(c.seq).map_err(|_| CanonError::UnsafeInteger)?;
    Ok(Value::obj([
        ("chunk_id", Value::str(c.chunk_id)),
        ("n_channels", Value::Int(i64::from(c.n_channels))),
        ("n_clock_offsets", Value::Int(c.clock_offsets.len() as i64)),
        ("n_local_clock", Value::Int(c.local_clock.len() as i64)),
        ("n_samples", Value::Int(i64::from(c.n_samples))),
        ("seq", Value::Int(seq)),
        ("stream_id", Value::str(c.stream_id)),
        (
            "t_first",
            Value::Float(c.lsl_timestamps.first().copied().unwrap_or(0.0)),
        ),
        (
            "t_last",
            Value::Float(c.lsl_timestamps.last().copied().unwrap_or(0.0)),
        ),
        (
            "timing_sha256",
            Value::str(timing_sha256(
                c.lsl_timestamps,
                c.clock_offsets,
                c.local_clock,
            )),
        ),
    ]))
}

/// Signed bytes: `nf.stream-chunk.v1 0x00 NF-CJSON(body)`.
pub fn stream_chunk_preimage(c: &StreamChunkFields<'_>) -> Result<Vec<u8>> {
    Ok(tagged_preimage(
        TAG_STREAM_CHUNK,
        &cjson::to_canonical(&stream_chunk_body(c)?)?,
    ))
}

// ---------------------------------------------------------------- §10.2 device token
/// NF-CJSON of the claims (audience checked).
pub fn device_token_payload(claims: &Value) -> Result<Vec<u8>> {
    if claims.get("aud").and_then(Value::as_str) != Some(DEVICE_TOKEN_AUDIENCE) {
        return Err(invalid(format!("aud must be {DEVICE_TOKEN_AUDIENCE}")));
    }
    cjson::to_canonical(claims)
}

/// Signed bytes: `nf.device-token.v1 0x00 payload`.
pub fn device_token_preimage(claims: &Value) -> Result<Vec<u8>> {
    Ok(tagged_preimage(
        TAG_DEVICE_TOKEN,
        &device_token_payload(claims)?,
    ))
}

/// A device token split into its parts. The claims are NOT verified yet.
#[derive(Debug, Clone, PartialEq)]
pub struct DeviceTokenParts {
    pub claims: Value,
    pub payload: Vec<u8>,
    pub signature: Vec<u8>,
}

/// Split `nfd1.<b64url payload>.<b64url sig>` as the platform parser does: the payload must
/// already be canonical, carry the audience and string/integer claims.
pub fn parse_device_token(token: &str) -> Result<DeviceTokenParts> {
    let parts: Vec<&str> = token.split('.').collect();
    if parts.len() != 3 || parts[0] != DEVICE_TOKEN_PREFIX || token.len() > MAX_DEVICE_TOKEN_LEN {
        return Err(invalid("malformed device token"));
    }
    let (Some(payload), Some(signature)) = (
        crate::b64::decode_url(parts[1]),
        crate::b64::decode_url(parts[2]),
    ) else {
        return Err(invalid("malformed device token"));
    };
    let text =
        std::str::from_utf8(&payload).map_err(|_| invalid("malformed device token payload"))?;
    let claims = cjson::parse(text)?;
    if cjson::to_canonical(&claims)? != payload {
        return Err(invalid("device token payload is not canonical"));
    }
    for k in ["tenant_id", "device_id", "stream_id"] {
        if claims.get(k).is_none() {
            return Err(invalid("malformed device token payload"));
        }
    }
    for k in ["iat", "exp"] {
        if !matches!(claims.get(k), Some(Value::Int(_))) {
            return Err(invalid("malformed device token payload"));
        }
    }
    if claims.get("aud").and_then(Value::as_str) != Some(DEVICE_TOKEN_AUDIENCE) {
        return Err(invalid("device token has the wrong audience"));
    }
    Ok(DeviceTokenParts {
        claims,
        payload,
        signature,
    })
}

// ---------------------------------------------------------------- §10.3-§10.5 untagged signatures
/// Provenance batch signature message: the ASCII bytes of the `provb` ID (no tag).
pub fn provb_signature_message(batch_id: &str) -> Result<Vec<u8>> {
    parse_id(batch_id)?;
    Ok(batch_id.as_bytes().to_vec())
}

/// Prov/consent anchors: NF-CJSON of the document without `sig` (no tag).
pub fn anchor_signed_part(anchor: &Value) -> Result<Vec<u8>> {
    match anchor.get("schema").and_then(Value::as_str) {
        Some(SCHEMA_PROV_ANCHOR | SCHEMA_CONSENT_ANCHOR) => {}
        _ => return Err(invalid("not an anchor document")),
    }
    cjson::to_canonical(&without_member(anchor, "sig"))
}

/// Deletion certificate: NF-CJSON of the document without `signature` (no tag).
pub fn certificate_signed_part(cert: &Value) -> Result<Vec<u8>> {
    require_schema(cert, SCHEMA_DELETION_CERT)?;
    cjson::to_canonical(&without_member(cert, "signature"))
}

// ---------------------------------------------------------------- §10.6 edge WAL AAD
/// `nf.wal.v1 0x00 UTF-8(stream_id) 0x00 ASCII(decimal seq)`.
pub fn wal_aad(stream_id: &str, seq: u64) -> Vec<u8> {
    let mut a = tagged_preimage(TAG_WAL, stream_id.as_bytes());
    a.push(0);
    a.extend_from_slice(seq.to_string().as_bytes());
    a
}

// ---------------------------------------------------------------- Ed25519 verification
#[cfg(feature = "stream")]
use crate::stream::sign::verify as ed25519_verify;

/// Stream chunk signature (§10.1).
#[cfg(feature = "stream")]
pub fn verify_stream_chunk(c: &StreamChunkFields<'_>, sig: &[u8], public_key: &[u8; 32]) -> bool {
    stream_chunk_preimage(c).is_ok_and(|p| ed25519_verify(public_key, &p, sig))
}

/// Parse and verify a device token (§10.2): signature, lifetime at most 600 s, and validity at
/// `now` (Unix seconds) within the ±30 s leeway. Returns the claims.
#[cfg(feature = "stream")]
pub fn verify_device_token(token: &str, public_key: &[u8; 32], now: i64) -> Result<Value> {
    let p = parse_device_token(token)?;
    if !ed25519_verify(
        public_key,
        &tagged_preimage(TAG_DEVICE_TOKEN, &p.payload),
        &p.signature,
    ) {
        return Err(invalid("device token signature does not verify"));
    }
    let int = |k: &str| match p.claims.get(k) {
        Some(Value::Int(n)) => *n,
        _ => 0,
    };
    let (iat, exp) = (int("iat"), int("exp"));
    if exp - iat > MAX_TOKEN_LIFETIME_S || exp <= iat {
        return Err(invalid("device token lifetime out of range"));
    }
    if iat > now + CLOCK_LEEWAY_S || exp < now - CLOCK_LEEWAY_S {
        return Err(invalid("device token expired or not yet valid"));
    }
    Ok(p.claims)
}

/// Provenance batch signature (§10.3).
#[cfg(feature = "stream")]
pub fn verify_provb_signature(batch_id: &str, sig: &[u8], public_key: &[u8; 32]) -> bool {
    provb_signature_message(batch_id).is_ok_and(|m| ed25519_verify(public_key, &m, sig))
}

/// Chain-head anchor (§10.4): `sig` is lowercase hex.
#[cfg(feature = "stream")]
pub fn verify_anchor(anchor: &Value, public_key: &[u8; 32]) -> bool {
    let Some(sig) = anchor
        .get("sig")
        .and_then(Value::as_str)
        .filter(|s| is_lower_hex(s, 128))
        .and_then(crate::sha256::from_hex)
    else {
        return false;
    };
    anchor_signed_part(anchor).is_ok_and(|m| ed25519_verify(public_key, &m, &sig))
}

/// Deletion certificate (§10.5): `signature = {"alg": "Ed25519", "key_id", "value": base64}`.
#[cfg(feature = "stream")]
pub fn verify_certificate(cert: &Value, public_key: &[u8; 32]) -> bool {
    let Some(s) = cert.get("signature") else {
        return false;
    };
    if s.get("alg").and_then(Value::as_str) != Some("Ed25519") {
        return false;
    }
    let Some(sig) = s
        .get("value")
        .and_then(Value::as_str)
        .and_then(crate::b64::decode_std)
    else {
        return false;
    };
    certificate_signed_part(cert).is_ok_and(|m| ed25519_verify(public_key, &m, &sig))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn id_v2_accepts_auditb_only_in_v2() {
        let id = format!("auditb:sha256:{}", "a".repeat(64));
        assert_eq!(parse_id_v2(&id).unwrap().0, "auditb");
        assert!(parse_id(&id).is_err());
        assert!(parse_id_v2("auditb:sha256:ABC").is_err());
        assert!(parse_id_v2(&format!("pv:sha256:{}", "0".repeat(64))).is_ok());
    }

    #[test]
    fn uuid_folding() {
        assert_eq!(
            canonical_uuid("00000000-0000-4000-8000-0000000000A1").unwrap(),
            "00000000-0000-4000-8000-0000000000a1"
        );
        assert!(canonical_uuid("00000000000040008000000000000000").is_err());
        assert!(canonical_uuid("00000000-0000-4000-8000-0000000000g1").is_err());
    }

    #[test]
    fn consent_rejects_bad_links_and_scopes() {
        let base = |seq: i64, prev: Value, scopes: Value| {
            Value::obj([
                ("schema", Value::str(SCHEMA_CONSENT_RECORD)),
                ("seq", Value::Int(seq)),
                ("prev", prev),
                ("scopes", scopes),
            ])
        };
        let ok_scopes = Value::Array(vec![Value::str("b"), Value::str("a")]);
        assert!(consent_record_hash(&base(0, Value::Null, ok_scopes.clone())).is_ok());
        assert!(consent_record_hash(&base(1, Value::Null, ok_scopes.clone())).is_err());
        assert!(
            consent_record_hash(&base(0, Value::str("a".repeat(64)), ok_scopes.clone())).is_err()
        );
        assert!(consent_record_hash(&base(1, Value::str("xyz"), ok_scopes)).is_err());
        assert!(
            consent_record_hash(&base(0, Value::Null, Value::Array(vec![Value::Int(1)]))).is_err()
        );
    }

    #[test]
    fn manifest_rejects_bad_digests_and_uuids() {
        let good = TrainingManifestArgs {
            tenant_id: "00000000-0000-4000-8000-0000000000a1".into(),
            input_node_ids: vec!["00000000-0000-4000-8000-000000000c01".into()],
            subject_hashes: vec!["0".repeat(64)],
            ..Default::default()
        };
        assert!(training_manifest(&good).is_ok());
        let bad_subject = TrainingManifestArgs {
            subject_hashes: vec!["A".repeat(64)],
            ..good.clone()
        };
        assert!(training_manifest(&bad_subject).is_err());
        let bad_input = TrainingManifestArgs {
            input_node_ids: vec!["not-a-uuid".into()],
            ..good
        };
        assert!(training_manifest(&bad_input).is_err());
    }

    #[test]
    fn audit_prev_rules() {
        let b = |seq: i64, prev: Value| {
            Value::obj([
                ("schema", Value::str(SCHEMA_AUDIT_BATCH)),
                ("seq", Value::Int(seq)),
                ("prev", prev),
                ("created_at", Value::str("2026-09-26T11:05:00.000Z")),
            ])
        };
        assert!(audit_batch_id(&b(0, Value::Null)).is_ok());
        assert!(audit_batch_id(&b(1, Value::Null)).is_err());
        let provb = format!("provb:sha256:{}", "0".repeat(64));
        assert!(audit_batch_id(&b(1, Value::str(provb))).is_err());
        let auditb = format!("auditb:sha256:{}", "0".repeat(64));
        assert!(audit_batch_id(&b(1, Value::str(auditb))).is_ok());
    }
}
