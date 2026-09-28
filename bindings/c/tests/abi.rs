//! Behaviour of the C ABI beyond the hash vectors: NULL and error paths, local recordings and
//! the chunk cache, the provenance recorder, the streaming client against a fake ingest server
//! and the API client against a fake HTTP stack. Everything goes through the exported functions.

mod common;
mod fixture;

use std::ffi::{CStr, c_char, c_void};
use std::path::PathBuf;
use std::sync::Mutex;
use std::sync::atomic::{AtomicU32, Ordering};

use common::*;
use neuroforge::api::*;
use neuroforge::hashing::*;
use neuroforge::local::*;
use neuroforge::provenance::*;
use neuroforge::streaming::*;
use neuroforge::*;
use nf_core::stream::proto::{Chunk, StreamAck, StreamState};

fn temp_dir(name: &str) -> PathBuf {
    static N: AtomicU32 = AtomicU32::new(0);
    let d = std::env::temp_dir().join(format!(
        "nf-cabi-{}-{}-{name}",
        std::process::id(),
        N.fetch_add(1, Ordering::SeqCst)
    ));
    let _ = std::fs::remove_dir_all(&d);
    std::fs::create_dir_all(&d).unwrap();
    d
}

fn path_c(p: &std::path::Path) -> std::ffi::CString {
    c(p.to_str().unwrap())
}

fn null<T>() -> *const T {
    std::ptr::null()
}

fn null_mut<T>() -> *mut T {
    std::ptr::null_mut()
}

// ---------------------------------------------------------------- errors and NULL safety
#[test]
fn null_arguments_are_errors_not_crashes() {
    let data = b"x";
    assert_eq!(
        status_of(|o| unsafe { nf_blob_id(null(), 5, o) }),
        NF_ERR_NULL_ARG
    );
    assert!(last_error().contains("data is NULL"));
    assert_eq!(
        unsafe { nf_blob_id(data.as_ptr(), 1, null_mut()) },
        NF_ERR_NULL_ARG
    );
    // NULL with length 0 is an empty input
    assert_eq!(
        text_out(|o| unsafe { nf_blob_id(null(), 0, o) }),
        "blob:sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    );
    assert!(!unsafe { nf_is_valid_id(null()) });
    assert_eq!(
        status_of(|o| unsafe { nf_training_subject_hash(null(), null(), o) }),
        NF_ERR_NULL_ARG
    );
    let mut rec: *mut nf_recording = null_mut();
    assert_eq!(
        unsafe { nf_recording_open(null(), null(), &mut rec) },
        NF_ERR_NULL_ARG
    );
    assert!(rec.is_null(), "outputs are written only on success");
    let mut info = std::mem::MaybeUninit::<nf_recording_info>::uninit();
    assert_eq!(
        unsafe { nf_recording_get_info(null(), info.as_mut_ptr()) },
        NF_ERR_NULL_ARG
    );
    assert_eq!(unsafe { nf_sender_stop(null()) }, NF_ERR_NULL_ARG);
    assert_eq!(unsafe { nf_wal_len(null(), null_mut()) }, NF_ERR_NULL_ARG);
    assert_eq!(unsafe { nf_chunk_rank(null()) }, 0);
    assert!(unsafe { nf_chunk_data(null(), null_mut()) }.is_null());
    assert_eq!(unsafe { nf_http_response_status(null()) }, 0);
    // every free accepts NULL
    unsafe {
        nf_recording_free(null_mut());
        nf_chunk_cache_free(null_mut());
        nf_chunk_free(null_mut());
        nf_prov_recorder_free(null_mut());
        nf_device_key_free(null_mut());
        nf_wal_free(null_mut());
        nf_stream_writer_free(null_mut());
        nf_sender_free(null_mut());
        nf_api_client_free(null_mut());
        nf_http_response_free(null_mut());
        nf_stream_state_free(null_mut());
        nf_buf_free(null_mut());
    }
}

#[test]
fn invalid_input_is_reported() {
    let bad_utf8 = [0x7b_u8, 0xff, 0x7d];
    assert_eq!(
        status_of(|o| unsafe { nf_canonicalize(bad_utf8.as_ptr(), 3, o) }),
        NF_ERR_INVALID_ARG
    );
    let dup = br#"{"a":1,"a":2}"#;
    assert_eq!(
        status_of(|o| unsafe { nf_canonicalize(dup.as_ptr(), dup.len(), o) }),
        NF_ERR_CANONICAL
    );
    assert!(last_error().to_lowercase().contains("duplicate"));
    let shape = [2u64];
    assert_eq!(
        status_of(|o| unsafe { nf_chunk_id(99, shape.as_ptr(), 1, b"ab".as_ptr(), 2, o) }),
        NF_ERR_INVALID_ARG
    );
    // wrong data length for the shape
    assert_eq!(
        status_of(|o| unsafe {
            nf_chunk_id(NF_DTYPE_INT16, shape.as_ptr(), 1, b"ab".as_ptr(), 2, o)
        }),
        NF_ERR_CANONICAL
    );
    let mut dt = 0;
    assert_eq!(
        unsafe { nf_dtype_parse(cp(&c("complex64")), &mut dt) },
        NF_ERR_INVALID_ARG
    );
    let not_array = br#"{"a":1}"#;
    assert_eq!(
        status_of(|o| unsafe { nf_verify_prov_chain(not_array.as_ptr(), not_array.len(), o) }),
        NF_ERR_INVALID_ARG
    );
    // a successful call clears the previous error
    assert_eq!(status_of(|o| unsafe { nf_format_number(1.5, o) }), NF_OK);
    assert_eq!(last_error(), "");
    // SAFETY: static strings
    let name = |s| {
        unsafe { CStr::from_ptr(nf_status_name(s)) }
            .to_str()
            .unwrap()
    };
    assert_eq!(name(NF_ERR_VERIFY), "NF_ERR_VERIFY");
    assert_eq!(name(1234), "NF_ERR_UNKNOWN");
}

// ---------------------------------------------------------------- recordings and cache
#[test]
fn recording_and_cache_reads() {
    let root = temp_dir("fixture");
    let chunk_id = fixture::write(&root);
    let root_c = path_c(&root);

    let mut rec: *mut nf_recording = null_mut();
    let id = c(fixture::RECORDING_ID);
    assert_eq!(
        unsafe { nf_recording_open(root_c.as_ptr(), id.as_ptr(), &mut rec) },
        NF_OK,
        "{}",
        last_error()
    );
    let mut info = nf_recording_info {
        n_samples: 0,
        n_channels: 0,
        sfreq: 0.0,
        dtype: 0,
        has_timestamps: false,
    };
    assert_eq!(unsafe { nf_recording_get_info(rec, &mut info) }, NF_OK);
    assert_eq!(
        (
            info.n_samples,
            info.n_channels,
            info.sfreq,
            info.dtype,
            info.has_timestamps
        ),
        (fixture::N_SAMPLES, 3, fixture::SFREQ, NF_DTYPE_INT16, true)
    );
    for (i, name) in fixture::CHANNELS.iter().enumerate() {
        let n = text_out(|o| unsafe { nf_recording_channel_name(rec, i as u64, o) });
        assert_eq!(&n, name);
        assert_eq!(
            text_out(|o| unsafe { nf_recording_channel_unit(rec, i as u64, o) }),
            "uV"
        );
    }
    assert_eq!(
        status_of(|o| unsafe { nf_recording_channel_name(rec, 3, o) }),
        NF_ERR_INVALID_ARG
    );

    // size query, too small, then a read that crosses chunk boundaries (250 x 2)
    let mut need = 0usize;
    assert_eq!(
        unsafe { nf_recording_read(rec, 240, 510, null_mut(), 0, &mut need) },
        NF_ERR_BUFFER_TOO_SMALL
    );
    assert_eq!(need, 270 * 3 * 2);
    let mut buf = vec![0u8; need];
    assert_eq!(
        unsafe { nf_recording_read(rec, 240, 510, buf.as_mut_ptr(), need - 1, &mut need) },
        NF_ERR_BUFFER_TOO_SMALL
    );
    assert_eq!(
        unsafe { nf_recording_read(rec, 240, 510, buf.as_mut_ptr(), buf.len(), &mut need) },
        NF_OK
    );
    for (k, v) in buf.as_chunks::<2>().0.iter().enumerate() {
        let (i, ch) = (240 + k as u64 / 3, k as u64 % 3);
        assert_eq!(i16::from_le_bytes([v[0], v[1]]), fixture::sample(i, ch));
    }
    // stop is clamped; start after stop is an error
    assert_eq!(
        unsafe { nf_recording_read(rec, 990, 5000, null_mut(), 0, &mut need) },
        NF_ERR_BUFFER_TOO_SMALL
    );
    assert_eq!(need, 10 * 3 * 2);
    assert_eq!(
        unsafe { nf_recording_read(rec, 20, 10, null_mut(), 0, &mut need) },
        NF_ERR_INVALID_ARG
    );
    let mut ts = vec![0f64; 4];
    let mut n = 0usize;
    assert_eq!(
        unsafe { nf_recording_read_timestamps(rec, 998, 1002, ts.as_mut_ptr(), 4, &mut n) },
        NF_OK
    );
    assert_eq!(n, 2);
    assert_eq!(
        &ts[..2],
        &[fixture::timestamp(998), fixture::timestamp(999)]
    );
    unsafe { nf_recording_free(rec) };

    // missing recording and a key that escapes the root
    let mut rec2: *mut nf_recording = null_mut();
    let missing = c("nope");
    assert_eq!(
        unsafe { nf_recording_open(root_c.as_ptr(), missing.as_ptr(), &mut rec2) },
        NF_ERR_NOT_FOUND
    );
    let escape = c("../x");
    assert_eq!(
        unsafe { nf_recording_open(root_c.as_ptr(), escape.as_ptr(), &mut rec2) },
        NF_ERR_INVALID_ARG
    );

    // chunk cache
    let cache_dir = path_c(&root.join("cache"));
    let mut cache: *mut nf_chunk_cache = null_mut();
    assert_eq!(
        unsafe { nf_chunk_cache_open(cache_dir.as_ptr(), 1 << 20, &mut cache) },
        NF_OK
    );
    let mut chunk: *mut nf_chunk = null_mut();
    let cid = c(&chunk_id);
    assert_eq!(
        unsafe { nf_chunk_cache_get(cache, cid.as_ptr(), &mut chunk) },
        NF_OK
    );
    assert_eq!(unsafe { nf_chunk_dtype(chunk) }, NF_DTYPE_FLOAT32);
    assert_eq!(unsafe { nf_chunk_rank(chunk) }, 2);
    // SAFETY: rank entries owned by the chunk
    let shape = unsafe { std::slice::from_raw_parts(nf_chunk_shape(chunk), 2) };
    assert_eq!(shape, &[2, 3]);
    let mut len = 0usize;
    let p = unsafe { nf_chunk_data(chunk, &mut len) };
    // SAFETY: len bytes owned by the chunk
    let bytes = unsafe { std::slice::from_raw_parts(p, len) };
    let vals: Vec<f32> = bytes
        .as_chunks::<4>()
        .0
        .iter()
        .map(|b| f32::from_le_bytes(*b))
        .collect();
    assert_eq!(vals, fixture::chunk_values());
    // the ID recomputed through the ABI matches the cache key
    let again = text_out(|o| unsafe {
        nf_chunk_id(
            NF_DTYPE_FLOAT32,
            shape.as_ptr(),
            2,
            bytes.as_ptr(),
            bytes.len(),
            o,
        )
    });
    assert_eq!(again, chunk_id);
    unsafe { nf_chunk_free(chunk) };
    let absent = c(&format!("chunk:sha256:{}", "0".repeat(64)));
    assert_eq!(
        unsafe { nf_chunk_cache_get(cache, absent.as_ptr(), &mut chunk) },
        NF_ERR_NOT_FOUND
    );
    let blob = c(&format!("blob:sha256:{}", "0".repeat(64)));
    assert_eq!(
        unsafe { nf_chunk_cache_get(cache, blob.as_ptr(), &mut chunk) },
        NF_ERR_INVALID_ARG
    );
    let mut size = 0u64;
    assert_eq!(unsafe { nf_chunk_cache_size(cache, &mut size) }, NF_OK);
    assert!(size > 24);
    unsafe { nf_chunk_cache_free(cache) };
    let _ = std::fs::remove_dir_all(&root);
}

/// Rewrite `nf_signal.scale` / `offset` in the fixture's group metadata.
fn set_scale_offset(root: &std::path::Path, scale: serde_json::Value, offset: serde_json::Value) {
    let p = root.join(fixture::RECORDING_ID).join("zarr.json");
    let mut g: serde_json::Value = serde_json::from_slice(&std::fs::read(&p).unwrap()).unwrap();
    g["attributes"]["nf_signal"]["scale"] = scale;
    g["attributes"]["nf_signal"]["offset"] = offset;
    std::fs::write(&p, serde_json::to_vec(&g).unwrap()).unwrap();
}

fn open_rec(root: &std::path::Path) -> (nf_status, *mut nf_recording) {
    let (root_c, id) = (path_c(root), c(fixture::RECORDING_ID));
    let mut rec: *mut nf_recording = null_mut();
    let s = unsafe { nf_recording_open(root_c.as_ptr(), id.as_ptr(), &mut rec) };
    (s, rec)
}

#[test]
fn recording_read_f64_is_physical() {
    let root = temp_dir("f64");
    fixture::write(&root);
    // unit scale: the doubles equal the stored int16 values
    let (s, rec) = open_rec(&root);
    assert_eq!(s, NF_OK, "{}", last_error());
    let mut n = 0usize;
    assert_eq!(
        unsafe { nf_recording_read_f64(rec, 998, 5000, null_mut(), 0, &mut n) },
        NF_ERR_BUFFER_TOO_SMALL
    );
    assert_eq!(n, 2 * 3);
    let mut out = vec![0f64; n];
    assert_eq!(
        unsafe { nf_recording_read_f64(rec, 998, 5000, out.as_mut_ptr(), n - 1, &mut n) },
        NF_ERR_BUFFER_TOO_SMALL
    );
    assert_eq!(
        unsafe { nf_recording_read_f64(rec, 998, 5000, out.as_mut_ptr(), out.len(), &mut n) },
        NF_OK
    );
    for (k, v) in out.iter().enumerate() {
        let (i, ch) = (998 + k as u64 / 3, k as u64 % 3);
        assert_eq!(*v, f64::from(fixture::sample(i, ch)));
    }
    assert_eq!(
        unsafe { nf_recording_read_f64(rec, 1000, 1000, null_mut(), 0, &mut n) },
        NF_OK,
        "an empty range needs no buffer"
    );
    assert_eq!(n, 0);
    unsafe { nf_recording_free(rec) };

    // per-channel scale and offset: physical = stored * scale + offset
    let (scale, offset) = ([0.5, 1.0, 2.0], [0.0, 10.0, -1.0]);
    set_scale_offset(&root, serde_json::json!(scale), serde_json::json!(offset));
    let (s, rec) = open_rec(&root);
    assert_eq!(s, NF_OK, "{}", last_error());
    let mut out = vec![0f64; 30];
    assert_eq!(
        unsafe { nf_recording_read_f64(rec, 240, 250, out.as_mut_ptr(), 30, &mut n) },
        NF_OK
    );
    for (k, v) in out.iter().enumerate() {
        let (i, ch) = (240 + k as u64 / 3, k as u64 % 3);
        let want = f64::from(fixture::sample(i, ch)) * scale[ch as usize] + offset[ch as usize];
        assert_eq!(*v, want, "sample {i} channel {ch}");
    }
    // the stored read stays exact
    let mut raw = [0u8; 6];
    let mut len = 0usize;
    assert_eq!(
        unsafe { nf_recording_read(rec, 240, 241, raw.as_mut_ptr(), 6, &mut len) },
        NF_OK
    );
    assert_eq!(
        i16::from_le_bytes([raw[2], raw[3]]),
        fixture::sample(240, 1)
    );
    unsafe { nf_recording_free(rec) };

    // malformed scale metadata is refused at open
    set_scale_offset(
        &root,
        serde_json::json!([1.0, 2.0]),
        serde_json::json!(offset),
    );
    assert_eq!(open_rec(&root).0, NF_ERR_CORRUPT);
    let _ = std::fs::remove_dir_all(&root);
}

// ---------------------------------------------------------------- provenance
#[test]
fn provenance_recorder_round_trip() {
    let dir = temp_dir("prov");
    let dir_c = path_c(&dir);
    let chain = c("session-1");
    let open = || {
        let mut r: *mut nf_prov_recorder = null_mut();
        assert_eq!(
            unsafe { nf_prov_recorder_open(dir_c.as_ptr(), chain.as_ptr(), &mut r) },
            NF_OK,
            "{}",
            last_error()
        );
        r
    };
    let r = open();
    let mut seq = 99u64;
    let mut id = empty();
    assert_eq!(
        unsafe { nf_prov_recorder_head(r, &mut seq, &mut id) },
        NF_ERR_NOT_FOUND
    );
    let recs = br#"[{"type":"entity","id":"urn:nf:rec:1","label":"recording"},
                   {"type":"activity","id":"urn:nf:run:1","label":"filter"},
                   {"type":"edge","rel":"used","from":"urn:nf:run:1","to":"urn:nf:rec:1"}]"#;
    let mut ids = Vec::new();
    for _ in 0..2 {
        let mut b = empty();
        assert_eq!(
            unsafe { nf_prov_recorder_record(r, recs.as_ptr(), recs.len(), &mut seq, &mut b) },
            NF_OK,
            "{}",
            last_error()
        );
        ids.push(take_str(b));
    }
    assert_eq!(seq, 1);
    let bad = br#"[{"type":"edge","rel":"controls","from":"a","to":"b"}]"#;
    assert_eq!(
        unsafe { nf_prov_recorder_record(r, bad.as_ptr(), bad.len(), null_mut(), null_mut()) },
        NF_ERR_INVALID_ARG
    );
    let mut n = 0usize;
    assert_eq!(unsafe { nf_prov_recorder_pending_count(r, &mut n) }, NF_OK);
    assert_eq!(n, 2);
    // the canonical upload bytes hash to the batch ID, and the batches form a valid chain
    let mut docs = Vec::new();
    for i in 0..2 {
        let (mut b_id, mut canon) = (empty(), empty());
        assert_eq!(
            unsafe { nf_prov_recorder_pending(r, i, &mut seq, &mut b_id, &mut canon) },
            NF_OK
        );
        let canon = take(canon);
        let recomputed = text_out(|o| unsafe { nf_prov_batch_id(canon.as_ptr(), canon.len(), o) });
        assert_eq!(recomputed, take_str(b_id));
        docs.push(String::from_utf8(canon).unwrap());
    }
    let arr = format!("[{}]", docs.join(","));
    let verified = text_out(|o| unsafe { nf_verify_prov_chain(arr.as_ptr(), arr.len(), o) });
    assert_eq!(verified, ids.join("\n"));
    assert_eq!(unsafe { nf_prov_recorder_mark_synced(r, 0) }, NF_OK);
    assert_eq!(
        unsafe { nf_prov_recorder_mark_synced(r, 7) },
        NF_ERR_INVALID_ARG
    );
    unsafe { nf_prov_recorder_free(r) };
    // reopened from disk: verified, same head, one pending
    let r = open();
    let mut head = empty();
    assert_eq!(
        unsafe { nf_prov_recorder_head(r, &mut seq, &mut head) },
        NF_OK
    );
    assert_eq!((seq, take_str(head)), (1, ids[1].clone()));
    assert_eq!(unsafe { nf_prov_recorder_pending_count(r, &mut n) }, NF_OK);
    assert_eq!(n, 1);
    assert_eq!(unsafe { nf_prov_recorder_len(r, &mut n) }, NF_OK);
    assert_eq!(n, 2);
    unsafe { nf_prov_recorder_free(r) };
    let _ = std::fs::remove_dir_all(&dir);
}

// ---------------------------------------------------------------- streaming
/// A fake IngestService: verifies every chunk signature, keeps the committed next_seq.
struct FakeIngest {
    public_key: [u8; 32],
    next_seq: Mutex<u64>,
    samples: Mutex<u64>,
    finished: Mutex<bool>,
    fail_code: i32,
    auth_seen: Mutex<Vec<String>>,
    chunk_calls: AtomicU32,
    finish_calls: AtomicU32,
    /// A writer (as usize) that pushes one full chunk while FinishStream is in flight.
    late_writer: Mutex<Option<usize>>,
}

impl FakeIngest {
    fn new(public_key: [u8; 32], fail_code: i32) -> Self {
        Self {
            public_key,
            next_seq: Mutex::new(0),
            samples: Mutex::new(0),
            finished: Mutex::new(false),
            fail_code,
            auth_seen: Mutex::new(Vec::new()),
            chunk_calls: AtomicU32::new(0),
            finish_calls: AtomicU32::new(0),
            late_writer: Mutex::new(None),
        }
    }
    fn state(&self) -> Vec<u8> {
        StreamState {
            stream_id: "s-1".into(),
            next_seq: *self.next_seq.lock().unwrap(),
            n_samples: *self.samples.lock().unwrap(),
            state: if *self.finished.lock().unwrap() {
                "finished".into()
            } else {
                "open".into()
            },
            suspect: false,
        }
        .encode()
    }
}

unsafe fn fake<'a>(user: *mut c_void) -> &'a FakeIngest {
    // SAFETY: the tests pass a live FakeIngest as `user`.
    unsafe { &*user.cast::<FakeIngest>() }
}

unsafe fn reply(r: *mut nf_reply, bytes: &[u8]) {
    assert_eq!(
        unsafe { nf_reply_set(r, bytes.as_ptr(), bytes.len()) },
        NF_OK
    );
}

unsafe extern "C" fn get_state(
    user: *mut c_void,
    _req: *const u8,
    _len: usize,
    auth: *const c_char,
    _timeout: f64,
    r: *mut nf_reply,
) -> i32 {
    let f = unsafe { fake(user) };
    let auth = unsafe { CStr::from_ptr(auth) }.to_str().unwrap().to_owned();
    f.auth_seen.lock().unwrap().push(auth);
    if f.fail_code != 0 {
        unsafe { reply(r, b"server unavailable") };
        return f.fail_code;
    }
    unsafe { reply(r, &f.state()) };
    0
}

unsafe extern "C" fn stream_chunks(
    user: *mut c_void,
    chunks: *const nf_bytes,
    n: usize,
    _auth: *const c_char,
    _timeout: f64,
    r: *mut nf_reply,
) -> i32 {
    let f = unsafe { fake(user) };
    f.chunk_calls.fetch_add(1, Ordering::SeqCst);
    // SAFETY: n views valid during the call
    let views = unsafe { std::slice::from_raw_parts(chunks, n) };
    let mut next = f.next_seq.lock().unwrap();
    for v in views {
        let bytes = unsafe { std::slice::from_raw_parts(v.data, v.len) };
        let c = Chunk::decode(bytes).unwrap();
        assert!(
            nf_core::stream::sign::verify_chunk_full(&c, &f.public_key),
            "chunk {} does not verify",
            c.seq
        );
        if c.seq == *next {
            *next += 1;
            *f.samples.lock().unwrap() += u64::from(c.n_samples);
        }
    }
    let ack = StreamAck {
        stream_id: "s-1".into(),
        next_seq: *next,
        accepted: n as u32,
        duplicates: 0,
        suspect: 0,
    };
    unsafe { reply(r, &ack.encode()) };
    0
}

unsafe extern "C" fn finish(
    user: *mut c_void,
    _req: *const u8,
    _len: usize,
    _auth: *const c_char,
    _timeout: f64,
    r: *mut nf_reply,
) -> i32 {
    let f = unsafe { fake(user) };
    f.finish_calls.fetch_add(1, Ordering::SeqCst);
    if let Some(w) = *f.late_writer.lock().unwrap() {
        // a writer racing the finish: one full chunk of float32 x 2 channels (chunk_samples 100)
        let samples: Vec<u8> = (0..200).flat_map(|k| (k as f32).to_le_bytes()).collect();
        let ts: Vec<f64> = (0..100).map(|i| 50.0 + i as f64 / 1000.0).collect();
        let s = unsafe {
            nf_stream_writer_push(
                w as *const nf_stream_writer,
                samples.as_ptr(),
                samples.len(),
                ts.as_ptr(),
                ts.len(),
                null_mut(),
            )
        };
        assert_eq!(s, NF_OK);
    }
    *f.finished.lock().unwrap() = true;
    unsafe { reply(r, &f.state()) };
    0
}

fn transport(f: &FakeIngest) -> nf_ingest_transport {
    nf_ingest_transport {
        user: (f as *const FakeIngest).cast_mut().cast(),
        get_stream_state: Some(get_state),
        stream_chunks: Some(stream_chunks),
        finish_stream: Some(finish),
    }
}

struct SendPtr<T>(*const T);
// SAFETY: the sender handle is thread-safe for run/stop/stats (header contract).
unsafe impl<T> Send for SendPtr<T> {}

#[test]
fn streaming_client_end_to_end() {
    let dir = temp_dir("wal");
    let seed = [42u8; 32];
    let mut key: *mut nf_device_key = null_mut();
    assert_eq!(
        unsafe { nf_device_key_from_seed(seed.as_ptr(), 32, &mut key) },
        NF_OK
    );
    assert_eq!(
        unsafe { nf_device_key_from_seed(seed.as_ptr(), 31, &mut key) },
        NF_ERR_INVALID_ARG
    );
    let mut pk = [0u8; 32];
    assert_eq!(
        unsafe { nf_device_key_public_key(key, pk.as_mut_ptr()) },
        NF_OK
    );

    // device token verifies with the public key
    let (t, d, s) = (c("tenant-a"), c("dev-1"), c("s-1"));
    let token = text_out(|o| unsafe {
        nf_device_key_token(key, t.as_ptr(), d.as_ptr(), s.as_ptr(), 300, o)
    });
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_secs() as i64;
    let claims =
        text_out(|o| unsafe { nf_verify_device_token(c(&token).as_ptr(), pk.as_ptr(), now, o) });
    assert!(claims.contains("\"device_id\":\"dev-1\""));
    assert_eq!(
        status_of(|o| unsafe {
            nf_device_key_token(key, t.as_ptr(), d.as_ptr(), s.as_ptr(), 601, o)
        }),
        NF_ERR_INVALID_ARG
    );

    let wal_key = [7u8; 32];
    let mut wal: *mut nf_wal = null_mut();
    let dir_c = path_c(&dir);
    assert_eq!(
        unsafe {
            nf_wal_open(
                dir_c.as_ptr(),
                s.as_ptr(),
                wal_key.as_ptr(),
                null(),
                false,
                &mut wal,
            )
        },
        NF_OK,
        "{}",
        last_error()
    );
    let mut writer: *mut nf_stream_writer = null_mut();
    assert_eq!(
        unsafe { nf_stream_writer_new(s.as_ptr(), NF_DTYPE_UINT8, 2, 100, key, wal, &mut writer) },
        NF_ERR_INVALID_ARG,
        "uint8 is not a stream dtype"
    );
    assert_eq!(
        unsafe {
            nf_stream_writer_new(s.as_ptr(), NF_DTYPE_FLOAT32, 2, 100, key, wal, &mut writer)
        },
        NF_OK,
        "{}",
        last_error()
    );
    // 250 samples x 2 channels: two full chunks of 100, 50 buffered
    let samples: Vec<u8> = (0..500)
        .flat_map(|k| (k as f32 * 0.25).to_le_bytes())
        .collect();
    let ts: Vec<f64> = (0..250).map(|i| 10.0 + i as f64 / 1000.0).collect();
    let mut chunks = 0usize;
    assert_eq!(
        unsafe { nf_stream_writer_add_clock_offset(writer, 9.5, -0.001) },
        NF_OK
    );
    assert_eq!(
        unsafe {
            nf_stream_writer_push(
                writer,
                samples.as_ptr(),
                samples.len(),
                ts.as_ptr(),
                ts.len(),
                &mut chunks,
            )
        },
        NF_OK
    );
    assert_eq!(chunks, 2);
    // mismatched sample bytes
    assert_eq!(
        unsafe { nf_stream_writer_push(writer, samples.as_ptr(), 3, ts.as_ptr(), 1, null_mut()) },
        NF_ERR_INVALID_ARG
    );
    let mut buffered = 0usize;
    assert_eq!(
        unsafe { nf_stream_writer_buffered_samples(writer, &mut buffered) },
        NF_OK
    );
    assert_eq!(buffered, 50);
    let mut wrote = false;
    assert_eq!(unsafe { nf_stream_writer_flush(writer, &mut wrote) }, NF_OK);
    assert!(wrote);
    let mut stats = nf_writer_stats::default();
    assert_eq!(
        unsafe { nf_stream_writer_get_stats(writer, &mut stats) },
        NF_OK
    );
    assert_eq!((stats.chunks, stats.samples), (3, 250));
    let mut next = 0u64;
    assert_eq!(
        unsafe { nf_stream_writer_next_seq(writer, &mut next) },
        NF_OK
    );
    assert_eq!(next, 3);
    let mut wal_len = 0usize;
    assert_eq!(unsafe { nf_wal_len(wal, &mut wal_len) }, NF_OK);
    assert_eq!(wal_len, 3);

    // sender: failing transport first
    let mut cfg = nf_sender_config {
        batch_max: 0,
        linger_s: 0.0,
        call_timeout_s: 0.0,
        backoff_min_s: 0.0,
        backoff_max_s: 0.0,
    };
    assert_eq!(unsafe { nf_sender_config_default(&mut cfg) }, NF_OK);
    assert_eq!(cfg.batch_max, 50);
    cfg.linger_s = 0.01;
    cfg.backoff_min_s = 0.001;
    cfg.backoff_max_s = 0.01;
    let mut sender: *mut nf_sender = null_mut();
    assert_eq!(
        unsafe {
            nf_sender_new(
                t.as_ptr(),
                d.as_ptr(),
                s.as_ptr(),
                key,
                wal,
                &cfg,
                &mut sender,
            )
        },
        NF_OK
    );
    let down = FakeIngest::new(pk, 14);
    let tr_down = transport(&down);
    let mut state = nf_stream_state {
        stream_id: empty(),
        next_seq: 0,
        n_samples: 0,
        state: empty(),
        suspect: false,
    };
    assert_eq!(
        unsafe { nf_sender_state(sender, &tr_down, &mut state) },
        NF_ERR_TRANSPORT
    );
    assert!(last_error().contains("server unavailable"));
    assert!(down.auth_seen.lock().unwrap()[0].starts_with("NFDevice nfd1."));

    // the handles can be freed: writer and sender keep their own references
    unsafe {
        nf_stream_writer_free(writer);
        nf_device_key_free(key);
    }

    // healthy transport: run on a thread, stop once everything is acked
    let server = FakeIngest::new(pk, 0);
    let tr = transport(&server);
    let (sp, tp) = (
        SendPtr(sender.cast_const()),
        SendPtr(&tr as *const nf_ingest_transport),
    );
    std::thread::scope(|scope| {
        let h = scope.spawn(move || {
            let (sp, tp) = (sp, tp);
            unsafe { nf_sender_run(sp.0, tp.0) }
        });
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(20);
        loop {
            let mut st = nf_sender_stats::default();
            assert_eq!(unsafe { nf_sender_get_stats(sender, &mut st) }, NF_OK);
            if st.chunks_acked == 3 {
                break;
            }
            assert!(!st.fatal, "sender stopped");
            assert!(
                std::time::Instant::now() < deadline,
                "sender did not ack in time"
            );
            std::thread::sleep(std::time::Duration::from_millis(10));
        }
        assert_eq!(unsafe { nf_sender_stop(sender) }, NF_OK);
        assert_eq!(h.join().unwrap(), NF_OK);
    });
    assert_eq!(unsafe { nf_wal_len(wal, &mut wal_len) }, NF_OK);
    assert_eq!(wal_len, 0, "acked records leave the WAL");
    let mut fatal = empty();
    assert_eq!(
        unsafe { nf_sender_fatal_error(sender, &mut fatal) },
        NF_ERR_NOT_FOUND
    );
    assert_eq!(unsafe { nf_sender_finish(sender, &tr, &mut state) }, NF_OK);
    assert_eq!(state.next_seq, 3);
    assert_eq!(state.n_samples, 250);
    // SAFETY: filled by the library
    let st = unsafe { CStr::from_ptr(state.state.data.cast()) }
        .to_str()
        .unwrap()
        .to_owned();
    assert_eq!(st, "finished");
    unsafe {
        nf_stream_state_free(&mut state);
        nf_stream_state_free(&mut state);
        nf_sender_free(sender);
        nf_wal_free(wal);
    }
    let _ = std::fs::remove_dir_all(&dir);
}

#[test]
fn ephemeral_and_dpapi_keys() {
    let dir = temp_dir("keys");
    let (dir_c, s) = (path_c(&dir), c("s-2"));
    // CABI-L3: no key source is an error; the in-memory key must be asked for explicitly
    let mut wal: *mut nf_wal = null_mut();
    assert_eq!(
        unsafe { nf_wal_open(dir_c.as_ptr(), s.as_ptr(), null(), null(), true, &mut wal) },
        NF_ERR_INVALID_ARG
    );
    assert!(wal.is_null());
    assert!(
        last_error().contains("nf_wal_open_ephemeral"),
        "{}",
        last_error()
    );
    assert_eq!(
        unsafe { nf_wal_open_ephemeral(dir_c.as_ptr(), s.as_ptr(), true, &mut wal) },
        NF_OK
    );
    let mut n = 99usize;
    assert_eq!(unsafe { nf_wal_len(wal, &mut n) }, NF_OK);
    assert_eq!(n, 0);
    unsafe { nf_wal_free(wal) };
    let mut key: *mut nf_device_key = null_mut();
    assert_eq!(unsafe { nf_device_key_generate(&mut key) }, NF_OK);
    unsafe { nf_device_key_free(key) };
    let sealed = path_c(&dir.join("device.key"));
    let st = unsafe { nf_device_key_open_sealed(sealed.as_ptr(), &mut key) };
    if cfg!(windows) {
        assert_eq!(st, NF_OK, "{}", last_error());
        let mut pk1 = [0u8; 32];
        assert_eq!(
            unsafe { nf_device_key_public_key(key, pk1.as_mut_ptr()) },
            NF_OK
        );
        unsafe { nf_device_key_free(key) };
        // the second open unseals the same key
        assert_eq!(
            unsafe { nf_device_key_open_sealed(sealed.as_ptr(), &mut key) },
            NF_OK
        );
        let mut pk2 = [0u8; 32];
        assert_eq!(
            unsafe { nf_device_key_public_key(key, pk2.as_mut_ptr()) },
            NF_OK
        );
        assert_eq!(pk1, pk2);
        unsafe { nf_device_key_free(key) };
    } else {
        assert_eq!(st, NF_ERR_UNSUPPORTED);
    }
    let _ = std::fs::remove_dir_all(&dir);
}

// ---------------------------------------------------------------- API client
/// A fake HTTP stack: 401 until the refreshed token is used, then 200; `/missing` is a 404
/// problem+json.
/// Requests since index `from` that carried the refreshed (valid) token.
fn authorised_calls(fake: &FakeHttp, from: usize) -> usize {
    fake.calls.lock().unwrap()[from..]
        .iter()
        .filter(|(_, _, h)| {
            h.iter()
                .any(|(k, v)| k == "authorization" && v == "Bearer tok-SECRET-fresh")
        })
        .count()
}

/// Statuses the `/huge` handler got back from `nf_http_reply_set_body` (a callback must not
/// panic, so it records instead of asserting).
static HUGE_STATUSES: Mutex<Vec<nf_status>> = Mutex::new(Vec::new());

/// (method, url, headers) of one exchange.
type Call = (String, String, Vec<(String, String)>);

struct FakeHttp {
    calls: Mutex<Vec<Call>>,
}

unsafe extern "C" fn http_send(
    user: *mut c_void,
    req: *const nf_http_request,
    r: *mut nf_http_reply,
) -> i32 {
    let f = unsafe { &*user.cast::<FakeHttp>() };
    let req = unsafe { &*req };
    let s = |p: *const c_char| unsafe { CStr::from_ptr(p) }.to_str().unwrap().to_owned();
    let headers: Vec<(String, String)> =
        unsafe { std::slice::from_raw_parts(req.headers, req.n_headers) }
            .iter()
            .map(|h| (s(h.name), s(h.value)))
            .collect();
    let (method, url) = (s(req.method), s(req.url));
    f.calls
        .lock()
        .unwrap()
        .push((method, url.clone(), headers.clone()));
    let auth = headers
        .iter()
        .find(|(k, _)| k == "authorization")
        .map(|(_, v)| v.clone())
        .unwrap_or_default();
    unsafe {
        if url.ends_with("/down") {
            let m = b"connection refused";
            nf_http_reply_set_body(r, m.as_ptr(), m.len());
            return 1;
        }
        if auth != "Bearer tok-SECRET-fresh" {
            nf_http_reply_set_status(r, 401);
            return 0;
        }
        if url.contains("/headers") {
            // a hostile server: more headers than NF_MAX_RESPONSE_HEADERS
            nf_http_reply_set_status(r, 200);
            for _ in 0..300 {
                nf_http_reply_add_header(r, c"x-pad".as_ptr(), c"1".as_ptr());
            }
            return 0;
        }
        if url.contains("/fill") {
            // body first, exactly at the cap: a header added afterwards must be refused
            nf_http_reply_set_status(r, 200);
            let body = vec![b'x'; NF_MAX_RESPONSE_BYTES];
            let s1 = nf_http_reply_set_body(r, body.as_ptr(), body.len());
            let s2 = nf_http_reply_add_header(r, c"x-late".as_ptr(), c"1".as_ptr());
            HUGE_STATUSES.lock().unwrap().extend([s1, s2]);
            return 0;
        }
        if url.contains("/huge") {
            // one byte over NF_MAX_RESPONSE_BYTES, then a small body: both must be refused
            nf_http_reply_set_status(r, 200);
            let body = vec![b'x'; NF_MAX_RESPONSE_BYTES + 1];
            let s1 = nf_http_reply_set_body(r, body.as_ptr(), body.len());
            let s2 = nf_http_reply_set_body(r, b"ok".as_ptr(), 2);
            HUGE_STATUSES.lock().unwrap().extend([s1, s2]);
            return 0;
        }
        if url.contains("/big") {
            // a hostile server: 2 MiB of body; the callback ignores the set_body status
            nf_http_reply_set_status(r, 200);
            let body = vec![b'x'; 2 << 20];
            nf_http_reply_set_body(r, body.as_ptr(), body.len());
            return 0;
        }
        if url.contains("/missing") {
            nf_http_reply_set_status(r, 404);
            nf_http_reply_add_header(
                r,
                c"content-type".as_ptr(),
                c"application/problem+json".as_ptr(),
            );
            let body = br#"{"type":"about:blank","title":"Not Found","status":404,"detail":"no such recording"}"#;
            nf_http_reply_set_body(r, body.as_ptr(), body.len());
            return 0;
        }
        nf_http_reply_set_status(r, 200);
        nf_http_reply_add_header(r, c"content-type".as_ptr(), c"application/json".as_ptr());
        let body = br#"{"ok":true}"#;
        nf_http_reply_set_body(r, body.as_ptr(), body.len());
    }
    0
}

unsafe extern "C" fn tokens(_user: *mut c_void, refresh: bool, r: *mut nf_reply) -> i32 {
    let t: &[u8] = if refresh {
        b"tok-SECRET-fresh"
    } else {
        b"tok-SECRET-stale"
    };
    unsafe { nf_reply_set(r, t.as_ptr(), t.len()) };
    0
}

#[test]
fn api_client_auth_refresh_and_problems() {
    assert_eq!(
        unsafe { nf_check_base_url(c"https://api.example.org".as_ptr()) },
        NF_OK
    );
    assert_eq!(
        unsafe { nf_check_base_url(c"http://127.0.0.1:8080".as_ptr()) },
        NF_OK
    );
    assert_eq!(
        unsafe { nf_check_base_url(c"http://api.example.org".as_ptr()) },
        NF_ERR_INVALID_ARG
    );
    let fake = FakeHttp {
        calls: Mutex::new(Vec::new()),
    };
    let tr = nf_http_transport {
        user: (&fake as *const FakeHttp).cast_mut().cast(),
        send: Some(http_send),
    };
    let tk = nf_token_source {
        user: null_mut(),
        token: Some(tokens),
    };
    let mut client: *mut nf_api_client = null_mut();
    assert_eq!(
        unsafe {
            nf_api_client_new(
                c"https://api.example.org/".as_ptr(),
                &tr,
                &tk,
                5.0,
                3,
                c"nf-test/1".as_ptr(),
                &mut client,
            )
        },
        NF_OK,
        "{}",
        last_error()
    );
    let q = [nf_header {
        name: c"limit".as_ptr(),
        value: c"10 & more".as_ptr(),
    }];
    let mut resp: *mut nf_http_response = null_mut();
    assert_eq!(
        unsafe {
            nf_api_client_request(
                client,
                c"GET".as_ptr(),
                c"/v1/recordings".as_ptr(),
                q.as_ptr(),
                1,
                null(),
                0,
                null(),
                0,
                &mut resp,
            )
        },
        NF_OK,
        "{}",
        last_error()
    );
    assert_eq!(unsafe { nf_http_response_status(resp) }, 200);
    let mut len = 0usize;
    let body = unsafe { std::slice::from_raw_parts(nf_http_response_body(resp, &mut len), len) };
    assert_eq!(body, br#"{"ok":true}"#);
    assert_eq!(unsafe { nf_http_response_header_count(resp) }, 1);
    let (mut n, mut v) = (null(), null());
    assert_eq!(
        unsafe { nf_http_response_header(resp, 0, &mut n, &mut v) },
        NF_OK
    );
    assert_eq!(
        unsafe { CStr::from_ptr(v) }.to_str().unwrap(),
        "application/json"
    );
    unsafe { nf_http_response_free(resp) };
    {
        let calls = fake.calls.lock().unwrap();
        assert_eq!(
            calls.len(),
            2,
            "401 with the stale token, then the refreshed one"
        );
        assert_eq!(
            calls[1].1,
            "https://api.example.org/v1/recordings?limit=10%20%26%20more"
        );
        assert!(
            calls[1]
                .2
                .contains(&("user-agent".into(), "nf-test/1".into()))
        );
    }
    assert_eq!(
        unsafe {
            nf_api_client_request(
                client,
                c"GET".as_ptr(),
                c"/v1/missing".as_ptr(),
                null(),
                0,
                null(),
                0,
                null(),
                0,
                &mut resp,
            )
        },
        NF_ERR_HTTP
    );
    // SAFETY: thread-local C string
    let detail = unsafe { CStr::from_ptr(nf_last_error_detail()) }
        .to_str()
        .unwrap()
        .to_owned();
    assert!(detail.contains("no such recording"), "{detail}");
    assert!(last_error().contains("404"), "{}", last_error());
    assert_eq!(
        unsafe {
            nf_api_client_request(
                client,
                c"POST".as_ptr(),
                c"/down".as_ptr(),
                null(),
                0,
                null(),
                0,
                b"{}".as_ptr(),
                2,
                &mut resp,
            )
        },
        NF_ERR_TRANSPORT
    );
    assert!(last_error().contains("connection refused"));

    // CABI-M1 case 12: the fixed 64 MiB response cap admits 2 MiB...
    let get = |path: &std::ffi::CStr, resp: &mut *mut nf_http_response| unsafe {
        nf_api_client_request(
            client,
            c"GET".as_ptr(),
            path.as_ptr(),
            null(),
            0,
            null(),
            0,
            null(),
            0,
            resp,
        )
    };
    let mut errors: Vec<String> = vec![detail.clone()];
    assert_eq!(get(c"/v1/big", &mut resp), NF_OK, "{}", last_error());
    unsafe { nf_http_response_free(resp) };
    // ...but one byte over the cap fails the request even though the callback returned 0, and the
    // refusal is sticky: a small body set afterwards is refused too (nothing oversize is copied)
    resp = null_mut();
    HUGE_STATUSES.lock().unwrap().clear();
    let before = fake.calls.lock().unwrap().len();
    assert_eq!(get(c"/v1/huge", &mut resp), NF_ERR_TRANSPORT);
    // over-cap is deterministic: nf-core does not retry it. The server sees the stale-token 401
    // round, then exactly 1 authorised request (a retry would add more)
    assert_eq!(authorised_calls(&fake, before), 1);
    assert!(resp.is_null());
    assert!(
        last_error().contains("NF_MAX_RESPONSE_BYTES"),
        "{}",
        last_error()
    );
    assert!(
        last_error().contains("response too large"),
        "{}",
        last_error()
    );
    assert_eq!(
        *HUGE_STATUSES.lock().unwrap(),
        vec![NF_ERR_INVALID_ARG, NF_ERR_INVALID_ARG]
    );
    errors.push(last_error());
    // body then headers: the shared cap holds in that order too (the body at exactly the cap is
    // accepted, the late header is refused, and the request fails)
    HUGE_STATUSES.lock().unwrap().clear();
    let before = fake.calls.lock().unwrap().len();
    assert_eq!(get(c"/v1/fill", &mut resp), NF_ERR_TRANSPORT);
    assert!(resp.is_null());
    assert_eq!(authorised_calls(&fake, before), 1);
    assert_eq!(
        *HUGE_STATUSES.lock().unwrap(),
        vec![NF_OK, NF_ERR_INVALID_ARG]
    );
    errors.push(last_error());
    // too many response headers fail the request too
    assert_eq!(get(c"/v1/headers", &mut resp), NF_ERR_TRANSPORT);
    assert!(resp.is_null());
    errors.push(last_error());
    unsafe { nf_api_client_free(client) };

    // CABI-M1 case 11: no error text ever carries a token
    let mut missing = null_mut();
    let fake2 = FakeHttp {
        calls: Mutex::new(Vec::new()),
    };
    let tr2 = nf_http_transport {
        user: (&fake2 as *const FakeHttp).cast_mut().cast(),
        send: Some(http_send),
    };
    let mut c2: *mut nf_api_client = null_mut();
    assert_eq!(
        unsafe {
            nf_api_client_new(
                c"https://api.example.org".as_ptr(),
                &tr2,
                &tk,
                5.0,
                1,
                null(),
                &mut c2,
            )
        },
        NF_OK
    );
    for path in [c"/v1/missing", c"/down"] {
        let s = unsafe {
            nf_api_client_request(
                c2,
                c"POST".as_ptr(),
                path.as_ptr(),
                null(),
                0,
                null(),
                0,
                null(),
                0,
                &mut missing,
            )
        };
        assert_ne!(s, NF_OK);
        errors.push(last_error());
        // SAFETY: thread-local C string
        errors.push(
            unsafe { CStr::from_ptr(nf_last_error_detail()) }
                .to_str()
                .unwrap()
                .to_owned(),
        );
    }
    unsafe { nf_api_client_free(c2) };
    for e in &errors {
        assert!(
            !e.contains("SECRET") && !e.contains("Bearer"),
            "token leaked into an error: {e}"
        );
    }
}

/// A token source that answers with more than NF_MAX_REPLY_BYTES.
unsafe extern "C" fn huge_token(_user: *mut c_void, _refresh: bool, r: *mut nf_reply) -> i32 {
    let t = vec![b't'; (1 << 20) + 1];
    let s = unsafe { nf_reply_set(r, t.as_ptr(), t.len()) };
    assert_eq!(s, NF_ERR_INVALID_ARG);
    0
}

/// An ingest server whose GetStreamState answer is larger than NF_MAX_REPLY_BYTES.
unsafe extern "C" fn huge_state(
    _user: *mut c_void,
    _req: *const u8,
    _len: usize,
    _auth: *const c_char,
    _timeout: f64,
    r: *mut nf_reply,
) -> i32 {
    let big = vec![0u8; (1 << 20) + 1];
    unsafe { nf_reply_set(r, big.as_ptr(), big.len()) };
    0
}

#[test]
fn oversized_callback_replies_fail_the_call() {
    // token reply too large: the request fails as an auth error, nothing is sent
    let fake = FakeHttp {
        calls: Mutex::new(Vec::new()),
    };
    let tr = nf_http_transport {
        user: (&fake as *const FakeHttp).cast_mut().cast(),
        send: Some(http_send),
    };
    let tk = nf_token_source {
        user: null_mut(),
        token: Some(huge_token),
    };
    let mut client: *mut nf_api_client = null_mut();
    assert_eq!(
        unsafe {
            nf_api_client_new(
                c"https://api.example.org".as_ptr(),
                &tr,
                &tk,
                5.0,
                1,
                null(),
                &mut client,
            )
        },
        NF_OK
    );
    let mut resp: *mut nf_http_response = null_mut();
    assert_eq!(
        unsafe {
            nf_api_client_request(
                client,
                c"GET".as_ptr(),
                c"/v1/x".as_ptr(),
                null(),
                0,
                null(),
                0,
                null(),
                0,
                &mut resp,
            )
        },
        NF_ERR_AUTH
    );
    assert!(fake.calls.lock().unwrap().is_empty());
    unsafe { nf_api_client_free(client) };

    // ingest reply too large: the state call fails as a transport error
    let dir = temp_dir("bigreply");
    let (dir_c, s) = (path_c(&dir), c("s-big"));
    let mut wal: *mut nf_wal = null_mut();
    assert_eq!(
        unsafe { nf_wal_open_ephemeral(dir_c.as_ptr(), s.as_ptr(), false, &mut wal) },
        NF_OK
    );
    let mut key: *mut nf_device_key = null_mut();
    assert_eq!(unsafe { nf_device_key_generate(&mut key) }, NF_OK);
    let mut sender: *mut nf_sender = null_mut();
    assert_eq!(
        unsafe {
            nf_sender_new(
                c"t".as_ptr(),
                c"d".as_ptr(),
                s.as_ptr(),
                key,
                wal,
                null(),
                &mut sender,
            )
        },
        NF_OK
    );
    let t = nf_ingest_transport {
        user: null_mut(),
        get_stream_state: Some(huge_state),
        stream_chunks: None,
        finish_stream: Some(huge_state),
    };
    let mut state = nf_stream_state {
        stream_id: empty(),
        next_seq: 0,
        n_samples: 0,
        state: empty(),
        suspect: false,
    };
    assert_eq!(
        unsafe { nf_sender_state(sender, &t, &mut state) },
        NF_ERR_TRANSPORT
    );
    assert!(
        last_error().contains("NF_MAX_REPLY_BYTES"),
        "{}",
        last_error()
    );
    assert!(
        !last_error().contains("nfd1."),
        "device token leaked: {}",
        last_error()
    );
    unsafe {
        nf_stream_state_free(&mut state);
        nf_sender_free(sender);
        nf_device_key_free(key);
        nf_wal_free(wal);
    }
    let _ = std::fs::remove_dir_all(&dir);
}

// ---------------------------------------------------------------- hardening (CABI-L1, CABI-L2)
/// A pointer into `buf` that is NOT aligned for `T`.
fn misaligned<T>(buf: &mut [u8]) -> *mut T {
    let base = buf.as_mut_ptr() as usize;
    let off = (0..std::mem::align_of::<T>())
        .find(|o| !(base + o).is_multiple_of(std::mem::align_of::<T>()))
        .expect("a misaligned offset");
    buf[off..].as_mut_ptr().cast::<T>()
}

#[test]
fn misaligned_and_oversized_pointers_are_errors() {
    let mut raw = vec![0u8; 64];
    // typed input slice (f64) at an odd address
    let ts: *const f64 = misaligned::<f64>(&mut raw);
    assert_eq!(
        status_of(|o| unsafe { nf_timing_sha256(ts, 2, null(), 0, null(), 0, o) }),
        NF_ERR_INVALID_ARG
    );
    assert!(last_error().contains("aligned"), "{}", last_error());
    // a length whose byte size overflows isize is refused before any read
    let ok = [0f64; 2];
    assert_eq!(
        status_of(|o| unsafe {
            nf_timing_sha256(ok.as_ptr(), usize::MAX / 4, null(), 0, null(), 0, o)
        }),
        NF_ERR_INVALID_ARG
    );
    assert!(last_error().contains("too large"), "{}", last_error());
    // pair arrays: 2 * n doubles overflowing
    assert_eq!(
        status_of(|o| unsafe {
            nf_timing_sha256(ok.as_ptr(), 2, ok.as_ptr(), usize::MAX, null(), 0, o)
        }),
        NF_ERR_INVALID_ARG
    );
    // misaligned output pointer
    let mut raw2 = vec![0u8; 16];
    let dt: *mut nf_dtype = misaligned::<nf_dtype>(&mut raw2);
    assert_eq!(
        unsafe { nf_dtype_parse(c"int16".as_ptr(), dt) },
        NF_ERR_INVALID_ARG
    );
    // misaligned handle
    let mut raw3 = vec![0u8; 64];
    let w: *const nf_wal = misaligned::<u64>(&mut raw3).cast();
    let mut n = 0usize;
    assert_eq!(unsafe { nf_wal_len(w, &mut n) }, NF_ERR_INVALID_ARG);
    // void frees ignore a misaligned pointer instead of dereferencing it
    let mut raw4 = vec![0u8; 64];
    unsafe {
        nf_buf_free(misaligned::<u64>(&mut raw4).cast());
        nf_stream_state_free(misaligned::<u64>(&mut raw4).cast());
    }
    // a misaligned caller buffer for f64 output is refused, not written
    let root = temp_dir("align");
    fixture::write(&root);
    let (s, rec) = open_rec(&root);
    assert_eq!(s, NF_OK);
    let mut raw5 = vec![0u8; 256];
    let out: *mut f64 = misaligned::<f64>(&mut raw5);
    assert_eq!(
        unsafe { nf_recording_read_f64(rec, 0, 2, out, 6, &mut n) },
        NF_ERR_INVALID_ARG
    );
    unsafe { nf_recording_free(rec) };
    let _ = std::fs::remove_dir_all(&root);
}

fn patch_json(path: &std::path::Path, f: impl FnOnce(&mut serde_json::Value)) {
    let mut v: serde_json::Value = serde_json::from_slice(&std::fs::read(path).unwrap()).unwrap();
    f(&mut v);
    std::fs::write(path, serde_json::to_vec(&v).unwrap()).unwrap();
}

#[test]
fn hostile_recording_metadata_is_bounded() {
    // (a) a huge sample count: reads beyond the per-call cap fail before allocating
    let root = temp_dir("huge");
    fixture::write(&root);
    let rec_dir = root.join(fixture::RECORDING_ID);
    let n = 2_000_000_000u64;
    patch_json(&rec_dir.join("zarr.json"), |g| {
        let s = &mut g["attributes"]["nf_signal"];
        s["n_samples"] = serde_json::json!(n);
        s["has_timestamps"] = serde_json::json!(false);
    });
    patch_json(&rec_dir.join("data/0/zarr.json"), |a| {
        a["shape"] = serde_json::json!([n, 3]);
    });
    let (s, rec) = open_rec(&root);
    assert_eq!(s, NF_OK, "{}", last_error());
    let mut need = 0usize;
    assert_eq!(
        unsafe { nf_recording_read(rec, 0, u64::MAX, null_mut(), 0, &mut need) },
        NF_ERR_INVALID_ARG
    );
    assert!(last_error().contains("split"), "{}", last_error());
    assert_eq!(
        unsafe { nf_recording_read_f64(rec, 0, u64::MAX, null_mut(), 0, &mut need) },
        NF_ERR_INVALID_ARG
    );
    // a small read of the same file still works
    let mut buf = [0u8; 12];
    assert_eq!(
        unsafe { nf_recording_read(rec, 0, 2, buf.as_mut_ptr(), 12, &mut need) },
        NF_OK
    );
    unsafe { nf_recording_free(rec) };
    let _ = std::fs::remove_dir_all(&root);

    // (b) more channels than the open-time limit is refused as corrupt
    let root = temp_dir("wide");
    fixture::write(&root);
    let rec_dir = root.join(fixture::RECORDING_ID);
    let ch = 70_000usize;
    patch_json(&rec_dir.join("zarr.json"), |g| {
        let s = &mut g["attributes"]["nf_signal"];
        s["n_channels"] = serde_json::json!(ch);
        s["ch_names"] = serde_json::json!((0..ch).map(|i| format!("c{i}")).collect::<Vec<_>>());
        s["units"] = serde_json::json!(vec!["uV"; ch]);
        // default scale/offset, so only the channel cap can refuse the file
        s.as_object_mut().unwrap().remove("scale");
        s.as_object_mut().unwrap().remove("offset");
    });
    patch_json(&rec_dir.join("data/0/zarr.json"), |a| {
        a["shape"] = serde_json::json!([fixture::N_SAMPLES, ch]);
    });
    let (s, rec) = open_rec(&root);
    assert_eq!(s, NF_ERR_CORRUPT, "{}", last_error());
    assert!(rec.is_null());
    assert!(last_error().contains("channel limit"), "{}", last_error());
    let _ = std::fs::remove_dir_all(&root);
}

// ---------------------------------------------------------------- CABI-T1: no stale last error
/// Text of the nested failure, captured inside the callback.
static NESTED_TEXT: Mutex<String> = Mutex::new(String::new());

/// HTTP transport whose LAST library call during the request fails on purpose.
unsafe extern "C" fn http_last_call_fails(
    _user: *mut c_void,
    _req: *const nf_http_request,
    r: *mut nf_http_reply,
) -> i32 {
    let mut b = empty();
    unsafe {
        nf_http_reply_set_status(r, 200);
        nf_http_reply_set_body(r, b"{}".as_ptr(), 2);
        nf_canonicalize(b"{".as_ptr(), 1, &mut b); // fails: sets this thread's last error
    }
    *NESTED_TEXT.lock().unwrap() = last_error();
    0
}

/// Token source returning a recognisable token.
unsafe extern "C" fn secret_token(_user: *mut c_void, _refresh: bool, r: *mut nf_reply) -> i32 {
    let t = b"tok-SECRET-t1";
    unsafe { nf_reply_set(r, t.as_ptr(), t.len()) };
    0
}

#[test]
fn nested_failure_leaves_no_stale_error_after_ok() {
    let tr = nf_http_transport {
        user: null_mut(),
        send: Some(http_last_call_fails),
    };
    let tk = nf_token_source {
        user: null_mut(),
        token: Some(secret_token),
    };
    let mut client: *mut nf_api_client = null_mut();
    assert_eq!(
        unsafe {
            nf_api_client_new(
                c"https://api.example.org".as_ptr(),
                &tr,
                &tk,
                5.0,
                1,
                null(),
                &mut client,
            )
        },
        NF_OK
    );
    let mut resp: *mut nf_http_response = null_mut();
    assert_eq!(
        unsafe {
            nf_api_client_request(
                client,
                c"GET".as_ptr(),
                c"/x".as_ptr(),
                null(),
                0,
                null(),
                0,
                null(),
                0,
                &mut resp,
            )
        },
        NF_OK
    );
    // the nested call really failed, and its text carries no token
    let nested = NESTED_TEXT.lock().unwrap().clone();
    assert!(!nested.is_empty());
    assert!(
        !nested.contains("SECRET") && !nested.contains("Bearer"),
        "{nested}"
    );
    // nothing survives the outer NF_OK
    assert_eq!(last_error(), "");
    // SAFETY: thread-local C string
    assert_eq!(
        unsafe { CStr::from_ptr(nf_last_error_detail()) }.to_bytes(),
        b""
    );
    unsafe {
        nf_http_response_free(resp);
        nf_api_client_free(client);
    }
    // value-returning entry points clear it too
    assert_eq!(
        status_of(|o| unsafe { nf_canonicalize(b"{".as_ptr(), 1, o) }),
        NF_ERR_CANONICAL
    );
    assert!(!last_error().is_empty());
    assert!(unsafe {
        nf_is_valid_id(
            c"blob:sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
                .as_ptr(),
        )
    });
    assert_eq!(last_error(), "");
}

// ---------------------------------------------------------------- CABI-T2: finish never loses data
#[test]
fn finish_refuses_while_chunks_are_pending() {
    let dir = temp_dir("finish");
    let (dir_c, s) = (path_c(&dir), c("s-1"));
    let seed = [11u8; 32];
    let mut key: *mut nf_device_key = null_mut();
    assert_eq!(
        unsafe { nf_device_key_from_seed(seed.as_ptr(), 32, &mut key) },
        NF_OK
    );
    let mut pk = [0u8; 32];
    assert_eq!(
        unsafe { nf_device_key_public_key(key, pk.as_mut_ptr()) },
        NF_OK
    );
    let mut wal: *mut nf_wal = null_mut();
    assert_eq!(
        unsafe { nf_wal_open_ephemeral(dir_c.as_ptr(), s.as_ptr(), false, &mut wal) },
        NF_OK
    );
    let mut writer: *mut nf_stream_writer = null_mut();
    assert_eq!(
        unsafe {
            nf_stream_writer_new(s.as_ptr(), NF_DTYPE_FLOAT32, 2, 100, key, wal, &mut writer)
        },
        NF_OK
    );
    // k = 3 pending chunks
    let samples: Vec<u8> = (0..600).flat_map(|k| (k as f32).to_le_bytes()).collect();
    let ts: Vec<f64> = (0..300).map(|i| 10.0 + i as f64 / 1000.0).collect();
    assert_eq!(
        unsafe {
            nf_stream_writer_push(
                writer,
                samples.as_ptr(),
                samples.len(),
                ts.as_ptr(),
                ts.len(),
                null_mut(),
            )
        },
        NF_OK
    );
    let wal_len = || {
        let mut n = 0usize;
        assert_eq!(unsafe { nf_wal_len(wal, &mut n) }, NF_OK);
        n
    };
    assert_eq!(wal_len(), 3);
    let mut cfg = nf_sender_config {
        batch_max: 0,
        linger_s: 0.0,
        call_timeout_s: 0.0,
        backoff_min_s: 0.0,
        backoff_max_s: 0.0,
    };
    assert_eq!(unsafe { nf_sender_config_default(&mut cfg) }, NF_OK);
    cfg.linger_s = 0.01;
    let mut sender: *mut nf_sender = null_mut();
    assert_eq!(
        unsafe {
            nf_sender_new(
                c"t".as_ptr(),
                c"d".as_ptr(),
                s.as_ptr(),
                key,
                wal,
                &cfg,
                &mut sender,
            )
        },
        NF_OK
    );
    let server = FakeIngest::new(pk, 0);
    let tr = transport(&server);
    let mut state = nf_stream_state {
        stream_id: empty(),
        next_seq: 0,
        n_samples: 0,
        state: empty(),
        suspect: false,
    };
    let mut errors = Vec::new();

    // 1. pending chunks: refused, nothing sent, WAL untouched
    assert_eq!(
        unsafe { nf_sender_finish(sender, &tr, &mut state) },
        NF_ERR_INVALID_ARG
    );
    assert!(
        last_error().contains("WAL still holds 3 chunks"),
        "{}",
        last_error()
    );
    errors.push(last_error());
    assert_eq!(server.finish_calls.load(Ordering::SeqCst), 0);
    assert_eq!(server.chunk_calls.load(Ordering::SeqCst), 0);
    assert_eq!(wal_len(), 3);
    assert!(state.state.data.is_null(), "no output on failure");

    // 2. while nf_sender_run is active: finish is refused (and a second run too)
    let (sp, tp) = (
        SendPtr(sender.cast_const()),
        SendPtr(&tr as *const nf_ingest_transport),
    );
    std::thread::scope(|scope| {
        let h = scope.spawn(move || {
            let (sp, tp) = (sp, tp);
            unsafe { nf_sender_run(sp.0, tp.0) }
        });
        // wait until run has drained the WAL (it keeps running afterwards)
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(20);
        while wal_len() > 0 {
            assert!(std::time::Instant::now() < deadline, "run did not drain");
            std::thread::sleep(std::time::Duration::from_millis(5));
        }
        assert_eq!(
            unsafe { nf_sender_finish(sender, &tr, &mut state) },
            NF_ERR_INVALID_ARG
        );
        assert!(last_error().contains("already active"), "{}", last_error());
        errors.push(last_error());
        assert_eq!(unsafe { nf_sender_run(sender, &tr) }, NF_ERR_INVALID_ARG);
        assert_eq!(server.finish_calls.load(Ordering::SeqCst), 0);
        assert_eq!(unsafe { nf_sender_stop(sender) }, NF_OK);
        assert_eq!(h.join().unwrap(), NF_OK);
    });

    // 3. drained: finish closes the stream with everything acked
    assert_eq!(wal_len(), 0);
    assert_eq!(
        unsafe { nf_sender_finish(sender, &tr, &mut state) },
        NF_OK,
        "{}",
        last_error()
    );
    assert_eq!(state.next_seq, 3);
    assert_eq!(server.finish_calls.load(Ordering::SeqCst), 1);
    unsafe { nf_stream_state_free(&mut state) };

    // 4. a writer racing the finish: the stream closes, but the loss is reported, not silent
    *server.late_writer.lock().unwrap() = Some(writer as usize);
    assert_eq!(
        unsafe { nf_sender_finish(sender, &tr, &mut state) },
        NF_ERR_INVALID_ARG
    );
    assert!(
        last_error().contains("1 chunks were written after finish started"),
        "{}",
        last_error()
    );
    errors.push(last_error());
    assert_eq!(server.finish_calls.load(Ordering::SeqCst), 2);
    assert_eq!(wal_len(), 1);

    // none of the new messages carries a token
    for e in &errors {
        assert!(
            !e.contains("nfd1.") && !e.contains("NFDevice"),
            "token in error: {e}"
        );
    }
    unsafe {
        nf_stream_state_free(&mut state);
        nf_sender_free(sender);
        nf_stream_writer_free(writer);
        nf_wal_free(wal);
        nf_device_key_free(key);
    }
    let _ = std::fs::remove_dir_all(&dir);
}
