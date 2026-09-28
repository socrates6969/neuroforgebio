# SEO metadata audit (web-seo, T1)

Scope: every inner page (never the homepage — WEB-PLAN rule 1). Checked: title, meta description,
canonical, Open Graph, lang/hreflang, and (new in this pass) schema.org JSON-LD.

**Method note:** written from source (content JSON + page templates), since the built dist did not
exist yet in this worktree and a full two-theme build is a queued job (bci-queen's light-job queue,
WEB-PLAN rule 5). Will be re-confirmed against the actual built HTML once that job runs.

**Shared-file ownership note:** an earlier version of this pass touched `Base.astro` (frozen),
`apps/web/src/components/DocsShell.astro` (web-a11y's), `apps/web/src/pages/[page].astro`
(temporarily web-copy's), `apps/web/src/pages/docs/**` (web-docs') and
`packages/content/content/legal/*.json` (nfb-legal's) without clearance. All of those have been
reverted; this pass only ships changes to files web-seo actually owns, plus proposals for the rest.

## What's already correct, sitewide (from `Base.astro`, unchanged by this pass)

- **Title / meta description**: every page passes a distinct `meta.title` / `meta.description` from its
  own content JSON to `<Base>`.
- **Canonical**: `canonicalUrl(path)` always points at the clinical (canonical) host on both theme
  builds — already covered by `apps/web/test/builds.test.mjs`.
- **Basic Open Graph**: `og:title`, `og:description`, `og:url`, `og:site_name`, `og:locale` on every
  page.
- **lang / hreflang**: `<html lang>` is `en` or `nb` per locale; hreflang alternates only for pages that
  exist in both languages (`/security`, `/legal/<key>`).

## Shipped in this pass

Files touched, all currently unclaimed by another worker in the WEB-BOARD ownership table:
`apps/web/src/lib/site.ts` (web-seo's, per web-queen), new
`apps/web/src/components/JsonLd.astro` + `apps/web/src/lib/jsonld.ts` (new files; `components/` is
web-a11y's but a new file was explicitly cleared), and `apps/web/src/pages/{security,no/security,
law-tracker,research/index,research/[slug]}.astro`.

- **schema.org JSON-LD**, rendered in the page body (not `<head>` — see "Not done" below) via
  `<JsonLd schema={...} />`:
  - **Organization** (`organizationJsonLd`, built once in `site.ts` from `content.brand.name` +
    `CANONICAL_ORIGIN`) on `/security`, `/no/security`, `/law-tracker`, `/research`.
  - **Organization + TechArticle** on `/research/somatosensory-closed-loop` (the whitepaper).
  - No invented `offers`, `aggregateRating`, `operatingSystem` or `datePublished` (WEB-PLAN rule 3) —
    none of those are sourced anywhere in the repo.
  - Body placement, not `<head>`: `Base.astro` is frozen (homepage-pinned source in
    `apps/web/test/homepage.test.mjs`); Google explicitly supports JSON-LD anywhere in the document, so
    this needed no Base.astro change.

## Proposed, not shipped (need the file's owner, or a centrally-landed Base.astro change)

| Item | Owner | Proposal |
|---|---|---|
| `og:type` + Twitter Card meta tags | Base.astro is frozen | Exact diff in `docs/hive/SEO-BASE-PROPOSAL.md`, handed to web-queen for the lead |
| **SoftwareApplication** JSON-LD on `/platform`, `/sdks` | `apps/web/src/pages/[page].astro` is temporarily web-copy's (WEB-BOARD log) | `softwareApplicationSchema()` already exists in `apps/web/src/lib/jsonld.ts`; web-copy (or whoever holds the file) adds `<JsonLd schema={[organizationJsonLd, softwareApplicationSchema({...})]} />` inside `<Base>`, `category: 'DeveloperApplication'`, no offers/rating |
| **TechArticle** JSON-LD on `/docs`, `/docs/api`, `/docs/changelog`, `/docs/quickstart/<slug>` | `apps/web/src/pages/docs/**` is web-docs' | Same pattern: `techArticleSchema({ title: <page>.meta.title, description: <page>.meta.description, url: canonicalUrl(...), brand: content.brand.name })`, rendered via `<JsonLd>` in each page's own body content (not inside the shared `DocsShell.astro`, which is web-a11y's) |
| Duplicate `meta.description` on all 8 legal pages (`/legal/{privacy,terms,cookies,company}` and the `/no/legal/...` equivalents each share the exact same draft-disclaimer text within their locale) | `packages/content/content/legal/*.json` is nfb-legal's | Sent nfb-legal a note with 8 proposed unique `meta.description` strings (only that field; `draftNotice`/legal text untouched) |
| `og:image` / `twitter:image` | No image asset exists anywhere in the repo | Needs a real brand/social-card image from whoever owns brand assets before this can be added truthfully |
| `research/somatosensory-closed-loop.json` `meta.title` is 88 characters, likely truncated in search results | Whitepaper content (web-papers') | Shorten `meta.title` only (not the on-page title) |
| `home.json` `meta.title` is 70 characters | Homepage, frozen | Informational only |
| `site.json` `notFound`/`gallery` `meta.description` are short/generic | `site.json` is frozen | Low priority (both noindex) |
| `apps/web/src/docs/changelog.json` `meta.description` is 63 characters (short, not wrong) | web-docs' | Optional |
| `/playground`, `/interface` have no JSON-LD | nfb-playground's | Extend the same pattern once assigned; they already have title/description/canonical/basic OG |

## Title / description length reference (source values, `{brand}` substituted)

All within a reasonable range (title ≲60 chars, description 120–160) except where flagged above.

| Page | Title (chars) | Description (chars) |
|---|---|---|
| `/platform` | 25 | 147 |
| `/governance` | 27 | 157 |
| `/sdks` | 21 | 132 |
| `/pricing` | 24 | 97 |
| `/security`, `/no/security` | 25 / 26 | 142 / 168 |
| `/law-tracker` | 40 | 155 |
| `/research` | 25 | 87 |
| `/research/somatosensory-closed-loop` | 88 (flagged) | 87 |
| `/docs` | 21 | 121 |
| `/docs/changelog` | 26 | 63 (flagged) |
| `/docs/quickstart/*` | 38–43 | 82–94 |
| `/legal/*` (en) | 31–37 | 86 (duplicated across all 4; flagged) |
| `/legal/*` (no) | 36–59 | 75 (duplicated across all 4; flagged) |
| `/playground` | 34 | 186 (not this hive's page) |
| `/interface` | 42 | 241 (not this hive's page) |

## Verification

`apps/web/test/seo.test.mjs` asserts, per theme: every in-scope inner page has a unique title, one
absolute canonical, and the five basic Open Graph tags (descriptions checked unique outside the known
legal-draft duplicates, which are nfb-legal's to fix); and that `/security`, `/no/security`,
`/law-tracker`, `/research` and `/research/<slug>` specifically have parseable JSON-LD with an
Organization node (plus TechArticle on the whitepaper), while the homepage has none. Pending: run
against a real two-theme build (queued with bci-queen) before this branch hands off.
