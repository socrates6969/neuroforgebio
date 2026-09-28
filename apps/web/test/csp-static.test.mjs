// SEC-150 static conformance: every resource referenced by every built page, stylesheet and bundle is
// allowed by the CSP that page is served with (scripts/csp-check.mjs). The browser-level twin is the
// CI-only e2e/security.spec.ts.
import { test } from 'node:test';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
import {
  cpSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  readdirSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve, sep } from 'node:path';
import {
  allowed,
  arenaLayoutProblems,
  checkCsp,
  cssRefs,
  effectiveSources,
  htmlRefs,
  jsRefs,
  exceptionsInUse,
  reachableScripts,
  reachableWasm,
  WASM_COMPILE,
} from '../scripts/csp-check.mjs';
import { CSP_EXCEPTIONS, csp, parseCsp } from '../security-headers.mjs';
import { hostHeadersForPath, parseHostHeaders } from '../host-headers.mjs';
import { postbuild } from '../scripts/postbuild.mjs';
import { read, requireDist } from './_dist.mjs';

const policy = parseCsp(csp());
const blocks = (kind, url) => !allowed(effectiveSources(policy, kind), url);

test('csp-check: both builds reference nothing their CSP would block', () => {
  for (const t of ['clinical', 'cosmos']) assert.deepEqual(checkCsp(requireDist(t)), [], t);
});

test('csp-check: fallback chains follow CSP3 (frame-src and worker-src fall back, form-action does not)', () => {
  assert.deepEqual(effectiveSources(policy, 'frame-src'), ["'none'"], 'frame-src -> default-src');
  assert.deepEqual(effectiveSources(policy, 'worker-src'), ["'self'"]);
  assert.equal(effectiveSources(parseCsp("default-src 'none'"), 'form-action'), null);
  assert.deepEqual(
    effectiveSources(parseCsp("default-src 'none'; script-src 'self'"), 'worker-src'),
    ["'self'"],
  );
});

test('csp-check: today’s policy blocks every external or embedded load a page could add', () => {
  for (const [kind, url] of [
    ['script-src', 'https://cdn.jsdelivr.net/npm/x.js'],
    ['script-src', '//cdn.example.org/x.js'],
    ['style-src', 'https://fonts.googleapis.com/css2?family=Inter'],
    ['font-src', 'https://fonts.gstatic.com/s/inter.woff2'],
    ['font-src', 'data:font/woff2;base64,AAAA'],
    ['img-src', 'https://example.org/a.png'],
    ['frame-src', '/embed/'],
    ['frame-src', 'https://www.youtube.com/embed/x'],
    ['object-src', '/a.pdf'],
    ['form-action', 'https://forms.example.org/submit'],
    ['connect-src', 'wss://example.org/socket'],
    ['base-uri', '/'],
    ['media-src', 'https://example.org/a.mp4'],
  ])
    assert.ok(blocks(kind, url), `${kind} ${url} must be blocked`);
  for (const [kind, url] of [
    ['script-src', '/_assets/a.js'],
    ['style-src', '/_assets/a.css'],
    ['img-src', 'data:image/svg+xml,%3Csvg%3E'],
    ['img-src', '../figures/a.svg'],
    ['font-src', '/_assets/inter.woff2'],
    ['form-action', '/search/'],
    ['media-src', '/media/promo.mp4'],
  ])
    assert.ok(!blocks(kind, url), `${kind} ${url} must be allowed`);
  assert.ok(
    allowed(["'self'"], 'https://site.example/x.js', {
      siteOrigins: ['https://site.example'],
    }),
    'absolute links to the site origin are self',
  );
});

test('csp-check: extracts refs from HTML, CSS and JS the way a browser classifies them', () => {
  const kinds = (refs) => refs.map((r) => `${r.kind} ${r.url}`);
  assert.deepEqual(
    kinds(
      htmlRefs(`<!-- <script src="https://ignored.example/x.js"></script> -->
      <script type="module" src="/_assets/a.js"></script>
      <link rel="stylesheet" href="/_assets/a.css"><link rel="canonical" href="https://x.example/">
      <link rel="modulepreload" href="/_assets/b.js"><link rel="preload" as="font" href="/f.woff2">
      <link rel="icon" href="/favicon.svg"><link rel="manifest" href="/site.webmanifest">
      <img src="/a.png" srcset="/a1.png 1x, /a2.png 2x"><picture><source srcset="/p.avif"></picture>
      <video src="/v.mp4" poster="/v.jpg"><source src="/v.webm"></video>
      <iframe src="https://www.youtube.com/embed/x"></iframe><object data="/a.pdf"></object>
      <form action="https://forms.example/s"></form><form></form><base href="/">
      <a href="https://external.example/">link</a><svg><image href="/i.png"/></svg>`),
    ),
    [
      'script-src /_assets/a.js',
      'style-src /_assets/a.css',
      'script-src /_assets/b.js',
      'font-src /f.woff2',
      'img-src /favicon.svg',
      'manifest-src /site.webmanifest',
      'img-src /a.png',
      'img-src /a1.png',
      'img-src /a2.png',
      'img-src /p.avif',
      'media-src /v.mp4',
      'img-src /v.jpg',
      'media-src /v.webm',
      'frame-src https://www.youtube.com/embed/x',
      'object-src /a.pdf',
      'form-action https://forms.example/s',
      'base-uri /',
      'img-src /i.png',
    ],
  );
  assert.deepEqual(
    kinds(
      cssRefs(`/* url(https://ignored) */ @import url("https://fonts.googleapis.com/css");
      @font-face{font-family:X;src:url(/_assets/x.woff2) format("woff2")}
      .a{background:url('https://img.example/b.png')} .m{mask:url(#m)}`),
    ),
    [
      'font-src /_assets/x.woff2',
      'img-src https://img.example/b.png',
      'style-src https://fonts.googleapis.com/css',
    ],
  );
  assert.deepEqual(
    kinds(
      jsRefs(
        'fetch("https://api.example/x");fetch(U,{});new WebSocket("wss://ws.example");new Worker("https://w.example/w.js");import("//cdn.example/m.js");fetch("/data.json")',
      ),
    ),
    [
      'connect-src https://api.example/x',
      'connect-src wss://ws.example',
      'worker-src https://w.example/w.js',
      'script-src //cdn.example/m.js',
    ],
  );
});

test('csp-check: a page that adds an iframe, a CDN font and an external form fails the dist check', () => {
  const d = mkdtempSync(join(tmpdir(), 'nf-csp-'));
  try {
    cpSync(requireDist('clinical'), d, { recursive: true });
    const page = join(d, 'security/index.html');
    writeFileSync(
      page,
      read(page).replace(
        '</body>',
        '<iframe src="https://www.youtube.com/embed/x"></iframe><link rel="stylesheet" href="https://fonts.googleapis.com/css2"><form action="https://forms.example/s"></form></body>',
      ),
    );
    writeFileSync(join(d, '_assets/evil.css'), '.x{background:url(https://track.example/p.gif)}');
    const problems = checkCsp(d);
    assert.equal(problems.length, 4, problems.join('\n'));
    for (const want of [
      /frame-src blocks https:\/\/www\.youtube/,
      /style-src blocks https:\/\/fonts/,
      /form-action blocks https:\/\/forms/,
      /img-src blocks https:\/\/track/,
    ])
      assert.ok(
        problems.some((p) => want.test(p)),
        String(want),
      );
  } finally {
    rmSync(d, { recursive: true, force: true });
  }
});

/* ------------------------------------------------------------ SEC-150 /arena exception trigger */

const GLUE = '_assets/arena_core.T3st0001.js';
const CHUNK = '_assets/arena.T3st0002.js';
const WASM = '_assets/arena_core_bg.T3st0003.wasm';
const TAG = `<script type="module" src="/${CHUNK}"></script></body>`;

/**
 * A copy of the clinical dist with an /arena/ page that loads a page chunk, which dynamically imports
 * wasm-bindgen-style glue. `wasm`: the glue references a .wasm file that exists in dist.
 */
function arenaFixture({ wasm }) {
  const d = mkdtempSync(join(tmpdir(), 'nf-csp-wasm-'));
  cpSync(requireDist('clinical'), d, { recursive: true });
  const ref = wasm ? `new URL("arena_core_bg.T3st0003.wasm",import.meta.url)` : 'u';
  writeFileSync(
    join(d, GLUE),
    `export default async function init(u){return WebAssembly.instantiateStreaming(fetch(${ref}))}`,
  );
  if (wasm) writeFileSync(join(d, WASM), Buffer.from([0, 97, 115, 109, 1, 0, 0, 0]));
  writeFileSync(join(d, CHUNK), 'const m=()=>import("./arena_core.T3st0001.js");m();');
  mkdirSync(join(d, 'arena'), { recursive: true });
  writeFileSync(
    join(d, 'arena/index.html'),
    read(join(d, 'security/index.html')).replace('</body>', TAG),
  );
  return d;
}
const arenaCsp = (d) =>
  hostHeadersForPath(parseHostHeaders(read(join(d, '_headers'))), '/arena/')[
    'Content-Security-Policy'
  ];

test('SEC-150 trigger: /arena/ that reaches a .wasm activates the exception (cloudflare); netlify KEEP FAIL', () => {
  const d = arenaFixture({ wasm: true });
  try {
    assert.deepEqual(exceptionsInUse(d), CSP_EXCEPTIONS);
    assert.deepEqual(
      reachableWasm(d, join(d, 'arena/index.html'), read(join(d, 'arena/index.html'))),
      [join(d, WASM)],
      'glue -> new URL("x.wasm", import.meta.url) resolves next to the glue',
    );
    const { active } = postbuild('clinical', { dist: d, stage: 'preview', host: 'cloudflare' });
    assert.deepEqual(active, CSP_EXCEPTIONS);
    assert.equal(arenaCsp(d), csp({ route: '/arena/' }));
    assert.deepEqual(JSON.parse(read(join(d, '_headers.json'))).activeExceptions, ['/arena/']);
    assert.deepEqual(checkCsp(d), [], '/arena/ carries wasm-unsafe-eval, so it may load the glue');
    assert.throws(
      () => postbuild('clinical', { dist: d, stage: 'preview', host: 'netlify' }),
      /cannot serve the SEC-150 exception for \/arena\/.*KEEP FAIL/,
    );
    // the same glue on another route is a violation of that route's CSP
    const page = join(d, 'security/index.html');
    writeFileSync(page, read(page).replace('</body>', TAG));
    const problems = checkCsp(d);
    assert.equal(problems.length, 1, problems.join('\n'));
    assert.match(
      problems[0],
      /^security\/index\.html: script-src lacks 'wasm-unsafe-eval' but loads _assets\/arena_core/,
    );
    assert.ok(
      WASM_COMPILE.test('WebAssembly.compile(b)') &&
        !WASM_COMPILE.test('new WebAssembly.Memory({initial:1})'),
    );
  } finally {
    rmSync(d, { recursive: true, force: true });
  }
});

test('SEC-150 trigger: /arena/ shipped WITHOUT wasm keeps the baseline CSP and netlify builds', () => {
  const d = arenaFixture({ wasm: false });
  try {
    assert.deepEqual(exceptionsInUse(d), []);
    for (const host of ['cloudflare', 'netlify']) {
      // the default-on CSP gate rejects this dist (glue that compiles wasm, no token); the test opts out
      assert.throws(
        () => postbuild('clinical', { dist: d, stage: 'preview', host }),
        /CSP check: dist\/clinical contains resources its own policy blocks:[\s\S]*arena\/index\.html: script-src lacks 'wasm-unsafe-eval'/,
      );
      const { active } = postbuild('clinical', {
        dist: d,
        stage: 'preview',
        host,
        cspCheck: false,
      });
      assert.deepEqual(active, [], host);
      assert.equal(arenaCsp(d), csp(), `${host}: /arena/ gets the baseline`);
      assert.deepEqual(JSON.parse(read(join(d, '_headers.json'))).activeExceptions, [], host);
      assert.doesNotMatch(read(join(d, '_headers')), /wasm-unsafe-eval|! Content-Security-Policy/);
    }
    // glue that compiles wasm without the exception is still caught by the reachability guard
    assert.match(
      checkCsp(d).join('\n'),
      /^arena\/index\.html: script-src lacks 'wasm-unsafe-eval'/m,
    );
  } finally {
    rmSync(d, { recursive: true, force: true });
  }
});

test('SEC-150 trigger: a .wasm reachable only from another route never activates /arena/', () => {
  const d = arenaFixture({ wasm: false });
  try {
    // /security/ references a real .wasm (no compile code); /arena/ still reaches none
    writeFileSync(join(d, WASM), Buffer.from([0, 97, 115, 109, 1, 0, 0, 0]));
    writeFileSync(
      join(d, '_assets/other.T3st0004.js'),
      'export const w=new URL("arena_core_bg.T3st0003.wasm",import.meta.url);',
    );
    const page = join(d, 'security/index.html');
    writeFileSync(
      page,
      read(page).replace(
        '</body>',
        '<script type="module" src="/_assets/other.T3st0004.js"></script></body>',
      ),
    );
    // a .wasm physically under /arena/ but referenced by nothing does not count either
    writeFileSync(join(d, 'arena/stray.wasm'), Buffer.from([0, 97, 115, 109, 1, 0, 0, 0]));
    assert.equal(reachableWasm(d, page, read(page)).length, 1, 'the other route does reach it');
    assert.deepEqual(exceptionsInUse(d), []);
    const { active } = postbuild('clinical', {
      dist: d,
      stage: 'preview',
      host: 'netlify',
      cspCheck: false,
    }); // /arena/ ships wasm-compiling glue without the token: gate would (rightly) reject
    assert.deepEqual(active, []);
    assert.equal(arenaCsp(d), csp());
  } finally {
    rmSync(d, { recursive: true, force: true });
  }
});

test('SEC-150 trigger: a detection error fails strict (no exception, baseline CSP, reason reported)', () => {
  const errors = [];
  assert.deepEqual(
    exceptionsInUse(join(tmpdir(), 'nf-no-such-dist-'), { onError: (e) => errors.push(e) }),
    [],
  );
  assert.equal(errors.length, 1);
  // in the pipeline: a site that WOULD activate, with detection failing, keeps the baseline everywhere
  const d = arenaFixture({ wasm: true });
  try {
    const failing = (dist, opts) => exceptionsInUse(join(dist, 'missing-subdir'), opts);
    const { active } = postbuild('clinical', {
      dist: d,
      stage: 'preview',
      host: 'cloudflare',
      detect: failing,
      cspCheck: false, // detection failed -> baseline, so the shipped glue is (correctly) blocked
    });
    assert.deepEqual(active, []);
    assert.equal(arenaCsp(d), csp());
    assert.doesNotMatch(read(join(d, '_headers')), /wasm-unsafe-eval/);
  } finally {
    rmSync(d, { recursive: true, force: true });
  }
});

test('reachableScripts/reachableWasm never leave the dist root', () => {
  const root = mkdtempSync(join(tmpdir(), 'nf-escape-'));
  try {
    const d = join(root, 'dist');
    mkdirSync(join(d, '_assets'), { recursive: true });
    writeFileSync(join(root, 'outside.js'), 'WebAssembly.compile(b)');
    writeFileSync(join(root, 'outside.wasm'), '');
    writeFileSync(
      join(d, '_assets/a.js'),
      'import("../../outside.js");new URL("../../outside.wasm",import.meta.url)',
    );
    const html =
      '<script type="module" src="/_assets/a.js"></script><script src="/../outside.js"></script>';
    writeFileSync(join(d, 'index.html'), html);
    assert.deepEqual(reachableScripts(d, join(d, 'index.html'), html), [
      resolve(d, '_assets/a.js'),
    ]);
    assert.deepEqual(reachableWasm(d, join(d, 'index.html'), html), []);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

/**
 * The CANONICAL arena layout (lead ruling, 2026-09-27): glue and .wasm are content-hashed Vite assets in the
 * shared /_assets/, imported from src/; nothing under /arena/pkg/. The /arena/ page chunk imports the hashed
 * glue, and the glue references the hashed .wasm (wasm-bindgen: new URL('<name>.wasm', import.meta.url)).
 */
function hashedArena(d, { from = 'arena' } = {}) {
  const wasm = '_assets/arena_core_bg.Ab12Cd34.wasm';
  writeFileSync(join(d, wasm), Buffer.from([0, 97, 115, 109, 1, 0, 0, 0]));
  writeFileSync(
    join(d, '_assets/arena_core.Ef56Gh78.js'),
    "export default async function __wbg_init(m){if(typeof m==='undefined'){m=new URL('arena_core_bg.Ab12Cd34.wasm',import.meta.url)}const {instance}=await WebAssembly.instantiateStreaming(fetch(m),{});return instance}",
  );
  writeFileSync(
    join(d, '_assets/arena.Ij90Kl12.js'),
    'const e=async()=>{const t=await import("./arena_core.Ef56Gh78.js");await t.default()};e();',
  );
  const tag = '<script type="module" src="/_assets/arena.Ij90Kl12.js"></script></body>';
  const base = read(join(d, 'security/index.html'));
  mkdirSync(join(d, 'arena'), { recursive: true });
  // the /arena/ page loads the chunk only when from === 'arena'; otherwise /security/ does
  writeFileSync(
    join(d, 'arena/index.html'),
    from === 'arena' ? base.replace('</body>', tag) : base,
  );
  if (from !== 'arena') writeFileSync(join(d, 'security/index.html'), base.replace('</body>', tag));
  return wasm;
}

test('SEC-150 trigger (canonical): /arena/ chunk -> hashed glue in /_assets/ -> hashed .wasm in /_assets/', () => {
  const d = mkdtempSync(join(tmpdir(), 'nf-arena-hashed-'));
  try {
    cpSync(requireDist('clinical'), d, { recursive: true });
    const wasm = hashedArena(d);
    const html = read(join(d, 'arena/index.html'));
    assert.deepEqual(reachableWasm(d, join(d, 'arena/index.html'), html), [resolve(d, wasm)]);
    assert.deepEqual(exceptionsInUse(d), CSP_EXCEPTIONS);
    const { active } = postbuild('clinical', { dist: d, stage: 'preview', host: 'cloudflare' });
    assert.deepEqual(active, CSP_EXCEPTIONS);
    assert.deepEqual(checkCsp(d), []);
    // /_assets/ is shared: only /arena/ documents get the arena CSP; the hashed glue and .wasm responses keep
    // the baseline (compilation is governed by the loading document's CSP) and the immutable cache
    const rules = parseHostHeaders(read(join(d, '_headers')));
    const cspOf = (u) => hostHeadersForPath(rules, u)['Content-Security-Policy'];
    for (const u of ['/arena/', '/arena/index.html'])
      assert.equal(cspOf(u), csp({ route: '/arena/' }), u);
    for (const u of [
      '/',
      '/security/',
      '/playground/',
      `/${wasm}`,
      '/_assets/arena_core.Ef56Gh78.js',
      '/_assets/arena.Ij90Kl12.js',
      '/does-not-exist',
    ])
      assert.equal(cspOf(u), csp(), u);
    for (const u of [`/${wasm}`, '/_assets/arena_core.Ef56Gh78.js'])
      assert.equal(
        hostHeadersForPath(rules, u)['Cache-Control'],
        'public, max-age=31536000, immutable',
        u,
      );
    assert.throws(
      () => postbuild('clinical', { dist: d, stage: 'preview', host: 'netlify' }),
      /KEEP FAIL/,
    );
  } finally {
    rmSync(d, { recursive: true, force: true });
  }
});

test('SEC-150 trigger (canonical): the same hashed glue + .wasm loaded only by another route never activates /arena/', () => {
  const d = mkdtempSync(join(tmpdir(), 'nf-arena-shared-'));
  try {
    cpSync(requireDist('clinical'), d, { recursive: true });
    const wasm = hashedArena(d, { from: 'security' });
    assert.equal(
      reachableWasm(d, join(d, 'security/index.html'), read(join(d, 'security/index.html'))).length,
      1,
      '/security/ reaches the shared .wasm',
    );
    assert.deepEqual(
      reachableWasm(d, join(d, 'arena/index.html'), read(join(d, 'arena/index.html'))),
      [],
    );
    assert.deepEqual(
      exceptionsInUse(d),
      [],
      'a .wasm in shared /_assets/ does not count for /arena/',
    );
    const { active } = postbuild('clinical', {
      dist: d,
      stage: 'preview',
      host: 'netlify',
      cspCheck: false,
    }); // /security/ loads wasm-compiling glue without the token: gate would (rightly) reject
    assert.deepEqual(active, []);
    assert.equal(arenaCsp(d), csp());
    // and /security/ loading wasm-compiling glue without the token is itself a violation
    assert.match(
      checkCsp(d).join('\n'),
      /^security\/index\.html: script-src lacks 'wasm-unsafe-eval' but loads _assets\/arena_core\.Ef56Gh78\.js/m,
    );
    assert.ok(existsSync(join(d, wasm)));
  } finally {
    rmSync(d, { recursive: true, force: true });
  }
});

test('arena checklist 1: public/arena/pkg files or unhashed arena/wasm assets anywhere in dist fail checkCsp', () => {
  const d = mkdtempSync(join(tmpdir(), 'nf-arena-layout-'));
  try {
    cpSync(requireDist('clinical'), d, { recursive: true });
    hashedArena(d); // the canonical hashed layout alone is clean
    postbuild('clinical', { dist: d, stage: 'preview', host: 'cloudflare' });
    assert.deepEqual(arenaLayoutProblems(d), []);
    assert.deepEqual(checkCsp(d), []);
    // the voided public/ layout, a stray unhashed .wasm, and unhashed glue each fail
    mkdirSync(join(d, 'arena/pkg'), { recursive: true });
    writeFileSync(join(d, 'arena/pkg/arena_core.js'), 'export default 1');
    writeFileSync(join(d, 'arena/pkg/arena_core_bg.1a2b3c4d.wasm'), '');
    writeFileSync(join(d, '_assets/arena_core_bg.wasm'), '');
    writeFileSync(join(d, '_assets/arena_core.js'), 'export default 1');
    writeFileSync(join(d, 'research/x.wasm'), '');
    // upper-case names must not slip past (nfb-security nit 1); distinct names, since Windows is case-insensitive
    writeFileSync(join(d, 'research/Y.WASM'), '');
    writeFileSync(join(d, 'research/ARENA_CORE_LOADER.MJS'), '');
    const problems = arenaLayoutProblems(d);
    assert.deepEqual(problems.map((p) => p.split(':')[0]).sort(), [
      '_assets/arena_core.js',
      '_assets/arena_core_bg.wasm',
      'arena/pkg/arena_core.js',
      'arena/pkg/arena_core_bg.1a2b3c4d.wasm',
      'research/ARENA_CORE_LOADER.MJS',
      'research/Y.WASM',
      'research/x.wasm',
    ]);
    for (const p of problems) assert.ok(checkCsp(d).includes(p), `checkCsp reports ${p}`);
  } finally {
    rmSync(d, { recursive: true, force: true });
  }
});

test('arena checklist 5: stub state (pkg/ absent, no loader) -> exception inactive, baseline CSP, checkCsp passes', () => {
  // nfb-arena's /arena renders the plain "unavailable" state without any wasm loader when pkg/ is absent
  const d = mkdtempSync(join(tmpdir(), 'nf-arena-stub-'));
  try {
    cpSync(requireDist('clinical'), d, { recursive: true });
    mkdirSync(join(d, 'arena'), { recursive: true });
    cpSync(join(d, 'security/index.html'), join(d, 'arena/index.html'));
    assert.deepEqual(exceptionsInUse(d), []);
    for (const host of ['cloudflare', 'netlify']) {
      const { active } = postbuild('clinical', { dist: d, stage: 'preview', host });
      assert.deepEqual(active, [], host);
      assert.deepEqual(JSON.parse(read(join(d, '_headers.json'))).activeExceptions, [], host);
      assert.equal(arenaCsp(d), csp(), host);
      assert.deepEqual(checkCsp(d), [], host);
    }
  } finally {
    rmSync(d, { recursive: true, force: true });
  }
});

test('arena checklist 1 (enforcing, real dist): no /arena/pkg/, no unhashed arena_core*.js or .wasm in either build', () => {
  // vacuous until the arena package ships; then it enforces the lead's final layout on every build
  for (const t of ['clinical', 'cosmos']) {
    const dist = requireDist(t);
    assert.ok(!existsSync(join(dist, 'arena/pkg')), `${t}: dist/arena/pkg/ must not exist`);
    assert.deepEqual(arenaLayoutProblems(dist), [], t);
  }
});

test('postbuild CLI: the default-on CSP gate fails the build on a blocked dist (--dist), passes a clean one', () => {
  const script = fileURLToPath(new URL('../scripts/postbuild.mjs', import.meta.url));
  const run = (dist) =>
    spawnSync(process.execPath, [script, 'clinical', '--dist', dist], { encoding: 'utf8' });
  const bad = arenaFixture({ wasm: false }); // /arena/ loads wasm-compiling glue, no exception
  const good = mkdtempSync(join(tmpdir(), 'nf-cli-good-'));
  try {
    const r = run(bad);
    assert.equal(r.status, 1, r.stderr);
    assert.match(
      r.stderr,
      /\[postbuild\] FAILED: CSP check: dist\/clinical contains resources its own policy blocks/,
    );
    assert.match(r.stderr, /arena\/index\.html: script-src lacks 'wasm-unsafe-eval'/);
    cpSync(requireDist('clinical'), good, { recursive: true });
    const ok = run(good);
    assert.equal(ok.status, 0, ok.stderr);
    assert.equal(
      spawnSync(process.execPath, [script, 'clinical', '--dist'], { encoding: 'utf8' }).status,
      2,
      'usage error',
    );
  } finally {
    rmSync(bad, { recursive: true, force: true });
    rmSync(good, { recursive: true, force: true });
  }
});

test('the cspCheck opt-out is test-only: no `cspCheck: false` outside apps/web/test/', () => {
  // nfb-build-queen: a deploy script or the site-rs driver must never copy the opt-out from a test
  const repo = fileURLToPath(new URL('../../../', import.meta.url));
  const SKIP = new Set(['node_modules', 'dist', 'target', '.astro', '.git']);
  const hits = [];
  const scan = (dir) => {
    for (const n of readdirSync(dir, { withFileTypes: true })) {
      const p = join(dir, n.name);
      if (n.isDirectory()) {
        if (!SKIP.has(n.name) && p !== join(repo, 'apps/web/test')) scan(p);
      } else if (/\.(m?[jt]s|rs|json|ya?ml)$/.test(n.name) && /cspCheck\s*:\s*false/.test(read(p)))
        hits.push(p.slice(repo.length).split(sep).join('/'));
    }
  };
  for (const d of ['apps/web', 'tools', '.github']) scan(join(repo, d));
  assert.deepEqual(hits, []);
});

test('real state (both builds): the /arena exception is active exactly when the CI pkg/ is committed', () => {
  // stub state (no apps/web/src/assets/arena/pkg): activeExceptions [] and baseline everywhere;
  // real state (pkg/ committed after a green arena-wasm run): ['/arena/'], arena CSP on /arena/ pages only
  const pkg = fileURLToPath(new URL('../src/assets/arena/pkg', import.meta.url));
  const real = existsSync(pkg);
  for (const t of ['clinical', 'cosmos']) {
    const dist = requireDist(t);
    const json = JSON.parse(read(join(dist, '_headers.json')));
    assert.deepEqual(json.activeExceptions, real ? ['/arena/'] : [], `${t} activeExceptions`);
    const rules = parseHostHeaders(read(join(dist, '_headers')));
    const cspOf = (u) => hostHeadersForPath(rules, u)['Content-Security-Policy'];
    assert.equal(cspOf('/arena/'), real ? csp({ route: '/arena/' }) : csp(), `${t} /arena/`);
    for (const u of ['/', '/security/', '/playground/', '/_assets/x.AbCd1234.wasm'])
      assert.equal(cspOf(u), csp(), `${t} ${u}`);
  }
});

test('the cspCheck opt-out is refused outside node --test, however it is passed', () => {
  // nfb-build-queen nit 1: the grep guard only sees the literal; this refuses a variable/spread false too
  const mod = new URL('../scripts/postbuild.mjs', import.meta.url).href;
  const env = { ...process.env };
  delete env.NODE_TEST_CONTEXT;
  const code = `import(${JSON.stringify(mod)}).then(({ postbuild }) => {
    const opts = { cspCheck: [false][0] };
    try { postbuild('clinical', { dist: 'does-not-matter', ...opts }); console.log('NOT REFUSED'); }
    catch (e) { console.log(e.message); }
  });`;
  const r = spawnSync(process.execPath, ['--input-type=module', '-e', code], {
    encoding: 'utf8',
    env,
  });
  assert.match(r.stdout, /the CSP check can only be turned off under node --test/, r.stderr);
  assert.ok(process.env.NODE_TEST_CONTEXT, 'node --test sets NODE_TEST_CONTEXT for this file');
});
