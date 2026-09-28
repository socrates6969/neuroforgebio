// Website security (SECURITY-REQUIREMENTS §A.2): headers SEC-150..156, inline check SEC-150a,
// security.txt SEC-157, and the no-storage promise the cookie statement relies on.
// Browser-level checks (CSP console violations, crossOriginIsolated, COEP + WebGL, same-origin
// requests) are CI-only Playwright: e2e/security.spec.ts.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { cpSync, mkdtempSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import {
  CACHE_IMMUTABLE,
  PERMISSIONS_POLICY,
  assertCspSafe,
  csp,
  hsts,
  parseCsp,
  resolveStage,
} from '../security-headers.mjs';
import { hostHeadersForPath, parseHostHeaders, resolveHost } from '../host-headers.mjs';
import { checkDist, scanHtml, sha256 } from '../scripts/inline-check.mjs';
import {
  assertPublicReady,
  buildDate,
  parseSecurityTxt,
  securityTxt,
} from '../scripts/security-txt.mjs';
import { postbuild } from '../scripts/postbuild.mjs';
import { createStaticServer } from '../scripts/serve.mjs';
import { brand, files, read, requireDist, walk } from './_dist.mjs';

const THEMES = ['clinical', 'cosmos'];
const headersOf = (t) => read(join(requireDist(t), '_headers'));
const rulesOf = (t) => parseHostHeaders(headersOf(t));

/* ------------------------------------------------------------ SEC-150 CSP */

test('SEC-150: the emitted CSP is exact and passes the unsafe/host gate', () => {
  for (const t of THEMES) {
    const h = hostHeadersForPath(rulesOf(t), '/');
    const value = h['Content-Security-Policy'];
    assert.equal(
      value,
      "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; manifest-src 'self'; worker-src 'self'; media-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'; upgrade-insecure-requests",
    );
    assert.equal(assertCspSafe(value), true);
  }
});

test('SEC-150: the CSP gate fails on unsafe-* keywords and on any non-self host', () => {
  const base = csp();
  const bad = [
    base.replace("script-src 'self'", "script-src 'self' 'unsafe-inline'"),
    base.replace("script-src 'self'", "script-src 'self' 'unsafe-eval'"),
    base.replace("style-src 'self'", "style-src 'self' 'unsafe-hashes' 'sha256-abc='"),
    base.replace("script-src 'self'", "script-src 'self' 'wasm-unsafe-eval'"),
    base.replace("script-src 'self'", "script-src 'self' https://cdn.jsdelivr.net"),
    base.replace("font-src 'self'", 'font-src fonts.gstatic.com'),
    base.replace("connect-src 'self'", 'connect-src *'),
    base.replace("script-src 'self'", "script-src 'self' data:"),
    base.replace("img-src 'self' data:", "img-src 'self' https:"),
    base.replace("default-src 'none'", "default-src 'self'"),
    base.replace("frame-ancestors 'none'", "frame-ancestors 'self'"),
    base.replace("object-src 'none'; ", ''),
  ];
  for (const v of bad) assert.throws(() => assertCspSafe(v), /CSP:/, v);
  // hashes and the (future, step 4.7) API origin are the only extras allowed
  assertCspSafe(base.replace("script-src 'self'", "script-src 'self' 'sha256-AbC+/9=' "));
  assertCspSafe(base.replace("connect-src 'self'", "connect-src 'self' https://api.example.org"), {
    allowedOrigins: ['https://api.example.org'],
  });
  assert.throws(() => parseCsp("script-src 'self'; script-src 'none'"), /duplicate/);
});

test('SEC-150 exception: wasm-unsafe-eval passes the gate on /arena/ only (csp-exceptions.json)', () => {
  const arena = csp({ route: '/arena/' });
  assert.equal(csp({ route: '/' }), csp(), 'no route or an unlisted route -> the exact baseline');
  assert.equal(arena, csp().replace("script-src 'self'", "script-src 'self' 'wasm-unsafe-eval'"));
  for (const r of ['/arena/', '/arena/sub/'])
    assert.equal(assertCspSafe(arena, { route: r }), true, r);
  for (const r of [undefined, '/', '/arena', '/arenax/', '/no/arena/', '/playground/'])
    assert.throws(() => assertCspSafe(arena, { route: r }), /wasm-unsafe-eval/, String(r));
  // only the listed token, only in script-src, even on /arena/
  assert.throws(
    () => assertCspSafe(arena.replace("'wasm-unsafe-eval'", "'unsafe-eval'"), { route: '/arena/' }),
    /unsafe-eval/,
  );
  assert.throws(
    () =>
      assertCspSafe(csp().replace("worker-src 'self'", "worker-src 'self' 'wasm-unsafe-eval'"), {
        route: '/arena/',
      }),
    /worker-src allows 'wasm-unsafe-eval'/,
  );
  assert.throws(
    () =>
      assertCspSafe(arena.replace("script-src 'self'", "script-src 'self' blob:"), {
        route: '/arena/',
      }),
    /non-self/,
  );
  // an unlisted token cannot be excepted, whatever the file says
  const bad = [
    { route: '/x/', directive: 'script-src', token: "'unsafe-eval'", owner: 'x', adr: 'x' },
  ];
  const x = csp({ route: '/x/', exceptions: bad });
  assert.throws(() => assertCspSafe(x, { route: '/x/', exceptions: bad }), /unsafe-eval/);
});

/* ------------------------------------------------------------ both builds identical */

test('both builds carry byte-identical _headers and _headers.json', () => {
  assert.equal(headersOf('cosmos'), headersOf('clinical'));
  assert.equal(
    read(join(requireDist('cosmos'), '_headers.json')),
    read(join(requireDist('clinical'), '_headers.json')),
  );
  const json = JSON.parse(read(join(requireDist('clinical'), '_headers.json')));
  assert.deepEqual(json.rules, rulesOf('clinical'), 'JSON copy = _headers');
});

/* ------------------------------------------------------------ SEC-151..154 snapshot */

test('SEC-151..154: header snapshot on every HTML page', () => {
  const rules = rulesOf('clinical');
  const dist = requireDist('clinical');
  const expected = {
    'Strict-Transport-Security': hsts(resolveStage()),
    'Permissions-Policy': PERMISSIONS_POLICY,
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'Cross-Origin-Opener-Policy': 'same-origin',
    'Cross-Origin-Resource-Policy': 'same-origin',
    'Cross-Origin-Embedder-Policy': 'require-corp',
    'Cache-Control': 'no-cache',
  };
  for (const f of files(dist, '.html')) {
    const rel = f.slice(dist.length).replace(/\\/g, '/');
    const url = rel === '/index.html' ? '/' : rel.replace(/index\.html$/, '');
    const h = hostHeadersForPath(rules, url);
    for (const [k, v] of Object.entries(expected)) assert.equal(h[k], v, `${url} ${k}`);
  }
  assert.match(
    PERMISSIONS_POLICY,
    /(^|, )usb=\(\)/,
    'the site must be visibly unable to reach USB amplifiers',
  );
  for (const d of ['serial=()', 'hid=()', 'bluetooth=()', 'fullscreen=(self)'])
    assert.ok(PERMISSIONS_POLICY.split(', ').includes(d), d);
});

test('SEC-151: HSTS is staged by SITE_STAGE (preview default 300, launch 86400, public 2y + preload)', () => {
  assert.equal(resolveStage(undefined), 'preview');
  assert.equal(hsts('preview'), 'max-age=300');
  assert.equal(hsts('launch'), 'max-age=86400');
  assert.equal(hsts('public'), 'max-age=63072000; includeSubDomains; preload');
  assert.throws(() => resolveStage('prod'), /SITE_STAGE/);
  assert.doesNotMatch(hsts('launch'), /preload/);
});

/* ------------------------------------------------------------ SEC-156 cache */

test('SEC-156: hashed assets are immutable, HTML and unhashed files are no-cache (one value each)', () => {
  for (const t of THEMES) {
    const dist = requireDist(t);
    const rules = rulesOf(t);
    const assets = readdirSync(join(dist, '_assets'));
    const js = assets.find((a) => a.endsWith('.js'));
    const css = assets.find((a) => a.endsWith('.css'));
    assert.ok(js && css, 'expected hashed JS and CSS');
    for (const a of [js, css]) {
      assert.match(a, /\.[A-Za-z0-9_-]{8}\.(js|css)$/, `${a} is content-hashed`);
      assert.equal(hostHeadersForPath(rules, `/_assets/${a}`)['Cache-Control'], CACHE_IMMUTABLE);
    }
    for (const p of [
      '/',
      '/security/',
      // "/security" has its own rule only in the netlify layout; Cloudflare redirects it to "/security/"
      ...(resolveHost() === 'netlify' ? ['/security'] : []),
      '/no/legal/privacy/',
      '/robots.txt',
      '/404.html',
    ])
      assert.equal(hostHeadersForPath(rules, p)['Cache-Control'], 'no-cache', p);
    assert.equal(
      hostHeadersForPath(rules, '/.well-known/security.txt')['Content-Type'],
      'text/plain; charset=utf-8',
    );
  }
});

test('serve.mjs (CI e2e server) sends the build headers', async () => {
  const dist = requireDist('cosmos');
  const server = createStaticServer(dist);
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  const base = `http://127.0.0.1:${server.address().port}`;
  try {
    const page = await fetch(`${base}/`);
    assert.equal(page.status, 200);
    assert.equal(page.headers.get('cross-origin-embedder-policy'), 'require-corp');
    assert.equal(page.headers.get('cross-origin-opener-policy'), 'same-origin');
    assert.equal(page.headers.get('cache-control'), 'no-cache');
    const cspv = page.headers.get('content-security-policy');
    assert.match(cspv, /^default-src 'none'; script-src 'self';/);
    assert.doesNotMatch(cspv, /upgrade-insecure-requests/, 'dropped only on loopback http');
    const a = readdirSync(join(dist, '_assets')).find((x) => x.endsWith('.js'));
    const asset = await fetch(`${base}/_assets/${a}`);
    assert.equal(asset.headers.get('cache-control'), CACHE_IMMUTABLE);
    assert.equal(asset.headers.get('cross-origin-resource-policy'), 'same-origin');
    const txt = await fetch(`${base}/.well-known/security.txt`);
    assert.equal(txt.headers.get('content-type'), 'text/plain; charset=utf-8');
    assert.equal((await fetch(`${base}/_headers`)).status, 404, '_headers itself is not served');
  } finally {
    server.close();
  }
});

/* ------------------------------------------------------------ SEC-150a inline code */

test('SEC-150a: no inline script, style, handler or style attribute in either build', () => {
  for (const t of THEMES) assert.deepEqual(checkDist(requireDist(t)), [], t);
});

test('SEC-150a: an injected inline-script fixture fails the check (and a CSP hash would cover it)', () => {
  const d = mkdtempSync(join(tmpdir(), 'nf-inline-'));
  try {
    const body = 'console.log(1)';
    writeFileSync(join(d, 'index.html'), `<!doctype html><p>ok</p><script>${body}</script>`);
    const problems = checkDist(d);
    assert.equal(problems.length, 1);
    assert.match(problems[0], /inline-script/);
    assert.deepEqual(checkDist(d, { scriptHashes: [sha256(body)] }), [], 'hash allowlist');
    for (const html of [
      '<button onclick="x()">x</button>',
      '<div style="color:red">x</div>',
      '<svg><rect style="fill:red"/></svg>',
      '<style>p{}</style>',
      '<a href="javascript:alert(1)">x</a>',
    ])
      assert.ok(scanHtml(html).length >= 1, html);
    assert.deepEqual(scanHtml('<script type="module" src="/_assets/a.js"></script>'), []);
    assert.deepEqual(scanHtml('<script type="application/ld+json">{}</script>'), []);
  } finally {
    rmSync(d, { recursive: true, force: true });
  }
});

test('SEC-150a: postbuild fails a build that contains inline code', () => {
  const d = mkdtempSync(join(tmpdir(), 'nf-post-'));
  try {
    cpSync(requireDist('clinical'), d, { recursive: true });
    writeFileSync(
      join(d, 'index.html'),
      read(join(d, 'index.html')).replace('</body>', '<script>alert(1)</script></body>'),
    );
    assert.throws(() => postbuild('clinical', { dist: d, stage: 'preview' }), /SEC-150a/);
  } finally {
    rmSync(d, { recursive: true, force: true });
  }
});

/* ------------------------------------------------------------ SEC-157 security.txt */

const txtOf = (t) => read(join(requireDist(t), '.well-known/security.txt'));

test('SEC-157: security.txt has the RFC 9116 fields; Expires in the future and < 365 days', () => {
  for (const t of THEMES) {
    const f = parseSecurityTxt(txtOf(t));
    assert.deepEqual(f.get('contact'), [`mailto:security@${brand.domain}`]);
    assert.equal(f.get('expires').length, 1, 'Expires exactly once');
    const exp = new Date(f.get('expires')[0]);
    assert.match(f.get('expires')[0], /^\d{4}-\d\d-\d\dT00:00:00\.000Z$/);
    const days = (exp.getTime() - Date.now()) / 86400_000;
    assert.ok(days > 0 && days < 365, `Expires ${days.toFixed(1)} days away`);
    assert.deepEqual(f.get('preferred-languages'), ['en, no']);
    assert.deepEqual(f.get('policy'), [`https://${brand.domain}/security#disclosure`]);
    assert.equal(f.get('canonical')[0], `https://${brand.domain}/.well-known/security.txt`);
    for (const v of [...f.get('canonical'), ...f.get('policy')]) assert.match(v, /^https:\/\//);
  }
});

test('SEC-157: identical in both builds except Canonical (canonical host first, then cosmos)', () => {
  const strip = (s) =>
    s
      .split('\n')
      .filter((l) => !l.startsWith('Canonical:'))
      .join('\n');
  assert.equal(strip(txtOf('cosmos')), strip(txtOf('clinical')));
  const c = parseSecurityTxt(txtOf('cosmos')).get('canonical');
  assert.deepEqual(c, [
    `https://${brand.domain}/.well-known/security.txt`,
    `https://${brand.secondaryHost}/.well-known/security.txt`,
  ]);
  assert.equal(parseSecurityTxt(txtOf('clinical')).get('canonical').length, 1);
});

test('SEC-157: Expires = build date + 180 days', () => {
  const t = securityTxt({ brand, theme: 'clinical', date: buildDate('2026-09-26') });
  assert.match(t, /^Expires: 2027-03-25T00:00:00\.000Z$/m);
  assert.throws(() => buildDate('not-a-date'), /SITE_BUILD_DATE/);
});

test('SEC-157/APP-L7: launch and public builds FAIL while placeholders remain; only previews keep them', () => {
  const txt = securityTxt({ brand, theme: 'clinical', date: buildDate() });
  assert.doesNotThrow(() => assertPublicReady(txt, { stage: 'preview', brand }));
  assert.throws(
    () => assertPublicReady(txt, { stage: 'launch', brand }),
    /SITE_STAGE=launch but placeholders remain/,
  );
  assert.throws(() => assertPublicReady(txt, { stage: 'public', brand }), /placeholders remain/);
  const tbd = txt.replace(/security@[^\s]+/, 'security@<domain TBD>');
  const real = {
    ...brand,
    domain: 'example.org',
    secondaryHost: 'cosmos.example.org',
    domainIsPlaceholder: false,
  };
  assert.throws(() => assertPublicReady(tbd, { stage: 'public', brand: real }), /placeholder/);
  const ok = securityTxt({ brand: real, theme: 'cosmos', date: buildDate() });
  assert.doesNotThrow(() => assertPublicReady(ok, { stage: 'public', brand: real }));
  // the real post-build step with today's placeholder brand.json
  const d = mkdtempSync(join(tmpdir(), 'nf-stage-'));
  try {
    cpSync(requireDist('clinical'), d, { recursive: true });
    assert.throws(() => postbuild('clinical', { dist: d, stage: 'public' }), /placeholders remain/);
    assert.throws(() => postbuild('clinical', { dist: d, stage: 'launch' }), /placeholders remain/);
  } finally {
    rmSync(d, { recursive: true, force: true });
  }
});

/* ------------------------------------------------------------ no storage (cookie statement) */

test('no cookies or web storage: built JS never touches document.cookie, localStorage, sessionStorage, IndexedDB', () => {
  // The cookie statement (legal/cookies) says the site stores nothing on the device. No exceptions today.
  const STORAGE =
    /document\s*\.\s*cookie|\blocalStorage\b|\bsessionStorage\b|\bindexedDB\b|\bcaches\s*\.\s*open|serviceWorker\s*\.\s*register/;
  const hits = [];
  for (const t of THEMES) {
    const dist = requireDist(t);
    for (const f of walk(dist))
      if (/\.(m?js|html)$/.test(f) && STORAGE.test(read(f)))
        hits.push(`${t}/${f.slice(dist.length + 1)}: ${read(f).match(STORAGE)[0]}`);
  }
  assert.deepEqual(hits, []);
});

test('no Set-Cookie anywhere in the header config', () => {
  assert.doesNotMatch(headersOf('clinical'), /set-cookie/i);
});
