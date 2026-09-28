//! The planted-leak control: flags any input channel that is suspiciously, almost
//! perfectly correlated with the label at zero lag — the signature of a channel that
//! directly (or near-directly) encodes the answer rather than genuine neural signal.
//!
//! This is a heuristic, not a proof of leak-freedom: it catches the specific control this
//! page plants (`label + tiny noise`, see [`crate::fixtures::with_planted_leak`]) and
//! anything of similar severity. It does not by itself certify a dataset leak-free.

use crate::data::Dataset;

/// Above this |Pearson r|, a channel is flagged. Genuine neural channels in the fixtures
/// (gain-scaled, lagged, noisy views of the label) sit well below this; the planted leak
/// (`label + 1e-6` noise) sits essentially at 1.0.
pub const LEAK_CORRELATION_THRESHOLD: f64 = 0.98;

/// Per-channel leak-check result.
#[derive(Debug, Clone)]
pub struct ChannelLeakCheck {
    pub channel_index: usize,
    pub abs_correlation: f64,
    pub flagged: bool,
}

/// Zero-lag Pearson correlation between two equal-length series. `None` if either has zero
/// variance (correlation undefined).
fn pearson(a: &[f64], b: &[f64]) -> Option<f64> {
    assert_eq!(a.len(), b.len());
    let n = a.len() as f64;
    if n == 0.0 {
        return None;
    }
    let mean_a = a.iter().sum::<f64>() / n;
    let mean_b = b.iter().sum::<f64>() / n;
    let mut cov = 0.0;
    let mut var_a = 0.0;
    let mut var_b = 0.0;
    for (x, y) in a.iter().zip(b) {
        let da = x - mean_a;
        let db = y - mean_b;
        cov += da * db;
        var_a += da * da;
        var_b += db * db;
    }
    if var_a <= 0.0 || var_b <= 0.0 {
        return None;
    }
    Some(cov / (var_a.sqrt() * var_b.sqrt()))
}

/// Run the leak check over every channel, pooling all trials in `dataset` (a channel only
/// counts as leaking if it correlates this strongly across the whole dataset, not a fluke
/// in one trial).
pub fn check_dataset(dataset: &Dataset) -> Vec<ChannelLeakCheck> {
    if dataset.trials.is_empty() {
        return Vec::new();
    }
    let n_channels = dataset.trials[0].n_channels();
    let mut label_all = Vec::new();
    let mut channel_all: Vec<Vec<f64>> = vec![Vec::new(); n_channels];
    for trial in &dataset.trials {
        label_all.extend_from_slice(&trial.label);
        for (c, series) in trial.channels.iter().enumerate() {
            channel_all[c].extend_from_slice(series);
        }
    }

    (0..n_channels)
        .map(|c| {
            let r = pearson(&channel_all[c], &label_all).unwrap_or(0.0);
            let abs_correlation = r.abs();
            ChannelLeakCheck {
                channel_index: c,
                abs_correlation,
                flagged: abs_correlation > LEAK_CORRELATION_THRESHOLD,
            }
        })
        .collect()
}

/// True if any channel was flagged.
pub fn any_leak(checks: &[ChannelLeakCheck]) -> bool {
    checks.iter().any(|c| c.flagged)
}
