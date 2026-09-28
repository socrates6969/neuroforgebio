//! Port of `apps/web/src/pages/robots.txt.ts` + `apps/web/indexing.mjs`'s `robotsTxt()` (main
//! branch, `chore/ci-site-hardening` merged 2026-09-27, `f8917e8`). Text-only, no HTML templating,
//! so it needed no reverse-engineering of Astro's compiler output — see PLAN.md Stage 2 item 2.
//!
//! `chore/ci-site-hardening` moved `robotsTxt()`'s logic into `indexing.mjs` and made it
//! stage-aware: on a non-indexable stage (`preview`, the default - see `headers::Stage`) it
//! short-circuits to a totally different, crawler-blocking body, regardless of theme.

use crate::headers::Stage;
use crate::theme::Theme;

/// `new URL(path, origin).href` for the one case this file needs: an absolute path joined onto an
/// origin with no path/query of its own (true for every `CANONICAL_ORIGIN` value in this repo).
fn url_join(origin: &str, absolute_path: &str) -> String {
    format!("{}{}", origin.trim_end_matches('/'), absolute_path)
}

/// Body of `/robots.txt` for `theme` at `stage`, byte-identical to `indexing.mjs`'s `robotsTxt()`.
pub fn robots_txt(theme: Theme, stage: Stage, canonical_origin: &str) -> String {
    if !stage.is_indexable() {
        return format!(
            "# SITE_STAGE={}: preview builds are not for search engines.\nUser-agent: *\nDisallow: /\n",
            stage.as_str()
        );
    }
    let mut lines: Vec<String> = vec![
        "User-agent: *".into(),
        "Allow: /".into(),
        "Disallow: /gallery/".into(),
    ];
    lines.push(String::new());
    match theme {
        Theme::Clinical => {
            lines.push(format!(
                "Sitemap: {}",
                url_join(canonical_origin, "/sitemap.xml")
            ));
        }
        Theme::Cosmos => {
            lines.push(format!(
                "# Secondary host (theme: {}). Canonical URLs point to {}",
                theme.as_str(),
                canonical_origin
            ));
        }
    }
    let mut body = lines.join("\n");
    body.push('\n');
    body
}

#[cfg(test)]
mod tests {
    use super::*;

    // Hand-derived from robots.txt.ts/indexing.mjs, not from a golden dist (see module doc comment).
    const ORIGIN: &str = "https://neuroforge-bio.invalid";

    #[test]
    fn clinical_has_sitemap_line_when_indexable() {
        let expected = "User-agent: *\nAllow: /\nDisallow: /gallery/\n\nSitemap: https://neuroforge-bio.invalid/sitemap.xml\n";
        assert_eq!(robots_txt(Theme::Clinical, Stage::Launch, ORIGIN), expected);
        assert_eq!(robots_txt(Theme::Clinical, Stage::Public, ORIGIN), expected);
    }

    #[test]
    fn cosmos_has_secondary_host_comment_not_sitemap_when_indexable() {
        let expected = "User-agent: *\nAllow: /\nDisallow: /gallery/\n\n# Secondary host (theme: cosmos). Canonical URLs point to https://neuroforge-bio.invalid\n";
        assert_eq!(robots_txt(Theme::Cosmos, Stage::Launch, ORIGIN), expected);
    }

    #[test]
    fn preview_stage_blocks_everything_regardless_of_theme() {
        let expected = "# SITE_STAGE=preview: preview builds are not for search engines.\nUser-agent: *\nDisallow: /\n";
        assert_eq!(
            robots_txt(Theme::Clinical, Stage::Preview, ORIGIN),
            expected
        );
        assert_eq!(robots_txt(Theme::Cosmos, Stage::Preview, ORIGIN), expected);
    }

    #[test]
    fn ends_with_exactly_one_trailing_newline() {
        for stage in [Stage::Preview, Stage::Launch, Stage::Public] {
            let out = robots_txt(Theme::Clinical, stage, ORIGIN);
            assert!(out.ends_with('\n') && !out.ends_with("\n\n"), "{stage:?}");
        }
    }
}
