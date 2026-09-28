// Built-console checks (run by scripts/test.mjs after `vite build` + postbuild):
// CSP/no-inline (SEC-150/150a), no web storage or cookies, no eval, no third-party origins (SEC-155),
// self-hosted fonts, bundle budget.
import assert from 'node:assert/strict';
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { gzipSync } from 'node:zlib';
import { dirname, join, resolve } from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { scanHtml } from '../../web/scripts/inline-check.mjs';
import { inlineProblems } from '../scripts/postbuild.mjs';
import {
  assertCspSafe,
  connectOrigins,
  consoleConfig,
  csp,
  parseCsp,
} from '../security-headers.mjs';

const CONSOLE = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const DIST = join(CONSOLE, 'dist');

function files(dir, out = []) {
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) files(p, out);
    else out.push(p);
  }
  return out;
}

const all = existsSync(DIST) ? files(DIST) : [];
const js = all.filter((f) => f.endsWith('.js'));
const css = all.filter((f) => f.endsWith('.css'));
const html = all.filter((f) => f.endsWith('.html'));
const text = (list) => list.map((f) => readFileSync(f, 'utf8')).join('\n');

test('dist exists with one HTML shell, hashed JS and CSS', () => {
  assert.ok(existsSync(join(DIST, 'index.html')), 'run the build first');
  assert.equal(html.length, 1);
  assert.ok(js.length >= 1 && css.length >= 1);
  for (const f of [...js, ...css])
    assert.match(f.replace(/\\/g, '/'), /\/assets\/[\w.-]+-[\w-]{8}\.(js|css)$/);
});

test('no inline script, style, handler or javascript: URL in the built HTML (SEC-150a)', () => {
  assert.deepEqual(inlineProblems(DIST), []);
  const shell = readFileSync(join(DIST, 'index.html'), 'utf8');
  assert.match(
    shell,
    /<script type="module" crossorigin src="\/assets\/index-[\w-]+\.js"><\/script>/,
  );
  assert.match(shell, /<html lang="en" data-theme="clinical">/);
});

test('the inline check catches an injected inline script (fixture)', () => {
  const bad =
    '<html><body><script>alert(1)</script><div style="x" onclick="y"></div></body></html>';
  const kinds = scanHtml(bad).map((p) => p.kind);
  assert.deepEqual(kinds.sort(), ['event-handler', 'inline-script', 'style-attribute']);
});

test('_headers carries the strict CSP and the SEC-151..154 headers', () => {
  const headers = readFileSync(join(DIST, '_headers'), 'utf8');
  const value = /Content-Security-Policy: (.+)/.exec(headers)[1];
  assertCspSafe(value, { allowedOrigins: connectOrigins(consoleConfig()) });
  const d = parseCsp(value);
  assert.deepEqual(d.get('script-src'), ["'self'"]);
  assert.deepEqual(d.get('style-src'), ["'self'"]);
  assert.deepEqual(d.get('require-trusted-types-for'), ["'script'"]);
  assert.deepEqual(d.get('frame-ancestors'), ["'none'"]);
  for (const h of [
    'Strict-Transport-Security: max-age=',
    'X-Frame-Options: DENY',
    'X-Content-Type-Options: nosniff',
    'Referrer-Policy: strict-origin-when-cross-origin',
    'Cross-Origin-Opener-Policy: same-origin',
    'Cross-Origin-Embedder-Policy: require-corp',
    'Permissions-Policy: accelerometer=()',
    'Cache-Control: no-store',
    'Cache-Control: public, max-age=31536000, immutable',
  ])
    assert.ok(headers.includes(h), h);
});

test('assertCspSafe rejects unsafe-inline, unsafe-eval, wildcards and stray hosts', () => {
  const withScript = (s) => csp().replace("script-src 'self'", `script-src 'self' ${s}`);
  assert.throws(() => assertCspSafe(withScript("'unsafe-inline'")));
  assert.throws(() => assertCspSafe(withScript("'unsafe-eval'")));
  assert.throws(() => assertCspSafe(csp({ connect: ['https://*.example.com'] })));
  assert.throws(() => assertCspSafe(csp({ connect: ['https://idp.example.com'] })));
  assert.doesNotThrow(() =>
    assertCspSafe(csp({ connect: ['https://idp.example.com'] }), {
      allowedOrigins: ['https://idp.example.com'],
    }),
  );
  assert.deepEqual(
    connectOrigins({
      issuer: 'https://idp.example.com/realms/x',
      apiBase: 'https://api.example.com',
    }),
    ['https://api.example.com', 'https://idp.example.com'],
  );
  assert.throws(() => connectOrigins({ issuer: 'http://idp.example.com', apiBase: '' }), /https/);
});

test('no cookies or web storage: the bundle never touches document.cookie, localStorage, sessionStorage, IndexedDB, caches or service workers', () => {
  const bad =
    /document\s*\.\s*cookie|\blocalStorage\b|\bsessionStorage\b|\bindexedDB\b|\bcaches\s*\.\s*open|serviceWorker\s*\.\s*register/;
  for (const f of js) assert.doesNotMatch(readFileSync(f, 'utf8'), bad, f);
});

test('no eval or string-compiled code in the bundle', () => {
  const src = text(js);
  assert.doesNotMatch(src, /\beval\s*\(/);
  assert.doesNotMatch(src, /new\s+Function\s*\(/);
  assert.doesNotMatch(src, /\bsetTimeout\s*\(\s*["'`]/);
});

test('no third-party origins: every absolute URL in the build is an inert string (SEC-155)', () => {
  // Allowed: XML namespaces and React's error-decoder link (text in error messages, never fetched).
  const INERT = [/^http:\/\/www\.w3\.org\//, /^https:\/\/react\.dev\/errors\//];
  const urls = new Set(text([...js, ...css, ...html]).match(/https?:\/\/[^\s"'`)<>\\]+/g) ?? []);
  const stray = [...urls].filter((u) => !INERT.some((re) => re.test(u)));
  assert.deepEqual(stray, []);
  // fonts: self-hosted files only, no data: fonts (font-src 'self')
  const styles = text(css);
  const fontUrls = [...styles.matchAll(/url\(([^)]+)\)/g)].map((m) => m[1]);
  assert.ok(fontUrls.length > 0);
  for (const u of fontUrls) assert.match(u, /^\/assets\/[\w.-]+\.(woff2?|ttf)$/, u);
  assert.match(styles, /IBM Plex Sans/);
});

test('bundle budget: JS <= 110 KB gzip, CSS <= 10 KB gzip', () => {
  const gz = (list) => list.reduce((n, f) => n + gzipSync(readFileSync(f)).length, 0);
  const jsGz = gz(js);
  const cssGz = gz(css);
  console.log(
    `console bundle: JS ${(jsGz / 1024).toFixed(1)} KB gzip, CSS ${(cssGz / 1024).toFixed(1)} KB gzip`,
  );
  assert.ok(jsGz <= 110 * 1024, `JS ${jsGz} bytes gzip`);
  assert.ok(cssGz <= 10 * 1024, `CSS ${cssGz} bytes gzip`);
});
