# M0 + M1 build report (branch `build/m0-m1`)

Date: 2026-09-26. Queen: nfb-build-queen. Workers: nfb-platform-eng (M0), nfb-copywriter (1.2), nfb-frontend (1.3, 1.6–1.9), nfb-designer-3d (1.1, 1.4, 1.5). Step 1.10 (deploy/publish) was not started; it is owner-gated.

## Passed locally (re-run by the queen after integration, Node 22.23.3 on Windows)

| Check | Command | Result |
|---|---|---|
| Clinical build | `node tools/dev/tasks.mjs build-web clinical` | exit 0, 14 pages in `apps/web/dist/clinical`, copy-lint on the built HTML is clean |
| Cosmos build | `node tools/dev/tasks.mjs build-web cosmos` | exit 0, 14 pages in `apps/web/dist/cosmos`, copy-lint on the built HTML is clean |
| Lint | `node tools/dev/tasks.mjs lint` | exit 0: repo-guard, copy-lint `packages/content`, Prettier, Ruff, `cargo fmt --check` |
| All tests | `node tools/dev/tasks.mjs test` | exit 0: tools 17/17, themes 14/14, ui 10/10, content 18/18, figures 6/6, web 17/17, pytest 72 passed + 5 CI-only skips, cargo 3/3 |
| Bundle test (1.6) | in `apps/web/test/bundle.test.mjs` | no three.js signatures in `dist/clinical`; the cosmos three chunk is loaded only through dynamic `import()`, not in any page's static script/modulepreload closure |
| Theme contract + contrast (1.1) | `packages/themes/test` | every required token in both themes, none extra; WCAG AA pairs pass in both themes (cosmos glass composited over `--color-bg`) |
| Copy-lint (0.4) | `node tools/copy-lint/cli.mjs` | fixture with every banned phrase fails with file:line; the allowlisted footer passes; content and both dists clean |
| Brand token (1.2) | content tests + `git grep NeuroForge -- apps packages openapi` | literal name only in `packages/content/brand.json`; a renamed `brand.name` flows through the loader |
| Text parity, canonical, robots, slot count (1.6) | web tests | identical extracted text in both builds; cosmos pages carry `rel=canonical` to the clinical origin; robots.txt per build; 4 slots per theme |
| Figure hash gate (1.7) | figures tests | a one-byte change to a pinned result file fails the build |
| Hashing spec (0.5) | pytest + cargo | Python reference reproduces every vector; the Rust stub (`core/nf-core`) reproduces every ID vector in `spec/test-vectors/ids.json` |
| Synthetic data (0.6) | pytest | PSD peak within one bin of the injected frequency; deterministic by seed; EDF/BDF/BrainVision round-trips and XDF structure checked locally |
| Link check (1.9) | `apps/web/scripts/linkcheck.mjs` (in web tests) | zero broken internal links in both builds |
| Third-party requests | grep of both dists | no jsdelivr / googleapis / gstatic / unpkg URLs; fonts self-hosted (D9) |

Measured JS (gzip, `apps/web/scripts/js-size.mjs`): clinical home 3.80 KB initial (budget 60 KB); cosmos home 5.78 KB before the hero is visible (budget 60 KB), plus 113.5 KB lazy three.js after the hero is visible.

## CI-only (written, not run locally; all workflows are `workflow_dispatch` only until the owner enables triggers)

- Playwright: visual snapshots 360/768/1440 × 2 themes, axe, keyboard (tabs, mobile menu), WebGL-disabled fallback, reduced motion (no animation frames), network log (three chunk only after the hero is visible, no jsdelivr), no horizontal scroll at 360 px.
- Lighthouse CI with the JS budgets above.
- MNE / pynwb / pyxdf open-tests for synthetic files; NWB/XDF/BDF readers group.
- `tofu validate` / plan for `infra/` (code only, never applied).
- gitleaks secret scan, CycloneDX SBOM, npm/pip/cargo audits.
- "A PR that breaks a test is blocked" and branch protection need the owner to enable CI triggers and required checks.

## Queen decisions taken during integration

- **Whitepaper figures:** the public manifest now shows only P4 (pooling capacity, PASS in `RESULTS_P3_P4.md`, labelled "preliminary"). P1 (H3 ABANDONED) and P2 (INCONCLUSIVE) were removed from the page under the whitepaper verification gate. They remain as test-only fixtures in `packages/figures/test/fixtures/unpublished.figures.json`, so the line and scatter renderers stay tested. Re-adding a manifest entry restores a figure.
- Prettier formatting applied to `packages/content` (formatting only).

## Open issues for the owner

1. **Copy review pending** (`packages/content/README.md`). The copywriter's questions: (a) removed "Sign in", "Book a demo", "Start free" and "Talk to us", and every "Join…" CTA is disabled with "opens soon"; (b) the compliance heading is "Neural data is sensitive. Our design starts there."; (c) law-tracker rows for Montana, the MIND Act and other bills are `verified: false`; check the paraphrases against `market/regulation.md`.
2. **Design deviations** for review in `packages/themes/README.md`: clinical emphasis colour, dark on-accent in cosmos, shadow instead of blur for elevation, all made to meet the AA contrast bar.
3. **Domain placeholder:** `brand.json` uses `neuroforge-bio.invalid`; cosmos canonical tags point there. Set the real domain before step 1.10.
4. **Before any public release (1.10, owner):** name clash check clean (`market/names.md`), hosting and domain, security headers (CSP `script-src 'self'`, HSTS, Referrer-Policy) on the host, and a written go/no-go.
5. The early-access form stays disabled until step 4.7 (endpoint and privacy policy).
6. Tooling note: in Git Bash, prepending the Node 22 folder to PATH still resolves `node` to v24 (a `node` stub file). Call `node.exe` by full path, or use PowerShell (see `docs/dev/toolchain.md`). uv lives inside `.venv`, not globally.
7. Nothing was pushed to `main`, deployed, published or purchased.

## Wave 2 (owner requirements, 2026-09-26): security page, security standards, legal pages, EN/NO

Workers: nfb-web-sec (S.1–S.5), nfb-platform-eng (S.6). Inputs snapshot: `docs/inputs/` (security + legal sources copied from the main checkout). Re-verified by the queen: both builds exit 0, `tasks.mjs lint` 0, `tasks.mjs test` 0 (tools 69, web 42, content 25, ui 10, figures 6, themes 14, pytest 72 + 5 CI-only skips, cargo 3).

- **i18n:** English at `/`, Norwegian bokmål under `/no/` (`lang="nb"`, hreflang en/nb/x-default). NO exists only for /security and the three legal pages; there is no machine-translated marketing copy. About 12 NO UI strings (`ui.no.json`) need owner review.
- **/security (SEC-158):** built from `website-security-page.md` (EN + NO), one page for both themes, with the anchors from the copy. Owner approval is needed before publishing.
- **Headers (SEC-150, 150a, 152–156):** one shared config, `apps/web/security-headers.mjs`, is emitted as an identical `_headers` file in both builds. The CSP has no unsafe-* and no third-party hosts. There is zero inline script/style, and a post-build check fails on any unhashed inline code. HSTS is staged by `SITE_STAGE`: preview 300, launch 86400, public 2y + includeSubDomains + preload.
- **security.txt (SEC-157):** generated per build with Expires = build date + 180 days. It is identical across builds except Canonical. `SITE_STAGE=public` fails the build while any placeholder domain remains.
- **Legal:** /legal/{privacy,terms,cookies} (+ /no/) carry a DRAFT banner and are noindex. The footer reads "Privacy · Terms · Cookies". A test proves that built JS writes no cookies or web storage. The early-access form stays disabled.
- **M0 SEC items:** coverage table in `docs/security/SEC-COVERAGE.md`.
  - Local tests: 001, 002, 080, 083, 084, 085 (gate logic), 086, 087, 089, 090, 091.
  - CI-only, never run: 081/082 (`release.yml` with cosign + SLSA), SBOM generation, audits + KEV, gitleaks.
  - Owner-gated 🔒: 088 branch protection, the CODEOWNERS security team, push protection, CI triggers.
- **CI-only web tests (written, not run):** `apps/web/e2e/security.spec.ts` covers zero CSP violations, `crossOriginIsolated`, the cosmos hero under COEP, same-origin requests, and no cookies or storage.
- **Copy-lint:** Norwegian negations were added. One reviewed exact-phrase allowlist entry exists ("certified US recipients" in the privacy draft, describing third parties). The banned-term list is unchanged.

Open for the owner:
- The real domain and cosmos host (placeholders are `.invalid`).
- Review of the NO UI strings.
- `.npz` research results are not banned by repo-guard (2 files are tracked).
- The imprint duty under ehandelsloven is UNVERIFIED in the terms draft; this is a question for nfb-legal.
- The hw-guard `command` rule will flag `std::process::Command` in a future Rust build script.

## Step 1.11 (lead follow-up, 2026-09-26)

Items 1–5 were already on the branch at `677359b` (wave 2 above). The queen re-checked them: the sources in `C:\Users\mariu\neuro-company\security\` and `legal\website\` are byte-identical to the snapshot in `docs/inputs/`, and `git grep "Marius R."` finds nothing.

New in 1.11:
- **Hero formats line fix.** "Designed forBIDS" is now "Designed for BIDS" in both themes (`packages/ui/src/components/Hero.astro`). The regression test `apps/web/test/formats.test.mjs` failed against the old build and passes after the fix.

### Website SEC IDs (SECURITY-REQUIREMENTS §A.2) mapped to implementation and tests

| SEC | Implemented in | Local test (passes) | CI-only (written, not run) | Owner-gated |
|---|---|---|---|---|
| 150 CSP | `apps/web/security-headers.mjs` → `dist/<theme>/_headers` | `security.test.mjs`: exact CSP; the gate fails on unsafe-* or any non-self host | `e2e/security.spec.ts`: zero CSP violations on every page (EN + NO) | enforced at public launch (1.10) |
| 150a inline code | Astro bundled scripts, `inlineStylesheets: 'never'`, `scripts/inline-check.mjs` | no inline script/style/handler/style attribute in either build; an injected fixture fails postbuild | | |
| 151 HSTS | staged by `SITE_STAGE` (preview 300 / launch 86400 / public 63072000 + includeSubDomains + preload) | value per stage | | preload submission 🔒 |
| 152 Permissions-Policy | shared config | header snapshot on every HTML page | | |
| 153 Referrer-Policy, nosniff, X-Frame-Options DENY | shared config | header snapshot | | |
| 154 COOP / CORP / COEP require-corp | shared config | header snapshot | `crossOriginIsolated === true` on `/`; cosmos hero (WebGL + fallback) under COEP | |
| 155 no third-party requests | self-hosted fonts and three.js | dist grep for third-party hosts; no cookie or web-storage writes in built JS | network log: every request is same-origin | |
| 156 cache | immutable hashed assets, no-cache HTML | one value per path | | |
| 157 security.txt | `scripts/security-txt.mjs` → `/.well-known/security.txt` | RFC 9116 fields; Expires = build date + 180 d; identical across builds except Canonical; a `SITE_STAGE=public` build fails on placeholders | | real domain 🔒 |
| 158 /security page | content from `website-security-page.md` (EN + NO), one page for both themes | copy-lint, text parity, i18n key parity (`i18n.test.mjs`) | | owner approval before publishing 🔒 |
| 160 TLS / hosting | not implemented (hosting does not exist yet) | | | 1.10 🔒 |

The M0 SEC IDs (080–091, 001, 002) are mapped in `docs/security/SEC-COVERAGE.md`.

## Step 1.12 (nfb-legal and nfb-security follow-ups, 2026-09-26)

- **Company information page (ehandelsloven § 8, nfb-legal).**
  - New pages `/legal/company` ("Company information") and `/no/legal/company` ("Selskapsinformasjon"), linked from the footer in both languages.
  - Content: name, address, e-mail, business register, org.nr., VAT (MVA) status and authorisations, all as placeholders until the AS is incorporated.
  - Both pages carry the DRAFT banner and noindex.
  - The source (`docs/inputs/legal-website/company-information.{en,no}.md`) was transcribed from nfb-legal's message; nfb-legal owns the text.
  - The updated terms-of-use drafts (§ 8 citation, line 51) were re-imported.
- **Copy-lint allowlist scoped to a path (nfb-security).**
  - Allowlist entries may now carry `paths`.
  - "certified US recipients" applies only to the privacy-policy pages; elsewhere it still fails, and a test covers both cases.
- **SEC-COVERAGE.md.** Added rows for SEC-150, 150a and 151–158, with evidence and a local vs CI-only split. `.npz` is recorded as a SEC-087 gap. The hw-guard narrowing proposal is recorded as not applied, pending the owner's written OK.
- **Verification (queen):** both builds exit 0; `tasks.mjs lint` 0; `tasks.mjs test` 0 (web 44, content 25, tools 70, pytest 72, cargo).
