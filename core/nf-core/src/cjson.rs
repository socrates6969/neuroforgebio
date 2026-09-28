//! NF-CJSON v1 (`docs/spec/hashing.md` §3): RFC 8785 (JCS) plus Unicode NFC of every string,
//! including object keys.
//!
//! - [`parse`] is strict: duplicate keys (also after NFC), `NaN`/`Infinity`, lone surrogates,
//!   raw control characters and integer literals beyond 2^53 - 1 are errors. Nesting is capped
//!   at [`MAX_DEPTH`] so hostile input cannot overflow the stack (SEC-062).
//! - [`to_canonical`] writes the canonical bytes: NFC strings, JCS escapes, ECMAScript number
//!   form, members sorted by UTF-16 code units, no whitespace.

use std::fmt;

use unicode_normalization::UnicodeNormalization;

/// Largest integer literal allowed (|n| <= 2^53 - 1).
pub const MAX_SAFE_INT: i64 = (1 << 53) - 1;
/// Maximum nesting depth accepted by the parser.
pub const MAX_DEPTH: usize = 128;

/// A JSON value. Integer literals stay integers (a batch `seq` of `1.0` is not an integer).
#[derive(Debug, Clone, PartialEq)]
pub enum Value {
    Null,
    Bool(bool),
    Int(i64),
    Float(f64),
    String(String),
    Array(Vec<Value>),
    /// Members in input order; canonical output sorts them.
    Object(Vec<(String, Value)>),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum CanonError {
    Syntax {
        pos: usize,
        msg: &'static str,
    },
    DuplicateKey(String),
    UnsafeInteger,
    NonFinite,
    LoneSurrogate,
    TooDeep,
    /// A structural rule of an ID kind (hashing.md §5) is violated.
    Invalid(String),
}

impl fmt::Display for CanonError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Syntax { pos, msg } => write!(f, "JSON syntax error at byte {pos}: {msg}"),
            Self::DuplicateKey(k) => write!(f, "duplicate key (after NFC): {k:?}"),
            Self::UnsafeInteger => f.write_str("integer beyond 2^53-1; encode it as a string"),
            Self::NonFinite => f.write_str("NaN and Infinity are not allowed"),
            Self::LoneSurrogate => f.write_str("lone surrogate in string"),
            Self::TooDeep => write!(f, "nesting deeper than {MAX_DEPTH}"),
            Self::Invalid(m) => f.write_str(m),
        }
    }
}

impl std::error::Error for CanonError {}

type Result<T> = std::result::Result<T, CanonError>;

impl Value {
    pub fn get(&self, key: &str) -> Option<&Value> {
        match self {
            Value::Object(m) => m.iter().find(|(k, _)| k == key).map(|(_, v)| v),
            _ => None,
        }
    }
    pub fn as_str(&self) -> Option<&str> {
        match self {
            Value::String(s) => Some(s),
            _ => None,
        }
    }
    pub fn obj<K: Into<String>>(members: impl IntoIterator<Item = (K, Value)>) -> Value {
        Value::Object(members.into_iter().map(|(k, v)| (k.into(), v)).collect())
    }
    pub fn str(s: impl Into<String>) -> Value {
        Value::String(s.into())
    }
}

// ---------------------------------------------------------------- parser
/// Parse JSON text strictly (hashing.md §3.1). Strings are NFC-normalised while parsing.
pub fn parse(text: &str) -> Result<Value> {
    let mut p = Parser {
        b: text.as_bytes(),
        i: 0,
    };
    p.ws();
    let v = p.value(0)?;
    p.ws();
    if p.i != p.b.len() {
        return Err(p.err("trailing characters"));
    }
    Ok(v)
}

/// Canonical bytes of JSON text.
pub fn canonicalize_text(text: &str) -> Result<Vec<u8>> {
    to_canonical(&parse(text)?)
}

struct Parser<'a> {
    b: &'a [u8],
    i: usize,
}

impl Parser<'_> {
    fn err(&self, msg: &'static str) -> CanonError {
        CanonError::Syntax { pos: self.i, msg }
    }
    fn ws(&mut self) {
        while let Some(c) = self.b.get(self.i) {
            if matches!(c, b' ' | b'\t' | b'\n' | b'\r') {
                self.i += 1;
            } else {
                break;
            }
        }
    }
    fn peek(&self) -> Option<u8> {
        self.b.get(self.i).copied()
    }
    fn lit(&mut self, word: &str, v: Value) -> Result<Value> {
        if self.b[self.i..].starts_with(word.as_bytes()) {
            self.i += word.len();
            Ok(v)
        } else {
            Err(self.err("invalid literal"))
        }
    }
    fn value(&mut self, depth: usize) -> Result<Value> {
        if depth > MAX_DEPTH {
            return Err(CanonError::TooDeep);
        }
        match self.peek() {
            None => Err(self.err("unexpected end of input")),
            Some(b'{') => self.object(depth),
            Some(b'[') => self.array(depth),
            Some(b'"') => Ok(Value::String(self.string()?)),
            Some(b't') => self.lit("true", Value::Bool(true)),
            Some(b'f') => self.lit("false", Value::Bool(false)),
            Some(b'n') => self.lit("null", Value::Null),
            Some(b'N') | Some(b'I') => Err(CanonError::NonFinite),
            Some(b'-') if self.b.get(self.i + 1) == Some(&b'I') => Err(CanonError::NonFinite),
            Some(c) if c == b'-' || c.is_ascii_digit() => self.number(),
            Some(_) => Err(self.err("unexpected character")),
        }
    }
    fn object(&mut self, depth: usize) -> Result<Value> {
        self.i += 1;
        let mut members: Vec<(String, Value)> = Vec::new();
        self.ws();
        if self.peek() == Some(b'}') {
            self.i += 1;
            return Ok(Value::Object(members));
        }
        loop {
            self.ws();
            if self.peek() != Some(b'"') {
                return Err(self.err("expected string key"));
            }
            let k = self.string()?;
            if members.iter().any(|(e, _)| *e == k) {
                return Err(CanonError::DuplicateKey(k));
            }
            self.ws();
            if self.peek() != Some(b':') {
                return Err(self.err("expected ':'"));
            }
            self.i += 1;
            self.ws();
            let v = self.value(depth + 1)?;
            members.push((k, v));
            self.ws();
            match self.peek() {
                Some(b',') => self.i += 1,
                Some(b'}') => {
                    self.i += 1;
                    return Ok(Value::Object(members));
                }
                _ => return Err(self.err("expected ',' or '}'")),
            }
        }
    }
    fn array(&mut self, depth: usize) -> Result<Value> {
        self.i += 1;
        let mut items = Vec::new();
        self.ws();
        if self.peek() == Some(b']') {
            self.i += 1;
            return Ok(Value::Array(items));
        }
        loop {
            self.ws();
            items.push(self.value(depth + 1)?);
            self.ws();
            match self.peek() {
                Some(b',') => self.i += 1,
                Some(b']') => {
                    self.i += 1;
                    return Ok(Value::Array(items));
                }
                _ => return Err(self.err("expected ',' or ']'")),
            }
        }
    }
    fn hex4(&mut self) -> Result<u32> {
        let h = self
            .b
            .get(self.i..self.i + 4)
            .ok_or_else(|| self.err("short \\u escape"))?;
        let s = std::str::from_utf8(h).map_err(|_| self.err("bad \\u escape"))?;
        let v = u32::from_str_radix(s, 16).map_err(|_| self.err("bad \\u escape"))?;
        self.i += 4;
        Ok(v)
    }
    fn string(&mut self) -> Result<String> {
        self.i += 1; // opening quote
        let mut out = String::new();
        loop {
            let start = self.i;
            while let Some(c) = self.peek() {
                if c == b'"' || c == b'\\' || c < 0x20 {
                    break;
                }
                self.i += 1;
            }
            // input is &str, and we only stop on ASCII bytes, so this slice is valid UTF-8
            out.push_str(std::str::from_utf8(&self.b[start..self.i]).expect("utf-8 slice"));
            match self.peek() {
                None => return Err(self.err("unterminated string")),
                Some(b'"') => {
                    self.i += 1;
                    break;
                }
                Some(b'\\') => {
                    self.i += 1;
                    let e = self.peek().ok_or_else(|| self.err("dangling escape"))?;
                    self.i += 1;
                    match e {
                        b'"' => out.push('"'),
                        b'\\' => out.push('\\'),
                        b'/' => out.push('/'),
                        b'b' => out.push('\u{8}'),
                        b'f' => out.push('\u{c}'),
                        b'n' => out.push('\n'),
                        b'r' => out.push('\r'),
                        b't' => out.push('\t'),
                        b'u' => {
                            let v = self.hex4()?;
                            let cp = if (0xD800..0xDC00).contains(&v) {
                                if self.b.get(self.i..self.i + 2) != Some(b"\\u") {
                                    return Err(CanonError::LoneSurrogate);
                                }
                                self.i += 2;
                                let lo = self.hex4()?;
                                if !(0xDC00..0xE000).contains(&lo) {
                                    return Err(CanonError::LoneSurrogate);
                                }
                                0x10000 + ((v - 0xD800) << 10) + (lo - 0xDC00)
                            } else if (0xDC00..0xE000).contains(&v) {
                                return Err(CanonError::LoneSurrogate);
                            } else {
                                v
                            };
                            out.push(char::from_u32(cp).ok_or(CanonError::LoneSurrogate)?);
                        }
                        _ => return Err(self.err("invalid escape")),
                    }
                }
                Some(_) => return Err(self.err("control character in string")),
            }
        }
        Ok(out.nfc().collect())
    }
    fn number(&mut self) -> Result<Value> {
        let start = self.i;
        if self.peek() == Some(b'-') {
            self.i += 1;
        }
        match self.peek() {
            Some(b'0') => self.i += 1,
            Some(c) if c.is_ascii_digit() => {
                while self.peek().is_some_and(|c| c.is_ascii_digit()) {
                    self.i += 1;
                }
            }
            _ => return Err(self.err("expected digit")),
        }
        let mut integer = true;
        if self.peek() == Some(b'.') {
            integer = false;
            self.i += 1;
            if !self.peek().is_some_and(|c| c.is_ascii_digit()) {
                return Err(self.err("expected fraction digit"));
            }
            while self.peek().is_some_and(|c| c.is_ascii_digit()) {
                self.i += 1;
            }
        }
        if matches!(self.peek(), Some(b'e') | Some(b'E')) {
            integer = false;
            self.i += 1;
            if matches!(self.peek(), Some(b'+') | Some(b'-')) {
                self.i += 1;
            }
            if !self.peek().is_some_and(|c| c.is_ascii_digit()) {
                return Err(self.err("expected exponent digit"));
            }
            while self.peek().is_some_and(|c| c.is_ascii_digit()) {
                self.i += 1;
            }
        }
        let text = std::str::from_utf8(&self.b[start..self.i]).expect("ascii");
        if integer {
            let digits = text.trim_start_matches('-');
            if digits.len() > 16 {
                return Err(CanonError::UnsafeInteger);
            }
            let n: i64 = text.parse().map_err(|_| CanonError::UnsafeInteger)?;
            if n.unsigned_abs() > MAX_SAFE_INT.unsigned_abs() {
                return Err(CanonError::UnsafeInteger);
            }
            if n == 0 && text.starts_with('-') {
                return Ok(Value::Float(-0.0));
            }
            return Ok(Value::Int(n));
        }
        let f: f64 = text.parse().map_err(|_| self.err("bad number"))?;
        if !f.is_finite() {
            return Err(CanonError::NonFinite);
        }
        Ok(Value::Float(f))
    }
}

// ---------------------------------------------------------------- writer
/// ECMAScript `Number.prototype.toString` of a finite double (RFC 8785 §3.2.2.3).
pub fn format_number(x: f64) -> Result<String> {
    if !x.is_finite() {
        return Err(CanonError::NonFinite);
    }
    if x == 0.0 {
        return Ok("0".into());
    }
    let mut out = String::new();
    if x < 0.0 {
        out.push('-');
    }
    let (digits, exp) = shortest_digits(x.abs());
    let k = digits.len() as i32;
    let n = exp + 1; // value = 0.d1d2..dk * 10^n
    if k <= n && n <= 21 {
        out.push_str(&digits);
        out.extend(std::iter::repeat_n('0', (n - k) as usize));
    } else if 0 < n && n <= 21 {
        out.push_str(&digits[..n as usize]);
        out.push('.');
        out.push_str(&digits[n as usize..]);
    } else if -6 < n && n <= 0 {
        out.push_str("0.");
        out.extend(std::iter::repeat_n('0', (-n) as usize));
        out.push_str(&digits);
    } else {
        let e1 = n - 1;
        out.push_str(&digits[..1]);
        if k > 1 {
            out.push('.');
            out.push_str(&digits[1..]);
        }
        out.push('e');
        out.push(if e1 < 0 { '-' } else { '+' });
        out.push_str(&e1.abs().to_string());
    }
    Ok(out)
}

fn split_exp(e: &str) -> (String, i32) {
    let (mant, exp) = e.split_once('e').expect("exponent form");
    (
        mant.chars().filter(|c| *c != '.').collect(),
        exp.parse().expect("exponent"),
    )
}

fn digits_value(digits: &str, exp: i32) -> f64 {
    format!("{}.{}e{exp}", &digits[..1], &digits[1..])
        .parse()
        .expect("float text")
}

/// Add one unit in the last place of a decimal digit string (`None` if the length changes).
fn digits_plus_one(d: &str) -> Option<String> {
    let mut b = d.as_bytes().to_vec();
    for i in (0..b.len()).rev() {
        if b[i] == b'9' {
            b[i] = b'0';
        } else {
            b[i] += 1;
            return Some(String::from_utf8(b).expect("ascii"));
        }
    }
    None
}

/// Shortest round-trip significand digits and decimal exponent of a positive finite double,
/// choosing like ECMAScript (Number::toString step 5): the candidate closest to `x`, and on an
/// exact tie the even one. Rust's `{:e}` already gives the shortest length; it can differ from
/// ECMAScript only in that tie, e.g. 0x43143ff3c1cb0959 = 1424953923781206.25 must print
/// `...206.2` (RFC 8785 Appendix B), where Rust prints `...206.3`.
fn shortest_digits(x: f64) -> (String, i32) {
    let (digits, exp) = split_exp(&format!("{x:e}"));
    // Fast path: a tie needs another same-length candidate that also round-trips.
    let last = digits.as_bytes()[digits.len() - 1];
    let alt_up = digits_plus_one(&digits).is_some_and(|d| digits_value(&d, exp) == x);
    let alt_down = digits.len() > 1 && last > b'0' && {
        let mut d = digits.clone().into_bytes();
        *d.last_mut().expect("digit") -= 1;
        digits_value(std::str::from_utf8(&d).expect("ascii"), exp) == x
    };
    if !alt_up && !alt_down {
        return (digits, exp);
    }
    // exact decimal expansion (a double has at most 767 significant digits)
    let (exact, eexp) = split_exp(&format!("{x:.800e}"));
    if eexp != exp || digits.len() >= exact.len() {
        return (digits, exp);
    }
    let k = digits.len();
    let floor = exact[..k].to_owned();
    let rest = exact[k..].trim_end_matches('0');
    let Some(ceil) = digits_plus_one(&floor) else {
        return (digits, exp);
    };
    let even = |d: &str| (d.as_bytes()[k - 1] - b'0').is_multiple_of(2);
    let preferred = match rest.as_bytes().first() {
        None => return (floor, exp), // exact
        Some(b'5') if rest.len() == 1 => {
            if even(&floor) {
                &floor
            } else {
                &ceil
            }
        }
        Some(c) if *c >= b'5' => &ceil,
        _ => &floor,
    };
    if *preferred != digits && digits_value(preferred, exp) == x {
        return (preferred.clone(), exp);
    }
    (digits, exp)
}

fn write_string(out: &mut String, s: &str) {
    out.push('"');
    for ch in s.nfc() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\u{8}' => out.push_str("\\b"),
            '\u{c}' => out.push_str("\\f"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
}

fn write_value(out: &mut String, v: &Value, depth: usize) -> Result<()> {
    if depth > MAX_DEPTH {
        return Err(CanonError::TooDeep);
    }
    match v {
        Value::Null => out.push_str("null"),
        Value::Bool(true) => out.push_str("true"),
        Value::Bool(false) => out.push_str("false"),
        Value::Int(n) => {
            if n.unsigned_abs() > MAX_SAFE_INT.unsigned_abs() {
                return Err(CanonError::UnsafeInteger);
            }
            out.push_str(&n.to_string());
        }
        Value::Float(f) => out.push_str(&format_number(*f)?),
        Value::String(s) => write_string(out, s),
        Value::Array(items) => {
            out.push('[');
            for (i, it) in items.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                write_value(out, it, depth + 1)?;
            }
            out.push(']');
        }
        Value::Object(members) => {
            let mut norm: Vec<(String, &Value)> = Vec::with_capacity(members.len());
            for (k, val) in members {
                let nk: String = k.nfc().collect();
                if norm.iter().any(|(e, _)| *e == nk) {
                    return Err(CanonError::DuplicateKey(nk));
                }
                norm.push((nk, val));
            }
            norm.sort_by(|a, b| a.0.encode_utf16().cmp(b.0.encode_utf16()));
            out.push('{');
            for (i, (k, val)) in norm.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                write_string(out, k);
                out.push(':');
                write_value(out, val, depth + 1)?;
            }
            out.push('}');
        }
    }
    Ok(())
}

/// Canonical UTF-8 bytes of a value (hashing.md §3).
pub fn to_canonical(v: &Value) -> Result<Vec<u8>> {
    let mut s = String::new();
    write_value(&mut s, v, 0)?;
    Ok(s.into_bytes())
}

/// Convert a `serde_json::Value` (e.g. a serialised model type). Integers outside the safe range
/// are rejected, as in the spec.
pub fn from_serde(v: &serde_json::Value) -> Result<Value> {
    Ok(match v {
        serde_json::Value::Null => Value::Null,
        serde_json::Value::Bool(b) => Value::Bool(*b),
        serde_json::Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                if i.unsigned_abs() > MAX_SAFE_INT.unsigned_abs() {
                    return Err(CanonError::UnsafeInteger);
                }
                Value::Int(i)
            } else if n.as_u64().is_some() {
                return Err(CanonError::UnsafeInteger);
            } else {
                let f = n.as_f64().ok_or(CanonError::NonFinite)?;
                Value::Float(f)
            }
        }
        serde_json::Value::String(s) => Value::String(s.clone()),
        serde_json::Value::Array(a) => {
            Value::Array(a.iter().map(from_serde).collect::<Result<_>>()?)
        }
        serde_json::Value::Object(m) => Value::Object(
            m.iter()
                .map(|(k, v)| Ok((k.clone(), from_serde(v)?)))
                .collect::<Result<_>>()?,
        ),
    })
}

/// Canonical bytes of any serde-serialisable value.
pub fn canonicalize_serde<T: serde::Serialize>(v: &T) -> Result<Vec<u8>> {
    let j = serde_json::to_value(v).map_err(|e| CanonError::Invalid(e.to_string()))?;
    to_canonical(&from_serde(&j)?)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn c(s: &str) -> String {
        String::from_utf8(canonicalize_text(s).unwrap()).unwrap()
    }

    #[test]
    fn basics() {
        assert_eq!(
            c(r#" {"b":1, "a":[true,null]} "#),
            r#"{"a":[true,null],"b":1}"#
        );
        assert_eq!(
            c("[1.0,-0,1e21,1E-7,0.000001]"),
            "[1,0,1e+21,1e-7,0.000001]"
        );
        assert_eq!(c(r#""é\/""#), "\"\u{e9}/\"");
    }

    #[test]
    fn errors() {
        assert_eq!(
            parse(r#"{"a":1,"a":2}"#),
            Err(CanonError::DuplicateKey("a".into()))
        );
        assert_eq!(parse("9007199254740992"), Err(CanonError::UnsafeInteger));
        assert_eq!(parse("NaN"), Err(CanonError::NonFinite));
        assert_eq!(parse("[-Infinity]"), Err(CanonError::NonFinite));
        assert_eq!(parse("1e400"), Err(CanonError::NonFinite));
        assert_eq!(parse(r#""\ud800""#), Err(CanonError::LoneSurrogate));
        assert_eq!(parse(r#""\udc00x""#), Err(CanonError::LoneSurrogate));
        assert!(matches!(parse("[1,]"), Err(CanonError::Syntax { .. })));
        assert!(matches!(parse("\"a\nb\""), Err(CanonError::Syntax { .. })));
        assert!(matches!(parse("01"), Err(CanonError::Syntax { .. })));
        let deep = "[".repeat(MAX_DEPTH + 2) + &"]".repeat(MAX_DEPTH + 2);
        assert_eq!(parse(&deep), Err(CanonError::TooDeep));
    }

    #[test]
    fn nfc_collision_on_constructed_values() {
        let v = Value::obj([("\u{e9}", Value::Int(1)), ("e\u{301}", Value::Int(2))]);
        assert!(matches!(to_canonical(&v), Err(CanonError::DuplicateKey(_))));
    }

    /// M6: `i64::MIN.abs()` overflows (panic in debug, wraps to `i64::MIN` in release and slips
    /// under the limit); the magnitude check must reject it on both public entry points.
    #[test]
    fn i64_min_is_not_a_safe_integer() {
        for n in [
            i64::MIN,
            i64::MIN + 1,
            i64::MAX,
            -MAX_SAFE_INT - 1,
            MAX_SAFE_INT + 1,
        ] {
            assert_eq!(to_canonical(&Value::Int(n)), Err(CanonError::UnsafeInteger));
            assert_eq!(
                from_serde(&serde_json::json!(n)),
                Err(CanonError::UnsafeInteger)
            );
        }
        assert_eq!(
            to_canonical(&Value::Int(-MAX_SAFE_INT)).unwrap(),
            b"-9007199254740991"
        );
        assert_eq!(
            parse("-9223372036854775808"),
            Err(CanonError::UnsafeInteger)
        );
    }

    #[test]
    fn serde_conversion() {
        let j = serde_json::json!({"z": 1, "a": [1.5, "x"], "big": 1u64 << 60});
        assert_eq!(from_serde(&j), Err(CanonError::UnsafeInteger));
        let j = serde_json::json!({"z": 1, "a": [1.5, "x"]});
        assert_eq!(
            to_canonical(&from_serde(&j).unwrap()).unwrap(),
            br#"{"a":[1.5,"x"],"z":1}"#
        );
    }
}
