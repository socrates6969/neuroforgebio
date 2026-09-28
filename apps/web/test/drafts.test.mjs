// Draft-page guard (web-queen T2). Draft content (web-papers /papers/draft/*, web-investor /investors) must:
//   1. carry <meta name="robots" content="noindex..."> on every built page of the route;
//   2. be absent from sitemap.xml;
//   3. not be linked from the home page (/) or from any <nav> block on any page.
// It passes vacuously while no such route exists and bites as soon as one is built.
//
// Scope note: the legal drafts (/legal/*, draft: true in packages/content) are deliberately linked from the
// footer on every page (nfb-legal: "Privacy · Terms · Cookies · Company information") and are noindex through
// Base's `noindex` prop; they are covered by i18n.test.mjs / security.test.mjs, not by this guard.
//
// Stage note: a preview build (SITE_STAGE=preview, the default) marks EVERY page noindex (APP-L8), so check 1
// is only discriminating on launch/public builds. Check 4 therefore also enforces it at the source: every Astro
// page file of a draft route must pass the `noindex` prop to Base, whatever the build stage.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { files, read, requireDist, urlPath, attrs, WEB } from './_dist.mjs';

const THEMES = ['clinical', 'cosmos'];
/** Draft route families (URL paths, EN and NO). Add a family here when a new draft section appears. */
export const DRAFT_ROUTES = [/^\/(?:no\/)?papers\/draft(?:\/|$)/, /^\/(?:no\/)?investors(?:\/|$)/];
export const isDraftPath = (p) => DRAFT_ROUTES.some((re) => re.test(p));

const ROBOTS_NOINDEX = /<meta\s+name="robots"\s+content="[^"]*\bnoindex\b[^"]*"/i;

/** Normalise an href to a site path (drops origin, query and fragment); null for external links. */
function hrefPath(href, origin) {
  try {
    const u = new URL(href, 'https://site.invalid/');
    if (u.origin !== 'https://site.invalid' && (!origin || u.origin !== origin)) return null;
    return u.pathname.endsWith('/') || u.pathname.includes('.') ? u.pathname : `${u.pathname}/`;
  } catch {
    return null;
  }
}

function draftPages(dist) {
  return files(dist, '.html')
    .map((f) => ({ file: f, path: urlPath(dist, f) }))
    .filter((p) => isDraftPath(p.path));
}

test('draft route matcher (unit)', () => {
  for (const p of [
    '/papers/draft/',
    '/papers/draft/x/',
    '/no/papers/draft/y/',
    '/investors/',
    '/no/investors/a/',
  ])
    assert.ok(isDraftPath(p), p);
  for (const p of [
    '/',
    '/papers/',
    '/papers/final/',
    '/research/',
    '/legal/terms/',
    '/investor-faq/',
  ])
    assert.ok(!isDraftPath(p), p);
});

for (const theme of THEMES) {
  test(`${theme}: draft pages are noindex, not in the sitemap, not linked from / or any nav`, (t) => {
    const dist = requireDist(theme);
    const drafts = draftPages(dist);
    t.diagnostic(`${theme}: ${drafts.length} draft page(s) found`);
    if (!drafts.length) return; // vacuous until web-papers / web-investor drafts land
    const draftSet = new Set(drafts.map((d) => d.path));

    for (const d of drafts)
      assert.match(
        read(d.file),
        ROBOTS_NOINDEX,
        `${d.path}: missing <meta name="robots" content="noindex">`,
      );

    const sitemap = join(dist, 'sitemap.xml');
    if (existsSync(sitemap)) {
      const locs = [...read(sitemap).matchAll(/<loc>([^<]+)<\/loc>/g)].map(
        (m) => hrefPath(m[1], null) ?? new URL(m[1]).pathname,
      );
      for (const loc of locs) assert.ok(!isDraftPath(loc), `sitemap.xml lists draft page ${loc}`);
    }

    const home = read(join(dist, 'index.html'));
    for (const a of attrs(home, 'a', 'href')) {
      const p = hrefPath(a.value, null);
      assert.ok(!p || (!draftSet.has(p) && !isDraftPath(p)), `/ links to draft page ${a.value}`);
    }
    for (const f of files(dist, '.html')) {
      for (const nav of read(f).match(/<nav\b[\s\S]*?<\/nav>/gi) || [])
        for (const a of attrs(nav, 'a', 'href')) {
          const p = hrefPath(a.value, null);
          assert.ok(
            !p || !isDraftPath(p),
            `${urlPath(dist, f)}: <nav> links to draft page ${a.value}`,
          );
        }
    }
  });
}

test('source: every Astro page of a draft route passes noindex to Base (stage-independent)', (t) => {
  const pages = join(WEB, 'src', 'pages');
  const astro = [];
  const walk = (d) => {
    for (const n of readdirSync(d)) {
      const p = join(d, n);
      if (statSync(p).isDirectory()) walk(p);
      else if (p.endsWith('.astro')) astro.push(p);
    }
  };
  walk(pages);
  // Route of a page file: src/pages/papers/draft/[slug].astro -> /papers/draft/[slug]/
  const routeOf = (f) => {
    const rel = relative(pages, f)
      .split(sep)
      .join('/')
      .replace(/\.astro$/, '');
    return `/${rel === 'index' ? '' : rel.replace(/\/?index$/, '') + '/'}`;
  };
  const draftFiles = astro.filter((f) => isDraftPath(routeOf(f)));
  t.diagnostic(`${draftFiles.length} draft page source file(s)`);
  for (const f of draftFiles) {
    const src = read(f);
    assert.match(
      src,
      /<Base\b[^>]*\bnoindex\b(?!\s*=\s*\{\s*false\s*\})/,
      `${relative(WEB, f)}: a draft route must render <Base ... noindex>`,
    );
  }
});
