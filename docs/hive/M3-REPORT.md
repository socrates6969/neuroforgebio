# M3 report: pipelines + provenance (branch `feature/m3-pipelines`)

Date 2026-09-26. Stacked on `feature/m2-ingest` (M2 not yet merged to main). Queen: nfb-build-queen. Workers: m3-prov (3.1, 3.2, 3.7), m3-exec (3.3, 3.4, 3.5), m3-sweeps (3.6, 3.9 scaffold), m3-console (3.8). Nothing deployed; CI remains dispatch-only; no dataset downloaded or published.

## Verified locally by the queen

- `node tools/dev/tasks.mjs lint`: exit 0. Both website builds: exit 0.
- `node tools/dev/tasks.mjs test`: exit 0. pytest **712 passed, 13 skipped** (all CI-only); console vitest 37/37 + node tests 14/14; web 45; content 25; cargo green.
- Real local PostgreSQL 16 (pgserver). **MNE 1.13.2 + scipy installed locally**, so the "equals direct MNE call" step tests run here. MNE import is about 35 MB; ICA peaks at about 110 MB.

| Step | Acceptance test | Local result |
|---|---|---|
| 3.1 | Graph fuzz (seeded DAGs 40–10k nodes): up/down lineage equals in-memory BFS; tampering with a node, edge or batch (incl. consistent rewrite without the key, untrusted re-sign) fails verification; WORM anchor catches a removed tail; two-tenant isolation | pass |
| 3.1 | Traversal latency, MEASUREMENT (100,029 nodes / 145,428 edges, local): artifact ancestry p95 1.87 ms; descendants of a raw file p95 2.54 ms; report ancestry p95 6.32 ms; worst case fan-out (~4.2k nodes) p95 223 ms. **Proposed target (to review):** p95 ≤ 10 ms for ≤ 200-node results, ≤ 500 ms for ~5k-node fan-outs | measured |
| 3.2 | Same ID for key-order/whitespace/number-form variants; frozen PipelineVersion vectors pass; changed re-publish → 409, identical → 200; name@semver resolves | pass |
| 3.3 | Real worker process killed mid-run → retried by another after lease expiry, no duplicate outputs, dead attempt's staging removed; provenance-commit fault injection → outputs invisible, retry publishes exactly one set; isolation on job/run/artifact | pass |
| 3.4 | Every step equals direct MNE calls; notch attenuation ≥ design attenuation (from MNE's FIR taps) − 3 dB (measured ~52.5 dB vs design 52.3 dB); seeded ICA bit-identical across two processes | pass |
| 3.5 | `tools/repro-check` fails on an unseeded fixture step; passes on the v1 library on x86-64 | pass (x86-64); arm64 cross-arch = CI-only |
| 3.6 | Planted effect (class-dependent 5 Hz burst; expected ordering derived from filter taps, not from a run): accuracy 1.0 / 1.0 / 0.4 at high-pass 1 / 4 / 10 Hz, notch irrelevant; every report cell links to run ID, run PROV activity and the metric artifact's hash | pass |
| 3.7 | PROV-JSON parsed and round-tripped with `prov` 3.2.2; OpenLineage RunEvents validate against the vendored OpenLineage 2-0-2 schema (Apache-2.0, source + sha256 recorded) | pass |
| 3.8 | Console: login (OIDC code + PKCE, memory-only tokens), datasets, upload, recording viewer, runs, sweep report, lineage explorer; typed client generated from OpenAPI with a drift test; strict CSP + no-inline + no-storage checks; bundle 76.2 KB JS gzip | unit/build pass; Playwright e2e + axe = CI-only |
| 3.9 | Study scaffold `research/multiverse/` (manifest with TODO placeholders only, runner, dispatch-only workflow). Status "Planned / in preparation" | scaffold only |

## CI-only (written, not run)

- Container step runner (image digest + cosign, `--network none`, read-only, non-root).
- `repro-check` x86-64 + arm64 matrix.
- Console Playwright e2e + axe.
- 3.9 study run: needs a selected dataset and a CI platform instance.

## SEC requirements

- **043:** hash chain + Ed25519 signature per provenance batch; WORM anchor and verify jobs.
- **044:** PipelineVersions are immutable and digest-addressed; images must be `@sha256`; cosign check in the container runner.
- **074:** sandboxed subprocess runner (scrubbed env, network block, timeout, kill on cancel).
- **015:** partly in the console (memory-only tokens, session clamps). Token lifetimes, reuse detection and cookie flags are IdP configuration (owner).

## Open issues

1. **Signing keys are KMS stubs** (env seed / dev ephemeral). A KMS-held asymmetric key is an infra step.
2. **Hashing spec v2** is needed for the new tags: `nf.prov-node.v1`, `nf.prov-anchor/v1`, plus the M2 tags.
3. **Scheduling and alerts:** anchor/verify jobs need a scheduler (cron) and SEC-102 alert rules.
4. **3.9 has no dataset yet.** No EEG decoding accession appears in the repo docs, and a CI platform instance is needed. Dataset choice and publication are owner decisions.
5. **Missing API pieces:**
   - no `GET /v1/runs` or `/v1/sweeps` list routes; no sweep cancel;
   - no step-library catalog in the API, so a wrong-typed override fails at the worker;
   - whoami, lineage and window responses are untyped in OpenAPI until 4.1.
6. **The console's e2e stack uses `uvicorn` via `uv run --with`** (unhashed, CI-only) until the platform declares an ASGI server dependency.
7. **`docs/security/licences.md` scope** should mention `apps/console`.
8. **Migration heads:** M5 (`feature/m5-ledger`) branched before `0005_sweeps` landed, so the queen adds an Alembic merge revision on the M5 branch.
