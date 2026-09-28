# apps/console (`@nf/console`)

React + TypeScript single-page console over the platform API (BLUEPRINT §3.8, BUILD-GUIDE 3.8):
login, projects and datasets, upload, recording viewer (pyramid window reads, canvas plot), runs,
sweep report, lineage explorer. Clinical theme tokens and self-hosted IBM Plex fonts from
`@nf/themes`; the product name comes from `@nf/content/brand.json` at runtime.

```sh
pnpm --filter @nf/console build        # vite build + dist/_headers + inline-code check
pnpm --filter @nf/console test         # tsc, vitest (jsdom), build, dist + drift + mock-IdP tests
node apps/console/scripts/gen-api.mjs  # regenerate the typed API client after API changes
pnpm --filter @nf/console test:e2e     # CI ONLY (Playwright + axe); see below
```

Runtime dependencies are only `react` and `react-dom` (MIT, exact pins) plus the workspace theme and
content packages; `tools/licence-check` now covers `apps/console` too.

## Configuration (build time)

| Variable | Default | Meaning |
|---|---|---|
| `NF_CONSOLE_OIDC_ISSUER` | `/mock-idp` | OIDC issuer (https). A path means the dev/e2e mock IdP on the console origin; a banner says so. A build with `NF_CONSOLE_STAGE` other than `preview` refuses the mock. |
| `NF_CONSOLE_OIDC_CLIENT_ID` | `nf-console` | Public client (no secret; PKCE). Redirect URI is the console root `https://<console>/`. |
| `NF_CONSOLE_OIDC_SCOPE` | `openid profile` | Scopes. |
| `NF_CONSOLE_OIDC_AUDIENCE` | empty | Optional `audience` parameter for IdPs that need it. |
| `NF_CONSOLE_API_BASE` | empty (same origin) | Platform API origin if not served under the console's `/v1`. |
| `NF_CONSOLE_STAGE` | `preview` | HSTS staging (SEC-151), as for the website. |

The issuer and API origins are the ONLY hosts added to `connect-src`. Pre-signed S3 upload URLs (an
object-store origin) would also need adding there when the S3 part backend is used; today the local
backend uploads parts through `/v1`.

## Security model

**Headers (SEC-150..156).** `dist/_headers` (and `_headers.json`) from `security-headers.mjs`: the
website's CSP (`default-src 'none'; script-src 'self'; style-src 'self'; ...; frame-ancestors 'none'`)
with no hashes at all, plus `require-trusted-types-for 'script'; trusted-types 'none'`; HSTS per
stage, Permissions-Policy, COOP/COEP/CORP, nosniff, DENY, `no-store` for the shell and `immutable`
for hashed assets. The postbuild step fails on any inline script, style, handler, `style=` or
`javascript:` URL (scanner reused from `apps/web/scripts/inline-check.mjs`). Fonts are files, never
`data:` (`assetsInlineLimit: 0`).

**Sessions (SEC-015), what a SPA can and cannot enforce:**

| Rule | Where it is enforced |
|---|---|
| Tokens never in storage or cookies | Console: memory only (`src/auth/oidc.ts`). A reload ends the session. Dist test + e2e check no `localStorage`/`sessionStorage`/`indexedDB`/`document.cookie`. The PKCE verifier, state and nonce also stay in memory: login runs in a popup that relays `?code&state` over a same-origin `BroadcastChannel`. |
| Access token <= 15 min | Console uses each access token for at most 15 min (clamped), then refreshes. **The IdP must also issue <= 15-min tokens**; the API rejects expired ones. |
| Refresh rotation + reuse detection | Console requires a new refresh token on every refresh and ends the session otherwise. **Reuse detection (replay revokes the family) is the IdP's job**; the mock IdP implements it and its test proves it. |
| Idle logoff 15 min | Console: no keyboard/pointer input for 15 min -> tokens dropped, refresh token revoked (RFC 7009). |
| Absolute lifetime 12 h | Console ends the session 12 h after sign-in, with or without activity. **The IdP session/refresh family must also expire at 12 h.** |
| Cookies `Secure; HttpOnly; SameSite=Strict; __Host-` | The console sets no cookies. Any cookie (IdP session, a future BFF) is the IdP's/BFF's configuration: owner item. |

**Role-based hiding is NOT enforcement.** `src/authz/can.ts` mirrors the server's matrix
(`src/api/authz.json`, generated from `nf_platform.auth.authorize`) using the *effective* roles from
`GET /v1/whoami`, only to avoid offering actions that would get a 403. The platform authorizes every
request (deny by default, tenant check, Postgres RLS). A test forces a hidden action and asserts the
server's 403 comes back; never remove a server check because the UI hides a control.

## Typed API client

`scripts/gen-api.mjs` runs `scripts/gen_openapi.py` with the repo `.venv` and writes `src/api/authz.json`
and `src/api/generated.ts` (schema types + an operation table with each route's `x-nf-action`), formatted
with the repo Prettier. Since M4 (4.1) the source is the committed contract `openapi/v1.yaml` (itself
drift-tested against the platform app); operations marked `x-nf-status: disabled` and CORS preflights
are skipped; `--print-openapi` prints the contract as JSON. `test/drift.test.mjs` regenerates in memory
and fails on any difference (skipped locally without `.venv`, required with `CI=true`).
`src/api/types.ts` only aliases generated types under the names the views use.

## Views

- Projects / datasets: paged lists; create forms only for roles that may create.
- Dataset: subjects -> sessions -> recordings; resumable upload (SHA-256 in the browser, parts PUT to
  the API's part targets, complete, poll until converted). The bearer token is sent only to `/v1/`
  URLs on the API origin, never to a part URL elsewhere.
- Recording: metadata, channels, viewer. The window request picks the smallest pyramid level with
  about 2 points per pixel and <= 250 000 JSON values; above level 0 it also draws the min/max
  envelope. A 422 "level must be in 0..N" is retried once at N.
- Runs: no list route exists in the platform yet, so the list shows runs started or opened in this
  session (memory only) plus open-by-ID; run detail polls until terminal, shows artifacts, the run
  record, cancel (writers) and "Open lineage".
- Sweeps: open by ID (no list route); report = variant-mean grid over the first two factors,
  sensitivity per factor, every run; every number links to its run(s).
- API keys (`#/api-keys`, 4.8): list with status, create (roles, scopes, expiry; the secret is shown
  once, from memory only), revoke with confirmation.
- Models (BUILD-GUIDE 6.6): paged model list with the taint status; model detail with its versions
  and, for the chosen version (newest by default, `?version=`), the taint panel
  (`retrain_required`: the consent-withdrawal deletion job(s) that caused it and whether deployments
  are blocked), intended use, use restrictions, the model card (task, inferences, evaluation,
  SEC-145 robustness measurements shown as "recorded, not claimed", SEC-143 privacy risk), code
  commit / pipeline versions / training-set size, and the training lineage in the lineage explorer.
  Deployment requests: every request of the model with its declared context, state (`approved`,
  `blocked` after a later taint, `refused`) and the server's reasons; a request form (declared
  purpose, setting, outputs, jurisdiction, behaviour influence, optional exception record) for
  roles that may request. The console never decides a deployment: EU AI Act Art. 5 settings
  (workplace, education) are offered so they can be declared honestly and refused by the platform
  with its reason. Stimulation, neuromodulation and actuator-control contexts are never offered
  (SEC-092); the API refuses and audits them if another client sends them, and such a stored
  refusal is shown readably. Reason codes of `registry.vocab` are rendered as text.
- Lineage: `GET /v1/provenance/{id}/lineage` up, down or both (merged); a keyboard listbox (arrows,
  Home/End, Enter re-roots) ordered along the data flow (raw_file -> convert -> recording -> run ->
  artifact) and a simple SVG graph of the same nodes.

## Tests

Local (`pnpm --filter @nf/console test`, run by `node tools/dev/tasks.mjs test` via `pnpm -r test`):
`tsc --noEmit`; vitest (jsdom, one fork) for OIDC/PKCE/session rules, API client, authz mirroring and
role hiding, lineage ranking + keyboard list, pyramid level choice, upload, sweep report, app shell;
then the build and node:test dist checks (no inline code, CSP safety, no storage/cookies, no eval, no
third-party URLs, self-hosted fonts, bundle budget JS <= 110 KB gzip), the OpenAPI drift test and the
mock-IdP protocol tests (PKCE, rotation, reuse detection).

CI only (`.github/workflows/console-e2e.yml`, dispatch-only, SHA-pinned, frozen installs):
`e2e/console.spec.ts` (upload a synthetic EDF from `tools/synth`, run `eeg-resample-features`, open
the lineage and see raw_file -> recording -> run -> artifact; zero CSP violations; same-origin
requests only; no cookies/storage; `crossOriginIsolated`; reload ends the session; viewer sees no
create/upload controls; an injected inline script is blocked), `e2e/a11y.spec.ts` (axe WCAG 2.1
A/AA on each view) and `e2e/models.spec.ts` (6.6 taint scenario: model_training consent, upload + run,
register a model version trained on the run's input recording, approve a deployment, the subject
withdraws, the DeletionJob flags the version; the console shows the model as retrain required with the
deletion job as the reason, the deployment as blocked, no control settings in the form, a new request
refused; axe on the model list and the tainted detail). The stack (`e2e/stack.py`) runs Postgres (pgserver), the API and a worker thread
in one process (the dev LocalKms is per process); `e2e/serve.mjs` serves `dist/` with its headers,
the mock IdP under `/mock-idp` and a `/v1` proxy. `e2e/mock-idp.mjs` is for development and tests
only and must never be deployed.
