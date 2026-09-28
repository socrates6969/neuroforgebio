//! Streaming client (`proto/ingest/v1`): device keys, the encrypted write-ahead log, the stream
//! writer that cuts, signs and stores chunks, and the sender that uploads them through a
//! caller-supplied transport. Data flows device -> SDK -> platform only.
//!
//! Typical use: `nf_device_key_*` and `nf_wal_open`, then `nf_stream_writer_new` on the
//! acquisition thread (`push`, `flush`) and `nf_sender_new` + `nf_sender_run` on a network
//! thread; `nf_sender_stop` from any thread ends `run`; `nf_sender_finish` closes the stream.
//!
//! Thread safety: `nf_device_key` and `nf_wal` are immutable/internally locked and may be shared;
//! `nf_stream_writer` locks internally; for `nf_sender` see `nf_sender_run`.

use std::ffi::{CString, c_char, c_void};
use std::sync::atomic::Ordering;
use std::sync::{Arc, Mutex};
use std::time::Duration;

use nf_core::stream::keystore::{DpapiKey, EphemeralKey, KeyError, KeyProvider, StaticKey};
use nf_core::stream::proto::StreamState;
use nf_core::stream::sender::{self, IngestTransport, RpcError, Sender, SenderConfig};
use nf_core::stream::sign::{self, DeviceKey};
use nf_core::stream::wal::{Wal, WalError};
use nf_core::stream::writer::{StreamConfig, StreamWriter, WriterError};

use crate::{
    Error, NF_ERR_CORRUPT, NF_ERR_INVALID_ARG, NF_ERR_IO, NF_ERR_NOT_FOUND, NF_ERR_TRANSPORT,
    NF_ERR_UNSUPPORTED, Result, cstr, dtype_from, free_handle, guard, handle, into_handle, nf_buf,
    nf_bytes, nf_dtype, nf_status, opt_cstr, out, put_buf, slice,
};

fn key_err(e: KeyError) -> Error {
    let code = match &e {
        KeyError::Unavailable(_) => NF_ERR_UNSUPPORTED,
        KeyError::Length => NF_ERR_INVALID_ARG,
        KeyError::Io(_) | KeyError::Os(_) => NF_ERR_IO,
    };
    Error::new(code, e.to_string())
}

fn wal_err(e: WalError) -> Error {
    match e {
        WalError::Io(io) => io.into(),
        WalError::Key(k) => key_err(k),
        other => Error::new(NF_ERR_CORRUPT, other.to_string()),
    }
}

fn writer_err(e: WriterError) -> Error {
    match e {
        WriterError::Wal(w) => wal_err(w),
        other => Error::new(NF_ERR_INVALID_ARG, other.to_string()),
    }
}

// ---------------------------------------------------------------- device keys
/// An Ed25519 device key. The secret never leaves the library. Opaque; thread-safe.
pub struct nf_device_key(Arc<DeviceKey>);

/// Generate a new random device key.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_device_key_generate(out_key: *mut *mut nf_device_key) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let o = unsafe { out(out_key, "out_key")? };
        *o = into_handle(nf_device_key(Arc::new(DeviceKey::generate())));
        Ok(())
    })
}

/// Import an existing 32-byte Ed25519 seed (for keys held in an OS keystore). There is no way to
/// export it again.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_device_key_from_seed(
    seed: *const u8,
    seed_len: usize,
    out_key: *mut *mut nf_device_key,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (s, o) = unsafe { (slice(seed, seed_len, "seed")?, out(out_key, "out_key")?) };
        let k = DeviceKey::from_seed(s).ok_or_else(|| Error::invalid("seed must be 32 bytes"))?;
        *o = into_handle(nf_device_key(Arc::new(k)));
        Ok(())
    })
}

/// Windows: load the key sealed with DPAPI at `path`, or create and seal a new one there.
/// Elsewhere: `NF_ERR_UNSUPPORTED`. Note (NR-L6): the seal uses DPAPI without extra entropy, so any
/// process running as the same Windows user can unseal the key; prefer an OS keystore seed via
/// `nf_device_key_from_seed` where the platform offers one.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_device_key_open_sealed(
    path: *const c_char,
    out_key: *mut *mut nf_device_key,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (p, o) = unsafe { (cstr(path, "path")?, out(out_key, "out_key")?) };
        let k = DeviceKey::load_or_create_sealed(std::path::Path::new(p)).map_err(key_err)?;
        *o = into_handle(nf_device_key(Arc::new(k)));
        Ok(())
    })
}

/// Free a device key (NULL is a no-op). Writers and senders keep their own reference.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_device_key_free(key: *mut nf_device_key) {
    // SAFETY: header contract.
    unsafe { free_handle(key) }
}

/// Copy the 32-byte public key into `out_public_key` (room for 32 bytes).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_device_key_public_key(
    key: *const nf_device_key,
    out_public_key: *mut u8,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (k, o) = unsafe { (handle(key, "key")?, out(out_public_key, "out_public_key")?) };
        let pk = k.0.public_key();
        // SAFETY: `out_public_key` has room for 32 bytes (header contract).
        unsafe { std::ptr::copy_nonoverlapping(pk.as_ptr(), o, 32) };
        Ok(())
    })
}

/// A device token (`nfd1.<payload>.<sig>`, hashing.md sec. 10.2) for `tenant_id`/`device_id`/
/// `stream_id`, valid `lifetime_s` seconds (at most 600) from now.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_device_key_token(
    key: *const nf_device_key,
    tenant_id: *const c_char,
    device_id: *const c_char,
    stream_id: *const c_char,
    lifetime_s: u64,
    out_token: *mut nf_buf,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (k, t, d, s, o) = unsafe {
            (
                handle(key, "key")?,
                cstr(tenant_id, "tenant_id")?,
                cstr(device_id, "device_id")?,
                cstr(stream_id, "stream_id")?,
                out(out_token, "out_token")?,
            )
        };
        if lifetime_s == 0 || lifetime_s > sign::MAX_TOKEN_LIFETIME_S {
            return Err(Error::invalid(format!(
                "lifetime_s must be 1..={}",
                sign::MAX_TOKEN_LIFETIME_S
            )));
        }
        put_buf(
            o,
            sign::make_device_token(&k.0, t, d, s, lifetime_s, sign::unix_now())?,
        );
        Ok(())
    })
}

// ---------------------------------------------------------------- WAL
/// The encrypted on-disk write-ahead log of one stream. Opaque; thread-safe.
pub struct nf_wal(Arc<Wal>);

/// Open (or create) the WAL of `stream_id` in `dir` with a persistent key. Key source, first
/// match wins: `key32` (32 bytes from an OS keystore: Windows DPAPI/Credential Manager, macOS
/// Keychain, Linux libsecret, Android Keystore), then `dpapi_key_path` (Windows only: a
/// DPAPI-sealed file created on first use; DPAPI without extra entropy can be unsealed by any
/// process of the same Windows user, tracked as NR-L6). Passing neither is `NF_ERR_INVALID_ARG`
/// since ABI 1.2: a WAL whose key dies with the process silently loses every unsent record on a
/// crash (CABI-L3); use `nf_wal_open_ephemeral` to ask for that explicitly. `fsync` makes every
/// append durable.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_wal_open(
    dir: *const c_char,
    stream_id: *const c_char,
    key32: *const u8,
    dpapi_key_path: *const c_char,
    fsync: bool,
    out_wal: *mut *mut nf_wal,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (d, s, dp, o) = unsafe {
            (
                cstr(dir, "dir")?,
                cstr(stream_id, "stream_id")?,
                opt_cstr(dpapi_key_path, "dpapi_key_path")?,
                out(out_wal, "out_wal")?,
            )
        };
        let provider: Box<dyn KeyProvider> = if !key32.is_null() {
            // SAFETY: 32 readable bytes (header contract).
            let k = unsafe { slice(key32, 32, "key32")? };
            Box::new(StaticKey::new(k).map_err(key_err)?)
        } else if let Some(p) = dp {
            Box::new(DpapiKey::new(p).map_err(key_err)?)
        } else {
            return Err(Error::invalid(
                "no WAL key source: pass key32 or dpapi_key_path (nf_wal_open_ephemeral for tests)",
            ));
        };
        let w = Wal::open(d, s, provider.as_ref(), fsync).map_err(wal_err)?;
        *o = into_handle(nf_wal(Arc::new(w)));
        Ok(())
    })
}

/// FOR TESTS AND THROWAWAY SESSIONS ONLY: records are unreadable after the process ends.
/// ABI 1.2. Opens (or creates) the WAL of `stream_id` in `dir` with a random in-memory key, so
/// unsent data is lost on a crash or restart. Wrappers must expose this only under an explicit
/// testing name, never as a default or an overload of the normal open (nfb-security, CABI-L3).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_wal_open_ephemeral(
    dir: *const c_char,
    stream_id: *const c_char,
    fsync: bool,
    out_wal: *mut *mut nf_wal,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (d, s, o) = unsafe {
            (
                cstr(dir, "dir")?,
                cstr(stream_id, "stream_id")?,
                out(out_wal, "out_wal")?,
            )
        };
        let w = Wal::open(d, s, &EphemeralKey::new(), fsync).map_err(wal_err)?;
        *o = into_handle(nf_wal(Arc::new(w)));
        Ok(())
    })
}

/// Free a WAL handle (NULL is a no-op). Records stay on disk; writers and senders keep their own
/// reference.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_wal_free(wal: *mut nf_wal) {
    // SAFETY: header contract.
    unsafe { free_handle(wal) }
}

/// Number of records waiting in the WAL (not yet acknowledged by the platform).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_wal_len(wal: *const nf_wal, out_len: *mut usize) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (w, o) = unsafe { (handle(wal, "wal")?, out(out_len, "out_len")?) };
        *o = w.0.len();
        Ok(())
    })
}

// ---------------------------------------------------------------- stream writer
/// Cuts pushed samples into signed chunks and appends them to the WAL. Opaque; locks
/// internally (one producer thread is the intended use).
pub struct nf_stream_writer(Mutex<StreamWriter>);

fn lock_writer(w: &nf_stream_writer) -> std::sync::MutexGuard<'_, StreamWriter> {
    w.0.lock()
        .unwrap_or_else(std::sync::PoisonError::into_inner)
}

/// Writer counters.
#[repr(C)]
#[derive(Debug, Clone, Copy, Default)]
pub struct nf_writer_stats {
    pub chunks: u64,
    pub samples: u64,
    /// Largest WAL length seen after an append.
    pub wal_peak: u64,
}

/// A writer for `stream_id`: `dtype` must be int16, int32, float32 or float64; `chunk_samples`
/// samples per chunk. Each chunk is signed once (Ed25519), so keep a chunk at **20 ms or longer**
/// (`chunk_samples >= 0.02 * sampling rate`, e.g. 20 at 1 kHz, 600 at 30 kHz): below that the
/// signature dominates the per-chunk cost on the device and on the verifying server (bci-hive
/// 013). The ABI cannot check this yet because it is not given the sampling rate.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_stream_writer_new(
    stream_id: *const c_char,
    dtype: nf_dtype,
    n_channels: u32,
    chunk_samples: u32,
    key: *const nf_device_key,
    wal: *const nf_wal,
    out_writer: *mut *mut nf_stream_writer,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (s, k, w, o) = unsafe {
            (
                cstr(stream_id, "stream_id")?,
                handle(key, "key")?,
                handle(wal, "wal")?,
                out(out_writer, "out_writer")?,
            )
        };
        let cfg = StreamConfig {
            stream_id: s.to_owned(),
            dtype: dtype_from(dtype)?,
            n_channels,
            chunk_samples,
            // sample-count chunking as in ABI 1.x (nf-core's legacy/irregular mode): this ABI is not
            // given the sampling rate, so nf-core's 20 ms timed check cannot apply here yet (the
            // timed constructor is on the held 1.3 list)
            sfreq: None,
        };
        let wr = StreamWriter::new(cfg, k.0.clone(), w.0.clone()).map_err(writer_err)?;
        *o = into_handle(nf_stream_writer(Mutex::new(wr)));
        Ok(())
    })
}

/// Free a writer (NULL is a no-op). Buffered samples that were not flushed are dropped.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_stream_writer_free(writer: *mut nf_stream_writer) {
    // SAFETY: header contract.
    unsafe { free_handle(writer) }
}

/// Push `n_timestamps` samples: `samples` holds `n_timestamps * n_channels` little-endian values
/// of the writer dtype in row-major order (`samples_len` bytes), `timestamps` one finite time per
/// sample: float64 seconds on the sender's LSL clock (`lsl_local_clock()`, an arbitrary
/// host-local origin, not Unix time), stored and uploaded as given, never rewritten. `out_chunks`
/// (may be NULL) receives how many full chunks were written.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_stream_writer_push(
    writer: *const nf_stream_writer,
    samples: *const u8,
    samples_len: usize,
    timestamps: *const f64,
    n_timestamps: usize,
    out_chunks: *mut usize,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (w, s, t) = unsafe {
            (
                handle(writer, "writer")?,
                slice(samples, samples_len, "samples")?,
                slice(timestamps, n_timestamps, "timestamps")?,
            )
        };
        let n = lock_writer(w).push(s, t).map_err(writer_err)?;
        // SAFETY: NULL or writable.
        if let Some(o) = unsafe { crate::opt_out(out_chunks, "out_chunks") }? {
            *o = n;
        }
        Ok(())
    })
}

/// Record an LSL clock offset measurement (`time_correction`): `offset` = remote clock - local
/// clock at `collection_time`, both float64 seconds on the local LSL clock. It travels with the
/// next chunk.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_stream_writer_add_clock_offset(
    writer: *const nf_stream_writer,
    collection_time: f64,
    offset: f64,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let w = unsafe { handle(writer, "writer")? };
        lock_writer(w).add_clock_offset(collection_time, offset);
        Ok(())
    })
}

/// Record the local LSL clock and the operating system's monotonic clock read at the same instant
/// (both float64 seconds); it travels with the next chunk and lets the platform relate the two.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_stream_writer_add_local_clock(
    writer: *const nf_stream_writer,
    lsl_time: f64,
    monotonic_time: f64,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let w = unsafe { handle(writer, "writer")? };
        lock_writer(w).add_local_clock(lsl_time, monotonic_time);
        Ok(())
    })
}

/// Write the buffered partial chunk (end of acquisition). `out_wrote` (may be NULL) tells
/// whether there was one.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_stream_writer_flush(
    writer: *const nf_stream_writer,
    out_wrote: *mut bool,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let w = unsafe { handle(writer, "writer")? };
        let wrote = lock_writer(w).flush().map_err(writer_err)?;
        // SAFETY: NULL or writable.
        if let Some(o) = unsafe { crate::opt_out(out_wrote, "out_wrote") }? {
            *o = wrote;
        }
        Ok(())
    })
}

/// Sequence number the next chunk will get.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_stream_writer_next_seq(
    writer: *const nf_stream_writer,
    out_seq: *mut u64,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (w, o) = unsafe { (handle(writer, "writer")?, out(out_seq, "out_seq")?) };
        *o = lock_writer(w).next_seq();
        Ok(())
    })
}

/// Samples pushed but not yet in a chunk.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_stream_writer_buffered_samples(
    writer: *const nf_stream_writer,
    out_samples: *mut usize,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (w, o) = unsafe { (handle(writer, "writer")?, out(out_samples, "out_samples")?) };
        *o = lock_writer(w).buffered_samples();
        Ok(())
    })
}

/// Writer counters.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_stream_writer_get_stats(
    writer: *const nf_stream_writer,
    out_stats: *mut nf_writer_stats,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (w, o) = unsafe { (handle(writer, "writer")?, out(out_stats, "out_stats")?) };
        let s = lock_writer(w).stats.clone();
        *o = nf_writer_stats {
            chunks: s.chunks,
            samples: s.samples,
            wal_peak: s.wal_peak as u64,
        };
        Ok(())
    })
}

// ---------------------------------------------------------------- transport callbacks
/// Largest reply accepted through `nf_reply_set` (1 MiB): ingest replies (StreamAck,
/// StreamState), error messages and bearer tokens are all small. A larger reply is refused and
/// the call fails as a transport error (CABI-M1 case 12: no unbounded buffering).
pub const NF_MAX_REPLY_BYTES: usize = 1 << 20;

/// Reply slot handed to a callback. Opaque; fill it with `nf_reply_set` during the call only.
pub struct nf_reply {
    pub(crate) data: Vec<u8>,
    /// A reply above `NF_MAX_REPLY_BYTES` was offered; the call fails even if the callback
    /// returns 0.
    pub(crate) overflow: bool,
}

impl nf_reply {
    pub(crate) fn new() -> Self {
        Self {
            data: Vec::new(),
            overflow: false,
        }
    }
}

/// Store a copy of `data` as the callback's reply: the response message bytes when the callback
/// returns 0, or a UTF-8 error message otherwise. More than `NF_MAX_REPLY_BYTES` is refused with
/// `NF_ERR_INVALID_ARG`, and the call then fails as a transport error whatever the callback
/// returns.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_reply_set(
    reply: *mut nf_reply,
    data: *const u8,
    len: usize,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (r, d) = unsafe { (out(reply, "reply")?, slice(data, len, "data")?) };
        if d.len() > NF_MAX_REPLY_BYTES {
            r.overflow = true;
            r.data.clear();
            return Err(Error::invalid(format!(
                "reply of {} bytes exceeds NF_MAX_REPLY_BYTES ({NF_MAX_REPLY_BYTES})",
                d.len()
            )));
        }
        r.data = d.to_vec();
        Ok(())
    })
}

/// A unary ingest call: `request` is the serialized protobuf request, `authorization` the full
/// metadata value (`NFDevice nfd1...`), `timeout_s` the deadline. Return 0 and set the serialized
/// response with `nf_reply_set`, or return the gRPC status code (non-zero) and optionally set a
/// message. Pointers are valid only during the call.
pub type nf_ingest_unary_fn = Option<
    unsafe extern "C" fn(
        user: *mut c_void,
        request: *const u8,
        request_len: usize,
        authorization: *const c_char,
        timeout_s: f64,
        reply: *mut nf_reply,
    ) -> i32,
>;

/// The client-streaming ingest call: `chunks` are `n_chunks` serialized Chunk messages to send
/// in order on one StreamChunks call; the reply is the serialized StreamAck.
pub type nf_ingest_chunks_fn = Option<
    unsafe extern "C" fn(
        user: *mut c_void,
        chunks: *const nf_bytes,
        n_chunks: usize,
        authorization: *const c_char,
        timeout_s: f64,
        reply: *mut nf_reply,
    ) -> i32,
>;

/// The caller's gRPC transport for `nf.ingest.v1.IngestService`. `user` is passed through unchanged.
/// Transport requirements (SEC-030, CABI-M1); a conforming transport MUST:
/// 1. use TLS 1.3 only and refuse lower versions (plain http only to a loopback host);
/// 2. verify the certificate chain and hostname on every connection (no accept-all handler);
/// 3. never follow redirects (return the 3xx as the result), and never send `authorization`
///    to any host other than the one it was given;
/// 4. enforce `timeout_s` as the whole-call deadline;
/// 5. never log, cache or persist `authorization`, request headers or bodies;
/// 6. keep the response within `NF_MAX_REPLY_BYTES` (larger replies fail the call).
///
/// Thread contract: each callback runs on the thread that called `nf_sender_run`, `nf_sender_state`
/// or `nf_sender_finish`. `nf_sender_run` calls them one at a time, but `nf_sender_state` or
/// `nf_sender_finish` on another thread may call them concurrently with a running sender, so the
/// callbacks and `user` must be thread-safe whenever you do that. Callbacks must not unwind, throw
/// or longjmp, and must return within their `timeout_s`.
#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct nf_ingest_transport {
    pub user: *mut c_void,
    pub get_stream_state: nf_ingest_unary_fn,
    pub stream_chunks: nf_ingest_chunks_fn,
    pub finish_stream: nf_ingest_unary_fn,
}

struct CIngest(nf_ingest_transport);

fn rpc_result(code: i32, reply: nf_reply) -> std::result::Result<Vec<u8>, RpcError> {
    if reply.overflow {
        return Err(RpcError {
            code: sender::code::RESOURCE_EXHAUSTED,
            message: format!("reply exceeds NF_MAX_REPLY_BYTES ({NF_MAX_REPLY_BYTES})"),
        });
    }
    if code == 0 {
        Ok(reply.data)
    } else {
        Err(RpcError {
            code,
            message: String::from_utf8_lossy(&reply.data).into_owned(),
        })
    }
}

fn c_auth(auth: &str) -> std::result::Result<CString, RpcError> {
    CString::new(auth).map_err(|_| RpcError {
        code: sender::code::INVALID_ARGUMENT,
        message: "authorization contains NUL".into(),
    })
}

fn missing(name: &str) -> RpcError {
    RpcError {
        code: sender::code::UNKNOWN,
        message: format!("transport callback {name} is NULL"),
    }
}

impl CIngest {
    fn unary(
        &self,
        f: nf_ingest_unary_fn,
        name: &str,
        request: &[u8],
        auth: &str,
        timeout: Duration,
    ) -> std::result::Result<Vec<u8>, RpcError> {
        let f = f.ok_or_else(|| missing(name))?;
        let auth = c_auth(auth)?;
        let mut reply = nf_reply::new();
        // SAFETY: the caller's callback; every pointer is valid for the duration of the call.
        let code = unsafe {
            f(
                self.0.user,
                request.as_ptr(),
                request.len(),
                auth.as_ptr(),
                timeout.as_secs_f64(),
                &mut reply,
            )
        };
        rpc_result(code, reply)
    }
}

impl IngestTransport for CIngest {
    fn get_stream_state(
        &self,
        request: Vec<u8>,
        auth: &str,
        timeout: Duration,
    ) -> std::result::Result<Vec<u8>, RpcError> {
        self.unary(
            self.0.get_stream_state,
            "get_stream_state",
            &request,
            auth,
            timeout,
        )
    }
    fn stream_chunks(
        &self,
        chunks: Vec<Vec<u8>>,
        auth: &str,
        timeout: Duration,
    ) -> std::result::Result<Vec<u8>, RpcError> {
        let f = self
            .0
            .stream_chunks
            .ok_or_else(|| missing("stream_chunks"))?;
        let auth = c_auth(auth)?;
        let views: Vec<nf_bytes> = chunks
            .iter()
            .map(|c| nf_bytes {
                data: c.as_ptr(),
                len: c.len(),
            })
            .collect();
        let mut reply = nf_reply::new();
        // SAFETY: as in `unary`; `views` and `chunks` outlive the call.
        let code = unsafe {
            f(
                self.0.user,
                views.as_ptr(),
                views.len(),
                auth.as_ptr(),
                timeout.as_secs_f64(),
                &mut reply,
            )
        };
        rpc_result(code, reply)
    }
    fn finish_stream(
        &self,
        request: Vec<u8>,
        auth: &str,
        timeout: Duration,
    ) -> std::result::Result<Vec<u8>, RpcError> {
        self.unary(
            self.0.finish_stream,
            "finish_stream",
            &request,
            auth,
            timeout,
        )
    }
}

// ---------------------------------------------------------------- sender
/// Uploads WAL chunks through a caller transport with batching, retries and device-token auth.
/// Opaque.
pub struct nf_sender {
    sender: Arc<Sender>,
    /// The WAL the sender drains; `nf_sender_finish` refuses while it holds records (CABI-T2).
    wal: Arc<Wal>,
    /// Held by `nf_sender_run` for its whole run and by `nf_sender_finish` for its whole call, so
    /// neither can start while the other is active (checked with try_lock, never blocking).
    phase: Mutex<()>,
}

impl nf_sender {
    fn enter(&self, what: &str) -> Result<std::sync::MutexGuard<'_, ()>> {
        match self.phase.try_lock() {
            Ok(g) => Ok(g),
            Err(std::sync::TryLockError::Poisoned(p)) => Ok(p.into_inner()),
            Err(std::sync::TryLockError::WouldBlock) => Err(Error::invalid(format!(
                "{what}: nf_sender_run or nf_sender_finish is already active on this sender"
            ))),
        }
    }
}

/// Sender tuning. Start from `nf_sender_config_default`.
#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct nf_sender_config {
    /// Most chunks per StreamChunks call (at least 1).
    pub batch_max: usize,
    /// How long to wait for more chunks before sending a partial batch.
    pub linger_s: f64,
    /// Per-call deadline.
    pub call_timeout_s: f64,
    /// Retry backoff bounds.
    pub backoff_min_s: f64,
    pub backoff_max_s: f64,
}

/// Server-side state of a stream. Free the strings with `nf_stream_state_free`.
#[repr(C)]
#[derive(Debug)]
pub struct nf_stream_state {
    pub stream_id: nf_buf,
    pub next_seq: u64,
    pub n_samples: u64,
    /// For example `"open"` or `"finished"`.
    pub state: nf_buf,
    pub suspect: bool,
}

/// Sender counters.
#[repr(C)]
#[derive(Debug, Clone, Copy, Default)]
pub struct nf_sender_stats {
    pub calls: u64,
    pub chunks_acked: u64,
    pub rpc_errors: u64,
    pub next_seq_acked: u64,
    /// Whether the sender stopped on a fatal error (see `nf_sender_fatal_error`).
    pub fatal: bool,
}

/// Defaults: batch_max 50, linger 0.2 s, call timeout 10 s, backoff 0.05..1 s.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_sender_config_default(out_config: *mut nf_sender_config) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let o = unsafe { out(out_config, "out_config")? };
        let d = SenderConfig::new("", "", "");
        *o = nf_sender_config {
            batch_max: d.batch_max,
            linger_s: d.linger.as_secs_f64(),
            call_timeout_s: d.call_timeout.as_secs_f64(),
            backoff_min_s: d.backoff_min.as_secs_f64(),
            backoff_max_s: d.backoff_max.as_secs_f64(),
        };
        Ok(())
    })
}

fn secs(x: f64, what: &str) -> Result<Duration> {
    Duration::try_from_secs_f64(x).map_err(|_| Error::invalid(format!("{what} must be >= 0")))
}

/// A sender for one stream. `config` may be NULL for the defaults.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_sender_new(
    tenant_id: *const c_char,
    device_id: *const c_char,
    stream_id: *const c_char,
    key: *const nf_device_key,
    wal: *const nf_wal,
    config: *const nf_sender_config,
    out_sender: *mut *mut nf_sender,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (t, d, s, k, w, o) = unsafe {
            (
                cstr(tenant_id, "tenant_id")?,
                cstr(device_id, "device_id")?,
                cstr(stream_id, "stream_id")?,
                handle(key, "key")?,
                handle(wal, "wal")?,
                out(out_sender, "out_sender")?,
            )
        };
        let mut cfg = SenderConfig::new(t, d, s);
        // SAFETY: NULL or a valid config.
        if let Some(c) = unsafe { crate::opt_handle(config, "config") }? {
            cfg.batch_max = c.batch_max.max(1);
            cfg.linger = secs(c.linger_s, "linger_s")?;
            cfg.call_timeout = secs(c.call_timeout_s, "call_timeout_s")?;
            cfg.backoff_min = secs(c.backoff_min_s, "backoff_min_s")?;
            cfg.backoff_max = secs(c.backoff_max_s, "backoff_max_s")?;
        }
        *o = into_handle(nf_sender {
            sender: Arc::new(Sender::new(cfg, k.0.clone(), w.0.clone())),
            wal: w.0.clone(),
            phase: Mutex::new(()),
        });
        Ok(())
    })
}

/// Free a sender (NULL is a no-op). Must not be called while `nf_sender_run` is running.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_sender_free(sender: *mut nf_sender) {
    // SAFETY: header contract.
    unsafe { free_handle(sender) }
}

/// Upload WAL chunks until `nf_sender_stop` is called or a fatal error occurs (check
/// `nf_sender_get_stats`). Blocks the calling thread; the transport callbacks run on it. Other
/// threads may call `nf_sender_stop` and `nf_sender_get_stats` meanwhile. Only one
/// `nf_sender_run` or `nf_sender_finish` may be active per sender: a second one returns
/// `NF_ERR_INVALID_ARG` at once.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_sender_run(
    sender: *const nf_sender,
    transport: *const nf_ingest_transport,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (s, t) = unsafe { (handle(sender, "sender")?, handle(transport, "transport")?) };
        let _running = s.enter("nf_sender_run")?;
        s.sender.run(&CIngest(*t));
        Ok(())
    })
}

/// Ask a running `nf_sender_run` to return (thread-safe).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_sender_stop(sender: *const nf_sender) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let s = unsafe { handle(sender, "sender")? };
        s.sender.stop.store(true, Ordering::SeqCst);
        Ok(())
    })
}

/// Clear a previous stop so `nf_sender_run` can be called again.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_sender_reset(sender: *const nf_sender) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let s = unsafe { handle(sender, "sender")? };
        s.sender.stop.store(false, Ordering::SeqCst);
        Ok(())
    })
}

fn put_state(o: &mut nf_stream_state, st: StreamState) {
    put_buf(&mut o.stream_id, st.stream_id);
    put_buf(&mut o.state, st.state);
    o.next_seq = st.next_seq;
    o.n_samples = st.n_samples;
    o.suspect = st.suspect;
}

fn rpc_err(e: RpcError) -> Error {
    Error::new(
        NF_ERR_TRANSPORT,
        format!("rpc code {}: {}", e.code, e.message),
    )
}

unsafe fn state_call(
    sender: *const nf_sender,
    transport: *const nf_ingest_transport,
    out_state: *mut nf_stream_state,
    call: impl FnOnce(&Sender, &CIngest) -> std::result::Result<StreamState, RpcError>,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (s, t, o) = unsafe {
            (
                handle(sender, "sender")?,
                handle(transport, "transport")?,
                out(out_state, "out_state")?,
            )
        };
        let st = call(&s.sender, &CIngest(*t)).map_err(rpc_err)?;
        put_state(o, st);
        Ok(())
    })
}

/// Ask the platform for the stream's state (GetStreamState). Failures are `NF_ERR_TRANSPORT`.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_sender_state(
    sender: *const nf_sender,
    transport: *const nf_ingest_transport,
    out_state: *mut nf_stream_state,
) -> nf_status {
    // SAFETY: forwarded contract.
    unsafe { state_call(sender, transport, out_state, |s, t| s.state(t)) }
}

/// Close the stream on the platform (FinishStream). This does NOT upload: stop all writers,
/// flush them, and run `nf_sender_run` until `nf_wal_len()` is 0 first. While the WAL still holds
/// records, or while `nf_sender_run` is active, this returns `NF_ERR_INVALID_ARG` and does not
/// call FinishStream (a closed stream can never receive them). If a writer adds records while
/// FinishStream is in flight, the stream is closed but the call returns `NF_ERR_INVALID_ARG`
/// reporting how many records can no longer be uploaded; on that error the stream IS closed but,
/// as for every error, `out_state` is not written (call `nf_sender_state` to read it). To abandon
/// unsent records on purpose, delete the WAL directory. (CABI-T2)
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_sender_finish(
    sender: *const nf_sender,
    transport: *const nf_ingest_transport,
    out_state: *mut nf_stream_state,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (s, t, o) = unsafe {
            (
                handle(sender, "sender")?,
                handle(transport, "transport")?,
                out(out_state, "out_state")?,
            )
        };
        let _finishing = s.enter("nf_sender_finish")?;
        let pending = s.wal.len();
        if pending > 0 {
            return Err(Error::invalid(format!(
                "WAL still holds {pending} chunks; drain first (flush the writer, nf_sender_run \
                 until nf_wal_len() == 0)"
            )));
        }
        let st = s.sender.finish(&CIngest(*t)).map_err(rpc_err)?;
        let late = s.wal.len();
        if late > 0 {
            return Err(Error::invalid(format!(
                "stream closed but {late} chunks were written after finish started; they cannot \
                 be uploaded (stop all writers before finishing)"
            )));
        }
        put_state(o, st);
        Ok(())
    })
}

/// Free the strings of a stream state (NULL is a no-op).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_stream_state_free(state: *mut nf_stream_state) {
    if !crate::usable(state) {
        return;
    }
    // SAFETY: a valid, aligned state (checked above).
    if let Some(s) = unsafe { state.as_mut() } {
        // SAFETY: buffers filled by put_state or zeroed.
        unsafe {
            crate::nf_buf_free(&mut s.stream_id);
            crate::nf_buf_free(&mut s.state);
        }
    }
}

/// Sender counters (thread-safe).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_sender_get_stats(
    sender: *const nf_sender,
    out_stats: *mut nf_sender_stats,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (s, o) = unsafe { (handle(sender, "sender")?, out(out_stats, "out_stats")?) };
        let st = s.sender.stats();
        *o = nf_sender_stats {
            calls: st.calls,
            chunks_acked: st.chunks_acked,
            rpc_errors: st.rpc_errors,
            next_seq_acked: st.next_seq_acked,
            fatal: st.fatal.is_some(),
        };
        Ok(())
    })
}

/// The fatal error that stopped the sender; `NF_ERR_NOT_FOUND` if there is none.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_sender_fatal_error(
    sender: *const nf_sender,
    out_message: *mut nf_buf,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (s, o) = unsafe { (handle(sender, "sender")?, out(out_message, "out_message")?) };
        let m = s
            .sender
            .stats()
            .fatal
            .ok_or_else(|| Error::new(NF_ERR_NOT_FOUND, "no fatal error"))?;
        put_buf(o, m);
        Ok(())
    })
}
