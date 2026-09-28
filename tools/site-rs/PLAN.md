# site-rs: Rust static-site generator plan

Goal (ORG-PLAN.md, RUST-POLICY.md): reproduce `apps/web`'s Astro build output without running
node. Staged port; Python/Astro stay on main as reference until parity is proven; nothing is
deleted until the lead merges.

## Stage 1: inventory

### Routes / pages (`apps/web/src/pages`, main branch)

| Route(s) | Source | Kind | Notes |
|---|---|---|---|
| `/` | `pages/index.astro` | content + 1 hydrated island (`HeroVisual`) | homepage; NEVER edit its source content |
| `/platform/`, `/governance/`, `/sdks/`, `/pricing/` | `pages/[page].astro` + `content/pages/*.json` | pure content | generic content-page template |
| `/security/` | `pages/security.astro` | pure content | English |
| `/no/security/` | `pages/no/security.astro` | pure content | Norwegian |
| `/legal/{privacy,terms,cookies,company}/` | `pages/legal/[page].astro` + `content/legal/*.en.json` | pure content | all 4 are `draft:true` today -> noindex, excluded from sitemap |
| `/no/legal/{...}/` | `pages/no/legal/[page].astro` + `*.no.json` | pure content | same drafts |
| `/law-tracker/` | `pages/law-tracker.astro` | pure content (large, tabbed via `AudienceTabs` island) | `content/pages/law-tracker.json` |
| `/research/` | `pages/research/index.astro` | pure content | index of whitepapers |
| `/research/{slug}/` | `pages/research/[slug].astro` | pure content, ships `FigureIsland` script | one whitepaper today: `somatosensory-closed-loop` |
| `/research/files/{file}` | `pages/research/files/[file].ts` | static file passthrough | serves `p4_capacity_vs_M.svg` from figures manifest |
| `/gallery/` | `pages/gallery.astro` | interactive (renders every `@nf/ui` component) | noindex, not in sitemap |
| `/404` | `pages/404.astro` | pure content | noindex |
| `/docs/`, `/docs/api/`, `/docs/changelog/`, `/docs/quickstart/{slug}/` | `pages/docs/*.astro` | pure content | **present on main, absent from the m5 golden dist** (see Finding below) |
| `/robots.txt` | `pages/robots.txt.ts` | generated text | theme-aware (clinical: crawlable + Sitemap line; cosmos: crawlable, no sitemap) |
| `/sitemap.xml` | `pages/sitemap.xml.ts` | generated XML | `sitemapRoutes()` in `lib/site.ts` |

Shared chrome: `layouts/Base.astro` (head/meta/CSP-relevant tags, `Nav`, `Footer`, `LangSwitch` from
`@nf/ui`) wraps every page. Interactive browser JS (hydrated islands): `HeroVisual`, `FigureIsland`,
`AudienceTabs`, `Nav` (mobile menu). These are **copied as built assets, not re-templated** — the
generator emits the same `<script type="module" src="/_assets/...">` tags and copies the existing
`_assets/*.js` files verbatim, per the task brief.

### Content sources (`packages/content/`)

- `brand.json` — company name, `domain` (canonical host), `secondaryHost`. Read by `astro.config.mjs`
  for `canonicalOrigin` and by `robots.txt.ts`/`sitemap.xml.ts` indirectly via `CANONICAL_ORIGIN`.
- `content/site.json`, `content/ui.{en,no}.json` — site chrome strings, nav labels, status pill/labels.
- `content/home.json` — homepage copy (**do not edit**).
- `content/pages/{platform,governance,sdks,pricing,law-tracker}.json` — generic content pages.
- `content/legal/{privacy,terms,cookies,company}.{en,no}.json` — legal drafts (`draft: true` today).
- `content/security.{en,no}.json` — security page copy.
- `content/research/somatosensory-closed-loop.json` — the one whitepaper.
- `packages/content/src/{index,schema,types,validate}.ts` — the loader/validator; `index.ts` builds
  the `content` object (`site`, `home`, `pages`, `whitepapers`, `locales.{en,no}.legal`, `ui`) that
  `apps/web/src/lib/site.ts` re-exports pieces of.

### Build / CSP pipeline

- `apps/web/astro.config.mjs` — picks `THEME` (`clinical`|`cosmos`) via `@theme` alias, sets
  `outDir: dist/<theme>`, `build.assets: '_assets'`, `inlineStylesheets: 'never'`, defines
  `__NF_THEME__`/`__NF_CANONICAL_ORIGIN__`/`__NF_REPO_ROOT__` for the pages.
- `apps/web/scripts/build.mjs` — copy-lint content -> verify figure manifests -> `astro build` per
  theme -> `postbuild.mjs` -> copy-lint `dist/<theme>`.
- `apps/web/scripts/postbuild.mjs` + `apps/web/security-headers.mjs` — after the Astro build:
  1. writes `.well-known/security.txt` (SEC-157, fails on placeholders if `SITE_STAGE=public`);
  2. `inline-check.mjs`: fails if any inline `<script>`/`<style>`/handler isn't hashed into the CSP
     (build already sets `inlineStylesheets: 'never'` and bundles all scripts, so today this is a
     no-op assertion, not a transform);
  3. writes `_headers` (Netlify/Cloudflare text) and `_headers.json` from `headerRules()` — same
     CSP (`default-src 'none'; script-src 'self'; ...`) for both themes, `Cache-Control` immutable
     for `/_assets/*`, revalidate for everything else.
- The Rust generator must reproduce the **postbuild** outputs (`_headers`, `_headers.json`,
  `.well-known/security.txt`) as well as the HTML/XML/text pages — porting `security-headers.mjs`'s
  logic (already pure functions, no I/O) is mechanical and should be one of the first non-text pieces
  done, since every page's headers depend on it.

## Finding: the m5 golden dist does NOT match main (checked 2026-09-27)

Compared `origin/main` against the commit that produced
`neuro-worktrees/m5/apps/web/dist/{clinical,cosmos}` (m5 HEAD `71148ff`, a read-only review of
branch `chore/ci-site-hardening`, **not merged to main**). `site-rs` itself is branched from main and
its `apps/web`/`packages/content` are byte-identical to `origin/main` (`git diff origin/main..HEAD`
is empty there). The divergence is entirely on the m5/golden side:

1. **Docs section removed.** m5 deletes `pages/docs/*.astro`, `lib/docs.ts`, `docs/*.json`,
   `components/Doc{Sections,Shell}.astro` (~11k lines, mostly the generated `api-reference.json`).
   Main still has all of it. Golden dist has no `/docs/` folder at all; main's source would produce
   one (`/docs/`, `/docs/api/`, `/docs/changelog/`, `/docs/quickstart/{4 slugs}/`).
2. **New indexing/noindex layer (APP-L8), not on main.** m5 adds `apps/web/indexing.mjs` and changes
   `Base.astro` from `{noindex && <meta name="robots" content="noindex,nofollow" />}` to
   `{robots && <meta name="robots" content={robots} />}` where `robots = robotsMeta({stage, noindex})`.
   Confirmed by inspection: `dist/clinical/index.html` (homepage, `noindex` prop is *false* on main)
   **does** contain a `<meta name="robots" ...>` tag in the golden dist — main's current `Base.astro`
   would not emit one there. This one change means **every page** in the golden dist differs from
   what main's layout produces, independent of per-page content.
3. **`robots.txt.ts` was rewritten.** Golden `robots.txt` is
   `# SITE_STAGE=preview: preview builds are not for search engines.\nUser-agent: *\nDisallow: /`.
   Main's `robots.txt.ts` (shown above) never emits that text at all — the whole file was replaced.
4. **`sitemap.xml.ts` differs indirectly**: `lib/site.ts`'s `sitemapRoutes()` drops
   `...DOCS_ROUTES` in m5; main still includes it, so main's sitemap has 4 more `<url>` entries.
5. **Content edited**: `packages/content/content/{home,pages/platform,pages/sdks}.json` changed one
   code sample from `eeg-basic@1.0.0` to `eeg-basic@1.2.0` in m5.
6. `astro.config.mjs`, `security-headers.mjs` gained the `SITE_STAGE`-aware `X-Robots-Tag` /
   `__NF_SITE_STAGE__` wiring to support (2).

**Consequence:** literal byte-for-byte parity against the m5 dist is not achievable while generating
from main's actual source (which is what this worktree, branched from main, contains) — the two
were never the same site. This is not a generator bug; it's the reference artifact being stale.
Byte-diff tests below are therefore written against **hand-derived expected output from main's own
source logic**, not against the m5 files, for anything touched by findings 2-4 (which is nearly
every emitted file).

### Lead decision (2026-09-27)

Target main's source as-is. The byte-parity gate stays, but its **golden file will be a fresh Astro
build of main**, made once node is allowed again. Until then: implement from main's source; the m5
dist is an **informal** check only, and only on the files listed below. **Parity is unproven until
the main-built golden exists.** If `chore/ci-site-hardening` merges into main first, the golden gets
rebuilt from merged main instead. Homepage source content is never edited, full stop.

**Update (2026-09-27, later that day):** the node/python ban was lifted (RUST-POLICY.md). web-queen
now builds real `apps/web/dist` output from the current tree (in a bci-queen compile slot) in
`neuro-worktrees/web-integration`; `tests/parity.rs` reads it via `NF_WEB_DIST` (see that file's doc
comment). This crate still doesn't build its own dist — that's a division-of-labour choice (web-queen
owns the site build, this crate owns the Rust generator), not a tool restriction anymore. So a real,
non-stale golden now exists in practice, refreshed whenever web-queen rebuilds and reports the commit;
the m5 snapshot below is superseded and kept only for its diagnostic history.

### Exact effect of finding 2 (read `indexing.mjs` from m5, since it doesn't exist on main)

```js
export function robotsMeta({ stage, noindex = false }) {
  return noindex || !isIndexable(stage) ? 'noindex,nofollow' : null;
}
```
`isIndexable` is false for the default `SITE_STAGE=preview`. So on m5's dist (built at the default
stage): **every** page gets `<meta name="robots" content="noindex,nofollow">`, identical string to
what main's `Base.astro` already emits for pages that pass `noindex` explicitly. That means:
- Pages where **main also already sets `noindex` explicitly** (gallery, 404, the 4 legal drafts x2
  locales = 8): the robots-meta line is **byte-identical** between main's real output and the golden
  dist. These 10 pages are not affected by finding 2 at all.
- Pages where **main's `noindex` is false** (governance, law-tracker, pricing, research index +
  1 whitepaper, security, no/security, platform, sdks, index): golden dist has exactly one extra
  `<meta name="robots" content="noindex,nofollow">` line that main's current layout would not emit.
  Known, single-line, mechanical difference — not a generator bug.
- `_headers`/`_headers.json`: m5's `globalHeaders()` adds `'X-Robots-Tag': ROBOTS_NOINDEX` (value
  `'noindex, nofollow'`, note the space — different string from the meta tag's) to literally every
  rule when stage is preview. Main's `globalHeaders()` has no such key. Whole-file diff on every rule.

### Files whose content INPUT is byte-identical between main and chore/ci-site-hardening

(`git diff origin/main..<m5 HEAD>` empty for these paths, checked 2026-09-27):
`packages/content/brand.json`, `content/site.json`, `content/ui.en.json`, `content/ui.no.json`,
`content/pages/governance.json`, `content/pages/law-tracker.json`, `content/pages/pricing.json`,
`content/research/somatosensory-closed-loop.json`, `content/security.en.json`,
`content/security.no.json`, all 8 of `content/legal/{privacy,terms,cookies,company}.{en,no}.json`.
(`content/home.json`, `content/pages/platform.json`, `content/pages/sdks.json` are **not** in this
list — finding 5, the `eeg-basic` version-string edit.)

Pages built only from the identical-input list above, ranked by how close an informal diff against
the golden dist should come once implemented:
1. **`/gallery/`, `/404`, `/legal/*`, `/no/legal/*`** (10 pages) — content unchanged AND the
   robots-meta line already matches (see above). Closest thing to a real informal check available
   before the main golden exists. `_headers`/`_headers.json` will still differ (X-Robots-Tag).
2. **`/governance/`, `/law-tracker/`, `/pricing/`, `/research/`,
   `/research/somatosensory-closed-loop/`, `/security/`, `/no/security/`** — content unchanged but
   expect exactly the one known extra robots-meta line (plus the header-file diff) versus the golden
   dist; everything else in the HTML body should informally match.
3. **`/platform/`, `/sdks/`, `/` (home)** — content changed (finding 5) *and* the robots-meta line,
   so two known differences. Still useful once the version-string difference is accounted for.
   Homepage source is never edited to force this: the mismatch is logged, not "fixed" by editing copy.
4. **`docs/*`, `robots.txt`, `sitemap.xml`, `_headers`/`_headers.json` overall** — no informal check
   possible (findings 1, 3, 4, and the header-file diff apply to every rule respectively).

## Stage 2: implementation order

1. Content-loading layer: serde structs for `brand.json`, `content/site.json`, legal `draft` flags,
   `whitepapers` keys — shared by every generator below. (done, minimal subset)
2. `robots.txt` per theme — plain text, no HTML templating, no dependency on the noindex finding.
   Ported from main's `pages/robots.txt.ts` verbatim logic. **Byte-parity proven** (see scorecard).
3. `sitemap.xml` — plain XML text. Ported from main's `sitemapRoutes()`, including the `/playground/`
   and `/interface/` routes added at `6a79900` (feature/neural-playground) and `DOCS_ROUTES`
   (`content::docs_routes()`: reads each `docs/quickstarts/*.json`'s `order` field and sorts by it —
   docs.ts sorts by `order`, not filename — then `/docs/`, those slugs, `/docs/api/`,
   `/docs/changelog/`). **Byte-parity proven** (see scorecard). Note: this only produces the
   *sitemap route strings* for `/docs/*` — the actual `/docs/*.astro` HTML pages are still item 6,
   not implemented.

**`tests/parity.rs` (web-queen T1, redesigned 2026-09-27 per web-queen's correction):** the reference
is `<dist root>/{clinical,cosmos}/{robots.txt,sitemap.xml}` **built from the current tree**, not
the frozen m5 snapshot — a fixture that predates the tree "proves nothing and goes stale at the next
sitemap change" (web-queen). Asserts 0 byte diff; fails with "build the site first" if that dist
doesn't exist (mirrors `apps/web/test/_dist.mjs`'s pattern). Dist root defaults to `apps/web/dist` in
this worktree (which won't exist here) but honours `NF_WEB_DIST` to point at web-queen's build in
`neuro-worktrees/web-integration` instead — division of labour (web-queen owns the site build, this
crate owns the generator), not a tool restriction: the node ban was lifted the same day. The old
m5-fixture-based tests were removed 2026-09-27; the fixture files themselves were deleted the same
day (web-queen: superseded, git history keeps them) once real parity against a live dist was proven.

**`#[ignore]`d by default (web-queen, 2026-09-27):** CI's Rust job (`cargo test --workspace --locked`,
`.github/workflows/ci.yml`) never builds `apps/web/dist`, so these 2 tests would fail every CI run if
not ignored. Run explicitly: `NF_WEB_DIST=<dist path> cargo test -p site-rs -- --ignored` — they still
hard-fail (not skip) with "build the site first" if no dist is found.

**Result (2026-09-27, run in bci-queen's lane B/C against web/integration `3d205c0` = main `90e56a6`
+ web/perf, which doesn't touch robots.txt/sitemap.xml): both tests pass, 0 byte diff, both themes.**
First run (before `DOCS_ROUTES` was wired) caught a real 9-line diff — exactly the 7 missing
`/docs/*` routes — proving the test actually detects drift, not just rubber-stamping. Fixed by adding
`content::docs_routes()`; re-run is green.
4. `security-headers.mjs` + `host-headers.mjs` port (`_headers`, `_headers.json`) — `src/headers.rs`,
   resumed 2026-09-27 (brought back from `wip/site-rs-headers-port`, updated for main's current API:
   `active` exceptions are now an explicit input to `cloudflare_rules()`/`host_rules()` rather than
   computed from `paths` alone, `_headers.json` gained `activeExceptions`). Covers `Stage`/`Host`
   resolution, `csp()` incl. per-route SEC-150 exceptions (`csp-exceptions.json`, e.g. `/arena/`'s
   `'wasm-unsafe-eval'`), `global_headers()`, both the Netlify and Cloudflare (splat layout +
   Cloudflare's rule/line limits) `_headers` layouts and renderers, and `_headers.json`. Unit-tested in
   `headers.rs`; byte-diff parity checked in `tests/parity.rs` (`headers_txt_matches_dist_byte_for_byte`,
   `headers_json_matches_dist_byte_for_byte`, both `#[ignore]`d like the others) which reads `paths` by
   walking the reference dist (same technique as robots.txt/sitemap.xml) and reads `stage`/`host`/
   `activeExceptions` back out of the dist's own `_headers.json` rather than assuming a fixed host.
   **Not wired into `main.rs`**: this crate has no HTML page generation yet (item 5), so it has no
   independent, correct `paths` list to build a real `_headers` file with outside a test.

   **GATE (team-lead ruling, 2026-09-27, on web-headers' review at
   `docs/hive/REVIEW-site-rs-headers.md`, `web/headers @34dc115`): `headers.rs` may run only as a
   parity check next to JS, never as the generator, until ALL of these are ported with tests:**
   | # | Gap | Status |
   |---|---|---|
   | 1 | wasm-reachable trigger (`exceptionsInUse`), fail-strict on error | **done, re-reviewed** - `src/csp_check.rs`, unit-tested against synthetic dists (reaches/doesn't-reach/only-another-route/dist-confinement/fail-strict); also follows `<link rel=modulepreload>` (web-headers 2nd review, `web/headers @c9dc2fe`, item a) and propagates a mid-scan read failure as a real error instead of silently skipping the file (item b) |
   | 2 | policy checker (`assertCspSafe`) | **done** - `headers::assert_csp_safe()`, unit-tested (baseline OK, unlisted wasm-unsafe-eval rejected, route-scoped exception OK only on its own route, non-self source rejected, missing directive rejected) |
   | 3 | Cloudflare rule/line-limit enforcement in the generator | **done** - `headers::render_host_headers_checked()` (calls `assert_cloudflare_limits` for Cloudflare); `tests/parity.rs`/`arena_fixture_parity.rs` call this, not the bare renderer |
   | 4 | per-URL assertions (e.g. `/arena/` gets exactly one policy) | **done** - `headers::parse_host_headers()`/`host_headers_for_path()`, unit-tested (`arena_gets_exactly_one_policy_and_it_is_the_route_csp`) |
   | 5 | `checkCsp`/`arenaLayoutProblems` (full static conformance + arena layout guard) | **out of scope** until a full `postbuild.mjs` replacement is proposed (lead: "goes with full replacement only") |
   | - | trip-wire: JS `INLINE_SCRIPT_HASHES`/`INLINE_STYLE_HASHES` still `[]` | **done** - `headers::tests::js_inline_hash_arrays_are_still_declared_empty` reads main's source text |
   | c | cross-check: run this crate's own trigger on the JS-built fixture, assert it agrees with `active.json` | **done** - `arena-fixture-js.mjs` now keeps the fixture dist alive (`dist-dir.txt`) instead of deleting it; `tests/arena_fixture_parity.rs`'s `own_trigger_agrees_with_js_on_*` |
   | (nit) | `checked_active` compare `directive` too | **done** (landed with the first gaps 1-4 commit) |
   | (nit) | repeated header key within one rule: JS keeps the last value, Rust kept both | **done** - `host_headers_for_path()` collapses same-rule repeats first |

   Web-headers' 2nd re-review (`web/headers @c9dc2fe`) confirmed gaps 1-4 + items 7-8 match JS and
   passed `dfccaae` as parity-only, good to batch. Team-lead's follow-up (still parity-only, item (d)
   "wire a Rust driver like postbuild step 3" stays out of scope "until the owner wants Rust
   authoritative"): items a, c and the nit above landed here; item b (nice-to-have) landed too.

   **New dependency (lead-approved 2026-09-27): `regex`**, pinned exact in `Cargo.toml` (`=1.13.1`),
   needed for `csp_check.rs`'s HTML/JS scanning. Full resolved tree (`Cargo.lock`, one `crates.io`
   fetch, no build scripts on any of the four - confirmed via `cargo build` output showing no build-
   script compile step for them):
   | Crate | Version | New this fetch? |
   |---|---|---|
   | `regex` | 1.13.1 | yes |
   | `regex-automata` | 0.4.18 | yes |
   | `aho-corasick` | 1.1.5 | yes |
   | `regex-syntax` | 0.8.11 | no - already in `Cargo.lock` (another workspace member's tree) |
   | `memchr` | 2.8.3 | no - already in `Cargo.lock` |
   `.crate` cache sizes for the 3 new ones: `aho-corasick-1.1.5.crate` 184,315 B,
   `regex-1.13.1.crate` 157,118 B, `regex-automata-0.4.18.crate` 628,707 B (970,140 B / ~947 KB total
   if fetched fresh - their cache file timestamps predate this session, so the actual fetch was
   likely just the crates.io index metadata, not these bytes over the network).

   Gaps 1-4 landed 2026-09-27 (branch `feature/site-rs-headers`, branched fresh off `origin/main` per
   web-queen since the earlier robots/sitemap work had already merged to main). **Still not a drop-in
   for `postbuild.mjs` step 3** even with 1-4 done: item 5 is deliberately not ported, and this crate
   still has no `main.rs` wiring to actually replace the JS build step - that's a separate, later
   decision the lead would need to make explicitly.

   `tests/arena_fixture_parity.rs` (team-lead ruling, before the review above landed) verifies the
   `/arena/` rule end-to-end: `tools/site-rs/scripts/arena-fixture-js.mjs` (committed 2026-09-27,
   web-queen: so anyone can reproduce this, not just the session that first wrote it; not part of the
   Rust build or CI) replicates `apps/web/test/csp-static.test.mjs`'s **canonical** `hashedArena()`
   fixture (web-headers' correction: hashed glue + hashed `.wasm` under shared `/_assets/` - the older
   `arenaFixture()` shape in that file is not what main actually ships) on top of a real dist, in two
   variants: `canonical-active` (the chunk reaches the hashed `.wasm`, exception active) and
   `stub-baseline` (`/arena/` built with no wasm-reaching loader, must stay baseline - web-headers'
   second pointer). Each variant calls the REAL, unmodified `postbuild()` for both hosts and dumps
   `paths.json`/`active.json`/`<host>._headers(.json)`/`netlify.error.txt`/`dist-dir.txt` (the last one
   points at the fixture's own dist dir, kept alive rather than deleted, for the `own_trigger_agrees_
   with_js_on_*` cross-check tests - review item c). The Rust test reads those same inputs, runs this
   crate's `headers.rs` on them, and byte-diffs both hosts' output (Netlify on `canonical-active` is
   expected to *fail* the same way JS does - "KEEP FAIL" - error message compared verbatim). Run:
   `node tools/site-rs/scripts/arena-fixture-js.mjs <repo-root> <clinical-dist-dir> <out-dir>` then
   `NF_ARENA_FIXTURE_DIR=<out-dir> cargo test -p site-rs -- --ignored`; delete the two dirs named in
   `<out-dir>/*/dist-dir.txt` afterwards. `#[ignore]`d by default.
   **Netlify against a real (non-fixture) dist:** web-queen built one, both themes, at
   `neuro-worktrees/wq-dist-netlify/{clinical,cosmos}` (from web/integration, web code = main
   `d20b47f` + playground notices, headers pipeline unchanged) - `tests/parity.rs`'s
   `headers_txt_matches_dist_byte_for_byte`/`headers_json_matches_dist_byte_for_byte` already read
   host/stage back out of whichever dist's `_headers.json` they're pointed at via `NF_WEB_DIST`, so
   pointing `NF_WEB_DIST` at `wq-dist-netlify` exercises the Netlify path with zero code changes.
5. HTML pages, simplest first, on branch `feature/site-rs-pages` (from `origin/main` `231468c`, team-
   lead 2026-09-27). **`404.astro` done** - `src/pages/not_found.rs`, byte-diff tested (`tests/
   pages_parity.rs`, `#[ignore]`d like the others). **Templating strategy, read before porting the
   next page** (full rationale in `not_found.rs`'s module doc comment): reimplementing Astro's
   compiler + Vite's bundler in Rust is not attempted. Instead, `templates/404.{clinical,cosmos}.html`
   are byte-exact copies of the reference dist's `404.html`, with the page's genuinely dynamic values
   (from `content/site.json`'s `notFound`) cut out as `@@SENTINEL@@` tokens and refilled at render
   time from the same content source Astro reads. This is real parity (byte-diff proven against a
   live dist, both themes) for a *frozen* build - it is fragile to any change in a component the
   copied boilerplate depends on (Nav, Footer, BrandMark, their `data-astro-cid-*` hashes, or Vite's
   `_assets/*` filenames), which the parity test catches on next run, not at the moment of drift.
   `content::substitute_tokens()` + `Brand::vars()` port `packages/content/src/validate.ts`'s
   `substitute()` (`{brand}`/`{legalName}`/`{domain}`/`{origin}`/`{pkg}` token replacement), needed by
   every future page's content too, not just this one.
   Next, in order: `gallery.astro` / `legal/[page].astro` x4 (+`no/`) (the 10 pages with a real
   informal check available before real dist parity existed) -> `security.astro` / `no/security.astro`
   -> `[page].astro` generic pages (`governance`, `pricing` first, then `platform`/`sdks`) ->
   `research/index.astro` -> `research/[slug].astro` -> `law-tracker.astro` -> `index.astro`
   (homepage last: highest scrutiny, source content frozen and never edited to force a match).
6. `docs/*` pages — only relevant if the lead keeps them on main; skip if `chore/ci-site-hardening`'s
   removal is going to land.

**Every item above is "implemented and self-consistent", never "byte-parity proven"**, until the
lead's fresh main-built golden exists (see Lead decision above). The informal-check ranking in the
Finding section says how close each page should come in the meantime, and which known differences
(robots-meta line, header X-Robots-Tag, `eeg-basic` version string) to expect and not chase.

## Parity scorecard (updated as pages land)

Checked against `NF_WEB_DIST` = `neuro-worktrees/web-integration/apps/web/dist`, built by web-queen
from `3d205c0` (≈ main `90e56a6`); refreshed whenever she rebuilds and reports the new commit.

| File | Status |
|---|---|
| `robots.txt` (both themes) | **byte-parity proven** — `tests/parity.rs`, 0 diff, 2026-09-27 |
| `sitemap.xml` (both themes) | **byte-parity proven** — `tests/parity.rs`, 0 diff, 2026-09-27 (incl. `/playground/`, `/interface/`, all 7 `/docs/*` routes) |
| `_headers` / `_headers.json` | **byte-parity proven, both hosts** — `tests/parity.rs`, 0 diff, both themes, cloudflare (web-integration dist) and netlify (wq-dist-netlify); plus the `/arena/` rule via fixture (`tests/arena_fixture_parity.rs`) |
| `404.html` (both themes) | **byte-parity proven** — `tests/pages_parity.rs`, `src/pages/not_found.rs`, see Stage 2 item 5's templating-strategy note |
| gallery / legal x4 (+no/) — 9 remaining pages with a real informal check available | not started |
| governance / law-tracker / pricing / research (x2) / security / no-security | not started |
| platform / sdks / index (home) | not started; home source never edited |
| `/docs/*` HTML pages (routes already in sitemap.xml) | not started; deferred, may be dropped if `chore/ci-site-hardening`'s removal lands |
| `/playground/`, `/interface/` HTML pages | not started (both are heavier, JS-driven pages — lower priority than the pure-content pages above) |

## APP-L8: SITE_STAGE (`chore/ci-site-hardening`, merged to main `f8917e8`, 2026-09-27)

Implemented (web-queen signal: the branch is on main). `headers::Stage` gained `is_indexable()`
(`isIndexable(stage)` in `apps/web/indexing.mjs`: `resolveStage(stage) !== 'preview'`) and a new
`headers::ROBOTS_NOINDEX` constant (`apps/web/stage.mjs`'s `'noindex, nofollow'` - note the space,
different from the `<meta name="robots">` tag's future `'noindex,nofollow'` spelling).

- `robots::robots_txt()` now takes a `Stage` parameter. On a non-indexable stage it short-circuits to
  `indexing.mjs`'s crawler-blocking body (`# SITE_STAGE=<stage>: preview builds are not for search
  engines.\nUser-agent: *\nDisallow: /\n`), regardless of theme; otherwise unchanged. `main.rs` reads
  `SITE_STAGE` the same way `resolveStage()` does (default `preview`).
- `headers::global_headers()` appends `X-Robots-Tag: noindex, nofollow` as the *last* header
  (matching `security-headers.mjs`'s `...robots` spread position) whenever `!stage.is_indexable()`.
- `tests/parity.rs`'s robots/headers tests already read `stage` back out of the reference dist's own
  `_headers.json` rather than hardcoding it (noted as a design win when the tests were first written)
  - `robots_txt_matches_dist_byte_for_byte` now does the same, via the existing `dist_headers_meta()`
    helper, so no test had to assume which stage a given reference dist was built at.
- **Not done**: the `<meta name="robots">` per-page logic (`Base.astro`'s `robotsMeta()`) - no HTML
  page ported so far needs it. `indexing.mjs`'s comment notes the homepage is frozen and doesn't get
  this treatment even once HTML pages exist; a future non-homepage page (404, legal drafts, ...) that
  already sets `noindex` explicitly is unaffected either way, since `robotsMeta()`'s two conditions
  (`noindex || !isIndexable(stage)`) both already resolve to the same `'noindex,nofollow'` value for
  those pages regardless of stage.
