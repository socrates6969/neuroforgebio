//! wasm-bindgen surface for the `/arena` page.
//!
//! Verified: `cargo check -p arena-core --features wasm --target wasm32-unknown-unknown`
//! passes. `wasm-bindgen-cli 0.2.129` (matching `Cargo.lock`) is now installed (lead-approved,
//! 2026-09-27). NOT yet verified: actually running `wasm-bindgen` to produce the `.wasm` + JS
//! glue bundle and wiring it into `apps/web/src/pages/arena/index.astro` -- that's the next
//! heavy-lane job (see docs/hive/ARENA-DESIGN.md), not done in this pass.

use crate::data::Dataset;
use crate::decoders::{Decoder, GruReservoirDecoder, KalmanDecoder, RidgeDecoder};
use crate::eval::{EvaluationCard, PositionEvaluationCard};
use crate::mc_rtt;
use wasm_bindgen::prelude::*;

/// Decoder choice + hyperparameters, as picked by the visitor in the page UI.
#[derive(serde::Deserialize)]
struct DecoderChoice {
    kind: String, // "ridge" | "kalman" | "gru_reservoir"
    ridge_lambda: Option<f64>,
    gru_hidden_dim: Option<usize>,
    gru_seed: Option<u64>,
}

fn build_decoder(choice: &DecoderChoice) -> Box<dyn Decoder> {
    match choice.kind.as_str() {
        "kalman" => Box::new(KalmanDecoder::new()),
        "gru_reservoir" => Box::new(GruReservoirDecoder::new(
            choice.gru_hidden_dim.unwrap_or(32),
            choice.gru_seed.unwrap_or(1),
            choice.ridge_lambda.unwrap_or(1.0),
        )),
        _ => Box::new(RidgeDecoder::new(choice.ridge_lambda.unwrap_or(1.0))),
    }
}

/// Generic entry point: `dataset_json` is already in this crate's own `Dataset` shape (a
/// single scalar label), `choice_json` encodes a [`DecoderChoice`]. Returns the
/// [`EvaluationCard`] as JSON. Kept for anything that isn't the MC_RTT position asset (e.g.
/// a future "paste your own data" mode); the page's actual default path is
/// [`run_mc_rtt_evaluation`] below.
#[wasm_bindgen]
pub fn run_evaluation(dataset_json: &str, choice_json: &str, seed: u64) -> Result<String, JsValue> {
    let dataset: Dataset =
        serde_json::from_str(dataset_json).map_err(|e| JsValue::from_str(&e.to_string()))?;
    let choice: DecoderChoice =
        serde_json::from_str(choice_json).map_err(|e| JsValue::from_str(&e.to_string()))?;
    let mut decoder = build_decoder(&choice);
    let card: EvaluationCard = crate::eval::evaluate(decoder.as_mut(), &dataset, 0.2, seed);
    serde_json::to_string(&card).map_err(|e| JsValue::from_str(&e.to_string()))
}

/// The page's real entry point: `asset_json` is the raw text of
/// `apps/web/src/assets/playground/mc-rtt-playground.json` (the page fetches/imports it as a
/// static asset and passes the text straight through -- this module never embeds or fetches
/// it itself). `n_units` selects a population size from the asset's fixed `unitOrder`;
/// `noise_level_index` an index into the asset's `noiseHz`; `choice_json` a [`DecoderChoice`].
/// Returns a [`PositionEvaluationCard`] (x, y and their mean R²) as JSON.
#[wasm_bindgen]
pub fn run_mc_rtt_evaluation(
    asset_json: &str,
    n_units: usize,
    noise_level_index: usize,
    choice_json: &str,
    seed: u64,
) -> Result<String, JsValue> {
    let dataset = mc_rtt::load_position_dataset(asset_json, n_units, noise_level_index)
        .map_err(|e| JsValue::from_str(&e.to_string()))?;
    let choice: DecoderChoice =
        serde_json::from_str(choice_json).map_err(|e| JsValue::from_str(&e.to_string()))?;
    let card: PositionEvaluationCard =
        crate::eval::evaluate_position(|| build_decoder(&choice), &dataset, 1.0 / 3.0, seed);
    serde_json::to_string(&card).map_err(|e| JsValue::from_str(&e.to_string()))
}
