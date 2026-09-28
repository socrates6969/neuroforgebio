//! Helpers shared by the ABI tests: call through the exported C functions exactly as C would.
#![allow(dead_code)]

use std::ffi::{CStr, CString, c_char};

use neuroforge::{NF_OK, nf_buf, nf_buf_free, nf_last_error, nf_status};
use nf_core::cjson::{self, Value};

pub fn empty() -> nf_buf {
    nf_buf {
        data: std::ptr::null_mut(),
        len: 0,
    }
}

/// Take the bytes out of a library buffer and free it (checks the trailing NUL).
pub fn take(mut b: nf_buf) -> Vec<u8> {
    assert!(!b.data.is_null(), "buffer not filled");
    // SAFETY: filled by the library with len + 1 bytes.
    let v = unsafe { std::slice::from_raw_parts(b.data, b.len + 1) }.to_vec();
    assert_eq!(v[b.len], 0, "missing NUL terminator");
    unsafe { nf_buf_free(&mut b) };
    assert!(b.data.is_null());
    v[..v.len() - 1].to_vec()
}

pub fn take_str(b: nf_buf) -> String {
    String::from_utf8(take(b)).expect("utf-8")
}

pub fn last_error() -> String {
    // SAFETY: thread-local C string owned by the library.
    unsafe { CStr::from_ptr(nf_last_error()) }
        .to_str()
        .unwrap()
        .to_owned()
}

/// Run `f(out)` and return the text result, panicking with the last error on failure.
pub fn text_out(f: impl FnOnce(*mut nf_buf) -> nf_status) -> String {
    let mut b = empty();
    let s = f(&mut b);
    assert_eq!(s, NF_OK, "status {s}: {}", last_error());
    take_str(b)
}

/// Status of `f(out)`; frees any output.
pub fn status_of(f: impl FnOnce(*mut nf_buf) -> nf_status) -> nf_status {
    let mut b = empty();
    let s = f(&mut b);
    unsafe { nf_buf_free(&mut b) };
    s
}

pub fn c(s: &str) -> CString {
    CString::new(s).unwrap()
}

pub fn cp(s: &CString) -> *const c_char {
    s.as_ptr()
}

pub fn load(name: &str) -> Value {
    let path = format!(
        "{}/../../spec/test-vectors/{name}",
        env!("CARGO_MANIFEST_DIR")
    );
    cjson::parse(&std::fs::read_to_string(path).expect("vector file")).expect("strict JSON")
}

pub fn get<'a>(v: &'a Value, key: &str) -> &'a Value {
    v.get(key).unwrap_or_else(|| panic!("missing {key}"))
}

pub fn arr<'a>(v: &'a Value, key: &str) -> &'a [Value] {
    match get(v, key) {
        Value::Array(a) => a,
        _ => panic!("{key} is not an array"),
    }
}

pub fn s<'a>(v: &'a Value, key: &str) -> &'a str {
    get(v, key)
        .as_str()
        .unwrap_or_else(|| panic!("{key} is not a string"))
}

pub fn int(v: &Value, key: &str) -> i64 {
    match get(v, key) {
        Value::Int(n) => *n,
        _ => panic!("{key} is not an integer"),
    }
}

pub fn num(v: &Value) -> f64 {
    match v {
        Value::Int(n) => *n as f64,
        Value::Float(f) => *f,
        _ => panic!("not a number"),
    }
}

/// Canonical JSON text of a value (what a C caller would pass in).
pub fn json(v: &Value) -> Vec<u8> {
    cjson::to_canonical(v).unwrap()
}

pub fn hex(s: &str) -> Vec<u8> {
    nf_core::sha256::from_hex(s).expect("hex")
}
