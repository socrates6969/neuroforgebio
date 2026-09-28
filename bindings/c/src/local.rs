//! Local data, read-only: `nf-signal/1` recordings (`docs/spec/zarr-layout.md`) and the
//! content-addressed chunk cache.
//!
//! Thread safety: `nf_recording`, `nf_chunk_cache` and `nf_chunk` may be used from several
//! threads at once (all operations take shared references; the cache verifies every read).

use std::ffi::c_char;

use nf_core::cache::{CachedChunk, ChunkCache};
use nf_core::ids::Dtype;
use nf_core::zarr::{self, ArrayMeta, FsStore, SignalInfo, Store, ZarrError};

use crate::{
    Error, NF_ERR_BUFFER_TOO_SMALL, NF_ERR_CORRUPT, NF_ERR_INVALID_ARG, NF_ERR_IO,
    NF_ERR_NOT_FOUND, NF_ERR_UNSUPPORTED, Result, cstr, dtype_code, free_handle, guard,
    guard_value, handle, into_handle, nf_buf, nf_dtype, nf_status, out, put_buf,
};

fn zarr_err(e: ZarrError) -> Error {
    let code = match &e {
        ZarrError::Io(io) if io.kind() == std::io::ErrorKind::NotFound => NF_ERR_NOT_FOUND,
        ZarrError::Io(_) => NF_ERR_IO,
        ZarrError::Missing(_) => NF_ERR_NOT_FOUND,
        ZarrError::Meta(_) => NF_ERR_CORRUPT,
        ZarrError::Unsupported(_) => NF_ERR_UNSUPPORTED,
        ZarrError::BadKey(_) | ZarrError::Shape(_) => NF_ERR_INVALID_ARG,
    };
    Error::new(code, e.to_string())
}

// ---------------------------------------------------------------- recordings
/// An open `nf-signal/1` recording (level 0). Opaque; free with `nf_recording_free`.
pub struct nf_recording {
    store: FsStore,
    id: String,
    info: SignalInfo,
    dtype: Dtype,
    data: ArrayMeta,
    timestamps: Option<ArrayMeta>,
    /// Stored bytes per sample row (n_channels x itemsize), overflow-checked at open.
    row_bytes: u64,
    /// Per-channel `physical = stored * scale + offset` (zarr-layout.md, nf_signal).
    scale: Vec<f64>,
    offset: Vec<f64>,
}

/// Level-0 facts of a recording.
#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct nf_recording_info {
    pub n_samples: u64,
    pub n_channels: u64,
    /// Sampling frequency in Hz.
    pub sfreq: f64,
    /// Stored dtype of the samples returned by `nf_recording_read`.
    pub dtype: nf_dtype,
    /// Whether `nf_recording_read_timestamps` has data.
    pub has_timestamps: bool,
}

fn open_recording(root: &str, id: &str) -> Result<nf_recording> {
    let store = FsStore::new(root);
    let group_key = format!("{id}/zarr.json");
    let group = store
        .get(&group_key)
        .map_err(zarr_err)?
        .ok_or_else(|| Error::new(NF_ERR_NOT_FOUND, format!("no recording at {group_key}")))?;
    let group: serde_json::Value = serde_json::from_slice(&group)
        .map_err(|e| Error::new(NF_ERR_CORRUPT, format!("{group_key}: {e}")))?;
    let sig = group
        .pointer("/attributes/nf_signal")
        .ok_or_else(|| Error::new(NF_ERR_CORRUPT, format!("{group_key}: no nf_signal")))?;
    if sig.get("layout").and_then(serde_json::Value::as_str) != Some("nf-signal/1") {
        return Err(Error::new(
            NF_ERR_UNSUPPORTED,
            format!("{group_key}: layout is not nf-signal/1"),
        ));
    }
    let info: SignalInfo = serde_json::from_value(sig.clone())
        .map_err(|e| Error::new(NF_ERR_CORRUPT, format!("{group_key}: {e}")))?;
    let per_channel = |key: &str, default: f64| -> Result<Vec<f64>> {
        match sig.get(key) {
            None | Some(serde_json::Value::Null) => Ok(vec![default; info.ch_names.len()]),
            Some(v) => serde_json::from_value::<Vec<f64>>(v.clone())
                .ok()
                .filter(|x| x.len() == info.ch_names.len() && x.iter().all(|f| f.is_finite()))
                .ok_or_else(|| {
                    Error::new(
                        NF_ERR_CORRUPT,
                        format!("{group_key}: {key} must hold one finite number per channel"),
                    )
                }),
        }
    };
    let (scale, offset) = (per_channel("scale", 1.0)?, per_channel("offset", 0.0)?);
    let has_ts = sig
        .get("has_timestamps")
        .and_then(serde_json::Value::as_bool)
        .unwrap_or(false);
    let data = zarr::read_meta(&store, &format!("{id}/data/0")).map_err(zarr_err)?;
    // untrusted metadata: the array must match the group attributes before we size buffers
    if data.shape != [info.n_samples, info.n_channels]
        || info.ch_names.len() as u64 != info.n_channels
        || info.units.len() as u64 != info.n_channels
    {
        return Err(Error::new(
            NF_ERR_CORRUPT,
            "data/0 shape does not match nf_signal n_samples x n_channels",
        ));
    }
    if info.n_channels > MAX_CHANNELS {
        return Err(Error::new(
            NF_ERR_CORRUPT,
            format!(
                "{} channels exceeds the {MAX_CHANNELS}-channel limit",
                info.n_channels
            ),
        ));
    }
    let row_bytes = info
        .n_channels
        .checked_mul(data.dtype.itemsize() as u64)
        .ok_or_else(|| Error::new(NF_ERR_CORRUPT, "row size overflows"))?;
    let timestamps = if has_ts {
        let m = zarr::read_meta(&store, &format!("{id}/timestamps")).map_err(zarr_err)?;
        if m.shape != [info.n_samples] || m.dtype != Dtype::Float64 {
            return Err(Error::new(
                NF_ERR_CORRUPT,
                "timestamps must be float64 with one value per sample",
            ));
        }
        Some(m)
    } else {
        None
    };
    Ok(nf_recording {
        store,
        id: id.to_owned(),
        info,
        dtype: data.dtype,
        data,
        timestamps,
        row_bytes,
        scale,
        offset,
    })
}

/// Open recording `recording_id` under the Zarr root directory `root` (read-only).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_recording_open(
    root: *const c_char,
    recording_id: *const c_char,
    out_recording: *mut *mut nf_recording,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (root, id, o) = unsafe {
            (
                cstr(root, "root")?,
                cstr(recording_id, "recording_id")?,
                out(out_recording, "out_recording")?,
            )
        };
        *o = into_handle(open_recording(root, id)?);
        Ok(())
    })
}

/// Free a recording (NULL is a no-op).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_recording_free(recording: *mut nf_recording) {
    // SAFETY: header contract.
    unsafe { free_handle(recording) }
}

/// Level-0 facts of an open recording.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_recording_get_info(
    recording: *const nf_recording,
    out_info: *mut nf_recording_info,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (r, o) = unsafe { (handle(recording, "recording")?, out(out_info, "out_info")?) };
        *o = nf_recording_info {
            n_samples: r.info.n_samples,
            n_channels: r.info.n_channels,
            sfreq: r.info.sfreq,
            dtype: dtype_code(r.dtype),
            has_timestamps: r.timestamps.is_some(),
        };
        Ok(())
    })
}

unsafe fn channel_field(
    recording: *const nf_recording,
    index: u64,
    out_text: *mut nf_buf,
    pick: impl FnOnce(&SignalInfo, usize) -> Option<String>,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (r, o) = unsafe { (handle(recording, "recording")?, out(out_text, "out")?) };
        let i = usize::try_from(index).map_err(|_| Error::invalid("index out of range"))?;
        let v = pick(&r.info, i).ok_or_else(|| {
            Error::invalid(format!(
                "channel {index} out of range (n_channels {})",
                r.info.n_channels
            ))
        })?;
        put_buf(o, v);
        Ok(())
    })
}

/// Name of channel `index` (0-based).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_recording_channel_name(
    recording: *const nf_recording,
    index: u64,
    out_name: *mut nf_buf,
) -> nf_status {
    // SAFETY: forwarded contract.
    unsafe {
        channel_field(recording, index, out_name, |i, k| {
            i.ch_names.get(k).cloned()
        })
    }
}

/// Unit of channel `index` (0-based), as stored (for example `"uV"`).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_recording_channel_unit(
    recording: *const nf_recording,
    index: u64,
    out_unit: *mut nf_buf,
) -> nf_status {
    // SAFETY: forwarded contract.
    unsafe { channel_field(recording, index, out_unit, |i, k| i.units.get(k).cloned()) }
}

/// Rows `[start, min(stop, n_samples))` and the byte count they need.
/// Largest number of channels accepted at open (CABI-L2: untrusted metadata).
const MAX_CHANNELS: u64 = 65_536;

/// Largest single read in stored bytes: the bound nf-core puts on one Zarr region (1 GiB).
const MAX_READ_BYTES: u64 = zarr::MAX_REGION_BYTES;

/// Rows `[start, min(stop, n_samples))` and the output units they need (`per_row` each). The
/// stored bytes the read allocates (`stored_per_row` each) must stay within `MAX_READ_BYTES`.
fn rows(
    r: &nf_recording,
    start: u64,
    stop: u64,
    per_row: u64,
    stored_per_row: u64,
) -> Result<(u64, u64, usize)> {
    let stop = stop.min(r.info.n_samples);
    if start > stop {
        return Err(Error::invalid(format!(
            "start {start} is after stop {stop} (n_samples {})",
            r.info.n_samples
        )));
    }
    let n = stop - start;
    if n.checked_mul(stored_per_row)
        .is_none_or(|b| b > MAX_READ_BYTES)
    {
        return Err(Error::invalid(format!(
            "range of {n} samples exceeds {MAX_READ_BYTES} bytes per read; split it"
        )));
    }
    let needed = n
        .checked_mul(per_row)
        .and_then(|b| usize::try_from(b).ok())
        .ok_or_else(|| Error::invalid("region too large"))?;
    Ok((start, stop, needed))
}

/// Copy `bytes` to a caller buffer or report the needed size.
unsafe fn to_caller(
    dst: *mut u8,
    capacity: usize,
    needed: usize,
    out_len: &mut usize,
    fill: impl FnOnce() -> Result<Vec<u8>>,
) -> Result<()> {
    *out_len = needed;
    if needed == 0 {
        return Ok(());
    }
    if dst.is_null() || capacity < needed {
        return Err(Error::new(
            NF_ERR_BUFFER_TOO_SMALL,
            format!("buffer holds {capacity} bytes, {needed} needed"),
        ));
    }
    let bytes = fill()?;
    if bytes.len() != needed {
        return Err(Error::new(NF_ERR_CORRUPT, "region size mismatch"));
    }
    // SAFETY: `dst` has `capacity >= needed` writable bytes (header contract); no overlap with a
    // freshly allocated Vec.
    unsafe { std::ptr::copy_nonoverlapping(bytes.as_ptr(), dst, needed) };
    Ok(())
}

/// Read samples `[start, stop)` (clamped to `n_samples`) of all channels into a caller buffer:
/// little-endian values of the recording dtype, row-major `[rows][n_channels]`.
/// `*out_len` always receives the byte count needed; when `out` is NULL or `capacity` is
/// smaller the call returns `NF_ERR_BUFFER_TOO_SMALL` without reading. An empty range needs no
/// buffer: it returns `NF_OK` with `*out_len` = 0 even when `out` is NULL.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_recording_read(
    recording: *const nf_recording,
    start: u64,
    stop: u64,
    out: *mut u8,
    capacity: usize,
    out_len: *mut usize,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (r, len) = unsafe {
            (
                handle(recording, "recording")?,
                self::out(out_len, "out_len")?,
            )
        };
        let (start, stop, needed) = rows(r, start, stop, r.row_bytes, r.row_bytes)?;
        // SAFETY: header contract for `out`/`capacity`.
        unsafe {
            to_caller(out, capacity, needed, len, || {
                zarr::read_region(
                    &r.store,
                    &format!("{}/data/0", r.id),
                    &r.data,
                    &[start, 0],
                    &[stop, r.info.n_channels],
                )
                .map_err(zarr_err)
            })
        }
    })
}

/// One little-endian stored value as f64 (int64 above 2^53 rounds to the nearest double).
fn stored_to_f64(dtype: Dtype, b: &[u8]) -> f64 {
    match dtype {
        Dtype::Int8 => f64::from(b[0] as i8),
        Dtype::Uint8 => f64::from(b[0]),
        Dtype::Int16 => f64::from(i16::from_le_bytes([b[0], b[1]])),
        Dtype::Uint16 => f64::from(u16::from_le_bytes([b[0], b[1]])),
        Dtype::Int32 => f64::from(i32::from_le_bytes([b[0], b[1], b[2], b[3]])),
        Dtype::Uint32 => f64::from(u32::from_le_bytes([b[0], b[1], b[2], b[3]])),
        Dtype::Int64 => i64::from_le_bytes(b[..8].try_into().expect("8 bytes")) as f64,
        Dtype::Float32 => f64::from(f32::from_le_bytes([b[0], b[1], b[2], b[3]])),
        Dtype::Float64 => f64::from_le_bytes(b[..8].try_into().expect("8 bytes")),
    }
}

/// ABI 1.1. Read samples `[start, stop)` (clamped to `n_samples`) of all channels as physical
/// values in double precision: `stored * scale + offset` per channel (zarr-layout.md), row-major
/// `[rows][n_channels]`, in the units of `nf_recording_channel_unit`. `out` has room for
/// `capacity` doubles; `*out_count` always receives the number of doubles needed, and a NULL or
/// too small `out` returns `NF_ERR_BUFFER_TOO_SMALL` without reading; an empty range returns
/// `NF_OK` with `*out_count` = 0 even when `out` is NULL. Use `nf_recording_read` for the exact
/// stored values.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_recording_read_f64(
    recording: *const nf_recording,
    start: u64,
    stop: u64,
    out: *mut f64,
    capacity: usize,
    out_count: *mut usize,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (r, count) = unsafe {
            (
                handle(recording, "recording")?,
                self::out(out_count, "out_count")?,
            )
        };
        let nch = r.info.n_channels;
        let (start, stop, needed) = rows(r, start, stop, nch, r.row_bytes)?;
        *count = needed;
        if needed == 0 {
            return Ok(());
        }
        if out.is_null() || capacity < needed {
            return Err(Error::new(
                NF_ERR_BUFFER_TOO_SMALL,
                format!("buffer holds {capacity} doubles, {needed} needed"),
            ));
        }
        let raw = zarr::read_region(
            &r.store,
            &format!("{}/data/0", r.id),
            &r.data,
            &[start, 0],
            &[stop, nch],
        )
        .map_err(zarr_err)?;
        let item = r.dtype.itemsize();
        if raw.len() != needed * item {
            return Err(Error::new(NF_ERR_CORRUPT, "region size mismatch"));
        }
        crate::check_region::<f64>(out as usize, needed, "out")?;
        // SAFETY: `out` has room for `capacity >= needed` doubles (header contract); aligned and
        // size-bounded (checked above).
        let dst = unsafe { std::slice::from_raw_parts_mut(out, needed) };
        for (k, (d, b)) in dst.iter_mut().zip(raw.chunks_exact(item)).enumerate() {
            let c = k % nch as usize;
            *d = stored_to_f64(r.dtype, b) * r.scale[c] + r.offset[c];
        }
        Ok(())
    })
}

/// Read timestamps `[start, stop)` (clamped) into `out` (room for `capacity` doubles): the
/// original per-sample times in float64 seconds, as recorded (for streamed data the sender's LSL
/// clock; for converted files the source format's clock). They are not Unix time unless the
/// source used it; the recording's wall-clock anchor is its `start_time` attribute.
/// `*out_count` receives the number of timestamps needed. `NF_ERR_NOT_FOUND` when the recording
/// has no timestamps; `NF_ERR_BUFFER_TOO_SMALL` as for `nf_recording_read`.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_recording_read_timestamps(
    recording: *const nf_recording,
    start: u64,
    stop: u64,
    out: *mut f64,
    capacity: usize,
    out_count: *mut usize,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (r, count) = unsafe {
            (
                handle(recording, "recording")?,
                self::out(out_count, "out_count")?,
            )
        };
        let meta = r
            .timestamps
            .as_ref()
            .ok_or_else(|| Error::new(NF_ERR_NOT_FOUND, "recording has no timestamps"))?;
        let (start, stop, needed) = rows(r, start, stop, 8, 8)?;
        let mut bytes = 0usize;
        let cap_bytes = capacity.saturating_mul(8);
        // SAFETY: `out` has `capacity` doubles (header contract); byte copy has no alignment need.
        let res = unsafe {
            to_caller(out.cast::<u8>(), cap_bytes, needed, &mut bytes, || {
                zarr::read_region(
                    &r.store,
                    &format!("{}/timestamps", r.id),
                    meta,
                    &[start],
                    &[stop],
                )
                .map_err(zarr_err)
            })
        };
        *count = bytes / 8;
        res
    })
}

// ---------------------------------------------------------------- chunk cache
/// The local content-addressed chunk cache. Opaque; free with `nf_chunk_cache_free`.
pub struct nf_chunk_cache(ChunkCache);

/// A chunk read from the cache (decoded, little-endian). Opaque; free with `nf_chunk_free`.
pub struct nf_chunk(CachedChunk);

/// Open the cache rooted at `root` (created if missing). `max_bytes` bounds its size; this ABI
/// only reads, so the bound matters only to other writers of the same directory.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_chunk_cache_open(
    root: *const c_char,
    max_bytes: u64,
    out_cache: *mut *mut nf_chunk_cache,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (root, o) = unsafe { (cstr(root, "root")?, out(out_cache, "out_cache")?) };
        *o = into_handle(nf_chunk_cache(ChunkCache::open(root, max_bytes)?));
        Ok(())
    })
}

/// Free a cache handle (NULL is a no-op). Cached files are kept.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_chunk_cache_free(cache: *mut nf_chunk_cache) {
    // SAFETY: header contract.
    unsafe { free_handle(cache) }
}

/// Fetch chunk `chunk_id` and verify its hash. `NF_ERR_NOT_FOUND` on a miss; an entry that fails
/// verification is removed from the cache and also reported as `NF_ERR_NOT_FOUND`.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_chunk_cache_get(
    cache: *const nf_chunk_cache,
    chunk_id: *const c_char,
    out_chunk: *mut *mut nf_chunk,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (c, id, o) = unsafe {
            (
                handle(cache, "cache")?,
                cstr(chunk_id, "chunk_id")?,
                out(out_chunk, "out_chunk")?,
            )
        };
        if !nf_core::ids::parse_id(id).is_ok_and(|(k, _)| k == "chunk") {
            return Err(Error::invalid(format!("not a chunk id: {id:?}")));
        }
        let got =
            c.0.get(id)?
                .ok_or_else(|| Error::new(NF_ERR_NOT_FOUND, format!("{id} is not cached")))?;
        *o = into_handle(nf_chunk(got));
        Ok(())
    })
}

/// Total bytes currently cached.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_chunk_cache_size(
    cache: *const nf_chunk_cache,
    out_bytes: *mut u64,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (c, o) = unsafe { (handle(cache, "cache")?, out(out_bytes, "out_bytes")?) };
        *o = c.0.size()?;
        Ok(())
    })
}

/// Free a chunk (NULL is a no-op).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_chunk_free(chunk: *mut nf_chunk) {
    // SAFETY: header contract.
    unsafe { free_handle(chunk) }
}

/// Dtype of a chunk (0 for NULL).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_chunk_dtype(chunk: *const nf_chunk) -> nf_dtype {
    // SAFETY: header contract.
    guard_value(0, || {
        Ok(dtype_code(unsafe { handle(chunk, "chunk") }?.0.dtype))
    })
}

/// Rank of a chunk (0 for NULL).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_chunk_rank(chunk: *const nf_chunk) -> usize {
    // SAFETY: header contract.
    guard_value(0, || Ok(unsafe { handle(chunk, "chunk") }?.0.shape.len()))
}

/// Shape of a chunk (`rank` entries), owned by the chunk (NULL for NULL).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_chunk_shape(chunk: *const nf_chunk) -> *const u64 {
    // SAFETY: header contract.
    guard_value(std::ptr::null(), || {
        Ok(unsafe { handle(chunk, "chunk") }?.0.shape.as_ptr())
    })
}

/// Decoded little-endian bytes of a chunk, owned by the chunk; `*out_len` receives the length.
/// NULL (and 0) for a NULL chunk.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_chunk_data(chunk: *const nf_chunk, out_len: *mut usize) -> *const u8 {
    guard_value(std::ptr::null(), || {
        // SAFETY: header contract.
        let (c, len) = unsafe {
            (
                crate::opt_handle(chunk, "chunk")?,
                crate::opt_out(out_len, "out_len")?,
            )
        };
        if let Some(l) = len {
            *l = c.map_or(0, |c| c.0.data.len());
        }
        Ok(c.map_or(std::ptr::null(), |c| c.0.data.as_ptr()))
    })
}
