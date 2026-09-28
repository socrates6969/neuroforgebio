# site-rs: what the skipped routes would need

Design note for `tests/head_parity.rs`'s (branch `feature/site-rs-head-parity`) explicit skip list:
`/docs/*`, `/playground/`, `/interface/`, `/investors/`, `/no/<page>/`, `/arena/`. For each route:
which content files and Astro logic actually produce its `<head>`/JSON-LD, what `tools/site-rs`
would need to load to compute the same values, an effort estimate, and any blocker. Read-only
investigation (source inspection); no code changes.

Every route below still goes through `Base.astro` (unchanged, "frozen" per
`apps/web/test/homepage.test.mjs` - the homepage's own rule, but the file is shared, so its
`title`/`description`/`canonical`/`noindex`/`locale` → head-field logic is identical everywhere):
`canonical = canonicalUrl(path)`, `og:title = title`, `og:description = description`,
`og:url = canonical`, `og:site_name = brand.name`, `og:locale = locale === 'no' ? 'nb_NO' : 'en_US'`,
`<meta name="robots">` present with `noindex,nofollow` iff the page's `noindex` prop is truthy. None
of that is route-specific work; it's already ported (`site_rs::head`, `site_rs::sitemap::canonical_url`).
What's route-specific, and listed per route below, is *only*: where `title`/`description` come from,
what decides `noindex`, and what (if anything) beyond the `Organization` JSON-LD node the page adds.

## `/docs/*` (`index`, `api`, `changelog`, `quickstart/[slug]`, `[guide]`)

- **Head fields:** all five route files pass `title`/`description` into `DocsShell.astro`, which
  calls `Base` with **no `noindex` prop and no `locale` prop** - so `noindex` is always `false` and
  `locale` is always `en` for every docs page (never under `/no/`). Each route's title/description
  source: `index` → `lib/docs.ts`'s `overview` (from `docs/index.json`); `api` → `overview.apiPage`
  (also `docs/index.json`, a nested key); `changelog` → `changes` (`docs/changelog.json`); `quickstart/
  [slug]` → the matching entry of `quickstarts` (`docs/quickstarts/*.json`, already loadable -
  `content::docs_routes()` reads this directory's `order` field, though not yet `meta.title`/
  `description`); `[guide]` → the matching entry of `guides` (`docs/guides/*.json`, same shape,
  `content::docs_routes()` already reads this dir too).
- **JSON-LD:** every docs page uses `DocsJsonLd.astro`, not the plain `<JsonLd schema={organizationJsonLd}>`
  every other checked route uses - it emits **two** nodes: `organizationJsonLd` (already checkable,
  `head::has_organization_schema()`) **plus** a `TechArticle` node
  (`jsonld.ts`'s `techArticleSchema({title, description, url, brand})` = `{"@context":..., "@type":
  "TechArticle", headline: stripBrandSuffix(title, brand), description, url}}`). `stripBrandSuffix`
  is an 8-line pure function (strips a trailing `" · {brand}"`/`" | {brand}"`), trivial to port.
- **What site-rs would need:** (1) `{brand}`-substituting loaders for `docs/index.json` (two title/
  description pairs: overview + the nested `apiPage`), `docs/changelog.json`, and per-file loaders for
  `docs/quickstarts/*.json`/`docs/guides/*.json` (already have the file list from `docs_routes()`,
  just not their `meta.title`/`description` yet - same 3-line JSON shape as every other checked
  route); (2) `stripBrandSuffix()` + `techArticleSchema()` ports (small, pure functions, ~15 lines
  together) for the JSON-LD check.
- **Effort:** small-to-medium. No new *kind* of complexity - same `{meta: {title, description}}`
  shape as every route already checked, same "always noindex=false, locale=en" simplicity as
  `/law-tracker/`. The only new work is the `TechArticle` JSON-LD variant and one nested-key title
  source (`apiPage`). Realistic estimate: half the effort of the entire `head_parity.rs` batch already
  landed (18 routes), since 5 of these 6 "routes" (`quickstart` × 4 slugs, `[guide]` × 2 slugs today)
  share the exact same shape as each other.
- **Blocker:** none technical. `docs/api.astro`'s own head fields (`overview.apiPage`) are simple, but
  its *body* is generated from `openapi/v1.yaml` (~650 operations) - out of scope for a head-only
  check anyway, so this doesn't block the head-parity work, only a future byte-diff port of that page.

## `/playground/` and `/interface/`

- **Head fields:** `title`/`description` from `content.pages.playground` /
  `content.pages.interface` - **same file shape and same loading mechanism** as `/platform/` etc.
  already checked (`packages/content/content/pages/{playground,interface}.json`). `noindex`: neither
  page passes the prop, so always `false`. `locale`: always `en` (no prop, and neither is a `/no/`
  route). This part is genuinely as easy as any already-checked generic page.
- **JSON-LD:** both build `[organizationJsonLd, datasetNode?, webAppNode]` where `webAppNode =
  webApplicationSchema({title, url, brand, isBasedOnUrl})` (`jsonld.ts`: `{"@context":...,
  "@type": "WebApplication", name: stripBrandSuffix(title, brand), url, applicationCategory:
  "EducationalApplication", isBasedOn: isBasedOnUrl}` - `description` is *omitted* on these two
  pages specifically, per `jsonld.ts`'s comment, "when the page's own meta/og description already
  says the same thing"). `datasetNode` is conditional: built via `datasetSchema()` from
  `parseDatasetCitation()`'s parse of the dataset's citation string (in
  `apps/web/src/assets/playground/mc-rtt-playground.json`, a large data asset, not simple content
  JSON) - `null` if the citation string doesn't match the expected format, in which case the page
  renders only `[organizationJsonLd, webAppNode]`.
- **What site-rs would need:** the two `pages/{playground,interface}.json` loaders (trivial, same
  shape); `webApplicationSchema()` + `stripBrandSuffix()` ports for the `WebApplication` node (~10
  lines beyond what `/docs/*` already needs); to *fully* verify JSON-LD, also `datasetSchema()` +
  `parseDatasetCitation()` (a regex parse of one citation string) and a loader for the relevant field
  of `mc-rtt-playground.json`. That data asset is large (not committed content-JSON-style data); a
  minimal loader that reads only the one citation string it needs is enough, no need to load the full
  dataset.
- **Effort:** small for title/description/robots/og (same as any generic page); small-medium for the
  `WebApplication` node; medium for the conditional `Dataset` node specifically, because of the extra
  citation-parsing step and the large asset file. A pragmatic first pass (matching how `/gallery/` and
  the research whitepaper page were scoped in the landed batch): check title/description/canonical/
  robots/og *and* the `Organization` node, explicitly skip the `Dataset`/`WebApplication` nodes for
  now with the same reasoning already established for those two routes.
- **Blocker:** none technical.

## `/investors/`

- **Head fields:** `title`/`description` from `content.pages.investors`
  (`packages/content/content/pages/investors.json`) - same shape as every generic page. `noindex`:
  **always `true`** (`<Base ... noindex>`, unconditional, per the route comment "draft investor page
  (noindex, not in the sitemaps, not linked from / or the nav)"). `locale`: `en` (no prop).
- **JSON-LD:** none - `investors.astro` has no `<JsonLd>` call at all (confirmed by source; same as
  `/gallery/` and the legal pages already in the skip-JSON-LD-only bucket).
- **What site-rs would need:** one more `pages/{key}.json` loader (same shape, same code path as
  `platform`/`governance`/etc. - could literally reuse the same generic-page loading function once one
  exists) plus a hardcoded `noindex: true`.
- **Effort:** trivial - this is the easiest route on this whole list, arguably easier than several
  routes already checked (no locale variant, no draft-flag lookup, no JSON-LD to verify at all).
- **Blocker:** none. This is a strong candidate for the *next* route added, not a genuinely hard case.

## `/no/<page>/` (`platform`, `governance`, `sdks`, `pricing` - Norwegian)

- **Head fields:** `title`/`description` from `getContent('no').innerPages[key].meta`, i.e.
  `packages/content/content/pages/{key}.no.json`'s `meta` - same shape as the `.en.json` files
  already checked (the security/legal `.no.json` routes prove this crate already handles the
  no-locale/`{brand}` case fine). `noindex = !reviewed`, where `reviewed` is a new boolean field on
  each `.no.json` file (`@nf/content`'s `INNER_PAGE_KEYS` = exactly
  `['platform','governance','sdks','pricing']`, same 4 keys `content::GENERIC_PAGE_KEYS` already has).
  Checked today: all four `.no.json` files have `"reviewed": false`, so all four routes are currently
  noindex. `locale`: always `no`.
- **JSON-LD:** none - `no/[page].astro` has no `<JsonLd>` call (same situation as `/investors/`).
- **What site-rs would need:** a loader reading `meta.title`/`description` **and** `reviewed` from
  `pages/{key}.no.json` (one extra field beyond what the `.en.json` loader needs, trivial); no new
  content-file *kind*, just one more boolean lookup on a file whose shape this crate already parses
  for the `.en.json` counterpart.
- **Effort:** trivial-to-small, similar to `/no/security/`/`/no/legal/*` already checked. The one
  genuinely new piece of logic is reading a `reviewed` flag from a JSON file and using it as
  `noindex`'s value - a two-line addition once a generic "read this JSON key" helper exists.
- **Blocker:** none technical. Worth noting for whoever eventually reviews Norwegian copy: once a
  `reviewed` flag flips to `true` for a given page, this route's expected `noindex` value (and
  therefore its expected `<meta name="robots">` presence) changes - the head-parity check would need
  re-running against a fresh dist at that point, same as any other content change, not a new problem.

## `/arena/`

- **Head fields:** `title`/`description` are **hardcoded literals inside `arena/index.astro` itself**
  (`{ title: 'Decoder Arena', description: '...' }`), not loaded from any content JSON - the one route
  on this list (and arguably in the whole site) whose head metadata isn't content-file-driven at all.
  Trivial to hardcode on the site-rs side too, if ported. `noindex = !wasmAvailable`, where
  `wasmAvailable = arenaPkgAvailable()` (`apps/web/src/lib/arena-pkg.mjs`) is a **build-time filesystem
  check**: `existsSync('apps/web/src/assets/arena/pkg/arena_core.js') &&
  existsSync('.../arena_core_bg.wasm')`. That directory is a CI-built artifact, "never committed here
  in the normal case" per the route's own comment - so in every local/dev build (and presumably most
  CI runs before the artifact is published), `wasmAvailable` is `false` and the page is `noindex`.
  `locale`: `en` (no prop).
- **JSON-LD:** none - `arena/index.astro` has no `<JsonLd>` call.
- **What site-rs would need:** the two literal strings (copy-paste, no loader needed) plus a port of
  `arenaPkgAvailable()`'s two-file existence check (trivial - `std::path::Path::exists()` twice)
  against `apps/web/src/assets/arena/pkg/`.
- **Effort:** trivial for the values themselves; the interesting part is state-dependence, not
  complexity - **this route's expected `noindex` value depends on which dist you're checking against**
  (whether that specific build's `arena/pkg/` artifact was present). A head-parity check for this route
  would need to read the *actual* built dist's own robots-meta presence as ground truth for whether
  the artifact was there (mirroring how `tests/parity.rs`'s headers tests already read `stage`/`host`
  back out of the dist's own `_headers.json` rather than assuming a fixed value) - it can't assume
  `wasmAvailable == false` and hardcode `noindex: true`, because that would silently pass even once the
  real artifact ships and the page should start being indexed.
- **Blocker:** the state-dependence above is a real design consideration, not a missing feature - it's
  the same pattern already solved for `robots.txt`/`_headers`' `stage`, just applied to one page's
  `noindex`. Not a reason to delay porting this route, just a reason its expected-value computation
  needs to read the dist rather than being purely computed from source, unlike every other route on
  this list.

## Summary (rough ordering by effort, cheapest first)

1. `/investors/` - trivial, no new content-file shape, no JSON-LD.
2. `/no/<page>/` × 4 - trivial-to-small, one extra boolean field on an already-handled file shape.
3. `/arena/` - trivial for the literal head values; the `noindex` state-dependence needs the same
   "read it back out of the dist" pattern already used elsewhere, not new capability.
4. `/playground/`, `/interface/` - small for title/description/robots/og/Organization (same as any
   generic page); medium if the `Dataset`/`WebApplication` JSON-LD nodes are also wanted (can be
   scoped out initially, same as `/gallery/` and the research whitepaper page already are).
5. `/docs/*` - small-to-medium, mostly repetitive work across `quickstart`/`guide` slugs once the
   `TechArticle` JSON-LD variant and `docs/index.json`'s nested `apiPage` key are handled once.

None of the six route groups has a hard technical blocker to head-parity coverage specifically (as
opposed to full byte-diff page ports, which are a separate, larger effort per PLAN.md). The only
route whose *design* (not effort) differs from what's already landed is `/arena/`, because its
`noindex` depends on build-time artifact presence rather than being computable from source alone.

## Measured: site-rs's render cost today

Web-queen ask: wall time and peak RSS for `site-rs` rendering the pages it currently covers, vs the
Astro build of those themes - **measured, not estimated**. All numbers below are from this session
(`tools/site-rs/tests/render_bench.rs`, `hive-peakmem`/`hive-freeram`, `cargo build --release -p
site-rs`), each measurement run 3x with the median reported, **measured on a shared dev PC** (other
work running concurrently: lane A had `swarm2 rs-a`; lane C was idle; `hive-freeram` read 5.72/15.59
GiB free before, 5.50/15.59 GiB after).

This branch only has `main.rs`'s current output to measure: `robots.txt` + `sitemap.xml` generation
(no HTML page rendering here yet - `not_found::render()` for `/404/` has since merged to main via
`feature/site-rs-pages`, but isn't in `render_bench.rs` yet; this section still needs extending, as
web-queen asked).

**2026-09-27 fixup, numbers unchanged:** `robots_txt()` gained a `Stage` parameter when APP-L8
merged to main; `render_bench.rs` now passes `Stage::Public` explicitly to keep exercising the same
full-generation code path these numbers describe (a non-indexable stage short-circuits to a few fixed
lines, which would measure something else entirely). Same code path, same inputs - no re-run needed.

**`cargo build --release -p site-rs`** (first release build, compiling `serde`/`serde_json`/`regex`
and their dependency tree from scratch): 10.3 s wall, 1,105 MB peak job commit.

**Release binary, whole process** (`site-rs.exe <repo-root> <theme> <out-dir>`, writing both files -
includes process startup, not just the generation work):

| Theme | Wall time (median of 3) | Peak commit |
|---|---|---|
| clinical | 0.010 s | < 1 MB |
| cosmos | 0.009 s | < 1 MB |

**Pure in-process computation** (`render_bench.rs`: 10,000 iterations of `robots_txt()` +
`sitemap_xml()` per theme, timed with `std::time::Instant`, isolating the actual generation work from
process startup):

| Theme | Median time per iteration (of 3 runs) |
|---|---|
| clinical | 4.185 µs |
| cosmos | 4.401 µs |

**Reading:** the whole-process wall time (~9-10 ms) is almost entirely process startup and the two
file writes, not the generation logic itself - the pure-computation number (~4-4.4 µs/iteration, over
2,000x smaller) is the more representative figure for "cost per page rendered" if this were wired into
a loop generating many pages. Both are close to the noise floor of this measurement method (sub-
millisecond binary startup, microsecond-scale string building) - real signal, but small enough that
CPU contention from other lanes plausibly explains run-to-run variance (e.g. clinical's first binary
run at 0.102 s vs 0.010/0.009 s for runs 2-3, almost certainly a one-time disk-cache/binary-load cost,
not sustained per-run cost).

**Astro reference (measured by others, cited with source, not this crate's own measurement):**
web-headers' lane-B run of both theme builds - 9.3 s wall, 922 MB peak (`WEB-BOARD.md`, 2026-09-27,
`web/headers 994f8bc`); nfb-playground's per-theme stills run, both builds within a 49 s job. This
crate doesn't run `astro build` itself (team-lead's ruling for this worktree: division of labour with
web-queen's site-build role, not a tool ban - the node/python ban itself was lifted 2026-09-27).

**This is not a like-for-like comparison.** Astro's build renders all 37 pages of the site (every
route, full HTML/CSS/JS bundling, image processing, the whole `dist/<theme>` tree); `site-rs` today
renders 2 text files (`robots.txt`, `sitemap.xml`). The numbers above answer "how much does each tool
cost to run right now", not "how much faster would a full site-rs be than Astro" - that question has
no honest answer yet, because site-rs doesn't do the other 35 pages' work. A meaningful per-page-
rendering comparison would need `not_found::render()`'s cost (once merged) and, eventually, a much
larger fraction of the site ported before the two numbers describe the same amount of work.
