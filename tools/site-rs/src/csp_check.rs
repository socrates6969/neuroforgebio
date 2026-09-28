//! Port of the wasm-reachability trigger from `apps/web/scripts/csp-check.mjs`
//! (`reachableScripts`, `reachableWasm`, `exceptionsInUse`) - review gap 1
//! (`docs/hive/REVIEW-site-rs-headers.md` on `web/headers @34dc115`, web-headers/team-lead ruling
//! 2026-09-27). This is what decides whether a built SEC-150 exception route is actually *active*:
//! a route being built is not enough, a page under it must reach a `.wasm` file, transitively
//! through same-origin scripts, confined to the dist root.
//!
//! **Simplified vs. JS**: script entry points are `<script src="...">` and `<link
//! rel="modulepreload" href="...">` (Astro emits the latter for module chunks it wants preloaded -
//! web-headers' review, 2026-09-27 re-review at `web/headers @c9dc2fe`, item a). Every other
//! `htmlRefs()` tag kind (stylesheets, images, iframes, ...) is still not ported - none of those can
//! carry an executable script reference, so they're irrelevant to the wasm-reachability question this
//! module answers, unlike gap 5's full conformance scan.
//!
//! **Fail-strict** (review gap 1's explicit requirement, sharpened per web-headers' nice-to-have item
//! b): a file read failure anywhere in the reachability walk propagates all the way up and fails the
//! *whole* detection strict (`[]`, reason reported) - exactly like JS, where `readFileSync` throws
//! uncaught inside `reachableScripts`/`reachableWasm` and only `exceptionsInUse`'s outer `try/catch`
//! stops it. `reachable_scripts`/`reachable_wasm` therefore return `io::Result`, not a value that
//! silently drops files it couldn't read.

use crate::headers::CspException;
use regex::Regex;
use std::collections::HashSet;
use std::path::{Path, PathBuf};

fn walk(dir: &Path, out: &mut Vec<PathBuf>) -> std::io::Result<()> {
    for entry in std::fs::read_dir(dir)? {
        let path = entry?.path();
        if path.is_dir() {
            walk(&path, out)?;
        } else {
            out.push(path);
        }
    }
    Ok(())
}

/// `urlOf(dist, f)` (mirrors `postbuild.mjs`'s per-file `sitePaths()` conversion, for one file).
fn url_of(dist: &Path, file: &Path) -> String {
    let rel = file
        .strip_prefix(dist)
        .unwrap_or(file)
        .to_string_lossy()
        .replace('\\', "/");
    if rel == "index.html" {
        "/".to_string()
    } else if let Some(stripped) = rel.strip_suffix("/index.html") {
        format!("/{stripped}/")
    } else {
        format!("/{rel}")
    }
}

/// `/^[a-z]+:|^\/\//i` - an absolute URL with a scheme, or a protocol-relative URL: never resolved
/// into dist (external).
fn is_external(url: &str) -> bool {
    if url.starts_with("//") {
        return true;
    }
    match url.find(':') {
        Some(i) if i > 0 => url[..i].chars().all(|c| c.is_ascii_alphabetic()),
        _ => false,
    }
}

/// Lexically joins `rel` (forward-slash-separated, may contain `.`/`..`) onto `base`, without
/// touching the filesystem (mirrors `node:path`'s `resolve()` for our controlled, relative inputs).
fn lexical_join(base: &Path, rel: &str) -> PathBuf {
    let mut out = base.to_path_buf();
    for seg in rel.split('/') {
        match seg {
            "" | "." => {}
            ".." => {
                out.pop();
            }
            s => out.push(s),
        }
    }
    out
}

/// `distFile(dist, from, url)`: resolve a URL written in `from` to a dist file path, confined to
/// `dist`, or `None` (external, escapes dist, or doesn't exist).
fn dist_file(dist: &Path, from: &Path, url: &str) -> Option<PathBuf> {
    if is_external(url) {
        return None;
    }
    let clean = url.split(['?', '#']).next().unwrap_or(url);
    let f = if let Some(stripped) = clean.strip_prefix('/') {
        lexical_join(dist, stripped)
    } else {
        lexical_join(from.parent().unwrap_or(dist), clean)
    };
    if f.starts_with(dist) && f.is_file() {
        Some(f)
    } else {
        None
    }
}

fn attr_regex(name: &str) -> Regex {
    Regex::new(&format!(
        r#"(?is)\s{}\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))"#,
        regex::escape(name)
    ))
    .expect("valid attr regex")
}

fn captured_attr<'a>(caps: &regex::Captures<'a>) -> &'a str {
    caps.get(1)
        .or_else(|| caps.get(2))
        .or_else(|| caps.get(3))
        .map(|g| g.as_str().trim())
        .unwrap_or("")
}

/// Minimal `htmlRefs()`: `<script src>` and `<link rel="modulepreload" href>` (see module doc
/// comment "Simplified vs. JS" - the only two tag kinds that can introduce a script entry point).
fn html_script_srcs(html: &str) -> Vec<String> {
    let comment_re = Regex::new(r"(?s)<!--.*?-->").expect("valid regex");
    let stripped = comment_re.replace_all(html, "");
    let src_re = attr_regex("src");
    let href_re = attr_regex("href");
    let rel_re = attr_regex("rel");
    let mut out = Vec::new();

    let script_tag_re = Regex::new(r"(?is)<script\b[^>]*>").expect("valid regex");
    for m in script_tag_re.find_iter(&stripped) {
        if let Some(caps) = src_re.captures(m.as_str()) {
            let url = captured_attr(&caps);
            if !url.is_empty() && !url.starts_with('#') {
                out.push(url.to_string());
            }
        }
    }

    let link_tag_re = Regex::new(r"(?is)<link\b[^>]*>").expect("valid regex");
    for m in link_tag_re.find_iter(&stripped) {
        let tag = m.as_str();
        let is_modulepreload = rel_re
            .captures(tag)
            .map(|c| {
                captured_attr(&c)
                    .to_lowercase()
                    .split_whitespace()
                    .any(|w| w == "modulepreload")
            })
            .unwrap_or(false);
        if !is_modulepreload {
            continue;
        }
        if let Some(caps) = href_re.captures(tag) {
            let url = captured_attr(&caps);
            if !url.is_empty() && !url.starts_with('#') {
                out.push(url.to_string());
            }
        }
    }
    out
}

/// `import\(.../["'`]...\.m?js["'`]` style relative/absolute JS import string literals.
fn js_import_regex() -> Regex {
    Regex::new(r#"["'`]((?:\.{1,2}/|/)[^"'`\s]+\.m?js)["'`]"#).expect("valid regex")
}

fn wasm_ref_regex() -> Regex {
    Regex::new(r#"["'`]([^"'`\s]+\.wasm)(?:[?#][^"'`\s]*)?["'`]"#).expect("valid regex")
}

/// `reachableScripts(dist, htmlFile, html)`. Returns `Err` (instead of silently treating the file as
/// having no imports) if a same-origin script it needs to scan can't be read - a real fail-strict
/// signal, not a skip (web-headers' nice-to-have item b).
pub fn reachable_scripts(
    dist: &Path,
    html_file: &Path,
    html: &str,
) -> std::io::Result<Vec<PathBuf>> {
    let mut seen: HashSet<PathBuf> = HashSet::new();
    let mut queue: Vec<PathBuf> = Vec::new();
    for url in html_script_srcs(html) {
        if let Some(f) = dist_file(dist, html_file, &url)
            && seen.insert(f.clone())
        {
            queue.push(f);
        }
    }
    let import_re = js_import_regex();
    let mut i = 0;
    while i < queue.len() {
        let f = queue[i].clone();
        i += 1;
        let text = std::fs::read_to_string(&f).map_err(|e| {
            std::io::Error::new(
                e.kind(),
                format!(
                    "could not read {} while following script imports from {}: {e}",
                    f.display(),
                    html_file.display()
                ),
            )
        })?;
        for cap in import_re.captures_iter(&text) {
            if let Some(f2) = dist_file(dist, &f, &cap[1])
                && seen.insert(f2.clone())
            {
                queue.push(f2);
            }
        }
    }
    Ok(queue)
}

/// `reachableWasm(dist, htmlFile, html)`. See `reachable_scripts` for the fail-strict contract.
pub fn reachable_wasm(dist: &Path, html_file: &Path, html: &str) -> std::io::Result<Vec<PathBuf>> {
    let wasm_re = wasm_ref_regex();
    let mut out: HashSet<PathBuf> = HashSet::new();
    for cap in wasm_re.captures_iter(html) {
        if let Some(f) = dist_file(dist, html_file, &cap[1]) {
            out.insert(f);
        }
    }
    for js in reachable_scripts(dist, html_file, html)? {
        let text = std::fs::read_to_string(&js).map_err(|e| {
            std::io::Error::new(
                e.kind(),
                format!(
                    "could not read {} while scanning for .wasm refs: {e}",
                    js.display()
                ),
            )
        })?;
        for cap in wasm_re.captures_iter(&text) {
            if let Some(f) = dist_file(dist, &js, &cap[1]) {
                out.insert(f);
            }
        }
    }
    Ok(out.into_iter().collect())
}

fn exceptions_in_use_inner(
    dist: &Path,
    list: &[CspException],
) -> std::io::Result<Vec<CspException>> {
    let mut all = Vec::new();
    walk(dist, &mut all)?;
    let pages: Vec<PathBuf> = all
        .into_iter()
        .filter(|f| f.extension().and_then(|e| e.to_str()) == Some("html"))
        .collect();
    let mut active = Vec::new();
    for e in list {
        let mut is_active = false;
        for f in &pages {
            if url_of(dist, f).starts_with(&e.route) {
                let html = std::fs::read_to_string(f)?;
                if !reachable_wasm(dist, f, &html)?.is_empty() {
                    is_active = true;
                    break;
                }
            }
        }
        if is_active {
            active.push(e.clone());
        }
    }
    Ok(active)
}

/// `exceptionsInUse(dist, { list, onError })`. Fail-strict: any error -> `[]`, reason via `on_error`.
pub fn exceptions_in_use(
    dist: &Path,
    list: &[CspException],
    on_error: impl FnOnce(&std::io::Error),
) -> Vec<CspException> {
    match exceptions_in_use_inner(dist, list) {
        Ok(v) => v,
        Err(e) => {
            on_error(&e);
            Vec::new()
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::headers::CspException;
    use std::fs;

    /// A tiny RAII temp dir, so tests don't need a `tempfile`-style dependency just for this.
    struct TestTempDir(PathBuf);
    impl TestTempDir {
        fn new() -> Self {
            // web-queen: flaky under `cargo test`'s default parallel threads - nanos-since-epoch
            // alone collided when two tests hit the same clock tick (coarser resolution than
            // nanoseconds on some systems/under load). Add a process-wide atomic counter so two
            // calls in the same process can never produce the same path, regardless of clock
            // granularity or scheduling.
            use std::sync::atomic::{AtomicU64, Ordering};
            use std::time::{SystemTime, UNIX_EPOCH};
            static COUNTER: AtomicU64 = AtomicU64::new(0);
            let n = COUNTER.fetch_add(1, Ordering::Relaxed);
            let nanos = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos();
            let path = std::env::temp_dir().join(format!(
                "nf-csp-check-test-{}-{nanos}-{n}",
                std::process::id()
            ));
            fs::create_dir_all(&path).unwrap();
            TestTempDir(path)
        }
        fn path(&self) -> &Path {
            &self.0
        }
    }
    impl Drop for TestTempDir {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    fn exception() -> CspException {
        CspException {
            route: "/arena/".to_string(),
            directive: "script-src".to_string(),
            token: "'wasm-unsafe-eval'".to_string(),
        }
    }

    /// Builds a minimal dist: /arena/index.html -> script src /_assets/a.js -> imports ./b.js which
    /// references a .wasm; /security/index.html has no scripts at all.
    fn build_dist() -> TestTempDir {
        let dir = TestTempDir::new();
        let d = dir.path();
        fs::create_dir_all(d.join("arena")).unwrap();
        fs::create_dir_all(d.join("security")).unwrap();
        fs::create_dir_all(d.join("_assets")).unwrap();
        fs::write(
            d.join("arena/index.html"),
            r#"<html><body><script type="module" src="/_assets/a.js"></script></body></html>"#,
        )
        .unwrap();
        fs::write(
            d.join("security/index.html"),
            "<html><body>no scripts</body></html>",
        )
        .unwrap();
        fs::write(d.join("_assets/a.js"), r#"import("./b.js");"#).unwrap();
        fs::write(
            d.join("_assets/b.js"),
            r#"new URL("thing.Ab12Cd34.wasm", import.meta.url);"#,
        )
        .unwrap();
        fs::write(
            d.join("_assets/thing.Ab12Cd34.wasm"),
            [0u8, 97, 115, 109, 1, 0, 0, 0],
        )
        .unwrap();
        dir
    }

    #[test]
    fn arena_page_reaches_the_wasm_transitively() {
        let dir = build_dist();
        let d = dir.path();
        let html = fs::read_to_string(d.join("arena/index.html")).unwrap();
        let wasm = reachable_wasm(d, &d.join("arena/index.html"), &html).unwrap();
        assert_eq!(wasm.len(), 1);
        assert!(wasm[0].ends_with("thing.Ab12Cd34.wasm"));
    }

    #[test]
    fn security_page_with_no_scripts_reaches_nothing() {
        let dir = build_dist();
        let d = dir.path();
        let html = fs::read_to_string(d.join("security/index.html")).unwrap();
        assert!(
            reachable_wasm(d, &d.join("security/index.html"), &html)
                .unwrap()
                .is_empty()
        );
    }

    #[test]
    fn exceptions_in_use_activates_only_the_built_reaching_route() {
        let dir = build_dist();
        let d = dir.path();
        let list = vec![exception()];
        let active = exceptions_in_use(d, &list, |e| panic!("unexpected error: {e}"));
        assert_eq!(active.len(), 1);
        assert_eq!(active[0].route, "/arena/");
    }

    #[test]
    fn exceptions_in_use_is_empty_when_wasm_is_reachable_only_from_another_route() {
        let dir = TestTempDir::new();
        let d = dir.path();
        std::fs::create_dir_all(d.join("arena")).unwrap();
        std::fs::create_dir_all(d.join("security")).unwrap();
        std::fs::create_dir_all(d.join("_assets")).unwrap();
        std::fs::write(
            d.join("arena/index.html"),
            "<html><body>no scripts</body></html>",
        )
        .unwrap();
        std::fs::write(
            d.join("security/index.html"),
            r#"<html><body><script type="module" src="/_assets/a.js"></script></body></html>"#,
        )
        .unwrap();
        std::fs::write(
            d.join("_assets/a.js"),
            r#"new URL("thing.Ab12Cd34.wasm", import.meta.url);"#,
        )
        .unwrap();
        std::fs::write(
            d.join("_assets/thing.Ab12Cd34.wasm"),
            [0u8, 97, 115, 109, 1, 0, 0, 0],
        )
        .unwrap();
        let list = vec![exception()];
        let active = exceptions_in_use(d, &list, |e| panic!("unexpected error: {e}"));
        assert!(
            active.is_empty(),
            "a .wasm reachable only from /security/ must not activate /arena/"
        );
    }

    #[test]
    fn dist_root_confinement_rejects_escapes() {
        let dir = TestTempDir::new();
        let d = dir.path();
        std::fs::create_dir_all(d.join("arena")).unwrap();
        std::fs::write(
            d.join("arena/index.html"),
            r#"<html><body><script src="../../../../outside.js"></script></body></html>"#,
        )
        .unwrap();
        let html = std::fs::read_to_string(d.join("arena/index.html")).unwrap();
        assert!(
            reachable_scripts(d, &d.join("arena/index.html"), &html)
                .unwrap()
                .is_empty()
        );
    }

    #[test]
    fn modulepreload_link_is_followed_as_a_script_entry_point() {
        let dir = TestTempDir::new();
        let d = dir.path();
        std::fs::create_dir_all(d.join("arena")).unwrap();
        std::fs::create_dir_all(d.join("_assets")).unwrap();
        std::fs::write(
            d.join("arena/index.html"),
            r#"<html><head><link rel="modulepreload" href="/_assets/glue.js"></head><body>no script tag, only the preload link</body></html>"#,
        )
        .unwrap();
        std::fs::write(
            d.join("_assets/glue.js"),
            r#"new URL("thing.Ab12Cd34.wasm", import.meta.url);"#,
        )
        .unwrap();
        std::fs::write(
            d.join("_assets/thing.Ab12Cd34.wasm"),
            [0u8, 97, 115, 109, 1, 0, 0, 0],
        )
        .unwrap();
        let html = std::fs::read_to_string(d.join("arena/index.html")).unwrap();
        let wasm = reachable_wasm(d, &d.join("arena/index.html"), &html).unwrap();
        assert_eq!(
            wasm.len(),
            1,
            "a modulepreload link must be followed like a script src"
        );
    }

    #[test]
    fn an_unreadable_dependency_fails_the_whole_detection_strict_not_silently() {
        // Same reachability chain as build_dist(), but the actually-imported file (b.js) is not
        // valid UTF-8, so read_to_string on it fails. JS's readFileSync('utf8') would produce
        // replacement characters rather than throw, but that's a JS/Rust string-model difference,
        // not the point of this test: the point is that reachable_wasm propagates a real read
        // failure instead of silently treating the file as "no further wasm refs found" - so a
        // future case that DOES fail on both sides (permission denied, file removed mid-scan) is
        // handled the fail-strict way here, not swallowed.
        let dir = TestTempDir::new();
        let d = dir.path();
        fs::create_dir_all(d.join("arena")).unwrap();
        fs::create_dir_all(d.join("_assets")).unwrap();
        fs::write(
            d.join("arena/index.html"),
            r#"<html><body><script type="module" src="/_assets/a.js"></script></body></html>"#,
        )
        .unwrap();
        fs::write(d.join("_assets/a.js"), r#"import("./b.js");"#).unwrap();
        fs::write(d.join("_assets/b.js"), [0xFF, 0xFE, 0x00, 0xFF]).unwrap(); // invalid UTF-8
        let html = fs::read_to_string(d.join("arena/index.html")).unwrap();
        let err = reachable_wasm(d, &d.join("arena/index.html"), &html).unwrap_err();
        assert!(
            err.to_string().contains("b.js"),
            "error should name the unreadable file: {err}"
        );
    }

    #[test]
    fn fail_strict_on_missing_dist_returns_empty_and_reports() {
        let missing = Path::new("this-dist-does-not-exist-anywhere");
        let mut reported = false;
        let active = exceptions_in_use(missing, &[exception()], |_e| reported = true);
        assert!(active.is_empty());
        assert!(reported);
    }
}
