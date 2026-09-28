//! Port of `apps/web/src/pages/sitemap.xml.ts` + `sitemapRoutes()`/`canonicalUrl()` from
//! `apps/web/src/lib/site.ts` (main branch). See PLAN.md Stage 2 item 3.
//!
//! `DOCS_ROUTES` (from `lib/docs.ts`) is computed by `content::docs_routes()` (reads each
//! `docs/quickstarts/*.json`'s `order` field and sorts by it - docs.ts sorts quickstarts by `order`,
//! not filename) and passed in by callers as `docs_routes`, rather than hardcoded here, so a caller
//! that (deliberately, e.g. in a focused unit test) passes `&[]` gets a visibly short route list
//! instead of a silently wrong one.

use crate::content::{GENERIC_PAGE_KEYS, LEGAL_KEYS, WHITEPAPER_SLUGS};

/// `canonicalUrl()` in `lib/site.ts`.
pub fn canonical_url(pathname: &str, canonical_origin: &str) -> String {
    let mut p = pathname.to_string();
    if let Some(stripped) = p.strip_suffix("index.html") {
        p = stripped.to_string();
    } else if let Some(stripped) = p.strip_suffix(".html") {
        p = stripped.to_string();
    }
    if !p.starts_with('/') {
        p = format!("/{p}");
    }
    if p != "/" && !p.ends_with('/') {
        p = format!("{p}/");
    }
    format!("{}{}", canonical_origin.trim_end_matches('/'), p)
}

/// `sitemapRoutes()` in `lib/site.ts`. `legal_is_draft(key)` mirrors
/// `content.locales.en.legal[k].draft`; `docs_routes` mirrors `DOCS_ROUTES` (see module doc comment).
pub fn sitemap_routes(
    docs_routes: &[String],
    legal_is_draft: impl Fn(&str) -> bool,
) -> Vec<String> {
    let mut routes = vec!["/".to_string()];
    for key in GENERIC_PAGE_KEYS {
        routes.push(format!("/{key}/"));
    }
    routes.push("/security/".to_string());
    routes.push("/no/security/".to_string());
    routes.push("/law-tracker/".to_string());
    // Added to main 2026-09-27 by the feature/neural-playground merge (6a79900), after this crate's
    // first commit - not in the m5 golden dist at all (that branch predates it).
    routes.push("/playground/".to_string());
    routes.push("/interface/".to_string());
    routes.push("/research/".to_string());
    for slug in WHITEPAPER_SLUGS {
        routes.push(format!("/research/{slug}/"));
    }
    routes.extend(docs_routes.iter().cloned());
    for key in LEGAL_KEYS {
        if !legal_is_draft(key) {
            routes.push(format!("/legal/{key}/"));
            routes.push(format!("/no/legal/{key}/"));
        }
    }
    routes
}

/// Body of `/sitemap.xml`, byte-identical to `sitemap.xml.ts`'s `Response` body.
pub fn sitemap_xml(routes: &[String], canonical_origin: &str) -> String {
    let urls = routes
        .iter()
        .map(|r| {
            format!(
                "  <url><loc>{}</loc></url>",
                canonical_url(r, canonical_origin)
            )
        })
        .collect::<Vec<_>>()
        .join("\n");
    format!(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n{urls}\n</urlset>\n"
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    const ORIGIN: &str = "https://neuroforge-bio.invalid";

    #[test]
    fn canonical_url_normalises_trailing_slash() {
        assert_eq!(
            canonical_url("/platform/", ORIGIN),
            "https://neuroforge-bio.invalid/platform/"
        );
        assert_eq!(
            canonical_url("/", ORIGIN),
            "https://neuroforge-bio.invalid/"
        );
    }

    #[test]
    fn routes_match_mains_sitemap_routes_minus_docs() {
        // Pure-function unit test: docs_routes=&[] here on purpose, to check the non-docs route
        // order/content in isolation. tests/parity.rs (with content::docs_routes() wired in) is what
        // checks the real, full route list - including docs - against an actual built dist.
        // All 4 legal keys are draft:true on main today, so they're excluded here too.
        let routes = sitemap_routes(&[], |_key| true);
        assert_eq!(
            routes,
            vec![
                "/",
                "/platform/",
                "/governance/",
                "/sdks/",
                "/pricing/",
                "/security/",
                "/no/security/",
                "/law-tracker/",
                "/playground/",
                "/interface/",
                "/research/",
                "/research/somatosensory-closed-loop/",
            ]
        );
    }

    #[test]
    fn xml_renders_one_url_element_per_route_in_order() {
        let routes = vec!["/".to_string(), "/platform/".to_string()];
        let expected = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n  <url><loc>https://neuroforge-bio.invalid/</loc></url>\n  <url><loc>https://neuroforge-bio.invalid/platform/</loc></url>\n</urlset>\n";
        assert_eq!(sitemap_xml(&routes, ORIGIN), expected);
    }
}
