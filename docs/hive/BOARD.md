# Build hive board (M0 + M1)

Queen: nfb-build-queen. Contracts: `docs/hive/CONTRACTS.md`. Status values: todo / doing / done / blocked.

| Step | Task | Owner | Status | Blockers / notes |
|---|---|---|---|---|
| 0.0 | Root skeleton (package.json, pnpm-workspace, .nvmrc, .editorconfig), contracts, board | queen | done | |
| 0.1 | Monorepo toolchains: pnpm, uv, cargo workspace stub, justfile, formatters, pinned versions | nfb-platform-eng | done | |
| 0.2 | CI skeleton (workflow_dispatch only) | nfb-platform-eng | done | owner enables triggers later |
| 0.3 | Security baseline: .gitignore data files, SECURITY.md, secret/data-file checks | nfb-platform-eng | done | |
| 0.4 | tools/copy-lint + fixtures | nfb-platform-eng | done | frontend + copywriter depend on CLI |
| 0.5 | docs/spec/hashing.md + spec/test-vectors + Python reference | nfb-platform-eng | done | |
| 0.6 | tools/synth synthetic generator (small) | nfb-platform-eng | done | |
| 0.7 | infra/ OpenTofu skeleton, code only, NEVER applied | nfb-platform-eng | done | |
| 1.1 | Token contract, clinical/cosmos tokens, contract + contrast tests | nfb-designer-3d | done | 15ec9d7 |
| 1.2 | packages/content, brand.json "NeuroForge Bio", copy fixes, sources | nfb-copywriter | done | commit 7743544; 18 tests pass, copy-lint clean; owner copy review pending |
| 1.3 | packages/ui components (tokens only), no-hex lint, gallery page | nfb-frontend | done | 43f0cfd; keyboard e2e CI-only; style lint + unit keyboard tests local |
| 1.4 | Clinical slots (EEG canvas etc.) | nfb-designer-3d | done | 15ec9d7 |
| 1.5 | Cosmos slots (three@0.160.0 lazy, SVG fallback) | nfb-designer-3d | done | 15ec9d7, 8d41d7c (bundle test) |
| 1.6 | THEME build, dist/clinical + dist/cosmos, canonical, robots, bundle test | nfb-frontend | done | apps/web/dist/{clinical,cosmos}; cosmos lazy-three test auto-enables when three is added to themes |
| 1.7 | Whitepaper page, figure islands, figures.json hash check, "In preparation" | nfb-frontend | done | queen: only P4 published (preliminary); P1 abandoned + P2 inconclusive hidden, kept as test fixtures |
| 1.8 | Secondary pages, law tracker, disabled early-access form, 404 | nfb-frontend | done | |
| 1.9 | Quality gate tests (Playwright/axe/Lighthouse = CI-only; link check local) | nfb-frontend | done | local linkcheck + js-size done; Playwright/axe/LHCI written, CI-only, not run |
| 1.10 | Deploy/publish | OWNER | gated | not in this hive's scope |

## Wave 2 (owner requirements 2026-09-26: security page, standards, legal pages, EN/NO)

| Step | Task | Owner | Status | Blockers / notes |
|---|---|---|---|---|
| S.1 | i18n EN (default) + NO bokmål in packages/content and apps/web (routes, lang, switcher) | nfb-web-sec | done (b60843f) | NO only for /security + legal; ~12 NO UI strings in ui.no.json need owner review |
| S.2 | /security page from docs/inputs/security/website-security-page.md (EN+NO), SEC-158 | nfb-web-sec | done (b60843f) | owner approval before publish |
| S.3 | Shared security headers for both builds (SEC-150, 150a, 152–156) + tests | nfb-web-sec | done (c896eec) | Playwright parts CI-only (e2e/security.spec.ts, not run) |
| S.4 | /.well-known/security.txt (SEC-157), placeholder fails a PUBLIC build | nfb-web-sec | done (c896eec) | domain + cosmos host TBD (.invalid placeholders) |
| S.5 | /legal/privacy, /legal/terms, /legal/cookies (EN+NO, DRAFT), footer links | nfb-web-sec | done (b60843f) | advokat review pending; noindex while draft |
| S.6 | M0 SEC items: 080–089, 001, 002; SEC-090/091 denylist guard | nfb-platform-eng | done | 2588037, 47c31a2, c37e6d1, 389d182; docs/security/SEC-COVERAGE.md. Local: 080 (lint), 083 (props), 084, 085 (gate logic), 086 (repo-guard), 087, 089, 090, 091, 001, 002. CI-only, never run: 081/082 release.yml, SBOM generation, audits+KEV, gitleaks. Owner 🔒: 088 settings, CODEOWNERS team, push protection, running release |
