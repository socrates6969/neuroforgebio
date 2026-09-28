# Web performance audit (web-perf, 2026-09-27)

Branch web/perf: origin/main 6a79900 (includes /playground and /interface) plus this work. Full per-page numbers:
`docs/web/perf-baseline.md`. Tooling: `tools/web/perf-audit.mjs` (offline, node only, no new dependencies), budgets
`tools/web/perf-budgets.json`, test `apps/web/test/perf-budget.test.mjs`. The homepage is not changed and not budgeted.

## Findings

1. **Fonts are about 92–94% of a typical inner page.** The median inner page is 106.7 KB (clinical) and 147.5 KB
   (cosmos). Of that, the woff2 faces are 98.3 KB for clinical (5 faces) and 138.8 KB for cosmos (7 faces), as an
   upper bound. Everything else is small: HTML median 3.6 KB, CSS about 4 KB and initial JS 0.6 KB. The fonts are
   already self-hosted, latin-subset woff2 with `font-display: swap`, so text renders at once. No font is preloaded.
   The woff fallbacks in the CSS are never fetched by current browsers. My first count included them and
   double-counted them (192/317 KB); the audit now counts only the first `src`.
2. **CSS arrives in many small render-blocking files.** Inner pages link 4 to 12 stylesheets (median 6; /gallery/
   has 12, / has 11). Some chunks are tiny, down to 48 bytes (`.next{margin-top:28px}` for the quickstarts). This
   comes from Astro/Vite per-component CSS splitting, with `inlineStylesheets: 'never'` required by the CSP. Over
   HTTP/2 the cost is extra requests before first render, not bytes.
3. **/docs/api/ carried 195 KB of scoped-style attributes (fixed below).** The page's scoped `<style>` made Astro
   stamp `data-astro-cid-ovyzdvsb` on each of 8,010 elements, which was 48% of its 406 KB of HTML. Other pages
   carry the same kind of overhead at a much smaller scale: 1–33% of raw HTML, and at most 1.2 KB after gzip. That
   is not worth changing.
4. **Images.** The only raster image on the site is the /interface WebGL-fallback still: a 1600x900 JPEG of 85 KB
   (clinical) or 80 KB (cosmos). It is shown first, so it is likely the page's LCP element. Re-encoded with sharp
   0.34.5, which is already in node_modules, it measured as follows:
   - AVIF q70: 36.0 / 33.9 KB (−58%), 47.5 / 48.0 dB PSNR against the JPEG.
   - WebP q82: 39.6 / 36.7 KB, 44.4 / 44.7 dB.

   The stills in `neuro-media/stills-manifest.json` are 2560x1440 JPEGs of 100–324 KB, and none ships yet. The
   budget test now requires AVIF/WebP and at most 200 KB per image.
5. **Lazy and data payloads are after first paint and fine as designed.** three.js is a dynamic chunk: 120.3 KB on
   cosmos / and /gallery/, and 126–129 KB on /interface/. /playground/ and /interface/ also fetch the MC_RTT replay
   JSON, which is 367 KB raw and 137.3 KB gzip.
6. **No render-blocking scripts and no third-party requests** on any page in either theme. Initial JS is at most
   7.7 KB (/playground/).

## Optimisation made: /docs/api scoped style to anchored global (web-queen approved, web-docs OK)

`apps/web/src/pages/docs/api.astro`: only the `<style>` block changed, to `<style is:global>`.

- **Selectors:** every one is anchored under DocsShell's `.docs` wrapper (`h3` and `summary` under `.docs .body`),
  so each rule keeps the specificity the scoped selector had.
- **Markup:** unchanged.
- **Scope:** the CSS is emitted only into the page's own chunk, which is linked by /docs/api/ alone.

| /docs/api/ | clinical before | clinical after | cosmos before | cosmos after |
|---|---|---|---|---|
| HTML raw | 406,089 B | 213,849 B (−47.3%) | 406,248 B | 214,008 B (−47.3%) |
| HTML gzip -9 | 18,213 B | 16,172 B (−11.2%) | 18,419 B | 16,380 B (−11.1%) |
| HTML brotli | 14,051 B | 12,982 B (−7.6%) | 14,143 B | 13,105 B (−7.3%) |
| scope attributes | 8,010 | 0 | 8,010 | 0 |
| page CSS raw | 756 B | 547 B | 756 B | 547 B |

Proof, with both builds made from the same tree (6a79900) with and without the change:

- **(a) Computed style:** a headless Chromium (Playwright 1.63, installed) compared every element's full computed
  style plus its layout box on /docs/api/ and /docs/. That was 8,139 elements on clinical and 8,143 on cosmos, with
  all `<details>` opened, at 1280 and 390 px. Result: **0 differing elements**, and the full-page screenshots were
  byte-identical in both themes.
- **(b) CSS of other pages:** `diff -rq` over both dist trees shows that only `docs/api/index.html` and its own
  `api.*.css` changed. Every other page, CSS, JS, font, `_headers` and `security.txt` file is byte-identical.
- **(c) Homepage:** `/` is untouched, because `index.html` and all its assets are byte-identical.
  `homepage.test.mjs`, `security.test.mjs` (CSP/SEC-150a inline) and the postbuild inline check all pass.

## Recommendations (not done: they change `/` or shared files, so they need web-queen and the lead)

- **R1 Fonts (largest lever):**
  - Preload the one body face per theme (IBM Plex Sans 400, 22.6 KB; Inter 400).
  - Ask the designer whether the third sans weight is needed, since each clinical face is 14.7–24.3 KB.

  Both options touch Base.astro or `packages/themes/*/tokens.css`, and so they touch `/`.
- **R2 CSS chunking:** merge the tiny per-component chunks. One way is Vite `build.cssCodeSplit` or `manualChunks`
  in `astro.config.mjs`. The other is a postbuild concat for inner pages only, which trades away cross-page caching
  of the small files. Either would cut about 3–10 blocking requests per page. The config route changes `/`'s
  `<link>` list.
- **R3 /interface still (nfb-playground):** switch to AVIF q70, with the JPEG kept in `<picture>` if wanted, to save
  about 49 KB/46 KB per visit. When it lands, remove the `IMAGE_FORMAT_EXCEPTIONS` entry in
  `perf-budget.test.mjs`.
- **R4 Playground data (nfb-playground):** the replay JSON is 137 KB gzip. Trimming numeric precision or using a
  binary typed-array format is worth measuring. I have not measured it.

## Verification on handoff

These checks ran on web/perf with Node 22.23.3. Builds and tests ran in bci-queen's lane C.

- **Theme builds:** both passed (16 s / 17 s, peak 411 / 420 MB).
- **Web tests:** `node --test apps/web/test/*.test.mjs` ran 83 tests: 82 passed, 0 failed, 1 skipped. The skip is
  the slow rebuild test, which needs `NF_WEB_REBUILD_TEST=1`.
- **Content tests:** `node --test packages/content/test/*.test.mjs` ran 25 tests and all 25 passed.
- **Lint:** `node tools/dev/tasks.mjs lint --skip=rust` passed (`lint: ok`), with ruff skipped because this
  worktree has no .venv.
- **Budget test on the old page:** the test fails on the pre-fix /docs/api/. Its 406 KB of raw HTML is over that
  page's 230 KB budget.
