//! Acquisition side: samples in, signed chunks into the write-ahead buffer. Never touches the
//! network, so a slow or unreachable server cannot block acquisition (SEC-093).

use std::sync::Arc;

use super::proto::{Chunk, ClockOffset, LocalClockSample};
use super::sign::{DeviceKey, sign_chunk};
use super::wal::{Wal, WalError};
use crate::ids::{self, Dtype};

/// Dtypes the stream protocol accepts (`proto/ingest/v1`: int16, int32, float32, float64).
pub const STREAM_DTYPES: [Dtype; 4] = [Dtype::Int16, Dtype::Int32, Dtype::Float32, Dtype::Float64];
/// Server limit on values per chunk (`MAX_VALUES_PER_CHUNK`).
pub const MAX_VALUES_PER_CHUNK: u64 = 1_000_000;
/// Shortest signed chunk of a regular-rate stream, in milliseconds (P7.7 R1: sign per >= 20 ms
/// chunk, never per 1 ms packet). Only the end-of-stream partial chunk ([`StreamWriter::flush`])
/// may be shorter, and it closes a timed writer.
pub const MIN_CHUNK_MS: f64 = 20.0;
/// Relative tolerance of the duration check (`chunk_samples * 1000 >= MIN_CHUNK_MS * sfreq`).
const DURATION_REL_TOL: f64 = 1e-9;
/// The error a timed writer returns for a push after a flush wrote the short final chunk.
pub const FLUSHED_MSG: &str = "writer flushed: open a new writer to continue";

#[derive(Debug)]
pub enum WriterError {
    Config(String),
    Input(String),
    Wal(WalError),
}

impl std::fmt::Display for WriterError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Config(m) => write!(f, "stream config: {m}"),
            Self::Input(m) => write!(f, "stream input: {m}"),
            Self::Wal(e) => write!(f, "{e}"),
        }
    }
}
impl std::error::Error for WriterError {}

#[derive(Debug, Clone)]
pub struct StreamConfig {
    pub stream_id: String,
    pub dtype: Dtype,
    pub n_channels: u32,
    /// Samples per chunk (the prototype used 100 = 100 ms at 1 kHz).
    pub chunk_samples: u32,
    /// Nominal sampling rate in Hz. `Some` (timed mode): [`StreamWriter::new`] refuses chunks
    /// shorter than [`MIN_CHUNK_MS`], and a flush that writes the short final chunk closes the
    /// writer. `None`: irregular-rate streams (no nominal rate, e.g. event markers) and legacy
    /// sample-count configs, which have no duration check.
    pub sfreq: Option<f64>,
}

impl StreamConfig {
    /// A regular-rate stream cut into chunks of at least `chunk_ms` milliseconds:
    /// `chunk_samples = ceil(chunk_ms * sfreq / 1000)` (ceil, so a chunk is never shorter than
    /// asked). Refuses a non-finite or non-positive `sfreq` (streams without a nominal rate use
    /// [`StreamConfig::irregular`]), a `chunk_ms` that is not finite or under [`MIN_CHUNK_MS`],
    /// and a chunk over [`MAX_VALUES_PER_CHUNK`] values: it never shrinks a chunk below 20 ms to
    /// fit the value cap.
    pub fn timed(
        stream_id: impl Into<String>,
        dtype: Dtype,
        n_channels: u32,
        sfreq: f64,
        chunk_ms: f64,
    ) -> Result<Self, WriterError> {
        if !sfreq.is_finite() || sfreq <= 0.0 {
            return Err(WriterError::Config(format!(
                "sfreq must be finite and > 0 Hz (got {sfreq}); streams without a nominal rate \
                 use an irregular config"
            )));
        }
        if !chunk_ms.is_finite() || chunk_ms < MIN_CHUNK_MS {
            return Err(WriterError::Config(format!(
                "chunk_ms must be finite and >= 20 ms (got {chunk_ms})"
            )));
        }
        let samples = (chunk_ms * sfreq / 1000.0).ceil();
        let values = samples * f64::from(n_channels);
        if samples > f64::from(u32::MAX) || values > MAX_VALUES_PER_CHUNK as f64 {
            return Err(WriterError::Config(format!(
                "{chunk_ms} ms at {sfreq} Hz x {n_channels} channels is {values} values, over \
                 the 1,000,000-value cap per chunk; chunks cannot be shorter than 20 ms, so use \
                 fewer channels per stream"
            )));
        }
        Ok(Self {
            stream_id: stream_id.into(),
            dtype,
            n_channels,
            // In range: 1 <= samples <= u32::MAX (sfreq > 0 and chunk_ms >= 20 give samples > 0).
            chunk_samples: samples as u32,
            sfreq: Some(sfreq),
        })
    }

    /// A stream without a nominal sampling rate (LSL `nominal_srate == 0`, e.g. event markers),
    /// chunked by sample count. Exempt from the [`MIN_CHUNK_MS`] floor: such a stream has no
    /// duration per sample, and it carries few samples.
    pub fn irregular(
        stream_id: impl Into<String>,
        dtype: Dtype,
        n_channels: u32,
        chunk_samples: u32,
    ) -> Self {
        Self {
            stream_id: stream_id.into(),
            dtype,
            n_channels,
            chunk_samples,
            sfreq: None,
        }
    }

    /// Chunk duration in milliseconds (`None` without a nominal rate).
    pub fn chunk_ms(&self) -> Option<f64> {
        self.sfreq
            .map(|f| f64::from(self.chunk_samples) * 1000.0 / f)
    }
}

/// Whether `chunk_samples` at `sfreq` Hz lasts at least [`MIN_CHUNK_MS`] (1e-9 relative
/// tolerance for the f64 comparison).
fn meets_min_duration(chunk_samples: u32, sfreq: f64) -> bool {
    f64::from(chunk_samples) * 1000.0 >= MIN_CHUNK_MS * sfreq * (1.0 - DURATION_REL_TOL)
}

#[derive(Debug, Clone, Default, PartialEq)]
pub struct WriterStats {
    pub chunks: u64,
    pub samples: u64,
    pub wal_peak: usize,
}

pub struct StreamWriter {
    cfg: StreamConfig,
    key: Arc<DeviceKey>,
    wal: Arc<Wal>,
    next_seq: u64,
    buf: Vec<u8>,
    ts: Vec<f64>,
    offsets: Vec<(f64, f64)>,
    local: Vec<(f64, f64)>,
    /// Timed mode only: set once a flush wrote the short final chunk.
    closed: bool,
    pub stats: WriterStats,
}

impl StreamWriter {
    /// Resumes after the highest seq the WAL ever held (a restarted client keeps its records, and a
    /// drained WAL does not restart numbering at 0: see [`Wal::next_seq`], H4).
    pub fn new(cfg: StreamConfig, key: Arc<DeviceKey>, wal: Arc<Wal>) -> Result<Self, WriterError> {
        if !STREAM_DTYPES.contains(&cfg.dtype) {
            return Err(WriterError::Config(format!(
                "dtype {} not accepted by the stream protocol",
                cfg.dtype.name()
            )));
        }
        if cfg.n_channels == 0 || cfg.chunk_samples == 0 {
            return Err(WriterError::Config(
                "n_channels and chunk_samples must be > 0".into(),
            ));
        }
        if u64::from(cfg.n_channels) * u64::from(cfg.chunk_samples) > MAX_VALUES_PER_CHUNK {
            return Err(WriterError::Config("chunk exceeds 1,000,000 values".into()));
        }
        if cfg.stream_id.is_empty() {
            return Err(WriterError::Config("stream_id is empty".into()));
        }
        if let Some(f) = cfg.sfreq {
            if !f.is_finite() || f <= 0.0 {
                return Err(WriterError::Config(format!(
                    "sfreq must be finite and > 0 Hz (got {f}); streams without a nominal rate \
                     use an irregular config"
                )));
            }
            if !meets_min_duration(cfg.chunk_samples, f) {
                return Err(WriterError::Config(format!(
                    "chunk shorter than 20 ms at {f} Hz ({} samples = {:.3} ms)",
                    cfg.chunk_samples,
                    f64::from(cfg.chunk_samples) * 1000.0 / f
                )));
            }
        }
        let next_seq = wal.next_seq();
        Ok(Self {
            cfg,
            key,
            wal,
            next_seq,
            buf: Vec::new(),
            ts: Vec::new(),
            offsets: Vec::new(),
            local: Vec::new(),
            closed: false,
            stats: WriterStats::default(),
        })
    }

    /// True once a timed writer's flush wrote the short final chunk; `push` is then refused.
    pub fn is_closed(&self) -> bool {
        self.closed
    }

    pub fn config(&self) -> &StreamConfig {
        &self.cfg
    }
    pub fn next_seq(&self) -> u64 {
        self.next_seq
    }
    pub fn buffered_samples(&self) -> usize {
        self.ts.len()
    }

    /// Record a clock-offset measurement (remote - local, LSL semantics). Stored unchanged with
    /// the next emitted chunk (SEC-094).
    pub fn add_clock_offset(&mut self, collection_time: f64, offset: f64) {
        self.offsets.push((collection_time, offset));
    }

    /// Record a (local LSL clock, OS monotonic clock) pair read at the same instant.
    pub fn add_local_clock(&mut self, lsl_time: f64, monotonic_time: f64) {
        self.local.push((lsl_time, monotonic_time));
    }

    /// Append `timestamps.len()` samples (`samples` = n x n_channels little-endian values, C
    /// order). Emits every full chunk; returns how many chunks were written to the WAL.
    pub fn push(&mut self, samples: &[u8], timestamps: &[f64]) -> Result<usize, WriterError> {
        if self.closed {
            return Err(WriterError::Input(FLUSHED_MSG.into()));
        }
        let row = self.cfg.n_channels as usize * self.cfg.dtype.itemsize();
        if samples.len() != timestamps.len() * row {
            return Err(WriterError::Input(
                "samples do not match timestamps x n_channels x dtype".into(),
            ));
        }
        if timestamps.iter().any(|t| !t.is_finite()) {
            return Err(WriterError::Input("timestamps must be finite".into()));
        }
        // Non-finite float samples are kept bit-exact (hashing spec §5.2); the server flags such
        // chunks as suspect (SEC-041) instead of the edge dropping data.
        self.buf.extend_from_slice(samples);
        self.ts.extend_from_slice(timestamps);
        let mut emitted = 0;
        let n = self.cfg.chunk_samples as usize;
        while self.ts.len() >= n {
            self.emit(n)?;
            emitted += 1;
        }
        Ok(emitted)
    }

    /// Emit the buffered partial chunk (end of acquisition). Returns whether one was written.
    ///
    /// `push` emits every full chunk at once, so a non-empty buffer here is always shorter than
    /// `chunk_samples`. In timed mode (`sfreq` set) that short chunk is the only one allowed
    /// under [`MIN_CHUNK_MS`], so writing it closes the writer: later pushes are refused and the
    /// caller opens a new writer to continue. A flush with an empty buffer writes nothing and
    /// does not close. Irregular/legacy writers (`sfreq == None`) stay open.
    pub fn flush(&mut self) -> Result<bool, WriterError> {
        if self.ts.is_empty() {
            return Ok(false);
        }
        // Closed even if the WAL write below fails: the buffer is already consumed by then.
        self.closed = self.cfg.sfreq.is_some();
        self.emit(self.ts.len())?;
        Ok(true)
    }

    fn emit(&mut self, n: usize) -> Result<(), WriterError> {
        let row = self.cfg.n_channels as usize * self.cfg.dtype.itemsize();
        let samples: Vec<u8> = self.buf.drain(..n * row).collect();
        let ts: Vec<f64> = self.ts.drain(..n).collect();
        let shape = [n as u64, u64::from(self.cfg.n_channels)];
        let chunk_id = ids::chunk_id(self.cfg.dtype, &shape, &samples)
            .map_err(|e| WriterError::Input(e.to_string()))?;
        let mut c = Chunk {
            stream_id: self.cfg.stream_id.clone(),
            seq: self.next_seq,
            n_samples: n as u32,
            n_channels: self.cfg.n_channels,
            dtype: self.cfg.dtype.name().to_owned(),
            samples,
            lsl_timestamps: ts,
            clock_offsets: self
                .offsets
                .drain(..)
                .map(|(a, b)| ClockOffset {
                    collection_time: a,
                    offset: b,
                })
                .collect(),
            local_clock: self
                .local
                .drain(..)
                .map(|(a, b)| LocalClockSample {
                    lsl_time: a,
                    monotonic_time: b,
                })
                .collect(),
            chunk_id,
            signature: vec![],
        };
        sign_chunk(&mut c, &self.key).map_err(|e| WriterError::Input(e.to_string()))?;
        self.wal
            .append(self.next_seq, &c.encode())
            .map_err(WriterError::Wal)?;
        self.next_seq += 1;
        self.stats.chunks += 1;
        self.stats.samples += n as u64;
        self.stats.wal_peak = self.stats.wal_peak.max(self.wal.len());
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use std::path::PathBuf;
    use std::sync::atomic::{AtomicU32, Ordering};

    use proptest::prelude::*;

    use super::*;
    use crate::stream::keystore::EphemeralKey;

    fn tmp_wal() -> (Arc<Wal>, PathBuf) {
        static N: AtomicU32 = AtomicU32::new(0);
        let d = std::env::temp_dir().join(format!(
            "nfcore-writer-{}-{}",
            std::process::id(),
            N.fetch_add(1, Ordering::SeqCst)
        ));
        let _ = std::fs::remove_dir_all(&d);
        let wal = Wal::open(&d, "s", &EphemeralKey::new(), false).unwrap();
        (Arc::new(wal), d)
    }

    /// Opens a writer on a throwaway WAL and reports only whether the config was accepted.
    fn check(cfg: StreamConfig) -> Result<(), String> {
        let (wal, d) = tmp_wal();
        let r = StreamWriter::new(cfg, Arc::new(DeviceKey::generate()), wal)
            .map(drop)
            .map_err(|e| e.to_string());
        let _ = std::fs::remove_dir_all(&d);
        r
    }

    fn timed(sfreq: f64, chunk_ms: f64) -> Result<StreamConfig, WriterError> {
        StreamConfig::timed("s", Dtype::Float32, 1, sfreq, chunk_ms)
    }

    fn push_n(w: &mut StreamWriter, start: usize, n: usize) -> Result<usize, WriterError> {
        let ts: Vec<f64> = (start..start + n).map(|i| i as f64 / 1000.0).collect();
        w.push(&vec![0u8; n * 4], &ts)
    }

    #[test]
    fn timed_1khz_20ms_is_20_samples_and_19_9ms_is_refused() {
        let cfg = timed(1000.0, 20.0).unwrap();
        assert_eq!(cfg.chunk_samples, 20);
        assert_eq!(cfg.sfreq, Some(1000.0));
        assert!((cfg.chunk_ms().unwrap() - 20.0).abs() < 1e-9);
        check(cfg).unwrap();
        let e = timed(1000.0, 19.9).unwrap_err().to_string();
        assert!(e.contains("20 ms"), "{e}");
    }

    #[test]
    fn timed_30khz_maps_100ms_to_3000_and_refuses_the_old_default() {
        assert_eq!(timed(30_000.0, 100.0).unwrap().chunk_samples, 3000);
        assert_eq!(timed(30_000.0, 20.0).unwrap().chunk_samples, 600);
        // The old SDK default: 100 samples = 3.33 ms at 30 kHz.
        assert!(timed(30_000.0, 3.33).is_err());
        let hand_built = StreamConfig {
            stream_id: "s".into(),
            dtype: Dtype::Float32,
            n_channels: 1,
            chunk_samples: 100,
            sfreq: Some(30_000.0),
        };
        let e = check(hand_built).unwrap_err();
        assert!(e.contains("chunk shorter than 20 ms at 30000 Hz"), "{e}");
    }

    #[test]
    fn timed_rounds_up_so_the_chunk_is_never_shorter() {
        // 20 ms at 250.5 Hz = 5.01 samples -> 6, never 5 (19.96 ms).
        let cfg = timed(250.5, 20.0).unwrap();
        assert_eq!(cfg.chunk_samples, 6);
        assert!(f64::from(cfg.chunk_samples) / 250.5 >= 0.020);
        check(cfg).unwrap();
        let five = StreamConfig {
            chunk_samples: 5,
            ..timed(250.5, 20.0).unwrap()
        };
        assert!(check(five).is_err());
    }

    #[test]
    fn timed_refuses_bad_rate_or_duration() {
        for f in [0.0, -250.0, f64::NAN, f64::INFINITY, f64::NEG_INFINITY] {
            let e = timed(f, 100.0).unwrap_err().to_string();
            assert!(e.contains("sfreq"), "{f}: {e}");
        }
        for ms in [f64::NAN, f64::INFINITY, 0.0, -20.0, 19.999] {
            let e = timed(1000.0, ms).unwrap_err().to_string();
            assert!(e.contains("20 ms"), "{ms}: {e}");
        }
        for f in [0.0, -1.0, f64::NAN] {
            let bad = StreamConfig {
                sfreq: Some(f),
                ..StreamConfig::irregular("s", Dtype::Float32, 1, 100)
            };
            assert!(check(bad).is_err(), "{f}");
        }
    }

    #[test]
    fn value_cap_fails_naming_both_limits_instead_of_shrinking() {
        // 1,024 channels x 3,000 samples (100 ms at 30 kHz) = 3.07 M values.
        let e = StreamConfig::timed("s", Dtype::Int16, 1024, 30_000.0, 100.0)
            .unwrap_err()
            .to_string();
        assert!(e.contains("20 ms") && e.contains("1,000,000"), "{e}");
        // 1,024 x 600 (20 ms) fits.
        let ok = StreamConfig::timed("s", Dtype::Int16, 1024, 30_000.0, 20.0).unwrap();
        assert_eq!(ok.chunk_samples, 600);
        check(ok).unwrap();
        // 2,000 channels cannot fit even at 20 ms.
        let e = StreamConfig::timed("s", Dtype::Int16, 2000, 30_000.0, 20.0)
            .unwrap_err()
            .to_string();
        assert!(e.contains("20 ms") && e.contains("1,000,000"), "{e}");
    }

    #[test]
    fn irregular_config_has_no_duration_check() {
        let cfg = StreamConfig::irregular("markers", Dtype::Int32, 1, 1);
        assert_eq!(cfg.sfreq, None);
        assert_eq!(cfg.chunk_ms(), None);
        check(cfg).unwrap();
    }

    #[test]
    fn short_flush_closes_a_timed_writer() {
        let (wal, d) = tmp_wal();
        let cfg = timed(1000.0, 20.0).unwrap();
        let mut w = StreamWriter::new(cfg, Arc::new(DeviceKey::generate()), wal.clone()).unwrap();
        assert_eq!(push_n(&mut w, 0, 25).unwrap(), 1);
        assert_eq!(w.buffered_samples(), 5);
        assert!(w.flush().unwrap());
        assert!(w.is_closed());
        assert_eq!(wal.pending(0), vec![0, 1]);
        let e = push_n(&mut w, 25, 20).unwrap_err().to_string();
        assert!(e.contains(FLUSHED_MSG), "{e}");
        assert!(!w.flush().unwrap());
        drop(w);
        drop(wal);
        let _ = std::fs::remove_dir_all(&d);
    }

    #[test]
    fn empty_flush_does_not_close_a_timed_writer() {
        let (wal, d) = tmp_wal();
        let cfg = timed(1000.0, 20.0).unwrap();
        let mut w = StreamWriter::new(cfg, Arc::new(DeviceKey::generate()), wal.clone()).unwrap();
        assert_eq!(push_n(&mut w, 0, 40).unwrap(), 2);
        assert!(!w.flush().unwrap());
        assert!(!w.is_closed());
        assert_eq!(push_n(&mut w, 40, 20).unwrap(), 1);
        drop(w);
        drop(wal);
        let _ = std::fs::remove_dir_all(&d);
    }

    #[test]
    fn irregular_writer_stays_open_after_flush() {
        let (wal, d) = tmp_wal();
        let cfg = StreamConfig::irregular("s", Dtype::Float32, 1, 5);
        let mut w = StreamWriter::new(cfg, Arc::new(DeviceKey::generate()), wal.clone()).unwrap();
        assert_eq!(push_n(&mut w, 0, 3).unwrap(), 0);
        assert!(w.flush().unwrap());
        assert!(!w.is_closed());
        assert_eq!(push_n(&mut w, 3, 5).unwrap(), 1);
        assert!(!w.flush().unwrap());
        assert_eq!(wal.pending(0), vec![0, 1]);
        drop(w);
        drop(wal);
        let _ = std::fs::remove_dir_all(&d);
    }

    proptest! {
        #![proptest_config(ProptestConfig { cases: 256, ..ProptestConfig::default() })]

        /// `timed` never yields a chunk under 20 ms; when the value cap is hit it fails and
        /// names both limits instead of shrinking the chunk.
        #[test]
        fn timed_never_goes_below_the_floor(
            sfreq in 0.1f64..=200_000.0,
            chunk_ms in 20.0f64..=10_000.0,
            n_channels in 1u32..64,
        ) {
            match StreamConfig::timed("s", Dtype::Float32, n_channels, sfreq, chunk_ms) {
                Ok(cfg) => {
                    let n = f64::from(cfg.chunk_samples);
                    prop_assert!(n / sfreq >= 0.020 - 1e-12);
                    prop_assert!(n * 1000.0 >= chunk_ms * sfreq * (1.0 - 1e-12));
                    prop_assert!(meets_min_duration(cfg.chunk_samples, sfreq));
                    let values = u64::from(cfg.chunk_samples) * u64::from(n_channels);
                    prop_assert!(values <= MAX_VALUES_PER_CHUNK);
                }
                Err(e) => {
                    let e = e.to_string();
                    let values = (chunk_ms * sfreq / 1000.0).ceil() * f64::from(n_channels);
                    prop_assert!(values > 1e6);
                    prop_assert!(e.contains("20 ms") && e.contains("1,000,000"), "{}", e);
                }
            }
        }
    }
}
