# Licence policy for browser-shipped code (SEC-084)

Status: DRAFT v0.1, 2026-09-26. Owner: the security role (placeholder, see `.github/CODEOWNERS`). Not legal advice;
nfb-legal reviews before the first public release.

**Scope.** Production `dependencies` (and `optionalDependencies`) of `apps/web` and `packages/*`, walked through the
installed `node_modules` tree. These packages end up in the static site that browsers download.
`devDependencies` (test runners, formatters, Playwright) are not shipped and are not checked by this gate; they are
still covered by the vulnerability gate (SEC-085) and the SBOM (SEC-083).

**Machine-readable source:** `security/licences.json`. The test `tools/licence-check/test/licence-check.test.mjs`
fails if the "Allowed" table below and the JSON differ.

**Check:** `node tools/licence-check/cli.mjs` (needs `pnpm install --frozen-lockfile`). Runs in CI (`security`
job) and in `node tools/dev/tasks.mjs lint` when `node_modules` exists. A GPL fixture proves it fails.

## Allowed

| SPDX ID | Why it is fine in a browser bundle |
|---|---|
| `MIT` | Permissive; keep the notice |
| `MIT-0` | Permissive, no attribution |
| `ISC` | Permissive; keep the notice |
| `0BSD` | Permissive, no attribution |
| `BSD-2-Clause` | Permissive; keep the notice |
| `BSD-3-Clause` | Permissive; keep the notice; no endorsement |
| `Apache-2.0` | Permissive with patent grant; keep NOTICE files |
| `Unlicense` | Public-domain dedication |
| `CC0-1.0` | Public-domain dedication (data, icons) |
| `OFL-1.1` | SIL Open Font License: self-hosted fonts (`@fontsource/*`) may be bundled, not sold alone |
| `BlueOak-1.0.0` | Permissive |
| `Zlib` | Permissive |

SPDX expressions are evaluated: `(MIT OR GPL-2.0-only)` passes (we choose MIT); `MIT AND GPL-2.0-only` fails.

## Denied in browser-shipped code

- Strong and network copyleft: `GPL-*`, `AGPL-*`, `SSPL-1.0`, `EUPL-*`, `OSL-3.0`.
- Weak copyleft: `LGPL-*`, `MPL-2.0`, `EPL-*`, `CDDL-*` (file-level obligations are hard to meet in minified bundles;
  ask the security role if one is unavoidable).
- Non-commercial or share-alike content licences: `CC-BY-NC-*`, `CC-BY-SA-*`.
- No licence field, `UNLICENSED`, or `SEE LICENSE IN ...` until reviewed.

## Build-only packages

Listed in `buildOnly`: the package's own licence is checked, but its dependency subtree is not, because it runs at
build time only and its output is our own code.

| Package | Reason |
|---|---|
| `astro` | Static site generator. Its transitive tree (e.g. `sharp`/libvips, LGPL) runs at build time; the shipped client runtime is Astro's own MIT code. |

## Exceptions

`exceptions` in `security/licences.json` maps `name@version` (or `name`) to a written reason, e.g. a package whose
`package.json` lacks a licence field but whose LICENSE file is MIT. Every exception needs a security-role review in
the PR (CODEOWNERS) and is re-checked when the version changes.

## Other dependency rules (SEC-084, enforced by review)

- A new **direct** dependency needs a reviewer from the security role (CODEOWNERS on manifests and lockfiles) and
  the dependency-review checkbox in the PR template.
- Denied: packages with no release in 24 months (unless vendored and reviewed); install scripts from unknown
  publishers; scripts loaded from a CDN at runtime (ADR 0009: bundle, never CDN).
