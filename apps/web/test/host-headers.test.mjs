// Host-ready `_headers` for Netlify and Cloudflare Pages (host-headers.mjs). The first tests run without
// a build (synthetic site paths); the last ones re-run postbuild on a copy of the real dist per host.
// Owner post-deploy checklist: docs/hive/HOSTING-HEADERS.md.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { cpSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import {
  CF_MAX_LINE,
  CF_MAX_RULES,
  HOSTS,
  assertCloudflareLimits,
  hostHeadersForPath,
  hostRules,
  parseHostHeaders,
  patternRegExp,
  renderHostHeaders,
  resolveHost,
} from '../host-headers.mjs';
import {
  CACHE_IMMUTABLE,
  assertCspSafe,
  csp,
  headerRules,
  parseCsp,
  renderHeadersFile,
  routeExceptions,
  CSP_EXCEPTIONS,
} from '../security-headers.mjs';
import { postbuild, sitePaths } from '../scripts/postbuild.mjs';
import { exceptionsInUse } from '../scripts/csp-check.mjs';
import { files, read, requireDist, urlPath } from './_dist.mjs';

// A site shaped like today's build, with `pages` extra inner pages (the hive keeps adding them).
function sitePathsFixture(pages = 0) {
  const p = [
    '/',
    '/404.html',
    '/.well-known/security.txt',
    '/robots.txt',
    '/sitemap.xml',
    '/research/files/p4_capacity_vs_M.svg',
    '/security/',
    '/no/security/',
    '/developers/api/',
  ];
  for (let i = 0; i < pages; i++) p.push(`/page-${i}/`);
  return p;
}

const ARENA_TOKEN = "'wasm-unsafe-eval'";

/**
 * Owner requirements, asserted on a parsed `_headers` for one URL. SEC-150 exception condition 1: the CSP
 * is the baseline byte for byte, except on an excepted route, where it is the baseline plus exactly the
 * listed token in script-src.
 */
function assertPolicy(h, where, url = where, active = []) {
  const value = h['Content-Security-Policy'];
  const d = parseCsp(value);
  assert.equal(assertCspSafe(value, { route: url }), true, where);
  const excepted = routeExceptions(url, active);
  assert.equal(value, excepted.length ? csp({ route: url }) : csp(), `${where} CSP snapshot`);
  if (excepted.length) {
    const base = parseCsp(csp());
    for (const [k, v] of base)
      assert.deepEqual(d.get(k), k === 'script-src' ? [...v, ARENA_TOKEN] : v, `${where} ${k}`);
    assert.equal(d.size, base.size, `${where} no extra directive`);
  } else assert.equal(value, csp(), `${where} baseline CSP`);
  assert.deepEqual(d.get('frame-ancestors'), ["'none'"], `${where} frame-ancestors`);
  assert.deepEqual(
    d.get('script-src'),
    excepted.length ? ["'self'", ARENA_TOKEN] : ["'self'"],
    `${where} script-src`,
  );
  assert.deepEqual(d.get('default-src'), ["'none'"], `${where} default-src`);
  assert.match(h['Strict-Transport-Security'], /^max-age=\d+/, `${where} HSTS`);
  assert.equal(h['X-Content-Type-Options'], 'nosniff', where);
  assert.equal(h['Referrer-Policy'], 'strict-origin-when-cross-origin', where);
  assert.equal(h['X-Frame-Options'], 'DENY', where);
  assert.equal(h['Cross-Origin-Opener-Policy'], 'same-origin', where);
  assert.equal(h['Cross-Origin-Embedder-Policy'], 'require-corp', where);
  assert.equal(h['Cross-Origin-Resource-Policy'], 'same-origin', where);
  const pp = h['Permissions-Policy'].split(', ');
  for (const f of ['camera', 'microphone', 'geolocation', 'usb', 'serial', 'hid', 'bluetooth'])
    assert.ok(pp.includes(`${f}=()`), `${where} Permissions-Policy denies ${f}`);
  assert.equal(h['Set-Cookie'], undefined, where);
}

test('SITE_HOST: cloudflare by default, netlify on request, anything else fails', () => {
  assert.equal(resolveHost(undefined), 'cloudflare');
  assert.equal(resolveHost(' netlify '), 'netlify');
  assert.equal(resolveHost(' cloudflare '), 'cloudflare');
  assert.deepEqual(HOSTS, ['netlify', 'cloudflare']);
  assert.throws(() => resolveHost('vercel'), /SITE_HOST/);
});

test('netlify output is byte-identical to the pre-existing renderHeadersFile(headerRules())', () => {
  const paths = sitePathsFixture(5);
  const want = renderHeadersFile(headerRules({ stage: 'preview', paths }), { stage: 'preview' });
  const rules = hostRules('netlify', { stage: 'preview', paths });
  assert.equal(renderHostHeaders('netlify', rules, { stage: 'preview' }), want);
});

test('cloudflare output stays within 100 rules as pages grow; the per-path layout does not', () => {
  for (const pages of [0, 50, 500]) {
    const paths = sitePathsFixture(pages);
    const cf = renderHostHeaders('cloudflare', hostRules('cloudflare', { stage: 'public', paths }));
    const n = assertCloudflareLimits(cf);
    assert.equal(n, 9, `${pages} extra pages -> ${n} rules (page count must not matter)`);
  }
  const big = renderHeadersFile(headerRules({ stage: 'public', paths: sitePathsFixture(60) }));
  assert.throws(() => assertCloudflareLimits(big), /rules > 100/);
  assert.throws(
    () => assertCloudflareLimits(`/*\n  X: ${'a'.repeat(CF_MAX_LINE)}\n`),
    /chars > 2000/,
  );
  assert.equal(CF_MAX_RULES, 100);
});

test('splat patterns match like the hosts document ("*" greedy, anchored)', () => {
  assert.ok(patternRegExp('/*/').test('/a/b/'));
  assert.ok(!patternRegExp('/*/').test('/'));
  assert.ok(!patternRegExp('/*/').test('/robots.txt'));
  assert.ok(patternRegExp('/*.html').test('/404.html'));
  assert.ok(!patternRegExp('/*.html').test('/404xhtml'), 'dot is literal');
  assert.ok(patternRegExp('/_assets/*').test('/_assets/a.1234abcd.js'));
  assert.ok(!patternRegExp('/robots.txt').test('/robots.txt.bak'));
});

test('both hosts: every URL gets the full policy and exactly one Cache-Control value', () => {
  const paths = sitePathsFixture(3);
  for (const host of HOSTS) {
    for (const stage of ['preview', 'launch', 'public']) {
      const text = renderHostHeaders(host, hostRules(host, { stage, paths }), { stage });
      const rules = parseHostHeaders(text);
      const urls = [...paths, '/_assets/index.AbCd1234.js', '/_assets/site.AbCd1234.css'];
      for (const u of urls) {
        const h = hostHeadersForPath(rules, u);
        assertPolicy(h, `${host}/${stage} ${u}`, u);
        const want = u.startsWith('/_assets/') ? CACHE_IMMUTABLE : 'no-cache';
        assert.equal(h['Cache-Control'], want, `${host}/${stage} ${u} Cache-Control`);
      }
      const txt = hostHeadersForPath(rules, '/.well-known/security.txt');
      assert.equal(txt['Content-Type'], 'text/plain; charset=utf-8', `${host} security.txt`);
    }
  }
});

test('HSTS preload is only sent by public builds, on both hosts', () => {
  const paths = sitePathsFixture();
  for (const host of HOSTS) {
    const hsts = (stage) =>
      hostHeadersForPath(hostRules(host, { stage, paths }), '/')['Strict-Transport-Security'];
    assert.equal(hsts('public'), 'max-age=63072000; includeSubDomains; preload', host);
    assert.doesNotMatch(hsts('launch'), /preload|includeSubDomains/, host);
    assert.doesNotMatch(hsts('preview'), /preload|includeSubDomains/, host);
  }
});

/* ------------------------------------------------------------ SEC-150 route exceptions */

const ARENA_SITE = [...sitePathsFixture(3), '/arena/', '/arena/data/runs.json'];

test('SEC-150 exception: csp-exceptions.json lists only /arena/ with wasm-unsafe-eval, owned by nfb-security', () => {
  const list = JSON.parse(read(new URL('../csp-exceptions.json', import.meta.url))).exceptions;
  assert.deepEqual(
    list.map((e) => [e.route, e.directive, e.token, e.owner]),
    [['/arena/', 'script-src', ARENA_TOKEN, 'nfb-security']],
  );
});

test('SEC-150 exception: inactive by default; an active exception needs its route built', () => {
  // /arena/ built but no wasm detected (active = [] from exceptionsInUse): baseline everywhere, netlify builds
  for (const host of HOSTS) {
    const rules = hostRules(host, { stage: 'public', paths: ARENA_SITE });
    for (const u of ['/arena/', '/arena/index.html', '/'])
      assertPolicy(hostHeadersForPath(rules, u), `${host} ${u} (no wasm)`, u);
  }
  // an "active" entry for a route that is not built, or not in csp-exceptions.json, is ignored
  const fake = { ...CSP_EXCEPTIONS[0] };
  for (const active of [CSP_EXCEPTIONS, [fake]]) {
    const paths = active === CSP_EXCEPTIONS ? sitePathsFixture(3) : ARENA_SITE;
    assert.doesNotThrow(() => hostRules('netlify', { stage: 'public', paths, active }));
    const cf = hostRules('cloudflare', { stage: 'public', paths, active });
    assert.ok(!cf.some((r) => r.detach), 'no detach rule');
  }
});

test('SEC-150 exception: netlify refuses to build a site with /arena/ (nfb-security KEEP FAIL)', () => {
  assert.throws(
    () => hostRules('netlify', { stage: 'public', paths: ARENA_SITE, active: CSP_EXCEPTIONS }),
    /KEEP FAIL/,
  );
  assert.doesNotThrow(() => hostRules('netlify', { stage: 'public', paths: sitePathsFixture(3) }));
});

test('SEC-150 exception: cloudflare gives /arena/ (and below) its own CSP and every other URL the baseline, byte for byte', () => {
  for (const stage of ['preview', 'public']) {
    const rules = hostRules('cloudflare', { stage, paths: ARENA_SITE, active: CSP_EXCEPTIONS });
    const text = renderHostHeaders('cloudflare', rules, { stage });
    assertCloudflareLimits(text);
    assert.match(
      text,
      /^\/arena\/\*\n {2}! Content-Security-Policy\n {2}Content-Security-Policy: /m,
    );
    const parsed = parseHostHeaders(text);
    assert.deepEqual(parsed, rules, 'render/parse round trip keeps the detach');
    const urls = [
      ...ARENA_SITE,
      '/arena/sub/',
      '/arena/index.html',
      '/arena',
      '/arenax/',
      '/no/arena/',
      '/does-not-exist',
      '/_assets/arena_core_bg.AbCd1234.wasm',
    ];
    for (const u of urls) {
      const h = hostHeadersForPath(parsed, u);
      assertPolicy(h, `cloudflare/${stage} ${u}`, u, CSP_EXCEPTIONS);
      assert.doesNotMatch(h['Content-Security-Policy'], /, /, `${u}: exactly one policy`);
    }
    for (const u of ['/arena/', '/arena/index.html'])
      assert.equal(
        hostHeadersForPath(parsed, u)['Content-Security-Policy'],
        csp({ route: '/arena/' }),
        `${u} gets the arena CSP`,
      );
    for (const u of ['/', '/arenax/', '/_assets/arena_core_bg.AbCd1234.wasm', '/does-not-exist'])
      assert.doesNotMatch(hostHeadersForPath(parsed, u)['Content-Security-Policy'], /wasm/, u);
  }
});

test("parseHostHeaders: detach lines must come before the rule's headers", () => {
  assert.throws(() => parseHostHeaders('/a/*\n  X-A: 1\n  ! X-A\n'), /detach after a header/);
  assert.deepEqual(parseHostHeaders('/a/*\n  ! X-A\n  X-A: 2\n'), [
    { path: '/a/*', detach: ['X-A'], headers: { 'X-A': '2' } },
  ]);
  const rules = [
    { path: '/*', headers: { 'X-A': '1', 'X-B': '1' } },
    { path: '/a/*', detach: ['X-A'], headers: { 'X-A': '2' } },
  ];
  assert.deepEqual(hostHeadersForPath(rules, '/a/'), { 'X-A': '2', 'X-B': '1' });
  assert.deepEqual(hostHeadersForPath(rules, '/b/'), { 'X-A': '1', 'X-B': '1' });
});

/* ------------------------------------------------------------ real dist */

test('dist: the _headers CSP is the only CSP (no <meta http-equiv> copy that could drift) and equals csp()', () => {
  // A meta CSP cannot carry frame-ancestors and would be a second policy to keep in sync.
  for (const t of ['clinical', 'cosmos']) {
    const dist = requireDist(t);
    const rules = parseHostHeaders(read(join(dist, '_headers')));
    assert.equal(hostHeadersForPath(rules, '/')['Content-Security-Policy'], csp(), t);
    for (const f of files(dist, '.html'))
      assert.doesNotMatch(read(f), /http-equiv\s*=\s*["']?content-security-policy/i, f);
  }
});

for (const host of HOSTS) {
  test(`dist: postbuild SITE_HOST=${host} emits a _headers that parses and holds the policy on every page`, () => {
    const d = mkdtempSync(join(tmpdir(), `nf-host-${host}-`));
    try {
      cpSync(requireDist('clinical'), d, { recursive: true });
      const active = exceptionsInUse(d);
      if (host === 'netlify' && active.length) {
        // nfb-security KEEP FAIL: no Netlify build while an excepted route (e.g. /arena/) is built
        assert.throws(
          () => postbuild('clinical', { dist: d, stage: 'preview', host }),
          /KEEP FAIL/,
        );
        return;
      }
      postbuild('clinical', { dist: d, stage: 'preview', host });
      const text = read(join(d, '_headers'));
      if (host === 'cloudflare') assertCloudflareLimits(text);
      const rules = parseHostHeaders(text);
      const json = JSON.parse(read(join(d, '_headers.json')));
      assert.equal(json.host, host);
      assert.deepEqual(json.rules, rules, '_headers.json = _headers');
      for (const f of files(d, '.html')) {
        const u = urlPath(d, f);
        const h = hostHeadersForPath(rules, u);
        assertPolicy(h, `${host} ${u}`, u, active);
        assert.equal(h['Cache-Control'], 'no-cache', `${host} ${u}`);
      }
      for (const p of sitePaths(d))
        assert.equal(hostHeadersForPath(rules, p)['Cache-Control'], 'no-cache', p);
    } finally {
      rmSync(d, { recursive: true, force: true });
    }
  });
}

test('serve.mjs (local e2e server) serves .wasm as application/wasm (instantiateStreaming needs it)', async () => {
  const { TYPES } = await import('../scripts/serve.mjs');
  assert.equal(TYPES['.wasm'], 'application/wasm');
});

test('SEC-150 exception (cond. 1/7): serve.mjs sends the arena CSP on /arena/ AND /arena/index.html, the baseline elsewhere', async () => {
  const d = mkdtempSync(join(tmpdir(), 'nf-serve-arena-'));
  const server = { close() {} };
  try {
    cpSync(requireDist('clinical'), d, { recursive: true });
    mkdirSync(join(d, 'arena'), { recursive: true });
    // the exception is active only because /arena/ reaches a .wasm (loader -> new URL(..., import.meta.url))
    writeFileSync(
      join(d, '_assets/core.AbCd1234.wasm'),
      Buffer.from([0, 97, 115, 109, 1, 0, 0, 0]),
    );
    writeFileSync(
      join(d, '_assets/loader.AbCd1234.js'),
      'export const w = new URL("core.AbCd1234.wasm", import.meta.url);',
    );
    writeFileSync(
      join(d, 'arena/index.html'),
      read(join(d, 'security/index.html')).replace(
        '</body>',
        '<script type="module" src="/_assets/loader.AbCd1234.js"></script></body>',
      ),
    );
    postbuild('clinical', { dist: d, stage: 'preview', host: 'cloudflare' });
    const { createStaticServer } = await import('../scripts/serve.mjs');
    const s = createStaticServer(d);
    server.close = () => s.close();
    await new Promise((r) => s.listen(0, '127.0.0.1', r));
    const base = `http://127.0.0.1:${s.address().port}`;
    // serve.mjs drops only upgrade-insecure-requests on loopback http
    const local = (v) => v.replace('; upgrade-insecure-requests', '');
    for (const p of ['/arena/', '/arena/index.html']) {
      const res = await fetch(`${base}${p}`);
      assert.equal(res.status, 200, p);
      assert.equal(res.headers.get('content-security-policy'), local(csp({ route: '/arena/' })), p);
    }
    for (const p of ['/', '/security/', '/does-not-exist'])
      assert.equal(
        (await fetch(`${base}${p}`)).headers.get('content-security-policy'),
        local(csp()),
        p,
      );
    const wasm = await fetch(`${base}/_assets/core.AbCd1234.wasm`);
    assert.equal(wasm.headers.get('content-type'), 'application/wasm');
  } finally {
    server.close();
    rmSync(d, { recursive: true, force: true });
  }
});
