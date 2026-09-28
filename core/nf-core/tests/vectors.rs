//! Conformance with hashing spec v1 (`docs/spec/hashing.md` §7): every case of
//! `spec/test-vectors/canonical-json.json` (bytes + SHA-256), every error case, every row of
//! `numbers.json`, and every ID in `ids.json`. The vector files themselves are read with
//! nf-core's own strict parser.

use nf_core::cjson::{self, Value};
use nf_core::ids::{self, Dtype};
use nf_core::sha256::from_hex;
use nf_core::{sha256, to_hex};

fn load(name: &str) -> Value {
    let path = format!(
        "{}/../../spec/test-vectors/{name}",
        env!("CARGO_MANIFEST_DIR")
    );
    let text = std::fs::read_to_string(&path).expect("read vector file");
    cjson::parse(&text).expect("vector file is strict JSON")
}

fn arr<'a>(v: &'a Value, key: &str) -> &'a [Value] {
    match v.get(key) {
        Some(Value::Array(a)) => a,
        _ => panic!("missing array {key}"),
    }
}

fn s<'a>(v: &'a Value, key: &str) -> &'a str {
    v.get(key)
        .and_then(Value::as_str)
        .unwrap_or_else(|| panic!("missing string {key}"))
}

#[test]
fn canonical_json_cases_and_errors() {
    let doc = load("canonical-json.json");
    let cases = arr(&doc, "cases");
    for c in cases {
        let name = s(c, "name");
        let got = cjson::canonicalize_text(s(c, "input")).unwrap_or_else(|e| panic!("{name}: {e}"));
        assert_eq!(
            std::str::from_utf8(&got).unwrap(),
            s(c, "canonical"),
            "case {name}"
        );
        assert_eq!(to_hex(&sha256(&got)), s(c, "sha256"), "case {name}");
    }
    let errors = arr(&doc, "errors");
    for e in errors {
        assert!(
            cjson::canonicalize_text(s(e, "input")).is_err(),
            "error case {} accepted",
            s(e, "name")
        );
    }
    assert_eq!((cases.len(), errors.len()), (12, 6));
}

#[test]
fn number_table() {
    let doc = load("numbers.json");
    let mut n = 0;
    for c in arr(&doc, "cases") {
        let bits = u64::from_str_radix(s(c, "ieee754"), 16).unwrap();
        let x = f64::from_bits(bits);
        assert_eq!(
            cjson::format_number(x).unwrap(),
            s(c, "canonical"),
            "bits {bits:016x}"
        );
        n += 1;
    }
    for e in arr(&doc, "errors") {
        let bits = u64::from_str_radix(s(e, "ieee754"), 16).unwrap();
        assert!(cjson::format_number(f64::from_bits(bits)).is_err());
        n += 1;
    }
    assert!(n >= 24);
}

fn le_bytes(dtype: Dtype, values: &[Value]) -> Vec<u8> {
    let num = |v: &Value| match v {
        Value::Int(i) => *i as f64,
        Value::Float(f) => *f,
        other => panic!("not a number: {other:?}"),
    };
    let int = |v: &Value| match v {
        Value::Int(i) => *i,
        other => panic!("not an integer: {other:?}"),
    };
    values
        .iter()
        .flat_map(|v| match dtype {
            Dtype::Int8 => (int(v) as i8).to_le_bytes().to_vec(),
            Dtype::Uint8 => (int(v) as u8).to_le_bytes().to_vec(),
            Dtype::Int16 => (int(v) as i16).to_le_bytes().to_vec(),
            Dtype::Uint16 => (int(v) as u16).to_le_bytes().to_vec(),
            Dtype::Int32 => (int(v) as i32).to_le_bytes().to_vec(),
            Dtype::Uint32 => (int(v) as u32).to_le_bytes().to_vec(),
            Dtype::Int64 => int(v).to_le_bytes().to_vec(),
            Dtype::Float32 => (num(v) as f32).to_le_bytes().to_vec(),
            Dtype::Float64 => num(v).to_le_bytes().to_vec(),
        })
        .collect()
}

#[test]
fn every_id_vector() {
    let doc = load("ids.json");
    let mut checked = 0;
    for b in arr(&doc, "blob") {
        assert_eq!(
            ids::blob_id(&from_hex(s(b, "data_hex")).unwrap()),
            s(b, "id")
        );
        checked += 1;
    }
    for p in arr(&doc, "pipeline_version") {
        let spec = p.get("spec").unwrap();
        let payload = ids::pipeline_version_payload(spec).unwrap();
        assert_eq!(
            std::str::from_utf8(&payload).unwrap(),
            s(p, "payload"),
            "{}",
            s(p, "name")
        );
        assert_eq!(
            ids::pipeline_version_id(spec).unwrap(),
            s(p, "id"),
            "{}",
            s(p, "name")
        );
        checked += 1;
    }
    for c in arr(&doc, "chunk") {
        let dtype = Dtype::parse(s(c, "dtype")).unwrap();
        let shape: Vec<u64> = arr(c, "shape")
            .iter()
            .map(|v| match v {
                Value::Int(i) => *i as u64,
                _ => panic!(),
            })
            .collect();
        let data = le_bytes(dtype, arr(c, "values"));
        assert_eq!(to_hex(&data), s(c, "data_hex"), "{}", s(c, "name"));
        assert_eq!(
            to_hex(&ids::chunk_preimage(dtype, &shape, &data).unwrap()),
            s(c, "preimage_hex")
        );
        assert_eq!(
            ids::chunk_id(dtype, &shape, &data).unwrap(),
            s(c, "id"),
            "{}",
            s(c, "name")
        );
        checked += 1;
    }
    let chain = arr(&doc, "prov_batch_chain");
    let batches: Vec<Value> = chain
        .iter()
        .map(|e| e.get("batch").unwrap().clone())
        .collect();
    for e in chain {
        let b = e.get("batch").unwrap();
        assert_eq!(
            std::str::from_utf8(&ids::prov_batch_payload(b).unwrap()).unwrap(),
            s(e, "payload")
        );
        assert_eq!(ids::prov_batch_id(b).unwrap(), s(e, "id"));
        checked += 1;
    }
    let chain_ids = ids::verify_chain(&batches).unwrap();
    assert_eq!(
        chain_ids,
        chain
            .iter()
            .map(|e| s(e, "id").to_owned())
            .collect::<Vec<_>>()
    );
    assert_eq!(checked, 12, "blob 3 + pv 3 + chunk 3 + prov batch 3");
}

#[test]
fn chain_breaks_when_an_earlier_batch_changes() {
    let doc = load("ids.json");
    let mut batches: Vec<Value> = arr(&doc, "prov_batch_chain")
        .iter()
        .map(|e| e.get("batch").unwrap().clone())
        .collect();
    if let Value::Object(m) = &mut batches[0] {
        for (k, v) in m.iter_mut() {
            if k == "created_at" {
                *v = Value::str("2026-09-26T12:00:00.001Z");
            }
        }
    }
    assert!(ids::verify_chain(&batches).is_err());
}

#[test]
fn pv_rules() {
    let mut spec = cjson::parse(
        r#"{"schema":"nf.pipeline-version/v1","meta":{"name":"a"},"steps":[{"image":"x:latest"}],"seed":1}"#,
    )
    .unwrap();
    assert!(ids::pipeline_version_id(&spec).is_err());
    if let Value::Object(m) = &mut spec {
        m[0].1 = Value::str("nf.pipeline-version/v2");
    }
    assert!(ids::pipeline_version_payload(&spec).is_err());
}
