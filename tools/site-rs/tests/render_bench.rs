//! Measured (not estimated) timing for `site-rs`'s current rendering work, for the "measured"
//! section of `docs/hive/site-rs-skipped-routes.md` (web-queen ask, 2026-09-27). Isolates pure
//! computation (`std::time::Instant` around N iterations, in-process, no process-startup or I/O
//! overhead beyond the one JSON read each function already does) from whole-process wall time,
//! which a separate `hive-peakmem`-wrapped run of the release binary measures instead.
//!
//! Only covers what this branch can actually render: `robots.txt` + `sitemap.xml` generation
//! (`main.rs`'s only real output today). `not_found::render()` (404 HTML) has since landed on
//! `main` (merged via `feature/site-rs-pages`) but isn't included here yet - this benchmark still
//! needs extending to cover it, per web-queen's follow-up ask; the numbers below are unaffected by
//! that landing.
//!
//! **2026-09-27 fixup**: `robots::robots_txt()` gained a `Stage` parameter when APP-L8
//! (`chore/ci-site-hardening`) merged to main - a non-indexable stage (`Stage::Preview`, the
//! default) makes it short-circuit to a few fixed lines instead of doing the real per-theme
//! generation this benchmark means to measure. Pinned to `Stage::Public` here (indexable, so the
//! full path runs) specifically to keep measuring the same work as before, not because `Public` is
//! this crate's actual default (`main.rs` defaults to `Preview`, matching `resolveStage()`). The
//! numbers themselves don't need re-running: this is the same code path/inputs as before, just with
//! an explicit stage argument that wasn't previously a parameter.
//!
//! `#[ignore]`d: not a correctness test, and printing timing numbers under normal `cargo test` runs
//! would be noise. Run: `cargo test --release -p site-rs --test render_bench -- --ignored --nocapture`

use site_rs::{content, headers::Stage, robots, sitemap, theme::Theme};
use std::time::Instant;

const ITERATIONS: u32 = 10_000;

#[test]
#[ignore = "prints measured timing, not a correctness check; run with --release --ignored --nocapture"]
fn robots_txt_and_sitemap_xml_render_cost() {
    let root = repo_root();
    let brand = content::Brand::load(&root).expect("load brand.json");
    let origin = brand.canonical_origin();
    let docs_routes = content::docs_routes(&root).expect("docs_routes");
    let routes = sitemap::sitemap_routes(&docs_routes, |key| {
        content::legal_is_draft(&root, key).unwrap_or(true)
    });

    for theme in [Theme::Clinical, Theme::Cosmos] {
        let start = Instant::now();
        for _ in 0..ITERATIONS {
            std::hint::black_box(robots::robots_txt(theme, Stage::Public, &origin));
            std::hint::black_box(sitemap::sitemap_xml(&routes, &origin));
        }
        let elapsed = start.elapsed();
        eprintln!(
            "[render_bench] {}: {ITERATIONS} iterations of (robots_txt + sitemap_xml) in {:?} \
             ({:?}/iteration)",
            theme.as_str(),
            elapsed,
            elapsed / ITERATIONS
        );
    }
}

/// Same resolution as every other test file (`tests/parity.rs` etc.).
fn repo_root() -> std::path::PathBuf {
    std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .expect("repo root")
}
