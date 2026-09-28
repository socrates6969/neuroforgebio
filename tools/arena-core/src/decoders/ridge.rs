//! Ridge regression decoder: one-shot linear fit, no memory across time steps.

use super::{Decoder, ridge_fit, ridge_predict};
use crate::data::{Dataset, Trial};
use nalgebra::DVector;

pub struct RidgeDecoder {
    lambda: f64,
    weights: Option<DVector<f64>>,
}

impl RidgeDecoder {
    pub fn new(lambda: f64) -> Self {
        Self {
            lambda,
            weights: None,
        }
    }
}

impl Decoder for RidgeDecoder {
    fn name(&self) -> &'static str {
        "ridge"
    }

    fn fit(&mut self, train: &Dataset) {
        let mut x_rows = Vec::new();
        let mut y = Vec::new();
        for trial in &train.trials {
            x_rows.extend(trial.feature_rows());
            y.extend_from_slice(&trial.label);
        }
        self.weights = Some(ridge_fit(&x_rows, &y, self.lambda));
    }

    fn predict(&self, trial: &Trial) -> Vec<f64> {
        let w = self
            .weights
            .as_ref()
            .expect("RidgeDecoder::predict called before fit");
        ridge_predict(w, &trial.feature_rows())
    }
}
