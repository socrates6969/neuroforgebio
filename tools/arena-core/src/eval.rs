//! Orchestrates a decoder + dataset into a self-describing [`EvaluationCard`].

use crate::data::Dataset;
use crate::decoders::Decoder;
use crate::leak::{self, ChannelLeakCheck};
use crate::metrics::{self, ShuffleNull, TrialScore};
use serde::Serialize;

/// Exactly what [`evaluate`] computes, spelled out so the card is self-describing rather
/// than asking the viewer to trust an unlabeled number.
pub const SCORING_CONVENTION: &str = "R^2 pooled over held-out trials from a block-wise \
(whole-trial) train/test split, never a per-sample shuffle; 95% CI is a percentile \
bootstrap resampling held-out trials; significance is an empirical one-sided p-value \
against a trial-level label-shuffle null.";

#[derive(Debug, Clone, Serialize)]
pub struct LeakCheckSummary {
    pub any_leak_detected: bool,
    pub threshold: f64,
    pub flagged_channels: Vec<usize>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ShuffleNullSummary {
    pub observed_r2: f64,
    pub null_mean: f64,
    pub null_std: f64,
    pub p_value: f64,
    pub n_shuffles: usize,
}

impl From<ShuffleNull> for ShuffleNullSummary {
    fn from(s: ShuffleNull) -> Self {
        Self {
            observed_r2: s.observed_r2,
            null_mean: s.null_mean,
            null_std: s.null_std,
            p_value: s.p_value,
            n_shuffles: s.n_shuffles,
        }
    }
}

/// The signed Evaluation Card shown to the visitor.
#[derive(Debug, Clone, Serialize)]
pub struct EvaluationCard {
    pub decoder: &'static str,
    pub n_train_trials: usize,
    pub n_test_trials: usize,
    pub r2: Option<f64>,
    pub r2_ci_95: Option<(f64, f64)>,
    pub leak_check: LeakCheckSummary,
    pub shuffle_null: Option<ShuffleNullSummary>,
    pub scoring_convention: &'static str,
}

/// Run the leak check, fit `decoder` on a block-wise train split of `dataset`, score it on
/// the held-out block, and package everything into an [`EvaluationCard`].
///
/// The leak check runs over the **whole** dataset (train + test pooled) because a leak is a
/// property of a channel, not of a particular split; it must be flagged regardless of which
/// trials end up on which side.
pub fn evaluate(
    decoder: &mut dyn Decoder,
    dataset: &Dataset,
    test_fraction: f64,
    seed: u64,
) -> EvaluationCard {
    let leak_checks: Vec<ChannelLeakCheck> = leak::check_dataset(dataset);
    let leak_summary = LeakCheckSummary {
        any_leak_detected: leak::any_leak(&leak_checks),
        threshold: leak::LEAK_CORRELATION_THRESHOLD,
        flagged_channels: leak_checks
            .iter()
            .filter(|c| c.flagged)
            .map(|c| c.channel_index)
            .collect(),
    };

    let (train, test) = dataset.block_split(test_fraction);
    decoder.fit(&train);

    let trial_scores: Vec<TrialScore> = test
        .trials
        .iter()
        .map(|trial| TrialScore {
            y_true: trial.label.clone(),
            y_pred: decoder.predict(trial),
        })
        .collect();

    let pooled_true: Vec<f64> = trial_scores
        .iter()
        .flat_map(|t| t.y_true.iter().copied())
        .collect();
    let pooled_pred: Vec<f64> = trial_scores
        .iter()
        .flat_map(|t| t.y_pred.iter().copied())
        .collect();
    let r2 = metrics::r2(&pooled_true, &pooled_pred);

    let r2_ci_95 = metrics::bootstrap_ci95(&trial_scores, seed, 1000);
    let shuffle_null = r2.and_then(|observed| {
        metrics::shuffle_null(&trial_scores, observed, seed, 1000).map(ShuffleNullSummary::from)
    });

    EvaluationCard {
        decoder: decoder.name(),
        n_train_trials: train.n_trials(),
        n_test_trials: test.n_trials(),
        r2,
        r2_ci_95,
        leak_check: leak_summary,
        shuffle_null,
        scoring_convention: SCORING_CONVENTION,
    }
}

/// A 2D position (e.g. cursor x/y) evaluation: `x` and `y` are scored independently (this
/// crate has no vector-label decoder), `mean_r2` averages the two point estimates -- the
/// same convention `tools/playground/nf_playground/decoders.py::r2_score` uses for its
/// headline number. The same `decoder` (same hyperparameters, re-fit per axis) is used for
/// both axes so the comparison is apples to apples.
#[derive(Debug, Clone, Serialize)]
pub struct PositionEvaluationCard {
    pub x: EvaluationCard,
    pub y: EvaluationCard,
    pub mean_r2: Option<f64>,
}

/// Run [`evaluate`] independently on `x` and `y` (same decoder constructor, same split
/// fraction and seed for both, so the two axes see the same train/test trial partition).
/// `new_decoder` is a factory rather than a single instance because each axis needs its own
/// fitted decoder state.
pub fn evaluate_position(
    mut new_decoder: impl FnMut() -> Box<dyn Decoder>,
    dataset: &crate::mc_rtt::PositionDataset,
    test_fraction: f64,
    seed: u64,
) -> PositionEvaluationCard {
    let mut dx = new_decoder();
    let x = evaluate(dx.as_mut(), &dataset.x, test_fraction, seed);
    let mut dy = new_decoder();
    let y = evaluate(dy.as_mut(), &dataset.y, test_fraction, seed);
    let mean_r2 = match (x.r2, y.r2) {
        (Some(a), Some(b)) => Some((a + b) / 2.0),
        _ => None,
    };
    PositionEvaluationCard { x, y, mean_r2 }
}
