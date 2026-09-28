//! Rust static-site generator for `apps/web` (ORG-PLAN.md Hive 1 `nfb-site-rs`). See PLAN.md for
//! scope, the page inventory, and the known main-vs-golden-dist divergence.
//!
//! Usage: `site-rs <repo-root> <clinical|cosmos> <out-dir>` — currently emits `robots.txt` and
//! `sitemap.xml` only (Stage 2 items 2-3); HTML pages are not implemented yet.

use site_rs::{content, headers::Stage, robots, sitemap, theme::Theme};
use std::path::PathBuf;

fn main() -> std::io::Result<()> {
    let args: Vec<String> = std::env::args().collect();
    let (Some(repo_root), Some(theme_arg), Some(out_dir)) = (args.get(1), args.get(2), args.get(3))
    else {
        eprintln!("usage: site-rs <repo-root> <clinical|cosmos> <out-dir>");
        std::process::exit(2);
    };
    let repo_root = PathBuf::from(repo_root);
    let Some(theme) = Theme::parse(theme_arg) else {
        eprintln!("theme must be clinical or cosmos, got {theme_arg}");
        std::process::exit(2);
    };
    let out_dir = PathBuf::from(out_dir);
    std::fs::create_dir_all(&out_dir)?;

    // Same default as apps/web's resolveStage(): read SITE_STAGE, default "preview".
    let stage = Stage::resolve(std::env::var("SITE_STAGE").ok().as_deref())
        .map_err(std::io::Error::other)?;

    let brand = content::Brand::load(&repo_root)?;
    let origin = brand.canonical_origin();

    std::fs::write(
        out_dir.join("robots.txt"),
        robots::robots_txt(theme, stage, &origin),
    )?;

    let docs_routes = content::docs_routes(&repo_root)?;
    let routes = sitemap::sitemap_routes(&docs_routes, |key| {
        content::legal_is_draft(&repo_root, key).unwrap_or(true)
    });
    std::fs::write(
        out_dir.join("sitemap.xml"),
        sitemap::sitemap_xml(&routes, &origin),
    )?;

    eprintln!(
        "[site-rs] wrote {}/{{robots.txt,sitemap.xml}} for theme={} (HTML pages not implemented yet, see PLAN.md)",
        out_dir.display(),
        theme.as_str()
    );
    Ok(())
}
