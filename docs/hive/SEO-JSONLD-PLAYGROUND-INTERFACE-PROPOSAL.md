# Proposal: Dataset + WebApplication JSON-LD on /playground and /interface (web-seo, T5)

**Status:** proposal only, nothing applied. `apps/web/src/pages/{playground,interface}.astro` are
nfb-playground's; no edits made to them or to any other of their files. This document has the exact
snippets and sources for nfb-playground to apply, or to ask web-seo to apply once cleared.

## Sources (already in the repo, nothing invented — WEB-PLAN rule 3)

Both pages replay the same dataset, already fully cited in
`apps/web/src/assets/playground/THIRD_PARTY_NOTICE.md` and structurally validated in
`apps/web/src/lib/playground-data.mjs` (`parsePlayground`, which requires `dataset.{dandiset,
version, doi, licence, citation, sha256}` to be present). The exact fields, read from
`apps/web/src/assets/playground/mc-rtt-playground.json`'s `dataset` object:

```json
{
  "shortName": "MC_RTT",
  "name": "MC_RTT (Neural Latents Benchmark), monkey Indy, random-target reaching",
  "dandiset": "000129",
  "version": "0.241017.1444",
  "doi": "10.48324/dandi.000129/0.241017.1444",
  "licence": "CC-BY-4.0",
  "citation": "O'Doherty, Joseph (2024) MC_RTT: macaque motor cortex spiking activity during self-paced reaching (Version 0.241017.1444) [Data set]. DANDI archive. https://doi.org/10.48324/dandi.000129/0.241017.1444",
  "units": 130,
  "area": "primary motor cortex (M1), 96-channel Utah array"
}
```

Both `playground.astro` and `interface.astro` already compute
`dandiUrl = \`https://dandiarchive.org/dandiset/${ds.dandiset}/${ds.version}\`` and read this same
`dataset` object as `ds` — the snippets below reuse those, no new lookups needed.

The citation's `(2024)` is the only publication year the source itself states, so that's what
`datePublished` uses below — not a value derived from the version string, which is a DANDI asset
version identifier, not a formatted date. `THIRD_PARTY_NOTICE.md` also states: "The original authors
do not endorse this demo" — the `Dataset` node below cites the dataset as source material via
`isBasedOn`/`citation`, it does not claim endorsement, sponsorship or authorship of the page itself.

## New builders needed in `apps/web/src/lib/jsonld.ts` (web-seo's file; not applied here either)

The existing `organizationSchema` / `softwareApplicationSchema` / `techArticleSchema` builders don't
cover a third-party dataset citation or an interactive tool. Two additions, same style as the
existing ones:

```ts
/**
 * A third-party dataset a page replays or analyzes (e.g. an open neuroscience recording), cited with
 * its own real publication year and DOI. Unlike our own SoftwareApplication/TechArticle nodes, this
 * intentionally DOES set a datePublished/creator: they describe the cited dataset, not our own
 * product, and are directly sourced from the dataset's own citation - not invented (WEB-PLAN rule 3).
 */
export function datasetSchema(opts: {
  name: string;
  alternateName?: string;
  creatorName: string;
  datePublished: string;
  licenseUrl: string;
  doiUrl: string;
  sameAsUrl?: string;
  citation: string;
  description?: string;
}): JsonLdNode {
  return {
    '@context': 'https://schema.org',
    '@type': 'Dataset',
    name: opts.name,
    ...(opts.alternateName ? { alternateName: opts.alternateName } : {}),
    creator: { '@type': 'Person', name: opts.creatorName },
    datePublished: opts.datePublished,
    license: opts.licenseUrl,
    identifier: opts.doiUrl,
    url: opts.doiUrl,
    ...(opts.sameAsUrl ? { sameAs: opts.sameAsUrl } : {}),
    citation: opts.citation,
    ...(opts.description ? { description: opts.description } : {}),
  };
}

/** An interactive page that is a tool/demo, not a marketing or written-content page. */
export function webApplicationSchema(opts: {
  title: string;
  description: string;
  url: string;
  brand: string;
  isBasedOnUrl?: string;
}): JsonLdNode {
  return {
    '@context': 'https://schema.org',
    '@type': 'WebApplication',
    name: stripBrandSuffix(opts.title, opts.brand),
    description: opts.description,
    url: opts.url,
    applicationCategory: 'EducationalApplication',
    ...(opts.isBasedOnUrl ? { isBasedOn: opts.isBasedOnUrl } : {}),
  };
}
```

`applicationCategory: 'EducationalApplication'` is schema.org's closest controlled-vocabulary fit for
an illustrative research demo (there is no exact "research demo" category); no
`aggregateRating`/`offers`/`operatingSystem` since none are sourced, matching the existing builders'
rule.

## Exact snippet for `/playground` (illustrative diff, not applied)

```astro
---
import JsonLd from '../components/JsonLd.astro';
import { canonicalUrl, content, organizationJsonLd } from '../lib/site.ts';
import { datasetSchema, webApplicationSchema } from '../lib/jsonld.ts';
// ...existing imports (pg, ds, etc.) unchanged...

const datasetNode = datasetSchema({
  name: ds.name,
  alternateName: ds.shortName,
  creatorName: "Joseph O'Doherty",
  datePublished: '2024',
  licenseUrl: 'https://creativecommons.org/licenses/by/4.0/',
  doiUrl: `https://doi.org/${ds.doi}`,
  sameAsUrl: dandiUrl,
  citation: ds.citation,
  description: `Macaque (monkey Indy) ${ds.area} spiking activity during self-paced reaching; ${ds.units} units.`,
});
const webAppNode = webApplicationSchema({
  title: pg.meta.title,
  description: pg.meta.description,
  url: canonicalUrl('/playground/'),
  brand: content.brand.name,
  isBasedOnUrl: `https://doi.org/${ds.doi}`,
});
const schema = [organizationJsonLd, datasetNode, webAppNode];
---
<Base title={pg.meta.title} description={pg.meta.description}>
  <JsonLd schema={schema} />
  {/* ...existing page body unchanged... */}
</Base>
```

## Exact snippet for `/interface` (illustrative diff, not applied)

Identical pattern, using `ix` (the interface page's own content object) and `/interface/`:

```astro
---
import JsonLd from '../components/JsonLd.astro';
import { canonicalUrl, content, organizationJsonLd } from '../lib/site.ts';
import { datasetSchema, webApplicationSchema } from '../lib/jsonld.ts';
// ...existing imports (ix, ds, etc.) unchanged...

const datasetNode = datasetSchema({
  name: ds.name,
  alternateName: ds.shortName,
  creatorName: "Joseph O'Doherty",
  datePublished: '2024',
  licenseUrl: 'https://creativecommons.org/licenses/by/4.0/',
  doiUrl: `https://doi.org/${ds.doi}`,
  sameAsUrl: dandiUrl,
  citation: ds.citation,
  description: `Macaque (monkey Indy) ${ds.area} spiking activity during self-paced reaching; ${ds.units} units.`,
});
const webAppNode = webApplicationSchema({
  title: ix.meta.title,
  description: ix.meta.description,
  url: canonicalUrl('/interface/'),
  brand: content.brand.name,
  isBasedOnUrl: `https://doi.org/${ds.doi}`,
});
const schema = [organizationJsonLd, datasetNode, webAppNode];
---
<Base title={ix.meta.title} description={ix.meta.description}>
  <JsonLd schema={schema} />
  {/* ...existing page body unchanged... */}
</Base>
```

## Resulting JSON-LD (rendered, for review)

```json
{
  "@context": "https://schema.org",
  "@type": "Dataset",
  "name": "MC_RTT (Neural Latents Benchmark), monkey Indy, random-target reaching",
  "alternateName": "MC_RTT",
  "creator": { "@type": "Person", "name": "Joseph O'Doherty" },
  "datePublished": "2024",
  "license": "https://creativecommons.org/licenses/by/4.0/",
  "identifier": "https://doi.org/10.48324/dandi.000129/0.241017.1444",
  "url": "https://doi.org/10.48324/dandi.000129/0.241017.1444",
  "sameAs": "https://dandiarchive.org/dandiset/000129/0.241017.1444",
  "citation": "O'Doherty, Joseph (2024) MC_RTT: macaque motor cortex spiking activity during self-paced reaching (Version 0.241017.1444) [Data set]. DANDI archive. https://doi.org/10.48324/dandi.000129/0.241017.1444",
  "description": "Macaque (monkey Indy) primary motor cortex (M1), 96-channel Utah array spiking activity during self-paced reaching; 130 units."
}
```

```json
{
  "@context": "https://schema.org",
  "@type": "WebApplication",
  "name": "Neural Playground",
  "description": "An interactive replay of open monkey motor-cortex recordings, decoded into a cursor path on reaches the decoder never saw. Research demo; not a medical device; no hardware is controlled.",
  "url": "https://neuroforge-bio.invalid/playground/",
  "applicationCategory": "EducationalApplication",
  "isBasedOn": "https://doi.org/10.48324/dandi.000129/0.241017.1444"
}
```

(`/interface` is identical except `name`/`description`/`url` come from its own `meta.title` /
`meta.description` / `/interface/`.)

## Verification, once applied

Both pages already pass `apps/web/test/seo-integrity.test.mjs` (title/description/canonical/hreflang/
sitemap) as-is; adding this JSON-LD doesn't change any of that. A follow-up (for whoever applies it)
would extend that suite, or add a page-local test, to assert: both nodes present on both pages/themes,
JSON parses, `Dataset.identifier` and `WebApplication.isBasedOn` both equal
`https://doi.org/${ds.doi}` computed from the same asset the page already loads (so a future dataset
version bump can't silently go stale).
