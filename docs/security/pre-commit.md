# Opt-in pre-commit hooks (SEC-086)

The hooks catch secrets before they reach git history. They are **opt-in** per clone; CI runs the same checks
regardless (`repo-guard` and `security` jobs in `.github/workflows/ci.yml`).

```sh
uv tool install pre-commit      # or: pipx install pre-commit
pre-commit install              # in the repository root; `pre-commit uninstall` removes it
pre-commit run --all-files      # optional first run
```

Hooks (`.pre-commit-config.yaml`):

| Hook | What it does | Needs |
|---|---|---|
| `gitleaks` (v8.30.1, pinned by commit) | scans the staged diff with `.gitleaks.toml` (default rules + allowlist for test vectors/lockfiles) | Go toolchain (pre-commit builds it). Without Go: install the gitleaks binary and change the id to `gitleaks-system` |
| `repo-guard` | provider key formats, private keys, tracked `.env`, neural-data files, files > 5 MB, dispatch-only workflows | Node 22 |
| `hw-guard` | stimulation/actuator denylist, inlet-only LSL, no device handles (only when proto/openapi/core/bindings/sdk change) | Node 22 |
| `ci-lint` | SHA-pinned actions, frozen installs (only when workflows change) | Node 22 |

**If a hook fires:** remove the secret, rotate it if it was ever real, and never bypass with `--no-verify`. A
documented non-secret example may carry `repo-guard:allow-secret` on its line; the reviewer checks it.
