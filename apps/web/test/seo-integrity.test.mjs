// Permanent SEO integrity test (web-seo T4, formalises docs/web/seo-audit-2.md): every built page,
// both themes, has a unique title and meta description, a canonical that is absolute, on the
// canonical (clinical) host, and matches the page's own path; every hreflang alternate resolves to a
// real page in the same theme's dist; every sitemap.xml URL exists in dist; and noindex pages never
// appear in the sitemap.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { join } from 'node:path';
import { canonicalOrigin, files, read, requireDist, urlPath } from './_dist.mjs';

const THEMES = ['clinical', 'cosmos'];

/** `<meta name=... | property=...>` tags, attribute order independent. */
function metaTags(html) {
  const out = [];
  for (const m of html.matchAll(/<meta\b[^>]*>/gi)) {
    const tag = m[0];
    const get = (attr) => tag.match(new RegExp(`\\s${attr}\\s*=\\s*("([^"]*)"|'([^']*)')`, 'i'));
    const name = get('name');
    const property = get('property');
    const content = get('content');
    out.push({
      name: name ? (name[2] ?? name[3]) : undefined,
      property: property ? (property[2] ?? property[3]) : undefined,
      content: content ? (content[2] ?? content[3]) : '',
    });
  }
  return out;
}
const metaValue = (html, key) =>
  metaTags(html).find((m) => m.name === key || m.property === key)?.content;

/** `<link rel=... href=... hreflang=...>` tags, optionally filtered by `rel`. */
function linkTags(html, relFilter) {
  const out = [];
  for (const m of html.matchAll(/<link\b[^>]*>/gi)) {
    const tag = m[0];
    const get = (attr) => tag.match(new RegExp(`\\s${attr}\\s*=\\s*("([^"]*)"|'([^']*)')`, 'i'));
    const rel = get('rel');
    if (!rel) continue;
    const relValue = rel[2] ?? rel[3];
    if (relFilter && relValue !== relFilter) continue;
    const href = get('href');
    const hreflang = get('hreflang');
    out.push({
      rel: relValue,
      href: href ? (href[2] ?? href[3]) : undefined,
      hreflang: hreflang ? (hreflang[2] ?? hreflang[3]) : undefined,
    });
  }
  return out;
}

/** "/x" -> "/x/"; "/" stays "/". */
const withSlash = (p) => (p === '/' ? '/' : p.endsWith('/') ? p : `${p}/`);

/** Astro's 404.html has no trailing-slash directory form; its canonical/sitemap use "/404/". */
const canonicalPath = (p) => p.replace(/^\/404\.html$/, '/404/');

for (const theme of THEMES) {
  test(`${theme}: every page has a unique, non-empty <title>`, () => {
    const dist = requireDist(theme);
    const byTitle = new Map();
    for (const f of files(dist, '.html')) {
      const p = urlPath(dist, f);
      const title = read(f).match(/<title>([^<]*)<\/title>/)?.[1];
      assert.ok(title && title.trim(), `${p}: missing <title>`);
      byTitle.set(title, [...(byTitle.get(title) ?? []), p]);
    }
    const dups = [...byTitle].filter(([, paths]) => paths.length > 1);
    assert.deepEqual(dups, [], `${theme}: duplicate <title>: ${JSON.stringify(dups)}`);
  });

  test(`${theme}: every page has a unique, non-empty meta description`, () => {
    const dist = requireDist(theme);
    const byDesc = new Map();
    for (const f of files(dist, '.html')) {
      const p = urlPath(dist, f);
      const desc = metaValue(read(f), 'description');
      assert.ok(desc && desc.trim(), `${p}: missing meta description`);
      byDesc.set(desc, [...(byDesc.get(desc) ?? []), p]);
    }
    const dups = [...byDesc].filter(([, paths]) => paths.length > 1);
    assert.deepEqual(dups, [], `${theme}: duplicate meta description: ${JSON.stringify(dups)}`);
  });

  test(`${theme}: every canonical is absolute, on the canonical host, and matches its own page`, () => {
    const dist = requireDist(theme);
    for (const f of files(dist, '.html')) {
      const p = urlPath(dist, f);
      const html = read(f);
      const canon = linkTags(html, 'canonical');
      assert.equal(
        canon.length,
        1,
        `${p}: expected exactly one rel=canonical, found ${canon.length}`,
      );
      const href = canon[0].href;
      assert.ok(href, `${p}: canonical has no href`);
      let u;
      assert.doesNotThrow(() => {
        u = new URL(href);
      }, `${p}: canonical href is not an absolute URL: ${href}`);
      assert.equal(
        `${u.protocol}//${u.host}`,
        canonicalOrigin,
        `${p}: canonical must be on the clinical host, got ${u.origin}`,
      );
      assert.equal(
        withSlash(u.pathname),
        withSlash(canonicalPath(p)),
        `${p}: canonical path does not match the page's own path (got ${u.pathname})`,
      );
    }
  });

  test(`${theme}: every hreflang alternate resolves to a real page in the same theme's dist`, () => {
    const dist = requireDist(theme);
    const known = new Set(
      files(dist, '.html').map((f) => withSlash(canonicalPath(urlPath(dist, f)))),
    );
    for (const f of files(dist, '.html')) {
      const p = urlPath(dist, f);
      const html = read(f);
      for (const a of linkTags(html, 'alternate').filter((a) => a.hreflang)) {
        let u;
        assert.doesNotThrow(() => {
          u = new URL(a.href);
        }, `${p}: alternate hreflang=${a.hreflang} href is not absolute: ${a.href}`);
        assert.ok(
          known.has(withSlash(u.pathname)),
          `${p}: hreflang=${a.hreflang} -> ${u.pathname} does not exist in the ${theme} dist`,
        );
      }
    }
  });

  test(`${theme}: every sitemap.xml URL exists in dist, and noindex pages are absent from it`, () => {
    const dist = requireDist(theme);
    const known = new Set(
      files(dist, '.html').map((f) => withSlash(canonicalPath(urlPath(dist, f)))),
    );
    const sitemap = read(join(dist, 'sitemap.xml'));
    const locs = [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]);
    assert.ok(locs.length > 0, `${theme}: sitemap.xml has no <loc> entries`);
    const inSitemap = new Set();
    for (const loc of locs) {
      const u = new URL(loc);
      assert.ok(known.has(withSlash(u.pathname)), `${theme}: sitemap URL not in dist: ${loc}`);
      inSitemap.add(withSlash(u.pathname));
    }
    for (const f of files(dist, '.html')) {
      const p = withSlash(canonicalPath(urlPath(dist, f)));
      const isNoindex = /<meta\s+name=["']robots["']\s+content=["']noindex/i.test(read(f));
      if (isNoindex)
        assert.ok(!inSitemap.has(p), `${theme}: ${p} is noindex but listed in sitemap.xml`);
    }
  });
}
