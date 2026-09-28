//! arena-core: leak-proof decoder evaluation for the "Decoder Arena" page.
//!
//! | Module | What |
//! |---|---|
//! | [`data`] | `Trial`/`Dataset` types and a block-wise train/test split |
//! | [`fixtures`] | synthetic fixtures with known ground truth, used by this crate's own
//!   decoder/leak tests |
//! | [`mc_rtt`] | parses the Neural Playground's precomputed MC_RTT/DANDI-000129 asset
//!   (`feature/neural-playground`, merged 2026-09-27) into [`data::Dataset`]s |
//! | [`decoders`] | ridge, Kalman, and a small GRU-style reservoir decoder |
//! | [`metrics`] | R², percentile bootstrap CI, shuffle-null significance |
//! | [`leak`] | the planted-leak control: per-channel zero-lag correlation check |
//! | [`eval`] | orchestrates a decoder + dataset into a signed [`eval::EvaluationCard`], and
//!   a decoder + x/y position dataset into a [`eval::PositionEvaluationCard`] |
//!
//! No I/O, no network, no hardware. Pure computation over in-memory data, so it can compile
//! to `wasm32-unknown-unknown` (feature `wasm`) and run entirely in a visitor's browser.

pub mod data;
pub mod decoders;
pub mod eval;
pub mod fixtures;
pub mod leak;
pub mod mc_rtt;
pub mod metrics;

#[cfg(feature = "wasm")]
pub mod wasm;

pub use data::{Dataset, Trial};
pub use eval::{EvaluationCard, evaluate};
