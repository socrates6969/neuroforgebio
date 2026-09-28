//! Caller-misuse robustness, the parts that need threads or crafted files (the NULL-per-argument
//! table, lengths and callback reentrancy are in `tests/c/test_misuse.c`, built with MSVC):
//! - the 2^30-byte per-read cap at its exact boundary (size queries only, nothing allocated);
//! - handles stay valid after the handles they were built from are freed;
//! - the last error is per thread;
//! - documented thread-safe handles used from several threads at once;
//! - `nf_sender_stop` / `nf_sender_get_stats` from a second thread while `nf_sender_run` blocks.
//!
//! Misuse the header declares undefined (foreign handle types, use after free, double free of a
//! handle, freeing a handle another thread uses) is listed in `bindings/c/README.md` and is not
//! executed.

mod common;
mod fixture;

use std::ffi::{CStr, c_char, c_void};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU32, Ordering};

use common::*;
use neuroforge::hashing::*;
use neuroforge::local::*;
use neuroforge::provenance::*;
use neuroforge::streaming::*;
use neuroforge::*;

fn temp_dir(name: &str) -> PathBuf {
    static N: AtomicU32 = AtomicU32::new(0);
    let d = std::env::temp_dir().join(format!(
        "nf-misuse-{}-{}-{name}",
        std::process::id(),
        N.fetch_add(1, Ordering::SeqCst)
    ));
    let _ = std::fs::remove_dir_all(&d);
    std::fs::create_dir_all(&d).unwrap();
    d
}

fn path_c(p: &Path) -> std::ffi::CString {
    c(p.to_str().unwrap())
}

fn null<T>() -> *const T {
    std::ptr::null()
}

fn null_mut<T>() -> *mut T {
    std::ptr::null_mut()
}

fn patch_json(path: &Path, f: impl FnOnce(&mut serde_json::Value)) {
    let mut v: serde_json::Value = serde_json::from_slice(&std::fs::read(path).unwrap()).unwrap();
    f(&mut v);
    std::fs::write(path, serde_json::to_vec(&v).unwrap()).unwrap();
}

fn open_rec(root: &Path) -> *mut nf_recording {
    let (root_c, id) = (path_c(root), c(fixture::RECORDING_ID));
    let mut rec: *mut nf_recording = null_mut();
    let s = unsafe { nf_recording_open(root_c.as_ptr(), id.as_ptr(), &mut rec) };
    assert_eq!(s, NF_OK, "{}", last_error());
    rec
}

// ---------------------------------------------------------------- 2^30 read cap boundary
#[test]
fn read_cap_boundary_is_exact() {
    const CAP: usize = 1 << 30;
    let root = temp_dir("cap");
    fixture::write(&root);
    let dir = root.join(fixture::RECORDING_ID);
    let n: u64 = 200_000_000;
    patch_json(&dir.join("zarr.json"), |g| {
        g["attributes"]["nf_signal"]["n_samples"] = serde_json::json!(n);
    });
    patch_json(&dir.join("data/0/zarr.json"), |a| {
        a["shape"] = serde_json::json!([n, 3]);
    });
    patch_json(&dir.join("timestamps/zarr.json"), |a| {
        a["shape"] = serde_json::json!([n]);
    });
    let rec = open_rec(&root);
    let row = 3 * 2; // 3 channels of int16
    let ok_rows = (CAP / row) as u64; // largest row count within the cap
    let mut need = 0usize;
    // at the cap: a size query answers BUFFER_TOO_SMALL with the exact size (nothing is read)
    assert_eq!(
        unsafe { nf_recording_read(rec, 0, ok_rows, null_mut(), 0, &mut need) },
        NF_ERR_BUFFER_TOO_SMALL
    );
    assert_eq!(need, ok_rows as usize * row);
    assert!(need <= CAP);
    // one row more crosses 2^30 stored bytes: refused before any allocation
    assert_eq!(
        unsafe { nf_recording_read(rec, 0, ok_rows + 1, null_mut(), 0, &mut need) },
        NF_ERR_INVALID_ARG
    );
    assert!(last_error().contains("split"), "{}", last_error());
    // the f64 read counts stored bytes too, not the doubles it returns
    assert_eq!(
        unsafe { nf_recording_read_f64(rec, 0, ok_rows, null_mut(), 0, &mut need) },
        NF_ERR_BUFFER_TOO_SMALL
    );
    assert_eq!(need, ok_rows as usize * 3);
    assert_eq!(
        unsafe { nf_recording_read_f64(rec, 0, ok_rows + 1, null_mut(), 0, &mut need) },
        NF_ERR_INVALID_ARG
    );
    // timestamps: 8 stored bytes per row, so exactly 2^27 rows is 2^30 bytes (allowed)
    let ts_rows = (CAP / 8) as u64;
    assert_eq!(
        unsafe { nf_recording_read_timestamps(rec, 0, ts_rows, null_mut(), 0, &mut need) },
        NF_ERR_BUFFER_TOO_SMALL
    );
    assert_eq!(need, ts_rows as usize);
    assert_eq!(
        unsafe { nf_recording_read_timestamps(rec, 0, ts_rows + 1, null_mut(), 0, &mut need) },
        NF_ERR_INVALID_ARG
    );
    // the cap is per call: the same range split in two is fine
    assert_eq!(
        unsafe { nf_recording_read(rec, ok_rows, ok_rows + 1, null_mut(), 0, &mut need) },
        NF_ERR_BUFFER_TOO_SMALL
    );
    assert_eq!(need, row);
    unsafe { nf_recording_free(rec) };
    let _ = std::fs::remove_dir_all(&root);
}

// ---------------------------------------------------------------- lifetimes and threads
#[test]
fn dependents_outlive_their_source_handles() {
    let dir = temp_dir("lifetime");
    let dir_c = path_c(&dir);
    let mut key: *mut nf_device_key = null_mut();
    assert_eq!(unsafe { nf_device_key_generate(&mut key) }, NF_OK);
    let mut wal: *mut nf_wal = null_mut();
    assert_eq!(
        unsafe { nf_wal_open_ephemeral(dir_c.as_ptr(), c"s".as_ptr(), false, &mut wal) },
        NF_OK
    );
    let mut w: *mut nf_stream_writer = null_mut();
    assert_eq!(
        unsafe { nf_stream_writer_new(c"s".as_ptr(), NF_DTYPE_FLOAT32, 1, 2, key, wal, &mut w) },
        NF_OK
    );
    let mut s: *mut nf_sender = null_mut();
    assert_eq!(
        unsafe {
            nf_sender_new(
                c"t".as_ptr(),
                c"d".as_ptr(),
                c"s".as_ptr(),
                key,
                wal,
                null(),
                &mut s,
            )
        },
        NF_OK
    );
    // free the key and WAL handles first: writer and sender keep their own references
    unsafe {
        nf_device_key_free(key);
        nf_wal_free(wal);
    }
    let samples: Vec<u8> = [1.0f32, 2.0, 3.0]
        .iter()
        .flat_map(|v| v.to_le_bytes())
        .collect();
    let ts = [1.0, 1.001, 1.002];
    let mut chunks = 0usize;
    assert_eq!(
        unsafe { nf_stream_writer_push(w, samples.as_ptr(), 12, ts.as_ptr(), 3, &mut chunks) },
        NF_OK
    );
    assert_eq!(chunks, 1);
    let mut st = nf_sender_stats::default();
    assert_eq!(unsafe { nf_sender_get_stats(s, &mut st) }, NF_OK);
    unsafe {
        nf_stream_writer_free(w);
        nf_sender_free(s);
    }
    // a chunk outlives its cache handle
    let root = temp_dir("chunk");
    let id = fixture::write(&root);
    let cache_c = path_c(&root.join("cache"));
    let mut cache: *mut nf_chunk_cache = null_mut();
    assert_eq!(
        unsafe { nf_chunk_cache_open(cache_c.as_ptr(), 1 << 20, &mut cache) },
        NF_OK
    );
    let mut chunk: *mut nf_chunk = null_mut();
    let id_c = c(&id);
    assert_eq!(
        unsafe { nf_chunk_cache_get(cache, id_c.as_ptr(), &mut chunk) },
        NF_OK
    );
    unsafe { nf_chunk_cache_free(cache) };
    let mut len = 0usize;
    assert!(!unsafe { nf_chunk_data(chunk, &mut len) }.is_null());
    assert_eq!(len, 24);
    unsafe { nf_chunk_free(chunk) };
    let _ = std::fs::remove_dir_all(&dir);
    let _ = std::fs::remove_dir_all(&root);
}

#[test]
fn last_error_is_per_thread() {
    assert_eq!(
        status_of(|o| unsafe { nf_canonicalize(b"{".as_ptr(), 1, o) }),
        NF_ERR_CANONICAL
    );
    let here = last_error();
    assert!(!here.is_empty());
    let there = std::thread::spawn(|| {
        // a fresh thread starts with no error, and its failure does not touch ours
        let before = last_error();
        let _ = status_of(|o| unsafe { nf_blob_id(null(), 1, o) });
        (before, last_error())
    })
    .join()
    .unwrap();
    assert_eq!(there.0, "");
    assert!(there.1.contains("NULL"));
    assert_eq!(last_error(), here);
}

#[test]
fn shared_handles_under_concurrent_use() {
    // documented thread-safe: nf_recording, nf_chunk_cache, nf_prov_recorder, nf_stream_writer,
    // nf_device_key, pure functions
    let root = temp_dir("threads");
    fixture::write(&root);
    let rec = open_rec(&root) as usize;
    let prov_dir = path_c(&root.join("prov"));
    let mut pr: *mut nf_prov_recorder = null_mut();
    assert_eq!(
        unsafe { nf_prov_recorder_open(prov_dir.as_ptr(), c"c".as_ptr(), &mut pr) },
        NF_OK
    );
    let pr = pr as usize;
    let mut key: *mut nf_device_key = null_mut();
    assert_eq!(unsafe { nf_device_key_generate(&mut key) }, NF_OK);
    let key = key as usize;
    const THREADS: usize = 4;
    const ROUNDS: usize = 50;
    std::thread::scope(|scope| {
        for t in 0..THREADS {
            scope.spawn(move || {
                let rec = rec as *const nf_recording;
                let pr = pr as *const nf_prov_recorder;
                let key = key as *const nf_device_key;
                let mut buf = vec![0u8; 60];
                let recs = format!(r#"[{{"type":"agent","id":"urn:t{t}","label":"worker"}}]"#);
                for i in 0..ROUNDS {
                    let start = ((t * ROUNDS + i) % 990) as u64;
                    let mut n = 0usize;
                    let s = unsafe {
                        nf_recording_read(rec, start, start + 10, buf.as_mut_ptr(), 60, &mut n)
                    };
                    assert_eq!(s, NF_OK);
                    let v = i16::from_le_bytes([buf[0], buf[1]]);
                    assert_eq!(v, fixture::sample(start, 0));
                    let s = unsafe {
                        nf_prov_recorder_record(
                            pr,
                            recs.as_ptr(),
                            recs.len(),
                            null_mut(),
                            null_mut(),
                        )
                    };
                    assert_eq!(s, NF_OK, "{}", last_error());
                    let tok = text_out(|o| unsafe {
                        nf_device_key_token(key, c"t".as_ptr(), c"d".as_ptr(), c"s".as_ptr(), 60, o)
                    });
                    assert!(tok.starts_with("nfd1."));
                }
            });
        }
    });
    // every record landed exactly once and the chain still verifies on reopen
    let mut n = 0usize;
    assert_eq!(
        unsafe { nf_prov_recorder_len(pr as *const _, &mut n) },
        NF_OK
    );
    assert_eq!(n, THREADS * ROUNDS);
    unsafe { nf_prov_recorder_free(pr as *mut _) };
    let mut again: *mut nf_prov_recorder = null_mut();
    assert_eq!(
        unsafe { nf_prov_recorder_open(prov_dir.as_ptr(), c"c".as_ptr(), &mut again) },
        NF_OK,
        "{}",
        last_error()
    );
    unsafe {
        nf_prov_recorder_free(again);
        nf_recording_free(rec as *mut _);
        nf_device_key_free(key as *mut _);
    }
    let _ = std::fs::remove_dir_all(&root);
}

/// Ingest transport that is permanently unavailable (the sender keeps retrying until stopped).
unsafe extern "C" fn unavailable(
    _user: *mut c_void,
    _req: *const u8,
    _len: usize,
    _auth: *const c_char,
    _timeout: f64,
    r: *mut nf_reply,
) -> i32 {
    unsafe { nf_reply_set(r, b"down".as_ptr(), 4) };
    14
}

#[test]
fn sender_stop_and_stats_from_another_thread() {
    let dir = temp_dir("stop");
    let dir_c = path_c(&dir);
    let mut key: *mut nf_device_key = null_mut();
    assert_eq!(unsafe { nf_device_key_generate(&mut key) }, NF_OK);
    let mut wal: *mut nf_wal = null_mut();
    assert_eq!(
        unsafe { nf_wal_open_ephemeral(dir_c.as_ptr(), c"s".as_ptr(), false, &mut wal) },
        NF_OK
    );
    let mut cfg = nf_sender_config {
        batch_max: 0,
        linger_s: 0.0,
        call_timeout_s: 0.0,
        backoff_min_s: 0.0,
        backoff_max_s: 0.0,
    };
    assert_eq!(unsafe { nf_sender_config_default(&mut cfg) }, NF_OK);
    cfg.backoff_min_s = 0.001;
    cfg.backoff_max_s = 0.005;
    let mut s: *mut nf_sender = null_mut();
    assert_eq!(
        unsafe {
            nf_sender_new(
                c"t".as_ptr(),
                c"d".as_ptr(),
                c"s".as_ptr(),
                key,
                wal,
                &cfg,
                &mut s,
            )
        },
        NF_OK
    );
    let t = nf_ingest_transport {
        user: null_mut(),
        get_stream_state: Some(unavailable),
        stream_chunks: None,
        finish_stream: Some(unavailable),
    };
    let (sp, tp) = (s as usize, &t as *const nf_ingest_transport as usize);
    std::thread::scope(|scope| {
        let h = scope.spawn(move || unsafe {
            nf_sender_run(sp as *const nf_sender, tp as *const nf_ingest_transport)
        });
        // stats from this thread while run() blocks on the other
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(10);
        loop {
            let mut st = nf_sender_stats::default();
            assert_eq!(unsafe { nf_sender_get_stats(s, &mut st) }, NF_OK);
            if st.rpc_errors >= 3 {
                break;
            }
            assert!(
                std::time::Instant::now() < deadline,
                "sender made no attempts"
            );
            std::thread::sleep(std::time::Duration::from_millis(5));
        }
        assert_eq!(unsafe { nf_sender_stop(s) }, NF_OK);
        assert_eq!(h.join().unwrap(), NF_OK);
    });
    // UNAVAILABLE is not fatal
    let mut fatal = empty();
    assert_eq!(
        unsafe { nf_sender_fatal_error(s, &mut fatal) },
        NF_ERR_NOT_FOUND
    );
    // stop is idempotent, reset lets run start again (it returns at once when stopped again)
    assert_eq!(unsafe { nf_sender_stop(s) }, NF_OK);
    assert_eq!(unsafe { nf_sender_reset(s) }, NF_OK);
    assert_eq!(unsafe { nf_sender_stop(s) }, NF_OK);
    assert_eq!(unsafe { nf_sender_run(s, &t) }, NF_OK);
    unsafe {
        nf_sender_free(s);
        nf_wal_free(wal);
        nf_device_key_free(key);
    }
    let _ = std::fs::remove_dir_all(&dir);
}

#[test]
fn pure_functions_from_many_threads() {
    let want = text_out(|o| unsafe { nf_blob_id(b"abc".as_ptr(), 3, o) });
    std::thread::scope(|scope| {
        for _ in 0..8 {
            let want = want.clone();
            scope.spawn(move || {
                for _ in 0..200 {
                    let got = text_out(|o| unsafe { nf_blob_id(b"abc".as_ptr(), 3, o) });
                    assert_eq!(got, want);
                    let bad = status_of(|o| unsafe { nf_canonicalize(b"[1,".as_ptr(), 3, o) });
                    assert_eq!(bad, NF_ERR_CANONICAL);
                    assert!(!last_error().is_empty());
                }
            });
        }
    });
    // SAFETY: static string
    assert_eq!(
        unsafe { CStr::from_ptr(nf_status_name(NF_OK)) }.to_bytes(),
        b"NF_OK"
    );
}
