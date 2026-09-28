// Two-build tests (BUILD-GUIDE 1.6, 1.8): data-theme, canonical, robots, sitemap, text parity,
// slot budget, theme contract, no third-party requests, law tracker and early-access rules.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readdirSync } from 'node:fs';
import { join, relative } from 'node:path';
import { spawnSync } from 'node:child_process';
import { robotsTxt } from '../indexing.mjs';
import {
  DIST,
  THEMES_DIR,
  attrs,
  canonicalOrigin,
  files,
  read,
  requireDist,
  urlPath,
  visibleText,
  walk,
} from './_dist.mjs';

const THEMES = ['clinical', 'cosmos'];

test('<html data-theme> is set statically on every page', () => {
  for (const t of THEMES) {
    const dist = requireDist(t);
    for (const f of files(dist, '.html'))
      assert.match(read(f), new RegExp(`<html[^>]*\\sdata-theme="${t}"`), relative(dist, f));
  }
});

test('every cosmos page has one rel=canonical to the same path on the clinical host', () => {
  const dist = requireDist('cosmos');
  const pages = files(dist, '.html');
  assert.ok(pages.length >= 10);
  for (const f of pages) {
    const tags = attrs(read(f), 'link', 'href').filter((a) => /rel=["']?canonical/i.test(a.tag));
    assert.equal(tags.length, 1, `${relative(dist, f)}: expected exactly one canonical`);
    const path = urlPath(dist, f).replace(/^\/404\.html$/, '/404/');
    assert.equal(tags[0].value, new URL(path, canonicalOrigin).href, relative(dist, f));
  }
});

test('robots.txt per build; clinical lists the sitemap; gallery is noindex and not in the sitemap', () => {
  // The built dist is a preview (Disallow: /, no sitemap; test/indexing.test.mjs); the per-theme
  // launch/public text is checked through the same generator the robots.txt route uses.
  const stage = 'launch';
  const c = robotsTxt({ stage, theme: 'clinical', canonicalOrigin });
  const k = robotsTxt({ stage, theme: 'cosmos', canonicalOrigin });
  const built = JSON.parse(read(join(requireDist('clinical'), '_headers.json'))).stage;
  if (built !== 'preview') assert.equal(read(join(requireDist('clinical'), 'robots.txt')), c);
  assert.match(c, /^User-agent: \*/m);
  assert.match(
    c,
    new RegExp(`^Sitemap: ${canonicalOrigin.replace(/\./g, '\\.')}/sitemap\\.xml$`, 'm'),
  );
  assert.doesNotMatch(k, /^Sitemap:/m);
  for (const t of THEMES) {
    const dist = DIST[t];
    assert.match(read(join(dist, 'gallery/index.html')), /<meta name="robots" content="noindex/);
    const sm = read(join(dist, 'sitemap.xml'));
    assert.doesNotMatch(sm, /gallery|404/);
    assert.match(sm, /\/research\/somatosensory-closed-loop\//);
  }
});

test('both builds contain the same pages and identical visible text', () => {
  const c = requireDist('clinical');
  const k = requireDist('cosmos');
  const pc = files(c, '.html')
    .map((f) => relative(c, f))
    .sort();
  const pk = files(k, '.html')
    .map((f) => relative(k, f))
    .sort();
  assert.deepEqual(pk, pc);
  const diffs = [];
  for (const rel of pc) {
    const a = visibleText(read(join(c, rel)));
    const b = visibleText(read(join(k, rel)));
    if (a !== b) {
      let i = 0;
      while (a[i] === b[i]) i++;
      diffs.push(
        `${rel} @${i}: clinical "${a.slice(i, i + 60)}" vs cosmos "${b.slice(i, i + 60)}"`,
      );
    }
  }
  assert.deepEqual(diffs, []);
});

test('slot budget: at most 4 slot files per theme', () => {
  for (const t of THEMES) {
    const dir = join(THEMES_DIR, t, 'slots');
    const n = readdirSync(dir).filter((f) => !f.startsWith('.')).length;
    assert.ok(n <= 4, `${t}: ${n} slot files`);
  }
});

test("designer's theme contract test passes (when present)", (t) => {
  const testDir = join(THEMES_DIR, 'test');
  const tests = existsSync(testDir)
    ? readdirSync(testDir).filter((f) => /\.test\.(mjs|js|ts)$/.test(f))
    : [];
  if (!tests.length) return t.skip('packages/themes/test has no tests yet (designer step 1.1)');
  const r = spawnSync(process.execPath, ['--test', ...tests.map((f) => join(testDir, f))], {
    encoding: 'utf8',
  });
  assert.equal(r.status, 0, r.stdout.slice(-3000) + r.stderr.slice(-2000));
});

const BANNED_HOSTS =
  /\b(?:cdn\.jsdelivr\.net|jsdelivr|googleapis\.com|gstatic\.com|cdnjs\.cloudflare\.com|unpkg\.com|googletagmanager|google-analytics|typekit|use\.fontawesome|cloudflareinsights|plausible\.io|hotjar|segment\.(?:io|com)|facebook\.net|doubleclick)\b/i;

test('no third-party hosts anywhere in dist, and no external resource loads', () => {
  const problems = [];
  for (const t of THEMES) {
    const dist = requireDist(t);
    for (const f of walk(dist)) {
      if (!/\.(html|css|js|mjs|xml|txt|svg|json|webmanifest)$/.test(f)) continue;
      const s = read(f);
      if (BANNED_HOSTS.test(s))
        problems.push(`${t}/${relative(dist, f)}: ${s.match(BANNED_HOSTS)[0]}`);
      if (f.endsWith('.html')) {
        const loads = [
          ...attrs(s, 'script', 'src'),
          ...attrs(s, 'img', 'src'),
          ...attrs(s, 'iframe', 'src'),
          ...attrs(s, 'source', 'src'),
          // canonical + hreflang alternates are metadata, not fetched resources
          ...attrs(s, 'link', 'href').filter(
            (a) => !/rel=["']?(canonical|alternate)\b/i.test(a.tag),
          ),
        ];
        for (const a of loads)
          if (/^(https?:)?\/\//i.test(a.value))
            problems.push(`${t}/${relative(dist, f)}: loads ${a.value}`);
      }
      if (f.endsWith('.css'))
        for (const m of s.matchAll(/url\(\s*["']?((?:https?:)?\/\/[^"')]+)/gi))
          problems.push(`${t}/${relative(dist, f)}: css url ${m[1]}`);
      if (/\.m?js$/.test(f))
        for (const m of s.matchAll(/["'`](https?:\/\/[^"'`\s]+)/g))
          if (!/^https?:\/\/www\.w3\.org\//.test(m[1]))
            problems.push(`${t}/${relative(dist, f)}: js url ${m[1]}`);
    }
  }
  assert.deepEqual(problems, []);
});

test('fonts are self-hosted (no @import of remote CSS, font files served from the build)', () => {
  for (const t of THEMES) {
    const dist = requireDist(t);
    for (const f of files(dist, '.css'))
      assert.doesNotMatch(read(f), /@import\s+(url\()?["']?https?:/i, relative(dist, f));
  }
});

test('law tracker: not-legal-advice banner, every row cites a source, unverified rows marked', () => {
  for (const t of THEMES) {
    const html = read(join(requireDist(t), 'law-tracker/index.html'));
    assert.match(html, /id="not-legal-advice"/);
    const rows = [
      ...html.matchAll(/<li class="row[^"]*"[^>]*data-verified="(true|false)"[\s\S]*?<\/li>/g),
    ];
    assert.ok(rows.length > 0);
    for (const r of rows) {
      assert.match(r[0], /class="src"/);
      if (r[1] === 'false') assert.match(r[0], /is-unverified/);
    }
    assert.ok(
      rows.some((r) => r[1] === 'false'),
      'expected at least one unverified row to be shown as unverified',
    );
  }
});

test('early-access form is rendered disabled and posts nowhere', () => {
  for (const t of THEMES) {
    const html = read(join(requireDist(t), 'pricing/index.html'));
    const form = html.match(/<form\b[\s\S]*?<\/form>/)?.[0] ?? '';
    assert.match(form, /<fieldset[^>]*\sdisabled/);
    assert.doesNotMatch(form, /\saction=/);
    assert.match(html, /id="early-access"/);
  }
});

test('whitepaper: In preparation status, IRB/FDA banner, figures preliminary, never "verified"', () => {
  for (const t of THEMES) {
    const html = read(join(requireDist(t), 'research/somatosensory-closed-loop/index.html'));
    assert.match(html, /id="irb-fda"/);
    assert.match(html, /pill--in-preparation/);
    const figs = html.match(/data-nf-fig/g) ?? [];
    assert.ok(figs.length >= 1, 'expected figure islands');
    assert.equal(
      (html.match(/<svg class="nf-plot-svg[^>]*role="img"[^>]*aria-label="[^"]+"/g) ?? []).length,
      figs.length,
      'every figure SVG has role=img + aria-label',
    );
    assert.doesNotMatch(visibleText(html), /\bverified\b/i);
  }
});
