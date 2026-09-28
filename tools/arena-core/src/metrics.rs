//! Scoring: R², percentile bootstrap confidence interval, shuffle-null significance.
//!
//! Same convention the BCI hive's harness lessons settled on: significance/"power" comes
//! from an empirical shuffle-null distribution, not an assumed closed-form power formula.

use rand::SeedableRng;
use rand::seq::SliceRandom;
use rand_chacha::ChaCha8Rng;

/// Coefficient of determination, R² = 1 - SS_res / SS_tot, pooled over all samples given.
/// Returns `None` if `y_true` has zero variance (R² is undefined; the caller should not
/// report a number in that case).
pub fn r2(y_true: &[f64], y_pred: &[f64]) -> Option<f64> {
    assert_eq!(y_true.len(), y_pred.len(), "length mismatch");
    if y_true.is_empty() {
        return None;
    }
    let mean = y_true.iter().sum::<f64>() / y_true.len() as f64;
    let ss_tot: f64 = y_true.iter().map(|y| (y - mean).powi(2)).sum();
    if ss_tot <= 0.0 {
        return None;
    }
    let ss_res: f64 = y_true
        .iter()
        .zip(y_pred)
        .map(|(y, p)| (y - p).powi(2))
        .sum();
    Some(1.0 - ss_res / ss_tot)
}

/// One held-out trial's true/predicted labels, kept together so resampling below can
/// resample whole trials (never individual samples — see `data::Dataset::block_split`).
pub struct TrialScore {
    pub y_true: Vec<f64>,
    pub y_pred: Vec<f64>,
}

fn pooled_r2(trials: &[&TrialScore]) -> Option<f64> {
    let y_true: Vec<f64> = trials
        .iter()
        .flat_map(|t| t.y_true.iter().copied())
        .collect();
    let y_pred: Vec<f64> = trials
        .iter()
        .flat_map(|t| t.y_pred.iter().copied())
        .collect();
    r2(&y_true, &y_pred)
}

/// Percentile bootstrap 95% CI on pooled R², resampling *trials* with replacement
/// (`n_resamples` times). Returns `None` if the point estimate itself is undefined, or if
/// too few resamples produced a defined R² to form an interval.
pub fn bootstrap_ci95(trials: &[TrialScore], seed: u64, n_resamples: usize) -> Option<(f64, f64)> {
    if trials.is_empty() {
        return None;
    }
    let mut rng = ChaCha8Rng::seed_from_u64(seed);
    let refs: Vec<&TrialScore> = trials.iter().collect();
    let mut samples = Vec::with_capacity(n_resamples);
    for _ in 0..n_resamples {
        let resample: Vec<&TrialScore> = (0..refs.len())
            .map(|_| *refs.choose(&mut rng).expect("non-empty"))
            .collect();
        if let Some(r) = pooled_r2(&resample) {
            samples.push(r);
        }
    }
    if samples.len() < n_resamples / 2 {
        return None; // too many degenerate resamples (e.g. near-constant labels) to trust
    }
    samples.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let lo_idx = ((samples.len() as f64) * 0.025).floor() as usize;
    let hi_idx = (((samples.len() as f64) * 0.975).ceil() as usize).min(samples.len() - 1);
    Some((samples[lo_idx], samples[hi_idx]))
}

/// Result of a shuffle-null significance test.
#[derive(Debug, Clone, Copy)]
pub struct ShuffleNull {
    pub observed_r2: f64,
    pub null_mean: f64,
    pub null_std: f64,
    /// One-sided empirical p-value: fraction of null draws with R² >= observed.
    pub p_value: f64,
    pub n_shuffles: usize,
}

/// Permute the *trial-level* label-to-prediction pairing (never within a trial) to build a
/// null distribution for R², then locate the observed R² against it. Permuting whole
/// trials, not samples, preserves each trial's internal autocorrelation under the null so
/// the test isn't itself leaking temporal structure.
pub fn shuffle_null(
    trials: &[TrialScore],
    observed_r2: f64,
    seed: u64,
    n_shuffles: usize,
) -> Option<ShuffleNull> {
    if trials.len() < 2 {
        return None; // need at least 2 trials to permute anything
    }
    let mut rng = ChaCha8Rng::seed_from_u64(seed ^ 0x5155_4145);
    let preds: Vec<&Vec<f64>> = trials.iter().map(|t| &t.y_pred).collect();
    let mut order: Vec<usize> = (0..trials.len()).collect();

    let mut null_samples = Vec::with_capacity(n_shuffles);
    for _ in 0..n_shuffles {
        order.shuffle(&mut rng);
        // Pair trial i's true label with a (possibly different) trial's prediction.
        // Skip pairings that happen to be length-mismatched (fixtures use fixed length,
        // but a real loader might not) by pooling only equal-length pairs.
        let mut y_true = Vec::new();
        let mut y_pred = Vec::new();
        for (i, &j) in order.iter().enumerate() {
            if trials[i].y_true.len() == preds[j].len() {
                y_true.extend_from_slice(&trials[i].y_true);
                y_pred.extend_from_slice(preds[j]);
            }
        }
        if let Some(r) = r2(&y_true, &y_pred) {
            null_samples.push(r);
        }
    }
    if null_samples.is_empty() {
        return None;
    }
    let n = null_samples.len();
    let null_mean = null_samples.iter().sum::<f64>() / n as f64;
    let null_var = null_samples
        .iter()
        .map(|r| (r - null_mean).powi(2))
        .sum::<f64>()
        / n as f64;
    let null_std = null_var.sqrt();
    let hits = null_samples.iter().filter(|&&r| r >= observed_r2).count();
    let p_value = (hits as f64 + 1.0) / (n as f64 + 1.0); // add-one, never exactly 0

    Some(ShuffleNull {
        observed_r2,
        null_mean,
        null_std,
        p_value,
        n_shuffles: n,
    })
}
