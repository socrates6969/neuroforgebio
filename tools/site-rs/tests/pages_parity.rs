//! HTML page byte-parity tests (PLAN.md Stage 2 item 5, first page). Same pattern as
//! `tests/parity.rs`: `#[ignore]`d by default (CI never builds `apps/web/dist`), reference dist root
//! from `NF_WEB_DIST` (defaults to a path that doesn't exist in this worktree). See
//! `src/pages/not_found.rs`'s module doc comment for the templating strategy and its known
//! fragility (frozen golden HTML with content holes, not a from-scratch Astro-compiler port).
//!
//! Run: `NF_WEB_DIST=<dist root> cargo test -p site-rs --test pages_parity -- --ignored`

use site_rs::content::Brand;
use site_rs::pages::not_found;
use site_rs::sitemap::canonical_url;
use site_rs::theme::Theme;
use std::path::{Path, PathBuf};

fn repo_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .expect("repo root")
}

fn dist_root() -> PathBuf {
    match std::env::var("NF_WEB_DIST") {
        Ok(v) if !v.trim().is_empty() => PathBuf::from(v),
        _ => repo_root().join("apps/web/dist"),
    }
}

fn require_dist_file(theme: Theme, rel: &str) -> String {
    let path = dist_root().join(theme.as_str()).join(rel);
    std::fs::read_to_string(&path).unwrap_or_else(|e| {
        panic!(
            "build the site first: could not read {} ({e}). Set NF_WEB_DIST to an existing \
             apps/web/dist (see module doc comment).",
            path.display()
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
                "  line {}: dist={:?} generated={:?}",
                i + 1,
                e.get(i),
                a.get(i)
            ));
        }
    }
    if e.len() != a.len() {
        diffs.push(format!(
            "  (dist has {} lines, generated has {})",
            e.len(),
            a.len()
        ));
    }
    diffs
}

#[test]
#[ignore = "needs a built apps/web dist; run with --ignored and NF_WEB_DIST (see module doc comment)"]
fn not_found_matches_dist_byte_for_byte() {
    let root = repo_root();
    let brand = Brand::load(&root).expect("load brand.json");
    let vars = brand.vars();
    let content = not_found::NotFoundContent::load(&root, &vars).expect("load site.json notFound");
    let origin = brand.canonical_origin();

    for theme in [Theme::Clinical, Theme::Cosmos] {
        let dist = require_dist_file(theme, "404.html");
        let canonical = canonical_url("/404", &origin);
        let generated = not_found::render(theme, &content, &canonical);
        let diffs = line_diff(&dist, &generated);
        assert!(
            diffs.is_empty(),
            "{} 404.html: {} diff line(s) vs apps/web/dist:\n{}",
            theme.as_str(),
            diffs.len(),
            diffs.join("\n")
        );
    }
}

#[test]
#[ignore = "needs a built apps/web dist; run with --ignored and NF_WEB_DIST (see module doc comment)"]
fn not_found_content_loads_from_real_site_json() {
    // Sanity check independent of the dist: the real content file parses and substitutes cleanly
    // (catches a schema drift even if NF_WEB_DIST is stale for some other reason).
    let root = repo_root();
    let brand = Brand::load(&root).expect("load brand.json");
    let content = not_found::NotFoundContent::load(&root, &brand.vars()).expect("load notFound");
    assert!(
        content.title.contains(&brand.name),
        "title should carry the substituted brand name"
    );
    assert!(
        !content.title.contains('{'),
        "no leftover {{token}} after substitution"
    );
}
