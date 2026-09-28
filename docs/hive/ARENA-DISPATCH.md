# Shipping Decoder Arena's real evaluator: one page for the owner

Today, `/arena` on the built site shows a plain "decoder loading unavailable" message and
runs no WebAssembly. This page is everything needed to change that: what the CI build
produces, where it lands, what it costs, and exactly what flips once it's there. No code
changes are needed for any of this — it's all already built and waiting on the two manual
approvals below.

## 1. What happens when you dispatch the build

Workflow: `.github/workflows/arena-wasm.yml` (branch `ci/arena-wasm-v2`, not yet on `main`
— merging it is step 0, see below). It only ever runs when someone manually triggers it
(`workflow_dispatch`) on GitHub-hosted runners — **this spends GitHub Actions minutes**,
which is why it's never triggered automatically.

What it does, in order:

1. Builds `tools/arena-core` to WebAssembly **twice**, from the same commit, with the
   pinned Rust toolchain and `Cargo.lock` locked. Both builds must produce byte-identical
   output or the job fails — this proves the build is deterministic, not just that it ran.
2. Checks every crate compiled into the `.wasm` comes from crates.io (not a private git
   fork or a local path) — a supply-chain check.
3. Verifies the output is a real WebAssembly module (correct magic bytes) and exactly the
   4 files expected (no unexpected extras).
4. Generates an SBOM (software bill of materials, CycloneDX format) listing the `.wasm`'s
   hash and every crate compiled into it.
5. **If nothing is committed yet** (today's state): prints a notice with the exact next
   step and stops — it does **not** commit anything on its own.
6. **If something is already committed**: re-checks that the committed files still match a
   fresh build from the current source, so a stale or hand-edited copy would be caught.

Nothing in this workflow touches the live site. It only produces a downloadable build
artifact (retained 90 days) and a pass/fail check.

## 2. Shipping the result (a second, separate approval)

The workflow's own output is not shipped automatically — on purpose, so a human looks at
it first. To actually ship it:

1. Download the `arena-wasm-a` artifact from the successful run (`out/` + `SHA256SUMS`).
2. Commit `out/*` as `apps/web/src/assets/arena/pkg/*` (4 files: `arena_core.js`,
   `arena_core_bg.wasm`, `arena_core.d.ts`, `arena_core_bg.wasm.d.ts`).
3. Commit `SHA256SUMS` as `security/arena-pkg.sha256`.
4. This commit needs a **security review** before it merges (nfb-security; the same review
   that approved the CSP exception in the first place, ADR 0014) — it's the point where a
   human confirms the downloaded bytes are what they claim to be.

Nothing hand-built on a developer's own machine may ship this way — only the artifact from
a green `arena-wasm.yml` run. `tools/repo-guard` enforces on every lint that a committed
`pkg/` and its manifest are present together and agree with each other; a follow-up run of
`arena-wasm.yml` after shipping re-confirms the committed copy still matches a fresh build.

## 3. What flips automatically once `pkg/` is committed and the site rebuilds

No further action needed for these — they're already wired to check for `pkg/`'s presence:

- **`/arena` stops being `noindex`.** `apps/web/src/lib/arena-pkg.mjs`'s
  `arenaPkgAvailable()` checks that both `arena_core.js` and `arena_core_bg.wasm` exist;
  `index.astro` uses that to decide the page's `noindex` meta tag and which markup renders
  (the real controls instead of the "unavailable" message).
- **The WebAssembly CSP exception activates, on `/arena` only.** The token is already
  listed, approved and dormant in `apps/web/csp-exceptions.json` — `scripts/csp-check.mjs`
  only actually emits it into the served header once it detects a page under `/arena/`
  genuinely reaching a `.wasm` file in the built site. Every other route keeps the
  stricter baseline CSP throughout, unchanged.
- **The evaluator runs.** `apps/web/src/assets/arena/loader.mjs` (rather than the current
  zero-WebAssembly stub) gets bundled, and Vite content-hashes both the glue and the
  `.wasm` into the site's normal hashed-asset output — same as any other JS/CSS file.

## 4. What does **not** flip automatically (separate, manual follow-ups)

- **The sitemap.** `/arena` isn't listed in `site.ts`'s `sitemapRoutes()` today, in either
  state. Adding it (if the sitemap is meant to include it) is a normal content change for
  whoever owns `site.ts`, unrelated to shipping the wasm build.
- **Hosting.** The `wasm-unsafe-eval` exception can currently only be served correctly on
  Cloudflare Pages or CloudFront (a per-path response-headers policy); a `SITE_HOST=netlify`
  build fails outright while the exception is active (nfb-security ruling, ADR 0014) until
  a separate Netlify-compatible approach is approved. This is input to the host decision,
  not something this workflow resolves.
- **Performance budgets.** web-perf's `/arena` budgets are measured on today's *stub*
  build (its JS/data are only ~1 KB there); the real decoder and wasm bundle will fail
  those budgets by design the moment `pkg/` lands. In the **same merge** as `pkg/`, get a
  measured budget adjustment from web-perf via `tools/web/perf-budget-adjustments.json` (a
  regenerated, evidence-based number) — never widen or silence the check to make it pass.

## 5. Before any of this can run

`ci/arena-wasm-v2` (the workflow itself) still needs to merge into `main` — as of this
writing it hasn't. Ask web-queen/nfb-build-queen for its current status before dispatching.

## Verified vs. not, plainly

Verified by running it, 2026-09-27, all on the *stub* (no-`pkg/`) state: `tools/arena-core`'s
own tests (11/11), the whole cargo workspace (107/107, `clippy -D warnings` clean),
the site's full web test suite (183+/184, 1 expected skip), the `packages/content` suite
(32/32), and lint (repo-guard, hw-guard, copy-lint, prettier) all clean — see
`docs/hive/ARENA-DESIGN.md` for the source commits these numbers are from. **Not yet
verified, because it hasn't run yet**: the `arena-wasm.yml` workflow itself, the real
(`pkg/`-present) site build, and the EXC-150-1 condition-7 browser tests
(`apps/web/e2e/arena-real.spec.ts`) — that file is written and ready but is inert
(self-skipping) until a real `pkg/` exists to test against.
