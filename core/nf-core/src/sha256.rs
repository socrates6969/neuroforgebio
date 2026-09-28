//! SHA-256 (FIPS 180-4) through the RustCrypto `sha2` crate, plus lowercase hex.

use sha2::Digest;

/// Streaming SHA-256 (for files that do not fit in memory).
#[derive(Clone, Default)]
pub struct Sha256(sha2::Sha256);

impl Sha256 {
    pub fn new() -> Self {
        Self(sha2::Sha256::new())
    }
    pub fn update(&mut self, data: &[u8]) {
        self.0.update(data);
    }
    pub fn finalize(self) -> [u8; 32] {
        self.0.finalize().into()
    }
}

/// SHA-256 digest of `data`.
pub fn sha256(data: &[u8]) -> [u8; 32] {
    sha2::Sha256::digest(data).into()
}

/// Lowercase hex encoding.
pub fn to_hex(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut s = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        s.push(HEX[(b >> 4) as usize] as char);
        s.push(HEX[(b & 0x0f) as usize] as char);
    }
    s
}

/// Decode lowercase or uppercase hex; `None` on odd length or a non-hex character.
pub fn from_hex(s: &str) -> Option<Vec<u8>> {
    if !s.len().is_multiple_of(2) {
        return None;
    }
    (0..s.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(s.get(i..i + 2)?, 16).ok())
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn nist_vectors() {
        assert_eq!(
            to_hex(&sha256(b"")),
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        );
        assert_eq!(
            to_hex(&sha256(b"abc")),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        );
        assert_eq!(
            to_hex(&sha256(
                b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"
            )),
            "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1"
        );
    }

    #[test]
    fn streaming_equals_one_shot() {
        let data: Vec<u8> = (0..10_000u32).map(|i| (i % 251) as u8).collect();
        let mut h = Sha256::new();
        for part in data.chunks(333) {
            h.update(part);
        }
        assert_eq!(h.finalize(), sha256(&data));
    }

    #[test]
    fn hex_roundtrip() {
        assert_eq!(from_hex("00ff10").unwrap(), vec![0, 255, 16]);
        assert!(from_hex("0").is_none() && from_hex("zz").is_none());
    }
}
