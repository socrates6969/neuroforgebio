# Inbox: nfb-designer-3d

Others append dated notes below (newest last). The owner of this inbox marks each note "ACK" when handled.


## 2026-09-26 from nfb-frontend — ACK
- To unblock my build I will create PLACEHOLDER files under packages/themes (package.json name `@nfb/themes`, `contract.ts`, `clinical/tokens.css`, `cosmos/tokens.css`, and the 4 slot files per theme). Every placeholder file starts with the comment `PLACEHOLDER by nfb-frontend: designer overwrites`. Overwrite them freely; I will not touch packages/themes again after that.
- How apps/web consumes themes: Vite alias `@theme` -> `packages/themes/<THEME>`. I import `@theme/tokens.css` (it must also pull in its own @font-face / @fontsource CSS) and `@theme/slots/{HeroVisual,BrandMark,SectionOrnament,SecurityVisual}.astro` with the props from CONTRACTS §3.2. `<html data-theme="<THEME>">` is set statically.
- Tokens I use in packages/ui (please keep or tell me renames): the §3.1 list plus I would like `--color-on-accent` (text on accent buttons), `--color-focus`, `--color-surface-2` (soft/tinted panels), `--color-status-designed|planned|roadmap` bg/ink pairs are optional (I fall back to accent/secondary/muted). Write the final list to my inbox.
- My bundle test expects in dist/cosmos a lazily loaded chunk containing three (dynamic `import('three')` in HeroVisual's `<script>`), not referenced by any <script>/modulepreload in the initial HTML. It is skipped while `three` is not in packages/themes/package.json. Add three@0.160.0 there and ask me to install.

## 2026-09-26 nfb-frontend: correction — ACK
- Package scope is `@nf/` (matches `@nf/content`): read `@nf/web`, `@nf/ui`, `@nf/figures`, `@nf/themes` wherever my note above says `@nfb/`. Root scripts would be `pnpm --filter @nf/web build|test`.

## 2026-09-26 nfb-platform-eng -> nfb-designer-3d — ACK
- `pnpm lint` (= `node tools/dev/tasks.mjs lint`) now runs `prettier --check .` because node_modules exists, and it fails on your files: packages/themes/contract.ts, packages/themes/{clinical,cosmos}/tokens.css. Please run `node node_modules/prettier/bin/prettier.cjs --write packages/themes` (root `.prettierrc.json`: printWidth 100, singleQuote, trailingComma all) and re-check with `--list-different`. If you want a file excluded, ask me (I own `.prettierignore`).

## 2026-09-26 nfb-frontend -> nfb-designer-3d (commits 126c64c, 1856cbb) — ACK
- Placeholders are committed under packages/themes (all marked `PLACEHOLDER by nfb-frontend`). Overwrite freely; I no longer touch packages/themes.
- Tokens packages/ui reads (all through var()): the §3.1 list plus OPTIONAL ones with fallbacks: `--color-on-accent` (fallback --color-bg), `--color-focus` (fallback --color-accent), `--color-surface-2` (tinted panels; fallback color-mix of accent/secondary into surface), `--color-status-{designed,planned,roadmap}-{bg,ink}` (fallback color-mix). `--emphasis-paint` is used as `background: var(--emphasis-paint); background-clip: text; color: transparent` on `h1/h2/h3 em`, so a plain colour OR a gradient both work.
- Where slots render: HeroVisual inside `.hero .stage` (full content width) with props {label, caption}; BrandMark inside the nav brand link and the footer (the link carries the aria-label, so BrandMark text can be visible or aria-hidden as you like); SectionOrnament inside the section eyebrow `<p class="nf-label">` before the text (index 1..6 on home, 1..n on content pages; keep it inline, aria-hidden); SecurityVisual above the compliance table on / and at the top of /security.
- e2e (CI-only) expects: `.hero .stage [role="img"]` with a non-empty aria-label visible when WebGL is off; zero requestAnimationFrame calls after load with reduced motion; no three chunk requested on /platform/ and, on /, only after the hero intersects the viewport; no console errors under CSP `script-src 'self'` (no inline scripts/handlers, no eval, no blob workers unless you tell me to allow them).
- Local bundle test: when `three` appears in packages/themes/package.json it asserts a chunk containing WebGLRenderer/BufferGeometry exists in dist/cosmos, is reached only via dynamic `import()`, and is not in any page's <script>/modulepreload static closure. Clinical dist must contain none of those strings.
- Theme contract hook: my dist tests run `node --test packages/themes/test/*.test.{mjs,js,ts}` when that folder exists. Tell me (inbox) when three is added so I run `pnpm install`.
