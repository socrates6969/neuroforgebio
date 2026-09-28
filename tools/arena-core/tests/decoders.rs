//! Each decoder should recover real signal on the clean fixture: held-out R^2 well above
//! the shuffle-null mean, and CI excluding zero. These are sanity thresholds on a synthetic
//! fixture, not claims about real neural data (see docs/hive/ARENA-DESIGN.md).

use arena_core::decoders::{Decoder, GruReservoirDecoder, KalmanDecoder, RidgeDecoder};
use arena_core::{eval, fixtures};

fn assert_recovers_signal(mut decoder: Box<dyn Decoder>, seed: u64) {
    let dataset = fixtures::clean(seed, 24, 300, 5, 2);
    let card = eval::evaluate(decoder.as_mut(), &dataset, 0.25, seed);

    let r2 = card.r2.expect("R^2 should be defined on this fixture");
    assert!(
        r2 > 0.1,
        "{} R^2 too low on clean fixture: {:.4}",
        card.decoder,
        r2
    );

    let null = card
        .shuffle_null
        .expect("shuffle null should be computable with 24 trials");
    assert!(
        null.observed_r2 > null.null_mean + 2.0 * null.null_std,
        "{} R^2 ({:.4}) not clearly above shuffle-null (mean={:.4}, sd={:.4})",
        card.decoder,
        null.observed_r2,
        null.null_mean,
        null.null_std
    );
    assert!(
        null.p_value < 0.05,
        "{} shuffle-null p-value too high: {:.4}",
        card.decoder,
        null.p_value
    );

    assert!(
        !card.leak_check.any_leak_detected,
        "{} run flagged a leak on a clean fixture: {:?}",
        card.decoder, card.leak_check.flagged_channels
    );
}

#[test]
fn ridge_recovers_signal() {
    assert_recovers_signal(Box::new(RidgeDecoder::new(1.0)), 10);
}

#[test]
fn kalman_recovers_signal() {
    assert_recovers_signal(Box::new(KalmanDecoder::new()), 11);
}

#[test]
fn gru_reservoir_recovers_signal() {
    assert_recovers_signal(Box::new(GruReservoirDecoder::new(24, 42, 1.0)), 12);
}

#[test]
fn block_split_never_splits_a_trial() {
    let dataset = fixtures::clean(5, 10, 50, 3, 1);
    let (train, test) = dataset.block_split(0.3);
    assert_eq!(train.n_trials() + test.n_trials(), dataset.n_trials());
    assert!(train.n_trials() >= 1 && test.n_trials() >= 1);
}
