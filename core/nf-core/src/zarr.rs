//! Zarr v3 chunk IO for the `nf-signal/1` layout (`docs/spec/zarr-layout.md`).
//!
//! Scope: regular chunk grid, default chunk-key encoding (`c/<i>/<j>`, separator `/`), the
//! `bytes` codec (little or big endian). Chunks at the array edge are stored full-size and padded
//! with the fill value, as the Zarr v3 spec requires. Compressed codecs (`zstd`, `gzip`,
//! `blosc`) are reported as unsupported: the SDK writes uncompressed local copies, and platform
//! data reaches the SDK as `nf-window/1` responses, not as raw (encrypted) chunks. Sharding is not
//! used by the layout (§1) and is rejected.
//!
//! Stores are plain key -> bytes maps ([`Store`]); [`FsStore`] maps keys to files under a root
//! directory and refuses keys that could escape it.
//!
//! Metadata is untrusted input: every size is computed with checked arithmetic and bounded by
//! [`MAX_CHUNK_BYTES`] (one decoded chunk) and [`MAX_REGION_BYTES`] (one `read_region` result), so
//! a hostile `zarr.json` yields a [`ZarrError`], never a panic, an overflow or a huge allocation.

use std::collections::BTreeMap;
use std::fmt;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};
use serde_json::json;

use crate::ids::Dtype;

#[derive(Debug)]
pub enum ZarrError {
    Io(std::io::Error),
    Meta(String),
    Unsupported(String),
    BadKey(String),
    Shape(String),
    Missing(String),
}

impl fmt::Display for ZarrError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Io(e) => write!(f, "zarr io: {e}"),
            Self::Meta(m) => write!(f, "zarr metadata: {m}"),
            Self::Unsupported(m) => write!(f, "zarr: unsupported {m}"),
            Self::BadKey(k) => write!(f, "zarr: refused store key {k:?}"),
            Self::Shape(m) => write!(f, "zarr shape: {m}"),
            Self::Missing(k) => write!(f, "zarr: missing {k}"),
        }
    }
}
impl std::error::Error for ZarrError {}
impl From<std::io::Error> for ZarrError {
    fn from(e: std::io::Error) -> Self {
        Self::Io(e)
    }
}

type Result<T> = std::result::Result<T, ZarrError>;

/// Largest decoded chunk accepted (256 MiB).
pub const MAX_CHUNK_BYTES: u64 = 256 << 20;
/// Largest region `read_region` will materialise (1 GiB); read bigger windows in pieces.
pub const MAX_REGION_BYTES: u64 = 1 << 30;
/// Largest array rank accepted.
pub const MAX_RANK: usize = 32;

/// `itemsize * prod(shape)` in bytes, `None` on overflow (mirrors `ids::checked_len`).
fn checked_bytes(itemsize: usize, shape: &[u64]) -> Option<u64> {
    shape
        .iter()
        .try_fold(itemsize as u64, |acc, &d| acc.checked_mul(d))
}

/// Checked byte size bounded by `limit`, as a `usize` safe to allocate.
fn bounded_bytes(itemsize: usize, shape: &[u64], limit: u64, what: &str) -> Result<usize> {
    let n = checked_bytes(itemsize, shape)
        .ok_or_else(|| ZarrError::Shape(format!("{what} size overflows")))?;
    if n > limit {
        return Err(ZarrError::Shape(format!(
            "{what} is {n} bytes, above the {limit}-byte limit"
        )));
    }
    usize::try_from(n).map_err(|_| ZarrError::Shape(format!("{what} does not fit in memory")))
}

/// A key -> bytes store (Zarr v3 abstract store, minimal).
pub trait Store {
    fn get(&self, key: &str) -> Result<Option<Vec<u8>>>;
    fn set(&mut self, key: &str, value: &[u8]) -> Result<()>;
}

/// In-memory store (tests, staging before upload).
#[derive(Debug, Default, Clone)]
pub struct MemStore(pub BTreeMap<String, Vec<u8>>);

impl Store for MemStore {
    fn get(&self, key: &str) -> Result<Option<Vec<u8>>> {
        Ok(self.0.get(key).cloned())
    }
    fn set(&mut self, key: &str, value: &[u8]) -> Result<()> {
        self.0.insert(key.to_owned(), value.to_vec());
        Ok(())
    }
}

/// Directory store: key `a/b/zarr.json` -> `<root>/a/b/zarr.json`.
#[derive(Debug, Clone)]
pub struct FsStore {
    root: PathBuf,
}

impl FsStore {
    pub fn new(root: impl Into<PathBuf>) -> Self {
        Self { root: root.into() }
    }
    pub fn root(&self) -> &Path {
        &self.root
    }
    fn path(&self, key: &str) -> Result<PathBuf> {
        let ok = !key.is_empty()
            && !key.starts_with('/')
            && !key.contains('\\')
            && !key.contains(':')
            && key
                .split('/')
                .all(|p| !p.is_empty() && p != "." && p != "..");
        if !ok {
            return Err(ZarrError::BadKey(key.to_owned()));
        }
        Ok(key
            .split('/')
            .fold(self.root.clone(), |p, part| p.join(part)))
    }
}

impl Store for FsStore {
    fn get(&self, key: &str) -> Result<Option<Vec<u8>>> {
        match std::fs::read(self.path(key)?) {
            Ok(b) => Ok(Some(b)),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(None),
            Err(e) => Err(e.into()),
        }
    }
    fn set(&mut self, key: &str, value: &[u8]) -> Result<()> {
        let p = self.path(key)?;
        if let Some(dir) = p.parent() {
            std::fs::create_dir_all(dir)?;
        }
        let tmp = p.with_extension("nftmp");
        std::fs::write(&tmp, value)?;
        std::fs::rename(&tmp, &p)?;
        Ok(())
    }
}

fn join(path: &str, leaf: &str) -> String {
    let p = path.trim_matches('/');
    if p.is_empty() {
        leaf.to_owned()
    } else {
        format!("{p}/{leaf}")
    }
}

// ---------------------------------------------------------------- metadata
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Endian {
    Little,
    Big,
}

/// Parsed array metadata (`zarr.json`, node_type array).
#[derive(Debug, Clone, PartialEq)]
pub struct ArrayMeta {
    pub shape: Vec<u64>,
    pub chunk_shape: Vec<u64>,
    pub dtype: Dtype,
    pub fill_value: f64,
    pub endian: Endian,
    pub dimension_names: Option<Vec<String>>,
    pub attributes: serde_json::Value,
}

#[derive(Deserialize)]
struct RawMeta {
    zarr_format: u8,
    node_type: String,
    #[serde(default)]
    shape: Vec<u64>,
    #[serde(default)]
    data_type: serde_json::Value,
    #[serde(default)]
    chunk_grid: serde_json::Value,
    #[serde(default)]
    chunk_key_encoding: serde_json::Value,
    #[serde(default)]
    fill_value: serde_json::Value,
    #[serde(default)]
    codecs: Vec<serde_json::Value>,
    #[serde(default)]
    dimension_names: Option<Vec<Option<String>>>,
    #[serde(default)]
    attributes: serde_json::Value,
    #[serde(default)]
    storage_transformers: Vec<serde_json::Value>,
}

fn meta_err(m: impl Into<String>) -> ZarrError {
    ZarrError::Meta(m.into())
}

impl ArrayMeta {
    pub fn new(shape: Vec<u64>, chunk_shape: Vec<u64>, dtype: Dtype) -> Result<Self> {
        if shape.len() != chunk_shape.len() || chunk_shape.contains(&0) {
            return Err(ZarrError::Shape(
                "chunk shape must be positive and match the rank".into(),
            ));
        }
        if shape.len() > MAX_RANK {
            return Err(ZarrError::Shape(format!("rank above {MAX_RANK}")));
        }
        // the whole array's byte size must be representable (strides and offsets use it) ...
        checked_bytes(dtype.itemsize(), &shape)
            .ok_or_else(|| ZarrError::Shape("array size overflows".into()))?;
        // ... and one chunk must be allocatable
        bounded_bytes(dtype.itemsize(), &chunk_shape, MAX_CHUNK_BYTES, "chunk")?;
        Ok(Self {
            shape,
            chunk_shape,
            dtype,
            fill_value: 0.0,
            endian: Endian::Little,
            dimension_names: None,
            attributes: json!({}),
        })
    }

    pub fn to_json(&self) -> serde_json::Value {
        let fill = if self.dtype.is_float() {
            json!(self.fill_value)
        } else {
            json!(self.fill_value as i64)
        };
        let mut m = json!({
            "zarr_format": 3,
            "node_type": "array",
            "shape": self.shape,
            "data_type": self.dtype.name(),
            "chunk_grid": {"name": "regular", "configuration": {"chunk_shape": self.chunk_shape}},
            "chunk_key_encoding": {"name": "default", "configuration": {"separator": "/"}},
            "fill_value": fill,
            "codecs": [{"name": "bytes", "configuration": {
                "endian": if self.endian == Endian::Little { "little" } else { "big" }}}],
            "attributes": self.attributes,
        });
        if let Some(d) = &self.dimension_names {
            m["dimension_names"] = json!(d);
        }
        m
    }

    pub fn from_json(bytes: &[u8]) -> Result<Self> {
        let raw: RawMeta = serde_json::from_slice(bytes)
            .map_err(|e| meta_err(format!("invalid zarr.json: {e}")))?;
        if raw.zarr_format != 3 || raw.node_type != "array" {
            return Err(meta_err("not a Zarr v3 array"));
        }
        if !raw.storage_transformers.is_empty() {
            return Err(ZarrError::Unsupported("storage transformers".into()));
        }
        let dtype = Dtype::parse(raw.data_type.as_str().unwrap_or(""))
            .map_err(|_| ZarrError::Unsupported(format!("data_type {}", raw.data_type)))?;
        if raw.chunk_grid["name"] != "regular" {
            return Err(ZarrError::Unsupported("chunk grid (only regular)".into()));
        }
        let chunk_shape: Vec<u64> =
            serde_json::from_value(raw.chunk_grid["configuration"]["chunk_shape"].clone())
                .map_err(|_| meta_err("chunk_shape"))?;
        let enc = &raw.chunk_key_encoding;
        let sep = enc["configuration"]["separator"].as_str().unwrap_or("/");
        if enc["name"] != "default" || sep != "/" {
            return Err(ZarrError::Unsupported(
                "chunk key encoding (only default with '/')".into(),
            ));
        }
        let mut endian = Endian::Little;
        let mut saw_bytes = false;
        for c in &raw.codecs {
            match c["name"].as_str().unwrap_or("") {
                "bytes" => {
                    saw_bytes = true;
                    endian = match c["configuration"]["endian"].as_str() {
                        Some("big") => Endian::Big,
                        _ => Endian::Little,
                    };
                }
                other => {
                    return Err(ZarrError::Unsupported(format!("codec {other}")));
                }
            }
        }
        if !saw_bytes {
            return Err(meta_err("missing bytes codec"));
        }
        let fill_value = match &raw.fill_value {
            serde_json::Value::Number(n) => n.as_f64().unwrap_or(0.0),
            serde_json::Value::Null => 0.0,
            serde_json::Value::String(s) if s == "NaN" => f64::NAN,
            // Zarr v3 spells the infinities as strings too (L12)
            serde_json::Value::String(s) if s == "Infinity" => f64::INFINITY,
            serde_json::Value::String(s) if s == "-Infinity" => f64::NEG_INFINITY,
            other => return Err(ZarrError::Unsupported(format!("fill_value {other}"))),
        };
        let meta = ArrayMeta {
            dimension_names: raw
                .dimension_names
                .map(|d| d.into_iter().map(|x| x.unwrap_or_default()).collect()),
            attributes: raw.attributes,
            ..ArrayMeta::new(raw.shape, chunk_shape, dtype)?
        };
        Ok(ArrayMeta {
            fill_value,
            endian,
            ..meta
        })
    }

    /// Number of chunks along each dimension.
    pub fn grid(&self) -> Vec<u64> {
        self.shape
            .iter()
            .zip(&self.chunk_shape)
            .map(|(s, c)| s.div_ceil(*c))
            .collect()
    }

    /// Decoded chunk size, checked and bounded (fields are public, so re-checked on every use).
    fn chunk_bytes(&self) -> Result<usize> {
        if self.chunk_shape.len() != self.shape.len() || self.chunk_shape.contains(&0) {
            return Err(ZarrError::Shape(
                "chunk shape must be positive and match the rank".into(),
            ));
        }
        bounded_bytes(
            self.dtype.itemsize(),
            &self.chunk_shape,
            MAX_CHUNK_BYTES,
            "chunk",
        )
    }

    fn fill_element(&self) -> Vec<u8> {
        let f = self.fill_value;
        match self.dtype {
            Dtype::Int8 => (f as i8).to_le_bytes().to_vec(),
            Dtype::Uint8 => (f as u8).to_le_bytes().to_vec(),
            Dtype::Int16 => (f as i16).to_le_bytes().to_vec(),
            Dtype::Uint16 => (f as u16).to_le_bytes().to_vec(),
            Dtype::Int32 => (f as i32).to_le_bytes().to_vec(),
            Dtype::Uint32 => (f as u32).to_le_bytes().to_vec(),
            Dtype::Int64 => (f as i64).to_le_bytes().to_vec(),
            Dtype::Float32 => (f as f32).to_le_bytes().to_vec(),
            Dtype::Float64 => f.to_le_bytes().to_vec(),
        }
    }
}

/// Chunk key for grid coordinates: `c/0/3`.
pub fn chunk_key(coords: &[u64]) -> String {
    let mut k = String::from("c");
    for c in coords {
        k.push('/');
        k.push_str(&c.to_string());
    }
    k
}

fn swap_in_place(buf: &mut [u8], itemsize: usize) {
    if itemsize > 1 {
        for el in buf.chunks_exact_mut(itemsize) {
            el.reverse();
        }
    }
}

fn strides(shape: &[u64]) -> Vec<u64> {
    let mut s = vec![1u64; shape.len()];
    for i in (0..shape.len().saturating_sub(1)).rev() {
        s[i] = s[i + 1] * shape[i + 1];
    }
    s
}

/// Iterate every index in the box `[lo, hi)` (C order) and call `f(index)`.
fn for_each_index(lo: &[u64], hi: &[u64], mut f: impl FnMut(&[u64])) {
    if lo.iter().zip(hi).any(|(a, b)| a >= b) {
        return;
    }
    let mut idx = lo.to_vec();
    loop {
        f(&idx);
        let mut d = idx.len();
        loop {
            if d == 0 {
                return;
            }
            d -= 1;
            idx[d] += 1;
            if idx[d] < hi[d] {
                break;
            }
            idx[d] = lo[d];
        }
    }
}

// ---------------------------------------------------------------- arrays
/// Write array metadata only.
pub fn write_meta(store: &mut dyn Store, path: &str, meta: &ArrayMeta) -> Result<()> {
    let bytes = serde_json::to_vec_pretty(&meta.to_json()).map_err(|e| meta_err(e.to_string()))?;
    store.set(&join(path, "zarr.json"), &bytes)
}

pub fn read_meta(store: &dyn Store, path: &str) -> Result<ArrayMeta> {
    let key = join(path, "zarr.json");
    let bytes = store.get(&key)?.ok_or(ZarrError::Missing(key))?;
    ArrayMeta::from_json(&bytes)
}

/// Encode one decoded chunk (little-endian elements, full chunk shape) through the codec chain.
pub fn encode_chunk(meta: &ArrayMeta, mut decoded: Vec<u8>) -> Result<Vec<u8>> {
    if decoded.len() != meta.chunk_bytes()? {
        return Err(ZarrError::Shape("chunk buffer has the wrong length".into()));
    }
    if meta.endian == Endian::Big {
        swap_in_place(&mut decoded, meta.dtype.itemsize());
    }
    Ok(decoded)
}

/// Decode one stored chunk into little-endian elements of the full chunk shape.
pub fn decode_chunk(meta: &ArrayMeta, mut stored: Vec<u8>) -> Result<Vec<u8>> {
    if stored.len() != meta.chunk_bytes()? {
        return Err(ZarrError::Shape("stored chunk has the wrong length".into()));
    }
    if meta.endian == Endian::Big {
        swap_in_place(&mut stored, meta.dtype.itemsize());
    }
    Ok(stored)
}

/// Read one chunk (decoded, little-endian, full chunk shape); a missing chunk is all fill value.
pub fn read_chunk(
    store: &dyn Store,
    path: &str,
    meta: &ArrayMeta,
    coords: &[u64],
) -> Result<Vec<u8>> {
    let bytes = meta.chunk_bytes()?;
    if coords.len() != meta.shape.len() || coords.iter().zip(meta.grid()).any(|(c, g)| *c >= g) {
        return Err(ZarrError::Shape("chunk coordinates out of range".into()));
    }
    match store.get(&join(path, &chunk_key(coords)))? {
        Some(b) => decode_chunk(meta, b),
        None => Ok(meta.fill_element().repeat(bytes / meta.dtype.itemsize())),
    }
}

pub fn write_chunk(
    store: &mut dyn Store,
    path: &str,
    meta: &ArrayMeta,
    coords: &[u64],
    decoded: Vec<u8>,
) -> Result<()> {
    if coords.len() != meta.shape.len() || coords.iter().zip(meta.grid()).any(|(c, g)| *c >= g) {
        return Err(ZarrError::Shape("chunk coordinates out of range".into()));
    }
    let enc = encode_chunk(meta, decoded)?;
    store.set(&join(path, &chunk_key(coords)), &enc)
}

/// Write a whole array given as little-endian C-order bytes of `meta.shape`.
pub fn write_array(store: &mut dyn Store, path: &str, meta: &ArrayMeta, data: &[u8]) -> Result<()> {
    let item = meta.dtype.itemsize();
    let chunk_bytes = meta.chunk_bytes()?;
    if checked_bytes(item, &meta.shape) != Some(data.len() as u64) {
        return Err(ZarrError::Shape(
            "data length does not match shape and dtype".into(),
        ));
    }
    write_meta(store, path, meta)?;
    let astr = strides(&meta.shape);
    let cstr = strides(&meta.chunk_shape);
    let zeros = vec![0u64; meta.shape.len()];
    let grid = meta.grid();
    let mut err = None;
    for_each_index(&zeros, &grid, |cc| {
        if err.is_some() {
            return;
        }
        let mut buf = meta.fill_element().repeat(chunk_bytes / item);
        let lo: Vec<u64> = cc
            .iter()
            .zip(&meta.chunk_shape)
            .map(|(c, s)| c * s)
            .collect();
        let hi: Vec<u64> = lo
            .iter()
            .zip(&meta.chunk_shape)
            .zip(&meta.shape)
            .map(|((l, s), n)| (l + s).min(*n))
            .collect();
        for_each_index(&lo, &hi, |ix| {
            let a: u64 = ix.iter().zip(&astr).map(|(i, s)| i * s).sum();
            let c: u64 = ix
                .iter()
                .zip(&lo)
                .zip(&cstr)
                .map(|((i, l), s)| (i - l) * s)
                .sum();
            let (a, c) = (a as usize * item, c as usize * item);
            buf[c..c + item].copy_from_slice(&data[a..a + item]);
        });
        if let Err(e) = write_chunk(store, path, meta, cc, buf) {
            err = Some(e);
        }
    });
    err.map_or(Ok(()), Err)
}

/// Read the box `[start, stop)` as little-endian C-order bytes.
pub fn read_region(
    store: &dyn Store,
    path: &str,
    meta: &ArrayMeta,
    start: &[u64],
    stop: &[u64],
) -> Result<Vec<u8>> {
    let rank = meta.shape.len();
    if start.len() != rank || stop.len() != rank {
        return Err(ZarrError::Shape("region rank mismatch".into()));
    }
    meta.chunk_bytes()?;
    let stop: Vec<u64> = stop
        .iter()
        .zip(&meta.shape)
        .map(|(s, n)| (*s).min(*n))
        .collect();
    let out_shape: Vec<u64> = start
        .iter()
        .zip(&stop)
        .map(|(a, b)| b.saturating_sub(*a))
        .collect();
    let item = meta.dtype.itemsize();
    let mut out = vec![0u8; bounded_bytes(item, &out_shape, MAX_REGION_BYTES, "region")?];
    if out.is_empty() {
        return Ok(out);
    }
    let ostr = strides(&out_shape);
    let cstr = strides(&meta.chunk_shape);
    let c_lo: Vec<u64> = start
        .iter()
        .zip(&meta.chunk_shape)
        .map(|(a, c)| a / c)
        .collect();
    let c_hi: Vec<u64> = stop
        .iter()
        .zip(&meta.chunk_shape)
        .map(|(b, c)| b.div_ceil(*c))
        .collect();
    let mut err = None;
    for_each_index(&c_lo, &c_hi, |cc| {
        if err.is_some() {
            return;
        }
        let chunk = match read_chunk(store, path, meta, cc) {
            Ok(c) => c,
            Err(e) => {
                err = Some(e);
                return;
            }
        };
        let base: Vec<u64> = cc
            .iter()
            .zip(&meta.chunk_shape)
            .map(|(c, s)| c * s)
            .collect();
        let lo: Vec<u64> = base.iter().zip(start).map(|(b, s)| (*b).max(*s)).collect();
        let hi: Vec<u64> = base
            .iter()
            .zip(&meta.chunk_shape)
            .zip(&stop)
            .map(|((b, s), e)| (b + s).min(*e))
            .collect();
        for_each_index(&lo, &hi, |ix| {
            let o: u64 = ix
                .iter()
                .zip(start)
                .zip(&ostr)
                .map(|((i, s), t)| (i - s) * t)
                .sum();
            let c: u64 = ix
                .iter()
                .zip(&base)
                .zip(&cstr)
                .map(|((i, b), t)| (i - b) * t)
                .sum();
            let (o, c) = (o as usize * item, c as usize * item);
            out[o..o + item].copy_from_slice(&chunk[c..c + item]);
        });
    });
    err.map_or(Ok(out), Err)
}

// ---------------------------------------------------------------- nf-signal/1
/// Level-0 description of a signal written by [`write_signal`].
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct SignalInfo {
    pub sfreq: f64,
    pub ch_names: Vec<String>,
    pub units: Vec<String>,
    pub dtype: String,
    pub source_dtype: String,
    pub n_samples: u64,
    pub n_channels: u64,
}

/// Stored dtype for a source dtype (zarr-layout.md §4, lossless).
pub fn stored_dtype(source: Dtype) -> Dtype {
    match source {
        Dtype::Int8 | Dtype::Uint8 | Dtype::Int16 => Dtype::Int16,
        Dtype::Uint16 | Dtype::Int32 => Dtype::Int32,
        Dtype::Uint32 | Dtype::Int64 => Dtype::Int64,
        Dtype::Float32 => Dtype::Float32,
        Dtype::Float64 => Dtype::Float64,
    }
}

/// Write level 0 of an `nf-signal/1` recording: group attributes and `<id>/data/0`
/// (time x channel). `data` is little-endian, `(n_samples, n_channels)`, already in the stored
/// dtype. Pyramid levels are computed by the platform (`pyramid.levels` is empty here), timestamps
/// are written when given (`<id>/timestamps`, float64).
#[allow(clippy::too_many_arguments)]
pub fn write_signal(
    store: &mut dyn Store,
    recording_id: &str,
    data: &[u8],
    dtype: Dtype,
    n_samples: u64,
    sfreq: f64,
    ch_names: &[String],
    units: &[String],
    chunk_s: f64,
    chunk_channels: u64,
    timestamps: Option<&[f64]>,
) -> Result<()> {
    let n_channels = ch_names.len() as u64;
    if units.len() as u64 != n_channels || n_channels == 0 {
        return Err(ZarrError::Shape(
            "need one unit per channel and >= 1 channel".into(),
        ));
    }
    if stored_dtype(dtype) != dtype {
        return Err(ZarrError::Unsupported(format!(
            "stored dtype {} (convert first)",
            dtype.name()
        )));
    }
    if !(sfreq.is_finite() && sfreq > 0.0) {
        return Err(ZarrError::Shape("sfreq must be positive".into()));
    }
    let mut uniq = ch_names.to_vec();
    uniq.sort();
    uniq.dedup();
    if uniq.len() != ch_names.len() {
        return Err(ZarrError::Shape("channel names must be unique".into()));
    }
    let ct = ((chunk_s * sfreq).round() as u64).clamp(1, n_samples.max(1));
    let cc = chunk_channels.clamp(1, n_channels);
    let has_ts = timestamps.is_some();
    let group = json!({
        "zarr_format": 3,
        "node_type": "group",
        "attributes": {
            "nf_signal": {
                "layout": "nf-signal/1",
                "sfreq": sfreq,
                "n_samples": n_samples,
                "n_channels": n_channels,
                "dtype": dtype.name(),
                "source_dtype": dtype.name(),
                "dims": ["time", "channel"],
                "ch_names": ch_names,
                "units": units,
                "scale": vec![1.0; ch_names.len()],
                "offset": vec![0.0; ch_names.len()],
                "chunks": [ct, cc],
                "start_time": null,
                "has_timestamps": has_ts,
                "has_clock_offsets": false,
                "pyramid": {"factor": 4, "reductions": ["mean", "min", "max"], "levels": []},
            },
            "channels": [],
            "meta": {"writer": format!("nf-core {}", crate::VERSION)},
        },
    });
    store.set(
        &join(recording_id, "zarr.json"),
        &serde_json::to_vec_pretty(&group).map_err(|e| meta_err(e.to_string()))?,
    )?;
    let data_group = json!({"zarr_format": 3, "node_type": "group", "attributes": {}});
    store.set(
        &join(recording_id, "data/zarr.json"),
        &serde_json::to_vec(&data_group).unwrap(),
    )?;
    let mut meta = ArrayMeta::new(vec![n_samples, n_channels], vec![ct, cc], dtype)?;
    meta.dimension_names = Some(vec!["time".into(), "channel".into()]);
    write_array(store, &join(recording_id, "data/0"), &meta, data)?;
    if let Some(ts) = timestamps {
        if ts.len() as u64 != n_samples {
            return Err(ZarrError::Shape("one timestamp per sample".into()));
        }
        let mut tm = ArrayMeta::new(
            vec![n_samples],
            vec![(ct * 16).min(n_samples.max(1))],
            Dtype::Float64,
        )?;
        tm.dimension_names = Some(vec!["time".into()]);
        let bytes: Vec<u8> = ts.iter().flat_map(|t| t.to_le_bytes()).collect();
        write_array(store, &join(recording_id, "timestamps"), &tm, &bytes)?;
    }
    Ok(())
}

/// Read `[start, stop)` samples x all channels of level 0 as little-endian bytes (stored dtype).
pub fn read_signal(
    store: &dyn Store,
    recording_id: &str,
    start: u64,
    stop: u64,
) -> Result<(ArrayMeta, Vec<u8>)> {
    let path = join(recording_id, "data/0");
    let meta = read_meta(store, &path)?;
    // untrusted metadata: level 0 must be (time, channel) before indexing its shape (H5)
    let &[_, n_channels] = meta.shape.as_slice() else {
        return Err(ZarrError::Shape(format!(
            "signal level 0 must be 2-D (time x channel), got rank {}",
            meta.shape.len()
        )));
    };
    let data = read_region(store, &path, &meta, &[start, 0], &[stop, n_channels])?;
    Ok((meta, data))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn i16s(v: &[i16]) -> Vec<u8> {
        v.iter().flat_map(|x| x.to_le_bytes()).collect()
    }

    #[test]
    fn roundtrip_with_edge_chunks() {
        let mut s = MemStore::default();
        let (n, c) = (7u64, 3u64);
        let vals: Vec<i16> = (0..(n * c) as i16).collect();
        let meta = ArrayMeta::new(vec![n, c], vec![3, 2], Dtype::Int16).unwrap();
        write_array(&mut s, "r/data/0", &meta, &i16s(&vals)).unwrap();
        assert_eq!(s.0.keys().filter(|k| k.contains("/c/")).count(), 3 * 2);
        let m2 = read_meta(&s, "r/data/0").unwrap();
        assert_eq!(m2, meta);
        let all = read_region(&s, "r/data/0", &m2, &[0, 0], &[n, c]).unwrap();
        assert_eq!(all, i16s(&vals));
        let win = read_region(&s, "r/data/0", &m2, &[2, 1], &[5, 3]).unwrap();
        let want: Vec<i16> = (2..5)
            .flat_map(|t| (1..3).map(move |ch| (t * 3 + ch) as i16))
            .collect();
        assert_eq!(win, i16s(&want));
        // edge chunk is stored full-size, padded with the fill value
        let edge = s.0.get("r/data/0/c/2/1").unwrap();
        assert_eq!(edge.len(), 3 * 2 * 2);
    }

    #[test]
    fn big_endian_and_missing_chunks() {
        let mut s = MemStore::default();
        let mut meta = ArrayMeta::new(vec![4], vec![2], Dtype::Int32).unwrap();
        meta.endian = Endian::Big;
        meta.fill_value = 7.0;
        write_meta(&mut s, "a", &meta).unwrap();
        write_chunk(
            &mut s,
            "a",
            &meta,
            &[0],
            [1i32, 2].iter().flat_map(|x| x.to_le_bytes()).collect(),
        )
        .unwrap();
        assert_eq!(s.0["a/c/0"], vec![0, 0, 0, 1, 0, 0, 0, 2]);
        let m = read_meta(&s, "a").unwrap();
        let v = read_region(&s, "a", &m, &[0], &[4]).unwrap();
        let got: Vec<i32> = v
            .chunks(4)
            .map(|b| i32::from_le_bytes(b.try_into().unwrap()))
            .collect();
        assert_eq!(got, vec![1, 2, 7, 7]);
    }

    fn meta_json(shape: &str, chunk: &str, dtype: &str) -> Vec<u8> {
        format!(
            r#"{{"zarr_format":3,"node_type":"array","shape":{shape},"data_type":"{dtype}",
          "chunk_grid":{{"name":"regular","configuration":{{"chunk_shape":{chunk}}}}},
          "chunk_key_encoding":{{"name":"default","configuration":{{"separator":"/"}}}},
          "fill_value":0,"codecs":[{{"name":"bytes","configuration":{{"endian":"little"}}}}]}}"#
        )
        .into_bytes()
    }

    /// H5: a level-0 array that is not 2-D is an error from `read_signal`, never an index panic.
    #[test]
    fn read_signal_rejects_non_2d_level0() {
        for (shape, chunk) in [("[100]", "[10]"), ("[]", "[]"), ("[2,3,4]", "[1,1,1]")] {
            let mut s = MemStore::default();
            s.set("r/data/0/zarr.json", &meta_json(shape, chunk, "int16"))
                .unwrap();
            assert!(
                matches!(read_signal(&s, "r", 0, 10), Err(ZarrError::Shape(_))),
                "{shape}"
            );
        }
        // a valid 2-D level 0 still reads
        let mut s = MemStore::default();
        write_signal(
            &mut s,
            "r",
            &i16s(&[1, 2, 3, 4]),
            Dtype::Int16,
            2,
            100.0,
            &["a".into(), "b".into()],
            &["uV".into(), "uV".into()],
            1.0,
            2,
            None,
        )
        .unwrap();
        assert_eq!(read_signal(&s, "r", 0, 2).unwrap().1, i16s(&[1, 2, 3, 4]));
    }

    /// H6: huge or overflowing sizes from metadata are errors, never an overflow panic or a
    /// multi-GB allocation.
    #[test]
    fn hostile_sizes_are_errors_not_allocations() {
        let huge = "[100000000000]"; // 1e11 float64 = 800 GB in one chunk
        let m = ArrayMeta::from_json(&meta_json(huge, huge, "float64"));
        assert!(matches!(m, Err(ZarrError::Shape(_))), "{m:?}");
        let over = format!("[{},{}]", u64::MAX, u64::MAX);
        assert!(matches!(
            ArrayMeta::from_json(&meta_json(&over, "[1,1]", "int16")),
            Err(ZarrError::Shape(_))
        ));
        assert!(matches!(
            ArrayMeta::from_json(&meta_json(&over, &over, "int16")),
            Err(ZarrError::Shape(_))
        ));
        let deep = format!("[{}]", vec!["1"; MAX_RANK + 1].join(","));
        assert!(ArrayMeta::from_json(&meta_json(&deep, &deep, "uint8")).is_err());
        // a large array with small chunks is fine to open, but a huge region read is refused
        let meta =
            ArrayMeta::from_json(&meta_json("[100000000000,64]", "[1000,64]", "float64")).unwrap();
        let s = MemStore::default();
        let r = read_region(&s, "a", &meta, &[0, 0], &[100_000_000_000, 64]);
        assert!(matches!(r, Err(ZarrError::Shape(_))), "{r:?}");
        let r = read_region(&s, "a", &meta, &[5, 0], &[7, 64]).unwrap();
        assert_eq!(r.len(), 2 * 64 * 8);
        // metadata mutated after validation (public fields) is re-checked, not trusted
        let mut bad = meta.clone();
        bad.chunk_shape = vec![u64::MAX, u64::MAX];
        assert!(read_chunk(&s, "a", &bad, &[0, 0]).is_err());
        assert!(read_region(&s, "a", &bad, &[0, 0], &[1, 1]).is_err());
        bad.chunk_shape = vec![1];
        assert!(read_chunk(&s, "a", &bad, &[0]).is_err());
        let mut ms = MemStore::default();
        assert!(write_array(&mut ms, "a", &bad, &[]).is_err());
    }

    #[test]
    fn fill_value_special_floats() {
        for (text, want) in [
            (r#""NaN""#, f64::NAN),
            (r#""Infinity""#, f64::INFINITY),
            (r#""-Infinity""#, f64::NEG_INFINITY),
        ] {
            let j = String::from_utf8(meta_json("[2]", "[2]", "float32"))
                .unwrap()
                .replace(r#""fill_value":0"#, &format!(r#""fill_value":{text}"#));
            let m = ArrayMeta::from_json(j.as_bytes()).unwrap();
            assert!(
                m.fill_value.to_bits() == want.to_bits()
                    || (want.is_nan() && m.fill_value.is_nan())
            );
        }
        let j = String::from_utf8(meta_json("[2]", "[2]", "float32"))
            .unwrap()
            .replace(r#""fill_value":0"#, r#""fill_value":"inf""#);
        assert!(ArrayMeta::from_json(j.as_bytes()).is_err());
    }

    #[test]
    fn rejects_compression_and_bad_keys() {
        let j = br#"{"zarr_format":3,"node_type":"array","shape":[2],"data_type":"int16",
          "chunk_grid":{"name":"regular","configuration":{"chunk_shape":[2]}},
          "chunk_key_encoding":{"name":"default","configuration":{"separator":"/"}},
          "fill_value":0,"codecs":[{"name":"bytes","configuration":{"endian":"little"}},
          {"name":"zstd","configuration":{"level":0,"checksum":false}}]}"#;
        assert!(matches!(
            ArrayMeta::from_json(j),
            Err(ZarrError::Unsupported(_))
        ));
        let fs = FsStore::new("x");
        for k in ["../a", "a/../../b", "/abs", "c:/x", "a\\b", ""] {
            assert!(matches!(fs.get(k), Err(ZarrError::BadKey(_))), "{k}");
        }
    }
}
