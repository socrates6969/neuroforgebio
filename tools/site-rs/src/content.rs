//! Minimal loader for the `packages/content` JSON sources this generator needs so far
//! (PLAN.md Stage 1 "content sources", Stage 2 items 1-3). Grows as more pages are ported.

use serde::Deserialize;
use std::path::Path;

#[derive(Debug, Deserialize)]
pub struct CodeIdentifiers {
    #[serde(rename = "pythonImport")]
    pub python_import: String,
}

#[derive(Debug, Deserialize)]
pub struct Brand {
    pub name: String,
    #[serde(rename = "legalName")]
    pub legal_name: String,
    pub domain: String,
    #[allow(dead_code)]
    #[serde(rename = "secondaryHost")]
    pub secondary_host: String,
    #[serde(rename = "codeIdentifiers")]
    pub code_identifiers: CodeIdentifiers,
}

impl Brand {
    /// astro.config.mjs: `const canonicalOrigin = \`https://${brand.domain}\`;`
    pub fn canonical_origin(&self) -> String {
        format!("https://{}", self.domain)
    }

    pub fn load(repo_root: &Path) -> std::io::Result<Brand> {
        let text = std::fs::read_to_string(repo_root.join("packages/content/brand.json"))?;
        serde_json::from_str(&text).map_err(|e| std::io::Error::other(e.to_string()))
    }

    /// `brandVars()` in `packages/content/src/index.ts`: the `{brand}`/`{legalName}`/`{domain}`/
    /// `{origin}`/`{pkg}` values `substitute()` fills content strings with.
    pub fn vars(&self) -> Vec<(&str, String)> {
        vec![
            ("brand", self.name.clone()),
            ("legalName", self.legal_name.clone()),
            ("domain", self.domain.clone()),
            ("origin", self.canonical_origin()),
            ("pkg", self.code_identifiers.python_import.clone()),
        ]
    }
}

/// `substitute()` in `packages/content/src/validate.ts`: replaces `{token}` with `vars[token]`,
/// leaving an unknown token untouched (mirrors `k in vars ? vars[k] : m`).
pub fn substitute_tokens(text: &str, vars: &[(&str, String)]) -> String {
    let mut out = String::with_capacity(text.len());
    let bytes = text.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] == b'{'
            && let Some(end) = text[i + 1..].find('}')
        {
            let key = &text[i + 1..i + 1 + end];
            if key.chars().all(|c| c.is_ascii_alphabetic())
                && let Some((_, v)) = vars.iter().find(|(k, _)| *k == key)
            {
                out.push_str(v);
                i += end + 2;
                continue;
            }
        }
        let ch = text[i..].chars().next().unwrap();
        out.push(ch);
        i += ch.len_utf8();
    }
    out
}

#[derive(Debug, Deserialize)]
pub struct LegalDoc {
    pub draft: bool,
}

/// `LEGAL_KEYS` in `apps/web/src/lib/site.ts`.
pub const LEGAL_KEYS: [&str; 4] = ["privacy", "terms", "cookies", "company"];

/// Whether `content/legal/{key}.en.json` is a draft (drives noindex + sitemap exclusion, both locales
/// share one `draft` flag pair-wise on main today).
pub fn legal_is_draft(repo_root: &Path, key: &str) -> std::io::Result<bool> {
    let text = std::fs::read_to_string(
        repo_root.join(format!("packages/content/content/legal/{key}.en.json")),
    )?;
    let doc: LegalDoc =
        serde_json::from_str(&text).map_err(|e| std::io::Error::other(e.to_string()))?;
    Ok(doc.draft)
}

/// `genericPages` keys in `apps/web/src/lib/site.ts` (insertion order matters for the sitemap).
pub const GENERIC_PAGE_KEYS: [&str; 4] = ["platform", "governance", "sdks", "pricing"];

/// `content.whitepapers` keys. Hand-enumerated for now (one entry on main); switch to reading
/// `packages/content/content/research/*.json` directory listing once more than one exists.
pub const WHITEPAPER_SLUGS: [&str; 1] = ["somatosensory-closed-loop"];

#[derive(Debug, Deserialize)]
struct DocOrder {
    order: i64,
}

/// Slugs of every `*.json` file directly under `dir`, sorted by that file's `order` field (not
/// filename) - shared by `guides` and `quickstarts` in `apps/web/src/lib/docs.ts`, both built the
/// same way via `import.meta.glob(...).sort((a, b) => a.order - b.order)`.
fn slugs_sorted_by_order(dir: &Path) -> std::io::Result<Vec<String>> {
    let mut entries: Vec<(i64, String)> = Vec::new();
    for entry in std::fs::read_dir(dir)? {
        let path = entry?.path();
        if path.extension().and_then(|e| e.to_str()) != Some("json") {
            continue;
        }
        let slug = path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or_default()
            .to_string();
        let text = std::fs::read_to_string(&path)?;
        let doc: DocOrder =
            serde_json::from_str(&text).map_err(|e| std::io::Error::other(e.to_string()))?;
        entries.push((doc.order, slug));
    }
    entries.sort_by_key(|(order, _)| *order);
    Ok(entries.into_iter().map(|(_, slug)| slug).collect())
}

/// `DOCS_ROUTES` in `apps/web/src/lib/docs.ts`: `['/docs/', ...guides sorted by "order", ...quickstarts
/// sorted by "order", '/docs/api/', '/docs/changelog/']` (guides added 2026-09-27,
/// `chore/ci-site-hardening`: SDK guides like `docs/guides/{c-abi,python-sdk}.json`, routed at
/// `/docs/<slug>/` - NOT under `/docs/quickstart/`, unlike quickstarts). Reads both directories'
/// `order` fields directly rather than hand-enumerating, so a new file picks itself up.
pub fn docs_routes(repo_root: &Path) -> std::io::Result<Vec<String>> {
    let guides = slugs_sorted_by_order(&repo_root.join("apps/web/src/docs/guides"))?;
    let quickstarts = slugs_sorted_by_order(&repo_root.join("apps/web/src/docs/quickstarts"))?;

    let mut routes = vec!["/docs/".to_string()];
    routes.extend(guides.into_iter().map(|slug| format!("/docs/{slug}/")));
    routes.extend(
        quickstarts
            .into_iter()
            .map(|slug| format!("/docs/quickstart/{slug}/")),
    );
    routes.push("/docs/api/".to_string());
    routes.push("/docs/changelog/".to_string());
    Ok(routes)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn vars() -> Vec<(&'static str, String)> {
        vec![
            ("brand", "NeuroForge Bio".to_string()),
            ("pkg", "neuroforge".to_string()),
        ]
    }

    #[test]
    fn substitutes_a_known_token() {
        assert_eq!(
            substitute_tokens("Page not found · {brand}", &vars()),
            "Page not found · NeuroForge Bio"
        );
    }

    #[test]
    fn leaves_an_unknown_token_untouched() {
        assert_eq!(substitute_tokens("{unknown}", &vars()), "{unknown}");
    }

    #[test]
    fn handles_multiple_and_adjacent_tokens() {
        assert_eq!(
            substitute_tokens("{brand}{pkg}", &vars()),
            "NeuroForge Bioneuroforge"
        );
    }

    #[test]
    fn does_not_touch_braces_that_are_not_alphabetic_tokens() {
        // e.g. JSON-ish or code-sample text that happens to contain braces
        assert_eq!(substitute_tokens("{1brand}", &vars()), "{1brand}");
    }
}
