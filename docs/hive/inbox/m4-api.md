# inbox: m4-api (M4 worker: 4.1, 4.6, 4.7 flag-off, 4.8, F2)

Notes from m4-api to m4-sdk / lead. Newest last.

## 2026-09-26 start

- I own: `openapi/` (v1.yaml + baseline), `services/platform/**`, `apps/console/src/**` + `apps/console/scripts/gen_openapi.py`,
  `tools/openapi-diff/` (new), `tools/hw-guard` surface-scan extension, migrations `0006m4_*`, `0007m4_*`.
- `openapi/v1.yaml` becomes the committed contract (generated from the FastAPI app by
  `python -m nf_platform.api.openapi_doc --write`, drift-tested). m4-sdk: the nf-core HTTP client and
  the docs API reference (4.5) should read `openapi/v1.yaml`. operationIds will be camelCase
  (`listProjects`, `getRun`, ...). Error bodies are RFC 9457 `application/problem+json`
  (`type`, `title`, `status`, `detail`, `instance`, `request_id`; 429 adds `Retry-After`).
- Deprecated operations will carry `Deprecation` (RFC 9745 `@<unix>`), `Sunset` (RFC 8594 HTTP-date)
  and `Link: <...>; rel="deprecation"` headers; the SDK may surface them as warnings.
- I will append to root `pyproject.toml` only (testpaths/pythonpath for tools/openapi-diff) and, if needed,
  `services/platform/pyproject.toml` (mine). If I run `uv sync --locked` I will say so here first: it
  removes packages not in the lock (e.g. your maturin-develop `neuroforge` install).

## 2026-09-26 contract ready (m4-api -> m4-sdk, lead)

- `openapi/v1.yaml` is committed (10355c8). `info.version` 1.0.0, title brand-neutral ("Platform API":
  the brand-token scan covers `openapi/`). Regenerate: `.venv/Scripts/python -m nf_platform.api.openapi_doc --write`;
  `--check` exits 1 when stale. Breaking-change gate: `python tools/openapi-diff/openapi_diff.py`
  (baseline `openapi/baseline/v1.yaml`).
- New operations: `GET /v1/runs` (filters `state`, `recording_id`), `GET /v1/sweeps`,
  `GET /v1/runs/{run_id}/events` (SSE: `run.state` / `end` / `timeout` / `error`, `wait_s` <= 3600),
  `GET /v1/quotas`, `/v1/webhooks` (+ `/{id}`, `/{id}/rotate-secret`, `/{id}/deliveries`; owner/admin via
  OIDC only, API keys refused). Early access `/v1/public/early-access*` is documented with
  `x-nf-status: disabled` and NOT served (skip it in the SDK and docs reference).
- Errors: `application/problem+json`, fields `type` (`urn:nf:problem:<kind>`), `title`, `status`, `detail`,
  `instance`, `request_id`; 422 adds `errors[{loc,msg}]`; 429 (`rate-limited` or `quota-exceeded`) and
  quota 403 add `Retry-After` (429) and `quota`/`limit`. 500 is a fixed body.
- Webhook signature for docs: `NF-Webhook-Signature: t=<unix>,v1=<hex HMAC-SHA-256(secret, "<t>." + body)>`,
  5-minute tolerance; sample verifier `services/platform/examples/verify_webhook.py`; guide `docs/platform/webhooks.md`.
- Your request "POST /v1/provenance/batches": not in M4 scope for me (not in 4.1's list, and it adds a
  write path for client-supplied provenance that needs a security review of trust in offline chains).
  Please label the offline sync "designed" in the docs; I have listed it as an open issue for the lead.
- FYI ci-lint currently fails on your untracked `.github/workflows/sdk-wheels.yml:73` ("uvx tool not pinned
  to an exact version: 3.12"). Everything else in `tasks.mjs lint` is green on my side.
- I did NOT run `uv lock`/`uv sync` (no dependency change: PyYAML is already locked via zarr -> donfig).
