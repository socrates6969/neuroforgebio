// EN + NO (bokmål) routing, lang, hreflang, language switch; /security (SEC-158), the legal drafts
// and the inner pages (platform/governance/sdks/pricing).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { join, relative } from 'node:path';
import { attrs, canonicalOrigin, files, read, REPO, requireDist, visibleText } from './_dist.mjs';

const THEMES = ['clinical', 'cosmos'];
const BILINGUAL = [
  '/security/',
  '/legal/privacy/',
  '/legal/terms/',
  '/legal/cookies/',
  '/legal/company/',
];
const INNER_PAGE_KEYS = ['platform', 'governance', 'sdks', 'pricing'];
/** Inner pages whose NO translation is reviewed (@nf/content Page.reviewed), read from the raw
 * content JSON rather than imported: apps/web's test runner has no TS type-stripping flag (see
 * route-inventory.test.mjs's header), so @nf/content's publishedInnerPages() isn't importable here. */
function reviewedInnerPages() {
  return INNER_PAGE_KEYS.filter(
    (k) =>
      JSON.parse(read(join(REPO, `packages/content/content/pages/${k}.no.json`))).reviewed === true,
  );
}
// Bilingual: gets hreflang alternates and a language-switch link. An inner page joins this only
// once reviewed; until then it's built (below) but noindex, unlinked, single-language.
const LOCALISED = [...BILINGUAL, ...reviewedInnerPages().map((k) => `/${k}/`)];
// Built: every /no/<x> that exists on disk, reviewed or not (lead ruling 2026-09-27: an inner page
// is always built so the owner can review the real rendered page by URL).
const BUILT_NO_ROUTES = [...BILINGUAL, ...INNER_PAGE_KEYS.map((k) => `/${k}/`)];
const ANCHORS = ['data', 'never', 'software', 'standards', 'testing', 'incidents', 'disclosure'];
const page = (t, p) => read(join(requireDist(t), p, 'index.html'));
const urlOf = (dist, f) =>
  '/' +
  relative(dist, f)
    .replace(/\\/g, '/')
    .replace(/index\.html$/, '');

test('Norwegian routes exist for /security, the four legal pages, and every inner page', () => {
  for (const t of THEMES) {
    const dist = requireDist(t);
    const no = files(join(dist, 'no'), '.html')
      .map((f) => urlOf(dist, f))
      .sort();
    assert.deepEqual(no, BUILT_NO_ROUTES.map((p) => `/no${p}`).sort());
  }
});

test('unreviewed /no/<inner page>: noindex, out of the sitemap, linked from nowhere', () => {
  for (const t of THEMES) {
    const dist = requireDist(t);
    const sm = read(join(dist, 'sitemap.xml'));
    const reviewed = new Set(reviewedInnerPages());
    for (const k of INNER_PAGE_KEYS) {
      if (reviewed.has(k)) continue; // reviewed pages are covered by the hreflang/switch tests below
      const html = page(t, `no/${k}`);
      assert.match(html, /<meta name="robots" content="noindex,nofollow"/, `no/${k}: noindex`);
      assert.doesNotMatch(sm, new RegExp(`/no/${k}/`), `no/${k} must not be in the sitemap`);
      assert.doesNotMatch(
        read(join(dist, `${k}/index.html`)),
        /hreflang="nb"/,
        `${k}: no NO alternate`,
      );
      for (const f of files(dist, '.html')) {
        if (urlOf(dist, f) === `/no/${k}/`) continue;
        assert.doesNotMatch(
          read(f),
          new RegExp(`href="/no/${k}/"`),
          `${urlOf(dist, f)} must not link to unreviewed /no/${k}/`,
        );
      }
    }
  }
});

test('hreflang en / nb / x-default on pages in both languages, none elsewhere', () => {
  for (const t of THEMES) {
    const dist = requireDist(t);
    for (const f of files(dist, '.html')) {
      const url = urlOf(dist, f);
      const alts = attrs(read(f), 'link', 'href').filter((a) => /rel="alternate"/.test(a.tag));
      const base = url.replace(/^\/no\//, '/');
      if (!LOCALISED.includes(base)) {
        assert.deepEqual(alts, [], `${url}: no alternates on single-language pages`);
        continue;
      }
      const map = Object.fromEntries(
        alts.map((a) => [a.tag.match(/hreflang="([^"]+)"/)[1], a.value]),
      );
      assert.deepEqual(
        map,
        {
          en: `${canonicalOrigin}${base}`,
          nb: `${canonicalOrigin}/no${base}`,
          'x-default': `${canonicalOrigin}${base}`,
        },
        url,
      );
    }
  }
});

test('language switch: only on bilingual pages, links to the existing other-language page', () => {
  for (const t of THEMES) {
    const dist = requireDist(t);
    for (const f of files(dist, '.html')) {
      const html = read(f);
      const url = urlOf(dist, f);
      const sw = html.match(/<nav class="nf-lang"[\s\S]*?<\/nav>/)?.[0];
      const base = url.replace(/^\/no\//, '/');
      if (!LOCALISED.includes(base)) {
        assert.equal(sw, undefined, `${url}: no switch without a translation`);
        continue;
      }
      assert.ok(sw, `${url}: language switch missing`);
      assert.match(sw, /aria-label="(Language|Språk)"/);
      const links = attrs(sw, 'a', 'href');
      assert.equal(links.length, 1);
      const target = url.startsWith('/no/') ? base : `/no${base}`;
      assert.equal(links[0].value, target);
      assert.match(
        links[0].tag,
        url.startsWith('/no/') ? /hreflang="en" lang="en"/ : /hreflang="nb" lang="nb"/,
      );
      assert.ok(existsSync(join(dist, target, 'index.html')), `${target} exists`);
    }
  }
});

test('Norwegian pages mark the untranslated English site chrome lang="en"', () => {
  const html = page('clinical', 'no/security');
  assert.match(html, /<div class="menu" id="nf-navlist" lang="en"/);
  assert.match(html, /<p class="tag" lang="en"/);
  assert.match(html, /<a href="\/no\/security\/" aria-current="page"/, 'nav Security -> NO page');
  assert.match(html, /href="#main"[^>]*>Hopp til innholdet</);
});

/* ------------------------------------------------------------ /security (SEC-158) */

test('/security and /no/security: title, meta, anchors, status pills, disclosure contact', () => {
  for (const t of THEMES) {
    for (const [p, title, pills, desc] of [
      [
        'security',
        'Security | ',
        ['Designed', 'Planned', 'Roadmap'],
        /^How .+ is designed to protect neural data/,
      ],
      [
        'no/security',
        'Sikkerhet | ',
        ['Designet', 'Planlagt', 'Veikart'],
        /^Slik er .+ utformet for å beskytte nevrale data/,
      ],
    ]) {
      const html = page(t, p);
      assert.match(html, new RegExp(`<title>${title.replace('|', '\\|')}[^<]+</title>`), p);
      assert.match(html.match(/<meta name="description" content="([^"]+)"/)[1], desc);
      for (const a of ANCHORS)
        assert.match(html, new RegExp(`<section[^>]*\\sid="${a}"`), `${p} #${a}`);
      for (const l of pills)
        assert.match(
          html,
          new RegExp(
            `class="pill pill--[a-z-]+"[^>]*>(<span[^>]*>[^<]*</span>)?${l}(</span>| \\(EU\\))`,
          ),
          `${p} pill ${l}`,
        );
      assert.match(html, /<table class="specs[^"]*"/, 'tables via the shared ComplianceGrid');
      assert.match(
        html,
        /class="nf-sv[^"]*" role="img"|role="img"[^>]*class="nf-sv/,
        'SecurityVisual slot',
      );
      assert.match(html, /href="mailto:security@[^"]+"/);
      assert.match(html, /href="\/\.well-known\/security\.txt"/);
      assert.doesNotMatch(visibleText(html), /<domain TBD>|\{brand\}|\{domain\}/);
    }
  }
});

test('/security EN and NO carry the same statuses in the same order', () => {
  const pills = (h) => [...h.matchAll(/class="pill pill--([a-z-]+)"/g)].map((m) => m[1]);
  const en = pills(page('clinical', 'security'));
  assert.ok(en.length >= 30);
  assert.deepEqual(pills(page('clinical', 'no/security')), en);
});

/* ------------------------------------------------------------ legal drafts */

test('legal pages: DRAFT banner, noindex, not in the sitemap; old placeholders gone', () => {
  for (const t of THEMES) {
    const dist = requireDist(t);
    const sm = read(join(dist, 'sitemap.xml'));
    for (const k of ['privacy', 'terms', 'cookies', 'company'])
      for (const [p, notice] of [
        [`legal/${k}`, /DRAFT – not legal advice/],
        [`no/legal/${k}`, /UTKAST – ikke juridisk rådgivning/],
      ]) {
        const html = page(t, p);
        const banner = html.match(/<p class="banner[^"]*" role="note" id="draft"[^>]*>([^<]+)</);
        assert.ok(banner, `${p}: visible draft banner`);
        assert.match(banner[1], notice);
        assert.match(html, /<meta name="robots" content="noindex,nofollow"/, `${p}: noindex`);
        assert.doesNotMatch(sm, new RegExp(`/${p}/`), `${p} must not be in the sitemap`);
      }
    assert.ok(!existsSync(join(dist, 'legal/imprint')), 'placeholder imprint page removed');
    assert.match(sm, /\/no\/security\//);
  }
});

test('footer: "Privacy · Terms · Cookies · Company information" (EN) and the draft titles (NO), localised hrefs', () => {
  const legalGroup = (html) => {
    const nav = html.match(/<nav aria-label="[^"]+" class="groups"[\s\S]*?<\/nav>/)[0];
    const groups = nav.split(/<p class="nf-label"[^>]*>/).slice(1);
    return groups.find((g) => /^(Legal|Juridisk)</.test(g));
  };
  const links = (g) =>
    [...g.matchAll(/<a href="([^"]+)"[^>]*>([^<]+)<\/a>/g)].map((m) => [m[1], m[2]]);
  assert.deepEqual(links(legalGroup(page('clinical', 'platform'))), [
    ['/legal/privacy/', 'Privacy'],
    ['/legal/terms/', 'Terms'],
    ['/legal/cookies/', 'Cookies'],
    ['/legal/company/', 'Company information'],
  ]);
  assert.deepEqual(links(legalGroup(page('clinical', 'no/legal/terms'))), [
    ['/no/legal/privacy/', 'Personvernerklæring'],
    ['/no/legal/terms/', 'Vilkår for bruk av nettstedet'],
    ['/no/legal/cookies/', 'Erklæring om informasjonskapsler (cookies)'],
    ['/no/legal/company/', 'Selskapsinformasjon'],
  ]);
});

test('legal drafts render verbatim structure: NO internal links point at NO pages', () => {
  const html = page('clinical', 'no/legal/privacy');
  assert.match(html, /<a href="\/no\/legal\/cookies\/">Erklæring om informasjonskapsler<\/a>/);
  assert.match(page('clinical', 'legal/terms'), /<a href="\/legal\/privacy">Privacy policy<\/a>/);
  for (const t of THEMES)
    for (const p of ['legal/privacy', 'no/legal/cookies'])
      assert.doesNotMatch(page(t, p), /<script(?![^>]*\ssrc=)[^>]*>/, 'no inline script');
});

test('company information (ehandelsloven § 8): key/value table has row headers and no empty header row', () => {
  for (const p of ['legal/company', 'no/legal/company']) {
    const html = page('clinical', p);
    assert.doesNotMatch(html, /<th[^>]*>\s*<\/th>/, `${p}: empty <th>`);
    assert.match(
      html,
      /<th scope="row"[^>]*>(Company name|Foretaksnavn)<\/th>/,
      `${p}: row header`,
    );
    assert.match(html, /Foretaksregisteret/);
  }
});
