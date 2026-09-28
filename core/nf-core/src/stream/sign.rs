//! Device identity, device tokens (SEC-016) and chunk signatures (SEC-040, SEC-094), matching
//! the server rules in `nf_platform/ingest/stream/protocol.py`:
//!
//! - chunk signing payload: tag `nf.stream-chunk.v1` 0x00 NF-CJSON of `{chunk_id, n_channels,
//!   n_clock_offsets, n_local_clock, n_samples, seq, stream_id, t_first, t_last, timing_sha256}`;
//!   `timing_sha256` covers the timestamps, clock-offset pairs and local-clock pairs (float64 LE).
//! - device token: `nfd1.<b64url(payload)>.<b64url(sig)>`, payload = NF-CJSON of `{aud,
//!   device_id, exp, iat, stream_id, tenant_id}`, signature over tag `nf.device-token.v1` 0x00
//!   payload; lifetime at most 600 s.
//!
//! The private key never leaves this type: there is no accessor for the secret. On Windows it
//! can be kept sealed with DPAPI ([`DeviceKey::load_or_create_sealed`]).

use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};

use ed25519_dalek::{Signer, SigningKey, Verifier, VerifyingKey};
use zeroize::Zeroizing;

use super::proto::Chunk;
use crate::cjson::{self, CanonError, Value};
use crate::ids::tagged_preimage;
use crate::sha256::to_hex;

pub const TAG_CHUNK_SIG: &str = crate::ids_v2::TAG_STREAM_CHUNK;
pub const TAG_DEVICE_TOKEN: &str = crate::ids_v2::TAG_DEVICE_TOKEN;
pub const TOKEN_PREFIX: &str = crate::ids_v2::DEVICE_TOKEN_PREFIX;
pub const TOKEN_AUDIENCE: &str = crate::ids_v2::DEVICE_TOKEN_AUDIENCE;
pub const AUTH_SCHEME: &str = "NFDevice";
pub const MAX_TOKEN_LIFETIME_S: u64 = 600;

pub struct DeviceKey(SigningKey);

impl std::fmt::Debug for DeviceKey {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "DeviceKey(public={})", to_hex(&self.public_key()))
    }
}

impl DeviceKey {
    pub fn generate() -> Self {
        let seed = super::keystore::random_key();
        Self(SigningKey::from_bytes(&seed))
    }

    /// Import an existing 32-byte Ed25519 seed (e.g. a key provisioned before the SDK).
    pub fn from_seed(seed: &[u8]) -> Option<Self> {
        let arr: Zeroizing<[u8; 32]> = Zeroizing::new(seed.try_into().ok()?);
        Some(Self(SigningKey::from_bytes(&arr)))
    }

    /// Windows: the seed is stored only in DPAPI-sealed form at `path` (created on first use).
    pub fn load_or_create_sealed(path: &Path) -> Result<Self, super::keystore::KeyError> {
        let seed = super::keystore::load_or_create_sealed(path)?;
        Ok(Self(SigningKey::from_bytes(&seed)))
    }

    pub fn public_key(&self) -> [u8; 32] {
        self.0.verifying_key().to_bytes()
    }

    pub fn sign(&self, msg: &[u8]) -> [u8; 64] {
        self.0.sign(msg).to_bytes()
    }
}

pub fn verify(public_key: &[u8; 32], msg: &[u8], sig: &[u8]) -> bool {
    let Ok(vk) = VerifyingKey::from_bytes(public_key) else {
        return false;
    };
    let Ok(sig) = ed25519_dalek::Signature::from_slice(sig) else {
        return false;
    };
    vk.verify(msg, &sig).is_ok()
}

pub use crate::ids_v2::timing_sha256;

/// Bytes the device signs for `chunk` (hashing spec v2 §10.1, built by [`crate::ids_v2`]).
pub fn signing_payload(c: &Chunk) -> Result<Vec<u8>, CanonError> {
    let offsets: Vec<(f64, f64)> = c
        .clock_offsets
        .iter()
        .map(|o| (o.collection_time, o.offset))
        .collect();
    let local: Vec<(f64, f64)> = c
        .local_clock
        .iter()
        .map(|l| (l.lsl_time, l.monotonic_time))
        .collect();
    crate::ids_v2::stream_chunk_preimage(&crate::ids_v2::StreamChunkFields {
        stream_id: &c.stream_id,
        seq: c.seq,
        n_samples: c.n_samples,
        n_channels: c.n_channels,
        chunk_id: &c.chunk_id,
        lsl_timestamps: &c.lsl_timestamps,
        clock_offsets: &offsets,
        local_clock: &local,
    })
}

pub fn sign_chunk(c: &mut Chunk, key: &DeviceKey) -> Result<(), CanonError> {
    c.signature = key.sign(&signing_payload(c)?).to_vec();
    Ok(())
}

/// Checks the signature only. The signature covers `chunk_id` but not the sample bytes, so this
/// alone does NOT prove the payload is intact: use [`verify_chunk_full`] for received chunks.
pub fn verify_chunk(c: &Chunk, public_key: &[u8; 32]) -> bool {
    signing_payload(c).is_ok_and(|p| verify(public_key, &p, &c.signature))
}

/// Signature check plus payload integrity (M9): `chunk_id` is recomputed from `dtype`,
/// `(n_samples, n_channels)` and `samples` (hashing spec section 5.2) and must equal the signed one.
pub fn verify_chunk_full(c: &Chunk, public_key: &[u8; 32]) -> bool {
    let Ok(dtype) = crate::ids::Dtype::parse(&c.dtype) else {
        return false;
    };
    let shape = [u64::from(c.n_samples), u64::from(c.n_channels)];
    crate::ids::chunk_id(dtype, &shape, &c.samples).is_ok_and(|id| id == c.chunk_id)
        && verify_chunk(c, public_key)
}

/// Unix seconds now.
pub fn unix_now() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

/// A short-lived token bound to one stream.
pub fn make_device_token(
    key: &DeviceKey,
    tenant_id: &str,
    device_id: &str,
    stream_id: &str,
    lifetime_s: u64,
    now: u64,
) -> Result<String, CanonError> {
    if lifetime_s == 0 || lifetime_s > MAX_TOKEN_LIFETIME_S {
        return Err(CanonError::Invalid(
            "token lifetime must be 1..=600 s".into(),
        ));
    }
    let iat = i64::try_from(now).map_err(|_| CanonError::UnsafeInteger)?;
    let payload = cjson::to_canonical(&Value::obj([
        ("aud", Value::str(TOKEN_AUDIENCE)),
        ("device_id", Value::str(device_id)),
        ("exp", Value::Int(iat + lifetime_s as i64)),
        ("iat", Value::Int(iat)),
        ("stream_id", Value::str(stream_id)),
        ("tenant_id", Value::str(tenant_id)),
    ]))?;
    let sig = key.sign(&tagged_preimage(TAG_DEVICE_TOKEN, &payload));
    Ok(format!(
        "{TOKEN_PREFIX}.{}.{}",
        crate::b64::encode_url(&payload),
        crate::b64::encode_url(&sig)
    ))
}

/// `authorization` metadata value for gRPC calls.
pub fn auth_header(token: &str) -> String {
    format!("{AUTH_SCHEME} {token}")
}
