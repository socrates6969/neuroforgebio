# Build hive: shared contracts (M0 + M1)

Queen: `nfb-build-queen`. Workers: `nfb-platform-eng`, `nfb-frontend`, `nfb-designer-3d`, `nfb-copywriter`.
Everyone reads this file first.

**Communication (file mailboxes).** Workers run as subagents and cannot message each other by name. To tell another worker something, APPEND a dated note to `docs/hive/inbox/<their-name>.md` (queen: `docs/hive/inbox/queen.md`). Re-read your own inbox at the start of each major step and before finishing; mark handled notes `ACK`. Inbox files are uncommitted scratch until the queen commits them; never `git add` another worker's inbox. To change a contract, write to the path owner's inbox AND the queen's before editing.

Worktree: `C:\Users\mariu\neuro-worktrees\build` (branch `build/m0-m1`). Monorepo at the repo root (BLUEPRINT §11), next to the existing docs.

## 1. Path ownership (only the owner edits; others ask via the owner's inbox file)

| Path | Owner |
|---|---|
| root `package.json`, `pnpm-workspace.yaml`, `justfile`, `pyproject.toml`, `Cargo.toml`, `rust-toolchain.toml`, `.editorconfig`, `.gitignore`, formatter configs | nfb-platform-eng |
| `.github/workflows/**` (workflow_dispatch ONLY, no push/PR triggers) | nfb-platform-eng (frontend may ask for web jobs) |
| `tools/copy-lint/**`, `tools/synth/**`, `docs/spec/**`, `spec/test-vectors/**`, `core/**`, `infra/**`, `SECURITY.md`, `docs/adr/**` | nfb-platform-eng |
| `packages/content/**` (all copy, `brand.json`, schema, loader, content tests) | nfb-copywriter |
| `packages/themes/**` (`contract.ts`, `clinical/`, `cosmos/`, token + contrast tests) | nfb-designer-3d |
| `apps/web/**`, `packages/ui/**`, `packages/figures/**`, bundle/theme/canonical tests | nfb-frontend |
| `docs/hive/**` | queen (workers may append to their own row in BOARD.md) |

## 2. Toolchain rules

- Node 22: `C:\Users\mariu\.local\node22\node_modules\node\bin` must be FIRST on PATH for pnpm/npx. In Git Bash:
  `export PATH="/c/Users/mariu/.local/node22/node_modules/node/bin:$PATH"` then `npx -y pnpm@9.15.0 ...`. Check `node -v` prints v22.
- **Only nfb-frontend runs `pnpm install`** (one install at a time; RAM is ~3 GB). Others add deps to their `package.json` and message nfb-frontend to install.
- Python: `C:\Users\mariu\AppData\Local\Programs\Python\Python312\python.exe`. uv is not installed; nfb-platform-eng decides (pip-install uv into a venv, or document uv as CI-only).
- Rust: `CARGO_BUILD_JOBS=1`, debug builds only.
- No Playwright browser installs, no heavy suites locally. Write those tests, tag them CI-only.
- Never `cd` in shared shells: absolute paths and `git -C C:/Users/mariu/neuro-worktrees/build`.
- Commits: only stage your own paths (`git -C ... add <your paths>`; never `git add -A`). On `index.lock` errors wait a few seconds and retry. Message format: `<area>: <what>` plus final line
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Author stays Marius Carlsson (already configured). Do NOT push; the queen pushes.
- Never deploy, publish, register, sign up, spend, or contact anyone.

## 3. Interfaces

### 3.1 Semantic tokens (designer defines values; everyone else uses only these names)
`packages/themes/contract.ts` exports `REQUIRED_TOKENS`. Starting list (BLUEPRINT §2.2):
`--color-bg --color-surface --color-ink --color-muted --color-accent --color-accent-ink --color-secondary --color-line --emphasis-paint --font-display --font-body --font-mono --radius-card --motion-duration --motion-ease --elevation-card`.
Designer may add tokens (e.g. `--color-on-accent`, `--color-focus`, spacing) but must write the final list to nfb-frontend's inbox.
Files: `packages/themes/clinical/tokens.css` scoped to `[data-theme="clinical"]`, `packages/themes/cosmos/tokens.css` scoped to `[data-theme="cosmos"]`. Fonts are self-hosted (D9) via `@fontsource/*` packages or files under `packages/themes/<theme>/fonts/`; never Google Fonts at runtime.

### 3.2 Slots (max 4 files per theme under `packages/themes/<theme>/slots/`)
`HeroVisual.astro`, `BrandMark.astro`, `SectionOrnament.astro`, `SecurityVisual.astro`. Island JS lives in the component's `<script>` (Astro bundles it). Props (typed in `contract.ts` as `SlotContract`):
- `HeroVisual { label: string; caption?: string }` renders `role="img" aria-label={label}` wrapper, canvas/WebGL inside with `aria-hidden="true"`.
- `BrandMark { name: string }`, `SectionOrnament { index?: number }`, `SecurityVisual { label: string }`.
Clinical: no `three` import anywhere. Cosmos: `import('three')` dynamically, only when visible + WebGL + no reduced motion + no Save-Data; SVG fallback rendered first. `three@0.160.0` is a dependency of `packages/themes` only.

### 3.3 Theme resolution (frontend)
`THEME=clinical|cosmos` env at build time; `apps/web` aliases `@theme` to `packages/themes/$THEME`, imports `@theme/tokens.css` and `@theme/slots/*`. Output: **`apps/web/dist/clinical` and `apps/web/dist/cosmos`** (decided by nfb-frontend; build with `pnpm --filter @nf/web build`, one theme with `node apps/web/scripts/build.mjs <theme>`). `<html data-theme>` set statically. Cosmos pages carry `rel=canonical` to the clinical host (placeholder origin from `brand.json` `domain`).

### 3.4 Content (copywriter)
`packages/content` exports a typed loader (`packages/content/src/index.ts`) returning content with `{brand}` already substituted from `brand.json`. The literal company name appears ONLY in `brand.json`. Every factual claim object has `source` (path in `market/` or a URL from those docs). Copywriter writes the draft shape to nfb-frontend's inbox early; frontend replies in copywriter's inbox if it needs changes; copywriter records it in `packages/content/README.md`.

### 3.5 Copy-lint (platform-eng)
CLI: `node tools/copy-lint/cli.mjs <files or dirs...>` scans `.json .md .mdx .html .astro`, prints `file:line: term`, exits 1 on any hit. Zero npm dependencies (node:test for its tests). Frontend wires it into `build` (lint content, then lint built HTML).

### 3.6 Research figures (frontend, step 1.7)
Read `research/somatosensory/code/results/*.json` and `code/figures/*.svg` read-only. Status "In preparation"; never label anything "verified". Do not invent or edit results.
