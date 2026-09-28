# @nf/content

All website copy, the brand token and the typed loader. Owner: nfb-copywriter (`docs/hive/CONTRACTS.md` §1, §3.4).

**Owner copy review: pending.** (BUILD-GUIDE step 1.2 acceptance: the owner reviews the copy before release.)

## Files

```
brand.json                         the ONLY place the company name and code identifiers are written
content/site.json                  English site chrome: nav items, footer copy, aria labels, banners, early-access
                                   form, 404, figure UI, gallery
content/ui.<en|no>.json            localised chrome: status labels, skip link, menu labels, language switch, legal footer
content/security.<en|no>.json      /security (SEC-158), from docs/inputs/security/website-security-page.md
content/legal/<page>.<en|no>.json  privacy, terms, cookies: GENERATED from docs/inputs/legal-website (nfb-legal drafts)
content/home.json                  hero, formats, pipeline (4 steps + code), governance, audience tabs, compliance grid,
                                   pricing teaser, research cards, CTA
content/pages/*.json               platform, governance, sdks, pricing, law-tracker, research (index)
scripts/import-legal.mjs           legal drafts (Markdown) -> content/legal/*.json (then run Prettier on content/legal)
content/research/<slug>.json       whitepaper page copy (intro, abstract placeholder, questions, figure captions)
src/types.ts                       hand-written types (source of truth for consumers)
src/schema.ts                      zero-dependency runtime schema mirroring types.ts
src/validate.ts                    validator, placeholder substitution, string walker
src/index.ts                       loader: validates, substitutes, exports typed content
test/content.test.mjs              node:test suite (see "Tests")
```

## API

```ts
import { content, brand, loadContent, type Content } from '@nf/content';
content.home.hero.heading; // "The data layer for <em>brain-computer interfaces.</em>"
content.pages.lawTracker.groups; // rows with source, sourceUrl?, grade?, verified
content.whitepapers['somatosensory-closed-loop'];
brand.origin; // https://<domain>; placeholder host while brand.domainIsPlaceholder
loadContent({ brand: { name: 'Other' } }); // tests only: proves a rename flows everywhere
getContent('en'); // the full site plus { locale, ui, security, legal, innerPages }
getContent('no'); // { brand, locale, ui, security, legal, innerPages }: no homepage copy in Norwegian
```

## Languages (EN + NO bokmål)

- English is the default at `/`; Norwegian bokmål lives under `/no/` with `<html lang="nb">` (BCP 47) and hreflang
  `en` / `nb` / `x-default`. The file suffix and URL segment are `no`.
- Norwegian exists for `/security`, the legal pages and the inner pages platform, governance, sdks and pricing
  (`content/pages/<page>.no.json`, exposed as `innerPages`; lead decision 2026-09-27). The inner-page texts are
  drafts pending the owner's language review. The homepage and other pages are not translated and have no `/no/`
  route; Norwegian pages keep the English nav/footer, marked `lang="en"`.
- Every `*.no.json` has exactly the keys of its EN counterpart (test). NO inner pages also keep EN's statuses,
  build states, sources, grades, links and code lines, and the same evidence per section (test); the only extra key
  is `pricing.earlyAccessNote`, which replaces the English-only early-access form, plus `reviewed` on every NO inner
  page: until the owner sets it to true, `publishedInnerPages('no')` leaves the page out, so it gets no route in
  LOCALISED_ROUTES, no hreflang or language switch, no sitemap entry, and noindex if built. Status labels: Designet / Planlagt /
  Veikart. The short NO UI strings in `ui.no.json` (skip link, menu, "Språk", `securityVisual`, "Under arbeid") were
  written by nfb-web-sec and need owner review; the security copy is nfb-security's, the legal text nfb-legal's.
- Security and legal strings may carry inline markup (`**bold**`, `*em*`, backtick code, `[text](href)`); apps/web
  renders it with an escaping inline renderer (`apps/web/src/lib/inline.ts`), never as raw HTML.
- Legal pages are generated: nfb-legal edits the drafts in the main checkout, they are re-copied into
  `docs/inputs/legal-website`, then run `node packages/content/scripts/import-legal.mjs`. A test fails when the JSON is
  stale. The company name becomes `{brand}` and the drafts' placeholder domain `{domain}`. `draft: true` means DRAFT
  banner, noindex and no sitemap entry.

- Synchronous, no fs reads. JSON is imported with `with { type: "json" }`. The package entry is erasable TypeScript
  with `.ts` import extensions (consumers need `allowImportingTsExtensions`, which Astro's base tsconfig sets).
- `loadContent()` throws `ContentError` on any schema error or leftover placeholder.

## Conventions

- **Placeholders** in copy: `{brand}`, `{legalName}`, `{domain}`, `{origin}`, `{pkg}` (Python import name). The loader
  substitutes them from `brand.json`. Never type the company name or the code identifier anywhere else under
  `packages/`, `apps/` or `openapi/`; the brand-token test scans for it (case-insensitive).
- **Headings** (`Rich`) may contain `<em>…</em>` and nothing else; themes paint `<em>` via `--emphasis-paint`.
  All other strings are plain text. One heading set for both themes (DECISIONS D8; no voice overrides).
- **Status** is one of `designed | planned | roadmap | in-preparation`; display text is in `site.statusLabels`.
- **Claims.** Every factual statement is an object with `text` and `source` (`market/<file>.md §N` or a
  `research/...` path), plus optional `sourceUrl` (must appear in those docs) and `grade` (as given there).
  Product plans are not claims; they carry a `status`.
- **CTAs** with `disabled: true` render as disabled buttons with their `note` (early access until BUILD-GUIDE 4.7).
  A `Link` with `status` points at something that does not exist yet (Docs): render text plus a status pill.
- `brand.json` placeholders: no domain is registered (`.invalid` host, `domainIsPlaceholder: true`) and no legal entity
  exists (`legalNameIsPlaceholder: true`). Code identifiers are `fixed: false` until the name clash check is clean.

## Tests

```sh
node --experimental-strip-types --no-warnings --test "packages/content/test/*.test.mjs"
```

Covers: schema validation (plus a validator self-test); every claim has a `source` that exists (file and § heading);
every `sourceUrl` appears in `market/` or `research/`; digits outside claims are flagged; binding copy fixes from
BLUEPRINT §2.6 and DECISIONS D1 verbatim; compliance wording from CONTENT-SPEC; banned-term backup check; research
statuses and IRB/FDA banner; law-tracker rows sourced with unverified rows flagged; early-access form disabled;
brand-token scan of `packages/`, `apps/`, `openapi/`; a changed brand flowing through the loader; and
`node tools/copy-lint/cli.mjs packages/content` (skipped with a message if the CLI is absent).
