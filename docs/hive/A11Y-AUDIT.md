# WCAG 2.2 AA audit — inner pages, both themes

Agent: web-a11y. Scope per WEB-PLAN: every inner page (not `/`), both themes (clinical, cosmos).
Method: no axe run was needed to *find* these — `@axe-core/playwright` is already wired in
`apps/web/e2e/a11y.spec.ts` (web-e2e's lane, CI-only) and a static check already runs locally in
`apps/web/test/html.test.mjs` (unique ids, dangling ARIA refs, one `<h1>`/`<main>`, `lang`, `alt`).
This audit is a manual read of every inner-page component, its content-driven markup, and the
shared `@nf/ui` / `@nf/themes` / `@nf/figures` packages they render through, checking: heading
order, landmarks, alt text, colour contrast (from the theme tokens), keyboard focus order and
visible focus, reduced motion, and form labels.

Pages covered: `/platform` `/governance` `/sdks` `/pricing` (generic, `[page].astro`), `/security`
(+ `/no/security`), `/legal/*` (+ `/no/legal/*`), `/docs` `/docs/api` `/docs/changelog`
`/docs/quickstart/*`, `/research` `/research/[slug]`, `/law-tracker`, `/gallery`, `/404`,
`/playground`, `/interface` (the last two merged into `web/a11y` from `origin/main` mid-audit;
spot-checked, see "Playground / Interface" below). `/` is out of scope per rule 1.

## Summary

| # | Issue | Page(s) | Criterion | Severity | Status |
|---|---|---|---|---|---|
| 1 | Last section ("open questions") had no `<h2>`; its `aria-labelledby` pointed at an unrelated paragraph (a note about how the rules table is generated), which also doubled as the `<ul>`'s label | `/law-tracker` | 1.3.1 Info and Relationships; 2.4.6 Headings and Labels | Moderate | **Fixed (Handoff B, `web/a11y-handoff-b` 2bb50ee)** |
| 2 | Statutory-definition `<blockquote>` labelled only via `title=` — never visible to sighted keyboard/touch users, hover-only | `/law-tracker` | 1.3.1 Info and Relationships | Low | **Fixed, merged to main** — landed via `web/a11y-law-tracker` (f8058ac), now on `origin/main` |
| 3 | API response-code descriptions (e.g. "text/event-stream of run.state events…") available only via `title=` hover | `/docs/api` | 1.3.1 Info and Relationships | Low | **Fixed, merged to main** — see "Handoff A, revised" below; a visible legend restores all 648 descriptions for everyone, not just under budget |
| 4 | Whitepaper's scrollable, keyboard-focusable BibTeX `<pre tabindex="0">` had no `aria-label`, unlike every other focusable code/table region in the codebase | `/research/[slug]` | 4.1.2 Name, Role, Value; 2.4.6 | Low | **Fixed (Handoff B, `web/a11y-handoff-b` 2bb50ee)** |
| 5 | `ComplianceGrid.astro`'s mobile layout hides `<thead>` with `display: none`, removing column headers from the accessibility tree (row headers via `scope="row"` still work); `/law-tracker`'s own table solves the identical problem correctly with a visually-hidden clip instead | `/security` (and any generic page using compliance tables) | 1.3.1 Info and Relationships | Moderate | **Reported, not fixed** — frozen (also renders on `/`); escalated to web-queen → lead |

Detail on each below. #2 and #3 (Handoff A) merged to `origin/main` already. #1 and #4 (Handoff B)
are fixed on `web/a11y-handoff-b` (sha `2bb50ee`), branched from `origin/main` once web-a11y held
the `packages/content/src` schema turn (web-papers → web-copy → web-a11y); the new label for #4
went in `ui.en.json`/`ui.no.json`, not `site.json` (a frozen homepage source, checked verbatim by
`homepage.test.mjs`). Only #5 remains open, blocked on a decision about the frozen component.

### Handoff A, revised — `/docs/api` response descriptions

The first version of fix #3 added a `.nf-visually-hidden` description span to every one of this
page's ~648 responses. web-queen's integration run of that (`0738d40`) tripped the `/docs/api`
perf budget in both themes (`htmlRaw 235881 > 235234`): 643 of those 648 descriptions are the same
7 strings repeated verbatim across nearly every operation (401/403/404/422/429/500, the default
error, and "Successful Response"). Went through three revisions before landing on the right one —
web-perf and I initially converged on cutting the repeats for size, but web-queen and the lead
correctly called that out: dropping information to hit a budget is backwards, and the 7 repeated
descriptions used to reach *nobody* reliably (hover-only `title=`), so simply deleting them made
sighted users worse off than before, not better.

Final design (`ad65b9f`):
1. (`c2c2658`) stopped repeating a description inline when it's identical to more than one
   response's — no information lost yet, just not yet re-homed.
2. (`9fcda97`, web-perf's catch) the wrapping `<span>` around each status code held `title=` before;
   once that's gone it carries no attributes and does nothing, so it's dropped.
3. (`ad65b9f`, web-queen's plan) added a visible `<dl>` legend — "Common response codes" — near the
   top of the Operations section, listing each of the 7 repeated descriptions once against every
   status code that uses it (derived at render time from `api-reference.json`, so it can't drift
   from the generated OpenAPI spec). The label lives in `apps/web/src/docs/index.json` (this page's
   own local doc-copy file, *not* `packages/content` — no schema-queue touch needed). Per-response
   hidden text stays only for the 5 descriptions unique to one response.

Net effect: every user — sighted, keyboard-only, screen-reader — now gets the same information the
old `title=` gave sighted mouse users (when it worked at all), just once instead of on every one of
~650 responses. Bytes, for reference: the legend adds ~650 B (once), the 5 unique per-response spans
~2 KB, both far under budget and nowhere near what triggered the original trip. I couldn't re-run
the built-dist `perf-budget.test.mjs` myself (needs a build slot); web-perf is verifying in their
next slot. Final SHA: `ad65b9f`.

## Overall finding

The codebase is already unusually careful about accessibility: `packages/themes/test/contrast.test.mjs`
computes real WCAG contrast ratios (composited over their backdrops) for every token pair in both
themes and passes; `packages/ui/test/keyboard.test.mjs` unit-tests the tabs/menu key logic;
`packages/ui/src/styles/base.css` has a global `prefers-reduced-motion` override, a real
`:focus-visible` style, and a working skip link; every animated cosmos slot (`HeroVisual` three.js
brain, `SecurityVisual` orbit rings, `SectionOrnament`) already gates motion on
`prefers-reduced-motion`, `Save-Data` and low device memory, and the three.js hero has a full SVG
fallback. Status is never colour-only (`StatusPill` always renders a text label). Interactive
figures (`@nf/figures/FigureIsland`) ship a server-rendered accessible data table, an `aria-live`
readout and full keyboard support, working with JS off.

Given that, this audit found few defects. They're listed by severity below, split into what's
fixed now (Handoff A: page-local files, no schema change), what's deferred (Handoff B: needs a
content field, and the `packages/content/src` schema is currently held by web-papers in a queue —
web-papers → web-copy → web-investor → web-a11y), and what's reported because the fix would touch a
file the homepage also renders through (rule 1/2: shared component, needs web-queen).

## Fixed — Handoff B (`web/a11y-handoff-b`, sha `2bb50ee`)

Landed once web-a11y held the `packages/content/src` schema turn (web-papers → web-copy → web-a11y).

### Moderate — `/law-tracker`: "Open questions" section had no heading
`apps/web/src/pages/law-tracker.astro` rendered the page's last section with
`aria-labelledby="h-open"` pointing at `<p class="srcnote" id="h-open">{lt.sourceNote}</p>` — a
paragraph of copy about *how the rules table is generated*, not a heading, and it also served as
the accessible name for the `<ul>` of open items. Every other section on the page has a real
`<h2>`; this one didn't, so a screen-reader user navigating by heading landed on nothing here, and
the announced "heading" for the section was unrelated boilerplate text. Fixed: added an
`openHeading` field ("Open questions") to `LawTracker` content (`packages/content/src/schema.ts`,
`packages/content/src/types.ts`, `packages/content/content/pages/law-tracker.json`) and rendered a
real `<h2 id="h-open">`; the source note stays a plain paragraph after the list, no longer
double-booked as a label.

### Low — whitepaper BibTeX citation block had no accessible name
`apps/web/src/pages/research/[slug].astro`'s citation footer rendered `<pre class="bib" tabindex="0">`
— a scrollable, keyboard-focusable region — with no `aria-label`, unlike every other such region in
the codebase (`PageBody.astro`'s code sample, `PipelineSteps`' code block, `DocSections`' code
blocks, and the API parameter/schema tables in `docs/api.astro` all name theirs). A screen-reader
user tabbing to it got an unlabelled focusable region. Fixed: added a `citation` label ("BibTeX
citation" / NO "BibTeX-referanse") to `ui.en.json`/`ui.no.json` (not `site.json` — that's a frozen
homepage source checked verbatim by `homepage.test.mjs`) and passed it as `aria-label` via `uiEn`.
Norwegian translation added too even though `/research` is English-only, to satisfy the i18n
key-parity test (`ui.no.json` must have the same keys as `ui.en.json`).

`content.test.mjs`: 26/27 locally (the 1 failure, `buildSource is not rendered on pages`, needs a
built `dist/` and is unrelated to this change — schema validation and i18n key-parity both pass).
Requested a bci-queen slot for the full build + `apps/web/test/*.test.mjs` before handoff to
web-queen.

## Fixed — Handoff A (this push, no schema/`site.json` change)

### Low — title-attribute-only supplementary text (2 spots)
- `apps/web/src/pages/law-tracker.astro`: `<blockquote class="def" title={rs.definitionLabel}>`
  labelled the statutory-definition quote only via `title`, which sighted keyboard/touch users
  never see (mouse-hover only). Replaced with a `.nf-visually-hidden` "Definition: " prefix so the
  label is in the accessible name for everyone, not just mouse users.
- `apps/web/src/pages/docs/api.astro`: `<span title={r.description}>{r.status}</span>` on API
  response codes had the same problem (e.g. "200" with a hover-only description like "text/event-stream
  of run.state events…"). Replaced with visible text + a `.nf-visually-hidden` parenthetical, so the
  description reaches screen readers and stays available (as hidden text) for everyone else who
  can't hover.

Both fixes use the existing `.nf-visually-hidden` utility from `packages/ui/src/styles/base.css`
(already imported globally via `Base.astro`), so no new CSS was needed.

## Reported, not fixed — shared component also used by the homepage

### Moderate — `ComplianceGrid` mobile layout removes column headers from assistive tech
`packages/ui/src/components/ComplianceGrid.astro` (used on `/security`, and available to
`/platform`/`/governance`/`/sdks`/`/pricing` via the generic page renderer) hides `<thead>` on
narrow viewports with `display: none`:
```css
@media (max-width: 640px) { thead { display: none; } ... }
```
`display: none` removes the column headers from the accessibility tree, not just visually, so a
screen-reader user on a narrow viewport loses the header association those `<th scope="col">`
cells provide (row headers via `scope="row"` still work). The bespoke table on `/law-tracker`
solves the same problem correctly with the standard visually-hidden clip technique
(`position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0)` — see
`law-tracker.astro`'s `.rules thead` rule), which keeps the headers in the accessibility tree while
hiding them visually.

`ComplianceGrid.astro` is also rendered on `/` (`apps/web/src/pages/index.astro` imports it
directly for the compliance section), so under rule 1 changing its CSS would change built `/` and
I'm not fixing it myself. Recommended fix (for whoever web-queen assigns it): swap the mobile
`thead { display: none }` for the clip-based visually-hidden pattern already proven on
`/law-tracker`. I'll take this if assigned.

## Checked, no action needed

- **Heading order**: every inner page follows h1 → h2 (per section) → h3 (per item/step), with no
  skips. `SectionHead` defaults to h2 and takes `level={1}` only for the page's own hero, so there's
  never a duplicate h1 on a content page. (`/gallery`'s two `<h1>`s — the page wrapper's and the
  `Hero` demo's — are deliberate and already exempted by name in `apps/web/test/html.test.mjs`;
  it's an internal, `noindex` component showcase, not a real content page.)
- **Landmarks**: `Base.astro` gives every page one `<header>`/nav, one `<main id="main" tabindex="-1">`,
  one `<footer>`; the primary nav, footer nav and language switch are each a `<nav>` with a distinct
  `aria-label`, so multiple nav landmarks are always distinguishable.
- **Alt text**: `Figure`/`FigureIsland` figures use `role="group"`/`role="img"` with `aria-label` and
  a server-rendered data table (no naked `<img>` in figure content); the one raster `<img>`
  (`/interface`'s WebGL fallback still) has a real `alt`. `apps/web/test/html.test.mjs` already
  fails the build on any `<img>` without `alt`.
- **Colour contrast**: `packages/themes/test/contrast.test.mjs` checks every text/background token
  pair (ink, muted, accent-ink, emphasis-paint gradient stops per stop, on-accent button fills,
  status pills over every backdrop) and every non-text UI colour (focus ring, accent marks) against
  WCAG AA (4.5:1 text, 3:1 UI) in both themes, composited correctly for cosmos's translucent glass
  surfaces. 28 pairs (clinical) / 34 pairs (cosmos), all passing.
- **Keyboard focus order / visible focus**: global `:focus-visible` outline in `base.css`; the mobile
  menu, `AudienceTabs` tablist and `FigureIsland` keyboard readout all have unit- or hand-verified
  key handling (arrow/Home/End, Escape, roving tabindex); scrollable code/table regions
  (`<pre tabindex="0">`, `.scroll`/`.tbl` wrappers) are keyboard-reachable per WCAG 2.1.1.
- **Reduced motion**: global `prefers-reduced-motion: reduce` override kills all transitions/animations
  in `base.css`; the cosmos `HeroVisual` (three.js) checks `matchMedia('(prefers-reduced-motion: reduce)')`
  before ever loading three.js and stops/repaints statically on a live media-query change;
  `SecurityVisual` and `SectionOrnament` stop their CSS `@keyframes` the same way. `/interface`
  (new, from `origin/main`) goes further and shows an explicit "reduced motion is on — show anyway"
  opt-in rather than silently animating.
- **Form labels**: `EarlyAccessForm`'s email input has a real `<label for>`; the disabled `<fieldset>`
  is described via `aria-describedby`. `/playground` and `/interface` (new) give every control
  (range, select, checkbox, radio group) a `<label>`/`<legend>`, keep them `disabled` until the
  enhancement script attaches real behaviour (so nothing looks interactive to AT before it is), and
  visually-hide their otherwise-redundant `<h2>` form headings rather than omitting them.
- **Docs pages** (`/docs/*`): consistent h1→h2→h3, `<details>`/`<summary>` for schemas (native
  disclosure, no custom JS needed), scrollable parameter tables wrapped in
  `role="region" aria-label="…"` with `tabindex="0"`.
- **Legal / security pages**: markdown-lite renderer (`apps/web/src/lib/inline.ts`) only emits
  `<code>`, `<a>`, `<strong>`, `<em>`, `<br>` — no raw HTML injection surface, external links always
  get `rel="noopener noreferrer"`.

## Playground / Interface (new pages, merged from `origin/main` mid-audit)

`/playground` and `/interface` landed in `origin/main` while this audit was in progress (owner:
nfb-playground). Spot-checked both against the same checklist: heading order is correct, canvases
are `role="img"` with `aria-label`, legends distinguish series by shape/dash pattern as well as
colour, controls are labelled and start `disabled` until JS enhances them, and `/interface` already
ships an explicit reduced-motion opt-in. No defects found; not deep-audited to the same depth as the
rest given they're outside this pass's original scope and actively owned elsewhere — flagging to
web-queen in case a follow-up pass is wanted once they stabilize.

## Files changed
- Merged to `origin/main` (Handoff A): `apps/web/src/pages/docs/api.astro` (#3: the `isDistinctive`
  filter, the dropped wrapper span, and the visible legend), `apps/web/src/docs/index.json` (one new
  label, `apiPage.commonResponses` — a separate, unvalidated local file this page already reads its
  copy from, not part of the `packages/content` schema/queue), and `apps/web/src/pages/law-tracker.astro`
  (#2: the blockquote label, merged via `web/a11y-law-tracker` f8058ac).
- `web/a11y-handoff-b` (sha `2bb50ee`, not yet merged): `apps/web/src/pages/law-tracker.astro` (#1:
  the missing `<h2>`), `apps/web/src/pages/research/[slug].astro` (#4: the citation `aria-label`),
  `packages/content/content/pages/law-tracker.json` (`openHeading`), `packages/content/content/ui.en.json`
  and `ui.no.json` (`citation`), `packages/content/src/schema.ts` and `types.ts` (both new fields).
