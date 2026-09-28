//! Test fixture shared by the Rust ABI tests and the C/C++ tests (via `examples/make_fixture.rs`):
//! a small `nf-signal/1` recording and a chunk cache with one entry. The C tests recompute the
//! same values from the formulas documented here.
#![allow(dead_code)]

use std::path::Path;

use nf_core::cache::ChunkCache;
use nf_core::ids::Dtype;
use nf_core::zarr::{self, FsStore};

pub const RECORDING_ID: &str = "rec-001";
pub const N_SAMPLES: u64 = 1000;
pub const CHANNELS: [&str; 3] = ["Fz", "Cz", "Pz"];
pub const SFREQ: f64 = 250.0;

/// Sample `i` of channel `c` (int16): `(i * 3 + c) % 2000 - 1000`.
pub fn sample(i: u64, c: u64) -> i16 {
    ((i * 3 + c) % 2000) as i16 - 1000
}

/// Timestamp of sample `i`: `100 + i / 250` seconds.
pub fn timestamp(i: u64) -> f64 {
    100.0 + i as f64 / SFREQ
}

/// Cached chunk: float32, shape [2, 3], values 0.5, 1.5, ..., 5.5.
pub fn chunk_values() -> Vec<f32> {
    (0..6).map(|k| k as f32 + 0.5).collect()
}

/// Write `<root>/rec-001` and `<root>/cache`; returns the cached chunk's ID.
pub fn write(root: &Path) -> String {
    let data: Vec<u8> = (0..N_SAMPLES)
        .flat_map(|i| (0..CHANNELS.len() as u64).flat_map(move |c| sample(i, c).to_le_bytes()))
        .collect();
    let ts: Vec<f64> = (0..N_SAMPLES).map(timestamp).collect();
    let names: Vec<String> = CHANNELS.iter().map(|s| (*s).to_owned()).collect();
    let units = vec!["uV".to_owned(); CHANNELS.len()];
    let mut store = FsStore::new(root);
    zarr::write_signal(
        &mut store,
        RECORDING_ID,
        &data,
        Dtype::Int16,
        N_SAMPLES,
        SFREQ,
        &names,
        &units,
        1.0,
        2,
        Some(&ts),
    )
    .expect("write recording");
    let bytes: Vec<u8> = chunk_values()
        .iter()
        .flat_map(|v| v.to_le_bytes())
        .collect();
    ChunkCache::open(root.join("cache"), 1 << 20)
        .expect("cache")
        .put(Dtype::Float32, &[2, 3], &bytes)
        .expect("put chunk")
}
