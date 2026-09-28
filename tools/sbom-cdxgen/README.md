# tools/sbom-cdxgen: isolated SBOM scanner (CI only)

`@cyclonedx/cdxgen` pinned to 12.8.4. It lives in its own package, **outside the pnpm workspace** (`pnpm-workspace.yaml`
excludes it), with its **own `pnpm-lock.yaml`**. Its large dependency tree therefore never lands in a developer install
(APP-L5; nfb-security decision, 2026-09-27).

## Rules (nfb-security conditions)

1. **Install.** It is installed only in the CI SBOM steps (`ci.yml` jobs `build-web` and `security`, and `release.yml`
   job `build`) with `pnpm install --dir tools/sbom-cdxgen --ignore-workspace --frozen-lockfile --ignore-scripts`.
   **`--ignore-workspace` is required.** Without it, pnpm walks up to the repository's `pnpm-workspace.yaml` and installs
   the root workspace instead of this package.
2. **Those jobs:**
   - `persist-credentials: false` on the checkout;
   - top-level `permissions: contents: read` (no job-level write scopes);
   - no secrets and no `id-token`.
3. **Lockfile checks.** `tools/repo-guard` checks `tools/sbom-cdxgen/pnpm-lock.yaml`:
   - it exists;
   - every package has an `integrity` hash;
   - there are no git or tarball sources.
4. **Ownership.** CODEOWNERS gives this folder to the security role.

The scanner's own files are excluded from the scanned SBOMs (`--exclude "tools/sbom-cdxgen/**"`).

## Updating the lockfile

Regenerate it offline from the local pnpm store, and have the security role review the diff:

```
pnpm install --dir tools/sbom-cdxgen --ignore-workspace --lockfile-only --offline
```

Changing the pinned version needs the network once; that fetch needs the lead's OK.
