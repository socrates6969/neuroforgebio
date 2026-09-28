# Review: chore/ci-site-hardening (queen, read-only, 2026-09-27)

Commits f14d7e6 (P1), 9cb7293 (P4), c01689c (P5), c56b918 (P3), 4ba3977 (P6), from main @12eb802. The worker was cut off by the usage
limit before reporting. **Nothing here is verified:** node and Python are banned under the owner hold, so no test, lint or build
has been re-run since the commits. The branch stays local (lead decision).

## Reviewed by reading the diffs (git diff only)

| Item | Verdict | Notes |
|---|---|---|
| P1 / APP-L3 | looks correct | `inputs.seeds` and `matrix.arch` reach `run:` only through `env:`; the seeds are validated with `^[0-9]{1,10}(,[0-9]{1,10}){0,31}$`; new ci-lint rules ban `${{ inputs.* }}` and `${{ github.event.* }}` in `run:`, plus `npx -y` and checkouts without `persist-credentials: false`; each rule has a fixture |
| P5 / APP-L7 | looks correct | `assertPublicReady` returns early only for `preview`; `launch` and `public` fail on placeholders |
| P6 / APP-L8 | looks correct | new zero-dependency `apps/web/indexing.mjs`; preview gives robots `Disallow: /`, `X-Robots-Tag: noindex, nofollow` (security-headers.mjs, so both themes get identical headers) and a meta robots tag on every page; launch/public keep the page-level `noindex` prop (gallery, 404, legal drafts); tests in `apps/web/test/indexing.test.mjs` |
| P4 / APP-L6 | **needs proof** | `pnpm.onlyBuiltDependencies: []` in the root package.json (pnpm 9 ignores it in pnpm-workspace.yaml, as the comment there says); the repo-guard test fails on any `requiresBuild` package not reviewed. An EMPTY allowlist is safe only if esbuild (Astro/Vite) and any native package still work without install scripts. **Owed:** an offline frozen install + both web builds + console build |
| P3 / APP-L5 | **fixed by file edits, unverified** | `persist-credentials: false` on every checkout: fine. c56b918 had made `@cyclonedx/cdxgen@12.8.4` a ROOT devDependency (+1,467 lockfile lines, so the worker ran `pnpm install` with network). **Decision (nfb-security + lead, 2026-09-27): isolate it.** Done as file edits: removed from the root package.json; new `tools/sbom-cdxgen` package (own lockfile, excluded from the workspace, CODEOWNERS = security role); the three SBOM steps (ci.yml build-web + security, release.yml build) install it with `pnpm install --dir tools/sbom-cdxgen --frozen-lockfile --ignore-scripts`, run `tools/sbom-cdxgen/node_modules/.bin/cdxgen` and `--exclude "tools/sbom-cdxgen/**"`. Those jobs have contents: read only, no secrets and no id-token. repo-guard checks that both lockfiles have integrity hashes and no git/tarball sources, that the scanner is excluded from the workspace, that it has its own lockfile, and that cdxgen is absent from the root lockfile |

**Note on P4:** the worker's comment in `tools/repo-guard/lib.mjs` says it verified the empty allowlist on 2026-09-27 with an offline frozen install plus both web builds (esbuild and sharp use prebuilt platform packages). That was apparently before the owner hold. The queen has not re-run it.

## Added after review (file edits, unverified)

- **APP-L4 ci-lint rule** (nfb-security): a job that uses a `secrets.*` value (other than GITHUB_TOKEN) must declare `environment:`. `SECRET_JOB_EXCEPTIONS` holds two entries, each with a reason and an expiry of 2026-10-31, after which the lint fails:
  - `multiverse-study.yml` job `study`;
  - `sdk-wheels.yml` job `docs-snippets` (M4 workflow).

## Merged in later

- **origin/main @90e56a6 (web/headers, SITE_HOST):** build.mjs had a comment conflict, resolved as a union; postbuild.mjs
  auto-merged. Web-headers' host rules build on `globalHeaders(stage)`, so the preview X-Robots-Tag is kept.
- **ci.yml build-web:** a last step rebuilds each theme with `SITE_HOST=cloudflare`, so `assertCloudflareLimits` runs on the
  real page set.
- **origin/main @c8d614c (T3: csp-check.mjs, /arena exception, default SITE_HOST=cloudflare):** merged.
  - postbuild step 4 fails the build when `checkCsp(dist)` finds anything its own `_headers` blocks.
  - The ci.yml build-web artefact now uses the default cloudflare layout. That is only the build default: no host
    is chosen and nothing is deployed.
  - The last step is a netlify build that must fail with "cannot serve the SEC-150 exception for /arena/" and
    "KEEP FAIL" when dist/<theme>/arena/index.html exists, and must succeed otherwise.
- **Slot run 2026-09-27 (bci-queen lane A):**
  - **Passed:** offline lockfile generation (this found the `--ignore-workspace` bug); the offline frozen install;
    ci-lint + repo-guard 32/32; lint; both builds; launch fails on placeholders; cloudflare.
  - **Not completed:** the full `tasks.mjs test` was killed by system memory pressure and is re-queued. The steps
    added after that run (the merge of main, the checkCsp gate, the netlify step) have not been re-run either.

## Owed before push/merge (all need node)

1. **Regenerate the lockfiles offline.** Until then repo-guard FAILS by design.
   - The root `pnpm-lock.yaml` still lists cdxgen from c56b918: `pnpm install --lockfile-only --offline`.
   - Generate `tools/sbom-cdxgen/pnpm-lock.yaml`: `pnpm install --dir tools/sbom-cdxgen --lockfile-only --offline`, using the store.
2. **Unit tests:** `node --test tools/ci-lint/test tools/repo-guard/test` (new tests: lockfile source policy, scanner isolation, the secret-environment rule with expiry) and the web tests (`apps/web/test/*`, incl. indexing, security and builds).
3. **Lint:** `node tools/dev/tasks.mjs lint` (ci-lint over every workflow, repo-guard, licence-check, prettier on the edited files).
4. **Builds:**
   - `pnpm install --frozen-lockfile --offline`, then both web builds at SITE_STAGE=preview and at SITE_STAGE=launch. The launch build must fail while the domain is a placeholder: that is P5 working.
   - The console build (P4 empty allowlist).
5. **One full run:** `node tools/dev/tasks.mjs test`.
6. **In CI (owner dispatch):** the three SBOM steps actually find and run the isolated cdxgen, and `--exclude` keeps the scanner out of the SBOMs.

## Out of scope (owner)

P2: the GitHub environments with required reviewers; the ci-lint rule above enforces them once they exist. P7: host choice plus a header smoke test on the preview URL.

## Parked homepage item (lead decision 2026-09-27)

P6's per-page preview robots meta is dropped. It needed an edit to `apps/web/src/layouts/Base.astro`, which renders
the home page, and the owner's "no homepage edits" directive (guarded by `apps/web/test/homepage.test.mjs`) covers
Base.astro even when the effect is preview-only. Base.astro is back to main. Preview builds stay non-indexable
through the two remaining layers, both asserted by `apps/web/test/indexing.test.mjs`: `X-Robots-Tag: noindex, nofollow`
on every response (`_headers` and `_headers.json`) and robots.txt `Disallow: /`. Pages with Base's `noindex` prop
(gallery, 404, legal drafts) keep their meta tag unchanged. The meta layer waits on the owner, together with the
Base.astro SEO proposal (`docs/hive/SEO-BASE-PROPOSAL.md`); the lead keeps the owner's decision list.
