//! Base64 (RFC 4648): standard alphabet with padding, and URL-safe without padding (device
//! tokens). Small on purpose: avoids a dependency for two helpers.

const STD: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
const URL: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";

fn encode(data: &[u8], alphabet: &[u8; 64], pad: bool) -> String {
    let mut out = String::with_capacity(data.len().div_ceil(3) * 4);
    for chunk in data.chunks(3) {
        let b = [
            chunk[0],
            *chunk.get(1).unwrap_or(&0),
            *chunk.get(2).unwrap_or(&0),
        ];
        let n = (u32::from(b[0]) << 16) | (u32::from(b[1]) << 8) | u32::from(b[2]);
        let chars = chunk.len() + 1;
        for i in 0..4 {
            if i < chars {
                out.push(alphabet[((n >> (18 - 6 * i)) & 63) as usize] as char);
            } else if pad {
                out.push('=');
            }
        }
    }
    out
}

/// Strict decoding (L10): `padded` inputs need exactly the RFC 4648 padding (length a multiple of
/// 4, at most two `=`), unpadded inputs must not contain `=`, and the unused low bits of the last
/// character must be zero, so every byte string has exactly one accepted encoding.
fn decode(s: &str, alphabet: &[u8; 64], padded: bool) -> Option<Vec<u8>> {
    let body = s.trim_end_matches('=');
    let pad = s.len() - body.len();
    if padded {
        if !s.len().is_multiple_of(4) || pad > 2 || (pad > 0 && body.len() % 4 + pad != 4) {
            return None;
        }
    } else if pad != 0 {
        return None;
    }
    let s = body;
    let mut rev = [255u8; 256];
    for (i, c) in alphabet.iter().enumerate() {
        rev[*c as usize] = i as u8;
    }
    if s.len() % 4 == 1 {
        return None;
    }
    let mut out = Vec::with_capacity(s.len() * 3 / 4);
    let bytes = s.as_bytes();
    for chunk in bytes.chunks(4) {
        let mut n = 0u32;
        for (i, c) in chunk.iter().enumerate() {
            let v = rev[*c as usize];
            if v == 255 {
                return None;
            }
            n |= u32::from(v) << (18 - 6 * i);
        }
        let take = chunk.len() - 1;
        // bits below the last decoded byte must be zero (non-canonical encodings rejected)
        if take < 3 && n & ((1u32 << (24 - 8 * take)) - 1) != 0 {
            return None;
        }
        for i in 0..take {
            out.push((n >> (16 - 8 * i)) as u8);
        }
    }
    Some(out)
}

pub fn encode_std(data: &[u8]) -> String {
    encode(data, STD, true)
}
pub fn decode_std(s: &str) -> Option<Vec<u8>> {
    decode(s, STD, true)
}
pub fn encode_url(data: &[u8]) -> String {
    encode(data, URL, false)
}
pub fn decode_url(s: &str) -> Option<Vec<u8>> {
    decode(s, URL, false)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rfc4648_vectors() {
        let cases = [
            ("", ""),
            ("f", "Zg=="),
            ("fo", "Zm8="),
            ("foo", "Zm9v"),
            ("foob", "Zm9vYg=="),
            ("fooba", "Zm9vYmE="),
            ("foobar", "Zm9vYmFy"),
        ];
        for (plain, enc) in cases {
            assert_eq!(encode_std(plain.as_bytes()), enc);
            assert_eq!(decode_std(enc).unwrap(), plain.as_bytes());
            assert_eq!(
                decode_url(&encode_url(plain.as_bytes())).unwrap(),
                plain.as_bytes()
            );
        }
        assert_eq!(encode_url(&[0xfb, 0xff]), "-_8");
        assert!(decode_std("Zm9v!").is_none());
    }

    /// L10: padding must be exact and trailing bits zero; the URL form takes no padding.
    #[test]
    fn strict_padding_and_trailing_bits() {
        for bad in [
            "Zg", "Zg=", "Zg===", "Zm8", "Zm8==", "Zh==", "Zm9=", "Z===", "Zm9v====",
        ] {
            assert!(decode_std(bad).is_none(), "{bad}");
        }
        for bad in ["Zg==", "Zh", "Zm9", "Zm8="] {
            assert!(decode_url(bad).is_none(), "{bad}");
        }
        assert_eq!(decode_url("Zg").unwrap(), b"f");
        assert_eq!(decode_url("Zm8").unwrap(), b"fo");
        assert_eq!(decode_std("").unwrap(), b"");
        for n in 0..40u8 {
            let data: Vec<u8> = (0..n).map(|i| i.wrapping_mul(37) ^ 0xa5).collect();
            assert_eq!(decode_std(&encode_std(&data)).unwrap(), data);
            assert_eq!(decode_url(&encode_url(&data)).unwrap(), data);
        }
    }
}
