//! A small "GRU-like" recurrent decoder.
//!
//! Honesty note (also in `docs/hive/ARENA-DESIGN.md`): this is a **fixed-gate GRU-
//! style reservoir** — the recurrent gating weights are random and fixed at construction,
//! never trained — with a **trained linear (ridge) readout** on the resulting hidden-state
//! trajectory. That is a real nonlinear decoder with memory, and it's cheap enough to run
//! at interactive latency in a browser, but it is not a fully backprop-trained GRU. The
//! Evaluation Card reports `decoder: "gru_reservoir"`, not "GRU", for exactly this reason.

use super::{Decoder, ridge_fit, ridge_predict};
use crate::data::{Dataset, Trial};
use nalgebra::DVector;
use rand::Rng;
use rand::SeedableRng;
use rand_chacha::ChaCha8Rng;

fn sigmoid(x: f64) -> f64 {
    1.0 / (1.0 + (-x).exp())
}

struct GruWeights {
    // input dim = n_channels, hidden dim = h
    w_z: Vec<Vec<f64>>,
    u_z: Vec<Vec<f64>>,
    w_r: Vec<Vec<f64>>,
    u_r: Vec<Vec<f64>>,
    w_h: Vec<Vec<f64>>,
    u_h: Vec<Vec<f64>>,
}

fn rand_matrix(rng: &mut ChaCha8Rng, rows: usize, cols: usize, scale: f64) -> Vec<Vec<f64>> {
    (0..rows)
        .map(|_| (0..cols).map(|_| rng.gen_range(-scale..scale)).collect())
        .collect()
}

fn matvec(m: &[Vec<f64>], v: &[f64]) -> Vec<f64> {
    m.iter()
        .map(|row| row.iter().zip(v).map(|(a, b)| a * b).sum())
        .collect()
}

pub struct GruReservoirDecoder {
    hidden_dim: usize,
    seed: u64,
    lambda: f64,
    weights: Option<GruWeights>,
    readout: Option<DVector<f64>>,
}

impl GruReservoirDecoder {
    pub fn new(hidden_dim: usize, seed: u64, lambda: f64) -> Self {
        Self {
            hidden_dim,
            seed,
            lambda,
            weights: None,
            readout: None,
        }
    }

    fn ensure_weights(&mut self, n_channels: usize) {
        if self.weights.is_some() {
            return;
        }
        let mut rng = ChaCha8Rng::seed_from_u64(self.seed);
        let h = self.hidden_dim;
        // Small input scale, spectral-radius-ish shrink on recurrent weights so the
        // reservoir stays stable (doesn't blow up) without needing a full eigen-solve.
        let recurrent_scale = 0.9 / (h as f64).sqrt();
        self.weights = Some(GruWeights {
            w_z: rand_matrix(&mut rng, h, n_channels, 0.5),
            u_z: rand_matrix(&mut rng, h, h, recurrent_scale),
            w_r: rand_matrix(&mut rng, h, n_channels, 0.5),
            u_r: rand_matrix(&mut rng, h, h, recurrent_scale),
            w_h: rand_matrix(&mut rng, h, n_channels, 0.5),
            u_h: rand_matrix(&mut rng, h, h, recurrent_scale),
        });
    }

    /// Run the fixed-gate GRU recurrence over one trial's feature rows, returning the
    /// hidden-state trajectory (`h_t` for each time step).
    fn hidden_trajectory(&self, rows: &[Vec<f64>]) -> Vec<Vec<f64>> {
        let w = self.weights.as_ref().expect("weights not initialized");
        let h_dim = self.hidden_dim;
        let mut h_prev = vec![0.0; h_dim];
        let mut out = Vec::with_capacity(rows.len());
        for x_t in rows {
            let wz_x = matvec(&w.w_z, x_t);
            let uz_h = matvec(&w.u_z, &h_prev);
            let z: Vec<f64> = wz_x
                .iter()
                .zip(&uz_h)
                .map(|(a, b)| sigmoid(a + b))
                .collect();

            let wr_x = matvec(&w.w_r, x_t);
            let ur_h = matvec(&w.u_r, &h_prev);
            let r: Vec<f64> = wr_x
                .iter()
                .zip(&ur_h)
                .map(|(a, b)| sigmoid(a + b))
                .collect();

            let r_h: Vec<f64> = r.iter().zip(&h_prev).map(|(a, b)| a * b).collect();
            let wh_x = matvec(&w.w_h, x_t);
            let uh_rh = matvec(&w.u_h, &r_h);
            let h_candidate: Vec<f64> = wh_x
                .iter()
                .zip(&uh_rh)
                .map(|(a, b)| (a + b).tanh())
                .collect();

            let h_new: Vec<f64> = z
                .iter()
                .zip(&h_prev)
                .zip(&h_candidate)
                .map(|((zi, hp), hc)| (1.0 - zi) * hp + zi * hc)
                .collect();

            out.push(h_new.clone());
            h_prev = h_new;
        }
        out
    }
}

impl Decoder for GruReservoirDecoder {
    fn name(&self) -> &'static str {
        "gru_reservoir"
    }

    fn fit(&mut self, train: &Dataset) {
        let n_channels = train.trials.first().map(|t| t.n_channels()).unwrap_or(0);
        self.ensure_weights(n_channels);

        let mut hidden_rows = Vec::new();
        let mut y = Vec::new();
        for trial in &train.trials {
            let rows = trial.feature_rows();
            let hidden = self.hidden_trajectory(&rows);
            hidden_rows.extend(hidden);
            y.extend_from_slice(&trial.label);
        }
        self.readout = Some(ridge_fit(&hidden_rows, &y, self.lambda));
    }

    fn predict(&self, trial: &Trial) -> Vec<f64> {
        let readout = self
            .readout
            .as_ref()
            .expect("GruReservoirDecoder::predict called before fit");
        let rows = trial.feature_rows();
        let hidden = self.hidden_trajectory(&rows);
        ridge_predict(readout, &hidden)
    }
}
