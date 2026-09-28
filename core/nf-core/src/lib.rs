//! nf-core: the one place shared SDK logic lives (BLUEPRINT §5).
//!
//! | Module | What | Spec |
//! |---|---|---|
//! | [`cjson`] | NF-CJSON v1 canonical JSON (RFC 8785 + NFC), strict parser | `docs/spec/hashing.md` §3 |
//! | [`ids`] | content IDs: `blob`, `pv`, `chunk`, `provb` + chain verification | hashing.md §4-§5 |
//! | [`ids_v2`] | v2 registrations: `auditb`, prov-node, consent, ruleset, sweep, training subject/manifest hashes; stream-chunk, device-token, provb, anchor, certificate and WAL bytes (+ Ed25519 checks with `stream`) | hashing.md §8-§10 |
//! | [`model`] | data model types (Recording, Channel, Segment, ProvRecord, Run ...) | BLUEPRINT §4 |
//! | [`zarr`] | Zarr v3 chunk read/write for the `nf-signal/1` layout | `docs/spec/zarr-layout.md` |
//! | [`cache`] | content-addressed local chunk cache (hash-verified on read) | BLUEPRINT §5 |
//! | [`http`] | API client core: auth tokens, retry policy, problem+json, URL policy | BLUEPRINT §4, SEC-030 |
//! | [`prov`] | offline provenance recorder (local hash chain, synced later) | hashing.md §5.3 |
//! | [`durable`] | temp file + fsync + rename + parent-directory fsync | - |
//! | `stream` (feature) | encrypted write-ahead buffer, chunk building/signing, device tokens, sender | `proto/ingest/v1`, SEC-016/037/093/094 |
//!
//! Direction: data flows device -> SDK -> platform only. Nothing in this crate sends anything to
//! acquisition hardware (SEC-090/091; `tools/hw-guard` scans `core/`).

pub mod b64;
pub mod cache;
pub mod cjson;
pub mod durable;
pub mod http;
pub mod ids;
pub mod ids_v2;
pub mod model;
pub mod prov;
pub mod sha256;
#[cfg(feature = "stream")]
pub mod stream;
pub mod zarr;

pub use sha256::{Sha256, sha256, to_hex};

/// `sha256:<64 lowercase hex>` digest label of raw bytes (hashing.md §2).
pub fn content_id(bytes: &[u8]) -> String {
    format!("sha256:{}", to_hex(&sha256(bytes)))
}

/// Crate version (reported in provenance records and the User-Agent).
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

#[cfg(test)]
mod tests {
    #[test]
    fn content_id_prefix() {
        assert_eq!(
            super::content_id(b"abc"),
            "sha256:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        );
    }
}
