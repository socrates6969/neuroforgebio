// Decoder Arena (/arena): standalone page, no shared-file edits (site.ts, @nf/content, sitemap,
// Base.astro, homepage). Checks the source stays self-contained, and that both built themes
// render correctly in whichever of the two states the build was in (nfb-security's EXC-150-1
// checklist items 1/2/5, ADR 0014):
//   - pkg/ absent (the normal state -- apps/web/src/assets/arena/pkg/ is a CI artifact, never
//     committed here): a plain "unavailable" message, no arena.ts script, no wasm/arena_core
//     reference anywhere in the page's HTML or scripts (checklist item 1: nothing under
//     public/arena, no unhashed arena files in dist).
//   - pkg/ present (only when someone has manually built it in for local testing): the full
//     interactive controls/card/leaderboard, evaluator imported normally (no @vite-ignore,
//     checklist item 2) so it ships as a content-hashed Vite asset.
import assert from 'node:assert/strict';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { test } from 'node:test';
import { REPO, WEB, attrs, brand, files, read, requireDist, visibleText } from './_dist.mjs';

const THEMES = ['clinical', 'cosmos'];
const ARENA_ASTRO = join(WEB, 'src/pages/arena/index.astro');
const ARENA_TS = join(WEB, 'src/scripts/arena.ts');
const LOADER_REAL = join(WEB, 'src/assets/arena/loader.mjs');
const LOADER_STUB = join(WEB, 'src/assets/arena/loader-stub.mjs');
const PKG_DIR = join(WEB, 'src/assets/arena/pkg');
const wasmAvailable =
  existsSync(join(PKG_DIR, 'arena_core.js')) && existsSync(join(PKG_DIR, 'arena_core_bg.wasm'));

test('source: if pkg/ exists, its manifest (security/arena-pkg.sha256) exists too', () => {
  // pkg/ is a CI-built, hash-gated artifact (tools/arena-core/README.md); it's usually absent
  // on a feature branch, but the lead's ruling is that a reviewed, CI-verified pkg/ + manifest
  // CAN be committed to ship a build -- so this doesn't assert absence, only that the two never
  // drift apart. The actual hash comparison (pkg/ == manifest == what's served) is
  // arena-wasm.test.mjs's job.
  const manifestPresent = existsSync(join(REPO, 'security/arena-pkg.sha256'));
  assert.equal(
    wasmAvailable,
    manifestPresent,
    `pkg/ present=${wasmAvailable}, manifest present=${manifestPresent} -- must match`,
  );
});

test('source: nothing arena-related lives under public/ (checklist item 1)', () => {
  const pub = join(WEB, 'public');
  const hits = existsSync(join(pub, 'arena')) ? [join(pub, 'arena')] : [];
  assert.deepEqual(hits, [], 'apps/web/public/arena/ must not exist (superseded scheme)');
});

test('source: the two loader variants agree on their exported shape', () => {
  const real = readFileSync(LOADER_REAL, 'utf8');
  const stub = readFileSync(LOADER_STUB, 'utf8');
  for (const name of ['AVAILABLE', 'initArena', 'runMcRttEvaluation']) {
    assert.ok(real.includes(name), `loader.mjs missing export ${name}`);
    assert.ok(stub.includes(name), `loader-stub.mjs missing export ${name}`);
  }
});

test('source: the loader is a normal Vite import, never @vite-ignore (checklist item 2)', () => {
  const real = readFileSync(LOADER_REAL, 'utf8');
  // Comments are allowed to mention @vite-ignore (loader.mjs documents that it deliberately
  // doesn't use it); only an actual `/* @vite-ignore */ import(...)` would defeat Vite's
  // resolution, so check for that specific pattern rather than the bare substring.
  assert.ok(
    !/\/\*\s*@vite-ignore\s*\*\/\s*import\(/.test(real),
    'loader.mjs must let Vite resolve and hash its imports',
  );
  assert.match(
    real,
    /from\s+['"]\.\/pkg\/arena_core\.js['"]/,
    'expected a normal import of the glue',
  );
  assert.match(
    real,
    /from\s+['"]\.\/pkg\/arena_core_bg\.wasm\?url['"]/,
    'expected the .wasm imported via ?url so Vite content-hashes it',
  );
  assert.match(
    real,
    /init\(\s*\{\s*module_or_path\s*:\s*wasmUrl\s*\}\s*\)/,
    'expected init({ module_or_path: wasmUrl }) -- the whole point of importing the .wasm via ?url',
  );
});

test('source: arena.ts makes exactly one fetch() call, and never touches a platform API path', () => {
  const ts = readFileSync(ARENA_TS, 'utf8');
  const fetchCalls = ts.match(/\bfetch\(/g) ?? [];
  assert.equal(
    fetchCalls.length,
    1,
    'expected exactly one fetch() (the same-origin dataset asset)',
  );
  assert.ok(
    !ts.includes('/v1/'),
    'no platform/API route references (nfb-security checklist item 5)',
  );
});

test('source: astro.config.mjs aliases virtual:arena-loader based on pkg/ presence', () => {
  const cfg = readFileSync(join(WEB, 'astro.config.mjs'), 'utf8');
  assert.match(cfg, /'virtual:arena-loader'/);
  assert.match(cfg, /arenaPkgAvailable/);
});

test('source: src/pages/arena/ contains only index.astro (regression: a stray .md there was a real, live /arena/DESIGN/ route -- caught by actually running the build, not by inspection; design docs live in docs/hive/ARENA-DESIGN.md instead)', () => {
  const entries = readdirSync(join(WEB, 'src/pages/arena'));
  assert.deepEqual(entries, ['index.astro']);
});

test('source: the page does not touch shared/frozen files', () => {
  const astro = readFileSync(ARENA_ASTRO, 'utf8');
  // The header comment documents what NOT to touch and mentions these by name, so check for an
  // actual import specifier rather than a bare substring (which the comment itself would match).
  assert.ok(!astro.includes("from '../../lib/site.ts'"), 'must not import site.ts');
  assert.ok(!/from\s+['"]@nf\/content['"]/.test(astro), 'must not import @nf/content');
  assert.ok(!/packages\/content\/content\/site\.json/.test(astro));
});

test('source: no other page links to /arena (homepage included)', () => {
  const pagesDir = join(WEB, 'src/pages');
  const hits = [];
  for (const f of files(pagesDir, '.astro')) {
    if (f === ARENA_ASTRO) continue;
    if (read(f).includes('/arena')) hits.push(f);
  }
  assert.deepEqual(hits, [], `unexpected /arena reference(s): ${hits.join(', ')}`);
});

test('source: dataset.sha256 in the shipped asset matches the pinned hash in tools/playground/nf_playground/dataset.py (EXC-150-1 condition 5c: pinned by sha256)', () => {
  const asset = JSON.parse(read(join(WEB, 'src/assets/playground/mc-rtt-playground.json')));
  const py = read(join(REPO, 'tools/playground/nf_playground/dataset.py'));
  const m = /SHA256\s*=\s*"([0-9a-f]{64})"/.exec(py);
  assert.ok(m, 'could not find the pinned SHA256 constant in dataset.py');
  assert.equal(
    asset.dataset.sha256,
    m[1],
    'the asset and the pipeline disagree on the source file hash',
  );
});

test("source: /arena carries visible CC-BY attribution, licence link, DOI, a changes-made statement and no-endorsement line (EXC-150-1 condition 5a/b/d, matching 308b779's pattern)", () => {
  const astro = readFileSync(ARENA_ASTRO, 'utf8');
  assert.match(astro, /doiUrl/);
  assert.match(astro, /licenceUrl/);
  assert.match(astro, /Derived from .* changes were made/);
  assert.match(
    astro,
    /do not endorse \{brand\.name\}/,
    'brand name must come from brand.json, never typed by hand',
  );
  assert.match(astro, /research and demonstration only/);
  assert.ok(
    !/\bmedical\b.*\b(device|use|diagnos)/i.test(astro.replace(/not a medical device/gi, '')),
  );
});

test('source: the shared nav does not link to /arena', () => {
  const nav = read(join(REPO, 'packages/ui/src/components/Nav.astro'));
  assert.ok(!nav.toLowerCase().includes('arena'));
});

test('source: sitemap.xml.ts (site.ts, web-seo-owned) does not list /arena while pkg/ is absent', () => {
  // We don't own site.ts, so we can't make its sitemap conditional on pkg/ ourselves -- this
  // just confirms today's reality (arena isn't in sitemapRoutes() at all yet) rather than
  // silently assuming it. Once a CI-built pkg/ ships, adding /arena to the sitemap is a
  // follow-up for whoever owns site.ts, not this file.
  const siteTs = read(join(WEB, 'src/lib/site.ts'));
  assert.ok(!siteTs.includes("'/arena/'"), 'site.ts must not list /arena in sitemapRoutes() yet');
});

test('source: arena.ts never touches Storage, cookies, or a cross-origin URL (lead ruling: in-memory leaderboard only)', () => {
  const ts = readFileSync(ARENA_TS, 'utf8');
  // Comments are allowed to mention these APIs by name (explaining why they're NOT used);
  // check for actual property access, not the bare word.
  assert.ok(
    !/\.(localStorage|sessionStorage|indexedDB)\b/.test(ts),
    'no persistent client storage',
  );
  assert.ok(!/document\.cookie/.test(ts), 'no cookies');
  assert.ok(!/https?:\/\//.test(ts), 'no cross-origin URLs in the client script');
});

test('source: the neurons slider gets a dynamic aria-valuetext (web-a11y finding 1, mirrors playground.ts)', () => {
  const astro = readFileSync(ARENA_ASTRO, 'utf8');
  assert.match(astro, /data-units-unit="units"/, 'root needs the unit word for arena.ts to read');
  assert.match(
    astro,
    /aria-valuetext=\{`\$\{model\.neuronCounts\[lastCount\]\} units`\}/,
    'initial value, server-rendered',
  );
  const ts = readFileSync(ARENA_TS, 'utf8');
  assert.match(
    ts,
    /this\.ui\.units\.setAttribute\('aria-valuetext',/,
    'expected the units range to update its own accessible value on input, not just the visible <output>',
  );
});

test('source: only the hidden status line is aria-live, not the results card (web-a11y finding 2)', () => {
  const astro = readFileSync(ARENA_ASTRO, 'utf8');
  assert.match(
    astro,
    /data-arena-live[^>]*aria-live="polite"|aria-live="polite"[^>]*data-arena-live/,
  );
  assert.ok(
    !/data-arena-card[^>]*aria-live|aria-live[^>]*data-arena-card/.test(astro),
    'the visible results card must not also be aria-live (double-announcement)',
  );
});

for (const theme of THEMES) {
  test(`dist (${theme}): /arena/ always renders the disclaimer and CTA`, () => {
    const dist = requireDist(theme);
    const html = read(join(dist, 'arena/index.html'));
    const text = visibleText(html);
    assert.match(text, /Decoder Arena/);
    assert.match(text, /not a medical device/i);
    assert.match(text, /no data leaves your device/i);
    assert.match(text, /Evaluate your own decoder privately/);
    assert.match(
      text,
      /Derived from MC_RTT.*changes were made/,
      'EXC-150-1 condition 5b/d attribution must render in every state',
    );
    assert.ok(
      text.includes(`do not endorse ${brand.name}`),
      'brand name (from brand.json) should be rendered, not the literal placeholder',
    );
    assert.match(text, /CC-BY-4\.0/);
    const links = attrs(html, 'a', 'href').map((a) => a.value);
    assert.ok(
      links.includes('https://creativecommons.org/licenses/by/4.0/'),
      'licence link missing',
    );
    assert.ok(
      links.some((h) => h.includes('doi.org/10.48324/dandi.000129')),
      'DOI link missing',
    );
  });

  test(`dist (${theme}): homepage does not reference /arena`, () => {
    const dist = requireDist(theme);
    const home = read(join(dist, 'index.html'));
    assert.ok(
      !home.includes('/arena'),
      'homepage must not link to /arena (never touch the homepage)',
    );
  });

  test(`dist (${theme}): /arena only built the one intended route`, () => {
    const dist = requireDist(theme);
    const built = files(join(dist, 'arena'), '.html');
    assert.deepEqual(built, [join(dist, 'arena', 'index.html')]);
  });

  if (!wasmAvailable) {
    test(`dist (${theme}): pkg/ absent -> plain "unavailable" state, zero wasm footprint`, () => {
      const dist = requireDist(theme);
      const html = read(join(dist, 'arena/index.html'));
      const text = visibleText(html);
      assert.match(text, /Decoder loading unavailable/);
      assert.ok(
        !/Run evaluation/.test(text),
        'interactive controls must not render when unavailable',
      );
      assert.ok(!/data-arena[^-]/.test(html), 'no interactive-panel markup when unavailable');
      assert.ok(!html.includes('arena_core'), 'no reference to the wasm bundle when unavailable');
      assert.equal(files(dist, '.wasm').length, 0, 'no .wasm anywhere in dist when unavailable');
      for (const s of attrs(html, 'script', 'src')) {
        const chunk = join(dist, s.value.replace(/^\//, ''));
        if (existsSync(chunk)) assert.ok(!read(chunk).includes('arena_core'));
      }
    });

    test(`dist (${theme}): pkg/ absent -> /arena is noindex and out of the sitemap`, () => {
      const dist = requireDist(theme);
      const html = read(join(dist, 'arena/index.html'));
      assert.match(html, /<meta\s+name="robots"\s+content="noindex,nofollow"\s*\/?>/);
      const sitemapPath = join(dist, 'sitemap.xml');
      if (existsSync(sitemapPath)) assert.ok(!read(sitemapPath).includes('/arena'));
    });
  } else {
    test(`dist (${theme}): pkg/ present -> full interactive controls, evaluator as a hashed Vite asset`, () => {
      const dist = requireDist(theme);
      const html = read(join(dist, 'arena/index.html'));
      const text = visibleText(html);
      assert.match(text, /Run evaluation/);
      assert.match(text, /Your runs \(this browser only\)/);
      const scripts = attrs(html, 'script', 'src').filter((s) => s.value);
      assert.ok(scripts.length > 0, 'expected at least one external <script src>');
      for (const m of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)) {
        if (!/\ssrc\s*=/i.test(m[1]))
          assert.equal(m[2].trim(), '', 'unexpected inline script body');
      }
      assert.equal(files(dist, '.wasm').length, 1, 'expected exactly one .wasm in dist');
      assert.ok(
        !/<meta\s+name="robots"\s+content="noindex/.test(html),
        'pkg/ present -> the page should be indexable again',
      );
    });
  }
}
