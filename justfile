# Task entry points (BUILD-GUIDE 0.1). Every recipe delegates to tools/dev/tasks.mjs, so the same
# commands work without `just` via the root package.json scripts (`pnpm lint`, `pnpm test`, ...).
#   just lint test
#   just THEME=cosmos build-web      or   just build-web cosmos
set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

THEME := env_var_or_default("THEME", "clinical")

default: lint test

lint:
    node tools/dev/tasks.mjs lint

test:
    node tools/dev/tasks.mjs test

fmt:
    node tools/dev/tasks.mjs fmt

build-web theme=THEME:
    node tools/dev/tasks.mjs build-web {{theme}}

build-web-all:
    node tools/dev/tasks.mjs build-web clinical
    node tools/dev/tasks.mjs build-web cosmos

copy-lint +paths:
    node tools/copy-lint/cli.mjs {{paths}}

repo-guard:
    node tools/repo-guard/cli.mjs
