//! Keys for the write-ahead buffer and the device identity (SEC-016, SEC-037).
//!
//! - Windows: DPAPI (CryptProtectData, current-user scope). Only the sealed blob is written to
//!   disk; the file format equals the 2.7 prototype's (`edge_prototype/wal.py`), so a key sealed
//!   by the prototype opens here and vice versa.
//! - macOS Keychain / Linux Secret Service: not implemented in the core yet; callers on those
//!   platforms pass a key they obtained from the OS keystore ([`StaticKey`]), or use an
//!   [`EphemeralKey`] (records cannot be recovered after a restart).

use std::path::{Path, PathBuf};

use zeroize::Zeroizing;

#[derive(Debug)]
pub enum KeyError {
    Io(std::io::Error),
    Unavailable(&'static str),
    Os(&'static str),
    Length,
}

impl std::fmt::Display for KeyError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Io(e) => write!(f, "key file: {e}"),
            Self::Unavailable(m) => write!(f, "OS keystore unavailable: {m}"),
            Self::Os(m) => write!(f, "OS keystore call failed: {m}"),
            Self::Length => f.write_str("key has the wrong length"),
        }
    }
}
impl std::error::Error for KeyError {}
impl From<std::io::Error> for KeyError {
    fn from(e: std::io::Error) -> Self {
        Self::Io(e)
    }
}

pub type Key32 = Zeroizing<[u8; 32]>;

pub trait KeyProvider: Send + Sync {
    fn key(&self) -> Result<Key32, KeyError>;
}

pub fn random_key() -> Key32 {
    let mut k = Zeroizing::new([0u8; 32]);
    getrandom::getrandom(k.as_mut()).expect("OS random source");
    k
}

/// A random key held in memory only.
pub struct EphemeralKey(Key32);

impl EphemeralKey {
    pub fn new() -> Self {
        Self(random_key())
    }
}
impl Default for EphemeralKey {
    fn default() -> Self {
        Self::new()
    }
}
impl KeyProvider for EphemeralKey {
    fn key(&self) -> Result<Key32, KeyError> {
        Ok(self.0.clone())
    }
}

/// A key the caller fetched from an OS keystore.
pub struct StaticKey(Key32);

impl StaticKey {
    pub fn new(bytes: &[u8]) -> Result<Self, KeyError> {
        let arr: [u8; 32] = bytes.try_into().map_err(|_| KeyError::Length)?;
        Ok(Self(Zeroizing::new(arr)))
    }
}
impl KeyProvider for StaticKey {
    fn key(&self) -> Result<Key32, KeyError> {
        Ok(self.0.clone())
    }
}

/// A 32-byte secret sealed with DPAPI at `path`, created on first use.
pub struct DpapiKey {
    path: PathBuf,
    cached: std::sync::Mutex<Option<Key32>>,
}

impl DpapiKey {
    pub fn new(path: impl Into<PathBuf>) -> Result<Self, KeyError> {
        if !cfg!(windows) {
            return Err(KeyError::Unavailable("DPAPI is only available on Windows"));
        }
        Ok(Self {
            path: path.into(),
            cached: std::sync::Mutex::new(None),
        })
    }
    pub fn path(&self) -> &Path {
        &self.path
    }
}

impl KeyProvider for DpapiKey {
    fn key(&self) -> Result<Key32, KeyError> {
        let mut c = self.cached.lock().expect("key lock");
        if let Some(k) = c.as_ref() {
            return Ok(k.clone());
        }
        let k = load_or_create_sealed(&self.path)?;
        *c = Some(k.clone());
        Ok(k)
    }
}

/// Unseal the secret at `path`, or create, seal and store a new random one.
pub fn load_or_create_sealed(path: &Path) -> Result<Key32, KeyError> {
    if path.exists() {
        let sealed = std::fs::read(path)?;
        let plain = Zeroizing::new(dpapi(&sealed, false)?);
        let arr: [u8; 32] = plain.as_slice().try_into().map_err(|_| KeyError::Length)?;
        return Ok(Zeroizing::new(arr));
    }
    let k = random_key();
    let sealed = dpapi(k.as_ref(), true)?;
    if let Some(dir) = path.parent() {
        std::fs::create_dir_all(dir)?;
    }
    let tmp = path.with_extension("tmp");
    {
        use std::io::Write;
        let mut f = std::fs::File::create(&tmp)?;
        f.write_all(&sealed)?;
        f.sync_all()?;
    }
    std::fs::rename(&tmp, path)?;
    crate::durable::sync_parent(path)?;
    Ok(k)
}

#[cfg(windows)]
fn dpapi(data: &[u8], protect: bool) -> Result<Vec<u8>, KeyError> {
    use std::ffi::c_void;

    #[repr(C)]
    struct Blob {
        cb: u32,
        pb: *mut u8,
    }
    #[link(name = "crypt32")]
    unsafe extern "system" {
        fn CryptProtectData(
            data_in: *const Blob,
            descr: *const u16,
            entropy: *const Blob,
            reserved: *mut c_void,
            prompt: *const c_void,
            flags: u32,
            data_out: *mut Blob,
        ) -> i32;
        fn CryptUnprotectData(
            data_in: *const Blob,
            descr: *mut *mut u16,
            entropy: *const Blob,
            reserved: *mut c_void,
            prompt: *const c_void,
            flags: u32,
            data_out: *mut Blob,
        ) -> i32;
    }
    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn LocalFree(mem: *mut c_void) -> *mut c_void;
    }
    const UI_FORBIDDEN: u32 = 0x1;
    let mut input = data.to_vec();
    let blob_in = Blob {
        cb: u32::try_from(input.len()).map_err(|_| KeyError::Length)?,
        pb: input.as_mut_ptr(),
    };
    let mut out = Blob {
        cb: 0,
        pb: std::ptr::null_mut(),
    };
    // SAFETY: pointers reference live buffers for the duration of the call; the output buffer is
    // allocated by the OS, copied, then released with LocalFree exactly once.
    let ok = unsafe {
        if protect {
            CryptProtectData(
                &blob_in,
                std::ptr::null(),
                std::ptr::null(),
                std::ptr::null_mut(),
                std::ptr::null(),
                UI_FORBIDDEN,
                &mut out,
            )
        } else {
            CryptUnprotectData(
                &blob_in,
                std::ptr::null_mut(),
                std::ptr::null(),
                std::ptr::null_mut(),
                std::ptr::null(),
                UI_FORBIDDEN,
                &mut out,
            )
        }
    };
    zeroize::Zeroize::zeroize(&mut input);
    if ok == 0 || out.pb.is_null() {
        return Err(KeyError::Os(if protect {
            "CryptProtectData"
        } else {
            "CryptUnprotectData"
        }));
    }
    // SAFETY: the OS returned `out.cb` valid bytes at `out.pb`.
    let v = unsafe { std::slice::from_raw_parts(out.pb, out.cb as usize).to_vec() };
    // SAFETY: `out.pb` was allocated by DPAPI with LocalAlloc.
    unsafe {
        std::ptr::write_bytes(out.pb, 0, out.cb as usize);
        LocalFree(out.pb.cast());
    }
    Ok(v)
}

#[cfg(not(windows))]
fn dpapi(_data: &[u8], _protect: bool) -> Result<Vec<u8>, KeyError> {
    Err(KeyError::Unavailable("DPAPI is only available on Windows"))
}

#[cfg(all(test, windows))]
mod tests {
    use super::*;

    #[test]
    fn dpapi_seals_and_reopens() {
        let p = std::env::temp_dir().join(format!("nfcore-dpapi-{}.key", std::process::id()));
        let _ = std::fs::remove_file(&p);
        let k1 = DpapiKey::new(&p).unwrap().key().unwrap();
        let sealed = std::fs::read(&p).unwrap();
        assert!(sealed.windows(32).all(|w| w != k1.as_ref()));
        let k2 = DpapiKey::new(&p).unwrap().key().unwrap();
        assert_eq!(k1, k2);
        let _ = std::fs::remove_file(&p);
    }
}
