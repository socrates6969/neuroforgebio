// ONE shared security-header config for both builds (SECURITY-REQUIREMENTS §A.2, SEC-150..156).
// scripts/postbuild.mjs emits it identically into dist/<theme>/_headers (Netlify / Cloudflare Pages
// format) and dist/<theme>/_headers.json (for any other host). The only theme difference allowed is
// that cosmos loads its self-hosted three.js chunk, which script-src 'self' already covers.
// Zero dependencies; imported by the build, the local tests and scripts/serve.mjs.
import { readFileSync } from 'node:fs';
import { ROBOTS_NOINDEX, STAGES, resolveStage } from './stage.mjs';

// Re-exported so existing importers keep working; page code imports stage.mjs directly (see there).
export { ROBOTS_NOINDEX, STAGES, resolveStage };

/**
 * HSTS per stage (SEC-151): previews max-age=300; first public week (launch) max-age=86400;
 * then (public) two years with includeSubDomains and preload. Preload-list submission is an owner action.
 */
export function hsts(stage) {
  switch (resolveStage(stage)) {
    case 'preview':
      return 'max-age=300';
    case 'launch':
      return 'max-age=86400';
    case 'public':
      return 'max-age=63072000; includeSubDomains; preload';
  }
}

/**
 * sha256 sources for inline <script> / <style> blocks (SEC-150a). The build is configured so none are
 * needed (bundled scripts, build.inlineStylesheets: 'never'); scripts/inline-check.mjs fails the build if
 * an inline block appears whose hash is not listed here. Inline event handlers and style="" attributes
 * can only be allowed with 'unsafe-hashes', which is banned, so they always fail the build.
 */
export const INLINE_SCRIPT_HASHES = [];
export const INLINE_STYLE_HASHES = [];

/**
 * SEC-150 per-route exceptions (csp-exceptions.json, owned by the security role). Only these tokens may ever
 * be excepted, only in script-src, only on a listed route; the file is validated on load.
 */
export const EXCEPTION_TOKENS = ["'wasm-unsafe-eval'"];
export const CSP_EXCEPTIONS = (() => {
  const url = new URL('./csp-exceptions.json', import.meta.url);
  const list = JSON.parse(readFileSync(url, 'utf8')).exceptions;
  for (const e of list)
    if (
      !/^\/[a-z0-9-]+\/$/.test(e.route) ||
      e.directive !== 'script-src' ||
      !EXCEPTION_TOKENS.includes(e.token) ||
      !e.owner ||
      !e.adr
    )
      throw new Error(`csp-exceptions.json: invalid entry ${JSON.stringify(e)}`);
  return list;
})();

/**
 * Exceptions that apply to a URL path: the route ("/arena/") and everything under it. The no-slash
 * spelling ("/arena") only redirects to the route, so it keeps the stricter baseline.
 */
export function routeExceptions(route, list = CSP_EXCEPTIONS) {
  if (!route) return [];
  return list.filter((e) => route.startsWith(e.route));
}

/**
 * SEC-150, exact directive order. Add the early-access API origin to connect-src/form-action at 4.7 only.
 * `route` (a URL path) adds that route's csp-exceptions.json tokens; without it the baseline is returned.
 */
export function csp({
  scriptHashes = INLINE_SCRIPT_HASHES,
  styleHashes = INLINE_STYLE_HASHES,
  route,
  exceptions = CSP_EXCEPTIONS,
} = {}) {
  const q = (h) => `'${h}'`;
  const extra = routeExceptions(route, exceptions).map((e) => e.token);
  return [
    "default-src 'none'",
    ["script-src 'self'", ...extra, ...scriptHashes.map(q)].join(' '),
    ["style-src 'self'", ...styleHashes.map(q)].join(' '),
    "img-src 'self' data:",
    "font-src 'self'",
    "connect-src 'self'",
    "manifest-src 'self'",
    "worker-src 'self'",
    "media-src 'self'",
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    'upgrade-insecure-requests',
  ].join('; ');
}

/** SEC-152: the site never touches devices (no USB/serial/HID/Bluetooth amplifiers). */
export const PERMISSIONS_POLICY = [
  'accelerometer=()',
  'ambient-light-sensor=()',
  'autoplay=()',
  'bluetooth=()',
  'browsing-topics=()',
  'camera=()',
  'display-capture=()',
  'encrypted-media=()',
  'fullscreen=(self)',
  'geolocation=()',
  'gyroscope=()',
  'hid=()',
  'magnetometer=()',
  'microphone=()',
  'midi=()',
  'payment=()',
  'publickey-credentials-get=()',
  'screen-wake-lock=()',
  'serial=()',
  'usb=()',
  'xr-spatial-tracking=()',
].join(', ');

/** Headers on every response (SEC-150, 151, 152, 153, 154; APP-L8 X-Robots-Tag on previews). */
export function globalHeaders(stage) {
  const robots = resolveStage(stage) === 'preview' ? { 'X-Robots-Tag': ROBOTS_NOINDEX } : {};
  return {
    'Content-Security-Policy': csp(),
    'Strict-Transport-Security': hsts(stage),
    'Permissions-Policy': PERMISSIONS_POLICY,
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'Cross-Origin-Opener-Policy': 'same-origin',
    'Cross-Origin-Resource-Policy': 'same-origin',
    'Cross-Origin-Embedder-Policy': 'require-corp',
    ...robots,
  };
}

/** SEC-156: content-hashed build assets are immutable; HTML and other unhashed files revalidate. */
export const CACHE_IMMUTABLE = 'public, max-age=31536000, immutable';
export const CACHE_REVALIDATE = 'no-cache';
/** Astro writes content-hashed files here (astro.config.mjs build.assets). */
export const HASHED_ASSET_PREFIX = '/_assets/';

/**
 * Header rules for a build. `paths` are the URL paths of every emitted file outside /_assets/
 * (HTML pages as "/x/"). Per-path rules instead of a "/*" catch-all keep Cache-Control single-valued:
 * Netlify and Cloudflare Pages merge every matching rule, so a global no-cache would be appended to
 * the immutable assets.
 */
export function headerRules({ stage, paths }) {
  const rules = [{ path: '/*', headers: globalHeaders(stage) }];
  rules.push({ path: `${HASHED_ASSET_PREFIX}*`, headers: { 'Cache-Control': CACHE_IMMUTABLE } });
  for (const p of [...new Set(paths)].sort()) {
    const headers = { 'Cache-Control': CACHE_REVALIDATE };
    if (p === '/.well-known/security.txt') headers['Content-Type'] = 'text/plain; charset=utf-8';
    rules.push({ path: p, headers });
    // "/x/" is also reachable as "/x" (trailingSlash: 'ignore'); cover both spellings.
    if (p.length > 1 && p.endsWith('/')) rules.push({ path: p.slice(0, -1), headers });
  }
  return rules;
}

/** Netlify / Cloudflare Pages `_headers` text. */
export function renderHeadersFile(rules, { stage } = {}) {
  const out = [
    '# Generated by apps/web/scripts/postbuild.mjs from apps/web/security-headers.mjs. Do not edit.',
    `# SITE_STAGE=${stage ?? 'preview'} (HSTS per SEC-151). Identical for dist/clinical and dist/cosmos.`,
  ];
  for (const r of rules) {
    out.push(r.path);
    for (const [k, v] of Object.entries(r.headers)) out.push(`  ${k}: ${v}`);
  }
  return out.join('\n') + '\n';
}

/** Parse a `_headers` file back into rules (used by serve.mjs and the tests). */
export function parseHeadersFile(text) {
  const rules = [];
  let cur = null;
  for (const line of text.split(/\r?\n/)) {
    if (!line.trim() || line.trimStart().startsWith('#')) continue;
    if (/^\S/.test(line)) {
      cur = { path: line.trim(), headers: {} };
      rules.push(cur);
    } else {
      if (!cur) throw new Error(`_headers: header before any path: ${line}`);
      const i = line.indexOf(':');
      if (i < 0) throw new Error(`_headers: malformed line: ${line}`);
      cur.headers[line.slice(0, i).trim()] = line.slice(i + 1).trim();
    }
  }
  return rules;
}

function matches(pattern, path) {
  if (pattern.endsWith('*')) return path.startsWith(pattern.slice(0, -1));
  return pattern === path;
}

/** Headers a Netlify/Cloudflare-style host would send for `path` (all matching rules merged). */
export function headersForPath(rules, path) {
  const out = {};
  for (const r of rules)
    if (matches(r.path, path))
      for (const [k, v] of Object.entries(r.headers)) out[k] = out[k] ? `${out[k]}, ${v}` : v;
  return out;
}

/** CSP string -> Map(directive -> [sources]). */
export function parseCsp(value) {
  const m = new Map();
  for (const part of value.split(';')) {
    const [name, ...sources] = part.trim().split(/\s+/).filter(Boolean);
    if (!name) continue;
    if (m.has(name.toLowerCase())) throw new Error(`CSP: duplicate directive ${name}`);
    m.set(name.toLowerCase(), sources);
  }
  return m;
}

/**
 * SEC-150 unit gate: throws if the CSP has any 'unsafe-*' keyword, a wildcard, a scheme source other
 * than data: for images, or any host (only 'self', 'none', sha256 hashes and `allowedOrigins` pass;
 * allowedOrigins is for the early-access API origin at step 4.7 and is empty today).
 */
export function assertCspSafe(
  value,
  { allowedOrigins = [], route, exceptions = CSP_EXCEPTIONS } = {},
) {
  const d = parseCsp(value);
  const excepted = routeExceptions(route, exceptions).filter(
    (e) => e.directive === 'script-src' && EXCEPTION_TOKENS.includes(e.token),
  );
  for (const req of [
    'default-src',
    'script-src',
    'style-src',
    'object-src',
    'base-uri',
    'frame-ancestors',
    'form-action',
  ])
    if (!d.has(req)) throw new Error(`CSP: missing ${req}`);
  for (const [name, sources] of d) {
    for (const s of sources) {
      const low = s.toLowerCase();
      if (excepted.some((e) => e.directive === name && e.token === s)) continue;
      if (/^'unsafe-/.test(low) || low === "'wasm-unsafe-eval'")
        throw new Error(`CSP: ${name} allows ${s}`);
      if (low === "'self'" || low === "'none'") continue;
      if (/^'sha256-[a-z0-9+/]+=*'$/i.test(s)) continue;
      if (name === 'img-src' && low === 'data:') continue;
      if (allowedOrigins.includes(s)) continue;
      throw new Error(`CSP: ${name} allows a non-self source ${s}`);
    }
  }
  for (const [name, want] of [
    ['default-src', "'none'"],
    ['object-src', "'none'"],
    ['base-uri', "'none'"],
    ['frame-ancestors', "'none'"],
  ])
    if (d.get(name).join(' ') !== want) throw new Error(`CSP: ${name} must be ${want}`);
  return true;
}
