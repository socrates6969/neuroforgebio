//! Decoders: ridge regression, a linear Kalman filter, and a small GRU-style reservoir.
//! All three implement [`Decoder`] so [`crate::eval::evaluate`] can treat them uniformly.

pub mod gru;
pub mod kalman;
pub mod ridge;

use crate::data::{Dataset, Trial};
use nalgebra::{DMatrix, DVector};

pub use gru::GruReservoirDecoder;
pub use kalman::KalmanDecoder;
pub use ridge::RidgeDecoder;

/// A decoder: fit on training trials, then predict a per-time-step label for a held-out
/// trial. Fitting and predicting never see each other's data — [`crate::eval::evaluate`]
/// is responsible for keeping train/test separated at the trial level.
pub trait Decoder {
    fn name(&self) -> &'static str;
    fn fit(&mut self, train: &Dataset);
    fn predict(&self, trial: &Trial) -> Vec<f64>;
}

/// Closed-form ridge regression: `w = (X^T X + lambda I)^-1 X^T y`, on features `x_rows`
/// (one row per sample) against targets `y`. `x_rows` gets an implicit bias column
/// appended. Shared by [`ridge::RidgeDecoder`] and the reservoir readout in [`gru`].
pub(crate) fn ridge_fit(x_rows: &[Vec<f64>], y: &[f64], lambda: f64) -> DVector<f64> {
    let n = x_rows.len();
    assert_eq!(n, y.len(), "length mismatch");
    let d = x_rows.first().map(|r| r.len()).unwrap_or(0) + 1; // +1 bias
    let mut x = DMatrix::<f64>::zeros(n, d);
    for (i, row) in x_rows.iter().enumerate() {
        for (j, v) in row.iter().enumerate() {
            x[(i, j)] = *v;
        }
        x[(i, d - 1)] = 1.0; // bias column
    }
    let y_vec = DVector::<f64>::from_row_slice(y);
    let xt = x.transpose();
    let mut gram = &xt * &x;
    for k in 0..d {
        gram[(k, k)] += lambda;
    }
    let rhs = &xt * y_vec;
    gram.clone()
        .lu()
        .solve(&rhs)
        .unwrap_or_else(|| DVector::<f64>::zeros(d))
}

pub(crate) fn ridge_predict(w: &DVector<f64>, x_rows: &[Vec<f64>]) -> Vec<f64> {
    let d = w.len();
    x_rows
        .iter()
        .map(|row| {
            let mut acc = w[d - 1]; // bias
            for (j, v) in row.iter().enumerate() {
                acc += w[j] * v;
            }
            acc
        })
        .collect()
}
