//! `neuroforge`: the stable C ABI over nf-core (ADR 0013, BLUEPRINT sec. 5). The header
//! `include/neuroforge.h` is generated from this crate by cbindgen and checked in.
//!
//! Conventions (the header repeats them for C readers):
//! - every fallible function returns [`nf_status`]; [`NF_OK`] is 0;
//! - on failure [`nf_last_error`] holds a UTF-8 message for the calling thread; every call
//!   clears it on entry and again on success, so the outer call's outcome always defines it
//!   (CABI-T1: a failing nested call inside a callback cannot leave stale text behind an
//!   `NF_OK`); read it only after a non-OK status;
//! - no panic crosses the boundary: each body runs in `catch_unwind` ([`NF_ERR_PANIC`]);
//! - short strings are NUL-terminated UTF-8, documents and data are `(ptr, len)`;
//! - variable-size results are [`nf_buf`]s released with [`nf_buf_free`], or caller buffers
//!   where stated;
//! - handles come from one constructor and go back through their `nf_*_free`, which accepts NULL.
//!
//! Direction: data flows device -> SDK -> platform only. Nothing here sends anything to
//! acquisition hardware (SEC-090/091; `tools/hw-guard` scans `bindings/`).

#![allow(non_camel_case_types)]
// The safety contract of every exported function is the pointer contract above and in the
// header; repeating it on ~100 functions adds nothing.
#![allow(clippy::missing_safety_doc)]

use std::cell::RefCell;
use std::ffi::{CStr, CString, c_char};
use std::panic::{AssertUnwindSafe, catch_unwind};

use nf_core::cjson::{self, CanonError, Value};
use nf_core::ids::Dtype;

pub mod api;
pub mod hashing;
pub mod local;
pub mod provenance;
pub mod streaming;

// ---------------------------------------------------------------- version
/// ABI major version: a change here breaks existing callers.
pub const NF_ABI_VERSION_MAJOR: u32 = 1;
/// ABI minor version: additions only.
pub const NF_ABI_VERSION_MINOR: u32 = 2;
/// ABI patch version: fixes without interface changes.
pub const NF_ABI_VERSION_PATCH: u32 = 1;

/// ABI version of the loaded library: `major << 16 | minor << 8 | patch`. A caller built against
/// this header is compatible when the majors are equal and the library minor is at least
/// `NF_ABI_VERSION_MINOR`.
#[unsafe(no_mangle)]
pub extern "C" fn nf_abi_version() -> u32 {
    (NF_ABI_VERSION_MAJOR << 16) | (NF_ABI_VERSION_MINOR << 8) | NF_ABI_VERSION_PATCH
}

static CORE_VERSION: std::sync::OnceLock<CString> = std::sync::OnceLock::new();

/// Version of nf-core inside this library (static string, never freed).
#[unsafe(no_mangle)]
pub extern "C" fn nf_core_version() -> *const c_char {
    CORE_VERSION
        .get_or_init(|| c_lossy(nf_core::VERSION.to_owned()))
        .as_ptr()
}

// ---------------------------------------------------------------- status codes
/// Result of every fallible call. Unknown non-zero values must be treated as errors (new codes
/// may be added in a minor version).
pub type nf_status = i32;

pub const NF_OK: nf_status = 0;
/// A required pointer argument was NULL.
pub const NF_ERR_NULL_ARG: nf_status = 1;
/// An argument is malformed: invalid UTF-8, unknown dtype, bad shape, out-of-range value.
pub const NF_ERR_INVALID_ARG: nf_status = 2;
/// A document cannot be canonicalised or breaks a hashing-spec rule (docs/spec/hashing.md).
pub const NF_ERR_CANONICAL: nf_status = 3;
/// A hash chain, signature or token did not verify.
pub const NF_ERR_VERIFY: nf_status = 4;
/// A filesystem operation failed.
pub const NF_ERR_IO: nf_status = 5;
/// The requested item does not exist (missing file, cache miss, empty chain).
pub const NF_ERR_NOT_FOUND: nf_status = 6;
/// A caller buffer is NULL or too small; the needed size was written to the size output.
pub const NF_ERR_BUFFER_TOO_SMALL: nf_status = 7;
/// Stored data is corrupt or does not authenticate (WAL record, Zarr metadata).
pub const NF_ERR_CORRUPT: nf_status = 8;
/// Not available on this platform or in this build (for example DPAPI outside Windows).
pub const NF_ERR_UNSUPPORTED: nf_status = 9;
/// A caller transport reported a failure, or an RPC failed.
pub const NF_ERR_TRANSPORT: nf_status = 10;
/// Authentication failed (token source error, or 401 after a refresh).
pub const NF_ERR_AUTH: nf_status = 11;
/// The API answered with a non-2xx status; `nf_last_error_detail()` holds the problem+json.
pub const NF_ERR_HTTP: nf_status = 12;
/// An internal error (a caught panic). Please report it.
pub const NF_ERR_PANIC: nf_status = 13;

/// Constant name of a status code (`"NF_OK"`, ...; `"NF_ERR_UNKNOWN"` otherwise). Static
/// string, never freed.
#[unsafe(no_mangle)]
pub extern "C" fn nf_status_name(status: nf_status) -> *const c_char {
    let s: &CStr = match status {
        NF_OK => c"NF_OK",
        NF_ERR_NULL_ARG => c"NF_ERR_NULL_ARG",
        NF_ERR_INVALID_ARG => c"NF_ERR_INVALID_ARG",
        NF_ERR_CANONICAL => c"NF_ERR_CANONICAL",
        NF_ERR_VERIFY => c"NF_ERR_VERIFY",
        NF_ERR_IO => c"NF_ERR_IO",
        NF_ERR_NOT_FOUND => c"NF_ERR_NOT_FOUND",
        NF_ERR_BUFFER_TOO_SMALL => c"NF_ERR_BUFFER_TOO_SMALL",
        NF_ERR_CORRUPT => c"NF_ERR_CORRUPT",
        NF_ERR_UNSUPPORTED => c"NF_ERR_UNSUPPORTED",
        NF_ERR_TRANSPORT => c"NF_ERR_TRANSPORT",
        NF_ERR_AUTH => c"NF_ERR_AUTH",
        NF_ERR_HTTP => c"NF_ERR_HTTP",
        NF_ERR_PANIC => c"NF_ERR_PANIC",
        _ => c"NF_ERR_UNKNOWN",
    };
    s.as_ptr()
}

// ---------------------------------------------------------------- last error (per thread)
thread_local! {
    static LAST_ERROR: RefCell<(CString, CString)> = RefCell::new((CString::default(), CString::default()));
}

/// Message of the last failed call on this thread, or `""`. Valid until the next `nf_` call on
/// this thread; copy it if you need it longer.
#[unsafe(no_mangle)]
pub extern "C" fn nf_last_error() -> *const c_char {
    LAST_ERROR.with(|e| e.borrow().0.as_ptr())
}

/// Extra detail of the last failed call on this thread, or `""`: the problem+json body for
/// `NF_ERR_HTTP`. Same lifetime as `nf_last_error()`.
#[unsafe(no_mangle)]
pub extern "C" fn nf_last_error_detail() -> *const c_char {
    LAST_ERROR.with(|e| e.borrow().1.as_ptr())
}

fn c_lossy(s: String) -> CString {
    CString::new(s.replace('\0', "\u{fffd}")).unwrap_or_default()
}

fn set_error(msg: String, detail: Option<String>) {
    LAST_ERROR.with(|e| {
        *e.borrow_mut() = (c_lossy(msg), c_lossy(detail.unwrap_or_default()));
    });
}

fn clear_error() {
    LAST_ERROR.with(|e| {
        let mut e = e.borrow_mut();
        if !e.0.is_empty() || !e.1.is_empty() {
            *e = (CString::default(), CString::default());
        }
    });
}

// ---------------------------------------------------------------- internal error + guard
/// An error on its way to C: status code, message, optional detail.
#[derive(Debug)]
pub(crate) struct Error {
    pub code: nf_status,
    pub msg: String,
    pub detail: Option<String>,
}

pub(crate) type Result<T> = std::result::Result<T, Error>;

impl Error {
    pub fn new(code: nf_status, msg: impl Into<String>) -> Self {
        Self {
            code,
            msg: msg.into(),
            detail: None,
        }
    }
    pub fn invalid(msg: impl Into<String>) -> Self {
        Self::new(NF_ERR_INVALID_ARG, msg)
    }
}

impl From<CanonError> for Error {
    fn from(e: CanonError) -> Self {
        Self::new(NF_ERR_CANONICAL, e.to_string())
    }
}

impl From<std::io::Error> for Error {
    fn from(e: std::io::Error) -> Self {
        let code = if e.kind() == std::io::ErrorKind::NotFound {
            NF_ERR_NOT_FOUND
        } else {
            NF_ERR_IO
        };
        Self::new(code, e.to_string())
    }
}

fn panic_message(p: &(dyn std::any::Any + Send)) -> String {
    let m = p
        .downcast_ref::<&str>()
        .map(|s| (*s).to_owned())
        .or_else(|| p.downcast_ref::<String>().cloned())
        .unwrap_or_else(|| "unknown panic".into());
    format!("internal error (panic): {m}")
}

/// Run an exported body: clear the thread's error, catch panics, map errors to a status. The
/// error is cleared again on success, because a callback inside the body may have run failing
/// nested calls (CABI-T1).
pub(crate) fn guard(f: impl FnOnce() -> Result<()>) -> nf_status {
    clear_error();
    match catch_unwind(AssertUnwindSafe(f)) {
        Ok(Ok(())) => {
            clear_error();
            NF_OK
        }
        Ok(Err(e)) => {
            set_error(e.msg, e.detail);
            e.code
        }
        Err(p) => {
            set_error(panic_message(p.as_ref()), None);
            NF_ERR_PANIC
        }
    }
}

/// Like [`guard`] for functions without a status: `fallback` on error or panic.
pub(crate) fn guard_value<T>(fallback: T, f: impl FnOnce() -> Result<T>) -> T {
    clear_error();
    match catch_unwind(AssertUnwindSafe(f)) {
        Ok(Ok(v)) => {
            clear_error();
            v
        }
        Ok(Err(e)) => {
            set_error(e.msg, e.detail);
            fallback
        }
        Err(p) => {
            set_error(panic_message(p.as_ref()), None);
            fallback
        }
    }
}

// ---------------------------------------------------------------- argument helpers
/// A NUL-terminated UTF-8 argument.
pub(crate) unsafe fn cstr<'a>(p: *const c_char, what: &str) -> Result<&'a str> {
    if p.is_null() {
        return Err(Error::new(NF_ERR_NULL_ARG, format!("{what} is NULL")));
    }
    // SAFETY: the caller passes a valid NUL-terminated string (header contract).
    unsafe { CStr::from_ptr(p) }
        .to_str()
        .map_err(|_| Error::invalid(format!("{what} is not valid UTF-8")))
}

/// An optional NUL-terminated UTF-8 argument (NULL = absent).
pub(crate) unsafe fn opt_cstr<'a>(p: *const c_char, what: &str) -> Result<Option<&'a str>> {
    if p.is_null() {
        Ok(None)
    } else {
        // SAFETY: as for cstr.
        unsafe { cstr(p, what) }.map(Some)
    }
}

/// A `(ptr, len)` argument; `ptr` may be NULL only when `len` is 0.
pub(crate) unsafe fn slice<'a, T>(p: *const T, len: usize, what: &str) -> Result<&'a [T]> {
    if len == 0 {
        return Ok(&[]);
    }
    if p.is_null() {
        return Err(Error::new(
            NF_ERR_NULL_ARG,
            format!("{what} is NULL with length {len}"),
        ));
    }
    check_region::<T>(p as usize, len, what)?;
    // SAFETY: the caller passes `len` readable elements at `p` (header contract); alignment and
    // the byte-size bound of from_raw_parts were checked above (CABI-L1).
    Ok(unsafe { std::slice::from_raw_parts(p, len) })
}

/// The `from_raw_parts` preconditions a C caller can get wrong: `addr` aligned for `T`, and
/// `len * size_of::<T>()` not above `isize::MAX` (CABI-L1). Violations are errors, not UB.
pub(crate) fn check_region<T>(addr: usize, len: usize, what: &str) -> Result<()> {
    if !addr.is_multiple_of(std::mem::align_of::<T>()) {
        return Err(Error::invalid(format!(
            "{what} is not aligned to {} bytes",
            std::mem::align_of::<T>()
        )));
    }
    if len
        .checked_mul(std::mem::size_of::<T>())
        .is_none_or(|b| b > isize::MAX as usize)
    {
        return Err(Error::invalid(format!("{what}: length {len} is too large")));
    }
    Ok(())
}

/// A `(ptr, len)` UTF-8 text argument.
pub(crate) unsafe fn text<'a>(p: *const u8, len: usize, what: &str) -> Result<&'a str> {
    // SAFETY: forwarded contract.
    std::str::from_utf8(unsafe { slice(p, len, what) }?)
        .map_err(|_| Error::invalid(format!("{what} is not valid UTF-8")))
}

/// A `(ptr, len)` JSON document parsed with nf-core's strict parser.
pub(crate) unsafe fn json(p: *const u8, len: usize, what: &str) -> Result<Value> {
    // SAFETY: forwarded contract.
    Ok(cjson::parse(unsafe { text(p, len, what) }?)?)
}

/// A non-NULL output pointer.
pub(crate) unsafe fn out<'a, T>(p: *mut T, what: &str) -> Result<&'a mut T> {
    if !p.is_null() {
        check_region::<T>(p as usize, 1, what)?;
    }
    // SAFETY: the caller passes a valid, writable pointer or NULL; alignment checked above.
    unsafe { p.as_mut() }.ok_or_else(|| Error::new(NF_ERR_NULL_ARG, format!("{what} is NULL")))
}

/// A non-NULL handle (or a caller struct passed by pointer).
pub(crate) unsafe fn handle<'a, T>(p: *const T, what: &str) -> Result<&'a T> {
    if !p.is_null() {
        check_region::<T>(p as usize, 1, what)?;
    }
    // SAFETY: the caller passes a live handle from the matching constructor, or NULL.
    unsafe { p.as_ref() }.ok_or_else(|| Error::new(NF_ERR_NULL_ARG, format!("{what} is NULL")))
}

/// An optional output pointer (NULL = not wanted).
pub(crate) unsafe fn opt_out<'a, T>(p: *mut T, what: &str) -> Result<Option<&'a mut T>> {
    if p.is_null() {
        Ok(None)
    } else {
        // SAFETY: forwarded contract.
        unsafe { out(p, what) }.map(Some)
    }
}

/// An optional input struct (NULL = defaults).
pub(crate) unsafe fn opt_handle<'a, T>(p: *const T, what: &str) -> Result<Option<&'a T>> {
    if p.is_null() {
        Ok(None)
    } else {
        // SAFETY: forwarded contract.
        unsafe { handle(p, what) }.map(Some)
    }
}

/// Whether `p` is non-NULL and aligned for `T` (for the void free functions, which cannot
/// report an error and simply ignore a bad pointer).
pub(crate) fn usable<T>(p: *const T) -> bool {
    !p.is_null() && check_region::<T>(p as usize, 1, "").is_ok()
}

/// Move a value into a new handle.
pub(crate) fn into_handle<T>(v: T) -> *mut T {
    Box::into_raw(Box::new(v))
}

/// Free a handle made by [`into_handle`] (NULL is a no-op).
pub(crate) unsafe fn free_handle<T>(p: *mut T) {
    let _ = catch_unwind(AssertUnwindSafe(|| {
        if !p.is_null() {
            // SAFETY: `p` came from into_handle and is freed once (header contract).
            drop(unsafe { Box::from_raw(p) });
        }
    }));
}

// ---------------------------------------------------------------- buffers
/// A library-owned byte buffer. `data[len]` is always 0 (not counted in `len`), so text results
/// are also C strings. Release with `nf_buf_free`. A zero-initialised `nf_buf` is empty.
#[repr(C)]
#[derive(Debug)]
pub struct nf_buf {
    pub data: *mut u8,
    pub len: usize,
}

/// A borrowed byte range passed to callbacks (valid only during the call).
#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct nf_bytes {
    pub data: *const u8,
    pub len: usize,
}

/// Fill `out` with a copy of `bytes` plus a trailing NUL.
pub(crate) fn put_buf(out: &mut nf_buf, bytes: impl Into<Vec<u8>>) {
    let mut v: Vec<u8> = bytes.into();
    let len = v.len();
    v.push(0);
    let b = v.into_boxed_slice();
    out.data = Box::into_raw(b).cast::<u8>();
    out.len = len;
}

/// Release a buffer filled by the library and reset it to empty. NULL, an empty buffer and a
/// buffer already freed are no-ops.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_buf_free(buf: *mut nf_buf) {
    let _ = catch_unwind(AssertUnwindSafe(|| {
        if !usable(buf) {
            return;
        }
        // SAFETY: a valid, aligned nf_buf (checked above; header contract).
        let Some(b) = (unsafe { buf.as_mut() }) else {
            return;
        };
        if !b.data.is_null() {
            // SAFETY: data/len came from put_buf: a boxed slice of len + 1 bytes.
            drop(unsafe { Box::from_raw(std::ptr::slice_from_raw_parts_mut(b.data, b.len + 1)) });
        }
        b.data = std::ptr::null_mut();
        b.len = 0;
    }));
}

// ---------------------------------------------------------------- dtypes
/// Sample data types (hashing.md sec. 5.2). Values are stable across ABI versions.
pub type nf_dtype = i32;
pub const NF_DTYPE_INT8: nf_dtype = 1;
pub const NF_DTYPE_UINT8: nf_dtype = 2;
pub const NF_DTYPE_INT16: nf_dtype = 3;
pub const NF_DTYPE_UINT16: nf_dtype = 4;
pub const NF_DTYPE_INT32: nf_dtype = 5;
pub const NF_DTYPE_UINT32: nf_dtype = 6;
pub const NF_DTYPE_INT64: nf_dtype = 7;
pub const NF_DTYPE_FLOAT32: nf_dtype = 8;
pub const NF_DTYPE_FLOAT64: nf_dtype = 9;

const DTYPES: [(nf_dtype, Dtype); 9] = [
    (NF_DTYPE_INT8, Dtype::Int8),
    (NF_DTYPE_UINT8, Dtype::Uint8),
    (NF_DTYPE_INT16, Dtype::Int16),
    (NF_DTYPE_UINT16, Dtype::Uint16),
    (NF_DTYPE_INT32, Dtype::Int32),
    (NF_DTYPE_UINT32, Dtype::Uint32),
    (NF_DTYPE_INT64, Dtype::Int64),
    (NF_DTYPE_FLOAT32, Dtype::Float32),
    (NF_DTYPE_FLOAT64, Dtype::Float64),
];

pub(crate) fn dtype_from(d: nf_dtype) -> Result<Dtype> {
    DTYPES
        .iter()
        .find(|(c, _)| *c == d)
        .map(|(_, t)| *t)
        .ok_or_else(|| Error::invalid(format!("unknown dtype code {d}")))
}

pub(crate) fn dtype_code(d: Dtype) -> nf_dtype {
    DTYPES.iter().find(|(_, t)| *t == d).map_or(0, |(c, _)| *c)
}

/// Name of a dtype (`"float32"`, ...), or NULL for an unknown code. Static string.
#[unsafe(no_mangle)]
pub extern "C" fn nf_dtype_name(dtype: nf_dtype) -> *const c_char {
    let s: &CStr = match dtype_from(dtype) {
        Ok(Dtype::Int8) => c"int8",
        Ok(Dtype::Uint8) => c"uint8",
        Ok(Dtype::Int16) => c"int16",
        Ok(Dtype::Uint16) => c"uint16",
        Ok(Dtype::Int32) => c"int32",
        Ok(Dtype::Uint32) => c"uint32",
        Ok(Dtype::Int64) => c"int64",
        Ok(Dtype::Float32) => c"float32",
        Ok(Dtype::Float64) => c"float64",
        Err(_) => return std::ptr::null(),
    };
    s.as_ptr()
}

/// Size of one element in bytes, or 0 for an unknown code.
#[unsafe(no_mangle)]
pub extern "C" fn nf_dtype_itemsize(dtype: nf_dtype) -> usize {
    dtype_from(dtype).map_or(0, Dtype::itemsize)
}

/// Parse a dtype name (`"int16"`, ...) into `*out`.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_dtype_parse(name: *const c_char, out: *mut nf_dtype) -> nf_status {
    guard(|| {
        // SAFETY: header contract for every pointer argument.
        let (name, out) = unsafe { (cstr(name, "name")?, self::out(out, "out")?) };
        *out = dtype_code(Dtype::parse(name).map_err(|e| Error::invalid(e.to_string()))?);
        Ok(())
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn version_packing() {
        assert_eq!(nf_abi_version() >> 16, NF_ABI_VERSION_MAJOR);
        // SAFETY: static string.
        let v = unsafe { CStr::from_ptr(nf_core_version()) };
        assert_eq!(v.to_str().unwrap(), nf_core::VERSION);
    }

    #[test]
    fn buf_round_trip_and_double_free() {
        let mut b = nf_buf {
            data: std::ptr::null_mut(),
            len: 0,
        };
        put_buf(&mut b, b"abc".to_vec());
        assert_eq!(b.len, 3);
        // SAFETY: filled above with len + 1 bytes.
        assert_eq!(unsafe { *b.data.add(3) }, 0);
        unsafe { nf_buf_free(&mut b) };
        assert!(b.data.is_null());
        unsafe { nf_buf_free(&mut b) };
        unsafe { nf_buf_free(std::ptr::null_mut()) };
    }

    #[test]
    fn panics_become_status() {
        let s = guard(|| panic!("boom"));
        assert_eq!(s, NF_ERR_PANIC);
        // SAFETY: thread-local C string.
        let m = unsafe { CStr::from_ptr(nf_last_error()) };
        assert!(m.to_str().unwrap().contains("boom"));
        assert_eq!(guard(|| Ok(())), NF_OK);
        assert_eq!(unsafe { CStr::from_ptr(nf_last_error()) }.to_bytes(), b"");
    }

    #[test]
    fn nested_failure_does_not_survive_an_outer_success() {
        // CABI-T1: a callback's last nested call fails, the outer call succeeds
        // SAFETY: thread-local C strings owned by the library
        let err = || {
            unsafe { CStr::from_ptr(nf_last_error()) }
                .to_bytes()
                .to_vec()
        };
        let detail = || {
            unsafe { CStr::from_ptr(nf_last_error_detail()) }
                .to_bytes()
                .to_vec()
        };
        let s = guard(|| {
            let inner = guard(|| {
                Err(Error {
                    code: NF_ERR_HTTP,
                    msg: "nested failure".into(),
                    detail: Some("{\"title\":\"x\"}".into()),
                })
            });
            assert_eq!(inner, NF_ERR_HTTP);
            // the nested text is visible inside the callback...
            assert_eq!(err(), b"nested failure");
            Ok(())
        });
        // ...but not after the outer NF_OK
        assert_eq!(s, NF_OK);
        assert_eq!(err(), b"");
        assert_eq!(detail(), b"");
        // the same through a value-returning entry point
        let v = guard_value(0u32, || {
            let _ = guard(|| Err(Error::invalid("nested")));
            Ok(7)
        });
        assert_eq!(v, 7);
        assert_eq!(err(), b"");
    }

    #[test]
    fn dtype_codes_round_trip() {
        for (c, d) in DTYPES {
            assert_eq!(dtype_code(d), c);
            assert_eq!(nf_dtype_itemsize(c), d.itemsize());
        }
        assert!(nf_dtype_name(0).is_null());
        assert_eq!(nf_dtype_itemsize(42), 0);
    }
}
