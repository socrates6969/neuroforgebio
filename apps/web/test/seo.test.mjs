// SEO metadata (web-seo, WEB-PLAN roster): every inner page gets a unique title + description and one
// canonical link (from Base.astro, sitewide, unrelated to the shared-file ownership limits below); a
// smaller set of pages also gets schema.org JSON-LD (Organization, plus TechArticle on the whitepaper).
//
// Scope note: `apps/web/src/pages/[page].astro` (/platform /governance /sdks /pricing) is temporarily
// owned by web-copy (WEB-BOARD log), and `apps/web/src/pages/docs/**` is web-docs' (WEB-BOARD ownership
// table), so JSON-LD there is a proposal (docs/web/seo-audit.md), not shipped in this pass. The pages
// web-seo actually renders JsonLd on: /security, /no/security, /law-tracker, /research,
// /research/<slug>, and (T5b, with nfb-playground's sign-off) /playground and /interface, which also
// carry a Dataset node citing MC_RTT/DANDI 000129 (docs/hive/SEO-JSONLD-PLAYGROUND-INTERFACE-PROPOSAL.md).
//
// og:type and Twitter Card tags are NOT added: they need <head>, i.e. Base.astro, which is frozen (one
// of the homepage-pinned sources in apps/web/test/homepage.test.mjs — any diff fails that test's raw
// source check, even an opt-in prop that never fires on "/"). Proposed instead in
// docs/hive/SEO-BASE-PROPOSAL.md for a centrally-landed change.
//
// JSON-LD does not need <head>: Google explicitly supports it anywhere in the document, so it renders
// in the page body via <JsonLd>, with no Base.astro change at all.
//
// The homepage is excluded on purpose (WEB-PLAN rule 1); gallery and 404 are internal/error pages, not
// indexable content.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { WEB, files, read, requireDist, urlPath } from './_dist.mjs';

const THEMES = ['clinical', 'cosmos'];
const OUT_OF_SCOPE = ['/gallery'];
/** Pages web-seo actually renders <JsonLd> on in this pass (see scope note above). */
const JSONLD_PAGES = [
  '/security/',
  '/no/security/',
  '/law-tracker/',
  '/research/',
  '/research/somatosensory-closed-loop/',
  '/playground/',
  '/interface/',
];

// The same asset apps/web/src/pages/{playground,interface}.astro import, and the same citation-
// parsing regex as apps/web/src/lib/jsonld.ts's parseDatasetCitation (duplicated here so this test
// stays independent of it - it's checking that the pages' derived values actually match the source,
// not just that the parser agrees with itself).
const MC_RTT_DATASET = JSON.parse(
  readFileSync(join(WEB, 'src/assets/playground/mc-rtt-playground.json'), 'utf8'),
).dataset;
const CITED = /^(.+?), (.+?) \((\d{4})\) (.+?) \(Version /.exec(MC_RTT_DATASET.citation);

/** Inner (real, indexable, in-scope) content pages. */
function innerPages(dist) {
  return files(dist, '.html').filter((f) => {
    const p = urlPath(dist, f);
    return (
      p !== '/' &&
      !/^\/404(\.html)?\/?$/.test(p) &&
      !OUT_OF_SCOPE.some((prefix) => p === `${prefix}/` || p.startsWith(`${prefix}/`))
    );
  });
}

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

function jsonLdBlocks(html) {
  return [
    ...html.matchAll(
      /<script[^>]*\stype=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script\s*>/gi,
    ),
  ].map((m) => m[1]);
}

for (const theme of THEMES) {
  test(`${theme}: every inner page has a title, description and one canonical link`, () => {
    const dist = requireDist(theme);
    const pages = innerPages(dist);
    assert.ok(pages.length >= 10, `expected several inner pages, got ${pages.length}`);
    const titles = [];
    const descriptions = [];
    for (const f of pages) {
      const html = read(f);
      const title = html.match(/<title>([^<]*)<\/title>/)?.[1];
      assert.ok(title && title.trim(), `${relative(dist, f)}: missing <title>`);
      titles.push(title);
      const description = metaValue(html, 'description');
      assert.ok(
        description && description.trim(),
        `${relative(dist, f)}: missing meta description`,
      );
      descriptions.push(description);
      const canonicals = [...html.matchAll(/<link\b[^>]*\srel=["']canonical["'][^>]*>/gi)];
      assert.equal(
        canonicals.length,
        1,
        `${relative(dist, f)}: expected exactly one rel=canonical`,
      );
      assert.match(
        canonicals[0][0],
        /href=["']https:\/\//,
        `${relative(dist, f)}: canonical must be absolute`,
      );
    }
    assert.equal(
      new Set(titles).size,
      titles.length,
      `${theme}: duplicate <title> across inner pages`,
    );
    // Descriptions: known pre-existing duplicates (all 4 legal pages per locale share the draft
    // disclaimer text; owned by nfb-legal, flagged in docs/web/seo-audit.md, not fixed here) are
    // excluded rather than silently allowed everywhere.
    const legalDup = descriptions.filter((d) =>
      /DRAFT.*Norwegian lawyer|UTKAST.*norsk advokat/i.test(d),
    );
    const other = descriptions.filter((d) => !legalDup.includes(d));
    assert.equal(
      new Set(other).size,
      other.length,
      `${theme}: duplicate meta description across inner pages (outside the known legal-draft dupes)`,
    );
  });

  test(`${theme}: every inner page has basic Open Graph tags`, () => {
    const dist = requireDist(theme);
    for (const f of innerPages(dist)) {
      const html = read(f);
      const rel = relative(dist, f);
      for (const key of ['og:title', 'og:description', 'og:url', 'og:site_name', 'og:locale']) {
        const v = metaValue(html, key);
        assert.ok(v && v.trim(), `${rel}: missing ${key}`);
      }
    }
  });

  test(`${theme}: JSON-LD pages (security, law-tracker, research, playground, interface) have parseable schema.org JSON-LD with an Organization node`, () => {
    const dist = requireDist(theme);
    for (const p of JSONLD_PAGES) {
      const f = files(dist, '.html').find((x) => urlPath(dist, x) === p);
      assert.ok(f, `${p}: page not found in dist`);
      const html = read(f);
      const blocks = jsonLdBlocks(html);
      assert.ok(blocks.length >= 1, `${p}: no <script type="application/ld+json"> block`);
      const nodes = [];
      for (const b of blocks) {
        let parsed;
        assert.doesNotThrow(
          () => {
            parsed = JSON.parse(b);
          },
          `${p}: JSON-LD block does not parse: ${b.slice(0, 120)}`,
        );
        nodes.push(...(Array.isArray(parsed) ? parsed : [parsed]));
      }
      for (const node of nodes) {
        assert.equal(node['@context'], 'https://schema.org', `${p}: JSON-LD node missing @context`);
        assert.ok(
          typeof node['@type'] === 'string' && node['@type'],
          `${p}: JSON-LD node missing @type`,
        );
      }
      assert.ok(
        nodes.some((n) => n['@type'] === 'Organization' && n.name && n.url),
        `${p}: no Organization node with name+url`,
      );
    }
  });

  test(`${theme}: /research/<slug> also carries a TechArticle node`, () => {
    const dist = requireDist(theme);
    const p = '/research/somatosensory-closed-loop/';
    const f = files(dist, '.html').find((x) => urlPath(dist, x) === p);
    const nodes = jsonLdBlocks(read(f)).flatMap((b) => {
      const parsed = JSON.parse(b);
      return Array.isArray(parsed) ? parsed : [parsed];
    });
    assert.ok(
      nodes.some((n) => n['@type'] === 'TechArticle'),
      `${p}: expected a TechArticle node`,
    );
  });

  test(`${theme}: /playground and /interface carry a Dataset node (MC_RTT/DANDI 000129) and a WebApplication node`, () => {
    const dist = requireDist(theme);
    const doiUrl = `https://doi.org/${MC_RTT_DATASET.doi}`;
    assert.ok(CITED, 'MC_RTT_DATASET.citation must match the DANDI citation form this test parses');
    const [, lastName, firstName, year, title] = CITED;
    for (const p of ['/playground/', '/interface/']) {
      const f = files(dist, '.html').find((x) => urlPath(dist, x) === p);
      assert.ok(f, `${p}: page not found in dist`);
      const nodes = jsonLdBlocks(read(f)).flatMap((b) => {
        const parsed = JSON.parse(b);
        return Array.isArray(parsed) ? parsed : [parsed];
      });
      const dataset = nodes.find((n) => n['@type'] === 'Dataset');
      assert.ok(dataset, `${p}: expected a Dataset node`);
      // nfb-playground's sign-off conditions: creator, datePublished and name are all parsed from
      // ds.citation (never hardcoded), so a re-pointed dataset version can't silently drift from the
      // visible citation; license URL is exact; the DOI is used as both identifier and isBasedOn.
      assert.deepEqual(
        dataset.creator,
        { '@type': 'Person', name: `${firstName} ${lastName}` },
        `${p}: Dataset creator must match the parsed citation`,
      );
      assert.equal(
        dataset.datePublished,
        year,
        `${p}: Dataset datePublished must match the citation year`,
      );
      assert.equal(dataset.name, title, `${p}: Dataset name must be the cited work's own title`);
      assert.equal(
        dataset.license,
        'https://creativecommons.org/licenses/by/4.0/',
        `${p}: Dataset license`,
      );
      assert.equal(dataset.identifier, doiUrl, `${p}: Dataset identifier`);
      assert.equal(dataset.url, doiUrl, `${p}: Dataset url must be https://doi.org/<dataset.doi>`);
      assert.match(dataset.citation, /^O'Doherty, Joseph \(2024\)/, `${p}: Dataset citation`);
      // no accuracy numbers or claims (WEB-PLAN rule 3 / nfb-playground condition 3)
      assert.doesNotMatch(
        String(dataset.description ?? ''),
        /R²|accuracy|percent|%/i,
        `${p}: Dataset description must not carry accuracy claims`,
      );

      const webApp = nodes.find((n) => n['@type'] === 'WebApplication');
      assert.ok(webApp, `${p}: expected a WebApplication node`);
      assert.equal(
        webApp.isBasedOn,
        doiUrl,
        `${p}: WebApplication isBasedOn must cite the same DOI`,
      );
      assert.doesNotMatch(
        String(webApp.description ?? ''),
        /R²|accuracy|percent|%/i,
        `${p}: WebApplication description must not carry accuracy claims`,
      );
    }
  });
}

test('the homepage is unaffected: no JSON-LD script anywhere in it', () => {
  for (const theme of THEMES) {
    const dist = requireDist(theme);
    const html = read(`${dist}/index.html`);
    assert.equal(jsonLdBlocks(html).length, 0, `${theme}: homepage must stay untouched`);
  }
});
