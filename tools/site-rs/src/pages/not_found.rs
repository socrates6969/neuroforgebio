//! Port of `apps/web/src/pages/404.astro` (via `Base.astro`, `@nf/ui`'s `Nav`/`Footer`/`LangSwitch`,
//! the theme package's `BrandMark`).
//!
//! **Templating strategy (PLAN.md Stage 2, first HTML page - read this before porting the next
//! one):** Astro's compiler output is not something this crate reimplements. Its exact whitespace
//! collapsing, `data-astro-cid-*` scoped-style hashes (one per `.astro`/`@nf/ui` component, stable
//! for a given component's *content* but otherwise opaque - Astro's own internal hash), and Vite's
//! content-hashed `_assets/*.css` filenames all come from running the real Astro/Vite build, which
//! this crate cannot do (RUST-POLICY.md: no node build step here, only verification scripts).
//! Reverse-engineering that compiler behaviour in Rust well enough to regenerate it from first
//! principles is not a tractable goal for a parity-checked port.
//!
//! Instead: `templates/404.{clinical,cosmos}.html` are **exact byte copies** of the reference dist's
//! `404.html` for each theme, with the page's handful of genuinely dynamic values (everything that
//! comes from `content/site.json`'s `notFound`, via `Base.astro`'s `title`/`description`/`canonical`
//! props) replaced by `@@SENTINEL@@` tokens at fixed points - not reconstructed from a model of
//! Astro's output, but the golden output itself with holes cut in it. `render()` below fills those
//! holes back in from the same content source Astro reads. This is honest about what's ported (the
//! content plumbing) and what isn't (Astro's compiler and Vite's bundler) - and the byte-diff test
//! (`tests/pages_parity.rs`) will catch it immediately if either the content changes in a way this
//! doesn't track, or (more seriously) if a component the copied boilerplate depends on changes and
//! silently drifts the astro-cid hashes or asset filenames out from under this frozen copy. That
//! second failure mode is a real, known fragility of this approach: it is not detected until the
//! parity test is next run against a fresh dist, not at the moment the drift happens.
//!
//! **This actually happened already** (2026-09-27, `chore/ci-site-hardening` merge to main
//! `f8917e8`): the two shared CSS chunk hrefs renamed from `api.<hash>.css`/`index.<hash>.css` to
//! `_guide_.<hash>.css`/`_guide_.<hash>.css` (same hashes, different Vite chunk-group name - some
//! other page's addition regrouped them), caught immediately by `tests/pages_parity.rs`, fixed by
//! updating the two literal hrefs in both templates. Confirms the design works as intended: real
//! drift, caught, cheap to fix.

use crate::content::substitute_tokens;
use crate::theme::Theme;
use serde::Deserialize;
use std::path::Path;

const TEMPLATE_CLINICAL: &str = include_str!("../../templates/404.clinical.html");
const TEMPLATE_COSMOS: &str = include_str!("../../templates/404.cosmos.html");

#[derive(Debug, Deserialize)]
struct Meta {
    title: String,
    description: String,
}

#[derive(Debug, Deserialize)]
struct HomeLink {
    label: String,
    href: String,
}

#[derive(Debug, Deserialize)]
struct RawNotFound {
    meta: Meta,
    heading: String,
    body: String,
    #[serde(rename = "homeLink")]
    home_link: HomeLink,
}

#[derive(Debug, Deserialize)]
struct RawSite {
    #[serde(rename = "notFound")]
    not_found: RawNotFound,
}

/// `site.notFound` (`content/site.json`), with `{brand}`-style tokens already substituted.
#[derive(Debug, Clone)]
pub struct NotFoundContent {
    pub title: String,
    pub description: String,
    /// Raw HTML (Astro renders this with `set:html`, i.e. unescaped) - e.g. `This page <em>does not
    /// exist.</em>`.
    pub heading: String,
    pub body: String,
    pub home_href: String,
    pub home_label: String,
}

impl NotFoundContent {
    pub fn load(repo_root: &Path, vars: &[(&str, String)]) -> std::io::Result<NotFoundContent> {
        let text = std::fs::read_to_string(repo_root.join("packages/content/content/site.json"))?;
        let site: RawSite =
            serde_json::from_str(&text).map_err(|e| std::io::Error::other(e.to_string()))?;
        let nf = site.not_found;
        Ok(NotFoundContent {
            title: substitute_tokens(&nf.meta.title, vars),
            description: substitute_tokens(&nf.meta.description, vars),
            heading: substitute_tokens(&nf.heading, vars),
            body: substitute_tokens(&nf.body, vars),
            home_href: substitute_tokens(&nf.home_link.href, vars),
            home_label: substitute_tokens(&nf.home_link.label, vars),
        })
    }
}

/// Renders `/404` for `theme`. `canonical` is `sitemap::canonical_url("/404", origin)` (this page
/// doesn't need anything else `Base.astro` computes: no hreflang alternates for `/404` - see
/// `apps/web/src/lib/i18n.ts`'s `alternates()`, which returns `[]` for any path not in `alternates`'
/// own path list).
pub fn render(theme: Theme, content: &NotFoundContent, canonical: &str) -> String {
    let template = match theme {
        Theme::Clinical => TEMPLATE_CLINICAL,
        Theme::Cosmos => TEMPLATE_COSMOS,
    };
    template
        .replace("@@TITLE@@", &content.title)
        .replace("@@DESCRIPTION@@", &content.description)
        .replace("@@CANONICAL@@", canonical)
        .replace("@@HEADING@@", &content.heading)
        .replace("@@BODY@@", &content.body)
        .replace("@@HOME_HREF@@", &content.home_href)
        .replace("@@HOME_LABEL@@", &content.home_label)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn content() -> NotFoundContent {
        NotFoundContent {
            title: "Page not found · NeuroForge Bio".to_string(),
            description: "This page does not exist.".to_string(),
            heading: "This page <em>does not exist.</em>".to_string(),
            body: "The link may be wrong, or the page may have moved. The home page lists \
                   everything that is published."
                .to_string(),
            home_href: "/".to_string(),
            home_label: "Back to the home page".to_string(),
        }
    }

    #[test]
    fn render_leaves_no_sentinel_tokens_behind() {
        for theme in [Theme::Clinical, Theme::Cosmos] {
            let out = render(theme, &content(), "https://neuroforge-bio.invalid/404/");
            assert!(
                !out.contains("@@"),
                "{theme:?} output still has a sentinel token:\n{out}"
            );
        }
    }

    #[test]
    fn render_places_theme_specific_data_theme_attribute() {
        let clinical = render(Theme::Clinical, &content(), "https://x.invalid/404/");
        assert!(clinical.contains(r#"data-theme="clinical""#));
        let cosmos = render(Theme::Cosmos, &content(), "https://x.invalid/404/");
        assert!(cosmos.contains(r#"data-theme="cosmos""#));
    }

    #[test]
    fn render_substitutes_the_canonical_url_into_both_spots() {
        let out = render(Theme::Clinical, &content(), "https://x.invalid/404/");
        assert_eq!(
            out.matches("https://x.invalid/404/").count(),
            2,
            "canonical link + og:url"
        );
    }
}
