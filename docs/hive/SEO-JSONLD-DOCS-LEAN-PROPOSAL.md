# Proposal: leaner JSON-LD on /docs/* (web-seo, web-queen review)

**Status:** proposal only, nothing applied. `apps/web/src/components/DocsJsonLd.astro` and the
`/docs/*` pages are web-docs' (they implemented their own JSON-LD wiring independently, on top of
`apps/web/src/components/JsonLd.astro` and `apps/web/src/lib/jsonld.ts`, which are web-seo's). The
change proposed below is entirely inside `JsonLd.astro` — no page file, and no `DocsJsonLd.astro`
line, needs to change — but it affects every page that renders 2+ JSON-LD nodes, so this needs
web-docs' and web-perf's sign-off, not just mine.

## Where the redundancy is

Every `/docs/*` page (`/docs/`, `/docs/api/`, `/docs/changelog/`, the 4 `/docs/quickstart/<slug>/`,
and the 2 `/docs/<guide>/` pages — 9 pages total, all via `DocsJsonLd.astro`) renders **two separate**
`<script type="application/ld+json">` tags: one full `Organization` node, one `TechArticle` node.
Each tag repeats its own `"@context":"https://schema.org"` string and its own
`<script type="application/ld+json">...</script>` wrapper. The `Organization` node's content
(`name`, `url`) is byte-identical on every single one of these 9 pages — only the `TechArticle`
node actually varies per page.

## Measured, on real content (`/docs/`, exact current values)

```
Organization: {"@context":"https://schema.org","@type":"Organization","name":"NeuroForge Bio","url":"https://neuroforge-bio.invalid"}
TechArticle:  {"@context":"https://schema.org","@type":"TechArticle","headline":"Docs","description":"Python SDK guide, quickstarts, API reference and changelog for the v1 API, and a preview of the C ABI. In development; the SDK is not published yet.","url":"https://neuroforge-bio.invalid/docs/"}
```

- **Current** (2 `<script>` tags): **490 bytes**.
- **Proposed** (1 `<script>` tag, `@graph`, shared `@context`): **428 bytes**.
- **Saves 62 bytes on this page.** Same saving (± a few bytes for headline/description length) on
  each of the other 8 `/docs/*` pages that use `DocsJsonLd.astro` → **≈558 bytes total** across the
  section. Against the ≈200 B headroom you mentioned, this alone covers it on any single page, with
  room to spare.

## The proposed change (not applied): `JsonLd.astro`, one file, web-seo's

```astro
---
// Renders one or more schema.org nodes as JSON-LD, inside the page body (never in <head>: Base.astro
// is frozen). Google explicitly supports JSON-LD anywhere in the document, not only <head>.
// Multiple nodes render as ONE `@graph`-wrapped <script>, not one <script> per node: same nodes, same
// @type values, same information - just without repeating "@context" and the <script> wrapper once
// per node. This is a standard, meaning-preserving JSON-LD technique (Google's own structured-data
// docs treat N separate <script> blocks and one @graph-wrapped block as equivalent). A single node
// still renders exactly as before (one plain node, no @graph wrapper) - existing single-node pages
// (/security, /no/security, /law-tracker, /research) are byte-identical to today.
// `type="application/ld+json")` is data, not code: scripts/inline-check.mjs (SEC-150a) exempts it
// from the CSP inline-script-hash requirement, so this needs no entry in security-headers.mjs. Every
// raw "<" in a value is replaced by its 6-character JSON escape sequence below, never a literal angle
// bracket, so a value can never break out into `</script>`.
import type { JsonLdNode } from '../lib/jsonld.ts';

interface Props { schema: JsonLdNode | JsonLdNode[] }
const { schema } = Astro.props;
const nodes = Array.isArray(schema) ? schema : [schema];
const doc =
  nodes.length === 1
    ? nodes[0]
    : {
        '@context': 'https://schema.org',
        '@graph': nodes.map(({ '@context': _drop, ...rest }) => rest),
      };
---
<script type="application/ld+json" set:html={JSON.stringify(doc).replace(/</g, '\\u003c')} />
```

## What else this touches (full cost, not just the component)

This is a **site-wide** change to a shared component, not a docs-only one — every page that
currently passes an array of 2+ nodes to `<JsonLd>` is affected, all for the better:

| Page(s) | Nodes today | Script tags today → after |
|---|---|---|
| `/docs/*` (9 pages) | Organization + TechArticle | 2 → 1, saves ~62 B/page |
| `/research/somatosensory-closed-loop/` | Organization + TechArticle | 2 → 1, saves ~62 B |
| `/playground/`, `/interface/` | Organization + Dataset + WebApplication | 3 → 1, saves more (a 3rd `@context`+wrapper instead of a 2nd) |
| `/security`, `/no/security`, `/law-tracker`, `/research/` | Organization only | 1 → 1, **byte-identical**, no change |

**Test impact (the real cost of this change):** my own test files parse JSON-LD by reading every
`<script type="application/ld+json">` block and doing
`Array.isArray(JSON.parse(b)) ? JSON.parse(b) : [JSON.parse(b)]` to get a flat node list. A
`@graph`-wrapped object is neither an array nor a bare node — that parsing would need to also unwrap
`parsed['@graph']` when present, or every one of these would need updating:
`apps/web/test/seo.test.mjs`, `apps/web/test/seo-integrity.test.mjs`,
`apps/web/test/seo-dist-audit.test.mjs`, and (web-docs' own) whatever `docs.test.mjs` uses to check
the Organization/TechArticle nodes on `/docs/*`. None of this is difficult (one small shared helper
function would fix all of them), but it's real, cross-file work, not just the one component edit.

## Also found, unrelated to leanness (flagging for web-docs, not fixing)

`/docs/api/`'s `DocsJsonLd` call uses `L.description` for the JSON-LD `TechArticle.description` -
but `L` is `overview.apiPage`, and `apiPage.description` in `apps/web/src/docs/index.json` is the
literal string `"Description"` (a table-column-header label reused elsewhere on the page, e.g.
`<th scope="col">{L.description}</th>`), not a real page description. So `/docs/api/`'s JSON-LD
currently says its own description is the single word "Description". Worth a real description there
regardless of whether this leanness proposal goes ahead.

## What I'd want before touching anything

1. web-docs: does `@graph`-wrapping change anything about how you read or test the docs pages' JSON-LD
   (beyond the parsing-helper update above)? OK with `/docs/api/`'s description bug being fixed
   separately?
2. web-perf: does this need re-measuring against `tools/web/perf-budgets.json`/
   `perf-budget-adjustments.json`, or does a documented reduction not need the same process as a raise?
3. If both are fine with it, I'd implement the `JsonLd.astro` change plus the shared unwrap-helper
   fix across the 3 test files I own, hand `docs.test.mjs`'s equivalent fix to web-docs (or offer to
   do it with their sign-off), and verify in a bci-queen slot before handoff - same pattern as T5b.
