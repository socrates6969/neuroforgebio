//! Loader for the Neural Playground's precomputed MC_RTT asset (schema `nf-playground/2`,
//! `apps/web/src/assets/playground/mc-rtt-playground.json`, built by `tools/playground` from
//! DANDI 000129, CC-BY-4.0). This module only *parses* that JSON and bins raw spikes into
//! `Dataset`s; it never fetches, downloads, or reads a file itself (no I/O in this crate).
//!
//! Schema `/2` (2026-09-27, `tools/playground/nf_playground/encode.py`) is a lossless,
//! compact re-encoding of `/1`'s integer series as first-value-plus-differences (`truePos`
//! and every decoded path: per-coordinate deltas; `spikes[u]`: deltas of sorted spike times;
//! `noiseSpikes[u]`: `{"t": [deltas of ms], "l": "<one 1-9 digit per spike>"}` instead of flat
//! `[ms, level, ...]` pairs) -- nothing is rounded or dropped, `expand()` inverts `compact()`
//! exactly. This loader expands each trial back to `/1`'s absolute values immediately after
//! parsing (`expand_trial`), matching `apps/web/src/lib/playground-data.mjs`'s
//! `expandCompact()`; everything after that point works in absolute values exactly as before.
//!
//! Honesty note (also in docs/hive/ARENA-DESIGN.md): the shipped asset intentionally carries only the 12
//! representative test reaches used for `/playground`'s visualizations
//! (`method.shownTrials`), not the full 330 train / 100 test reaches the playground's own
//! headline R² numbers were computed from offline. A Decoder Arena run that fits and scores
//! on a block-split of these same 12 trials is therefore working with far less data than
//! `/playground` reports on — its R² is real (computed live, not replayed), but noisier and
//! not comparable to `/playground`'s numbers. The Evaluation Card must say so.

use crate::data::{Dataset, Trial};
use serde::Deserialize;

pub const EXPECTED_SCHEMA: &str = "nf-playground/2";

#[derive(Debug, Deserialize)]
struct RawDatasetInfo {
    #[serde(rename = "shortName")]
    short_name: String,
    dandiset: String,
    version: String,
    doi: String,
    licence: String,
    citation: String,
    sha256: String,
    units: usize,
}

#[derive(Debug, Deserialize)]
struct RawMethodInfo {
    #[serde(rename = "binMs")]
    bin_ms: u32,
}

/// Compact encoding of one unit's noise spikes: `noiseSpikes[u]` in schema `/2`, see the
/// module doc comment. `t` are the delta-encoded ms offsets, `l` one ASCII digit ('1'-'9')
/// per spike, same order.
#[derive(Debug, Deserialize)]
struct RawNoiseSpikeEnc {
    t: Vec<i64>,
    l: String,
}

#[derive(Debug, Deserialize)]
struct RawTrial {
    #[serde(rename = "durationMs")]
    duration_ms: u32,
    bins: u32,
    /// Delta-encoded per coordinate (schema `/2`); use [`expand_trial`], never this directly.
    #[serde(rename = "truePos")]
    true_pos: Vec<i64>,
    /// Delta-encoded per unit (schema `/2`); use [`expand_trial`], never this directly.
    spikes: Vec<Vec<i64>>,
    #[serde(rename = "noiseSpikes")]
    noise_spikes: Vec<RawNoiseSpikeEnc>,
}

/// One trial with every series expanded back to `/1`'s absolute values (see the module doc
/// comment); everything downstream of [`expand_trial`] works only in absolute values.
struct ExpandedTrial {
    duration_ms: u32,
    bins: u32,
    true_pos: Vec<i64>,
    spikes: Vec<Vec<i64>>,
    /// Per unit, flat `[ms0, level0, ms1, level1, ...]` pairs -- same shape `/1` used.
    noise_spikes: Vec<Vec<i64>>,
}

/// Inverse of `encode.py::delta`: first value absolute, each later value a delta from the
/// previous *output* value.
fn undelta(values: &[i64]) -> Vec<i64> {
    let mut out = Vec::with_capacity(values.len());
    for &v in values {
        out.push(if out.is_empty() {
            v
        } else {
            out[out.len() - 1] + v
        });
    }
    out
}

/// Inverse of `encode.py::delta_xy`: interleaved (x, y), each coordinate differenced against
/// its own previous *output* value (index `i-2`, not `i-1`).
fn undelta_xy(values: &[i64]) -> Vec<i64> {
    let mut out = Vec::with_capacity(values.len());
    for (i, &v) in values.iter().enumerate() {
        out.push(if i < 2 { v } else { out[i - 2] + v });
    }
    out
}

fn expand_trial(t: &RawTrial, ti: usize) -> Result<ExpandedTrial, McRttError> {
    let true_pos = undelta_xy(&t.true_pos);
    let spikes = t.spikes.iter().map(|s| undelta(s)).collect();
    let noise_spikes =
        t.noise_spikes
            .iter()
            .enumerate()
            .map(|(u, enc)| {
                let ms = undelta(&enc.t);
                if enc.l.chars().count() != ms.len() {
                    return Err(McRttError::Shape(format!(
                        "trial {ti} noiseSpikes[{u}]: t/l length mismatch ({} vs {})",
                        ms.len(),
                        enc.l.chars().count()
                    )));
                }
                let mut pairs = Vec::with_capacity(ms.len() * 2);
                for (i, c) in enc.l.chars().enumerate() {
                    let level = c.to_digit(10).filter(|d| (1..=9).contains(d)).ok_or_else(
                        || {
                            McRttError::Shape(format!(
                                "trial {ti} noiseSpikes[{u}]: level digit out of range 1-9: {c:?}"
                            ))
                        },
                    )?;
                    pairs.push(ms[i]);
                    pairs.push(level as i64);
                }
                Ok(pairs)
            })
            .collect::<Result<Vec<_>, _>>()?;
    Ok(ExpandedTrial {
        duration_ms: t.duration_ms,
        bins: t.bins,
        true_pos,
        spikes,
        noise_spikes,
    })
}

#[derive(Debug, Deserialize)]
struct RawAsset {
    schema: String,
    dataset: RawDatasetInfo,
    method: RawMethodInfo,
    #[serde(rename = "posScale")]
    pos_scale: f64,
    #[serde(rename = "noiseHz")]
    noise_hz: Vec<f64>,
    #[serde(rename = "unitOrder")]
    unit_order: Vec<usize>,
    trials: Vec<RawTrial>,
}

#[derive(Debug)]
pub enum McRttError {
    Json(String),
    Schema(String),
    Shape(String),
}

impl std::fmt::Display for McRttError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            McRttError::Json(m) => write!(f, "mc-rtt asset: invalid JSON: {m}"),
            McRttError::Schema(m) => write!(f, "mc-rtt asset: {m}"),
            McRttError::Shape(m) => write!(f, "mc-rtt asset: {m}"),
        }
    }
}
impl std::error::Error for McRttError {}

/// Provenance shown on the Evaluation Card, straight from the pinned DANDI asset.
#[derive(Debug, Clone, serde::Serialize)]
pub struct DatasetProvenance {
    pub short_name: String,
    pub dandiset: String,
    pub version: String,
    pub doi: String,
    pub licence: String,
    pub citation: String,
    pub sha256: String,
    pub n_units_total: usize,
    pub n_units_used: usize,
    pub n_trials: usize,
    pub bin_ms: u32,
    pub noise_hz_used: f64,
}

/// x and y are separate [`Dataset`]s over the *same* trials/channels; [`crate::eval`] scores
/// them independently (arena-core has no built-in notion of a vector-valued label), and the
/// page/tests average the two R²s the same way `tools/playground` does.
pub struct PositionDataset {
    pub x: Dataset,
    pub y: Dataset,
    pub provenance: DatasetProvenance,
}

/// Parse `json` (the raw asset text) and bin it into a [`PositionDataset`] using the first
/// `n_units` units of the asset's fixed random `unitOrder` (matching `/playground`'s own
/// population-size subsetting) and noise spikes up to `noise_level_index` into `noiseHz`.
///
/// Noise nesting: each stored noise spike carries the *lowest* noiseHz index at which a
/// uniform random draw would include it (`tools/playground/nf_playground/build.py::
/// noise_spikes`: a spike passes at level `r` when `key < r / max(noiseHz)`, and the
/// threshold only grows with `r`), so "lower levels are nested subsets of higher ones" means
/// a spike stored with level `L` is present at every requested index `>= L`. `noise_level_index
/// == 0` (noiseHz\[0\] == 0 Hz) always means no added spikes.
pub fn load_position_dataset(
    json: &str,
    n_units: usize,
    noise_level_index: usize,
) -> Result<PositionDataset, McRttError> {
    let raw: RawAsset = serde_json::from_str(json).map_err(|e| McRttError::Json(e.to_string()))?;
    if raw.schema != EXPECTED_SCHEMA {
        return Err(McRttError::Schema(format!(
            "expected schema {EXPECTED_SCHEMA}, got {}",
            raw.schema
        )));
    }
    let total_units = raw.dataset.units;
    if raw.unit_order.len() != total_units {
        return Err(McRttError::Shape(format!(
            "unitOrder has {} entries, dataset.units says {}",
            raw.unit_order.len(),
            total_units
        )));
    }
    if n_units == 0 || n_units > total_units {
        return Err(McRttError::Shape(format!(
            "n_units must be in 1..={total_units}, got {n_units}"
        )));
    }
    if raw.noise_hz.is_empty() || noise_level_index >= raw.noise_hz.len() {
        return Err(McRttError::Shape(format!(
            "noise_level_index must be < {}, got {noise_level_index}",
            raw.noise_hz.len()
        )));
    }
    if raw.trials.is_empty() {
        return Err(McRttError::Shape("no trials in asset".into()));
    }

    let active_units: Vec<usize> = raw.unit_order[..n_units].to_vec();
    let bin_ms = raw.method.bin_ms as i64;

    let mut x_trials = Vec::with_capacity(raw.trials.len());
    let mut y_trials = Vec::with_capacity(raw.trials.len());

    for (ti, raw_t) in raw.trials.iter().enumerate() {
        let t = expand_trial(raw_t, ti)?;
        let bins = t.bins as usize;
        if t.duration_ms as i64 != bins as i64 * bin_ms {
            return Err(McRttError::Shape(format!(
                "trial {ti}: durationMs != bins * binMs"
            )));
        }
        if t.true_pos.len() != 2 * bins {
            return Err(McRttError::Shape(format!(
                "trial {ti}: truePos length != 2 * bins"
            )));
        }
        if t.spikes.len() != total_units || t.noise_spikes.len() != total_units {
            return Err(McRttError::Shape(format!(
                "trial {ti}: spikes/noiseSpikes must list every unit"
            )));
        }

        let mut channels = Vec::with_capacity(active_units.len());
        for &u in &active_units {
            let mut counts = vec![0.0_f64; bins];
            bin_spike_times_ms(&t.spikes[u], bin_ms, bins, &mut counts);
            if noise_level_index > 0 {
                add_noise_counts(
                    &t.noise_spikes[u],
                    noise_level_index,
                    bin_ms,
                    bins,
                    &mut counts,
                );
            }
            channels.push(counts);
        }

        let mut label_x = Vec::with_capacity(bins);
        let mut label_y = Vec::with_capacity(bins);
        for b in 0..bins {
            label_x.push(t.true_pos[2 * b] as f64 / raw.pos_scale);
            label_y.push(t.true_pos[2 * b + 1] as f64 / raw.pos_scale);
        }

        x_trials.push(Trial {
            channels: channels.clone(),
            label: label_x,
        });
        y_trials.push(Trial {
            channels,
            label: label_y,
        });
    }

    let provenance = DatasetProvenance {
        short_name: raw.dataset.short_name,
        dandiset: raw.dataset.dandiset,
        version: raw.dataset.version,
        doi: raw.dataset.doi,
        licence: raw.dataset.licence,
        citation: raw.dataset.citation,
        sha256: raw.dataset.sha256,
        n_units_total: total_units,
        n_units_used: n_units,
        n_trials: x_trials.len(),
        bin_ms: raw.method.bin_ms,
        noise_hz_used: raw.noise_hz[noise_level_index],
    };

    Ok(PositionDataset {
        x: Dataset { trials: x_trials },
        y: Dataset { trials: y_trials },
        provenance,
    })
}

/// Half-open bins `[k*bin_ms, (k+1)*bin_ms)`, matching
/// `tools/playground/nf_playground/decoders.py::bin_spikes`.
fn bin_spike_times_ms(spike_times_ms: &[i64], bin_ms: i64, bins: usize, counts: &mut [f64]) {
    for &t in spike_times_ms {
        if t < 0 {
            continue;
        }
        let idx = (t / bin_ms) as usize;
        if idx < bins {
            counts[idx] += 1.0;
        }
    }
}

/// `noise_pairs` is a flat `[ms0, level0, ms1, level1, ...]` list (see [`load_position_dataset`]
/// doc comment for the nesting rule). Adds one count per included spike to the matching bin.
fn add_noise_counts(
    noise_pairs: &[i64],
    noise_level_index: usize,
    bin_ms: i64,
    bins: usize,
    counts: &mut [f64],
) {
    let mut i = 0;
    while i + 1 < noise_pairs.len() {
        let ms = noise_pairs[i];
        let level = noise_pairs[i + 1] as usize;
        if level <= noise_level_index && ms >= 0 {
            let idx = (ms / bin_ms) as usize;
            if idx < bins {
                counts[idx] += 1.0;
            }
        }
        i += 2;
    }
}
