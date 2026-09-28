//! Synthetic fixtures with known ground truth, for this crate's own tests only.
//!
//! Real evaluation is meant to run against the Neural Playground's precomputed MC_RTT
//! (DANDI 000129) asset once `feature/neural-playground` merges (see
//! `docs/hive/ARENA-DESIGN.md`). Until then, these fixtures stand in — and for
//! testing a *leak detector* specifically, a synthetic fixture with a deliberately planted,
//! known leak is arguably the right tool regardless of what real data becomes available.

use crate::data::{Dataset, Trial};
use rand::Rng;
use rand::SeedableRng;
use rand_chacha::ChaCha8Rng;

/// A clean fixture: `n_trials` trials of `n_steps` steps, with `n_signal_channels` channels
/// that each carry a noisy, phase-shifted view of a smooth latent label signal, plus
/// `n_noise_channels` pure-noise channels that carry no information about the label.
/// No channel here is a leak (see [`with_planted_leak`] for that).
pub fn clean(
    seed: u64,
    n_trials: usize,
    n_steps: usize,
    n_signal_channels: usize,
    n_noise_channels: usize,
) -> Dataset {
    let mut rng = ChaCha8Rng::seed_from_u64(seed);
    let trials = (0..n_trials)
        .map(|_| make_trial(&mut rng, n_steps, n_signal_channels, n_noise_channels))
        .collect();
    Dataset { trials }
}

/// The same fixture as [`clean`], but with one extra channel defined as `label + tiny
/// noise` — a direct, deliberate leak. A leak-proof harness must flag this channel.
pub fn with_planted_leak(
    seed: u64,
    n_trials: usize,
    n_steps: usize,
    n_signal_channels: usize,
    n_noise_channels: usize,
) -> Dataset {
    let mut base = clean(seed, n_trials, n_steps, n_signal_channels, n_noise_channels);
    let mut rng = ChaCha8Rng::seed_from_u64(seed ^ 0xDEAD_BEEF);
    for trial in &mut base.trials {
        let leak: Vec<f64> = trial
            .label
            .iter()
            .map(|&y| y + rng.gen_range(-1e-6..1e-6))
            .collect();
        trial.channels.push(leak);
    }
    base
}

fn make_trial(
    rng: &mut ChaCha8Rng,
    n_steps: usize,
    n_signal_channels: usize,
    n_noise_channels: usize,
) -> Trial {
    // Smooth latent label: a sum of a couple of low-frequency sinusoids plus a random
    // walk component, so decoders with memory (Kalman, the GRU reservoir) have real
    // temporal structure to exploit and a purely instantaneous linear fit doesn't max out.
    let phase: f64 = rng.gen_range(0.0..std::f64::consts::TAU);
    let freq1 = 0.05;
    let freq2 = 0.013;
    let mut walk = 0.0_f64;
    let label: Vec<f64> = (0..n_steps)
        .map(|t| {
            walk += rng.gen_range(-0.02..0.02);
            (freq1 * t as f64 + phase).sin() + 0.5 * (freq2 * t as f64).cos() + 0.3 * walk
        })
        .collect();

    let mut channels = Vec::with_capacity(n_signal_channels + n_noise_channels);
    for c in 0..n_signal_channels {
        let gain = 0.6 + 0.4 * (c as f64 / (n_signal_channels.max(1) as f64));
        let lag = c % 3; // a small, varying lag so channels aren't all identical
        let ch: Vec<f64> = (0..n_steps)
            .map(|t| {
                let src_t = t.saturating_sub(lag);
                gain * label[src_t] + rng.gen_range(-0.3..0.3)
            })
            .collect();
        channels.push(ch);
    }
    for _ in 0..n_noise_channels {
        let ch: Vec<f64> = (0..n_steps).map(|_| rng.gen_range(-1.0..1.0)).collect();
        channels.push(ch);
    }

    Trial { channels, label }
}
