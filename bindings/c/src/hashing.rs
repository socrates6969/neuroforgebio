//! Hashing spec v1 and v2 (`docs/spec/hashing.md`): canonical JSON, content IDs, chain and
//! signature verification. All functions are pure and thread-safe.
//!
//! Documents are `(ptr, len)` UTF-8 JSON parsed by nf-core's strict parser (duplicate keys,
//! unsafe integers and lone surrogates are rejected with `NF_ERR_CANONICAL`). IDs and hashes come
//! back as NUL-terminated text in an `nf_buf`.

use std::collections::BTreeMap;
use std::ffi::c_char;

use nf_core::cjson::{self, Value};
use nf_core::ids;
use nf_core::ids_v2::{self as v2, StreamChunkFields, TrainingManifestArgs};

use crate::{
    Error, NF_ERR_INVALID_ARG, NF_ERR_VERIFY, Result, cstr, dtype_from, guard, guard_value, json,
    nf_buf, nf_dtype, nf_status, out, put_buf, slice,
};

fn chain_err(e: cjson::CanonError) -> Error {
    Error::new(NF_ERR_VERIFY, e.to_string())
}

unsafe fn public_key(p: *const u8) -> Result<[u8; 32]> {
    // SAFETY: the caller passes 32 readable bytes (header contract).
    let s = unsafe { slice(p, 32, "public_key") }?;
    Ok(s.try_into().expect("32 bytes"))
}

fn json_array(v: Value, what: &str) -> Result<Vec<Value>> {
    match v {
        Value::Array(a) => Ok(a),
        _ => Err(Error::invalid(format!("{what} must be a JSON array"))),
    }
}

/// One ID per line (`'\n'`, no trailing newline).
fn lines(ids: Vec<String>) -> Vec<u8> {
    ids.join("\n").into_bytes()
}

// ---------------------------------------------------------------- v1: canonical JSON
/// NF-CJSON v1 canonical bytes of a JSON document (hashing.md sec. 3).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_canonicalize(
    json_text: *const u8,
    json_len: usize,
    out_canonical: *mut nf_buf,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (t, o) = unsafe {
            (
                crate::text(json_text, json_len, "json")?,
                out(out_canonical, "out_canonical")?,
            )
        };
        put_buf(o, cjson::canonicalize_text(t)?);
        Ok(())
    })
}

/// Canonical text of one number (hashing.md sec. 3.3). Non-finite values fail with
/// `NF_ERR_CANONICAL`.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_format_number(x: f64, out_text: *mut nf_buf) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let o = unsafe { out(out_text, "out_text")? };
        put_buf(o, cjson::format_number(x)?);
        Ok(())
    })
}

// ---------------------------------------------------------------- v1: IDs
/// `blob:sha256:<hex>` of raw bytes (hashing.md sec. 5.1).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_blob_id(data: *const u8, len: usize, out_id: *mut nf_buf) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (d, o) = unsafe { (slice(data, len, "data")?, out(out_id, "out_id")?) };
        put_buf(o, ids::blob_id(d));
        Ok(())
    })
}

/// Streaming blob ID of a file, and its size in bytes (`out_size` may be NULL).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_blob_id_file(
    path: *const c_char,
    out_id: *mut nf_buf,
    out_size: *mut u64,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (p, o) = unsafe { (cstr(path, "path")?, out(out_id, "out_id")?) };
        let f = std::fs::File::open(p)?;
        let (id, n) = ids::blob_id_reader(std::io::BufReader::new(f))?;
        put_buf(o, id);
        // SAFETY: NULL or writable.
        if let Some(s) = unsafe { crate::opt_out(out_size, "out_size") }? {
            *s = n;
        }
        Ok(())
    })
}

/// `pv:sha256:<hex>` of a pipeline-version spec (hashing.md sec. 5.4).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_pipeline_version_id(
    spec_json: *const u8,
    spec_len: usize,
    out_id: *mut nf_buf,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (v, o) = unsafe {
            (
                json(spec_json, spec_len, "spec_json")?,
                out(out_id, "out_id")?,
            )
        };
        put_buf(o, ids::pipeline_version_id(&v)?);
        Ok(())
    })
}

/// `chunk:sha256:<hex>` of an array chunk (hashing.md sec. 5.2): `shape` has `rank` entries and
/// `data` is `itemsize * prod(shape)` little-endian bytes in C order.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_chunk_id(
    dtype: nf_dtype,
    shape: *const u64,
    rank: usize,
    data: *const u8,
    data_len: usize,
    out_id: *mut nf_buf,
) -> nf_status {
    guard(|| {
        let dt = dtype_from(dtype)?;
        // SAFETY: header contract.
        let (sh, d, o) = unsafe {
            (
                slice(shape, rank, "shape")?,
                slice(data, data_len, "data")?,
                out(out_id, "out_id")?,
            )
        };
        put_buf(o, ids::chunk_id(dt, sh, d)?);
        Ok(())
    })
}

/// `provb:sha256:<hex>` of one provenance batch (hashing.md sec. 5.3).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_prov_batch_id(
    batch_json: *const u8,
    batch_len: usize,
    out_id: *mut nf_buf,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (v, o) = unsafe {
            (
                json(batch_json, batch_len, "batch_json")?,
                out(out_id, "out_id")?,
            )
        };
        put_buf(o, ids::prov_batch_id(&v)?);
        Ok(())
    })
}

/// Verify a provenance batch chain given as a JSON array of batches (hashing.md sec. 5.3). On
/// success `out_ids` holds the batch IDs, one per line. A broken chain is `NF_ERR_VERIFY`.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_verify_prov_chain(
    batches_json: *const u8,
    batches_len: usize,
    out_ids: *mut nf_buf,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (v, o) = unsafe {
            (
                json(batches_json, batches_len, "batches_json")?,
                out(out_ids, "out_ids")?,
            )
        };
        let batches = json_array(v, "batches_json")?;
        put_buf(o, lines(ids::verify_chain(&batches).map_err(chain_err)?));
        Ok(())
    })
}

/// Whether `id` is a well-formed v1 ID (`blob|pv|chunk|provb:sha256:<64 hex>`). NULL or invalid
/// UTF-8 is false.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_is_valid_id(id: *const c_char) -> bool {
    // SAFETY: header contract.
    guard_value(false, || Ok(ids::is_valid_id(unsafe { cstr(id, "id") }?)))
}

// ---------------------------------------------------------------- v2 (sec. 8-sec. 9): IDs and hashes
/// Whether `id` is a well-formed v2 ID (v1 kinds plus `auditb`).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_is_valid_id_v2(id: *const c_char) -> bool {
    // SAFETY: header contract.
    guard_value(false, || {
        Ok(v2::parse_id_v2(unsafe { cstr(id, "id") }?).is_ok())
    })
}

/// Shared shape of the "one JSON document in, one text out" v2 functions.
unsafe fn doc_to_text(
    p: *const u8,
    len: usize,
    out_text: *mut nf_buf,
    f: impl FnOnce(&Value) -> Result<String>,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (v, o) = unsafe { (json(p, len, "json")?, out(out_text, "out")?) };
        put_buf(o, f(&v)?);
        Ok(())
    })
}

/// `auditb:sha256:<hex>` of one audit batch (hashing.md sec. 9.1).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_audit_batch_id(
    batch_json: *const u8,
    batch_len: usize,
    out_id: *mut nf_buf,
) -> nf_status {
    // SAFETY: forwarded contract.
    unsafe {
        doc_to_text(batch_json, batch_len, out_id, |v| {
            Ok(v2::audit_batch_id(v)?)
        })
    }
}

/// Verify an audit batch chain (JSON array); IDs one per line. Broken chain: `NF_ERR_VERIFY`.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_verify_audit_chain(
    batches_json: *const u8,
    batches_len: usize,
    out_ids: *mut nf_buf,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (v, o) = unsafe {
            (
                json(batches_json, batches_len, "batches_json")?,
                out(out_ids, "out_ids")?,
            )
        };
        let batches = json_array(v, "batches_json")?;
        put_buf(
            o,
            lines(v2::verify_audit_chain(&batches).map_err(chain_err)?),
        );
        Ok(())
    })
}

/// Bare SHA-256 hex of a provenance node record (hashing.md sec. 9.2).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_prov_node_hash(
    record_json: *const u8,
    record_len: usize,
    out_hash: *mut nf_buf,
) -> nf_status {
    // SAFETY: forwarded contract.
    unsafe {
        doc_to_text(record_json, record_len, out_hash, |v| {
            Ok(v2::prov_node_hash(v)?)
        })
    }
}

/// Bare SHA-256 hex of a consent record (hashing.md sec. 9.3; scopes are a set).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_consent_record_hash(
    record_json: *const u8,
    record_len: usize,
    out_hash: *mut nf_buf,
) -> nf_status {
    // SAFETY: forwarded contract.
    unsafe {
        doc_to_text(record_json, record_len, out_hash, |v| {
            Ok(v2::consent_record_hash(v)?)
        })
    }
}

/// Verify a consent record chain (JSON array); hashes one per line. Broken: `NF_ERR_VERIFY`.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_verify_consent_chain(
    records_json: *const u8,
    records_len: usize,
    out_hashes: *mut nf_buf,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (v, o) = unsafe {
            (
                json(records_json, records_len, "records_json")?,
                out(out_hashes, "out_hashes")?,
            )
        };
        let records = json_array(v, "records_json")?;
        put_buf(
            o,
            lines(v2::verify_consent_chain(&records).map_err(chain_err)?),
        );
        Ok(())
    })
}

/// Bare SHA-256 hex of a jurisdiction ruleset's public rules (hashing.md sec. 9.4).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_ruleset_content_sha256(
    rules_json: *const u8,
    rules_len: usize,
    out_hash: *mut nf_buf,
) -> nf_status {
    // SAFETY: forwarded contract.
    unsafe {
        doc_to_text(rules_json, rules_len, out_hash, |v| {
            Ok(v2::ruleset_content_sha256(v)?)
        })
    }
}

/// Label of a parameter-sweep variant of `base_pv_id` (hashing.md sec. 9.5).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_sweep_variant_label(
    base_pv_id: *const c_char,
    params_json: *const u8,
    params_len: usize,
    out_label: *mut nf_buf,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (base, v, o) = unsafe {
            (
                cstr(base_pv_id, "base_pv_id")?,
                json(params_json, params_len, "params_json")?,
                out(out_label, "out_label")?,
            )
        };
        put_buf(o, v2::sweep_variant_label(base, &v)?);
        Ok(())
    })
}

/// Bare SHA-256 hex identifying a training subject within a tenant (hashing.md sec. 9.6).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_training_subject_hash(
    tenant_id: *const c_char,
    subject_id: *const c_char,
    out_hash: *mut nf_buf,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (t, s, o) = unsafe {
            (
                cstr(tenant_id, "tenant_id")?,
                cstr(subject_id, "subject_id")?,
                out(out_hash, "out_hash")?,
            )
        };
        put_buf(o, v2::training_subject_hash(t, s)?);
        Ok(())
    })
}

fn strings(a: &Value, key: &str) -> Result<Vec<String>> {
    match a.get(key) {
        Some(Value::Array(items)) => items
            .iter()
            .map(|x| {
                x.as_str()
                    .map(str::to_owned)
                    .ok_or_else(|| Error::invalid(format!("{key} must hold strings")))
            })
            .collect(),
        _ => Err(Error::invalid(format!("{key} must be an array"))),
    }
}

fn string(a: &Value, key: &str) -> Result<String> {
    a.get(key)
        .and_then(Value::as_str)
        .map(str::to_owned)
        .ok_or_else(|| Error::invalid(format!("{key} must be a string")))
}

fn opt_string(a: &Value, key: &str) -> Result<Option<String>> {
    match a.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(s)) => Ok(Some(s.clone())),
        _ => Err(Error::invalid(format!("{key} must be null or a string"))),
    }
}

fn manifest_args(a: &Value) -> Result<TrainingManifestArgs> {
    let shards = match a.get("shards") {
        None | Some(Value::Null) => None,
        Some(Value::Object(m)) => Some(
            m.iter()
                .map(|(k, x)| match x {
                    Value::Int(n) => Ok((k.clone(), *n)),
                    _ => Err(Error::invalid("shard values must be integers")),
                })
                .collect::<Result<BTreeMap<String, i64>>>()?,
        ),
        _ => return Err(Error::invalid("shards must be null or an object")),
    };
    let n_source_recordings = match a.get("n_source_recordings") {
        Some(Value::Int(n)) => *n,
        _ => return Err(Error::invalid("n_source_recordings must be an integer")),
    };
    Ok(TrainingManifestArgs {
        tenant_id: string(a, "tenant_id")?,
        input_node_ids: strings(a, "input_node_ids")?,
        subject_hashes: strings(a, "subject_hashes")?,
        n_source_recordings,
        shards,
        excluded_subject_hashes: strings(a, "excluded_subject_hashes")?,
        pipeline_version_ids: strings(a, "pipeline_version_ids")?,
        code_commit: string(a, "code_commit")?,
        recipe: opt_string(a, "recipe")?,
        parent_version_id: opt_string(a, "parent_version_id")?,
        weights_source: opt_string(a, "weights_source")?,
    })
}

/// Build a training manifest (hashing.md sec. 9.7) from a JSON object with the members
/// `tenant_id`, `input_node_ids`, `subject_hashes`, `n_source_recordings`, `shards` (object or
/// null), `excluded_subject_hashes`, `pipeline_version_ids`, `code_commit`, `recipe` and
/// `parent_version_id` (string or null), and the optional `weights_source` (`"platform"` or
/// `"upload"`; absent or null leaves the member out, so older manifests keep their digests).
/// `out_manifest` receives the canonical JSON.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_training_manifest_build(
    args_json: *const u8,
    args_len: usize,
    out_manifest: *mut nf_buf,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (a, o) = unsafe {
            (
                json(args_json, args_len, "args_json")?,
                out(out_manifest, "out_manifest")?,
            )
        };
        let doc = v2::training_manifest(&manifest_args(&a)?)?;
        put_buf(o, cjson::to_canonical(&doc)?);
        Ok(())
    })
}

/// Bare SHA-256 hex digest of a training manifest document (hashing.md sec. 9.7).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_training_manifest_digest(
    manifest_json: *const u8,
    manifest_len: usize,
    out_digest: *mut nf_buf,
) -> nf_status {
    // SAFETY: forwarded contract.
    unsafe {
        doc_to_text(manifest_json, manifest_len, out_digest, |v| {
            Ok(v2::training_manifest_digest(v)?)
        })
    }
}

unsafe fn pairs(p: *const f64, n: usize, what: &str) -> Result<Vec<(f64, f64)>> {
    let len = n
        .checked_mul(2)
        .ok_or_else(|| Error::new(NF_ERR_INVALID_ARG, format!("{what} count overflows")))?;
    // SAFETY: the caller passes 2 * n doubles (header contract).
    let flat = unsafe { slice(p, len, what) }?;
    Ok(flat
        .as_chunks::<2>()
        .0
        .iter()
        .map(|c| (c[0], c[1]))
        .collect())
}

/// Timing hash of a stream chunk (hashing.md sec. 10.1): `lsl_timestamps` has `n_timestamps`
/// doubles; `clock_offsets` and `local_clock` are flat pairs (`2 * n` doubles each).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_timing_sha256(
    lsl_timestamps: *const f64,
    n_timestamps: usize,
    clock_offsets: *const f64,
    n_clock_offsets: usize,
    local_clock: *const f64,
    n_local_clock: usize,
    out_hash: *mut nf_buf,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (ts, off, loc, o) = unsafe {
            (
                slice(lsl_timestamps, n_timestamps, "lsl_timestamps")?,
                pairs(clock_offsets, n_clock_offsets, "clock_offsets")?,
                pairs(local_clock, n_local_clock, "local_clock")?,
                out(out_hash, "out_hash")?,
            )
        };
        put_buf(o, v2::timing_sha256(ts, &off, &loc));
        Ok(())
    })
}

// ---------------------------------------------------------------- v2 (sec. 10): Ed25519 verification
/// The chunk fields a stream-chunk signature covers (hashing.md sec. 10.1). Pairs are flat
/// `(a, b)` doubles: `clock_offsets` = (collection_time, offset), `local_clock` =
/// (lsl_time, monotonic_time).
#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct nf_stream_chunk_fields {
    pub stream_id: *const c_char,
    pub seq: u64,
    pub n_samples: u32,
    pub n_channels: u32,
    pub chunk_id: *const c_char,
    pub lsl_timestamps: *const f64,
    pub n_timestamps: usize,
    pub clock_offsets: *const f64,
    pub n_clock_offsets: usize,
    pub local_clock: *const f64,
    pub n_local_clock: usize,
}

/// Verify a stream-chunk signature (64 bytes) against a 32-byte Ed25519 public key.
/// `*out_valid` is set; a bad signature is not an error.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_verify_stream_chunk(
    fields: *const nf_stream_chunk_fields,
    signature: *const u8,
    signature_len: usize,
    public_key: *const u8,
    out_valid: *mut bool,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (f, sig, pk, o) = unsafe {
            (
                crate::handle(fields, "fields")?,
                slice(signature, signature_len, "signature")?,
                self::public_key(public_key)?,
                out(out_valid, "out_valid")?,
            )
        };
        // SAFETY: header contract for the pointers inside `fields`.
        let (sid, cid, ts, off, loc) = unsafe {
            (
                cstr(f.stream_id, "fields.stream_id")?,
                cstr(f.chunk_id, "fields.chunk_id")?,
                slice(f.lsl_timestamps, f.n_timestamps, "fields.lsl_timestamps")?,
                pairs(f.clock_offsets, f.n_clock_offsets, "fields.clock_offsets")?,
                pairs(f.local_clock, f.n_local_clock, "fields.local_clock")?,
            )
        };
        let c = StreamChunkFields {
            stream_id: sid,
            seq: f.seq,
            n_samples: f.n_samples,
            n_channels: f.n_channels,
            chunk_id: cid,
            lsl_timestamps: ts,
            clock_offsets: &off,
            local_clock: &loc,
        };
        *o = v2::verify_stream_chunk(&c, sig, &pk);
        Ok(())
    })
}

/// Parse and verify a device token (hashing.md sec. 10.2) at `now_unix_s`: signature, lifetime at
/// most 600 s, validity within the 30 s leeway. On success `out_claims` (may be NULL) receives
/// the canonical claims JSON; any failure is `NF_ERR_VERIFY`.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_verify_device_token(
    token: *const c_char,
    public_key: *const u8,
    now_unix_s: i64,
    out_claims: *mut nf_buf,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (t, pk) = unsafe { (cstr(token, "token")?, self::public_key(public_key)?) };
        let claims = v2::verify_device_token(t, &pk, now_unix_s).map_err(chain_err)?;
        // SAFETY: NULL or writable.
        if let Some(o) = unsafe { crate::opt_out(out_claims, "out_claims") }? {
            put_buf(o, cjson::to_canonical(&claims)?);
        }
        Ok(())
    })
}

/// Verify an Ed25519 signature over a provenance batch ID (hashing.md sec. 10.3).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_verify_provb_signature(
    batch_id: *const c_char,
    signature: *const u8,
    signature_len: usize,
    public_key: *const u8,
    out_valid: *mut bool,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (id, sig, pk, o) = unsafe {
            (
                cstr(batch_id, "batch_id")?,
                slice(signature, signature_len, "signature")?,
                self::public_key(public_key)?,
                out(out_valid, "out_valid")?,
            )
        };
        *o = v2::verify_provb_signature(id, sig, &pk);
        Ok(())
    })
}

unsafe fn verify_doc(
    p: *const u8,
    len: usize,
    public_key: *const u8,
    out_valid: *mut bool,
    f: impl FnOnce(&Value, &[u8; 32]) -> bool,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (v, pk, o) = unsafe {
            (
                json(p, len, "json")?,
                self::public_key(public_key)?,
                out(out_valid, "out_valid")?,
            )
        };
        *o = f(&v, &pk);
        Ok(())
    })
}

/// Verify a signed provenance or consent chain-head anchor document (hashing.md sec. 10.4).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_verify_anchor(
    anchor_json: *const u8,
    anchor_len: usize,
    public_key: *const u8,
    out_valid: *mut bool,
) -> nf_status {
    // SAFETY: forwarded contract.
    unsafe {
        verify_doc(
            anchor_json,
            anchor_len,
            public_key,
            out_valid,
            v2::verify_anchor,
        )
    }
}

/// Verify a signed deletion certificate document (hashing.md sec. 10.5).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_verify_certificate(
    certificate_json: *const u8,
    certificate_len: usize,
    public_key: *const u8,
    out_valid: *mut bool,
) -> nf_status {
    // SAFETY: forwarded contract.
    unsafe {
        verify_doc(
            certificate_json,
            certificate_len,
            public_key,
            out_valid,
            v2::verify_certificate,
        )
    }
}
