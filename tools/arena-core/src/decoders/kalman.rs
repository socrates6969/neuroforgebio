//! Linear-Gaussian Kalman filter decoder, the classic BCI kinematic-decode setup.
//!
//! State `x_t = [position, velocity]`. Dynamics `x_{t+1} = A x_t + w_t` and observation
//! `z_t = H x_t + v_t` (`z_t` = the neural channels at time `t`). `A` and `H` are fit by
//! least squares from training trials; `Q` (process noise) and `R` (measurement noise) are
//! estimated from the residuals of those fits. Filtering only (no smoothing pass), which
//! is what a real-time/in-browser decoder would run.

use super::Decoder;
use crate::data::{Dataset, Trial};
use nalgebra::{DMatrix, DVector, Matrix2, Vector2};

pub struct KalmanDecoder {
    a: Matrix2<f64>,
    h: Option<DMatrix<f64>>, // n_channels x 2
    q: Matrix2<f64>,
    r: Option<DMatrix<f64>>, // n_channels x n_channels, diagonal
    n_channels: usize,
}

impl Default for KalmanDecoder {
    fn default() -> Self {
        Self::new()
    }
}

impl KalmanDecoder {
    pub fn new() -> Self {
        Self {
            a: Matrix2::identity(),
            h: None,
            q: Matrix2::identity() * 1e-3,
            r: None,
            n_channels: 0,
        }
    }

    fn state_trajectory(trial: &Trial) -> Vec<Vector2<f64>> {
        let n = trial.n_steps();
        let mut states = Vec::with_capacity(n);
        for t in 0..n {
            let pos = trial.label[t];
            let vel = if t == 0 {
                0.0
            } else {
                trial.label[t] - trial.label[t - 1]
            };
            states.push(Vector2::new(pos, vel));
        }
        states
    }
}

impl Decoder for KalmanDecoder {
    fn name(&self) -> &'static str {
        "kalman"
    }

    fn fit(&mut self, train: &Dataset) {
        assert!(!train.trials.is_empty(), "Kalman fit needs >=1 trial");
        self.n_channels = train.trials[0].n_channels();

        // --- Fit A: least squares x_{t+1} ~= A x_t, pooled over all trials/steps. ---
        let mut xt_rows = Vec::new();
        let mut xt1_rows = Vec::new();
        for trial in &train.trials {
            let states = Self::state_trajectory(trial);
            for t in 0..states.len().saturating_sub(1) {
                xt_rows.push(states[t]);
                xt1_rows.push(states[t + 1]);
            }
        }
        let n_pairs = xt_rows.len();
        if n_pairs >= 2 {
            let mut xt = DMatrix::<f64>::zeros(n_pairs, 2);
            let mut xt1 = DMatrix::<f64>::zeros(n_pairs, 2);
            for i in 0..n_pairs {
                xt[(i, 0)] = xt_rows[i][0];
                xt[(i, 1)] = xt_rows[i][1];
                xt1[(i, 0)] = xt1_rows[i][0];
                xt1[(i, 1)] = xt1_rows[i][1];
            }
            let xtxt = xt.transpose() * &xt + DMatrix::<f64>::identity(2, 2) * 1e-6;
            if let Some(inv) = xtxt.clone().try_inverse() {
                let a_est = inv * xt.transpose() * &xt1; // solves xt * A^T ~= xt1
                self.a = Matrix2::new(a_est[(0, 0)], a_est[(1, 0)], a_est[(0, 1)], a_est[(1, 1)]);
            }
            // Process noise from one-step-ahead residuals.
            let mut resid = [0.0; 2];
            let mut count = 0.0;
            for i in 0..n_pairs {
                let pred = self.a * xt_rows[i];
                let e = xt1_rows[i] - pred;
                resid[0] += e[0] * e[0];
                resid[1] += e[1] * e[1];
                count += 1.0;
            }
            if count > 0.0 {
                self.q = Matrix2::new(
                    (resid[0] / count).max(1e-6),
                    0.0,
                    0.0,
                    (resid[1] / count).max(1e-6),
                );
            }
        }

        // --- Fit H: least squares z_t ~= H x_t, pooled. ---
        let mut all_states = Vec::new();
        let mut all_channels: Vec<Vec<f64>> = Vec::new();
        for trial in &train.trials {
            let states = Self::state_trajectory(trial);
            let rows = trial.feature_rows();
            all_states.extend(states);
            all_channels.extend(rows);
        }
        let n = all_states.len();
        let mut x = DMatrix::<f64>::zeros(n, 2);
        let mut z = DMatrix::<f64>::zeros(n, self.n_channels);
        for i in 0..n {
            x[(i, 0)] = all_states[i][0];
            x[(i, 1)] = all_states[i][1];
            for c in 0..self.n_channels {
                z[(i, c)] = all_channels[i][c];
            }
        }
        let xtx = x.transpose() * &x + DMatrix::<f64>::identity(2, 2) * 1e-6;
        let h = if let Some(inv) = xtx.clone().try_inverse() {
            (inv * x.transpose() * &z).transpose() // n_channels x 2
        } else {
            DMatrix::<f64>::zeros(self.n_channels, 2)
        };

        // Measurement noise (diagonal) from residuals.
        let mut r_diag = vec![1e-3_f64; self.n_channels];
        for i in 0..n {
            let xi = Vector2::new(x[(i, 0)], x[(i, 1)]);
            let pred = &h * xi;
            for c in 0..self.n_channels {
                let e = z[(i, c)] - pred[c];
                r_diag[c] += e * e / n.max(1) as f64;
            }
        }
        let mut r = DMatrix::<f64>::zeros(self.n_channels, self.n_channels);
        for (c, v) in r_diag.into_iter().enumerate() {
            r[(c, c)] = v.max(1e-6);
        }

        self.h = Some(h);
        self.r = Some(r);
    }

    fn predict(&self, trial: &Trial) -> Vec<f64> {
        let h = self.h.as_ref().expect("KalmanDecoder::predict before fit");
        let r = self.r.as_ref().expect("KalmanDecoder::predict before fit");
        let rows = trial.feature_rows();

        let mut x_hat = Vector2::new(0.0, 0.0);
        let mut p = Matrix2::identity();
        let mut out = Vec::with_capacity(rows.len());

        for row in &rows {
            // Predict
            let x_pred = self.a * x_hat;
            let p_pred = self.a * p * self.a.transpose() + self.q;

            // Update
            let z = DVector::<f64>::from_row_slice(row);
            let z_pred = h * x_pred;
            let innovation = &z - &z_pred;
            let s = h * p_pred * h.transpose() + r; // n_channels x n_channels
            // Both arms have type Matrix<f64, Const<2>, Dyn, ..> (2 x n_channels); the
            // fallback multiplies by a zero matrix instead of `DMatrix::zeros(2, n)`
            // directly so the match arms agree on the static row dimension.
            let k = match s.clone().try_inverse() {
                Some(s_inv) => p_pred * h.transpose() * s_inv,
                None => {
                    p_pred * h.transpose() * DMatrix::<f64>::zeros(self.n_channels, self.n_channels)
                }
            };
            let correction = &k * &innovation;
            x_hat = x_pred + Vector2::new(correction[0], correction[1]);
            let kh = &k * h;
            p = (Matrix2::identity()
                - Matrix2::new(kh[(0, 0)], kh[(0, 1)], kh[(1, 0)], kh[(1, 1)]))
                * p_pred;

            out.push(x_hat[0]);
        }
        out
    }
}
