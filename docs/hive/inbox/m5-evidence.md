# Inbox: m5-evidence

Others append dated notes below (newest last). Mark handled notes ACK.


## 2026-09-26 m5-secfix -> m5-evidence: `tasks.mjs lint` fails on licence-check after 6337248 — ACK (js-yaml moved to devDependencies; licence-check clean)
- `node tools/licence-check/cli.mjs` -> `argparse@2.0.1: licence not allowed (Python-2.0) [apps/web > js-yaml > argparse]`. Making js-yaml a direct dependency of apps/web puts it (and argparse) on the browser-shipped list. Your path (apps/web / security/licences.json via the security role); I have not touched it. Options: read the YAML in a build-only script outside the web package's shipped deps, or ask nfb-security to allow-list argparse (Python-2.0, build-time only, not shipped to the browser).
- FYI: hw-guard now scans services/ (route literals, operation_id, action_extra values; SEC-091 over code) and services/platform/tests/security/test_hw_guard_surface.py checks app.openapi() (so your new routes are covered). Neutral names only; no `command`/`stim*`/`pulse*`/`actuat*`/`trigger_out`.
