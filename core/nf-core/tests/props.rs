//! Property tests for NF-CJSON canonicalisation (hashing spec §3).

use nf_core::cjson::{self, CanonError, Value};
use proptest::prelude::*;

fn arb_string() -> impl Strategy<Value = String> {
    // mix of ASCII, controls, combining marks and non-BMP characters
    prop::collection::vec(
        prop_oneof![
            4 => any::<char>(),
            2 => prop::sample::select(vec!['a', 'e', '\u{301}', '\u{30a}', '"', '\\', '\n', '\u{1}', '\u{1F600}', '\u{FB33}', '\u{E000}']),
        ],
        0..8,
    )
    .prop_map(|v| v.into_iter().collect())
}

fn arb_value() -> impl Strategy<Value = Value> {
    let leaf = prop_oneof![
        Just(Value::Null),
        any::<bool>().prop_map(Value::Bool),
        (-cjson::MAX_SAFE_INT..=cjson::MAX_SAFE_INT).prop_map(Value::Int),
        any::<f64>()
            .prop_filter("finite", |f| f.is_finite())
            .prop_map(Value::Float),
        arb_string().prop_map(Value::String),
    ];
    leaf.prop_recursive(4, 48, 6, |inner| {
        prop_oneof![
            prop::collection::vec(inner.clone(), 0..6).prop_map(Value::Array),
            prop::collection::vec((arb_string(), inner), 0..6).prop_map(Value::Object),
        ]
    })
}

/// Serialise with arbitrary member order and whitespace (a non-canonical but equal document).
fn noisy(v: &Value, rot: usize, ws: &str) -> String {
    match v {
        Value::Array(a) => format!(
            "[{ws}{}{ws}]",
            a.iter()
                .map(|x| noisy(x, rot, ws))
                .collect::<Vec<_>>()
                .join(&format!("{ws},{ws}"))
        ),
        Value::Object(m) => {
            let mut members: Vec<String> = m
                .iter()
                .map(|(k, x)| format!("{}{ws}:{ws}{}", json_str(k), noisy(x, rot, ws)))
                .collect();
            if !members.is_empty() {
                let r = rot % members.len();
                members.rotate_left(r);
            }
            format!("{{{ws}{}{ws}}}", members.join(","))
        }
        Value::String(s) => json_str(s),
        Value::Float(f) => format!("{f:e}"),
        other => String::from_utf8(cjson::to_canonical(other).unwrap()).unwrap(),
    }
}

/// Escape every non-ASCII character as \u (surrogate pairs), the opposite of canonical form.
fn json_str(s: &str) -> String {
    let mut o = String::from("\"");
    for c in s.chars() {
        match c {
            '"' => o.push_str("\\\""),
            '\\' => o.push_str("\\\\"),
            c if (c as u32) < 0x20 || !c.is_ascii() => {
                let mut buf = [0u16; 2];
                for u in c.encode_utf16(&mut buf) {
                    o.push_str(&format!("\\u{u:04X}"));
                }
            }
            c => o.push(c),
        }
    }
    o.push('"');
    o
}

/// Found by `canonical_is_a_fixed_point`: RFC 8785 prints 2^53 (a double) as `9007199254740992`
/// (also a row of numbers.json), but hashing spec §3.1 rejects that literal on input. So the
/// canonical text of such a value is valid output but not valid NF-CJSON input. The Python
/// reference behaves the same (`json.loads` yields an int, `format_number` refuses it). Reported
/// for spec v2; the behaviour is pinned here so a change is deliberate.
#[test]
fn integral_doubles_beyond_2_53() {
    let v = Value::Array(vec![Value::Float(9007199254740992.0)]);
    let c = cjson::to_canonical(&v).unwrap();
    assert_eq!(c, b"[9007199254740992]");
    assert_eq!(
        cjson::parse("[9007199254740992]"),
        Err(CanonError::UnsafeInteger)
    );
    assert_eq!(cjson::canonicalize_text("[9007199254740992.0]").unwrap(), c);
}

proptest! {
    #![proptest_config(ProptestConfig { cases: 512, ..ProptestConfig::default() })]

    #[test]
    fn canonical_is_a_fixed_point(v in arb_value()) {
        let Ok(c) = cjson::to_canonical(&v) else {
            // only NFC key collisions may fail for generated values
            prop_assert!(matches!(cjson::to_canonical(&v), Err(CanonError::DuplicateKey(_))));
            return Ok(());
        };
        let text = std::str::from_utf8(&c).unwrap();
        match cjson::canonicalize_text(text) {
            Ok(again) => prop_assert_eq!(again, c),
            // Spec quirk (see `integral_doubles_beyond_2_53` below): an integral double in
            // [2^53, 1e21) prints as a plain integer that §3.1 then refuses to parse.
            Err(CanonError::UnsafeInteger) => {}
            Err(e) => prop_assert!(false, "{e}"),
        }
    }

    #[test]
    fn order_whitespace_and_escaping_do_not_matter(v in arb_value(), rot in 0usize..7, ws in prop::sample::select(vec!["", " ", "\n\t ", "\r\n"])) {
        let Ok(c) = cjson::to_canonical(&v) else { return Ok(()); };
        let parsed = cjson::parse(&noisy(&v, rot, ws));
        // duplicate keys that only differ before NFC are rejected by the parser, as specified
        let Ok(parsed) = parsed else { return Ok(()); };
        prop_assert_eq!(cjson::to_canonical(&parsed).unwrap(), c);
    }

    #[test]
    fn numbers_round_trip(x in any::<f64>().prop_filter("finite", |f| f.is_finite())) {
        let s = cjson::format_number(x).unwrap();
        let back: f64 = s.parse().unwrap();
        prop_assert!(back == x, "{} -> {} -> {}", x, s, back); // -0 == 0
        prop_assert!(!s.contains('+') || s.contains("e+"));
        prop_assert!(!s.ends_with(".0"));
    }

    #[test]
    fn safe_integers_print_plainly(i in -cjson::MAX_SAFE_INT..=cjson::MAX_SAFE_INT) {
        prop_assert_eq!(cjson::format_number(i as f64).unwrap(), i.to_string());
    }

    #[test]
    fn parser_never_panics(bytes in prop::collection::vec(any::<u8>(), 0..64)) {
        if let Ok(text) = std::str::from_utf8(&bytes) {
            let _ = cjson::parse(text);
        }
    }
}

/// Hostile but structurally valid dimensions: zero, tiny, huge, overflowing.
fn arb_dim() -> impl Strategy<Value = u64> {
    prop_oneof![
        3 => 0u64..8,
        2 => prop::sample::select(vec![300u64, 4096, 1 << 20, 1 << 32, 1 << 40, 100_000_000_000, u64::MAX / 2, u64::MAX]),
        1 => any::<u64>(),
    ]
}

/// A `zarr.json` that parses as JSON and has every field the reader expects, with bad ranks
/// (0..6, shape and chunk ranks may differ) and huge dims, so the shape/size code is reached.
fn arb_zarr_meta() -> impl Strategy<Value = (Vec<u64>, Vec<u64>, String)> {
    (
        prop::collection::vec(arb_dim(), 0..6),
        prop::collection::vec(arb_dim(), 0..6),
        prop::sample::select(vec![
            "int8", "uint8", "int16", "uint16", "int32", "uint32", "int64", "float32", "float64",
            "bool", "",
        ]),
    )
        .prop_map(|(shape, chunk, dtype)| {
            let j = serde_json::json!({
                "zarr_format": 3,
                "node_type": "array",
                "shape": shape,
                "data_type": dtype,
                "chunk_grid": {"name": "regular", "configuration": {"chunk_shape": chunk}},
                "chunk_key_encoding": {"name": "default", "configuration": {"separator": "/"}},
                "fill_value": 0,
                "codecs": [{"name": "bytes", "configuration": {"endian": "little"}}],
            });
            (shape, chunk, j.to_string())
        })
}

proptest! {
    #![proptest_config(ProptestConfig { cases: 256, ..ProptestConfig::default() })]

    /// SEC-062 (short, local): Zarr metadata parsing never panics on hostile bytes.
    #[test]
    fn zarr_meta_parser_never_panics(bytes in prop::collection::vec(any::<u8>(), 0..256)) {
        let _ = nf_core::zarr::ArrayMeta::from_json(&bytes);
    }

    /// H5/H6: valid-looking metadata with bad ranks and huge dims is rejected or bounded; reading
    /// a region or a signal from it returns an error or a correctly sized buffer, never panics.
    #[test]
    fn zarr_hostile_metadata_never_panics((shape, chunk, text) in arb_zarr_meta()) {
        use nf_core::zarr::{self, MemStore, Store, MAX_CHUNK_BYTES};
        let Ok(meta) = zarr::ArrayMeta::from_json(text.as_bytes()) else { return Ok(()); };
        prop_assert_eq!(&meta.shape, &shape);
        prop_assert_eq!(&meta.chunk_shape, &chunk);
        prop_assert_eq!(shape.len(), chunk.len());
        let item = meta.dtype.itemsize() as u64;
        let chunk_bytes = chunk.iter().try_fold(item, |a, &d| a.checked_mul(d));
        prop_assert!(chunk_bytes.is_some_and(|b| b <= MAX_CHUNK_BYTES), "accepted chunk {:?}", chunk);
        prop_assert!(shape.iter().try_fold(item, |a, &d| a.checked_mul(d)).is_some());
        // keep the test cheap on RAM: region/fill reads only for chunks up to 1 MiB
        if chunk_bytes.unwrap() > 1 << 20 {
            return Ok(());
        }
        let mut s = MemStore::default();
        s.set("r/data/0/zarr.json", text.as_bytes()).unwrap();
        let stop: Vec<u64> = shape.iter().map(|d| (*d).min(16)).collect();
        let start = vec![0u64; shape.len()];
        if let Ok(buf) = zarr::read_region(&s, "r/data/0", &meta, &start, &stop) {
            let want = stop.iter().product::<u64>() * item;
            prop_assert_eq!(buf.len() as u64, want);
        }
        if let Ok((m, _)) = zarr::read_signal(&s, "r", 0, 16) {
            prop_assert_eq!(m.shape.len(), 2);
        }
    }

    /// M6: every integer outside +-(2^53-1), including i64::MIN, is rejected on both entry points.
    #[test]
    fn unsafe_integers_are_rejected(n in prop_oneof![
        Just(i64::MIN), Just(i64::MAX), Just(i64::MIN + 1),
        (cjson::MAX_SAFE_INT + 1)..=i64::MAX,
        i64::MIN..=(-cjson::MAX_SAFE_INT - 1),
    ]) {
        prop_assert_eq!(cjson::to_canonical(&Value::Int(n)), Err(CanonError::UnsafeInteger));
        prop_assert_eq!(cjson::from_serde(&serde_json::json!(n)), Err(CanonError::UnsafeInteger));
    }
}
