//! Conformance with hashing spec v2 (`docs/spec/hashing.md` §12): every case of
//! `spec/test-vectors/ids-v2.json` is recomputed from its inputs (IDs, bare digests, labels and
//! every preimage / payload / body / signed part / AAD). With the `stream` feature every
//! signature is also verified with the listed test public key and reproduced with the RFC 8032
//! test secret (Ed25519 is deterministic), and tampered inputs must fail.
//!
//! The property tests check the §9.3 / §9.7 set rules: permuting, duplicating or upper-casing
//! manifest inputs, and permuting or duplicating consent scopes, never changes the digest.

use std::collections::BTreeMap;

use nf_core::cjson::{self, Value};
use nf_core::ids::{self, Dtype};
use nf_core::ids_v2::{self as v2, StreamChunkFields, TrainingManifestArgs};
use nf_core::sha256::{from_hex, to_hex};
use proptest::prelude::*;

fn load(name: &str) -> Value {
    let path = format!(
        "{}/../../spec/test-vectors/{name}",
        env!("CARGO_MANIFEST_DIR")
    );
    let text = std::fs::read_to_string(&path).expect("read vector file");
    cjson::parse(&text).expect("vector file is strict JSON")
}

fn v2doc() -> Value {
    load("ids-v2.json")
}

fn get<'a>(v: &'a Value, key: &str) -> &'a Value {
    v.get(key).unwrap_or_else(|| panic!("missing member {key}"))
}

fn arr<'a>(v: &'a Value, key: &str) -> &'a [Value] {
    match get(v, key) {
        Value::Array(a) => a,
        _ => panic!("{key} is not an array"),
    }
}

fn s<'a>(v: &'a Value, key: &str) -> &'a str {
    get(v, key)
        .as_str()
        .unwrap_or_else(|| panic!("{key} is not a string"))
}

fn opt_s<'a>(v: &'a Value, key: &str) -> Option<&'a str> {
    match get(v, key) {
        Value::Null => None,
        Value::String(x) => Some(x),
        _ => panic!("{key} is neither null nor a string"),
    }
}

fn int(v: &Value, key: &str) -> i64 {
    match get(v, key) {
        Value::Int(n) => *n,
        _ => panic!("{key} is not an integer"),
    }
}

fn num(v: &Value) -> f64 {
    match v {
        Value::Int(n) => *n as f64,
        Value::Float(f) => *f,
        _ => panic!("not a number"),
    }
}

fn strings(v: &Value, key: &str) -> Vec<String> {
    arr(v, key)
        .iter()
        .map(|x| x.as_str().expect("string item").to_owned())
        .collect()
}

fn text(b: &[u8]) -> &str {
    std::str::from_utf8(b).expect("utf-8")
}

fn with_member(v: &Value, key: &str, new: Value) -> Value {
    match v {
        Value::Object(m) => Value::Object(
            m.iter()
                .map(|(k, x)| (k.clone(), if k == key { new.clone() } else { x.clone() }))
                .collect(),
        ),
        _ => panic!("not an object"),
    }
}

fn manifest_args(a: &Value) -> TrainingManifestArgs {
    let shards = match get(a, "shards") {
        Value::Null => None,
        Value::Object(m) => Some(
            m.iter()
                .map(|(k, x)| match x {
                    Value::Int(n) => (k.clone(), *n),
                    _ => panic!("shard value is not an integer"),
                })
                .collect::<BTreeMap<String, i64>>(),
        ),
        _ => panic!("shards is neither null nor an object"),
    };
    TrainingManifestArgs {
        tenant_id: s(a, "tenant_id").to_owned(),
        input_node_ids: strings(a, "input_node_ids"),
        subject_hashes: strings(a, "subject_hashes"),
        n_source_recordings: int(a, "n_source_recordings"),
        shards,
        excluded_subject_hashes: strings(a, "excluded_subject_hashes"),
        pipeline_version_ids: strings(a, "pipeline_version_ids"),
        code_commit: s(a, "code_commit").to_owned(),
        recipe: opt_s(a, "recipe").map(str::to_owned),
        parent_version_id: opt_s(a, "parent_version_id").map(str::to_owned),
        // §9.7 amendment: absent in the frozen cases, present in the weights-source-* cases
        weights_source: a
            .get("weights_source")
            .and_then(|_| opt_s(a, "weights_source"))
            .map(str::to_owned),
    }
}

fn pairs(v: &Value, key: &str) -> Vec<(f64, f64)> {
    arr(v, key)
        .iter()
        .map(|p| match p {
            Value::Array(x) if x.len() == 2 => (num(&x[0]), num(&x[1])),
            _ => panic!("{key}: not a pair"),
        })
        .collect()
}

// ---------------------------------------------------------------- hashes (§9)
#[test]
fn audit_batch_chain() {
    let doc = v2doc();
    let cases = arr(&doc, "audit_batch_chain");
    assert_eq!(cases.len(), 2);
    let mut batches = Vec::new();
    for (i, c) in cases.iter().enumerate() {
        let b = get(c, "batch");
        assert_eq!(
            text(&v2::audit_batch_payload(b).unwrap()),
            s(c, "payload"),
            "batch {i}"
        );
        assert_eq!(v2::audit_batch_id(b).unwrap(), s(c, "id"), "batch {i}");
        assert!(v2::parse_id_v2(s(c, "id")).is_ok());
        batches.push(b.clone());
    }
    let ids: Vec<String> = cases.iter().map(|c| s(c, "id").to_owned()).collect();
    assert_eq!(v2::verify_audit_chain(&batches).unwrap(), ids);
    // negative: a modified first batch breaks the link from the second
    let mut tampered = batches.clone();
    tampered[0] = with_member(&tampered[0], "scope", Value::str("_platform"));
    assert!(v2::verify_audit_chain(&tampered).is_err());
    // negative: wrong prev kind
    let wrong = with_member(
        &batches[1],
        "prev",
        Value::str(ids[0].replace("auditb", "provb")),
    );
    assert!(v2::audit_batch_id(&wrong).is_err());
}

#[test]
fn prov_node_hashes() {
    let doc = v2doc();
    let cases = arr(&doc, "prov_node");
    assert_eq!(cases.len(), 3);
    for c in cases {
        let name = s(c, "name");
        let a = get(c, "args");
        let attrs = get(a, "attrs");
        let built = v2::prov_node_record(
            s(a, "node_id"),
            s(a, "kind"),
            s(a, "type"),
            opt_s(a, "ref"),
            opt_s(a, "content"),
            Some(attrs),
        );
        assert_eq!(&built, get(c, "record"), "{name}");
        assert_eq!(
            text(&cjson::to_canonical(&built).unwrap()),
            s(c, "payload"),
            "{name}"
        );
        assert_eq!(v2::prov_node_hash(&built).unwrap(), s(c, "hash"), "{name}");
        assert_eq!(
            v2::prov_node_hash(get(c, "record")).unwrap(),
            s(c, "hash"),
            "{name}"
        );
    }
}

#[test]
fn consent_record_chain() {
    let doc = v2doc();
    let cases = arr(&doc, "consent_record_chain");
    assert_eq!(cases.len(), 2);
    let mut records = Vec::new();
    for (i, c) in cases.iter().enumerate() {
        let r = get(c, "record");
        assert_eq!(
            text(&v2::consent_record_payload(r).unwrap()),
            s(c, "payload"),
            "record {i}"
        );
        assert_eq!(
            v2::consent_record_hash(r).unwrap(),
            s(c, "hash"),
            "record {i}"
        );
        records.push(r.clone());
    }
    let hashes: Vec<String> = cases.iter().map(|c| s(c, "hash").to_owned()).collect();
    assert_eq!(v2::verify_consent_chain(&records).unwrap(), hashes);
    let mut tampered = records.clone();
    tampered[0] = with_member(&tampered[0], "kind", Value::str("withdraw"));
    assert!(v2::verify_consent_chain(&tampered).is_err());
}

#[test]
fn consent_record_noncanonical_scopes() {
    let doc = v2doc();
    let c = get(&doc, "consent_record_noncanonical_scopes");
    let r = get(c, "record");
    let canon = v2::canonical_consent_record(r).unwrap();
    assert_eq!(text(&cjson::to_canonical(&canon).unwrap()), s(c, "payload"));
    assert_eq!(v2::consent_record_hash(r).unwrap(), s(c, "hash"));
    // = consent_record_chain[0]
    let chain0 = &arr(&doc, "consent_record_chain")[0];
    assert_eq!(s(c, "hash"), s(chain0, "hash"));
    assert_eq!(&canon, get(chain0, "record"));
}

#[test]
fn ruleset_hash() {
    let doc = v2doc();
    let c = get(&doc, "ruleset");
    let rules = get(c, "rules");
    assert_eq!(text(&cjson::to_canonical(rules).unwrap()), s(c, "payload"));
    assert_eq!(
        v2::ruleset_content_sha256(rules).unwrap(),
        s(c, "content_sha256")
    );
    // negative: rule order is part of the hash (manifest order)
    let Value::Array(mut rev) = rules.clone() else {
        panic!("rules is not an array")
    };
    rev.reverse();
    assert_ne!(
        v2::ruleset_content_sha256(&Value::Array(rev)).unwrap(),
        s(c, "content_sha256")
    );
}

#[test]
fn sweep_variant_labels() {
    let doc = v2doc();
    let cases = arr(&doc, "sweep_variant");
    assert_eq!(cases.len(), 3);
    for c in cases {
        let name = s(c, "name");
        let (base, params) = (s(c, "base"), get(c, "params"));
        assert_eq!(
            text(&v2::sweep_variant_payload(base, params).unwrap()),
            s(c, "payload"),
            "{name}"
        );
        assert_eq!(
            v2::sweep_variant_label(base, params).unwrap(),
            s(c, "label"),
            "{name}"
        );
    }
    assert!(v2::sweep_variant_label("pv:sha256:xyz", &Value::Object(vec![])).is_err());
}

#[test]
fn training_subject_hashes() {
    let doc = v2doc();
    let cases = arr(&doc, "training_subject");
    assert_eq!(cases.len(), 4);
    for c in cases {
        let (t, sub) = (s(c, "tenant_id"), s(c, "subject_id"));
        assert_eq!(
            to_hex(&v2::training_subject_preimage(t, sub).unwrap()),
            s(c, "preimage_hex"),
            "{t}/{sub}"
        );
        assert_eq!(
            v2::training_subject_hash(t, sub).unwrap(),
            s(c, "hash"),
            "{t}/{sub}"
        );
    }
}

#[test]
fn training_manifests() {
    let doc = v2doc();
    let cases = arr(&doc, "training_manifest");
    assert_eq!(cases.len(), 5);
    for c in cases {
        let name = s(c, "name");
        let built = v2::training_manifest(&manifest_args(get(c, "args"))).unwrap();
        assert_eq!(&built, get(c, "manifest"), "{name}");
        assert_eq!(
            text(&cjson::to_canonical(&built).unwrap()),
            s(c, "payload"),
            "{name}"
        );
        assert_eq!(
            v2::training_manifest_digest(&built).unwrap(),
            s(c, "digest"),
            "{name}"
        );
        assert_eq!(
            v2::training_manifest_digest(get(c, "manifest")).unwrap(),
            s(c, "digest"),
            "{name}"
        );
    }
    // §9.7: duplicate and upper-case inputs give the same digest as the plain case
    let by_name = |n: &str| {
        cases
            .iter()
            .find(|c| s(c, "name") == n)
            .unwrap_or_else(|| panic!("case {n}"))
    };
    assert_eq!(
        s(by_name("duplicate-inputs"), "digest"),
        s(by_name("plain"), "digest")
    );
    let wrong_schema = with_member(get(by_name("plain"), "manifest"), "schema", Value::str("x"));
    assert!(v2::training_manifest_digest(&wrong_schema).is_err());
    // §9.7 amendment (AppSec M3): weights_source is a hashed member when present, absent before
    for n in ["weights-source-upload", "weights-source-platform"] {
        let m = get(by_name(n), "manifest");
        assert!(m.get("weights_source").is_some(), "{n}");
        assert_ne!(
            s(by_name(n), "digest"),
            s(by_name("plain"), "digest"),
            "{n}"
        );
    }
    assert!(
        get(by_name("plain"), "manifest")
            .get("weights_source")
            .is_none()
    );
    let mut bad = manifest_args(get(by_name("weights-source-upload"), "args"));
    bad.weights_source = Some("laptop".into());
    assert!(v2::training_manifest(&bad).is_err());
}

// ---------------------------------------------------------------- signed bytes (§10)
/// (timestamps, clock-offset pairs, local-clock pairs)
type Timing = (Vec<f64>, Vec<(f64, f64)>, Vec<(f64, f64)>);

fn chunk_fields_parts(ch: &Value) -> Timing {
    let ts = arr(ch, "lsl_timestamps").iter().map(num).collect();
    (ts, pairs(ch, "clock_offsets"), pairs(ch, "local_clock"))
}

fn chunk_fields<'a>(ch: &'a Value, parts: &'a Timing) -> StreamChunkFields<'a> {
    StreamChunkFields {
        stream_id: s(ch, "stream_id"),
        seq: u64::try_from(int(ch, "seq")).unwrap(),
        n_samples: u32::try_from(int(ch, "n_samples")).unwrap(),
        n_channels: u32::try_from(int(ch, "n_channels")).unwrap(),
        chunk_id: s(ch, "chunk_id"),
        lsl_timestamps: &parts.0,
        clock_offsets: &parts.1,
        local_clock: &parts.2,
    }
}

#[test]
fn stream_chunk_bytes() {
    let doc = v2doc();
    let c = get(&doc, "stream_chunk_signature");
    let ch = get(c, "chunk");
    // chunk_id is the v1 §5.2 ID of the float32 samples, shape [n_samples, n_channels]
    let data: Vec<u8> = arr(ch, "samples")
        .iter()
        .flat_map(|x| (num(x) as f32).to_le_bytes())
        .collect();
    let shape = [int(ch, "n_samples") as u64, int(ch, "n_channels") as u64];
    assert_eq!(s(ch, "dtype"), "float32");
    assert_eq!(
        ids::chunk_id(Dtype::Float32, &shape, &data).unwrap(),
        s(ch, "chunk_id")
    );
    let parts = chunk_fields_parts(ch);
    let f = chunk_fields(ch, &parts);
    assert_eq!(
        v2::timing_sha256(&parts.0, &parts.1, &parts.2),
        s(c, "timing_sha256")
    );
    assert_eq!(
        text(&cjson::to_canonical(&v2::stream_chunk_body(&f).unwrap()).unwrap()),
        s(c, "body")
    );
    assert_eq!(
        to_hex(&v2::stream_chunk_preimage(&f).unwrap()),
        s(c, "preimage_hex")
    );
}

#[test]
fn device_token_bytes() {
    let doc = v2doc();
    let c = get(&doc, "device_token");
    let claims = get(c, "claims");
    assert_eq!(
        text(&v2::device_token_payload(claims).unwrap()),
        s(c, "payload")
    );
    assert_eq!(
        to_hex(&v2::device_token_preimage(claims).unwrap()),
        s(c, "preimage_hex")
    );
    let p = v2::parse_device_token(s(c, "token")).unwrap();
    assert_eq!(&p.claims, claims);
    assert_eq!(text(&p.payload), s(c, "payload"));
    assert_eq!(to_hex(&p.signature), s(c, "signature_hex"));
    let rebuilt = format!(
        "{}.{}.{}",
        v2::DEVICE_TOKEN_PREFIX,
        nf_core::b64::encode_url(&p.payload),
        nf_core::b64::encode_url(&p.signature)
    );
    assert_eq!(rebuilt, s(c, "token"));
    // negatives: wrong audience, non-canonical payload, wrong prefix
    let bad_aud = with_member(claims, "aud", Value::str("other"));
    assert!(v2::device_token_payload(&bad_aud).is_err());
    let noncanon = format!(
        "nfd1.{}.{}",
        nf_core::b64::encode_url(b"{ \"aud\":\"nf-ingest/v1\"}"),
        nf_core::b64::encode_url(&p.signature)
    );
    assert!(v2::parse_device_token(&noncanon).is_err());
    assert!(v2::parse_device_token(&s(c, "token").replacen("nfd1", "nfd2", 1)).is_err());
}

#[test]
fn provb_anchor_certificate_bytes() {
    let doc = v2doc();
    let pb = get(&doc, "provb_signature");
    assert_eq!(
        to_hex(&v2::provb_signature_message(s(pb, "batch_id")).unwrap()),
        s(pb, "message_hex")
    );
    // the batch is the frozen v1 vector prov_batch_chain[0]
    let v1 = load("ids.json");
    let batch0 = &arr(&v1, "prov_batch_chain")[0];
    assert_eq!(s(batch0, "id"), s(pb, "batch_id"));
    for key in ["prov_anchor", "consent_anchor"] {
        let a = get(&doc, key);
        assert_eq!(
            text(&v2::anchor_signed_part(get(a, "document")).unwrap()),
            s(a, "signed_part"),
            "{key}"
        );
    }
    let prov_head = s(get(get(&doc, "prov_anchor"), "document"), "head");
    assert_eq!(prov_head, s(pb, "batch_id"));
    let consent_head = s(get(get(&doc, "consent_anchor"), "document"), "head");
    assert_eq!(
        consent_head,
        s(&arr(&doc, "consent_record_chain")[1], "hash")
    );
    let cert = get(&doc, "deletion_certificate");
    assert_eq!(
        text(&v2::certificate_signed_part(get(cert, "document")).unwrap()),
        s(cert, "signed_part")
    );
    assert!(v2::anchor_signed_part(get(cert, "document")).is_err());
}

#[test]
fn wal_aad_bytes() {
    let doc = v2doc();
    let cases = arr(&doc, "wal_aad");
    assert_eq!(cases.len(), 2);
    for c in cases {
        let seq = u64::try_from(int(c, "seq")).unwrap();
        assert_eq!(
            to_hex(&v2::wal_aad(s(c, "stream_id"), seq)),
            s(c, "aad_hex")
        );
    }
}

// ---------------------------------------------------------------- Ed25519 (stream feature)
#[cfg(feature = "stream")]
mod signatures {
    use super::*;
    use nf_core::stream::sign::DeviceKey;

    fn keys(doc: &Value) -> (DeviceKey, [u8; 32]) {
        let k = get(doc, "test_key");
        let key = DeviceKey::from_seed(&from_hex(s(k, "secret_hex")).unwrap()).unwrap();
        let public: [u8; 32] = from_hex(s(k, "public_hex")).unwrap().try_into().unwrap();
        assert_eq!(
            key.public_key(),
            public,
            "public key from the RFC 8032 secret"
        );
        (key, public)
    }

    fn flip(mut b: Vec<u8>) -> Vec<u8> {
        b[0] ^= 1;
        b
    }

    #[test]
    fn stream_chunk_signature() {
        let doc = v2doc();
        let (key, pk) = keys(&doc);
        let c = get(&doc, "stream_chunk_signature");
        let ch = get(c, "chunk");
        let parts = chunk_fields_parts(ch);
        let f = chunk_fields(ch, &parts);
        let sig = from_hex(s(c, "signature_hex")).unwrap();
        assert!(v2::verify_stream_chunk(&f, &sig, &pk));
        assert_eq!(
            to_hex(&key.sign(&v2::stream_chunk_preimage(&f).unwrap())),
            s(c, "signature_hex")
        );
        assert!(!v2::verify_stream_chunk(&f, &flip(sig.clone()), &pk));
        let other = StreamChunkFields {
            seq: f.seq + 1,
            ..f
        };
        assert!(!v2::verify_stream_chunk(&other, &sig, &pk));
    }

    #[test]
    fn device_token_signature() {
        let doc = v2doc();
        let (key, pk) = keys(&doc);
        let c = get(&doc, "device_token");
        let claims = get(c, "claims");
        let pre = v2::device_token_preimage(claims).unwrap();
        assert_eq!(to_hex(&key.sign(&pre)), s(c, "signature_hex"));
        let iat = int(claims, "iat");
        let token = s(c, "token");
        assert_eq!(&v2::verify_device_token(token, &pk, iat).unwrap(), claims);
        // the SDK's own token builder produces the same token for the same claims and time
        let built = nf_core::stream::sign::make_device_token(
            &key,
            s(claims, "tenant_id"),
            s(claims, "device_id"),
            s(claims, "stream_id"),
            u64::try_from(int(claims, "exp") - iat).unwrap(),
            u64::try_from(iat).unwrap(),
        )
        .unwrap();
        assert_eq!(built, token);
        // negatives: expired, not yet valid, tampered signature
        assert!(v2::verify_device_token(token, &pk, int(claims, "exp") + 31).is_err());
        assert!(v2::verify_device_token(token, &pk, iat - 31).is_err());
        let p = v2::parse_device_token(token).unwrap();
        let bad = format!(
            "nfd1.{}.{}",
            nf_core::b64::encode_url(&p.payload),
            nf_core::b64::encode_url(&flip(p.signature))
        );
        assert!(v2::verify_device_token(&bad, &pk, iat).is_err());
    }

    #[test]
    fn provb_signature() {
        let doc = v2doc();
        let (key, pk) = keys(&doc);
        let c = get(&doc, "provb_signature");
        let id = s(c, "batch_id");
        let sig = from_hex(s(c, "signature_hex")).unwrap();
        assert!(v2::verify_provb_signature(id, &sig, &pk));
        assert_eq!(to_hex(&key.sign(id.as_bytes())), s(c, "signature_hex"));
        assert!(!v2::verify_provb_signature(id, &flip(sig.clone()), &pk));
        let other = format!("provb:sha256:{}", "0".repeat(64));
        assert!(!v2::verify_provb_signature(&other, &sig, &pk));
    }

    #[test]
    fn anchor_signatures() {
        let doc = v2doc();
        let (key, pk) = keys(&doc);
        for k in ["prov_anchor", "consent_anchor"] {
            let a = get(get(&doc, k), "document");
            assert!(v2::verify_anchor(a, &pk), "{k}");
            let part = v2::anchor_signed_part(a).unwrap();
            assert_eq!(to_hex(&key.sign(&part)), s(a, "sig"), "{k}");
            let tampered = with_member(a, "seq", Value::Int(int(a, "seq") + 1));
            assert!(!v2::verify_anchor(&tampered, &pk), "{k}");
        }
    }

    #[test]
    fn deletion_certificate_signature() {
        let doc = v2doc();
        let (key, pk) = keys(&doc);
        let cert = get(get(&doc, "deletion_certificate"), "document");
        assert!(v2::verify_certificate(cert, &pk));
        let part = v2::certificate_signed_part(cert).unwrap();
        assert_eq!(
            nf_core::b64::encode_std(&key.sign(&part)),
            s(get(cert, "signature"), "value")
        );
        let tampered = with_member(cert, "subject_pseudonym", Value::str("P-018"));
        assert!(!v2::verify_certificate(&tampered, &pk));
    }
}

// ---------------------------------------------------------------- set rules (§9.3, §9.7)
fn plain_manifest() -> (TrainingManifestArgs, String) {
    let doc = v2doc();
    let c = arr(&doc, "training_manifest")
        .iter()
        .find(|c| s(c, "name") == "plain")
        .expect("plain case")
        .clone();
    (manifest_args(get(&c, "args")), s(&c, "digest").to_owned())
}

fn consent0() -> (Value, String) {
    let doc = v2doc();
    let c = arr(&doc, "consent_record_chain")[0].clone();
    (get(&c, "record").clone(), s(&c, "hash").to_owned())
}

/// A permutation of `items` with extra copies (some upper-cased when `upper` is set).
fn scramble(items: &[String], picks: &[usize], upper: &[bool], rot: usize) -> Vec<String> {
    let mut out: Vec<String> = items.to_vec();
    for (i, p) in picks.iter().enumerate() {
        let x = &items[p % items.len()];
        let up = upper.get(i).copied().unwrap_or(false);
        out.push(if up {
            x.to_ascii_uppercase()
        } else {
            x.clone()
        });
    }
    let n = out.len();
    out.rotate_left(rot % n);
    if rot % 2 == 1 {
        out.reverse();
    }
    out
}

proptest! {
    #![proptest_config(ProptestConfig::with_cases(64))]

    #[test]
    fn manifest_inputs_are_a_set(
        picks in prop::collection::vec(0usize..8, 0..6),
        upper in prop::collection::vec(any::<bool>(), 0..6),
        rot in 0usize..16,
    ) {
        let (args, digest) = plain_manifest();
        let inputs = scramble(&args.input_node_ids, &picks, &upper, rot);
        let subjects = scramble(&args.subject_hashes, &picks, &[], rot + 1);
        let a = TrainingManifestArgs { input_node_ids: inputs, subject_hashes: subjects, ..args };
        let doc = v2::training_manifest(&a).unwrap();
        prop_assert_eq!(v2::training_manifest_digest(&doc).unwrap(), digest);
    }

    #[test]
    fn consent_scopes_are_a_set(
        picks in prop::collection::vec(0usize..8, 0..6),
        rot in 0usize..16,
    ) {
        let (rec, hash) = consent0();
        let scopes = strings(&rec, "scopes");
        let scrambled = scramble(&scopes, &picks, &[], rot);
        let r = with_member(&rec, "scopes", Value::Array(scrambled.into_iter().map(Value::String).collect()));
        prop_assert_eq!(v2::consent_record_hash(&r).unwrap(), hash);
    }
}
