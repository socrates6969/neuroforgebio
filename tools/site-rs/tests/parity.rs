//! Byte-diff parity test (web-queen T1, redesigned per web-queen's 2026-09-27 correction): the
//! reference is `<dist root>/{clinical,cosmos}/{robots.txt,sitemap.xml}` as built by Astro from the
//! current tree, NOT a frozen snapshot - an assertion against a fixture that predates the current
//! tree "proves nothing and goes stale at the next sitemap change" (web-queen). An earlier version
//! of this test used a frozen m5-dist fixture (`tests/fixtures/m5-golden-dist-2026-09-27/`, since
//! deleted - see git history for that commit if needed) for exactly this reason.
//!
//! **This crate does not build that dist itself**: the node/python ban was lifted 2026-09-27
//! (RUST-POLICY.md), but team-lead's ruling for this worktree is division of labour, not a tool
//! ban - web-queen owns building `apps/web/dist` (in a bci-queen slot) and this crate owns the Rust
//! generator, so the dist root defaults to `apps/web/dist` in THIS worktree (which won't exist here)
//! but can be pointed at a dist built elsewhere via `NF_WEB_DIST`; web-queen reports which commit
//! it's from each time she rebuilds it, treat it read-only. Run e.g.:
//! `NF_WEB_DIST=C:\Users\mariu\neuro-worktrees\web-integration\apps\web\dist cargo test -p site-rs`
//!
//! If the dist root (for either theme) doesn't exist, these tests fail with a clear "build the site
//! first" message (mirroring `apps/web/test/_dist.mjs`'s pattern) instead of silently skipping.
//!
//! **`#[ignore]`d by default** (web-queen, 2026-09-27): CI's Rust job runs `cargo test --workspace
//! --locked` without ever building `apps/web/dist`, so an un-ignored version of these tests would
//! fail every CI run. Run them explicitly with a dist in hand:
//! `NF_WEB_DIST=C:\Users\mariu\neuro-worktrees\web-integration\apps\web\dist cargo test -p site-rs -- --ignored`
//! They still hard-fail (not skip) when run without `NF_WEB_DIST` and no local `apps/web/dist`.
//!
//! `headers_txt_matches_dist_byte_for_byte` / `headers_json_matches_dist_byte_for_byte` cover
//! `_headers`/`_headers.json` (`headers.rs`); they read the reference dist's own `stage`/`host`/
//! `activeExceptions` back out of its `_headers.json` rather than assuming SITE_HOST=cloudflare, so
//! they'd also exercise the Netlify path if a dist is ever built with `SITE_HOST=netlify` - none has
//! been yet, so that path is currently unverified against a real dist (unit-tested in `headers.rs`
//! only).

use site_rs::headers::{self, CspException, Host, Stage};
use site_rs::{content, robots, sitemap, theme::Theme};
use std::path::{Path, PathBuf};

fn repo_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .expect("repo root")
}

/// `NF_WEB_DIST` overrides the dist root (web-queen builds this elsewhere - division of labour, not
/// a tool ban, see module doc comment); defaults to `apps/web/dist` in this worktree, which won't
/// exist without it.
fn dist_root() -> PathBuf {
    match std::env::var("NF_WEB_DIST") {
        Ok(v) if !v.trim().is_empty() => PathBuf::from(v),
        _ => repo_root().join("apps/web/dist"),
    }
}

fn dist_dir(theme: Theme) -> PathBuf {
    dist_root().join(theme.as_str())
}

/// Line-by-line diff, so a failure names exactly which lines differ instead of dumping two blobs.
fn line_diff(expected: &str, actual: &str) -> Vec<String> {
    let exp_lines: Vec<&str> = expected.lines().collect();
    let act_lines: Vec<&str> = actual.lines().collect();
    let mut diffs = Vec::new();
    for i in 0..exp_lines.len().max(act_lines.len()) {
        let e = exp_lines.get(i).copied();
        let a = act_lines.get(i).copied();
        if e != a {
            diffs.push(format!("  line {}: dist={:?} generated={:?}", i + 1, e, a));
        }
    }
    if exp_lines.len() != act_lines.len() {
        diffs.push(format!(
            "  (dist has {} lines, generated has {})",
            exp_lines.len(),
            act_lines.len()
        ));
    }
    diffs
}

/// Reads `<dist root>/<theme>/<name>`, or fails with a build-it-first message; set `NF_WEB_DIST` to
/// point at a dist built elsewhere (see module doc comment for why this crate doesn't build its own).
fn require_dist_file(theme: Theme, name: &str) -> String {
    let path = dist_dir(theme).join(name);
    std::fs::read_to_string(&path).unwrap_or_else(|e| {
        panic!(
            "build the site first: could not read {} ({e}).\n\
             Set NF_WEB_DIST to an existing apps/web/dist built for THEME={} (web-queen builds one \
             in a bci-queen slot; ask which commit it's currently from), or build one yourself in a \
             slot (`node scripts/build.mjs {}` from apps/web).",
            path.display(),
            theme.as_str(),
            theme.as_str()
        )
    })
}

fn generated_robots_txt(theme: Theme, stage: Stage) -> String {
    let brand = content::Brand::load(&repo_root()).expect("load brand.json");
    robots::robots_txt(theme, stage, &brand.canonical_origin())
}

fn walk(dir: &Path, out: &mut Vec<PathBuf>) {
    for entry in std::fs::read_dir(dir).expect("read_dir") {
        let path = entry.expect("dir entry").path();
        if path.is_dir() {
            walk(&path, out);
        } else {
            out.push(path);
        }
    }
}

/// Mirrors `postbuild.mjs`'s `sitePaths()`: every emitted file's URL path outside `/_assets/`,
/// excluding `_headers`/`_headers.json` themselves. Used only here (this crate has no HTML page
/// generation yet, so it can't enumerate these paths on its own - see `headers.rs`'s "Known gap 1").
fn site_paths(dist: &Path) -> Vec<String> {
    let mut files = Vec::new();
    walk(dist, &mut files);
    let mut out: Vec<String> = files
        .into_iter()
        .filter_map(|f| {
            let rel = f
                .strip_prefix(dist)
                .ok()?
                .to_string_lossy()
                .replace('\\', "/");
            if rel.starts_with("_assets/") || rel == "_headers" || rel == "_headers.json" {
                return None;
            }
            Some(if rel == "index.html" {
                "/".to_string()
            } else if let Some(stripped) = rel.strip_suffix("/index.html") {
                format!("/{stripped}/")
            } else {
                format!("/{rel}")
            })
        })
        .collect();
    out.sort();
    out
}

/// Reads `stage`/`host`/`activeExceptions` back out of a dist's own `_headers.json`, so this test
/// doesn't hardcode which stage/host web-queen built with (and stays correct if a future dist has a
/// real active SEC-150 exception, e.g. an `/arena/` page that reaches a `.wasm`).
fn dist_headers_meta(theme: Theme) -> (Stage, Host, Vec<String>) {
    let text = require_dist_file(theme, "_headers.json");
    let v: serde_json::Value = serde_json::from_str(&text).expect("parse _headers.json");
    let stage = Stage::resolve(v["stage"].as_str()).expect("valid stage in dist _headers.json");
    let host = Host::resolve(v["host"].as_str()).expect("valid host in dist _headers.json");
    let active = v["activeExceptions"]
        .as_array()
        .map(|a| {
            a.iter()
                .filter_map(|x| x.as_str().map(String::from))
                .collect()
        })
        .unwrap_or_default();
    (stage, host, active)
}

/// Generates both `_headers` text and `_headers.json` for `theme`, using the same `paths`/`stage`/
/// `host`/`active` the reference dist itself reports (see `dist_headers_meta`).
fn generated_headers(
    theme: Theme,
    stage: Stage,
    host: Host,
    active_routes: &[String],
) -> (String, String) {
    let root = repo_root();
    let exceptions = headers::load_csp_exceptions(&root).expect("load csp-exceptions.json");
    let paths = site_paths(&dist_dir(theme));
    let active: Vec<CspException> = exceptions
        .iter()
        .filter(|e| active_routes.iter().any(|r| r == &e.route))
        .cloned()
        .collect();
    // Review gap 2 (assertCspSafe): mirror postbuild.mjs's own pre-write gate - baseline CSP first,
    // then each active exception's route CSP.
    headers::assert_csp_safe(&headers::csp(None, &exceptions), None, &exceptions, &[])
        .expect("baseline CSP must be SEC-150 safe");
    for e in &active {
        headers::assert_csp_safe(
            &headers::csp(Some(&e.route), &exceptions),
            Some(&e.route),
            &exceptions,
            &[],
        )
        .unwrap_or_else(|err| panic!("route {} CSP must be SEC-150 safe: {err}", e.route));
    }
    let rules = headers::host_rules(host, stage, &paths, &exceptions, &active).expect("host_rules");
    // Checked, not bare render_host_headers: review gap 3 (the generator must call
    // assert_cloudflare_limits) - this is that call site.
    let text =
        headers::render_host_headers_checked(host, &rules, stage).expect("cloudflare limits");
    let checked = headers::checked_active(&active, &exceptions, &paths);
    let json = headers::HeadersJson::new(stage, host, &checked, &rules)
        .render()
        .expect("render _headers.json");
    (text, json)
}

fn generated_sitemap_xml() -> String {
    let root = repo_root();
    let brand = content::Brand::load(&root).expect("load brand.json");
    let docs_routes = content::docs_routes(&root).expect("compute DOCS_ROUTES");
    let routes = sitemap::sitemap_routes(&docs_routes, |key| {
        content::legal_is_draft(&root, key).unwrap_or(true)
    });
    sitemap::sitemap_xml(&routes, &brand.canonical_origin())
}

#[test]
#[ignore = "needs a built apps/web dist; run with --ignored and NF_WEB_DIST (see module doc comment)"]
fn robots_txt_matches_dist_byte_for_byte() {
    for theme in [Theme::Clinical, Theme::Cosmos] {
        let dist = require_dist_file(theme, "robots.txt");
        // Reads the reference dist's own stage (from its _headers.json) rather than assuming
        // preview, same reasoning as the headers tests - see dist_headers_meta.
        let (stage, _host, _active) = dist_headers_meta(theme);
        let generated = generated_robots_txt(theme, stage);
        let diffs = line_diff(&dist, &generated);
        assert!(
            diffs.is_empty(),
            "{} robots.txt: {} diff line(s) vs apps/web/dist:\n{}",
            theme.as_str(),
            diffs.len(),
            diffs.join("\n")
        );
    }
}

#[test]
#[ignore = "needs a built apps/web dist; run with --ignored and NF_WEB_DIST (see module doc comment)"]
fn sitemap_xml_matches_dist_byte_for_byte() {
    for theme in [Theme::Clinical, Theme::Cosmos] {
        let dist = require_dist_file(theme, "sitemap.xml");
        let generated = generated_sitemap_xml();
        let diffs = line_diff(&dist, &generated);
        assert!(
            diffs.is_empty(),
            "{} sitemap.xml: {} diff line(s) vs apps/web/dist:\n{}",
            theme.as_str(),
            diffs.len(),
            diffs.join("\n")
        );
    }
}

/// web-queen T-headers: byte parity for `_headers`, checked against whatever host/stage the
/// reference dist was actually built with (`dist_headers_meta`) - today that's SITE_HOST=cloudflare,
/// SITE_STAGE=preview, no active SEC-150 exceptions (`docs/hive/HEADERS-MATRIX.md`). If the dist is
/// ever built with SITE_HOST=netlify instead, this test exercises that path too.
#[test]
#[ignore = "needs a built apps/web dist; run with --ignored and NF_WEB_DIST (see module doc comment)"]
fn headers_txt_matches_dist_byte_for_byte() {
    for theme in [Theme::Clinical, Theme::Cosmos] {
        let dist = require_dist_file(theme, "_headers");
        let (stage, host, active_routes) = dist_headers_meta(theme);
        let (generated, _json) = generated_headers(theme, stage, host, &active_routes);
        let diffs = line_diff(&dist, &generated);
        assert!(
            diffs.is_empty(),
            "{} _headers ({}, {}): {} diff line(s) vs apps/web/dist:\n{}",
            theme.as_str(),
            host.as_str(),
            stage.as_str(),
            diffs.len(),
            diffs.join("\n")
        );
    }
}

#[test]
#[ignore = "needs a built apps/web dist; run with --ignored and NF_WEB_DIST (see module doc comment)"]
fn headers_json_matches_dist_byte_for_byte() {
    for theme in [Theme::Clinical, Theme::Cosmos] {
        let dist = require_dist_file(theme, "_headers.json");
        let (stage, host, active_routes) = dist_headers_meta(theme);
        let (_text, generated) = generated_headers(theme, stage, host, &active_routes);
        let diffs = line_diff(&dist, &generated);
        assert!(
            diffs.is_empty(),
            "{} _headers.json ({}, {}): {} diff line(s) vs apps/web/dist:\n{}",
            theme.as_str(),
            host.as_str(),
            stage.as_str(),
            diffs.len(),
            diffs.join("\n")
        );
    }
}
