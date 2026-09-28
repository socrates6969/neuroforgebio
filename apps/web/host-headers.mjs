// Host-specific `_headers` layouts for the ONE policy in security-headers.mjs (which stays the single
// source of every header value; this file only decides which paths carry them).
//
// Netlify and Cloudflare Pages both read dist/<theme>/_headers and both merge every matching rule,
// joining a repeated header with ", ". They differ in one way that matters here:
//   - Netlify: no documented rule limit, so the per-path layout from headerRules() is used as-is.
//   - Cloudflare Pages: at most 100 rules and 2,000 characters per line
//     (developers.cloudflare.com/pages/configuration/headers, read 2026-09-27). headerRules() emits one
//     rule per page and per trailing-slash spelling, which grows with every new page (80 already in a
//     devportal build), so Cloudflare gets a fixed-size layout that uses documented splat patterns:
//     "/" and "/*/" for pages, "/*.html" for the 404 page, one rule per other unhashed file.
// Select with SITE_HOST=cloudflare|netlify (default cloudflare: the only host that can serve a SEC-150
// route exception; the owner has not chosen a host yet, the lead recommends Cloudflare Pages).
//
// SEC-150 per-route exceptions (csp-exceptions.json, e.g. 'wasm-unsafe-eval' on /arena/): a second CSP
// header would be joined as "A, B" and browsers enforce both, so the route must carry ONLY its own CSP.
//   - Cloudflare documents "! Header" (detach): "/arena/*" detaches the baseline CSP and sets the route's.
//     The splat is taken to match the empty string too (so "/arena/" is covered); if the host disagrees,
//     the route keeps the stricter baseline and wasm fails closed. The post-deploy checklist verifies it.
//   - Netlify documents no detach, so a netlify build FAILS while an exception is active
//     (nfb-security decision "KEEP FAIL", 2026-09-27; docs/hive/T3-ARENA-WASM-PLAN.md).
// Which exceptions are active is decided from the built dist by scripts/csp-check.mjs exceptionsInUse()
// (route built AND a .wasm reachable from it) and passed in as `active`; the default is none (strict).
// Zero dependencies.
import {
  CACHE_IMMUTABLE,
  CACHE_REVALIDATE,
  CSP_EXCEPTIONS,
  HASHED_ASSET_PREFIX,
  csp,
  globalHeaders,
  headerRules,
  renderHeadersFile,
} from './security-headers.mjs';

export const HOSTS = ['netlify', 'cloudflare'];

export function resolveHost(value = process.env.SITE_HOST) {
  const host = value && value.trim() ? value.trim() : 'cloudflare';
  if (!HOSTS.includes(host))
    throw new Error(`SITE_HOST must be one of ${HOSTS.join('|')}, got "${host}"`);
  return host;
}

/** Cloudflare Pages `_headers` limits (see header comment). */
export const CF_MAX_RULES = 100;
export const CF_MAX_LINE = 2000;

const SECURITY_TXT = '/.well-known/security.txt';
const CSP = 'Content-Security-Policy';

/** Only listed exceptions whose route is built can be active, whatever the caller passes. */
function checkedActive(active, paths) {
  return active.filter(
    (e) => CSP_EXCEPTIONS.includes(e) && paths.some((p) => p.startsWith(e.route)),
  );
}

/**
 * Cloudflare layout: the rule count depends on the number of unhashed non-HTML files, not on pages.
 * Cache-Control stays single-valued because no two cache rules can match the same served URL
 * (pages end in "/", the 404 page in ".html", hashed assets live under /_assets/, the rest are exact).
 */
export function cloudflareRules({ stage, paths, active = [] }) {
  const rules = [{ path: '/*', headers: globalHeaders(stage) }];
  rules.push({ path: `${HASHED_ASSET_PREFIX}*`, headers: { 'Cache-Control': CACHE_IMMUTABLE } });
  const revalidate = { 'Cache-Control': CACHE_REVALIDATE };
  rules.push({ path: '/', headers: revalidate });
  rules.push({ path: '/*/', headers: revalidate });
  rules.push({ path: '/*.html', headers: revalidate });
  for (const p of [...new Set(paths)].sort()) {
    if (p.endsWith('/') || p.endsWith('.html') || p.startsWith(HASHED_ASSET_PREFIX)) continue;
    const headers = { ...revalidate };
    if (p === SECURITY_TXT) headers['Content-Type'] = 'text/plain; charset=utf-8';
    rules.push({ path: p, headers });
  }
  for (const e of checkedActive(active, paths))
    rules.push({ path: `${e.route}*`, detach: [CSP], headers: { [CSP]: csp({ route: e.route }) } });
  return rules;
}

/**
 * Rules for `host`; `paths` as for headerRules() (postbuild.mjs sitePaths()); `active` the SEC-150
 * exceptions in use (csp-check.mjs exceptionsInUse()), default none.
 */
export function hostRules(host, { stage, paths, active: requested = [] }) {
  const active = checkedActive(requested, paths);
  if (resolveHost(host) === 'cloudflare') return cloudflareRules({ stage, paths, active });
  if (active.length)
    throw new Error(
      `SITE_HOST=netlify cannot serve the SEC-150 exception for ${active.map((e) => e.route).join(', ')} ` +
        '(Netlify has no header detach; nfb-security: KEEP FAIL). Build with SITE_HOST=cloudflare.',
    );
  return headerRules({ stage, paths });
}

/** `_headers` text for `host`. The netlify text is exactly renderHeadersFile() (unchanged bytes). */
export function renderHostHeaders(host, rules, { stage } = {}) {
  if (resolveHost(host) === 'netlify') return renderHeadersFile(rules, { stage });
  const lines = renderHeadersFile([], { stage }).trimEnd().split('\n');
  lines.push(
    '# SITE_HOST=cloudflare: splat layout within the Cloudflare Pages limit of 100 rules.',
  );
  for (const r of rules) {
    lines.push(r.path);
    for (const k of r.detach ?? []) lines.push(`  ! ${k}`);
    for (const [k, v] of Object.entries(r.headers)) lines.push(`  ${k}: ${v}`);
  }
  return lines.join('\n') + '\n';
}

/** Parse either layout; Cloudflare "! Header" lines become rule.detach (rules shaped as rendered). */
export function parseHostHeaders(text) {
  const rules = [];
  let cur = null;
  for (const line of text.split(/\r?\n/)) {
    if (!line.trim() || line.trimStart().startsWith('#')) continue;
    if (/^\S/.test(line)) {
      cur = { path: line.trim(), headers: {} };
      rules.push(cur);
      continue;
    }
    if (!cur) throw new Error(`_headers: header before any path: ${line}`);
    const t = line.trim();
    if (t.startsWith('!')) {
      if (Object.keys(cur.headers).length)
        throw new Error(`_headers: detach after a header in ${cur.path}`);
      const next = {
        path: cur.path,
        detach: [...(cur.detach ?? []), t.slice(1).trim()],
        headers: {},
      };
      rules[rules.length - 1] = next;
      cur = next;
      continue;
    }
    const i = t.indexOf(':');
    if (i < 0) throw new Error(`_headers: malformed line: ${line}`);
    cur.headers[t.slice(0, i).trim()] = t.slice(i + 1).trim();
  }
  return rules;
}

/** Throws unless `text` fits Cloudflare Pages' documented `_headers` limits. */
export function assertCloudflareLimits(text) {
  const lines = text.split(/\r?\n/);
  const ruleCount = lines.filter((l) => /^\//.test(l)).length;
  if (ruleCount > CF_MAX_RULES)
    throw new Error(
      `Cloudflare _headers: ${ruleCount} rules > ${CF_MAX_RULES}; rules past the limit would not apply`,
    );
  const long = lines.find((l) => l.length > CF_MAX_LINE);
  if (long)
    throw new Error(`Cloudflare _headers: a line has ${long.length} chars > ${CF_MAX_LINE}`);
  return ruleCount;
}

/** A `_headers` path pattern as a RegExp: "*" is a greedy splat anywhere (both hosts document this). */
export function patternRegExp(pattern) {
  const esc = pattern.split('*').map((s) => s.replace(/[.+?^${}()|[\]\\]/g, '\\$&'));
  return new RegExp(`^${esc.join('.*')}$`);
}

/**
 * Headers a Netlify/Cloudflare host sends for `path`: every matching rule merged, repeats joined ", ".
 * A detached header keeps only the values set by the rules that detach it (Cloudflare "! Header").
 */
export function hostHeadersForPath(rules, path) {
  const matching = rules.filter((r) => patternRegExp(r.path).test(path));
  const detached = new Set(matching.flatMap((r) => r.detach ?? []));
  const out = {};
  for (const r of matching)
    for (const [k, v] of Object.entries(r.headers)) {
      if (detached.has(k) && !(r.detach ?? []).includes(k)) continue;
      out[k] = out[k] ? `${out[k]}, ${v}` : v;
    }
  return out;
}
