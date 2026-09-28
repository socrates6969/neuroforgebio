# @nf/themes

Two build-time themes for `apps/web` (BLUEPRINT §2.2–2.3, CONTRACTS §3.1–3.2). `apps/web` aliases
`@theme` to `packages/themes/$THEME`, imports `@theme/tokens.css` and the four slots from
`@theme/slots/`. Only the selected theme enters the module graph, so clinical never ships three.js
or the cosmos fonts, and vice versa.

| Path | What |
|---|---|
| `contract.ts` | `REQUIRED_TOKENS` (§3.1), `EXTENDED_TOKENS` (ui extras), `THEME_TOKENS`, `SLOT_NAMES`, `SlotContract` |
| `clinical/tokens.css` | `[data-theme='clinical']` values from `design/option-1.html` `:root` + IBM Plex fonts |
| `cosmos/tokens.css` | `[data-theme='cosmos']` values from `design/option-3.html` `:root` + Space Grotesk / Inter / JetBrains Mono |
| `clinical/slots/*.astro` | HeroVisual (canvas 10-20 EEG montage), BrandMark (monochrome), SectionOrnament (numbered hairline), SecurityVisual (spec-table SVG) |
| `cosmos/slots/*.astro` | HeroVisual (SVG fallback + lazy three.js point-cloud brain), BrandMark (gradient), SectionOrnament (orbit glow), SecurityVisual (vault SVG) |
| `test/*.test.mjs` | `node --test` (zero deps): contract, contrast, fonts, slot budget, three isolation, CSP hygiene |

Run the tests: `node --test packages/themes/test/*.test.mjs` (also run by `apps/web` dist tests and `pnpm -r test`).

## Tokens

All 25 tokens are defined in both themes; the contract test fails on a missing token or on any
token not listed in `contract.ts`. `--motion-duration` drops to `0ms` under
`prefers-reduced-motion: reduce`.

`--color-surface`, `--color-surface-2`, `--color-line` and the cosmos status fills are translucent
("glass"); the contrast test composites them over `--color-bg` (and pills over each surface) before
measuring (BLUEPRINT §2.7).

Pairs checked at WCAG AA (4.5:1 text, 3:1 non-text): ink, muted, accent-ink and every
`--emphasis-paint` stop on bg / surface / surface-2; on-accent on accent and on accent-ink (button
hover); bg on ink (code blocks, skip link); each status ink on its fill over bg / surface /
surface-2; focus and accent (UI marks) on bg / surface. Current result: all pass (clinical 28 pairs,
cosmos 34).

### Deviations from the designs / BLUEPRINT §2.2 table

| Token | Design | Here | Why |
|---|---|---|---|
| clinical `--emphasis-paint` | accent `#0E7C86` | `var(--color-accent-ink)` `#0A5F67` | accent on the tinted panel (`--color-surface-2` `#EEF3F7`) is 4.43:1, below AA; `.rich em` body text can sit there |
| cosmos `--color-on-accent` | white on a `#6D28D9→#0E7490` gradient button | `#05010F` on `--color-accent` `#8B5CF6` | ui paints the primary button with the flat accent and swaps to accent-ink `#B79CFF` on hover; white fails on both (4.23:1, 2.28:1), the dark ink passes (4.87:1, 9.05:1) |
| cosmos `--elevation-card` | glass blur + border | inset highlight + violet drop shadow | ui applies it as `box-shadow`; blur needs `backdrop-filter`, which a token cannot carry |
| cosmos `--font-mono` | none (Inter fallback) | JetBrains Mono | D9 asks for a mono font |
| cosmos heading weight | 600 | 400/500 from `packages/ui` base styles | weights are ui's; only 400/500 of Space Grotesk ship |
| mono 600 | used once (`law-tracker .v`) | not shipped | the browser uses 500; not worth another font file |

Status pills: clinical values are the design's `.pill.on/.plan/.road` colours; cosmos values are new
(violet / cyan / white tints) because option 3 has only outline badges.

## Fonts (self-hosted, DECISIONS.md D9)

Each `tokens.css` `@import`s the `latin` subset CSS of exactly the weights used; Vite copies the
woff2/woff files into the build. No request leaves the site.

| Theme | Package (exact version) | Weights | Licence (from the package's `LICENSE` file, checked 2026-09-26) |
|---|---|---|---|
| clinical | `@fontsource/ibm-plex-sans` 5.3.0 | 400, 500, 600 | SIL Open Font License 1.1 (Copyright 2019 IBM Corp.) |
| clinical | `@fontsource/ibm-plex-mono` 5.3.0 | 400, 500 | SIL Open Font License 1.1 (Copyright 2017 IBM Corp.) |
| cosmos | `@fontsource/space-grotesk` 5.3.0 | 400, 500 | SIL Open Font License 1.1 (Copyright 2020 The Space Grotesk Project Authors) |
| cosmos | `@fontsource/inter` 5.3.0 | 400, 500, 600 | SIL Open Font License 1.1 (Copyright 2016 The Inter Project Authors) |
| cosmos | `@fontsource/jetbrains-mono` 5.3.0 | 400, 500 | SIL Open Font License 1.1 (Copyright 2020 The JetBrains Mono Project Authors) |

The npm metadata of all five packages also says `OFL-1.1`. OFL allows bundling and self-hosting;
the font names are not used as product names.

## Slots

- Slots render **no text of their own**: labels and captions come from `packages/content`. Section
  numbers are CSS generated content from `data-n`, so both builds have identical HTML text (web
  test "identical visible text").
- `HeroVisual` renders `role="img"` with the content label; the canvas/SVG inside is `aria-hidden`;
  the caption is a sibling paragraph (outside the `role="img"` subtree, so it is read).
- **Clinical HeroVisual**: vanilla 2D canvas, started with `requestIdleCallback`. It draws one
  static frame first; the `requestAnimationFrame` loop runs only when motion is allowed, the stage
  intersects the viewport and the tab is visible. Colours and font are read from the tokens.
  Canvas text is limited to electrode names; the design's header and scale-bar words were dropped
  (copy lives in content).
- **Cosmos HeroVisual**: the server-rendered SVG is the fallback and the no-JS view. `import('three')`
  (npm `three@0.160.0`, never a CDN) happens only when the stage intersects the viewport AND WebGL
  is available AND reduced motion is off AND Save-Data is off AND `navigator.deviceMemory` is not
  <= 2. The loop pauses off-screen and in hidden tabs; `pagehide` disposes geometry, materials and
  the renderer (and `pageshow` from the bfcache re-arms the observer). Palette: `--color-accent`,
  `--color-secondary`, `--color-accent-ink` plus the design's pink `#F472B6` (not a token).
- CSP `script-src 'self'`: only Astro-bundled module scripts; no inline scripts or handlers, no
  eval/`Function`, no workers or blob URLs (checked by `contract.test.mjs`).
- Gradient ids in cosmos SVGs are numbered per page render (`Astro.locals`), so BrandMark can appear
  twice on a page.

## Measured (local build, 2026-09-26)

- cosmos home, initial JS: about 6 KB gzip (Nav 0.6, HeroVisual 4.9, AudienceTabs 0.6).
- lazy three chunk: 459 KB raw, 115 KB gzip (tree-shaken from `three.module.js`).
- clinical home, initial JS: about 4 KB gzip (HeroVisual 2.9).
