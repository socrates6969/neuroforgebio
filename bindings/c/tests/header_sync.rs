//! Cheap drift check without cbindgen: every exported function in `src/` is declared in the
//! checked-in `include/neuroforge.h`, and the header declares nothing that is no longer exported.
//! The byte-exact check is `node bindings/c/tools/header.mjs --check` (CI).

use std::collections::BTreeSet;

fn exported() -> BTreeSet<String> {
    let src = concat!(env!("CARGO_MANIFEST_DIR"), "/src");
    let mut names = BTreeSet::new();
    for e in std::fs::read_dir(src).unwrap() {
        let text = std::fs::read_to_string(e.unwrap().path()).unwrap();
        let mut marked = false;
        for line in text.lines() {
            let l = line.trim();
            if l == "#[unsafe(no_mangle)]" {
                marked = true;
                continue;
            }
            if marked && let Some(i) = l.find("extern \"C\" fn ") {
                let rest = &l[i + "extern \"C\" fn ".len()..];
                names.insert(rest[..rest.find('(').unwrap()].to_owned());
                marked = false;
            }
        }
    }
    names
}

fn declared() -> BTreeSet<String> {
    let h = std::fs::read_to_string(concat!(env!("CARGO_MANIFEST_DIR"), "/include/neuroforge.h"))
        .unwrap();
    h.lines()
        .filter(|l| !l.starts_with("//") && !l.starts_with(' ') && !l.starts_with("typedef"))
        .filter_map(|l| {
            let open = l.find('(')?;
            let name = l[..open].rsplit([' ', '*']).next()?;
            name.starts_with("nf_").then(|| name.to_owned())
        })
        .collect()
}

#[test]
fn header_declares_exactly_the_exports() {
    let (e, d) = (exported(), declared());
    assert!(e.len() > 90, "found only {} exports", e.len());
    let missing: Vec<_> = e.difference(&d).collect();
    let stale: Vec<_> = d.difference(&e).collect();
    assert!(
        missing.is_empty() && stale.is_empty(),
        "header out of date (node bindings/c/tools/header.mjs): missing {missing:?}, stale {stale:?}"
    );
}

/// The `//` comment block directly above the first line declaring `decl` in the header.
fn doc_of(decl: &str) -> String {
    let h = std::fs::read_to_string(concat!(env!("CARGO_MANIFEST_DIR"), "/include/neuroforge.h"))
        .unwrap();
    let lines: Vec<&str> = h.lines().collect();
    let at = lines
        .iter()
        .position(|l| !l.starts_with("//") && l.contains(decl))
        .unwrap_or_else(|| panic!("{decl} not declared"));
    let mut doc: Vec<&str> = lines[..at]
        .iter()
        .rev()
        .take_while(|l| l.starts_with("//"))
        .copied()
        .collect();
    doc.reverse();
    doc.join("\n")
}

#[test]
fn security_contracts_are_documented_in_the_header() {
    // CABI-L4: DPAPI sealing without entropy (NR-L6) is stated where it is reachable
    for f in ["nf_device_key_open_sealed(", "nf_wal_open("] {
        assert!(doc_of(f).contains("NR-L6"), "{f} lacks the NR-L6 note");
    }
    // CABI-L3: the WAL needs an explicit key source
    assert!(doc_of("nf_wal_open(").contains("NF_ERR_INVALID_ARG"));
    assert!(doc_of("nf_wal_open_ephemeral(").starts_with(
        "// FOR TESTS AND THROWAWAY SESSIONS ONLY: records are unreadable after the process ends."
    ));
    // CABI-L5: every callback table states its thread contract
    for t in [
        "typedef struct nf_ingest_transport {",
        "typedef struct nf_http_transport {",
        "typedef struct nf_token_source {",
    ] {
        let d = doc_of(t);
        assert!(
            d.contains("Thread contract") && d.contains("thread-safe"),
            "{t} lacks a thread contract"
        );
    }
}

#[test]
fn transport_requirements_are_in_the_header() {
    // CABI-M1 step 1: the SEC-030 contract sits on both caller transport tables
    for t in [
        "typedef struct nf_http_transport {",
        "typedef struct nf_ingest_transport {",
    ] {
        let d = doc_of(t);
        for must in [
            "Transport requirements (SEC-030, CABI-M1)",
            "TLS 1.3 only",
            "certificate chain and hostname",
            "never follow redirects",
            "timeout_s",
            "never log",
        ] {
            assert!(d.contains(must), "{t} lacks {must:?}");
        }
    }
    // the caps are header constants (nfb-security)
    let h = std::fs::read_to_string(concat!(env!("CARGO_MANIFEST_DIR"), "/include/neuroforge.h"))
        .unwrap();
    for c in [
        "#define NF_MAX_RESPONSE_BYTES ",
        "#define NF_MAX_RESPONSE_HEADERS ",
        "#define NF_MAX_RESPONSE_HEADER_BYTES ",
        "#define NF_MAX_REPLY_BYTES ",
    ] {
        assert!(h.contains(c), "header lacks {c}");
    }
}
