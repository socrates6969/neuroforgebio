// Metadata audit of the built dist (web-seo): every page, both themes, has a unique title and meta
// description, a canonical URL matching its own route, noindex + sitemap exclusion on the routes that
// need it, and (where a page carries JSON-LD) a parseable schema.org block. Follows the pattern in
// apps/web/test/seo-integrity.test.mjs; this file is scoped to web-queen's post-report-23 checklist.
//
// The noindex/sitemap checks are invariants, not a hardcoded page list (web-queen, after an earlier
// draft of this file got /arena and /no/security wrong): every sitemap URL is non-noindex and exists
// in dist; every noindex page is absent from the sitemap; /no/<inner page> is noindex iff its
// translation isn't yet reviewed (@nf/content Page.reviewed - read from the raw content JSON, not
// imported, matching apps/web/test/i18n.test.mjs: apps/web's test runner has no TS type-stripping
// flag); every legal page (either locale) is noindex iff draft:true; /arena is noindex iff the dist
// ships no .wasm (apps/web/test/arena-wasm.test.mjs's own convention: check the whole dist for any
// .wasm, not just the configured assets dir, so a build-output move can't silently go unnoticed).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { join } from 'node:path';
import { REPO, canonicalOrigin, files, read, requireDist, urlPath } from './_dist.mjs';
import { checkDist } from '../scripts/linkcheck.mjs';

const THEMES = ['clinical', 'cosmos'];
const INNER_PAGE_KEYS = ['platform', 'governance', 'sdks', 'pricing'];
const LEGAL_KEYS = ['privacy', 'terms', 'cookies', 'company'];

const contentJson = (rel) => JSON.parse(read(join(REPO, 'packages/content/content', rel)));
const isReviewedNo = (key) => contentJson(`pages/${key}.no.json`).reviewed === true;
const isDraftLegal = (key, locale) => contentJson(`legal/${key}.${locale}.json`).draft === true;

/** `<meta name=... | property=...>` tags, attribute order independent. */
function metaTags(html) {
  const out = [];
  for (const m of html.matchAll(/<meta\b[^>]*>/gi)) {
    const tag = m[0];
    const get = (attr) => tag.match(new RegExp(`\\s${attr}\\s*=\\s*("([^"]*)"|'([^']*)')`, 'i'));
    const name = get('name');
    const content = get('content');
    out.push({
      name: name ? (name[2] ?? name[3]) : undefined,
      content: content ? (content[2] ?? content[3]) : '',
    });
  }
  return out;
}
const metaValue = (html, key) => metaTags(html).find((m) => m.name === key)?.content;
const isNoindex = (html) => /^noindex\b/i.test(metaValue(html, 'robots') ?? '');

/** `<link rel=...>` tags, optionally filtered by `rel`. */
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
    out.push({ rel: relValue, href: href ? (href[2] ?? href[3]) : undefined });
  }
  return out;
}

function jsonLdBlocks(html) {
  return [
    ...html.matchAll(
      /<script[^>]*\stype=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script\s*>/gi,
    ),
  ].map((m) => m[1]);
}

const withSlash = (p) => (p === '/' ? '/' : p.endsWith('/') ? p : `${p}/`);
/** Astro's 404.html has no trailing-slash directory form; canonical/sitemap use "/404/". */
const canonicalPath = (p) => p.replace(/^\/404\.html$/, '/404/');

for (const theme of THEMES) {
  test(`${theme}: every page has a unique title and meta description`, () => {
    const dist = requireDist(theme);
    const byTitle = new Map();
    const byDesc = new Map();
    for (const f of files(dist, '.html')) {
      const p = urlPath(dist, f);
      const html = read(f);
      const title = html.match(/<title>([^<]*)<\/title>/)?.[1];
      assert.ok(title && title.trim(), `${p}: missing <title>`);
      byTitle.set(title, [...(byTitle.get(title) ?? []), p]);
      const desc = metaValue(html, 'description');
      assert.ok(desc && desc.trim(), `${p}: missing meta description`);
      byDesc.set(desc, [...(byDesc.get(desc) ?? []), p]);
    }
    const dupTitles = [...byTitle].filter(([, paths]) => paths.length > 1);
    assert.deepEqual(dupTitles, [], `${theme}: duplicate <title>: ${JSON.stringify(dupTitles)}`);
    const dupDescs = [...byDesc].filter(([, paths]) => paths.length > 1);
    assert.deepEqual(
      dupDescs,
      [],
      `${theme}: duplicate meta description: ${JSON.stringify(dupDescs)}`,
    );
  });

  test(`${theme}: every canonical URL matches the page's own route, on the clinical host`, () => {
    const dist = requireDist(theme);
    for (const f of files(dist, '.html')) {
      const p = urlPath(dist, f);
      const html = read(f);
      const canon = linkTags(html, 'canonical');
      assert.equal(canon.length, 1, `${p}: expected exactly one rel=canonical`);
      const href = canon[0].href;
      let u;
      assert.doesNotThrow(() => {
        u = new URL(href);
      }, `${p}: canonical href is not absolute: ${href}`);
      assert.equal(
        `${u.protocol}//${u.host}`,
        canonicalOrigin,
        `${p}: canonical must be on the clinical host`,
      );
      assert.equal(
        withSlash(u.pathname),
        withSlash(canonicalPath(p)),
        `${p}: canonical path does not match its own route`,
      );
    }
  });

  test(`${theme}: every JSON-LD block on every page parses as schema.org`, () => {
    const dist = requireDist(theme);
    for (const f of files(dist, '.html')) {
      const p = urlPath(dist, f);
      for (const b of jsonLdBlocks(read(f))) {
        let parsed;
        assert.doesNotThrow(
          () => {
            parsed = JSON.parse(b);
          },
          `${p}: JSON-LD block does not parse: ${b.slice(0, 120)}`,
        );
        for (const node of Array.isArray(parsed) ? parsed : [parsed]) {
          assert.equal(
            node['@context'],
            'https://schema.org',
            `${p}: JSON-LD node missing @context`,
          );
          assert.ok(
            typeof node['@type'] === 'string' && node['@type'],
            `${p}: JSON-LD node missing @type`,
          );
        }
      }
    }
  });

  test(`${theme}: sitemap.xml and robots-noindex are consistent (no noindex page in the sitemap, no sitemap URL is noindex)`, () => {
    const dist = requireDist(theme);
    const noindexByPath = new Map(
      files(dist, '.html').map((f) => [
        withSlash(canonicalPath(urlPath(dist, f))),
        isNoindex(read(f)),
      ]),
    );
    const sitemap = read(join(dist, 'sitemap.xml'));
    const locs = [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]);
    assert.ok(locs.length > 0, `${theme}: sitemap.xml has no <loc> entries`);
    const sitemapPaths = new Set();
    for (const loc of locs) {
      const p = withSlash(new URL(loc).pathname);
      assert.ok(noindexByPath.has(p), `${theme}: sitemap URL not found in dist: ${loc}`);
      assert.equal(noindexByPath.get(p), false, `${theme}: sitemap URL is noindex: ${loc}`);
      sitemapPaths.add(p);
    }
    for (const [p, noindex] of noindexByPath)
      if (noindex)
        assert.ok(!sitemapPaths.has(p), `${theme}: noindex page is in the sitemap: ${p}`);
  });

  test(`${theme}: /no/<inner page> is noindex iff its translation isn't reviewed yet`, () => {
    const dist = requireDist(theme);
    for (const key of INNER_PAGE_KEYS) {
      const f = files(dist, '.html').find((x) => urlPath(dist, x) === `/no/${key}/`);
      assert.ok(f, `/no/${key}/: page not found in dist`);
      const reviewed = isReviewedNo(key);
      assert.equal(
        isNoindex(read(f)),
        !reviewed,
        `/no/${key}/: noindex must be ${!reviewed} (Page.reviewed=${reviewed})`,
      );
    }
  });

  test(`${theme}: every legal page (either locale) is noindex iff draft:true`, () => {
    const dist = requireDist(theme);
    for (const locale of ['en', 'no']) {
      const prefix = locale === 'en' ? '/legal' : '/no/legal';
      for (const key of LEGAL_KEYS) {
        const f = files(dist, '.html').find((x) => urlPath(dist, x) === `${prefix}/${key}/`);
        assert.ok(f, `${prefix}/${key}/: page not found in dist`);
        const draft = isDraftLegal(key, locale);
        assert.equal(
          isNoindex(read(f)),
          draft,
          `${prefix}/${key}/: noindex must be ${draft} (draft=${draft})`,
        );
      }
    }
  });

  test(`${theme}: /arena is noindex iff the dist ships no .wasm`, () => {
    const dist = requireDist(theme);
    const f = files(dist, '.html').find((x) => urlPath(dist, x) === '/arena/');
    assert.ok(f, '/arena/: page not found in dist');
    const hasWasm = files(dist, '.wasm').length > 0;
    assert.equal(
      isNoindex(read(f)),
      !hasWasm,
      `/arena/: noindex must be ${!hasWasm} (dist has ${files(dist, '.wasm').length} .wasm file(s))`,
    );
  });

  // Every internal <a>/<link>/<script>/<img>/<source>/<iframe> href/src (both themes, every locale
  // - checkDist walks the whole dist tree, /no/ included) resolves to a built page, a fragment id on
  // that page, or another built asset. This is already apps/web/scripts/linkcheck.mjs, already run by
  // apps/web/test/links.test.mjs on every handoff - reusing it here (not reimplementing it) so this
  // file's own report covers it too, per web-queen's ask, without a second, divergent implementation.
  test(`${theme}: every internal link/asset reference resolves (apps/web/scripts/linkcheck.mjs)`, () => {
    const { checked, broken } = checkDist(requireDist(theme));
    assert.ok(checked > 50, `${theme}: only ${checked} internal references checked`);
    assert.deepEqual(broken, [], `${theme}: broken internal references:\n${broken.join('\n')}`);
  });

  test(`${theme}: every hreflang alternate is reciprocal (A -> B implies B -> A with A's own locale)`, () => {
    const dist = requireDist(theme);
    // path -> [{hreflang, href}], excluding x-default (not a locale to reciprocate from/to).
    const altsByPath = new Map();
    for (const f of files(dist, '.html')) {
      const p = withSlash(canonicalPath(urlPath(dist, f)));
      const alts = linkTags(read(f), 'alternate').filter(
        (a) => a.hreflang && a.hreflang !== 'x-default',
      );
      if (alts.length) altsByPath.set(p, alts);
    }
    const resolvedPath = (href) => {
      try {
        return withSlash(new URL(href).pathname);
      } catch {
        return null;
      }
    };
    const problems = [];
    for (const [p, alts] of altsByPath) {
      // The page's own locale, as it identifies itself: its self-referencing alternate's hreflang.
      const selfAlt = alts.find((a) => resolvedPath(a.href) === p);
      if (!selfAlt) {
        problems.push(`${p}: has hreflang alternates but none is self-referencing`);
        continue;
      }
      for (const a of alts) {
        const targetPath = resolvedPath(a.href);
        if (!targetPath || targetPath === p) continue;
        const targetAlts = altsByPath.get(targetPath);
        if (!targetAlts) {
          problems.push(
            `${p} -> ${targetPath} (hreflang=${a.hreflang}): target has no hreflang alternates at all`,
          );
          continue;
        }
        const backMatch = targetAlts.find(
          (b) => resolvedPath(b.href) === p && b.hreflang === selfAlt.hreflang,
        );
        if (!backMatch)
          problems.push(
            `${p} (hreflang=${selfAlt.hreflang}) -> ${targetPath} (hreflang=${a.hreflang}), but ${targetPath} has no matching hreflang=${selfAlt.hreflang} alternate back`,
          );
      }
    }
    assert.deepEqual(
      problems,
      [],
      `${theme}: non-reciprocal hreflang pairs:\n${problems.join('\n')}`,
    );
  });
}
