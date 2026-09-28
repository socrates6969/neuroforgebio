//! Loads the real, shipped MC_RTT asset (compiled into the test binary; no runtime I/O) and
//! runs the actual evaluation pipeline on it -- the only test in this crate against real
//! neural data rather than a synthetic fixture.

use arena_core::decoders::{Decoder, RidgeDecoder};
use arena_core::eval;
use arena_core::mc_rtt;

const ASSET_JSON: &str =
    include_str!("../../../apps/web/src/assets/playground/mc-rtt-playground.json");

#[test]
fn loads_and_validates_provenance() {
    let ds = mc_rtt::load_position_dataset(ASSET_JSON, 32, 0).expect("asset should parse");
    assert_eq!(ds.provenance.dandiset, "000129");
    assert_eq!(ds.provenance.licence, "CC-BY-4.0");
    assert_eq!(ds.provenance.n_units_used, 32);
    assert!(ds.provenance.n_units_total >= 32);
    assert_eq!(ds.provenance.noise_hz_used, 0.0);
    assert_eq!(ds.x.n_trials(), ds.y.n_trials());
    assert!(
        ds.x.n_trials() >= 2,
        "need at least 2 trials to split/score"
    );
}

#[test]
fn rejects_wrong_schema() {
    let bad = ASSET_JSON.replacen("nf-playground/2", "nf-playground/999", 1);
    let err = mc_rtt::load_position_dataset(&bad, 8, 0);
    assert!(
        err.is_err(),
        "a schema mismatch must be rejected, not silently parsed"
    );
}

#[test]
fn rejects_out_of_range_params() {
    assert!(mc_rtt::load_position_dataset(ASSET_JSON, 0, 0).is_err());
    assert!(mc_rtt::load_position_dataset(ASSET_JSON, 100_000, 0).is_err());
    assert!(mc_rtt::load_position_dataset(ASSET_JSON, 8, 100).is_err());
}

#[test]
fn real_data_runs_end_to_end_without_false_leak() {
    // 32 of 130 units, no injected noise -- a middling, fast-to-test configuration.
    let dataset = mc_rtt::load_position_dataset(ASSET_JSON, 32, 0).expect("parses");

    let card = eval::evaluate_position(
        || Box::new(RidgeDecoder::new(10.0)) as Box<dyn Decoder>,
        &dataset,
        1.0 / 3.0, // only 12 trials shipped; a 1/3 test split keeps >=1 trial each side
        7,
    );

    // Real spike counts should never trip the planted-leak heuristic (that's only meant to
    // catch a channel that IS the label, like the synthetic fixture in leak_control.rs).
    assert!(
        !card.x.leak_check.any_leak_detected,
        "x axis: {:?}",
        card.x.leak_check
    );
    assert!(
        !card.y.leak_check.any_leak_detected,
        "y axis: {:?}",
        card.y.leak_check
    );

    // With only ~8 training trials this is not a claim about decode quality -- just that the
    // pipeline runs end to end and produces a finite, in-range number.
    if let Some(r2) = card.mean_r2 {
        assert!(r2.is_finite());
    }
}

#[test]
fn noise_levels_are_nested() {
    // A higher noise_level_index must never *remove* spikes relative to a lower one: total
    // spike counts pooled over all channels/trials/bins should be monotone non-decreasing.
    let mut totals = Vec::new();
    for level in 0..4 {
        let ds = mc_rtt::load_position_dataset(ASSET_JSON, 16, level).expect("parses");
        let total: f64 =
            ds.x.trials
                .iter()
                .flat_map(|t| t.channels.iter())
                .flat_map(|c| c.iter())
                .sum();
        totals.push(total);
    }
    for w in totals.windows(2) {
        assert!(
            w[1] >= w[0],
            "noise levels not nested: {:?} then {:?} (all totals: {:?})",
            w[0],
            w[1],
            totals
        );
    }
}
