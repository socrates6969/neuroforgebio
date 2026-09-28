# M4 report: public API + Python SDK (branch `feature/m4-api-sdk`)

Date 2026-09-26. Lead: nfb-build-lead-2 (second build lead, parallel to nfb-build-queen on M5). Workers: m4-api (4.1, 4.6, 4.7 flag-off, 4.8, F2) and m4-sdk (4.2–4.5). Nothing deployed or published; no package uploaded; CI stays `workflow_dispatch` only.
The branch contains main @5b9cf63 (M5 merged, commit 17e84a8), so the lead can fast-forward or merge without conflicts.

## Verified locally by the lead after the M5 merge (Windows, Node 22, Py 3.12, Rust 1.95 debug)

- `tasks.mjs lint`: ok (repo-guard, hw-guard incl. `services/` and the new `--surface` scan, ci-lint, licence-check, copy-lint, Prettier, ruff, cargo fmt).
- `tasks.mjs test`: pytest **1006 passed, 13 skipped** (the skips are CI-only); tool node tests 83/83; workspace tests: themes 14, ui 10, figures 6, content 25, repo-guard 20, copy-lint 14, web 52 (all pass, after rebuilding both themes); cargo test green.
- SDK (not in the root runner; needs the maturin-built extension): `pytest bindings/python/tests` **25 passed, 2 skipped** (both 10-minute runs, CI-only). `cargo test -p nf-core --features stream`: 31 + 7 + 9 + 5 pass. `cargo clippy --workspace --all-targets -D warnings`: clean (with `PYO3_PYTHON` set).
- `openapi-diff` against the committed baseline: 0 breaking, 21 additive. Console client, docs API reference and `openapi/v1.yaml` drift checks: clean.

| Step | Acceptance test | Local result |
|---|---|---|
| 4.1 | Contract tests on every endpoint (hypothesis fuzz over the spec's operations + authz-matrix responses validated against the spec; schemathesis not added because of its dependency weight); undocumented-route check both ways (SEC-077); forced exception gives problem+json without internals (SEC-079); breaking change without major bump fails `tools/openapi-diff` (fixture tests) | pass |
| 4.2 | All 0.5 vectors; proptest canonicalisation + buffering; 2.7 network-cut test with nf-core in place of the prototype (via the Python binding against the existing test server) | pass. Worker-reported run: 20 s, 2 cuts, server array == sent samples |
| 4.3 | Website snippet runs as published (in-process server) | pass (snippet pinned to the real `eeg-basic@1.0.0`) |
| 4.4 | Synthetic outlet (test fixture) clock offset recovered within LSL's reported uncertainty; inlet-only (SEC-091, hw-guard) | pass on one host (true offset 0). A non-zero inter-host offset needs two hosts: not tested |
| 4.5 | Every quickstart code block executed (14 blocks, in-process); copy-lint; both builds | pass locally; against staging = CI-only |
| 4.6 | Sample verifier passes a valid signature and rejects a replay older than 5 min; SSRF per blocked target (SEC-076); SSE run events | pass |
| 4.7 🔒 | Rate limit, 30-day purge of unconfirmed, CORS, honeypot (tests force the flag on) | pass. **Flag OFF by default; route not mounted; website form untouched; no privacy text** |
| 4.8 | Quota exceeded → 403/429 problem+json; revoked key stops within 60 s (REST at once; SSE closed within 60 s, fake clock) | pass |
| F2 | Revoke/expiry mid-stream | Fixed in parallel by M5 (4ddde86). On merge the M5 version was kept and M4's duplicate dropped; main's tests cover it |

## CI-only (written, not run)

- `sdk-wheels.yml`: abi3 wheels on Windows/macOS/Linux, clean-runner install test, cosign + SLSA provenance (SEC-082), no publish step.
- Release builds; `cargo deny` / `cargo audit` (not installed locally; `deny.toml` added).
- 10-minute LSL stream test and 10-minute network-cut run; docs quickstarts against staging.
- `ci.yml` rust job now also runs `cargo test -p nf-core --features stream`.

## Changes made while merging M5

- Migrations renamed and re-chained: `0010m4_quotas_webhooks` → `0011m4_early_access`, after `0009m5_phi` (single head).
- hw-guard: M5's `services/` scan and M4's `--surface` scan combined; 14/14 hw-guard tests pass.
- M5's evidence-kit test now reads nf-core's version from its manifest (M4 bumped it to 0.1.0).
- The SDK test stack grants the fixture subject consent (M5 5.4 enforces consent on reads and runs).

## Open issues

1. **Owner gate 4.7:** go-live needs a privacy policy (owner/counsel), a real mailer, and enabling the website form in both builds.
2. **Rust network transport** for nf-core is planned: HTTP/gRPC transports are injected by the Python binding today. C/C++ bindings need it.
3. **Offline provenance sync** has no server endpoint (`POST /v1/provenance/batches` proposed by m4-sdk). It needs a security review of trust in client-supplied chains; the docs label it "designed".
4. **Webhook dispatcher scheduling** and the gateway rate limit are infra steps (`docs/platform/rate-limits.md`).
5. **Hashing spec v2 candidate:** integral doubles in [2^53, 1e21) canonicalise to integer literals that §3.1 rejects on input (both implementations agree; pinned by a test).
6. `architecture/BLUEPRINT.md` §2.6 still says `eeg-basic@1.2.0`; the website now shows the real `1.0.0`.
7. The SDK tests are not in `tasks.mjs test` (they need `maturin develop`); they run in `sdk-wheels.yml` and locally via `pytest bindings/python/tests`.
8. **Coordination:** asked nfb-devportal-lead which files it edits under `openapi/` and `apps/web` docs; no reply at the time of writing. The spec is generated from the app (`python -m nf_platform.api.openapi_doc --write`), so hand edits to `v1.yaml` would fail the drift test.

## Paused (owner request, 2026-09-26)

M4 was already complete when the pause arrived: nothing half-finished and no uncommitted work. No workers are running. Follow-ups queued for when work resumes:
- Register the webhook payload schema module in the M5 outbound-schema hook of `services/platform/tests/security/test_hw_guard_surface.py` (asked by nfb-build-queen). Today M4's `--surface` scan already covers the `webhooks` section of the generated OpenAPI.
- Dev portal (team-lead decision): `/developers/api` renders `apps/web/src/docs/api-reference.json`; `/docs` pages move to `/developers` in devportal's rebase. `apps/web/test/docs.test.mjs` reads `dist/.../docs/api/index.html`, so that path changes in the same rebase.

## Bug-hunt fixes (after resume, 2026-09-26)

Source: the independent bug hunt (`BUG-HUNT.md` in the lead's scratchpad). Each fix has a regression test.

| ID | Fix | Commit |
|---|---|---|
| H1 | Webhooks: a key under a retired pepper marks the delivery "signing key unavailable" and backs off; `deliver_due` isolates a crash per row and records the attempt (backoff, then failed) | f8636b2 |
| H2 | SSRF: `::/96` (IPv4-compatible IPv6) blocked and unwrapped; 4 new blocked-matrix entries | f8636b2 |
| H3 | `ProvExportOut` = object \| array; contract test per format. The baseline was re-copied (the old one described a shape the server never returned; nothing is published yet) | f8636b2 |
| H4 | nf-core stream: WAL high-water mark, so a drained WAL never restarts at seq 0; an ack past what was sent is fatal and deletes nothing | daf2763 |
| H5, H6 | nf-core zarr: rank check; checked size math with maximum chunk (256 MiB) and region (1 GiB) sizes; hostile-metadata property tests | daf2763 |
| M1 | Webhook enqueue in a savepoint; a concurrent duplicate is skipped (threaded test) | f8636b2 |
| M6–M10, L10, L12 | nf-core: `i64::MIN` safe-int check, non-array `steps` rejected, parent-directory fsync (no-op on Windows), `verify_chunk_full`, cache evict tolerates NotFound, strict base64, Infinity fill values | daf2763 |
| (flake) | Stream security test harness drained a stale "abort" event (the failure seen twice in full runs) | 7afa69f |

Not changed, with reasons:
- **L1** (no `DROP ROLE` in the m4 downgrades): roles are cluster-wide, and the test harness clones databases in one cluster. Dropping a role that other databases still use would fail, and no existing migration drops its role.
- **L5** (429/quota denials are not audited): kept as is to avoid audit flooding. This needs an explicit decision from the security role.
- M2–M5 and M11 are in M5/M6 code, not M4.

## Merge with M6 and hashing spec v2 in nf-core (2026-09-27)

- `origin/main` @12eb802 (M6) merged (ac72a31). New Alembic join `0015_merge_m4_m6` (0011m4_early_access + 0014m6_key_shred_freeze), single head. M6's registry `LineageOut` was renamed `ModelLineageOut`: the name clash made FastAPI rename the provenance `LineageOut` schema in the spec.
- nf-core `ids_v2` (f7512ec): builders for every v2 tag and signed document. It applies both new rules: manifest `inputs` are lowercase-folded, de-duplicated and sorted (§9.7), and consent `scopes` are de-duplicated and sorted (§9.3). `tests/vectors_v2.rs` recomputes all 27 `ids-v2.json` cases, verifies the signatures with the RFC 8032 test key, checks tampered inputs, and property-tests the set rules.
- Checks (resource rules: targeted tests per change, one full suite, `OMP_NUM_THREADS=4`):
  - lint ok;
  - cargo test green (nf-core 44 + 9 + 13 + 5 + 19); clippy `-D warnings` clean;
  - SDK 25 passed, 2 skipped;
  - workspace tests pass (console 65); both web builds and the console build ok;
  - full pytest: 1171 passed, 14 skipped, 1 failed. The failure was `test_harness_passes_on_the_v1_library`, which asserts `OMP_NUM_THREADS == "1"` in the recorded environment: the harness keeps an inherited value, and the resource rule sets 4. It passes when rerun without the variable (1 passed). This is an environment interaction with the M3 repro harness, not an M4 change. Decide whether the harness should force 1.
