#!/usr/bin/env node
// Static CSP conformance check (SEC-150) over every built page, offline and in milliseconds.
// For each resource a page or stylesheet references, it finds the CSP directive a browser would use and
// checks the URL against that directive's sources in the EMITTED _headers. This catches the next
// iframe, CDN font, external image or form target before CI's Playwright run (e2e/security.spec.ts,
// which sees runtime violations) and without a browser. Inline code is scripts/inline-check.mjs (SEC-150a).
// Not covered here: URLs built at runtime in JS; bundles are only scanned for literal external URLs
// handed to fetch / Worker / WebSocket / EventSource / import() / sendBeacon. SEC-150 exceptions: a page
// whose CSP lacks 'wasm-unsafe-eval' must not reach (via script src and relative .js imports) any bundle
// that compiles WebAssembly.
// Usage: node scripts/csp-check.mjs <distDir...>   (exit 1 on any violation)
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { hostHeadersForPath, parseHostHeaders } from '../host-headers.mjs';
import { CSP_EXCEPTIONS, parseCsp } from '../security-headers.mjs';

function* walk(dir) {
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) yield* walk(p);
    else yield p;
  }
}

/** CSP fallback chains (CSP3): the first directive present in the policy wins. */
const FALLBACK = {
  'script-src': ['script-src', 'default-src'],
  'style-src': ['style-src', 'default-src'],
  'img-src': ['img-src', 'default-src'],
  'font-src': ['font-src', 'default-src'],
  'media-src': ['media-src', 'default-src'],
  'object-src': ['object-src', 'default-src'],
  'manifest-src': ['manifest-src', 'default-src'],
  'connect-src': ['connect-src', 'default-src'],
  'worker-src': ['worker-src', 'child-src', 'script-src', 'default-src'],
  'frame-src': ['frame-src', 'child-src', 'default-src'],
  // no fallback: absent means unrestricted
  'form-action': ['form-action'],
  'base-uri': ['base-uri'],
};

/** Sources that apply to `kind` under the parsed policy, or null if the kind is unrestricted. */
export function effectiveSources(policy, kind) {
  for (const d of FALLBACK[kind]) if (policy.has(d)) return policy.get(d);
  return null;
}

/**
 * Is `url` (as written in the page at `pagePath`) allowed by `sources`? Relative and same-origin URLs
 * match 'self'. `siteOrigins` are the origins the site is served from (absolute self-links).
 */
export function allowed(sources, url, { siteOrigins = [] } = {}) {
  if (sources === null) return true;
  const low = sources.map((s) => s.toLowerCase());
  if (low.length === 1 && low[0] === "'none'") return false;
  const scheme = /^([a-z][a-z0-9+.-]*):/i.exec(url)?.[1]?.toLowerCase();
  if (!scheme || url.startsWith('//')) {
    if (url.startsWith('//')) return low.includes(url.split('/').slice(0, 3).join('/'));
    return low.includes("'self'");
  }
  if (low.includes(`${scheme}:`)) return true;
  if (scheme === 'http' || scheme === 'https' || scheme === 'ws' || scheme === 'wss') {
    const origin = new URL(url).origin;
    if (siteOrigins.includes(origin) && low.includes("'self'")) return true;
    return sources.includes(origin);
  }
  return false; // data:, blob:, javascript: ... only by explicit scheme source
}

const attr = (tag, name) =>
  new RegExp(`\\s${name}\\s*=\\s*(?:"([^"]*)"|'([^']*)'|([^\\s>]+))`, 'i')
    .exec(tag)
    ?.slice(1)
    .find((v) => v !== undefined);

const PRELOAD_AS = {
  script: 'script-src',
  style: 'style-src',
  image: 'img-src',
  font: 'font-src',
  fetch: 'connect-src',
  audio: 'media-src',
  video: 'media-src',
  track: 'media-src',
  worker: 'worker-src',
};

/** Resource references in one HTML document: [{kind, url, tag}]. <a href> is navigation, not CSP. */
export function htmlRefs(html) {
  const refs = [];
  const src = html.replace(/<!--[\s\S]*?-->/g, '');
  const push = (kind, url, tag) => {
    if (url !== undefined && url.trim() !== '' && !url.trim().startsWith('#'))
      refs.push({ kind, url: url.trim(), tag: tag.slice(0, 80) });
  };
  for (const m of src.matchAll(
    /<(script|link|img|source|video|audio|track|iframe|frame|object|embed|form|base|image|use|input|button)\b[^>]*>/gi,
  )) {
    const [tag, nameRaw] = m;
    const name = nameRaw.toLowerCase();
    if (name === 'script') push('script-src', attr(tag, 'src'), tag);
    else if (name === 'link') {
      const rel = (attr(tag, 'rel') ?? '').toLowerCase().split(/\s+/);
      const href = attr(tag, 'href');
      if (rel.includes('stylesheet')) push('style-src', href, tag);
      else if (rel.includes('modulepreload')) push('script-src', href, tag);
      else if (rel.includes('manifest')) push('manifest-src', href, tag);
      else if (rel.includes('icon') || rel.includes('apple-touch-icon')) push('img-src', href, tag);
      else if (rel.includes('preload') || rel.includes('prefetch')) {
        const as = (attr(tag, 'as') ?? '').toLowerCase();
        if (PRELOAD_AS[as]) push(PRELOAD_AS[as], href, tag);
      }
    } else if (
      name === 'img' ||
      name === 'image' ||
      name === 'use' ||
      (name === 'input' && /type\s*=\s*["']?image/i.test(tag))
    ) {
      push('img-src', attr(tag, 'src') ?? attr(tag, 'href') ?? attr(tag, 'xlink:href'), tag);
      for (const c of (attr(tag, 'srcset') ?? '').split(','))
        push('img-src', c.trim().split(/\s+/)[0], tag);
    } else if (name === 'source') {
      // <source> inside <picture> is an image; inside <video>/<audio> it is media
      push(
        attr(tag, 'srcset') !== undefined ? 'img-src' : 'media-src',
        attr(tag, 'src') ?? attr(tag, 'srcset')?.split(/[\s,]/)[0],
        tag,
      );
    } else if (name === 'video' || name === 'audio' || name === 'track') {
      push('media-src', attr(tag, 'src'), tag);
      if (name === 'video') push('img-src', attr(tag, 'poster'), tag);
    } else if (name === 'iframe' || name === 'frame') {
      // an iframe with no src still loads about:blank, which CSP allows; any src is checked
      push('frame-src', attr(tag, 'src'), tag);
    } else if (name === 'object') push('object-src', attr(tag, 'data') ?? 'about:object', tag);
    else if (name === 'embed') push('object-src', attr(tag, 'src') ?? 'about:embed', tag);
    else if (name === 'form') push('form-action', attr(tag, 'action'), tag);
    else if (name === 'button' || name === 'input')
      push('form-action', attr(tag, 'formaction'), tag);
    else if (name === 'base') push('base-uri', attr(tag, 'href'), tag);
  }
  for (const m of src.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style\s*>/gi))
    refs.push(...cssRefs(m[1]));
  return refs;
}

/** url(...) references in CSS: fonts inside @font-face, images elsewhere; @import is a stylesheet. */
export function cssRefs(css) {
  const refs = [];
  const clean = css.replace(/\/\*[\s\S]*?\*\//g, '');
  const faces = [...clean.matchAll(/@font-face\s*\{[^}]*\}/gi)].map((m) => [
    m.index,
    m.index + m[0].length,
  ]);
  const inFace = (i) => faces.some(([a, b]) => i >= a && i < b);
  for (const m of clean.matchAll(/url\(\s*(?:"([^"]*)"|'([^']*)'|([^)\s]*))\s*\)/gi)) {
    const url = m[1] ?? m[2] ?? m[3];
    if (/@import\s+$/i.test(clean.slice(Math.max(0, m.index - 20), m.index))) continue; // below
    if (!url || url.startsWith('#')) continue; // SVG fragment references are not fetches
    refs.push({ kind: inFace(m.index) ? 'font-src' : 'img-src', url, tag: m[0].slice(0, 80) });
  }
  for (const m of clean.matchAll(/@import\s+(?:url\()?\s*["']?([^"')\s;]+)/gi))
    refs.push({ kind: 'style-src', url: m[1], tag: m[0].slice(0, 80) });
  return refs;
}

const JS_SINKS = [
  [/\bfetch\(\s*["'`]((?:https?:)?\/\/[^"'`]+)/g, 'connect-src'],
  [/\bnew\s+(?:WebSocket|EventSource)\(\s*["'`]([a-z]+:\/\/[^"'`]+)/g, 'connect-src'],
  [/\bsendBeacon\(\s*["'`]((?:https?:)?\/\/[^"'`]+)/g, 'connect-src'],
  [/\bnew\s+(?:Shared)?Worker\(\s*["'`]((?:https?:)?\/\/[^"'`]+)/g, 'worker-src'],
  [/\bimport\(\s*["'`]((?:https?:)?\/\/[^"'`]+)/g, 'script-src'],
];

/** Literal external URLs passed to network sinks in a JS bundle. */
export function jsRefs(js) {
  const refs = [];
  for (const [re, kind] of JS_SINKS)
    for (const m of js.matchAll(re)) refs.push({ kind, url: m[1], tag: m[0].slice(0, 80) });
  return refs;
}

const urlOf = (dist, f) => {
  const rel = relative(dist, f).split(sep).join('/');
  if (rel === 'index.html') return '/';
  return rel.endsWith('/index.html') ? `/${rel.slice(0, -'index.html'.length)}` : `/${rel}`;
};

/**
 * Check one built dist against its own _headers. Returns ["<file>: <directive> blocks <url> (<tag>)"].
 * CSS and JS are checked against the policy of the page URL "/" (every page carries the same CSP).
 */
export function checkCsp(dist, { siteOrigins = [] } = {}) {
  const rules = parseHostHeaders(readFileSync(join(dist, '_headers'), 'utf8'));
  const problems = [];
  const policyFor = (p) => {
    const v = hostHeadersForPath(rules, p)['Content-Security-Policy'];
    if (!v) throw new Error(`csp-check: no Content-Security-Policy for ${p}`);
    return parseCsp(v);
  };
  const report = (file, policy, refs) => {
    for (const r of refs) {
      if (/^(about:blank)$/i.test(r.url)) continue;
      if (!allowed(effectiveSources(policy, r.kind), r.url, { siteOrigins }))
        problems.push(
          `${relative(dist, file).split(sep).join('/')}: ${r.kind} blocks ${r.url} (${r.tag})`,
        );
    }
  };
  const root = policyFor('/');
  for (const f of walk(dist)) {
    if (f.endsWith('.html')) {
      const policy = policyFor(urlOf(dist, f));
      const html = readFileSync(f, 'utf8');
      report(f, policy, htmlRefs(html));
      // SEC-150 exceptions: a page may only reach WebAssembly-compiling code if its CSP allows it
      const wasmOk = (policy.get('script-src') ?? []).includes("'wasm-unsafe-eval'");
      if (!wasmOk)
        for (const js of reachableScripts(dist, f, html))
          if (WASM_COMPILE.test(readFileSync(js, 'utf8')))
            problems.push(
              `${relative(dist, f).split(sep).join('/')}: script-src lacks 'wasm-unsafe-eval' but loads ${relative(dist, js).split(sep).join('/')}, which compiles WebAssembly`,
            );
    } else if (f.endsWith('.css')) report(f, root, cssRefs(readFileSync(f, 'utf8')));
    else if (/\.m?js$/.test(f)) report(f, root, jsRefs(readFileSync(f, 'utf8')));
  }
  problems.push(...arenaLayoutProblems(dist));
  return problems;
}

/** A Vite content-hashed build asset: /_assets/<name>.<8-char hash>.<ext> (astro.config.mjs build.assets). */
const HASHED_ASSET = /^_assets\/[^/]+\.[A-Za-z0-9_-]{8}\.[a-z0-9]+$/;

/**
 * nfb-security arena checklist item 1 (lead's final ruling, 2026-09-27): the arena package is imported through
 * Vite from src/assets/arena/pkg, so its glue and .wasm exist only as content-hashed /_assets/ files. Anything
 * under /arena/pkg/ (the voided public/ layout), any .wasm, or any arena_core*.js that is not such a hashed
 * asset fails the check. It checks the SHAPE of the name only, not that the hash derives from the content:
 * Vite produces the names, and the byte-level integrity of the .wasm is proven separately (nfb-build-queen's
 * dist == pkg test, security/arena-pkg.sha256). This guard is not an integrity check.
 */
export function arenaLayoutProblems(dist) {
  const problems = [];
  for (const f of walk(dist)) {
    const rel = relative(dist, f).split(sep).join('/');
    if (rel.startsWith('arena/pkg/'))
      problems.push(
        `${rel}: arena package file outside the hashed build assets (nothing may live under /arena/pkg/)`,
      );
    else if (
      (/\.wasm$/i.test(rel) || /(^|\/)arena_core[^/]*\.m?js$/i.test(rel)) &&
      !HASHED_ASSET.test(rel)
    )
      problems.push(`${rel}: unhashed arena/wasm asset (must be a content-hashed /_assets/ file)`);
  }
  return problems;
}

/** Code that compiles WebAssembly (needs 'wasm-unsafe-eval'); a bare WebAssembly.Memory etc. does not. */
export const WASM_COMPILE =
  /WebAssembly\s*\.\s*(instantiateStreaming|compileStreaming|instantiate|compile|Module)\b/;

/**
 * Same-origin JS files a page can load: its <script src> and modulepreloads, then (transitively) every
 * relative "*.js" string literal in those files that resolves to a file in dist (static and dynamic
 * imports, Vite's preload maps). An over-approximation, which is the safe direction for this check.
 */
export function reachableScripts(dist, htmlFile, html) {
  const seen = new Set();
  const queue = [];
  const add = (from, url) => {
    // confined to dist (nfb-security nit 1): a "../../x.js" literal never reads outside the build
    const f = distFile(dist, from, url);
    if (f && !seen.has(f)) {
      seen.add(f);
      queue.push(f);
    }
  };
  for (const r of htmlRefs(html)) if (r.kind === 'script-src') add(htmlFile, r.url);
  while (queue.length) {
    const f = queue.shift();
    for (const m of readFileSync(f, 'utf8').matchAll(
      /["'`]((?:\.{1,2}\/|\/)[^"'`\s]+\.m?js)["'`]/g,
    ))
      add(f, m[1]);
  }
  return [...seen];
}

/** Resolve a URL written in `from` (a dist file) to a dist file path, or null (external / outside dist). */
function distFile(dist, from, url) {
  if (/^[a-z]+:|^\/\//i.test(url)) return null;
  const clean = url.split(/[?#]/)[0];
  const f = resolve(clean.startsWith('/') ? join(dist, clean) : join(dirname(from), clean));
  const root = resolve(dist);
  return f.startsWith(root + sep) && existsSync(f) ? f : null;
}

/**
 * .wasm files in dist that a page can load: referenced from its HTML or, as a string literal, from any
 * script it can reach (wasm-bindgen's `new URL('x_bg.wasm', import.meta.url)` resolves against the script).
 */
export function reachableWasm(dist, htmlFile, html) {
  const out = new Set();
  const addIn = (from, text) => {
    for (const m of text.matchAll(/["'`]([^"'`\s]+\.wasm)(?:[?#][^"'`\s]*)?["'`]/g)) {
      const f = distFile(dist, from, m[1]);
      if (f) out.add(f);
    }
  };
  addIn(htmlFile, html);
  for (const js of reachableScripts(dist, htmlFile, html)) addIn(js, readFileSync(js, 'utf8'));
  return [...out];
}

/**
 * SEC-150 exceptions in use (lead/web-queen trigger, 2026-09-27): an exception is active only when a page
 * under its route is built AND that page can reach a .wasm file in dist. A .wasm reachable only from other
 * routes never activates it. Any error during detection fails strict: no exception (baseline CSP
 * everywhere), and `onError` is told why.
 */
export function exceptionsInUse(dist, { list = CSP_EXCEPTIONS, onError = () => {} } = {}) {
  try {
    const pages = [...walk(dist)].filter((f) => f.endsWith('.html'));
    return list.filter((e) =>
      pages.some(
        (f) =>
          urlOf(dist, f).startsWith(e.route) &&
          reachableWasm(dist, f, readFileSync(f, 'utf8')).length > 0,
      ),
    );
  } catch (err) {
    onError(err);
    return [];
  }
}

const isMain = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  const dirs = process.argv.slice(2);
  if (!dirs.length) {
    console.error('usage: node scripts/csp-check.mjs <distDir...>');
    process.exit(2);
  }
  let bad = 0;
  for (const d of dirs) {
    const problems = checkCsp(resolve(d));
    bad += problems.length;
    console.error(
      problems.length ? `csp-check ${d}:\n  ${problems.join('\n  ')}` : `csp-check ${d}: clean`,
    );
  }
  process.exit(bad ? 1 : 0);
}
