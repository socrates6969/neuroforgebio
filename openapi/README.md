# openapi

The public API contract (BLUEPRINT §4, BUILD-GUIDE 4.1).

| File | What |
|---|---|
| `v1.yaml` | OpenAPI 3.1 contract of `/v1`: every operation, typed responses, RFC 9457 errors, security, `webhooks`. |
| `baseline/v1.yaml` | The last published 1.x contract. `tools/openapi-diff` compares `v1.yaml` against it. |

## How it is kept true

- `v1.yaml` is generated from the platform's FastAPI routes plus the platform conventions
  (`services/platform/nf_platform/api/openapi_doc.py`) and committed:
  `python -m nf_platform.api.openapi_doc --write` (`--check` exits 1 when stale).
- Tests (`services/platform/tests/api/`): the committed file equals the generated one; every route
  the app serves is documented and every documented operation is served unless marked
  `x-nf-status: disabled` (SEC-077); every response in the authz matrix and in the hypothesis
  contract fuzz test validates against this file; errors are `application/problem+json` without
  internals (SEC-079); hw-guard's surface scan finds no hardware-control names (SEC-090).
- `python tools/openapi-diff/openapi_diff.py` fails on a breaking change unless `info.version` gets
  a new major version. Only additive changes within v1 (BLUEPRINT §4.3). After a release, copy
  `v1.yaml` to `baseline/v1.yaml`.
- The console's typed client (`apps/console/src/api/generated.ts`) and the SDK/docs read this file.

## Conventions

- `x-nf-action`: the authorization action (SEC-020). `x-nf-api-key-scope`: the scope an API key needs;
  operations without it (webhook management) refuse API keys.
- Errors: `#/components/schemas/Problem` for 401, 403, 404, 422, 429, 500 and `default`.
- Deprecation: `deprecated: true` + `x-nf-sunset`; responses then carry `Deprecation` (RFC 9745),
  `Sunset` (RFC 8594) and `Link: <changelog>; rel="deprecation"`. Minimum support window 12 months.
- `x-nf-status: disabled`: documented but not served by default (OWNER-GATED early access, 4.7).
- The title is brand-neutral on purpose: the company name is a brand token (BLUEPRINT §2.2).
