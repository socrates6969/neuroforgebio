//! Verifies `headers.rs`'s `/arena/` SEC-150 exception handling (the one thing no real dist can
//! exercise yet - `headers.rs`'s "Known gap 2": no page here reaches a real `.wasm`) against
//! synthetic fixtures, per team-lead's ruling 2026-09-27: reuse
//! `apps/web/test/csp-static.test.mjs`'s canonical `hashedArena()` fixture (web-headers: the current
//! layout, hashed glue + hashed `.wasm` under the shared `/_assets/`, replicated read-only in a
//! standalone script since the helper isn't exported), run the REAL, unmodified `postbuild()`
//! (`apps/web/scripts/postbuild.mjs`) on it, and byte-diff this crate's output on the same fixture
//! (same `paths`, same `active` exceptions) against it.
//!
//! Two variants, both built by `scripts/arena-fixture-js.mjs` (committed, not part of the Rust
//! build or CI - see that file's header) into `NF_ARENA_FIXTURE_DIR/<variant>/`:
//! - `canonical-active/`: `/arena/`'s chunk reaches the hashed `.wasm` -> the exception is active.
//! - `stub-baseline/`: `/arena/` is built with no wasm-reaching loader -> baseline CSP everywhere,
//!   per web-headers' pointer that this case must also be checked.
//!
//! Each variant dir has: `paths.json` (`sitePaths()`'s output), `active.json` (`exceptionsInUse()`'s
//! output), `cloudflare._headers` + `cloudflare._headers.json` (from the real `postbuild()`), and
//! either `netlify._headers(.json)` or `netlify.error.txt` (postbuild() throws "KEEP FAIL" whenever
//! `canonical-active`'s exception would need Netlify to serve it).
//!
//! `#[ignore]`d like the dist-based parity tests: needs that directory, doesn't exist by default.
//! Run: `NF_ARENA_FIXTURE_DIR=<out-dir> cargo test -p site-rs --test arena_fixture_parity -- --ignored`
//!
//! Most tests here take the fixture's `active.json` (computed by the REAL JS `exceptionsInUse()`) as
//! given and check that this crate's `headers.rs` renders the same `_headers`/`_headers.json` from
//! it: generation parity. The two `own_trigger_agrees_with_js_on_*` tests close the other half
//! (web-headers review item c): they run THIS crate's own `csp_check::exceptions_in_use()` against
//! the fixture's live dist directory (`dist-dir.txt`, kept alive by `arena-fixture-js.mjs`
//! specifically for this - delete it manually once done, it's outside the repo) and assert it agrees
//! with JS's `active.json`: detection parity, not just generation parity. `csp_check.rs` also has its
//! own unit tests against small synthetic dists built directly in Rust, covering the same cases plus
//! dist-root confinement and fail-strict-on-read-error, which don't need this fixture at all.

use serde::Deserialize;
use site_rs::csp_check;
use site_rs::headers::{self, CspException, Host, Stage};
use std::path::{Path, PathBuf};

fn repo_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .expect("repo root")
}

fn fixture_dir(variant: &str) -> PathBuf {
    let base = std::env::var("NF_ARENA_FIXTURE_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|_| repo_root().join("does-not-exist-run-arena-fixture-js-first"));
    base.join(variant)
}

fn read_fixture_file(variant: &str, name: &str) -> String {
    let dir = fixture_dir(variant);
    let path = dir.join(name);
    std::fs::read_to_string(&path).unwrap_or_else(|e| {
        panic!(
            "could not read {} ({e}). Build the fixtures first: \
             `node tools/site-rs/scripts/arena-fixture-js.mjs <repo-root> <clinical-dist-dir> <out-dir>`, \
             then set NF_ARENA_FIXTURE_DIR to that <out-dir> (this reads <out-dir>/{}/{}).",
            path.display(),
            variant,
            name
        )
    })
}

fn line_diff(expected: &str, actual: &str) -> Vec<String> {
    let e: Vec<&str> = expected.lines().collect();
    let a: Vec<&str> = actual.lines().collect();
    let mut diffs = Vec::new();
    for i in 0..e.len().max(a.len()) {
        if e.get(i) != a.get(i) {
            diffs.push(format!(
                "  line {}: js={:?} rust={:?}",
                i + 1,
                e.get(i),
                a.get(i)
            ));
        }
    }
    if e.len() != a.len() {
        diffs.push(format!(
            "  (js has {} lines, rust has {})",
            e.len(),
            a.len()
        ));
    }
    diffs
}

#[derive(Deserialize)]
struct FixtureException {
    route: String,
    directive: String,
    token: String,
}

fn read_active(variant: &str) -> Vec<CspException> {
    let raw: Vec<FixtureException> =
        serde_json::from_str(&read_fixture_file(variant, "active.json"))
            .expect("parse active.json");
    raw.into_iter()
        .map(|e| CspException {
            route: e.route,
            directive: e.directive,
            token: e.token,
        })
        .collect()
}

fn read_paths(variant: &str) -> Vec<String> {
    serde_json::from_str(&read_fixture_file(variant, "paths.json")).expect("parse paths.json")
}

/// The live fixture dist directory (kept alive by `arena-fixture-js.mjs` specifically for this
/// cross-check, unlike `paths.json`/`active.json` which are plain data files - see that script's
/// `dist-dir.txt` comment). Web-headers review item c.
fn fixture_dist_dir(variant: &str) -> PathBuf {
    let text = read_fixture_file(variant, "dist-dir.txt");
    PathBuf::from(text.trim())
}

fn assert_cloudflare_matches(variant: &str) {
    let root = repo_root();
    let exceptions = headers::load_csp_exceptions(&root).expect("load csp-exceptions.json");
    let paths = read_paths(variant);
    let active = read_active(variant);

    let rules = headers::host_rules(
        Host::Cloudflare,
        Stage::Preview,
        &paths,
        &exceptions,
        &active,
    )
    .expect("cloudflare host_rules must succeed");
    let text = headers::render_host_headers_checked(Host::Cloudflare, &rules, Stage::Preview)
        .expect("cloudflare limits");
    let checked = headers::checked_active(&active, &exceptions, &paths);
    let json = headers::HeadersJson::new(Stage::Preview, Host::Cloudflare, &checked, &rules)
        .render()
        .expect("render json");

    let js_text = read_fixture_file(variant, "cloudflare._headers");
    let js_json = read_fixture_file(variant, "cloudflare._headers.json");

    let text_diffs = line_diff(&js_text, &text);
    assert!(
        text_diffs.is_empty(),
        "[{variant}] cloudflare _headers diff:\n{}",
        text_diffs.join("\n")
    );
    let json_diffs = line_diff(&js_json, &json);
    assert!(
        json_diffs.is_empty(),
        "[{variant}] cloudflare _headers.json diff:\n{}",
        json_diffs.join("\n")
    );
}

#[test]
#[ignore = "needs the arena fixtures (NF_ARENA_FIXTURE_DIR); see module doc comment"]
fn canonical_active_cloudflare_matches_js_and_carries_the_exception() {
    let active = read_active("canonical-active");
    assert_eq!(
        active.len(),
        1,
        "canonical-active fixture must have exactly one active exception"
    );
    assert_eq!(active[0].route, "/arena/");

    assert_cloudflare_matches("canonical-active");

    let root = repo_root();
    let exceptions = headers::load_csp_exceptions(&root).expect("load csp-exceptions.json");
    let paths = read_paths("canonical-active");
    let rules = headers::host_rules(
        Host::Cloudflare,
        Stage::Preview,
        &paths,
        &exceptions,
        &active,
    )
    .unwrap();
    let text = headers::render_host_headers_checked(Host::Cloudflare, &rules, Stage::Preview)
        .expect("cloudflare limits");
    assert!(text.contains("/arena/*"));
    assert!(text.contains("  ! Content-Security-Policy"));
    assert!(text.contains("'wasm-unsafe-eval'"));
}

#[test]
#[ignore = "needs the arena fixtures (NF_ARENA_FIXTURE_DIR); see module doc comment"]
fn canonical_active_netlify_fails_the_same_way_as_js() {
    let root = repo_root();
    let exceptions = headers::load_csp_exceptions(&root).expect("load csp-exceptions.json");
    let paths = read_paths("canonical-active");
    let active = read_active("canonical-active");

    let js_error = read_fixture_file("canonical-active", "netlify.error.txt");
    let rust_error =
        headers::host_rules(Host::Netlify, Stage::Preview, &paths, &exceptions, &active)
            .expect_err("netlify host_rules must fail when an exception is active");
    assert_eq!(
        js_error.trim_end(),
        rust_error.trim_end(),
        "netlify error message must match JS exactly"
    );
}

#[test]
#[ignore = "needs the arena fixtures (NF_ARENA_FIXTURE_DIR); see module doc comment"]
fn stub_baseline_has_no_active_exception_and_matches_js_on_both_hosts() {
    let active = read_active("stub-baseline");
    assert!(
        active.is_empty(),
        "an /arena/ page with no wasm-reaching loader must not activate the exception"
    );

    assert_cloudflare_matches("stub-baseline");

    let root = repo_root();
    let exceptions = headers::load_csp_exceptions(&root).expect("load csp-exceptions.json");
    let paths = read_paths("stub-baseline");
    let rules = headers::host_rules(Host::Netlify, Stage::Preview, &paths, &exceptions, &active)
        .expect("netlify must succeed when nothing is active");
    let text = headers::render_host_headers_checked(Host::Netlify, &rules, Stage::Preview)
        .expect("netlify has no rule-count cap");
    let js_text = read_fixture_file("stub-baseline", "netlify._headers");
    let diffs = line_diff(&js_text, &text);
    assert!(
        diffs.is_empty(),
        "stub-baseline netlify _headers diff:\n{}",
        diffs.join("\n")
    );
    assert!(
        !text.contains("wasm-unsafe-eval"),
        "baseline CSP must not carry the exception token"
    );
}

// ---------------------------------------------------------------------- web-headers review item c
// Cross-check: run THIS crate's own wasm-reachability trigger (csp_check::exceptions_in_use) on the
// exact same fixture files JS scanned, and assert it finds the same active exceptions JS's
// active.json recorded. This is what closes the gap the earlier version of this file's module doc
// comment flagged: previously the trigger was never run against the JS-built fixture, only against
// small dists built directly in Rust in csp_check.rs's own unit tests.

#[test]
#[ignore = "needs the arena fixtures (NF_ARENA_FIXTURE_DIR); see module doc comment"]
fn own_trigger_agrees_with_js_on_canonical_active() {
    let root = repo_root();
    let list = headers::load_csp_exceptions(&root).expect("load csp-exceptions.json");
    let dist = fixture_dist_dir("canonical-active");
    let js_active = read_active("canonical-active");

    let mut error: Option<String> = None;
    let rust_active = csp_check::exceptions_in_use(&dist, &list, |e| error = Some(e.to_string()));

    assert!(
        error.is_none(),
        "detection must not error on a readable fixture: {error:?}"
    );
    let rust_routes: Vec<&str> = rust_active.iter().map(|e| e.route.as_str()).collect();
    let js_routes: Vec<&str> = js_active.iter().map(|e| e.route.as_str()).collect();
    assert_eq!(
        rust_routes, js_routes,
        "this crate's own trigger must agree with JS's exceptionsInUse"
    );
}

#[test]
#[ignore = "needs the arena fixtures (NF_ARENA_FIXTURE_DIR); see module doc comment"]
fn own_trigger_agrees_with_js_on_stub_baseline() {
    let root = repo_root();
    let list = headers::load_csp_exceptions(&root).expect("load csp-exceptions.json");
    let dist = fixture_dist_dir("stub-baseline");
    let js_active = read_active("stub-baseline");
    assert!(
        js_active.is_empty(),
        "sanity: stub-baseline's own active.json should be empty"
    );

    let mut error: Option<String> = None;
    let rust_active = csp_check::exceptions_in_use(&dist, &list, |e| error = Some(e.to_string()));

    assert!(
        error.is_none(),
        "detection must not error on a readable fixture: {error:?}"
    );
    assert!(
        rust_active.is_empty(),
        "this crate's own trigger must also find nothing active"
    );
}
