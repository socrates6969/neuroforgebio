// schema.org JSON-LD builders (web-seo, WEB-PLAN roster). These only reshape page content that is
// already rendered on the page (title/description, both sourced and evidence-tagged in @nf/content)
// into structured data. No metric, price, rating or certification is added here (WEB-PLAN rule 3):
// no aggregateRating, no offers, no operatingSystem/softwareVersion, no author/datePublished, because
// none of those are in the repo yet. Add them only once a real, sourced value exists.
export interface JsonLdNode {
  '@context': 'https://schema.org';
  '@type': string;
  [key: string]: unknown;
}

/** "Title · Brand" / "Title | Brand" -> "Title" (a schema name/headline should not carry the site suffix). */
export function stripBrandSuffix(title: string, brand: string): string {
  for (const sep of [' · ', ' | ']) {
    const suffix = `${sep}${brand}`;
    if (title.endsWith(suffix)) return title.slice(0, -suffix.length);
  }
  return title;
}

/** Site-wide Organization node. Added to every inner page by Base.astro (never the homepage). */
export function organizationSchema(name: string, url: string): JsonLdNode {
  return { '@context': 'https://schema.org', '@type': 'Organization', name, url };
}

/** /platform and /sdks: the product and its SDKs are software, described as planned/roadmap in copy. */
export function softwareApplicationSchema(opts: {
  title: string;
  description: string;
  url: string;
  brand: string;
  category: string;
}): JsonLdNode {
  return {
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    name: stripBrandSuffix(opts.title, opts.brand),
    description: opts.description,
    url: opts.url,
    applicationCategory: opts.category,
  };
}

/** Docs pages and research whitepapers: written technical content. */
export function techArticleSchema(opts: {
  title: string;
  description: string;
  url: string;
  brand: string;
}): JsonLdNode {
  return {
    '@context': 'https://schema.org',
    '@type': 'TechArticle',
    headline: stripBrandSuffix(opts.title, opts.brand),
    description: opts.description,
    url: opts.url,
  };
}

/**
 * Parses `creator`/`datePublished`/`name` out of a DANDI-style citation string, e.g.
 * "O'Doherty, Joseph (2024) MC_RTT: macaque motor cortex spiking activity during self-paced
 * reaching (Version 0.241017.1444) [Data set]. DANDI archive. https://doi.org/...". Deriving these
 * from the citation (instead of hardcoding them at each call site) means a re-pointed dataset version
 * can never silently drift from what the visible citation says (nfb-playground, T5b review). `name`
 * is the dataset's own title (their citation, not our descriptive `dataset.name` field) - schema.org
 * `Dataset.name` here is a citation of their work. Returns null if the citation isn't in this form,
 * so a page can render no Dataset node rather than an invented one.
 */
export function parseDatasetCitation(
  citation: string,
): { creatorName: string; datePublished: string; name: string } | null {
  const m = /^(.+?), (.+?) \((\d{4})\) (.+?) \(Version /.exec(citation);
  if (!m) return null;
  return { creatorName: `${m[2]} ${m[1]}`, datePublished: m[3], name: m[4] };
}

/**
 * A third-party dataset a page replays or analyzes (e.g. an open neuroscience recording), cited with
 * its own real publication year and DOI (docs/hive/SEO-JSONLD-PLAYGROUND-INTERFACE-PROPOSAL.md).
 * Unlike the builders above, this intentionally sets `datePublished`/`creator`: they describe the
 * cited dataset, not our own product, and every field must come from the dataset's own citation
 * (never the CC-BY notice's summary of what we changed, and never a draft DANDI page's author list
 * when a versioned citation exists) - nothing here is invented (WEB-PLAN rule 3). `name`,
 * `creatorName` and `datePublished` should come from `parseDatasetCitation(citation)`, not be
 * hardcoded at the call site.
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

/**
 * An interactive page that is a tool/demo, not a marketing or written-content page. `isBasedOnUrl`
 * should point at the cited dataset's DOI, never claim the page shows the raw, unmodified data (the
 * page's own CC-BY notice already states what was changed) - this node adds no accuracy numbers.
 * `description` is optional: when the page's own meta/og description already says the same thing,
 * skip it here rather than repeat it (perf-budget trim, T5b review).
 */
export function webApplicationSchema(opts: {
  title: string;
  description?: string;
  url: string;
  brand: string;
  isBasedOnUrl?: string;
}): JsonLdNode {
  return {
    '@context': 'https://schema.org',
    '@type': 'WebApplication',
    name: stripBrandSuffix(opts.title, opts.brand),
    ...(opts.description ? { description: opts.description } : {}),
    url: opts.url,
    applicationCategory: 'EducationalApplication',
    ...(opts.isBasedOnUrl ? { isBasedOn: opts.isBasedOnUrl } : {}),
  };
}
