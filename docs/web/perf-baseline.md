# Web performance baseline (2026-09-27)

Measured by `node tools/web/perf-audit.mjs --pages` on both theme builds of web/perf, which is origin/main
6a79900 plus the /docs/api style change (docs/hive/PERF-AUDIT.md). Node 22.23.3, Windows. Budgets:
`tools/web/perf-budgets.json`, enforced by `apps/web/test/perf-budget.test.mjs`.

**How it is measured.** Sizes are gzip -9 unless marked raw. KB = 1024 bytes.

- **Initial JS** is `<script src>` plus modulepreload plus their static-import closure (same rule as
  `apps/web/scripts/js-size.mjs`).
- **Lazy JS** is reachable only through `import()`.
- **Data** is the hashed `/_assets/*.json|bin|wasm` the JS fetches.
- **Fonts** are the woff2 each linked `@font-face` would fetch. That is an upper bound, because a browser
  fetches only the faces a page renders; the woff fallbacks are never fetched by current browsers.
- **Total** is HTML + CSS + initial JS + fonts + images. Lazy JS and data come after first paint and are
  listed separately.
- **Requests** counts HTML, stylesheets, initial JS, fonts and images.

## Summary per theme (29 pages each)

| Metric | clinical: home | clinical: inner median | clinical: inner max | cosmos: home | cosmos: inner median | cosmos: inner max |
|---|---|---|---|---|---|---|
| Total | 116.3 KB | 106.7 KB | 197.3 KB /interface/ | 160.2 KB | 147.5 KB | 233.2 KB /interface/ |
| HTML | 7.2 KB | 3.6 KB | 15.8 KB /docs/api/ | 7.7 KB | 3.7 KB | 16.0 KB /docs/api/ |
| HTML raw | — | 13.9 KB | 208.8 KB /docs/api/ | — | 14.1 KB | 209.0 KB /docs/api/ |
| CSS | 7.1 KB | 3.9 KB | 7.9 KB /gallery/ | 7.8 KB | 4.1 KB | 8.7 KB /gallery/ |
| Initial JS | 3.8 KB | 0.6 KB | 7.7 KB /playground/ | 5.9 KB | 0.6 KB | 7.7 KB /playground/ |
| Lazy JS | 0 | 0 | 126.3 KB /interface/ (three.js) | 120.3 KB | 0 | 129.3 KB /interface/ |
| Data | 0 | 0 | 137.3 KB /playground/, /interface/ (367 KB raw JSON) | 0 | 0 | 137.3 KB |
| Fonts (woff2) | 98.3 KB (5) | 98.3 KB (5) | 98.3 KB (5) | 138.8 KB (7) | 138.8 KB (7) | 138.8 KB (7) |
| Images | 0 | 0 | 83.4 KB, 1 JPEG /interface/ | 0 | 0 | 78.3 KB, 1 JPEG /interface/ |
| Requests | 20 | 13 | 22 /gallery/ | 23 | 15 | 25 /gallery/ |
| Render-blocking CSS files | 11 | 6 | 12 /gallery/ | 11 | 6 | 12 /gallery/ |
| Render-blocking scripts | 0 | 0 | 0 | 0 | 0 | 0 |

- **Fonts:** every @font-face uses `font-display: swap` and is self-hosted latin-subset woff2. No page
  preloads a font.
- **Third parties:** none; no page loads a third-party resource.
- **Images:** the only raster image is the /interface WebGL fallback still, a 1600x900 JPEG. No other
  page has an `<img>`. Figures are inline SVG: 1.4 to 19.6 KB raw per page, largest on /gallery/.

## Per page (inner pages; the home row is for reference and is not budgeted)

`total / html / css / initial JS + lazy JS / data / fonts / images / requests`, in KB gzip.

| Page | clinical | cosmos |
|---|---|---|
| / (not budgeted) | 116.3 / 7.2 / 7.1 / 3.8+0 / 0 / 98.3 / 0 / 20 | 160.2 / 7.7 / 7.8 / 5.9+120.3 / 0 / 138.8 / 0 / 23 |
| /404.html | 103.5 / 1.6 / 3.1 / 0.6+0 / 0 / 98.3 / 0 / 11 | 144.3 / 1.8 / 3.2 / 0.6+0 / 0 / 138.8 / 0 / 13 |
| /docs/ | 105.6 / 2.9 / 3.9 / 0.6+0 / 0 / 98.3 / 0 / 13 | 146.4 / 3.0 / 4.1 / 0.6+0 / 0 / 138.8 / 0 / 15 |
| /docs/api/ | 118.5 / 15.8 / 3.9 / 0.6+0 / 0 / 98.3 / 0 / 12 | 159.4 / 16.0 / 4.1 / 0.6+0 / 0 / 138.8 / 0 / 14 |
| /docs/changelog/ | 104.9 / 2.3 / 3.7 / 0.6+0 / 0 / 98.3 / 0 / 12 | 145.7 / 2.4 / 3.9 / 0.6+0 / 0 / 138.8 / 0 / 14 |
| /docs/quickstart/* (4) | 105.2–105.7 / 2.5–3.0 / 3.9 / 0.6+0 / 0 / 98.3 / 0 / 13 | 146.0–146.5 / 2.6–3.1 / 4.0 / 0.6+0 / 0 / 138.8 / 0 / 15 |
| /gallery/ | 119.4 / 8.9 / 7.9 / 4.3+0 / 0 / 98.3 / 0 / 22 | 163.7 / 9.8 / 8.7 / 6.5+120.3 / 0 / 138.8 / 0 / 25 |
| /governance/ | 106.8 / 3.2 / 4.8 / 0.6+0 / 0 / 98.3 / 0 / 16 | 147.9 / 3.4 / 5.1 / 0.6+0 / 0 / 138.8 / 0 / 18 |
| /interface/ | 197.3 / 4.6 / 4.5 / 6.5+126.3 / 137.3 / 98.3 / 83.4 / 16 | 233.2 / 4.7 / 4.7 / 6.7+129.3 / 137.3 / 138.8 / 78.3 / 19 |
| /law-tracker/ | 108.7 / 5.6 / 4.4 / 0.6+0 / 0 / 98.3 / 0 / 13 | 149.5 / 5.7 / 4.6 / 0.6+0 / 0 / 138.8 / 0 / 15 |
| /legal/* and /no/legal/* (8) | 105.3–108.3 / 2.7–5.7 / 3.7 / 0.6+0 / 0 / 98.3 / 0 / 12 | 146.1–149.1 / 2.8–5.8 / 3.9 / 0.6+0 / 0 / 138.8 / 0 / 14 |
| /platform/ | 107.1 / 3.5 / 4.8 / 0.6+0 / 0 / 98.3 / 0 / 16 | 148.2 / 3.7 / 5.1 / 0.6+0 / 0 / 138.8 / 0 / 18 |
| /playground/ | 116.9 / 5.9 / 5.0 / 7.7+0 / 137.3 / 98.3 / 0 / 15 | 157.7 / 6.0 / 5.2 / 7.7+0 / 137.3 / 138.8 / 0 / 17 |
| /pricing/ | 106.2 / 2.6 / 4.8 / 0.6+0 / 0 / 98.3 / 0 / 16 | 147.3 / 2.9 / 5.1 / 0.6+0 / 0 / 138.8 / 0 / 18 |
| /research/ | 105.2 / 2.4 / 4.0 / 0.6+0 / 0 / 98.3 / 0 / 14 | 145.9 / 2.5 / 4.2 / 0.6+0 / 0 / 138.8 / 0 / 16 |
| /research/somatosensory-closed-loop/ | 109.2 / 5.1 / 4.7 / 1.1+0 / 0 / 98.3 / 0 / 14 | 149.9 / 5.2 / 4.9 / 1.1+0 / 0 / 138.8 / 0 / 16 |
| /sdks/ | 106.4 / 2.8 / 4.8 / 0.6+0 / 0 / 98.3 / 0 / 16 | 147.4 / 3.0 / 5.1 / 0.6+0 / 0 / 138.8 / 0 / 18 |
| /security/, /no/security/ | 109.2, 109.6 / 5.9, 6.4 / 4.4 / 0.6+0 / 0 / 98.3 / 0 / 13 | 150.3, 150.8 / 6.1, 6.5 / 5.0 / 0.6+0 / 0 / 138.8 / 0 / 15 |

## Budgets

`tools/web/perf-budgets.json` holds a budget for each inner page and each metric:

- **Default rule:** the measured value +10%, rounded up, with a floor of +1 KB for byte metrics and +1 for
  counts.
- **New pages:** a page added later gets the `"*"` entry, which is the theme's largest inner page +10%.
- **Hard rules** (not budgets), enforced by the test:
  - no render-blocking classic script;
  - raster images must be AVIF/WebP and at most 200 KB (the /interface JPEG is a listed exception);
  - every @font-face is self-hosted woff2 with `font-display: swap`;
  - no third-party resources.

After a reviewed, deliberate size change, regenerate with `node tools/web/perf-audit.mjs --write-budgets` and
commit the JSON diff with the reason.
