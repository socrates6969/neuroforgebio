//! The offline provenance recorder: a local hash chain of PROV batches, synced to the platform
//! later (hashing.md sec. 5.3). Thread-safe: the handle locks internally.

use std::ffi::c_char;
use std::sync::Mutex;

use nf_core::cjson;
use nf_core::model::ProvRecord;
use nf_core::prov::{ProvError, ProvRecorder};

use crate::{
    Error, NF_ERR_INVALID_ARG, NF_ERR_NOT_FOUND, NF_ERR_VERIFY, cstr, free_handle, guard, handle,
    into_handle, nf_buf, nf_status, out, put_buf, text,
};

/// A local provenance chain. Opaque; free with `nf_prov_recorder_free`.
pub struct nf_prov_recorder(Mutex<ProvRecorder>);

fn prov_err(e: ProvError) -> Error {
    match e {
        ProvError::Io(io) => io.into(),
        ProvError::Canon(c) => Error::new(NF_ERR_VERIFY, format!("provenance chain: {c}")),
        ProvError::Invalid(m) => Error::new(NF_ERR_INVALID_ARG, format!("provenance: {m}")),
        ProvError::Sync(m) => Error::new(NF_ERR_INVALID_ARG, format!("provenance sync: {m}")),
    }
}

fn lock(r: &nf_prov_recorder) -> std::sync::MutexGuard<'_, ProvRecorder> {
    // a panic while holding the lock cannot leave the chain half-written (appends are atomic
    // file writes), so a poisoned lock is still usable
    r.0.lock()
        .unwrap_or_else(std::sync::PoisonError::into_inner)
}

/// Open (or create) chain `chain` in directory `dir` and verify it. A chain that does not verify
/// is `NF_ERR_VERIFY`.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_prov_recorder_open(
    dir: *const c_char,
    chain: *const c_char,
    out_recorder: *mut *mut nf_prov_recorder,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (d, c, o) = unsafe {
            (
                cstr(dir, "dir")?,
                cstr(chain, "chain")?,
                out(out_recorder, "out_recorder")?,
            )
        };
        let r = ProvRecorder::open(d, c).map_err(prov_err)?;
        *o = into_handle(nf_prov_recorder(Mutex::new(r)));
        Ok(())
    })
}

/// Free a recorder (NULL is a no-op). The chain stays on disk.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_prov_recorder_free(recorder: *mut nf_prov_recorder) {
    // SAFETY: header contract.
    unsafe { free_handle(recorder) }
}

/// Append one batch. `records_json` is a JSON array of PROV records
/// (`{"type":"entity"|"activity"|"agent","id","label"[,"content"]}` or
/// `{"type":"edge","rel","from","to"}`). `out_seq` (may be NULL) receives the batch sequence
/// number and `out_id` (may be NULL) its `provb:` ID.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_prov_recorder_record(
    recorder: *const nf_prov_recorder,
    records_json: *const u8,
    records_len: usize,
    out_seq: *mut u64,
    out_id: *mut nf_buf,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (r, t) = unsafe {
            (
                handle(recorder, "recorder")?,
                text(records_json, records_len, "records_json")?,
            )
        };
        let recs: Vec<ProvRecord> = serde_json::from_str(t)
            .map_err(|e| Error::new(NF_ERR_INVALID_ARG, format!("records_json: {e}")))?;
        let b = lock(r).record(&recs).map_err(prov_err)?;
        // SAFETY: NULL or writable.
        unsafe {
            if let Some(s) = crate::opt_out(out_seq, "out_seq")? {
                *s = b.seq;
            }
            if let Some(o) = crate::opt_out(out_id, "out_id")? {
                put_buf(o, b.id);
            }
        }
        Ok(())
    })
}

/// Number of batches in the chain.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_prov_recorder_len(
    recorder: *const nf_prov_recorder,
    out_len: *mut usize,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (r, o) = unsafe { (handle(recorder, "recorder")?, out(out_len, "out_len")?) };
        *o = lock(r).len();
        Ok(())
    })
}

/// Sequence number and ID of the newest batch; `NF_ERR_NOT_FOUND` for an empty chain.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_prov_recorder_head(
    recorder: *const nf_prov_recorder,
    out_seq: *mut u64,
    out_id: *mut nf_buf,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (r, s, o) = unsafe {
            (
                handle(recorder, "recorder")?,
                out(out_seq, "out_seq")?,
                out(out_id, "out_id")?,
            )
        };
        let g = lock(r);
        let b = g
            .head()
            .ok_or_else(|| Error::new(NF_ERR_NOT_FOUND, "the chain is empty"))?;
        *s = b.seq;
        put_buf(o, b.id.clone());
        Ok(())
    })
}

/// Number of batches not yet marked synced.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_prov_recorder_pending_count(
    recorder: *const nf_prov_recorder,
    out_count: *mut usize,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (r, o) = unsafe { (handle(recorder, "recorder")?, out(out_count, "out_count")?) };
        *o = lock(r).pending().len();
        Ok(())
    })
}

/// Pending batch `index` (0 = oldest unsynced): sequence number, ID, and the canonical batch
/// bytes to upload (`out_canonical` may be NULL).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_prov_recorder_pending(
    recorder: *const nf_prov_recorder,
    index: usize,
    out_seq: *mut u64,
    out_id: *mut nf_buf,
    out_canonical: *mut nf_buf,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (r, s, o) = unsafe {
            (
                handle(recorder, "recorder")?,
                out(out_seq, "out_seq")?,
                out(out_id, "out_id")?,
            )
        };
        let g = lock(r);
        let b = g
            .pending()
            .get(index)
            .ok_or_else(|| Error::new(NF_ERR_NOT_FOUND, format!("no pending batch {index}")))?;
        let canonical = cjson::to_canonical(&b.value)?;
        *s = b.seq;
        put_buf(o, b.id.clone());
        // SAFETY: NULL or writable.
        if let Some(c) = unsafe { crate::opt_out(out_canonical, "out_canonical") }? {
            put_buf(c, canonical);
        }
        Ok(())
    })
}

/// Mark every batch up to and including `seq` as synced (persisted).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_prov_recorder_mark_synced(
    recorder: *const nf_prov_recorder,
    seq: u64,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let r = unsafe { handle(recorder, "recorder")? };
        lock(r).mark_synced(seq).map_err(prov_err)
    })
}
