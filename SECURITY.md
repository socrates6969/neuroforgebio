# Security policy

Status: pre-launch. Nothing in this repository runs in production. Controls below are the M0 baseline
(BUILD-GUIDE 0.3, BLUEPRINT §8.1 and §8.7); items marked *(owner)* need an owner action on the hosting account.

## Reporting a vulnerability

Please follow our **[vulnerability disclosure policy](docs/security/VULN-DISCLOSURE.md)** (draft; scope, safe
harbour, response targets, 90-day coordinated disclosure). Do not open a public issue.

- **Security contact:** `security@<domain TBD>` *(owner: the domain and mailbox are not set up yet)*. Until it
  exists, report privately to the repository owner (Marius Carlsson) through the code host's private
  vulnerability reporting, once the owner enables it *(owner)*.
- `/.well-known/security.txt` (RFC 9116) is published with the website before any public launch (SEC-157).
- Coverage of the M0 security requirements: [docs/security/SEC-COVERAGE.md](docs/security/SEC-COVERAGE.md).

## Rules for contributors (humans and agents)

- **No neural or human-subject data in the repository, ever.** `.gitignore` excludes recording formats
  (`*.edf *.bdf *.nwb *.xdf *.set *.fif *.vhdr *.vmrk *.eeg *.mat ...`) and any `data/` directory, and
  `tools/repo-guard` fails CI if one is tracked. Tests use synthetic signals from `tools/synth`, generated at
  test time into ignored directories. `dev` and `staging` environments hold synthetic or public data only.
- **No secrets in the repository.** Secrets live in the cloud secret manager or CI secrets. `.env*`, `*.pem`,
  `*.key`, `*.tfvars` and OpenTofu state are ignored; repo-guard scans every tracked file for provider key
  formats (AWS, GitHub, Slack, Google, Stripe, Anthropic, OpenAI) and private-key blocks. A documented,
  non-secret example may carry the marker `repo-guard:allow-secret` on its line; reviewers must check it.
- **Minimal dependencies.** Repo tooling (`tools/copy-lint`, `tools/repo-guard`, `tools/dev`) has zero npm
  dependencies. Lockfiles (`pnpm-lock.yaml`, `uv.lock`, `Cargo.lock`) are committed. three.js is bundled, not
  loaded from a CDN (ADR 0009).
- **Infrastructure code is never applied by agents.** `infra/` is code only (ADR 0004).

## What CI checks (`.github/workflows/`, manual `workflow_dispatch` only until the owner enables triggers)

| Check | Job | Tool |
|---|---|---|
| Tracked data files, files > 5 MB, secrets, dispatch-only workflows (SEC-086/087) | `repo-guard` | `node tools/repo-guard/cli.mjs` (also local `lint`) |
| No stimulation/actuator API, inlet-only LSL, no device handles (SEC-090/091) | `repo-guard` | `node tools/hw-guard/cli.mjs` (also local `lint`) |
| SHA-pinned actions, no `pull_request_target`, read-only token, frozen installs (SEC-080/089) | `repo-guard` | `node tools/ci-lint/cli.mjs` (also local `lint`) |
| Secret scanning over git history (SEC-086) | `security` | gitleaks 8.30.1 + `.gitleaks.toml` (CI-only; opt-in pre-commit hook: docs/security/pre-commit.md) |
| Licences of browser-shipped packages (SEC-084) | `security` | `node tools/licence-check/cli.mjs` (also local `lint`) |
| Known vulnerabilities: critical/high with a fix, or CISA KEV, unless VEX (SEC-085) | `security` | `pnpm audit`, `pip-audit`, `cargo audit` + `tools/vuln-gate` + `security/vex/` (CI-only lookups) |
| CycloneDX 1.6 SBOM per artefact with `nfb:supportLevel`/`nfb:endOfSupport` (SEC-083) | `build-web`, `security` | `@cyclonedx/cdxgen` + `tools/sbom-props` |
| Signed release bundles + SLSA provenance, verified (SEC-081/082) | `release.yml` | cosign keyless, `actions/attest-build-provenance` (written, never run) |

## Hosting settings *(owner)*

Branch protection, CODEOWNERS review, secret scanning and push protection: the exact settings are listed in
[docs/security/branch-protection.md](docs/security/branch-protection.md). Nothing is applied yet.

## Planned (BLUEPRINT §8)

TLS 1.3, AES-256 at rest with KMS envelope encryption and per-subject data keys, RBAC with attribute checks,
WORM audit log, signed container images, yearly external penetration test (roadmap, budget item).
