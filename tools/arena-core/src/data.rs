//! Trial/dataset types and the block-wise split.
//!
//! Deliberately asset-agnostic: nothing here knows about MC_RTT, DANDI, or any particular
//! recording format. A future loader maps the Neural Playground's precomputed asset onto
//! these types; until then, [`crate::fixtures`] builds them synthetically for tests.

use serde::{Deserialize, Serialize};

/// One trial: a fixed-length block of aligned neural-channel samples and a scalar label
/// per time step (e.g. one kinematic component). Trials are the unit of independence —
/// samples *within* a trial are correlated (firing-rate autocorrelation, kinematic
/// smoothness), samples *across* trials are treated as independent draws.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Trial {
    /// `channels[c][t]` = channel `c` at time step `t`.
    pub channels: Vec<Vec<f64>>,
    /// `label[t]` = the decoding target at time step `t`.
    pub label: Vec<f64>,
}

impl Trial {
    pub fn n_channels(&self) -> usize {
        self.channels.len()
    }

    pub fn n_steps(&self) -> usize {
        self.label.len()
    }

    /// `X[t] = [channels[0][t], ..., channels[C-1][t]]`, one row per time step.
    pub fn feature_rows(&self) -> Vec<Vec<f64>> {
        let n = self.n_steps();
        (0..n)
            .map(|t| self.channels.iter().map(|c| c[t]).collect())
            .collect()
    }
}

/// A collection of trials, always split and scored at trial granularity.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Dataset {
    pub trials: Vec<Trial>,
}

impl Dataset {
    pub fn n_trials(&self) -> usize {
        self.trials.len()
    }

    /// Deterministic block-wise train/test split: whole trials go to train or test, never
    /// split mid-trial, and the split is by trial *index* — never a per-sample shuffle.
    /// A per-sample split would leak temporally adjacent (and hence correlated) samples
    /// across the train/test boundary, inflating R² on any decoder with memory.
    ///
    /// `test_fraction` in `(0, 1)`; at least one trial is kept on each side when
    /// `n_trials >= 2`.
    pub fn block_split(&self, test_fraction: f64) -> (Dataset, Dataset) {
        assert!(
            test_fraction > 0.0 && test_fraction < 1.0,
            "test_fraction must be in (0, 1)"
        );
        let n = self.n_trials();
        let mut n_test = ((n as f64) * test_fraction).round() as usize;
        if n >= 2 {
            n_test = n_test.clamp(1, n - 1);
        }
        let n_train = n - n_test;
        let train = Dataset {
            trials: self.trials[..n_train].to_vec(),
        };
        let test = Dataset {
            trials: self.trials[n_train..].to_vec(),
        };
        (train, test)
    }
}
