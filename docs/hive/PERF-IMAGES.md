# Proposal: AVIF/WebP for the site's stills (web-perf T2, 2026-09-27)

**Lead ruling, 2026-09-27:** option A was approved: Astro's built-in `<Picture>`, encoded at build time.
Option B (pre-encoding in a tool and committing the files) is not approved.

**Sequence, corrected by web-queen:** sharp is not resolvable from `apps/web` as things stand, because it is only
astro's optional dependency.

1. nfb-playground ships the no-WebGL fallback with plain JPEG stills on /playground and /interface. While that
   runs, `perf-budget.test.mjs` lists both pages in `IMAGE_FORMAT_EXCEPTIONS`, and web-perf regenerates the
   budgets for those pages from a build of that commit.
2. web-e2e declares `sharp: 0.34.5` in `apps/web`. This was lead-approved: it is the version already in the
   lockfile, so no new package is downloaded.
3. nfb-playground switches the stills to `<Picture formats={['avif']} fallbackFormat="jpg" widths={[1280, 1600]}>`.
   web-perf reviews the diff, removes both exceptions and re-tightens the two pages' budgets.

**Ownership and measurement:**

- web-perf does not edit those pages.
- `tools/web/perf-audit.mjs` already counts `<Picture>` output. It counts the first `<source>`, and within a
  `srcset` only the largest candidate (the worst case). A JPEG `<img>` passes only as a fallback behind an
  AVIF/WebP source.

## Which images

| Image | Where | Size today | Status |
|---|---|---|---|
| `interface-still-{clinical,cosmos}.jpg` | `apps/web/src/assets/interface/`, WebGL/no-JS fallback on /interface/, shown first (likely LCP) | 1600x900, 85,379 / 80,171 B | on main |
| `playground-still-{clinical,cosmos}.jpg` | `apps/web/src/assets/playground/` (playground worktree), /playground/ fallback | 1600x900, **byte-identical to the interface stills** (same MD5) | nfb-playground branch |
| `interface-{clinical,cosmos}-t{0.5,6,11,21}.jpg` (8 files) | `neuro-media/stills-manifest.json`, marketing stills for /interface | 2560x1440, 100,901–324,245 B | not on the site |

There are no other raster images. The rest of the figures are inline SVG.

## Measured sizes

**Method.** Each image was encoded with sharp 0.34.5 / libvips 8.17.3 from this repo's `node_modules`, resized with
the default Lanczos3 kernel. For the resized rows, "JPEG q85" is mozjpeg at the same width, which is what a plain
resize would ship.

**PSNR caveat.** PSNR is measured against the source JPEG resized to the same width, so it measures what the
re-encode loses relative to today's file. It is not a comparison with the lossless render.

**Run cost.** One node process on Windows, 81 s for all 32 rows, peak RSS 122 MB, no build slot used.

Script: `C:\Users\mariu\AppData\Local\Temp\claude\...\scratchpad\stills.cjs`, which would become a tool if approved.

### Site stills (1600x900; the playground copies give identical numbers)

| Still | Width | Today | AVIF q60 | AVIF q70 | WebP q82 | JPEG q85 at width |
|---|---|---|---|---|---|---|
| clinical | 1600 | 85,379 | 27,843 (45.6 dB) | **35,235 (47.4 dB), −59%** | 39,600 (44.4 dB) | — |
| clinical | 1280 | — | 19,199 (44.5 dB) | 24,744 (46.3 dB) | 26,914 (43.5 dB) | 39,340 |
| cosmos | 1600 | 80,171 | 26,131 (46.0 dB) | **33,182 (47.9 dB), −59%** | 36,668 (44.7 dB) | — |
| cosmos | 1280 | — | 17,990 (44.8 dB) | 23,271 (46.5 dB) | 25,370 (43.8 dB) | 36,506 |

Encode time for one still: AVIF 0.4–0.8 s, WebP about 0.1 s.

### Marketing stills (2560x1440), AVIF q70 (PSNR)

| Still | Today | 2560 | 1600 | 1280 |
|---|---|---|---|---|
| clinical t0.5 | 181,362 | 67,591 (48.2) | 36,953 (46.7) | 27,479 (46.3) |
| clinical t6 | 294,934 | 112,770 (46.2) | 60,886 (44.7) | 47,034 (44.4) |
| clinical t11 | 324,245 | 121,006 (46.0) | 65,177 (44.5) | 50,902 (44.2) |
| clinical t21 | 109,892 | 31,579 (50.2) | 18,456 (49.2) | 14,384 (48.8) |
| cosmos t0.5 | 165,049 | 61,860 (49.0) | 33,406 (47.3) | 25,155 (46.8) |
| cosmos t6 | 257,960 | 98,065 (47.1) | 53,056 (45.4) | 41,376 (44.9) |
| cosmos t11 | 288,364 | 107,468 (46.7) | 58,337 (44.9) | 45,576 (44.5) |
| cosmos t21 | 100,901 | 27,659 (51.3) | 16,399 (49.9) | 12,822 (49.4) |

- **Whole set:** AVIF q70 at native size is 59–73% smaller than today's JPEGs (the per-still table above).
- **At a display width of 1280/1600:** every still is at most 65 KB.
- **Budget:** all of them pass the budget test's 200 KB rule. Of today's JPEGs, only t0.5, t21 and the site stills
  would pass it.
- **WebP q82:** 12–49% larger than AVIF q70 at 1–5 dB lower PSNR.
- **AVIF q60:** saves about another 20%, but the busy frames (t6, t11) drop to 42–43 dB, where I would want a
  designer's eye before using it.

## Recommendation

1. **Format.** Use AVIF q70 as the primary `<source>`. The JPEG stays as the `<img>` fallback, as nfb-playground
   proposed, because no-WebGL/old browsers are the likeliest to lack AVIF. The audit counts only the source, and
   `perf-budget.test.mjs` allows a JPEG only behind an AVIF/WebP source. Skip a WebP tier: AVIF support covers
   current browsers, and the JPEG covers the rest.
2. **Sizes.** Ship `srcset` widths of 1280w and 1600w.
   - The stage is at most 1200 CSS px wide (`.nf-wrap` max-width), and the source is only 1600 px, so larger widths
     add nothing.
   - Use `sizes="(min-width: 1248px) 1152px, calc(100vw - 48px)"`, adjusted to the real padding.
   - Phones (4:5 crop, about 390 CSS px at 3x) get 1280. That is 23–25 KB instead of 80–85 KB.
3. **Keep the still eager.** It is the first paint on /interface/ and /playground/, so no `loading="lazy"`. Add
   `fetchpriority="high"`.
4. **Dedupe.** The playground and interface stills are the same bytes. One shared asset would let the browser cache
   it across both pages.
5. **Marketing stills.** If any goes on a page, use the same `<picture>` treatment at 1280/1600 (2560 only for
   full-bleed hero use).

## Two ways to build it (no new dependency either way)

- **A. Astro's built-in `<Picture>` (`astro:assets`).** Recommended for the site stills.
  - It encodes at build time through Astro's sharp image service, with
    `formats={['avif']}`, `fallbackFormat="jpg"`, `widths={[1280, 1600]}`, `loading="eager"` and
    `fetchpriority="high"`.
  - No committed binaries, no new tool. The encoded files are cached in `node_modules/.astro-cache/<theme>`.
  - Cost: about 1–3 s per theme on a cold build for 2 stills × 2 widths (from the encode times above), then cached.
  - It emits plain attributes with no inline style, so it is compatible with the strict CSP. I will confirm that
    with `security.test.mjs` when it is built.
- **B. Pre-encode in nfb-playground's `tools/playground/render-stills.mjs`** and commit the `.avif` next to the `.jpg`.
  - This works for images rendered outside the build (the marketing stills).
  - Cost: about 40–120 KB of binaries per still set in git, and the script must declare `sharp` itself.

## Dependency

Neither option adds a package download.

- **sharp 0.34.5** (Apache-2.0) is already in `pnpm-lock.yaml` as an optional dependency of astro 5.18.2
  (`"sharp": "^0.34.0"`).
- **@img/sharp-win32-x64 0.34.5** bundles **libvips 8.17.3** under **Apache-2.0 AND LGPL-3.0-or-later**. It is
  19 MB installed on Windows; sharp itself is 624 KB.
- It runs only at build time and ships nothing to browsers, so the browser-licence check (SEC-084) is unaffected.
  The LGPL part is the dynamically linked libvips binary, used only on the build machine.
- **Option A:** needs no manifest change.
- **Option B:** needs `sharp: 0.34.5` declared as a devDependency where the script lives, because depending on
  astro's optional copy is fragile. That resolves offline from the store, but it is a `package.json` and lockfile
  edit, so web-queen and the lead must approve it.

## Ownership

- /interface and /playground are nfb-playground's pages. They agreed to `<picture>` with a JPEG fallback on
  2026-09-27.
- web-perf supplies these numbers and the budget rule, and reviews the result with `tools/web/perf-audit.mjs`.
