# M2 report: ingest + storage (branch `feature/m2-ingest`)

Date 2026-09-26. Queen: nfb-build-queen. Workers: m2-core (2.1, 2.2, 2.8), m2-data (2.3, 2.4, 2.5), m2-stream (2.4 endpoint, 2.6, 2.7, SEC-038).
Rebased on main @6b0ef19 (after the lint-scope and third-party-data chores). Nothing deployed; no cloud accounts; CI remains dispatch-only.

## Verified locally by the queen (Windows, ~3 GB free RAM)

- `node tools/dev/tasks.mjs lint`: exit 0 (repo-guard, hw-guard incl. `proto/`, ci-lint, licence-check, copy-lint, Prettier, ruff, cargo fmt, import-linter via tests).
- `node tools/dev/tasks.mjs test`: exit 0. **pytest 478 passed, 18 skipped** (all skips CI-only, see below); web/tool suites green; cargo green.
- **Real PostgreSQL 16 locally** via `pgserver` (pip-bundled binaries): migrations and RLS run against a real server, not SQLite. A template DB is migrated once and cloned per test; the cluster stops at session end.

| Step | Acceptance test (BUILD-GUIDE) | Local result |
|---|---|---|
| 2.1 | Migrations up/down/up; model = migration drift check; two-tenant isolation on every table (14 tables, FORCE RLS + policy each) + app-level BOLA; import-linter (5 contracts) | pass |
| 2.2 | Authz matrix: 7 roles × every route (enumerated from the app; an unmapped route fails); expired key 401; wrong scope 403; admin roles without phishing-resistant `amr` 403 | pass |
| 2.3 | Ciphertext at rest; tampered AAD/ciphertext fails; nonce uniqueness; **crypto-shred: primary AND pre-shred backup copy unreadable, other subjects fine** (object store and Postgres key store); per-tenant KMS keys + encryption-context binding; keys never logged | pass |
| 2.4 | Window read equals source (int exact, float tolerance); pyramid = decimated reference; Zarr at rest is ciphertext and shreddable; `GET /v1/recordings/{id}/data` with authz, audit, cross-tenant 404, shredded subject 410 | pass |
| 2.4 | Chunk-size benchmark, MEASUREMENT (64 ch × 1 kHz × 300 s int16, encrypted): 1-s window read 13.0 / 10.3 / 7.9 / 8.4 ms for 1 / 2 / 4 / 10 s chunks | measured |
| 2.5 | Round-trip EDF, BDF (bit-exact, cross-checked with pyedflib), BrainVision (bit-exact), XDF (exact timestamps + clock offsets), BIDS (EDF/BrainVision); seeded corrupt-file fuzz gives typed errors | pass |
| 2.6 | Hash mismatch rejected (direct + presigned); resumed multipart works; quarantined recording: `scientist` 403, `data-steward` 200; worker converts, writes provenance, quarantines | pass |
| 2.7 | 25 s, 64 ch × 1 kHz, two 2-s network cuts: server array == sent samples, no gaps, no duplicates; 5-s server stall: acquisition continues to the WAL, no loss (max gap 0.03 s, WAL peak 54 chunks); LSL outlet→inlet→server via pylsl | pass |
| 2.7 | Throughput, MEASUREMENT: 3.2× real time for 64 ch × 1 kHz float32, 100 ms chunks, on this PC | measured |
| 2.8 | Every data-read route emits an audit event (enumerated); modified/removed batch fails hash-chain verification; no credentials in audit rows or logs | pass |

## CI-only (written, not run; `workflow_dispatch`)

- `platform-integration` job: docker-compose Postgres 16 + MinIO (images pinned by digest), S3/MinIO object-store tests, Object-Lock audit bucket.
- Reader tests needing MNE / pynwb / mne-bids / bids-validator (NWB round-trip, MNE re-reads, BIDS validation).
- 1,024 ch × 30 kHz chunk benchmark; the full 10-minute stream test with network cuts.

## SEC requirements

- **Covered by local tests:**
  - Identity and access: 010, 011, 014, 016 (device tokens; the mTLS option is not built), 020, 021 (app + RLS + per-tenant KMS).
  - Cryptography: 031, 032, 033, 034, 037 (WAL AES-GCM; DPAPI on Windows only), 038 (`docs/security/crypto-inventory.md`).
  - Ingest and streaming: 040, 041, 042 (app-level), 060 (partial: size limits and worker-only parsing; the sandbox comes in M3), 061, 062 (short seeded fuzz), 063, 064, 071.
  - Stimulation exclusion (§G): 090 (hw-guard over `proto/`, device → platform only), 091 (edge prototype), 093, 094.
  - Audit: 100, 103, 105, 140, 141 (partial), 147.
- **Owner/infra-gated or later:** 012, 013, 015 (IdP/console); 023 (IAM); 025 break-glass flow (console); 101 retention policy; 102 alert rules; 121/122/123 IaC, restore drill, two-person approval; 073 (no container yet); 022 governance-attribute write rights (M5).

## Open issues

1. **No job queue yet.** Uploads are processed by a `process_pending` worker function; the Postgres queue is step 3.3 (M3).
2. **`LocalKms` is per-process,** so a separate dev worker process cannot decrypt. Fine for tests; real KMS in CI/cloud.
3. **Converter identifiers (SEC-140/141) are dropped,** because no governed table exists yet (M5).
4. **Sanity amplitude limits are placeholders** (1 V). Live window reads lag up to 1 s.
5. **Hashing spec v2 proposal:** new ID tags `auditb:`, `nf.device-token.v1` and `nf.stream-chunk.v1` use the v1 construction with their own tags. They need a spec update (SDK review).
6. **MinIO:** upstream images are no longer publicly pullable. Compose uses `bitnamilegacy/minio` (frozen 2025.7.23, test-only), which needs an owner/security decision.
7. **hw-guard does not scan `services/`.** If its denylist were applied there, it would flag `from alembic import command` and the XDF "Stimulus" event-marker fixtures (recording markers, not commands). Extending the guard to `services/` needs a decision with nfb-security.
8. **Not yet built:** a quarantine-release endpoint (M5 policy engine) and mixed-rate EDF / EDF+D.
