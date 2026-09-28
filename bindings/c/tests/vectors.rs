//! Hashing spec conformance through the C ABI: every ID, hash and verification of
//! `spec/test-vectors/{canonical-json,numbers,ids,ids-v2}.json` is recomputed by calling the
//! exported `extern "C"` functions exactly as a C caller would.
//!
//! `tests/c/vectors.h` (the C test's copy of the same vectors) is generated here from the vector
//! files; `c_vectors_header_is_current` fails when it is stale. Regenerate with
//! `NF_UPDATE_C_VECTORS=1 cargo test -p neuroforge-c --test vectors`.

mod common;

use common::*;
use neuroforge::hashing::*;
use neuroforge::*;
use nf_core::cjson::Value;

fn pk(doc: &Value) -> [u8; 32] {
    hex(s(get(doc, "test_key"), "public_hex"))
        .try_into()
        .unwrap()
}

// ---------------------------------------------------------------- v1
#[test]
fn canonical_json_and_numbers() {
    let doc = load("canonical-json.json");
    for case in arr(&doc, "cases") {
        let input = s(case, "input").as_bytes();
        let got = text_out(|o| unsafe { nf_canonicalize(input.as_ptr(), input.len(), o) });
        assert_eq!(got, s(case, "canonical"), "{}", s(case, "name"));
    }
    for e in arr(&doc, "errors") {
        let input = s(e, "input").as_bytes();
        let st = status_of(|o| unsafe { nf_canonicalize(input.as_ptr(), input.len(), o) });
        assert_eq!(st, NF_ERR_CANONICAL, "error case {}", s(e, "name"));
        assert!(!last_error().is_empty());
    }
    let nums = load("numbers.json");
    for case in arr(&nums, "cases") {
        let x = f64::from_bits(u64::from_str_radix(s(case, "ieee754"), 16).unwrap());
        assert_eq!(
            text_out(|o| unsafe { nf_format_number(x, o) }),
            s(case, "canonical")
        );
    }
    for e in arr(&nums, "errors") {
        let x = f64::from_bits(u64::from_str_radix(s(e, "ieee754"), 16).unwrap());
        assert_eq!(
            status_of(|o| unsafe { nf_format_number(x, o) }),
            NF_ERR_CANONICAL
        );
    }
}

#[test]
fn ids_v1() {
    let doc = load("ids.json");
    for b in arr(&doc, "blob") {
        let d = hex(s(b, "data_hex"));
        let id = text_out(|o| unsafe { nf_blob_id(d.as_ptr(), d.len(), o) });
        assert_eq!(id, s(b, "id"));
        assert!(unsafe { nf_is_valid_id(cp(&c(&id))) });
    }
    for p in arr(&doc, "pipeline_version") {
        let spec = json(get(p, "spec"));
        let id = text_out(|o| unsafe { nf_pipeline_version_id(spec.as_ptr(), spec.len(), o) });
        assert_eq!(id, s(p, "id"), "{}", s(p, "name"));
    }
    for ch in arr(&doc, "chunk") {
        let mut dt = 0;
        assert_eq!(
            unsafe { nf_dtype_parse(cp(&c(s(ch, "dtype"))), &mut dt) },
            NF_OK
        );
        let shape: Vec<u64> = arr(ch, "shape").iter().map(|v| num(v) as u64).collect();
        let data = hex(s(ch, "data_hex"));
        let id = text_out(|o| unsafe {
            nf_chunk_id(
                dt,
                shape.as_ptr(),
                shape.len(),
                data.as_ptr(),
                data.len(),
                o,
            )
        });
        assert_eq!(id, s(ch, "id"), "{}", s(ch, "name"));
    }
    let chain = arr(&doc, "prov_batch_chain");
    for e in chain {
        let b = json(get(e, "batch"));
        let id = text_out(|o| unsafe { nf_prov_batch_id(b.as_ptr(), b.len(), o) });
        assert_eq!(id, s(e, "id"));
    }
    let batches = json(&Value::Array(
        chain.iter().map(|e| get(e, "batch").clone()).collect(),
    ));
    let ids = text_out(|o| unsafe { nf_verify_prov_chain(batches.as_ptr(), batches.len(), o) });
    let want: Vec<&str> = chain.iter().map(|e| s(e, "id")).collect();
    assert_eq!(ids, want.join("\n"));
    // a broken chain is NF_ERR_VERIFY: drop the first batch
    let broken = json(&Value::Array(
        chain
            .iter()
            .skip(1)
            .map(|e| get(e, "batch").clone())
            .collect(),
    ));
    assert_eq!(
        status_of(|o| unsafe { nf_verify_prov_chain(broken.as_ptr(), broken.len(), o) }),
        NF_ERR_VERIFY
    );
}

// ---------------------------------------------------------------- v2 hashes
fn doc_text(
    f: unsafe extern "C" fn(*const u8, usize, *mut nf_buf) -> nf_status,
    v: &Value,
) -> String {
    let t = json(v);
    text_out(|o| unsafe { f(t.as_ptr(), t.len(), o) })
}

#[test]
fn ids_v2_hashes() {
    let doc = load("ids-v2.json");
    let audit = arr(&doc, "audit_batch_chain");
    for c in audit {
        let id = doc_text(nf_audit_batch_id, get(c, "batch"));
        assert_eq!(id, s(c, "id"));
        assert!(unsafe { nf_is_valid_id_v2(cp(&common::c(&id))) });
        assert!(
            !unsafe { nf_is_valid_id(cp(&common::c(&id))) },
            "auditb is v2 only"
        );
    }
    let batches = Value::Array(audit.iter().map(|c| get(c, "batch").clone()).collect());
    let want: Vec<&str> = audit.iter().map(|c| s(c, "id")).collect();
    assert_eq!(doc_text(nf_verify_audit_chain, &batches), want.join("\n"));

    for c in arr(&doc, "prov_node") {
        assert_eq!(doc_text(nf_prov_node_hash, get(c, "record")), s(c, "hash"));
    }
    let consent = arr(&doc, "consent_record_chain");
    for c in consent {
        assert_eq!(
            doc_text(nf_consent_record_hash, get(c, "record")),
            s(c, "hash")
        );
    }
    let recs = Value::Array(consent.iter().map(|c| get(c, "record").clone()).collect());
    let want: Vec<&str> = consent.iter().map(|c| s(c, "hash")).collect();
    assert_eq!(doc_text(nf_verify_consent_chain, &recs), want.join("\n"));
    let nc = get(&doc, "consent_record_noncanonical_scopes");
    assert_eq!(
        doc_text(nf_consent_record_hash, get(nc, "record")),
        s(nc, "hash")
    );

    let rs = get(&doc, "ruleset");
    assert_eq!(
        doc_text(nf_ruleset_content_sha256, get(rs, "rules")),
        s(rs, "content_sha256")
    );
    for c in arr(&doc, "sweep_variant") {
        let (base, params) = (common::c(s(c, "base")), json(get(c, "params")));
        let label = text_out(|o| unsafe {
            nf_sweep_variant_label(base.as_ptr(), params.as_ptr(), params.len(), o)
        });
        assert_eq!(label, s(c, "label"), "{}", s(c, "name"));
    }
    for c in arr(&doc, "training_subject") {
        let (t, sub) = (common::c(s(c, "tenant_id")), common::c(s(c, "subject_id")));
        let h = text_out(|o| unsafe { nf_training_subject_hash(t.as_ptr(), sub.as_ptr(), o) });
        assert_eq!(h, s(c, "hash"));
    }
    for c in arr(&doc, "training_manifest") {
        let built = doc_text(nf_training_manifest_build, get(c, "args"));
        assert_eq!(
            built.as_bytes(),
            json(get(c, "manifest")),
            "{}",
            s(c, "name")
        );
        assert_eq!(built, s(c, "payload"), "{}", s(c, "name"));
        assert_eq!(
            doc_text(nf_training_manifest_digest, get(c, "manifest")),
            s(c, "digest")
        );
    }
}

// ---------------------------------------------------------------- v2 signatures
fn flat_pairs(v: &Value, key: &str) -> Vec<f64> {
    arr(v, key)
        .iter()
        .flat_map(|p| match p {
            Value::Array(x) => x.iter().map(num).collect::<Vec<_>>(),
            _ => panic!("pair"),
        })
        .collect()
}

#[test]
fn ids_v2_signatures() {
    let doc = load("ids-v2.json");
    let pk = pk(&doc);

    let c = get(&doc, "stream_chunk_signature");
    let ch = get(c, "chunk");
    let ts: Vec<f64> = arr(ch, "lsl_timestamps").iter().map(num).collect();
    let (off, loc) = (
        flat_pairs(ch, "clock_offsets"),
        flat_pairs(ch, "local_clock"),
    );
    let timing = text_out(|o| unsafe {
        nf_timing_sha256(
            ts.as_ptr(),
            ts.len(),
            off.as_ptr(),
            off.len() / 2,
            loc.as_ptr(),
            loc.len() / 2,
            o,
        )
    });
    assert_eq!(timing, s(c, "timing_sha256"));
    let (sid, cid) = (common::c(s(ch, "stream_id")), common::c(s(ch, "chunk_id")));
    let mut fields = nf_stream_chunk_fields {
        stream_id: sid.as_ptr(),
        seq: int(ch, "seq") as u64,
        n_samples: int(ch, "n_samples") as u32,
        n_channels: int(ch, "n_channels") as u32,
        chunk_id: cid.as_ptr(),
        lsl_timestamps: ts.as_ptr(),
        n_timestamps: ts.len(),
        clock_offsets: off.as_ptr(),
        n_clock_offsets: off.len() / 2,
        local_clock: loc.as_ptr(),
        n_local_clock: loc.len() / 2,
    };
    let sig = hex(s(c, "signature_hex"));
    let verify = |f: &nf_stream_chunk_fields, sig: &[u8]| {
        let mut ok = false;
        let st =
            unsafe { nf_verify_stream_chunk(f, sig.as_ptr(), sig.len(), pk.as_ptr(), &mut ok) };
        assert_eq!(st, NF_OK, "{}", last_error());
        ok
    };
    assert!(verify(&fields, &sig));
    let mut bad = sig.clone();
    bad[0] ^= 1;
    assert!(!verify(&fields, &bad));
    fields.seq += 1;
    assert!(!verify(&fields, &sig));

    let dt = get(&doc, "device_token");
    let token = common::c(s(dt, "token"));
    let iat = int(get(dt, "claims"), "iat");
    let claims =
        text_out(|o| unsafe { nf_verify_device_token(token.as_ptr(), pk.as_ptr(), iat, o) });
    assert_eq!(claims.as_bytes(), json(get(dt, "claims")));
    let exp = int(get(dt, "claims"), "exp");
    assert_eq!(
        status_of(|o| unsafe { nf_verify_device_token(token.as_ptr(), pk.as_ptr(), exp + 31, o) }),
        NF_ERR_VERIFY
    );
    // NULL claims output is allowed
    assert_eq!(
        unsafe { nf_verify_device_token(token.as_ptr(), pk.as_ptr(), iat, std::ptr::null_mut()) },
        NF_OK
    );

    let pb = get(&doc, "provb_signature");
    let (id, sig) = (common::c(s(pb, "batch_id")), hex(s(pb, "signature_hex")));
    let mut ok = false;
    assert_eq!(
        unsafe {
            nf_verify_provb_signature(id.as_ptr(), sig.as_ptr(), sig.len(), pk.as_ptr(), &mut ok)
        },
        NF_OK
    );
    assert!(ok);

    for key in ["prov_anchor", "consent_anchor"] {
        let a = json(get(get(&doc, key), "document"));
        let mut ok = false;
        assert_eq!(
            unsafe { nf_verify_anchor(a.as_ptr(), a.len(), pk.as_ptr(), &mut ok) },
            NF_OK
        );
        assert!(ok, "{key}");
    }
    let cert = json(get(get(&doc, "deletion_certificate"), "document"));
    let mut ok = false;
    assert_eq!(
        unsafe { nf_verify_certificate(cert.as_ptr(), cert.len(), pk.as_ptr(), &mut ok) },
        NF_OK
    );
    assert!(ok);
    // a different key does not verify
    let other = [7u8; 32];
    assert_eq!(
        unsafe { nf_verify_certificate(cert.as_ptr(), cert.len(), other.as_ptr(), &mut ok) },
        NF_OK
    );
    assert!(!ok);
}

// ---------------------------------------------------------------- tests/c/vectors.h
/// A C string literal: printable ASCII except `"`, `\` and `?` stays, everything else becomes a
/// 3-digit octal escape (a hex escape could swallow following hex digits).
fn c_str(s: &[u8]) -> String {
    let mut o = String::from("\"");
    let mut seg = 0;
    let mut after_escape = false;
    for &b in s {
        // MSVC limits one literal segment; adjacent literals are concatenated
        if o.len() - seg > 1000 {
            o.push_str("\"\n        \"");
            seg = o.len();
        }
        if (0x20..0x7f).contains(&b) && !matches!(b, b'"' | b'\\' | b'?') {
            // a digit right after an octal escape reads as a fourth digit to MSVC (C4125)
            if after_escape && b.is_ascii_digit() {
                o.push_str("\" \"");
            }
            o.push(b as char);
            after_escape = false;
        } else {
            o.push_str(&format!("\\{b:03o}"));
            after_escape = true;
        }
    }
    o.push('"');
    o
}

fn c_text(s: &str) -> String {
    c_str(s.as_bytes())
}

fn c_json(v: &Value) -> String {
    c_str(&json(v))
}

fn c_bits(xs: &[f64]) -> String {
    let items: Vec<String> = xs
        .iter()
        .map(|x| format!("0x{:016x}ull", x.to_bits()))
        .collect();
    format!("{{{}}}", items.join(", "))
}

fn generate_c_vectors() -> String {
    let v1 = load("ids.json");
    let v2 = load("ids-v2.json");
    let cj = load("canonical-json.json");
    let mut h = String::new();
    let mut line = |l: String| {
        h.push_str(&l);
        h.push('\n');
    };
    line(
        "/* Generated by bindings/c/tests/vectors.rs from spec/test-vectors/*.json. Do not edit:"
            .into(),
    );
    line(" * NF_UPDATE_C_VECTORS=1 cargo test -p neuroforge-c --test vectors */".into());
    line("#ifndef NF_TEST_VECTORS_H".into());
    line("#define NF_TEST_VECTORS_H".into());
    line("#include <stddef.h>".into());
    line("#include <stdint.h>".into());
    line(String::new());
    line("typedef struct { const char *in; const char *out; } nf_vec_pair;".into());
    line(
        "typedef struct { const char *in; const char *out; const char *extra; } nf_vec_triple;"
            .into(),
    );
    line("typedef struct { const char *dtype; uint64_t shape[4]; size_t rank; const char *data_hex; const char *id; } nf_vec_chunk;".into());
    line(String::new());

    let pairs = |name: &str, items: Vec<(String, String)>| {
        let mut s = format!("static const nf_vec_pair {name}[] = {{\n");
        for (a, b) in &items {
            s.push_str(&format!("    {{{a}, {b}}},\n"));
        }
        s.push_str("};\n");
        s.push_str(&format!("#define {name}_N {}\n", items.len()));
        s
    };
    let mut body = String::new();
    body += &pairs(
        "NF_VEC_CANONICAL",
        arr(&cj, "cases")
            .iter()
            .map(|c| (c_text(s(c, "input")), c_text(s(c, "canonical"))))
            .collect(),
    );
    body += &pairs(
        "NF_VEC_CANONICAL_ERRORS",
        arr(&cj, "errors")
            .iter()
            .map(|c| (c_text(s(c, "input")), c_text(s(c, "name"))))
            .collect(),
    );
    body += &pairs(
        "NF_VEC_BLOB",
        arr(&v1, "blob")
            .iter()
            .map(|c| (c_text(s(c, "data_hex")), c_text(s(c, "id"))))
            .collect(),
    );
    body += &pairs(
        "NF_VEC_PV",
        arr(&v1, "pipeline_version")
            .iter()
            .map(|c| (c_json(get(c, "spec")), c_text(s(c, "id"))))
            .collect(),
    );
    body += &pairs(
        "NF_VEC_PROVB",
        arr(&v1, "prov_batch_chain")
            .iter()
            .map(|c| (c_json(get(c, "batch")), c_text(s(c, "id"))))
            .collect(),
    );
    body += &pairs(
        "NF_VEC_AUDITB",
        arr(&v2, "audit_batch_chain")
            .iter()
            .map(|c| (c_json(get(c, "batch")), c_text(s(c, "id"))))
            .collect(),
    );
    body += &pairs(
        "NF_VEC_PROV_NODE",
        arr(&v2, "prov_node")
            .iter()
            .map(|c| (c_json(get(c, "record")), c_text(s(c, "hash"))))
            .collect(),
    );
    let mut consent: Vec<(String, String)> = arr(&v2, "consent_record_chain")
        .iter()
        .map(|c| (c_json(get(c, "record")), c_text(s(c, "hash"))))
        .collect();
    let nc = get(&v2, "consent_record_noncanonical_scopes");
    consent.push((c_json(get(nc, "record")), c_text(s(nc, "hash"))));
    body += &pairs("NF_VEC_CONSENT", consent);
    let rs = get(&v2, "ruleset");
    body += &pairs(
        "NF_VEC_RULESET",
        vec![(c_json(get(rs, "rules")), c_text(s(rs, "content_sha256")))],
    );
    body += &pairs(
        "NF_VEC_MANIFEST_BUILD",
        arr(&v2, "training_manifest")
            .iter()
            .map(|c| (c_json(get(c, "args")), c_json(get(c, "manifest"))))
            .collect(),
    );
    body += &pairs(
        "NF_VEC_MANIFEST_DIGEST",
        arr(&v2, "training_manifest")
            .iter()
            .map(|c| (c_json(get(c, "manifest")), c_text(s(c, "digest"))))
            .collect(),
    );
    line(body);

    let triples = |name: &str, items: Vec<(String, String, String)>| {
        let mut s = format!("static const nf_vec_triple {name}[] = {{\n");
        for (a, b, c) in &items {
            s.push_str(&format!("    {{{a}, {b}, {c}}},\n"));
        }
        s.push_str("};\n");
        s.push_str(&format!("#define {name}_N {}\n", items.len()));
        s
    };
    line(triples(
        "NF_VEC_SWEEP",
        arr(&v2, "sweep_variant")
            .iter()
            .map(|c| {
                (
                    c_text(s(c, "base")),
                    c_json(get(c, "params")),
                    c_text(s(c, "label")),
                )
            })
            .collect(),
    ));
    line(triples(
        "NF_VEC_SUBJECT",
        arr(&v2, "training_subject")
            .iter()
            .map(|c| {
                (
                    c_text(s(c, "tenant_id")),
                    c_text(s(c, "subject_id")),
                    c_text(s(c, "hash")),
                )
            })
            .collect(),
    ));

    line("static const nf_vec_chunk NF_VEC_CHUNK[] = {".into());
    let chunks = arr(&v1, "chunk");
    for c in chunks {
        let shape: Vec<u64> = arr(c, "shape").iter().map(|v| num(v) as u64).collect();
        let mut padded = shape.clone();
        padded.resize(4, 0);
        let sh: Vec<String> = padded.iter().map(|x| format!("{x}u")).collect();
        line(format!(
            "    {{{}, {{{}}}, {}, {}, {}}},",
            c_text(s(c, "dtype")),
            sh.join(", "),
            shape.len(),
            c_text(s(c, "data_hex")),
            c_text(s(c, "id"))
        ));
    }
    line("};".into());
    line(format!("#define NF_VEC_CHUNK_N {}\n", chunks.len()));

    let chain = |key: &str, member: &str, out: &str, cases: &[Value]| {
        let docs = Value::Array(cases.iter().map(|c| get(c, member).clone()).collect());
        let ids: Vec<&str> = cases.iter().map(|c| s(c, out)).collect();
        (c_json(&docs), c_text(&ids.join("\n")), key.to_owned())
    };
    for (docs, ids, key) in [
        chain("PROVB", "batch", "id", arr(&v1, "prov_batch_chain")),
        chain("AUDITB", "batch", "id", arr(&v2, "audit_batch_chain")),
        chain(
            "CONSENT",
            "record",
            "hash",
            arr(&v2, "consent_record_chain"),
        ),
    ] {
        line(format!("static const char NF_VEC_{key}_CHAIN[] = {docs};"));
        line(format!(
            "static const char NF_VEC_{key}_CHAIN_IDS[] = {ids};"
        ));
    }
    line(String::new());

    let k = get(&v2, "test_key");
    line(format!(
        "static const char NF_VEC_PUBLIC_KEY_HEX[] = {};",
        c_text(s(k, "public_hex"))
    ));
    let sc = get(&v2, "stream_chunk_signature");
    let ch = get(sc, "chunk");
    let ts: Vec<f64> = arr(ch, "lsl_timestamps").iter().map(num).collect();
    line(format!(
        "static const char NF_VEC_CHUNK_STREAM_ID[] = {};",
        c_text(s(ch, "stream_id"))
    ));
    line(format!(
        "static const char NF_VEC_CHUNK_CHUNK_ID[] = {};",
        c_text(s(ch, "chunk_id"))
    ));
    line(format!(
        "static const uint64_t NF_VEC_CHUNK_SEQ = {}u;",
        int(ch, "seq")
    ));
    line(format!(
        "static const uint32_t NF_VEC_CHUNK_N_SAMPLES = {}u;",
        int(ch, "n_samples")
    ));
    line(format!(
        "static const uint32_t NF_VEC_CHUNK_N_CHANNELS = {}u;",
        int(ch, "n_channels")
    ));
    line(format!(
        "static const uint64_t NF_VEC_CHUNK_TS_BITS[] = {};",
        c_bits(&ts)
    ));
    line(format!(
        "static const uint64_t NF_VEC_CHUNK_OFFSETS_BITS[] = {};",
        c_bits(&flat_pairs(ch, "clock_offsets"))
    ));
    line(format!(
        "static const uint64_t NF_VEC_CHUNK_LOCAL_BITS[] = {};",
        c_bits(&flat_pairs(ch, "local_clock"))
    ));
    line(format!(
        "static const char NF_VEC_CHUNK_TIMING_SHA256[] = {};",
        c_text(s(sc, "timing_sha256"))
    ));
    line(format!(
        "static const char NF_VEC_CHUNK_SIGNATURE_HEX[] = {};",
        c_text(s(sc, "signature_hex"))
    ));
    let dt = get(&v2, "device_token");
    line(format!(
        "static const char NF_VEC_TOKEN[] = {};",
        c_text(s(dt, "token"))
    ));
    line(format!(
        "static const char NF_VEC_TOKEN_CLAIMS[] = {};",
        c_json(get(dt, "claims"))
    ));
    line(format!(
        "static const int64_t NF_VEC_TOKEN_IAT = {};",
        int(get(dt, "claims"), "iat")
    ));
    line(format!(
        "static const int64_t NF_VEC_TOKEN_EXP = {};",
        int(get(dt, "claims"), "exp")
    ));
    let pb = get(&v2, "provb_signature");
    line(format!(
        "static const char NF_VEC_PROVB_SIG_BATCH_ID[] = {};",
        c_text(s(pb, "batch_id"))
    ));
    line(format!(
        "static const char NF_VEC_PROVB_SIG_HEX[] = {};",
        c_text(s(pb, "signature_hex"))
    ));
    line(format!(
        "static const char NF_VEC_PROV_ANCHOR[] = {};",
        c_json(get(get(&v2, "prov_anchor"), "document"))
    ));
    line(format!(
        "static const char NF_VEC_CONSENT_ANCHOR[] = {};",
        c_json(get(get(&v2, "consent_anchor"), "document"))
    ));
    line(format!(
        "static const char NF_VEC_DELETION_CERTIFICATE[] = {};",
        c_json(get(get(&v2, "deletion_certificate"), "document"))
    ));
    line(String::new());
    line("#endif /* NF_TEST_VECTORS_H */".into());
    h
}

#[test]
fn c_vectors_header_is_current() {
    let path = format!("{}/tests/c/vectors.h", env!("CARGO_MANIFEST_DIR"));
    let want = generate_c_vectors();
    if std::env::var_os("NF_UPDATE_C_VECTORS").is_some() {
        std::fs::write(&path, &want).unwrap();
    }
    let have = std::fs::read_to_string(&path)
        .unwrap_or_default()
        .replace("\r\n", "\n");
    assert!(
        have == want,
        "tests/c/vectors.h is stale: NF_UPDATE_C_VECTORS=1 cargo test -p neuroforge-c --test vectors"
    );
}
