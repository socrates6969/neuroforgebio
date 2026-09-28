# Toolchain (BUILD-GUIDE 0.1)

| Toolchain | Pin | Where |
|---|---|---|
| Node | 22 (`.nvmrc`, `package.json#engines` `>=22 <23`) | pnpm 9.15.0 (`packageManager`) |
| Python | 3.12 (`pyproject.toml` `requires-python = "==3.12.*"`, `.python-version`) | uv project, `uv.lock` committed |
| Rust | 1.95.0 + rustfmt + clippy (`rust-toolchain.toml`) | cargo workspace `Cargo.toml`, crate `core/nf-core` |
| Formatters | Prettier 3.9.9 (`.prettierrc.json`), Ruff (`[tool.ruff]`), rustfmt (`rustfmt.toml`) | EditorConfig for everything else |

## Entry points

`just` is optional. Every recipe delegates to `tools/dev/tasks.mjs`, so these are equivalent:

| just | without just |
|---|---|
| `just lint test` | `node tools/dev/tasks.mjs lint` and `... test` (or `pnpm lint`, `pnpm test`) |
| `just THEME=cosmos build-web` / `just build-web cosmos` | `pnpm build:web:cosmos` / `node tools/dev/tasks.mjs build-web cosmos` |
| `just fmt` | `node tools/dev/tasks.mjs fmt` |

`lint` = repo-guard, hw-guard (SEC-090/091), ci-lint (SEC-080/089), licence-check (SEC-084, when `node_modules` exists), copy-lint on `packages/content`, Prettier check, Ruff check + format check, `cargo fmt --check`. See `docs/security/SEC-COVERAGE.md`.
`test` = node:test suites of the zero-dependency tools, `pnpm -r test` for workspace packages, pytest, `cargo test` (debug).
Locally a missing tool (no `node_modules`, no `.venv`) is skipped with a warning; with `CI=true` it fails.
`--skip=rust,python,web,prettier` skips a toolchain.

## Python: uv (decision)

uv is not installed globally on the dev PC. It is installed **inside the project venv** and listed in the `dev`
dependency group, so `uv sync` never removes itself:

```sh
# one-time bootstrap (Windows)
C:\Users\mariu\AppData\Local\Programs\Python\Python312\python.exe -m venv .venv
.venv\Scripts\python.exe -m pip install uv
.venv\Scripts\uv.exe sync --locked          # numpy, pytest, ruff, uv
.venv\Scripts\python.exe -m pytest
```

CI uses `astral-sh/setup-uv` and `uv sync --locked`. The `readers` group (MNE, pynwb, pyxdf) is CI-only
(`uv sync --locked --group readers`); it is not installed locally because of RAM.

## Rust

`.cargo/config.toml` sets `build.jobs = 1` (≈3 GB free RAM). Debug builds only on the dev PC; release builds
and wheels are CI-only.

## Line endings

`.gitattributes` forces LF (`* text=auto eol=lf`) because `core.autocrlf` is on for this clone; test
fixtures and test vectors depend on exact bytes.
