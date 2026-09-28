# M4 board: public API + Python SDK (branch `feature/m4-api-sdk`)

Lead: nfb-build-lead-2 (second build lead). Parallel team: nfb-build-queen runs M5 in `neuro-worktrees/m5`.
Base: main @89c3ab9 (M0–M3). Worktree: `C:\Users\mariu\neuro-worktrees\m4` (own `.venv` via `uv sync --locked`, own `node_modules`).

## Workers

| Worker | Steps | Owns (write) |
|---|---|---|
| m4-api | 4.1, 4.6, 4.8, F2, 4.7 (flag-off only) | `openapi/`, `services/platform/**`, `apps/console/src/**` (keys UI, generated client), `tools/openapi-diff/` (new), migrations `0010m4_*`, `0011m4_*` |
| m4-sdk | 4.2, 4.3, 4.4, 4.5 | `core/nf-core/`, `bindings/python/`, `proto/` (read-mostly), `apps/web/src/pages/docs/**` + docs content, `tools/doc-snippets/` (new) |
| lead | board, report, shared files | `docs/hive/M4-*.md`, root `Cargo.toml`, root `pyproject.toml`, `.github/workflows/*`, `tools/hw-guard` rule paths |

Shared files are edited by the lead only; workers send the exact change they need.

## Coordination with M5 (nfb-build-queen)

- F2: both teams fixed it in parallel; M5's version is kept (see status).
- Migrations: after merging main (M5 @5b9cf63) the M4 revisions were renamed `0010m4_quotas_webhooks` -> `0011m4_early_access`, chained after `0009m5_phi` (single head).
- Root pyproject: M4 only appends (dev group, testpaths, pythonpath).
- CI: new jobs are `workflow_dispatch` only.

## Status

| Step | Status | Notes |
|---|---|---|
| 4.1 OpenAPI + contract tests + diff check | done (m4-api) | `openapi/v1.yaml` committed + drift test; route enumeration both ways (SEC-077); hypothesis contract fuzz over 57 ops + matrix responses validated vs spec (schemathesis not added: dep weight); `tools/openapi-diff` + baseline; problem+json forced-exception test (SEC-079); Deprecation/Sunset; GET /v1/runs, /v1/sweeps; console client regenerated from the spec, drift green |
| 4.2 nf-core crate | done (local), CI parts pending | a118f0a, 9e40ec3, 5e7d295. All 0.5 vectors pass; proptest canonicalisation + buffering; 2.7 network-cut test passes with nf-core (20 s local, 2 cuts, 11 retried RPC errors, server array == sent, max acquisition gap 0.078 s). CI-only: release build, `cargo deny`/`cargo audit` (not installed locally), 10-min run. Rust gRPC/HTTPS transport: planned (transports injected by the binding). |
| 4.3 PyO3 bindings + `neuroforge` | done (local), wheels CI-only | 9e40ec3. abi3 py3.12, debug `maturin develop` only. Website snippet executed as published (pinned to the real `eeg-basic@1.0.0`; 1.2.0 never existed). `sdk-wheels.yml`: wheels, clean-runner install, cosign + SLSA, no publish (never run). Release-notes template (SEC-134). |
| 4.4 LSL bridge (inlet-only) | done (local), 10-min CI-only | aa99ec1. pylsl inlet, `lsl_time_correction_ex`; one-host offset (true 0) within reported uncertainty; skewed sender stamps kept bit-exact end to end; offsets stored as measured. A non-zero inter-clock offset needs two hosts (not tested). |
| 4.5 Docs quickstarts | done (local), staging CI-only | 0694e99. /docs: 4 quickstarts (14 code blocks, all executed in-process), API reference generated from openapi/v1.yaml (drift test), changelog. Both builds + copy-lint + 49 web tests pass. |
| 4.6 Webhooks + SSE | done (m4-api) | HMAC-SHA-256 t+body, 5-min tolerance, rotation overlap 24 h, backoff retries; SSRF per-target tests + resolve-once pinning; SSE `/v1/runs/{id}/events`; sample verifier `services/platform/examples/verify_webhook.py`. Dispatcher scheduling = infra |
| 4.7 Early-access endpoint | code done, flag OFF (m4-api) | OWNER-GATED: route not mounted unless `NF_EARLY_ACCESS_ENABLED=true`; spec `x-nf-status: disabled`; tests force the flag on. No mailer, no privacy text, website form untouched |
| 4.8 Quotas, rate limits, key UI | done (m4-api) | storage 403 / active runs 429 problem+json; local token bucket (gateway part in `docs/platform/rate-limits.md`); console `#/api-keys`; revoked key: REST at once, SSE closed within 60 s (fake clock) |
| F2 | superseded by M5 | M4 had its own fix (8a6492c); on merging main @5b9cf63 the M5 implementation (4ddde86, incl. SEC-034a shred abort) was kept and the M4 duplicate test file dropped. Main's tests cover revoke/expiry mid-stream and F5 |
