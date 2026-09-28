//! Port of `apps/web/security-headers.mjs` + `apps/web/host-headers.mjs` (main branch, as of
//! `d20b47f`). Produces `_headers` (Netlify/Cloudflare Pages text) and `_headers.json`.
//!
//! **Known gap 1, same pattern as `sitemap.rs`'s old `DOCS_ROUTES` gap:** the JS side computes its
//! `paths` input (every emitted file's URL path, outside `/_assets/`) by walking the actual built
//! `dist/<theme>` directory (`postbuild.mjs`'s `sitePaths()`). This crate doesn't build HTML pages
//! yet (PLAN.md Stage 2 items 5-6 are not done), so it has no independent way to enumerate every
//! page path (gallery, 404, legal x8, docs x7, playground, interface, research/files/*.svg, ...).
//! `cloudflare_rules()`/`header_rules()` therefore take `paths: &[String]` as an explicit input,
//! same as `sitemap_routes()` takes `docs_routes` - callers must supply the real path list (e.g. by
//! walking a reference dist, see `tests/parity.rs`) until page generation makes it derivable here.
//!
//! **Known gap 2, now ported in `csp_check.rs`** (review gap 1, `docs/hive/REVIEW-site-rs-headers.md`
//! on `web/headers @34dc115`): `scripts/csp-check.mjs`'s `exceptionsInUse()` - the wasm-reachability
//! scan that decides which SEC-150 exceptions (e.g. `/arena/`'s `'wasm-unsafe-eval'`) are actually
//! *active* in a given build. `cloudflare_rules()`/`host_rules()` still take `active: &[CspException]`
//! as an explicit input (mirroring the current JS signature, which also moved to taking `active` as a
//! parameter rather than computing it from `paths` alone) - callers run `csp_check::exceptions_in_use()`
//! themselves and pass the result in, or pass `&[]` for the baseline-everywhere case (every real dist
//! seen so far - `docs/hive/HEADERS-MATRIX.md`: "Active SEC-150 exceptions in this build: none").
//!
//! **Gate (team-lead ruling, 2026-09-27, on web-headers' review):** the JS headers step
//! (`postbuild.mjs`) stays authoritative. This module may run only as a **parity check next to JS**,
//! never as the generator, until ALL of review gaps 1-4 are ported with tests: (1) the wasm trigger
//! with fail-strict on error - done, `csp_check.rs`; (2) the policy checker (`assertCspSafe`) - done,
//! see `assert_csp_safe()` below; (3) a call to the Cloudflare rule/line-count limit check - done, see
//! `render_host_headers_checked()`; (4) per-URL assertions (e.g. `/arena/` gets exactly one policy) -
//! done, see `parse_host_headers()`/`host_headers_for_path()` and `tests/arena_fixture_parity.rs`.
//! Gap 5 (`checkCsp`/`arenaLayoutProblems`, the full static conformance scan and the arena layout
//! guard) is explicitly out of scope until a full `postbuild.mjs` replacement is proposed - it is not
//! needed for a parity check.
//!
//! **Drift to expect:** `chore/ci-site-hardening` (not on main yet) will add `X-Robots-Tag: noindex,
//! nofollow` to `globalHeaders()` on preview builds (APP-L8, review item 6). This port's
//! `global_headers()` has no stage-dependent header yet - byte parity against a dist built after that
//! merge will show exactly one extra header line, not a bug here. Re-baseline once it lands rather
//! than chasing it now.
//!
//! Also simplified: `INLINE_SCRIPT_HASHES`/`INLINE_STYLE_HASHES` are hardcoded empty (they are `[]`
//! in `security-headers.mjs` today and enforced empty by the build's `inlineStylesheets: 'never'` +
//! bundled-scripts setup) - `tests` below asserts the JS source still declares them empty (review item
//! 7), so a real hash landing there fails loudly instead of silently dropping out of this port.

use regex::Regex;
use serde::ser::{SerializeMap, Serializer};
use serde::{Deserialize, Serialize};
use std::path::Path;

pub const HASHED_ASSET_PREFIX: &str = "/_assets/";
pub const CACHE_IMMUTABLE: &str = "public, max-age=31536000, immutable";
pub const CACHE_REVALIDATE: &str = "no-cache";
const SECURITY_TXT: &str = "/.well-known/security.txt";
const CSP_HEADER: &str = "Content-Security-Policy";
pub const CF_MAX_RULES: usize = 100;
pub const CF_MAX_LINE: usize = 2000;
/// `EXCEPTION_TOKENS` in security-headers.mjs - only these tokens may ever be excepted.
const EXCEPTION_TOKENS: &[&str] = &["'wasm-unsafe-eval'"];

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Stage {
    Preview,
    Launch,
    Public,
}

impl Stage {
    pub fn as_str(self) -> &'static str {
        match self {
            Stage::Preview => "preview",
            Stage::Launch => "launch",
            Stage::Public => "public",
        }
    }

    /// `resolveStage()`: default `preview`.
    pub fn resolve(value: Option<&str>) -> Result<Stage, String> {
        match value.map(str::trim).filter(|s| !s.is_empty()) {
            None => Ok(Stage::Preview),
            Some("preview") => Ok(Stage::Preview),
            Some("launch") => Ok(Stage::Launch),
            Some("public") => Ok(Stage::Public),
            Some(other) => Err(format!(
                "SITE_STAGE must be one of preview|launch|public, got \"{other}\""
            )),
        }
    }

    /// `hsts(stage)` (SEC-151).
    pub fn hsts(self) -> &'static str {
        match self {
            Stage::Preview => "max-age=300",
            Stage::Launch => "max-age=86400",
            Stage::Public => "max-age=63072000; includeSubDomains; preload",
        }
    }

    /// `isIndexable(stage)` in `apps/web/indexing.mjs`: `resolveStage(stage) !== 'preview'`.
    pub fn is_indexable(self) -> bool {
        self != Stage::Preview
    }
}

/// `ROBOTS_NOINDEX` in `apps/web/stage.mjs` - note the space after the comma, unlike the `<meta
/// name="robots">` tag's `'noindex,nofollow'` (no space, when a future page ports that logic).
pub const ROBOTS_NOINDEX: &str = "noindex, nofollow";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Host {
    Netlify,
    Cloudflare,
}

impl Host {
    pub fn as_str(self) -> &'static str {
        match self {
            Host::Netlify => "netlify",
            Host::Cloudflare => "cloudflare",
        }
    }

    /// `resolveHost()`: default `cloudflare`.
    pub fn resolve(value: Option<&str>) -> Result<Host, String> {
        match value.map(str::trim).filter(|s| !s.is_empty()) {
            None => Ok(Host::Cloudflare),
            Some("netlify") => Ok(Host::Netlify),
            Some("cloudflare") => Ok(Host::Cloudflare),
            Some(other) => Err(format!(
                "SITE_HOST must be one of netlify|cloudflare, got \"{other}\""
            )),
        }
    }
}

/// One entry of `csp-exceptions.json` (only the fields this port needs to act on).
#[derive(Debug, Clone, Deserialize)]
pub struct CspException {
    pub route: String,
    pub directive: String,
    pub token: String,
}

#[derive(Deserialize)]
struct RawException {
    route: String,
    directive: String,
    token: String,
    owner: String,
    adr: String,
}

#[derive(Deserialize)]
struct ExceptionsFile {
    exceptions: Vec<RawException>,
}

/// `^/[a-z0-9-]+/$` (security-headers.mjs's route validation regex), checked without a regex dep.
fn is_valid_route(route: &str) -> bool {
    let bytes = route.as_bytes();
    if bytes.len() < 3 || bytes[0] != b'/' || bytes[bytes.len() - 1] != b'/' {
        return false;
    }
    route[1..route.len() - 1]
        .bytes()
        .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'-')
}

/// `CSP_EXCEPTIONS` - loads and validates `apps/web/csp-exceptions.json` the same way
/// security-headers.mjs does at import time (route shape, directive, token, owner/adr present).
pub fn load_csp_exceptions(repo_root: &Path) -> std::io::Result<Vec<CspException>> {
    let text = std::fs::read_to_string(repo_root.join("apps/web/csp-exceptions.json"))?;
    let file: ExceptionsFile =
        serde_json::from_str(&text).map_err(|e| std::io::Error::other(e.to_string()))?;
    let mut out = Vec::with_capacity(file.exceptions.len());
    for e in file.exceptions {
        if !is_valid_route(&e.route)
            || e.directive != "script-src"
            || !EXCEPTION_TOKENS.contains(&e.token.as_str())
            || e.owner.is_empty()
            || e.adr.is_empty()
        {
            return Err(std::io::Error::other(format!(
                "csp-exceptions.json: invalid entry for route {:?}",
                e.route
            )));
        }
        out.push(CspException {
            route: e.route,
            directive: e.directive,
            token: e.token,
        });
    }
    Ok(out)
}

/// `routeExceptions(route, list)`.
pub fn route_exceptions<'a>(
    route: Option<&str>,
    list: &'a [CspException],
) -> Vec<&'a CspException> {
    match route {
        None => Vec::new(),
        Some(route) => list
            .iter()
            .filter(|e| route.starts_with(&e.route))
            .collect(),
    }
}

/// `checkedActive(active, paths)`: only listed exceptions whose route is actually built can be
/// active, whatever the caller passes in `active` (a sanity filter, not the wasm-reachability
/// detection itself - see `csp_check::exceptions_in_use()` for that now, review gap 1). JS checks
/// `CSP_EXCEPTIONS.includes(e)` (reference identity, since `exceptionsInUse()` always returns
/// elements sourced from that same array); this port checks route+directive+token equality against
/// `list` instead (review item 8: compare `directive` too, to mirror identity fully), since Rust
/// structs here are owned/cloned rather than shared references - same effect: `active` can't smuggle
/// in an exception `list` doesn't recognize.
pub fn checked_active<'a>(
    active: &'a [CspException],
    list: &[CspException],
    paths: &[String],
) -> Vec<&'a CspException> {
    active
        .iter()
        .filter(|e| {
            list.iter()
                .any(|l| l.route == e.route && l.directive == e.directive && l.token == e.token)
                && paths.iter().any(|p| p.starts_with(&e.route))
        })
        .collect()
}

/// `csp({ route, exceptions })`. `scriptHashes`/`styleHashes` are omitted (see module doc comment).
pub fn csp(route: Option<&str>, exceptions: &[CspException]) -> String {
    let extra: Vec<&str> = route_exceptions(route, exceptions)
        .into_iter()
        .map(|e| e.token.as_str())
        .collect();
    let script_src = if extra.is_empty() {
        "script-src 'self'".to_string()
    } else {
        format!("script-src 'self' {}", extra.join(" "))
    };
    [
        "default-src 'none'".to_string(),
        script_src,
        "style-src 'self'".to_string(),
        "img-src 'self' data:".to_string(),
        "font-src 'self'".to_string(),
        "connect-src 'self'".to_string(),
        "manifest-src 'self'".to_string(),
        "worker-src 'self'".to_string(),
        "media-src 'self'".to_string(),
        "object-src 'none'".to_string(),
        "base-uri 'none'".to_string(),
        "form-action 'self'".to_string(),
        "frame-ancestors 'none'".to_string(),
        "upgrade-insecure-requests".to_string(),
    ]
    .join("; ")
}

/// `parseCsp(value)`: CSP string -> ordered directive -> sources. Order matters for `render`-style
/// consumers but not for `assert_csp_safe`; kept as a `Vec<(String, Vec<String>)>` (not a `HashMap`)
/// so error messages and any future rendering stay deterministic.
pub fn parse_csp(value: &str) -> Result<Vec<(String, Vec<String>)>, String> {
    let mut out: Vec<(String, Vec<String>)> = Vec::new();
    for part in value.split(';') {
        let mut words = part.split_whitespace();
        let Some(name) = words.next() else { continue };
        let name = name.to_lowercase();
        if out.iter().any(|(n, _)| *n == name) {
            return Err(format!("CSP: duplicate directive {name}"));
        }
        out.push((name, words.map(str::to_string).collect()));
    }
    Ok(out)
}

fn csp_get<'a>(parsed: &'a [(String, Vec<String>)], name: &str) -> Option<&'a [String]> {
    parsed
        .iter()
        .find(|(n, _)| n == name)
        .map(|(_, v)| v.as_slice())
}

/// `assertCspSafe(value, { allowedOrigins, route, exceptions })` (review gap 2, SEC-150 gate). Review
/// item 2's exact checks: no `'unsafe-*'`/`'wasm-unsafe-eval'` outside a listed `(route, script-src,
/// token)` exception, only `'self'`/`'none'`/sha256/`data:` (img-src only) sources otherwise, the
/// required directives present, and `default-src`/`object-src`/`base-uri`/`frame-ancestors` == `'none'`.
pub fn assert_csp_safe(
    value: &str,
    route: Option<&str>,
    exceptions: &[CspException],
    allowed_origins: &[&str],
) -> Result<(), String> {
    let parsed = parse_csp(value)?;
    let excepted: Vec<&CspException> = route_exceptions(route, exceptions)
        .into_iter()
        .filter(|e| e.directive == "script-src" && EXCEPTION_TOKENS.contains(&e.token.as_str()))
        .collect();

    for required in [
        "default-src",
        "script-src",
        "style-src",
        "object-src",
        "base-uri",
        "frame-ancestors",
        "form-action",
    ] {
        if csp_get(&parsed, required).is_none() {
            return Err(format!("CSP: missing {required}"));
        }
    }

    let sha256_re = Regex::new(r"(?i)^'sha256-[a-z0-9+/]+=*'$").expect("valid regex");
    for (name, sources) in &parsed {
        for s in sources {
            let low = s.to_lowercase();
            if excepted
                .iter()
                .any(|e| &e.directive == name && &e.token == s)
            {
                continue;
            }
            if low.starts_with("'unsafe-") || low == "'wasm-unsafe-eval'" {
                return Err(format!("CSP: {name} allows {s}"));
            }
            if low == "'self'" || low == "'none'" {
                continue;
            }
            if sha256_re.is_match(s) {
                continue;
            }
            if name == "img-src" && low == "data:" {
                continue;
            }
            if allowed_origins.contains(&s.as_str()) {
                continue;
            }
            return Err(format!("CSP: {name} allows a non-self source {s}"));
        }
    }

    for (name, want) in [
        ("default-src", "'none'"),
        ("object-src", "'none'"),
        ("base-uri", "'none'"),
        ("frame-ancestors", "'none'"),
    ] {
        let got = csp_get(&parsed, name).unwrap_or(&[]).join(" ");
        if got != want {
            return Err(format!("CSP: {name} must be {want}"));
        }
    }
    Ok(())
}

/// `PERMISSIONS_POLICY`.
pub fn permissions_policy() -> String {
    [
        "accelerometer=()",
        "ambient-light-sensor=()",
        "autoplay=()",
        "bluetooth=()",
        "browsing-topics=()",
        "camera=()",
        "display-capture=()",
        "encrypted-media=()",
        "fullscreen=(self)",
        "geolocation=()",
        "gyroscope=()",
        "hid=()",
        "magnetometer=()",
        "microphone=()",
        "midi=()",
        "payment=()",
        "publickey-credentials-get=()",
        "screen-wake-lock=()",
        "serial=()",
        "usb=()",
        "xr-spatial-tracking=()",
    ]
    .join(", ")
}

/// One `_headers` rule: an ordered path + ordered headers (+ Cloudflare "! Header" detach list).
/// Serialized to JSON with a hand-rolled `Serialize` so key/header order matches the JS output
/// exactly (`serde_json::Map`'s default `BTreeMap` would sort keys alphabetically).
#[derive(Debug, Clone)]
pub struct Rule {
    pub path: String,
    pub detach: Vec<String>,
    pub headers: Vec<(String, String)>,
}

impl Serialize for Rule {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        let mut map = serializer.serialize_map(None)?;
        map.serialize_entry("path", &self.path)?;
        if !self.detach.is_empty() {
            map.serialize_entry("detach", &self.detach)?;
        }
        map.serialize_entry("headers", &OrderedHeaders(&self.headers))?;
        map.end()
    }
}

struct OrderedHeaders<'a>(&'a [(String, String)]);
impl Serialize for OrderedHeaders<'_> {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        let mut map = serializer.serialize_map(Some(self.0.len()))?;
        for (k, v) in self.0 {
            map.serialize_entry(k, v)?;
        }
        map.end()
    }
}

/// `globalHeaders(stage)` (APP-L8: `X-Robots-Tag` appended last, only on `preview`).
pub fn global_headers(stage: Stage, exceptions: &[CspException]) -> Vec<(String, String)> {
    let mut headers = vec![
        (CSP_HEADER.to_string(), csp(None, exceptions)),
        (
            "Strict-Transport-Security".to_string(),
            stage.hsts().to_string(),
        ),
        ("Permissions-Policy".to_string(), permissions_policy()),
        (
            "Referrer-Policy".to_string(),
            "strict-origin-when-cross-origin".to_string(),
        ),
        ("X-Content-Type-Options".to_string(), "nosniff".to_string()),
        ("X-Frame-Options".to_string(), "DENY".to_string()),
        (
            "Cross-Origin-Opener-Policy".to_string(),
            "same-origin".to_string(),
        ),
        (
            "Cross-Origin-Resource-Policy".to_string(),
            "same-origin".to_string(),
        ),
        (
            "Cross-Origin-Embedder-Policy".to_string(),
            "require-corp".to_string(),
        ),
    ];
    if !stage.is_indexable() {
        headers.push(("X-Robots-Tag".to_string(), ROBOTS_NOINDEX.to_string()));
    }
    headers
}

fn sorted_dedup(paths: &[String]) -> Vec<String> {
    let mut v = paths.to_vec();
    v.sort();
    v.dedup();
    v
}

/// `headerRules({ stage, paths })` (the original, per-path layout - still used for Netlify).
pub fn header_rules(stage: Stage, paths: &[String], exceptions: &[CspException]) -> Vec<Rule> {
    let mut rules = vec![Rule {
        path: "/*".to_string(),
        detach: vec![],
        headers: global_headers(stage, exceptions),
    }];
    rules.push(Rule {
        path: format!("{HASHED_ASSET_PREFIX}*"),
        detach: vec![],
        headers: vec![("Cache-Control".to_string(), CACHE_IMMUTABLE.to_string())],
    });
    for p in sorted_dedup(paths) {
        let mut headers = vec![("Cache-Control".to_string(), CACHE_REVALIDATE.to_string())];
        if p == SECURITY_TXT {
            headers.push((
                "Content-Type".to_string(),
                "text/plain; charset=utf-8".to_string(),
            ));
        }
        rules.push(Rule {
            path: p.clone(),
            detach: vec![],
            headers: headers.clone(),
        });
        if p.len() > 1 && p.ends_with('/') {
            rules.push(Rule {
                path: p[..p.len() - 1].to_string(),
                detach: vec![],
                headers,
            });
        }
    }
    rules
}

/// `cloudflareRules({ stage, paths, active })`. `active` should already be `checked_active()`-filtered
/// (callers that haven't run the wasm-reachability scan - see module doc comment "Known gap 2" -
/// simply pass `&[]`, which is every real dist seen so far).
pub fn cloudflare_rules(
    stage: Stage,
    paths: &[String],
    exceptions: &[CspException],
    active: &[CspException],
) -> Vec<Rule> {
    let mut rules = vec![Rule {
        path: "/*".to_string(),
        detach: vec![],
        headers: global_headers(stage, exceptions),
    }];
    rules.push(Rule {
        path: format!("{HASHED_ASSET_PREFIX}*"),
        detach: vec![],
        headers: vec![("Cache-Control".to_string(), CACHE_IMMUTABLE.to_string())],
    });
    let revalidate = vec![("Cache-Control".to_string(), CACHE_REVALIDATE.to_string())];
    rules.push(Rule {
        path: "/".to_string(),
        detach: vec![],
        headers: revalidate.clone(),
    });
    rules.push(Rule {
        path: "/*/".to_string(),
        detach: vec![],
        headers: revalidate.clone(),
    });
    rules.push(Rule {
        path: "/*.html".to_string(),
        detach: vec![],
        headers: revalidate.clone(),
    });
    for p in sorted_dedup(paths) {
        if p.ends_with('/') || p.ends_with(".html") || p.starts_with(HASHED_ASSET_PREFIX) {
            continue;
        }
        let mut headers = revalidate.clone();
        if p == SECURITY_TXT {
            headers.push((
                "Content-Type".to_string(),
                "text/plain; charset=utf-8".to_string(),
            ));
        }
        rules.push(Rule {
            path: p,
            detach: vec![],
            headers,
        });
    }
    for e in checked_active(active, exceptions, paths) {
        rules.push(Rule {
            path: format!("{}*", e.route),
            detach: vec![CSP_HEADER.to_string()],
            headers: vec![(CSP_HEADER.to_string(), csp(Some(&e.route), exceptions))],
        });
    }
    rules
}

/// `hostRules(host, { stage, paths, active })`.
pub fn host_rules(
    host: Host,
    stage: Stage,
    paths: &[String],
    exceptions: &[CspException],
    active: &[CspException],
) -> Result<Vec<Rule>, String> {
    let checked = checked_active(active, exceptions, paths);
    match host {
        Host::Cloudflare => Ok(cloudflare_rules(stage, paths, exceptions, active)),
        Host::Netlify => {
            if !checked.is_empty() {
                let routes: Vec<&str> = checked.iter().map(|e| e.route.as_str()).collect();
                return Err(format!(
                    "SITE_HOST=netlify cannot serve the SEC-150 exception for {} (Netlify has no \
                     header detach; nfb-security: KEEP FAIL). Build with SITE_HOST=cloudflare.",
                    routes.join(", ")
                ));
            }
            Ok(header_rules(stage, paths, exceptions))
        }
    }
}

/// `renderHeadersFile(rules, { stage })` (the original, Netlify-compatible text format).
pub fn render_headers_file(rules: &[Rule], stage: Stage) -> String {
    let mut out = vec![
        "# Generated by apps/web/scripts/postbuild.mjs from apps/web/security-headers.mjs. Do not edit.".to_string(),
        format!(
            "# SITE_STAGE={} (HSTS per SEC-151). Identical for dist/clinical and dist/cosmos.",
            stage.as_str()
        ),
    ];
    for r in rules {
        out.push(r.path.clone());
        for (k, v) in &r.headers {
            out.push(format!("  {k}: {v}"));
        }
    }
    let mut s = out.join("\n");
    s.push('\n');
    s
}

/// `renderHostHeaders(host, rules, { stage })`.
pub fn render_host_headers(host: Host, rules: &[Rule], stage: Stage) -> String {
    match host {
        Host::Netlify => render_headers_file(rules, stage),
        Host::Cloudflare => {
            let mut lines: Vec<String> = render_headers_file(&[], stage)
                .trim_end()
                .split('\n')
                .map(str::to_string)
                .collect();
            lines.push(
                "# SITE_HOST=cloudflare: splat layout within the Cloudflare Pages limit of 100 rules."
                    .to_string(),
            );
            for r in rules {
                lines.push(r.path.clone());
                for k in &r.detach {
                    lines.push(format!("  ! {k}"));
                }
                for (k, v) in &r.headers {
                    lines.push(format!("  {k}: {v}"));
                }
            }
            let mut s = lines.join("\n");
            s.push('\n');
            s
        }
    }
}

/// `assertCloudflareLimits(text)`. Returns the rule count on success.
pub fn assert_cloudflare_limits(text: &str) -> Result<usize, String> {
    let lines: Vec<&str> = text.lines().collect();
    let rule_count = lines.iter().filter(|l| l.starts_with('/')).count();
    if rule_count > CF_MAX_RULES {
        return Err(format!(
            "Cloudflare _headers: {rule_count} rules > {CF_MAX_RULES}; rules past the limit would not apply"
        ));
    }
    if let Some(long) = lines.iter().find(|l| l.len() > CF_MAX_LINE) {
        return Err(format!(
            "Cloudflare _headers: a line has {} chars > {CF_MAX_LINE}",
            long.len()
        ));
    }
    Ok(rule_count)
}

/// `renderHostHeaders` + the Cloudflare limit gate `postbuild.mjs` applies right after it (review
/// gap 3: "the generator must call `assert_cloudflare_limits`"). This is the function any driver
/// should call instead of the bare `render_host_headers`, so the check can't be forgotten.
pub fn render_host_headers_checked(
    host: Host,
    rules: &[Rule],
    stage: Stage,
) -> Result<String, String> {
    let text = render_host_headers(host, rules, stage);
    if host == Host::Cloudflare {
        assert_cloudflare_limits(&text)?;
    }
    Ok(text)
}

/// `patternRegExp(pattern)`: `"*"` is a greedy splat anywhere (both hosts document this).
fn pattern_regexp(pattern: &str) -> Regex {
    let escaped: Vec<String> = pattern.split('*').map(regex::escape).collect();
    Regex::new(&format!("^{}$", escaped.join(".*"))).expect("valid pattern regex")
}

/// `parseHostHeaders(text)`: parse either rendered layout back into rules; a Cloudflare `"! Header"`
/// line becomes part of that rule's `detach` list.
pub fn parse_host_headers(text: &str) -> Result<Vec<Rule>, String> {
    let mut rules: Vec<Rule> = Vec::new();
    for line in text.lines() {
        if line.trim().is_empty() || line.trim_start().starts_with('#') {
            continue;
        }
        if !line.starts_with(char::is_whitespace) {
            rules.push(Rule {
                path: line.trim().to_string(),
                detach: vec![],
                headers: vec![],
            });
            continue;
        }
        let Some(last) = rules.last_mut() else {
            return Err(format!("_headers: header before any path: {line}"));
        };
        let t = line.trim();
        if let Some(detached) = t.strip_prefix('!') {
            if !last.headers.is_empty() {
                return Err(format!("_headers: detach after a header in {}", last.path));
            }
            last.detach.push(detached.trim().to_string());
            continue;
        }
        let Some(i) = t.find(':') else {
            return Err(format!("_headers: malformed line: {line}"));
        };
        last.headers
            .push((t[..i].trim().to_string(), t[i + 1..].trim().to_string()));
    }
    Ok(rules)
}

/// `hostHeadersForPath(rules, path)`: headers a host would send for `path` - every matching rule
/// merged in order, repeated headers joined `", "`, a detached header keeping only the values set by
/// the rule(s) that detach it.
pub fn host_headers_for_path(rules: &[Rule], path: &str) -> Vec<(String, String)> {
    let matching: Vec<&Rule> = rules
        .iter()
        .filter(|r| pattern_regexp(&r.path).is_match(path))
        .collect();
    let detached: std::collections::HashSet<&str> = matching
        .iter()
        .flat_map(|r| r.detach.iter().map(String::as_str))
        .collect();
    let mut out: Vec<(String, String)> = Vec::new();
    for r in &matching {
        // JS's `r.headers` is a plain object: a repeated key within ONE rule already collapsed to
        // its last value before this function ever runs (object-literal construction semantics).
        // `Rule.headers` is a `Vec`, which doesn't enforce that - collapse the same way here first,
        // so a same-rule repeat isn't mistaken for a separate rule's header to comma-join.
        let mut own: Vec<(&str, &str)> = Vec::new();
        for (k, v) in &r.headers {
            if let Some(existing) = own.iter_mut().find(|(ek, _)| *ek == k.as_str()) {
                existing.1 = v.as_str();
            } else {
                own.push((k.as_str(), v.as_str()));
            }
        }
        for (k, v) in own {
            if detached.contains(k) && !r.detach.iter().any(|d| d == k) {
                continue;
            }
            if let Some(existing) = out.iter_mut().find(|(ek, _)| ek == k) {
                existing.1 = format!("{}, {v}", existing.1);
            } else {
                out.push((k.to_string(), v.to_string()));
            }
        }
    }
    out
}

/// `_headers.json`'s shape (postbuild.mjs). Field declaration order = JS key order (no alphabetical
/// re-sort, unlike a bare `serde_json::Map`).
#[derive(Serialize)]
pub struct HeadersJson<'a> {
    #[serde(rename = "generatedBy")]
    pub generated_by: &'static str,
    pub stage: &'a str,
    pub host: &'a str,
    #[serde(rename = "activeExceptions")]
    pub active_exceptions: Vec<&'a str>,
    pub note: &'static str,
    pub rules: &'a [Rule],
}

impl<'a> HeadersJson<'a> {
    /// `active` here is the *checked* list (already filtered by `checked_active()`), matching what
    /// `postbuild.mjs` writes as `active.map((e) => e.route)`.
    pub fn new(
        stage: Stage,
        host: Host,
        active: &[&'a CspException],
        rules: &'a [Rule],
    ) -> HeadersJson<'a> {
        HeadersJson {
            generated_by: "apps/web/security-headers.mjs",
            stage: stage.as_str(),
            host: host.as_str(),
            active_exceptions: active.iter().map(|e| e.route.as_str()).collect(),
            note: "Rules in order; a host must merge all matching rules (path \"/*\" matches everything, \"/_assets/*\" every hashed asset).",
            rules,
        }
    }

    /// `JSON.stringify(obj, null, 2) + '\n'`.
    pub fn render(&self) -> serde_json::Result<String> {
        let mut s = serde_json::to_string_pretty(self)?;
        s.push('\n');
        Ok(s)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn no_exceptions() -> Vec<CspException> {
        Vec::new()
    }

    // ----------------------------------------------------------------- APP-L8: X-Robots-Tag/Stage

    #[test]
    fn preview_is_not_indexable_launch_and_public_are() {
        assert!(!Stage::Preview.is_indexable());
        assert!(Stage::Launch.is_indexable());
        assert!(Stage::Public.is_indexable());
    }

    #[test]
    fn global_headers_adds_x_robots_tag_only_on_preview() {
        let preview = global_headers(Stage::Preview, &no_exceptions());
        assert_eq!(
            preview.last(),
            Some(&("X-Robots-Tag".to_string(), ROBOTS_NOINDEX.to_string())),
            "X-Robots-Tag must be the last header, matching indexing.mjs's ...robots spread"
        );

        for stage in [Stage::Launch, Stage::Public] {
            let headers = global_headers(stage, &no_exceptions());
            assert!(
                !headers.iter().any(|(k, _)| k == "X-Robots-Tag"),
                "{stage:?} must not carry X-Robots-Tag"
            );
        }
    }

    #[test]
    fn robots_noindex_value_has_a_space_unlike_the_meta_tag_spelling() {
        // stage.mjs: 'noindex, nofollow' (space) - different from Base.astro's meta content
        // 'noindex,nofollow' (no space, ported by a future HTML page, not here).
        assert_eq!(ROBOTS_NOINDEX, "noindex, nofollow");
    }

    #[test]
    fn csp_baseline_has_no_extra_script_src_tokens() {
        let baseline = csp(None, &no_exceptions());
        assert!(baseline.contains("script-src 'self'; "));
        assert!(!baseline.contains("wasm-unsafe-eval"));
    }

    #[test]
    fn csp_route_exception_adds_token_only_on_its_route() {
        let exceptions = vec![CspException {
            route: "/arena/".to_string(),
            directive: "script-src".to_string(),
            token: "'wasm-unsafe-eval'".to_string(),
        }];
        let arena = csp(Some("/arena/"), &exceptions);
        assert!(arena.contains("script-src 'self' 'wasm-unsafe-eval'"));
        let other = csp(Some("/gallery/"), &exceptions);
        assert!(!other.contains("wasm-unsafe-eval"));
        let baseline = csp(None, &exceptions);
        assert!(!baseline.contains("wasm-unsafe-eval"));
    }

    #[test]
    fn checked_active_rejects_unbuilt_and_unlisted_routes() {
        let list = vec![CspException {
            route: "/arena/".to_string(),
            directive: "script-src".to_string(),
            token: "'wasm-unsafe-eval'".to_string(),
        }];
        let paths_without_arena = vec!["/".to_string(), "/gallery/".to_string()];
        assert!(checked_active(&list, &list, &paths_without_arena).is_empty());

        let paths_with_arena = vec!["/arena/".to_string()];
        assert_eq!(checked_active(&list, &list, &paths_with_arena).len(), 1);

        let unlisted = vec![CspException {
            route: "/other/".to_string(),
            directive: "script-src".to_string(),
            token: "'wasm-unsafe-eval'".to_string(),
        }];
        assert!(checked_active(&unlisted, &list, &["/other/".to_string()]).is_empty());
    }

    #[test]
    fn cloudflare_rules_no_exceptions_matches_dist_shape() {
        let paths = vec!["/".to_string(), "/robots.txt".to_string()];
        let rules = cloudflare_rules(Stage::Preview, &paths, &no_exceptions(), &[]);
        // /* , /_assets/*, /, /*/, /*.html, then /robots.txt (not ending in / or .html)
        assert_eq!(rules.len(), 6);
        assert_eq!(rules[0].path, "/*");
        assert_eq!(rules[5].path, "/robots.txt");
    }

    #[test]
    fn netlify_rejects_when_an_exception_is_active_on_a_built_route() {
        let exceptions = vec![CspException {
            route: "/arena/".to_string(),
            directive: "script-src".to_string(),
            token: "'wasm-unsafe-eval'".to_string(),
        }];
        let paths = vec!["/arena/".to_string()];
        let err = host_rules(
            Host::Netlify,
            Stage::Preview,
            &paths,
            &exceptions,
            &exceptions,
        )
        .unwrap_err();
        assert!(err.contains("SITE_HOST=netlify"));
        assert!(err.contains("/arena/"));
    }

    #[test]
    fn render_host_headers_cloudflare_uses_splat_comment_and_detach_lines() {
        let rules = vec![Rule {
            path: "/arena/*".to_string(),
            detach: vec!["Content-Security-Policy".to_string()],
            headers: vec![(
                "Content-Security-Policy".to_string(),
                "baseline".to_string(),
            )],
        }];
        let text = render_host_headers(Host::Cloudflare, &rules, Stage::Preview);
        assert!(text.contains("SITE_HOST=cloudflare"));
        assert!(text.contains("  ! Content-Security-Policy"));
        assert!(text.contains("  Content-Security-Policy: baseline"));
    }

    #[test]
    fn headers_json_key_order_is_not_alphabetised() {
        let rules: Vec<Rule> = vec![];
        let json = HeadersJson::new(Stage::Preview, Host::Cloudflare, &[], &rules)
            .render()
            .unwrap();
        let gb = json.find("generatedBy").unwrap();
        let stage = json.find("\"stage\"").unwrap();
        let host = json.find("\"host\"").unwrap();
        let active = json.find("activeExceptions").unwrap();
        let note = json.find("\"note\"").unwrap();
        let rules_pos = json.find("\"rules\"").unwrap();
        assert!(gb < stage && stage < host && host < active && active < note && note < rules_pos);
    }

    // -------------------------------------------------------------- review gap 2: assert_csp_safe

    #[test]
    fn assert_csp_safe_accepts_the_baseline() {
        let baseline = csp(None, &no_exceptions());
        assert_csp_safe(&baseline, None, &no_exceptions(), &[]).unwrap();
    }

    #[test]
    fn assert_csp_safe_rejects_wasm_unsafe_eval_without_a_listed_exception() {
        let bad = "default-src 'none'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self'; \
                    object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'";
        let err = assert_csp_safe(bad, None, &no_exceptions(), &[]).unwrap_err();
        assert!(err.contains("wasm-unsafe-eval") || err.contains("allows"));
    }

    #[test]
    fn assert_csp_safe_accepts_wasm_unsafe_eval_only_on_the_listed_route() {
        let exceptions = vec![CspException {
            route: "/arena/".to_string(),
            directive: "script-src".to_string(),
            token: "'wasm-unsafe-eval'".to_string(),
        }];
        let arena_csp = csp(Some("/arena/"), &exceptions);
        assert_csp_safe(&arena_csp, Some("/arena/"), &exceptions, &[]).unwrap();
        // The same CSP string checked against a DIFFERENT route must fail: the token isn't excepted
        // there, mirroring JS's per-route gate in postbuild.mjs's assertCspSafe(csp({route}), {route}).
        let err = assert_csp_safe(&arena_csp, Some("/gallery/"), &exceptions, &[]).unwrap_err();
        assert!(err.contains("wasm-unsafe-eval") || err.contains("allows"));
    }

    #[test]
    fn assert_csp_safe_rejects_a_non_self_source() {
        let bad = "default-src 'none'; script-src 'self' https://evil.example; style-src 'self'; \
                    object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'";
        assert!(assert_csp_safe(bad, None, &no_exceptions(), &[]).is_err());
    }

    #[test]
    fn assert_csp_safe_rejects_missing_required_directive() {
        let bad = "default-src 'none'; style-src 'self'; object-src 'none'; base-uri 'none'; \
                    frame-ancestors 'none'; form-action 'self'"; // no script-src
        let err = assert_csp_safe(bad, None, &no_exceptions(), &[]).unwrap_err();
        assert!(err.contains("script-src"));
    }

    // ---------------------------------------------------- review gap 3: cloudflare limit is called

    #[test]
    fn render_host_headers_checked_enforces_the_cloudflare_rule_limit() {
        let stage = Stage::Preview;
        // Cloudflare's layout only emits one rule per path that ISN'T a page (doesn't end in "/" or
        // ".html", isn't under /_assets/) - e.g. text/svg files - everything else is covered by the
        // fixed "/", "/*/" and "/*.html" splats. Use enough non-page paths to exceed CF_MAX_RULES.
        let paths: Vec<String> = (0..200).map(|i| format!("/file-{i}.txt")).collect();
        let rules = cloudflare_rules(stage, &paths, &no_exceptions(), &[]);
        assert!(
            rules.len() > CF_MAX_RULES,
            "test setup: expected more than {CF_MAX_RULES} rules, got {}",
            rules.len()
        );
        let err = render_host_headers_checked(Host::Cloudflare, &rules, stage).unwrap_err();
        assert!(err.contains("rules"));
    }

    #[test]
    fn render_host_headers_checked_passes_through_for_netlify_regardless_of_rule_count() {
        let stage = Stage::Preview;
        let paths: Vec<String> = (0..200).map(|i| format!("/page-{i}/")).collect();
        let rules = header_rules(stage, &paths, &no_exceptions());
        // Netlify has no documented rule cap, so the same rule count that fails Cloudflare must pass.
        render_host_headers_checked(Host::Netlify, &rules, stage).unwrap();
    }

    // ------------------------------------------------ review gap 4: per-URL parse + lookup matcher

    #[test]
    fn parse_host_headers_round_trips_cloudflare_rules_with_detach() {
        let rules = vec![
            Rule {
                path: "/*".to_string(),
                detach: vec![],
                headers: vec![(
                    "Content-Security-Policy".to_string(),
                    "baseline".to_string(),
                )],
            },
            Rule {
                path: "/arena/*".to_string(),
                detach: vec!["Content-Security-Policy".to_string()],
                headers: vec![(
                    "Content-Security-Policy".to_string(),
                    "arena-csp".to_string(),
                )],
            },
        ];
        let text = render_host_headers(Host::Cloudflare, &rules, Stage::Preview);
        let parsed = parse_host_headers(&text).unwrap();
        assert_eq!(parsed.len(), 2);
        assert_eq!(parsed[1].path, "/arena/*");
        assert_eq!(
            parsed[1].detach,
            vec!["Content-Security-Policy".to_string()]
        );
    }

    #[test]
    fn arena_gets_exactly_one_policy_and_it_is_the_route_csp() {
        let exceptions = vec![CspException {
            route: "/arena/".to_string(),
            directive: "script-src".to_string(),
            token: "'wasm-unsafe-eval'".to_string(),
        }];
        let paths = vec![
            "/".to_string(),
            "/arena/".to_string(),
            "/gallery/".to_string(),
        ];
        let active = exceptions.clone();
        let rules = cloudflare_rules(Stage::Preview, &paths, &exceptions, &active);
        let text = render_host_headers(Host::Cloudflare, &rules, Stage::Preview);
        let parsed = parse_host_headers(&text).unwrap();

        let arena_headers = host_headers_for_path(&parsed, "/arena/");
        let arena_csp_values: Vec<&str> = arena_headers
            .iter()
            .filter(|(k, _)| k == "Content-Security-Policy")
            .map(|(_, v)| v.as_str())
            .collect();
        assert_eq!(
            arena_csp_values.len(),
            1,
            "review gap 4: /arena/ must get exactly one CSP value"
        );
        assert_eq!(arena_csp_values[0], csp(Some("/arena/"), &exceptions));

        let gallery_headers = host_headers_for_path(&parsed, "/gallery/");
        let gallery_csp: Vec<&str> = gallery_headers
            .iter()
            .filter(|(k, _)| k == "Content-Security-Policy")
            .map(|(_, v)| v.as_str())
            .collect();
        assert_eq!(
            gallery_csp,
            vec![csp(None, &exceptions)],
            "other routes keep the baseline"
        );
    }

    #[test]
    fn a_repeated_key_within_one_rule_keeps_only_the_last_value_like_a_js_object_would() {
        // JS's `r.headers` is a plain object; a repeated key at construction time collapses to the
        // last value before any of this runs. Rule.headers is a Vec, so build one directly with a
        // repeat to check host_headers_for_path() reproduces that collapse (web-headers' minor nit).
        let rules = vec![Rule {
            path: "/*".to_string(),
            detach: vec![],
            headers: vec![
                ("X-Example".to_string(), "first".to_string()),
                ("X-Example".to_string(), "second".to_string()),
            ],
        }];
        let out = host_headers_for_path(&rules, "/anything/");
        let values: Vec<&str> = out
            .iter()
            .filter(|(k, _)| k == "X-Example")
            .map(|(_, v)| v.as_str())
            .collect();
        assert_eq!(
            values,
            vec!["second"],
            "must keep only the last value, not comma-join both"
        );
    }

    // ------------------------------------------------------------ review item 7: JS inline hashes

    #[test]
    fn js_inline_hash_arrays_are_still_declared_empty() {
        // Trip-wire, not full JS parsing (see module doc comment): if main ever lists a real inline
        // hash, this port's hardcoded-empty INLINE_SCRIPT_HASHES/INLINE_STYLE_HASHES silently goes
        // stale. Fails loudly instead.
        let root = Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../..")
            .canonicalize()
            .unwrap();
        let src = std::fs::read_to_string(root.join("apps/web/security-headers.mjs")).unwrap();
        assert!(
            src.contains("export const INLINE_SCRIPT_HASHES = [];"),
            "main's INLINE_SCRIPT_HASHES is no longer empty - this port's csp() needs updating"
        );
        assert!(
            src.contains("export const INLINE_STYLE_HASHES = [];"),
            "main's INLINE_STYLE_HASHES is no longer empty - this port's csp() needs updating"
        );
    }
}
