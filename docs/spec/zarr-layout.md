# Canonical signal layout on Zarr v3 (`nf-signal/1`)

Status: **v1 draft** (BUILD-GUIDE 2.4). Implementation: `services/platform/nf_platform/signals/zarr_store.py`.
Tests: `services/platform/tests/signals/`. A change to anything below that alters stored bytes or attribute
meaning is a new layout version (`nf-signal/2`), never an in-place edit.

## 1. Where recordings live

One Zarr v3 hierarchy per recording, in the `zarr/` bucket, under a prefix owned by one tenant and one subject.
Every Zarr key (metadata `zarr.json` and every chunk) is stored as an NFE1 envelope (AES-256-GCM, subject DEK,
AAD = tenant, subject, `zarr/<object key>`, object version; see `nf_platform/storage/keyring.py`). Data and
metadata at rest are therefore ciphertext, and crypto-shredding the subject makes the recording unreadable.
Because an AEAD cannot authenticate a byte range, **sharding is not used**: each chunk is one object, fetched
whole.

## 2. Hierarchy

```
<recording_id>/                group, attrs: nf_signal, channels, meta
<recording_id>/data/0          level 0: shape (time, channel), stored dtype (§4)
<recording_id>/data/<k>        level k >= 1: block mean over factor**k samples (float32; float64 if stored is float64)
<recording_id>/min/<k>         level k >= 1: block minimum (stored dtype, exact)
<recording_id>/max/<k>         level k >= 1: block maximum (stored dtype, exact)
<recording_id>/timestamps      optional, float64 (time,): original per-sample timestamps in seconds
<recording_id>/clock_offsets   optional, float64 (n, 2): (collection_time, offset) pairs, as recorded (XDF)
```

`dimension_names` are `("time", "channel")` on every signal array. Arrays are C-ordered.

## 3. Chunking (time x channel)

- Level 0 chunk = `round(chunk_s * sfreq)` samples x `min(chunk_channels, n_channels)` channels.
- Defaults: `chunk_s = 4.0`, `chunk_channels = 64` (BLUEPRINT §3.4 ESTIMATE "1-10 s x 64 channels"; the
  default is a starting point, re-measured with `python -m nf_platform.signals.bench`; numbers are
  measurements, not targets).
- Pyramid levels use the same chunk shape, capped at the level length.
- Codec chain: Zarr v3 defaults (bytes, little-endian + zstd). Compression happens **before** encryption.

## 4. Dtype policy (lossless)

| Source dtype | Stored dtype |
|---|---|
| int8, uint8 | int16 |
| int16 | int16 |
| uint16 | int32 |
| int32 (e.g. BDF 24-bit) | int32 |
| int64 | int64 |
| float32 | float32 |
| float64 | float64 |

Anything else (complex, bool, object, strings) is rejected. Float data must be finite. Integer sources keep
their digital values; the conversion to physical units lives in attributes (§5), so integer round-trips are
bit-exact. Float sources are never down-cast.

## 5. Attributes (`<recording_id>/zarr.json` attributes)

`nf_signal` (required):

| Key | Meaning |
|---|---|
| `layout` | `"nf-signal/1"` |
| `sfreq` | level-0 sampling rate in Hz (float) |
| `n_samples`, `n_channels` | level-0 shape |
| `dtype`, `source_dtype` | stored and source numpy dtype names |
| `dims` | `["time", "channel"]` |
| `ch_names` | unique channel names, in channel order |
| `units` | per-channel physical unit string (e.g. `"uV"`, `"µV"`, `"V"`) |
| `scale`, `offset` | per-channel floats: **physical = stored * scale + offset** |
| `chunks` | level-0 chunk shape `[time, channel]` |
| `start_time` | ISO 8601 start of recording or `null` |
| `has_timestamps`, `has_clock_offsets` | whether the optional arrays exist |
| `pyramid` | `{factor, reductions: ["mean","min","max"], levels: [{level, decimation, n_samples, sfreq}]}` |

`channels`: list of per-channel objects written by converters, including the governance attributes of
BLUEPRINT §3.2 (`modality`, `nervous_system`, `derived_from_non_neural`, `sampling_rate`, `units`,
`device_ref`) with defaults by modality (editable later), plus format-specific fields needed for exact export
(e.g. EDF physical/digital min/max).

`meta`: converter metadata (source format, events/annotations with onsets in seconds, non-identifying header
fields, XDF stream info). Direct identifiers are never stored here (SEC-141); they are returned separately to
the governed table.

## 6. Multiscale pyramid

Level `k` has decimation `d = factor**k` (`factor = 4`) and `ceil(n / d)` samples; sample `j` summarises level-0
samples `[j*d, min((j+1)*d, n))` (the last block may be partial). Levels are added while the level still has at
least `pyramid_min_samples` (default 256) samples, up to 12 levels. Means are computed in float64 and stored in
float32 (float64 for float64 sources); min/max are exact.

## 7. Window semantics

`read_window(store, recording_id, start_s, end_s, channels=None, level=0, kind="mean", physical=False)` returns
an array `(n_channels, n_samples)` with the samples `j` of level `k` such that
`start_s <= j * d / sfreq < end_s`, clipped to the recording. Channels are selected by name or index, in the
requested order. Level 0 returns the stored dtype (exact); `physical=True` applies `scale`/`offset` (float64).
Windows are addressed by recording id and seconds only; no subject names appear in paths or query strings
(SEC-036).
