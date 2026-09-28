# Branch protection and hosting settings (SEC-088, SEC-086, SEC-089) 🔒

Status: **NOT APPLIED.** These are the settings the owner (Marius Carlsson) applies on the code host when the
repository is created. No agent creates, changes or reads hosting settings. After applying them, the owner exports
them and commits the export next to this file (see "Evidence").

## 1. Ruleset for `main` (Settings → Rules → Rulesets, target: default branch)

| Setting | Value | SEC |
|---|---|---|
| Restrict deletions | on | 088 |
| Block force pushes | on | 088 |
| Require signed commits | on (SSH or GPG signing keys for every committer, agents' commits included) | 088 |
| Require a pull request before merging | on; required approvals **1** | 088 |
| Dismiss stale approvals on new commits | on | 088 |
| Require review from Code Owners | on (`.github/CODEOWNERS`; replace the `@PLACEHOLDER-ORG/...` teams first) | 084, 088 |
| Require approval of the most recent reviewable push | on | 088 |
| Require conversation resolution | on | 088 |
| Require status checks to pass | on; strict (branch up to date) | 088 |
| Required checks | `repo-guard`, `lint (ubuntu-latest)`, `test (ubuntu-latest)`, `python`, `rust`, `build-web (clinical)`, `build-web (cosmos)`, `security` | 080–087, 089–091 |
| Bypass list | empty (the owner does not bypass either; emergency changes go through a PR) | 088 |

**Two reviewers** on `services/platform/governance/`, `infra/`, `core/nf-core/src/crypto*`: add a second ruleset
targeting those paths (or a push ruleset with a file-path restriction) with required approvals **2**; CODEOWNERS
already lists two teams for them.

**Status checks need a trigger.** All workflows are `workflow_dispatch` only (Actions minutes are owner spend, and
`tools/repo-guard` enforces it). Required checks cannot run on pull requests until the owner decides to add a
`pull_request` trigger (never `pull_request_target`, SEC-089) to `ci.yml` and relaxes repo-guard's trigger rule in
the same PR.

## 2. Actions settings (Settings → Actions → General)

| Setting | Value | SEC |
|---|---|---|
| Workflow permissions | **Read repository contents** (default `GITHUB_TOKEN` read-only); do not allow Actions to create or approve PRs | 088, 089 |
| Allowed actions | "Allow select actions": GitHub-owned + the SHA-pinned list in `.github/workflows/` (checkout, setup-node, upload/download-artifact, attest-build-provenance, pnpm/action-setup, astral-sh/setup-uv, Swatinem/rust-cache, taiki-e/install-action, opentofu/setup-opentofu, sigstore/cosign-installer); require full-SHA pinning if offered | 089 |
| Fork pull request workflows | require approval for all outside collaborators; do not send secrets or write tokens to fork PR workflows | 089 |
| Artifact and log retention | 90 days | 083 |

## 3. Code security (Settings → Code security)

| Setting | Value | SEC |
|---|---|---|
| Secret scanning | on | 086 |
| Push protection | on (no bypass without a reason) | 086 |
| Private vulnerability reporting | on (until `security@<domain TBD>` exists) | 001 |
| Dependabot alerts | on (security updates optional; version updates off, lockfile changes go through the one installer) | 085 |
| Dependency graph | on | 083 |

## 4. Account

- Owner account and every maintainer: 2FA with a hardware key or passkey.
- A second owner (deputy) is added before the first external contributor.

## Evidence (manual audit each milestone)

After applying, the owner exports the settings and commits them here, unchanged:

```sh
gh api repos/<owner>/<repo>/rulesets > docs/security/hosting-export/rulesets.json
gh api repos/<owner>/<repo>/rulesets/<id> > docs/security/hosting-export/ruleset-main.json
gh api repos/<owner>/<repo>/actions/permissions > docs/security/hosting-export/actions-permissions.json
gh api repos/<owner>/<repo>/actions/permissions/workflow > docs/security/hosting-export/actions-workflow.json
```

Each milestone the security role compares the export with the tables above and records the result in the
milestone report. These commands are read-only; they are listed for the owner and are not run by agents.
