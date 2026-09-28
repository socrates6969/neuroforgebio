# Merge notes: `integrate/security-fixes` (from main @b0e5303)

Prepared by nfb-build-lead-2 on 2026-09-27, using git and file tools only. Python and node are banned (owner hold, `RUST-POLICY.md`), so **no Python or web test was run**.

**Status: VERIFIED 2026-09-27 (see "Full verification"); the only open item is ae52d4d, which is tofu-unvalidated.**

## Merges (in order)

| Merge | Branch | Conflicts resolved by reading |
|---|---|---|
| ee8193a | `fix/appsec-m1-m3` @6236186 | (1) `db/context.py` `role_session` allow-list: AppSec's rename `nf_audit` → `nf_audit_writer`, plus M4's `nf_site` and `nf_webhook`; `nf_audit_batcher` stays excluded. (2) `tools/repro-check/nf_repro/__main__.py`: main's forced thread pins kept, including the forced `PYTHONHASHSEED` (lead's decision); AppSec's version still defaulted `PYTHONHASHSEED`. |
| 30563ce | `fix/nr-m1-body-limit` @0a2ee5c | `app.py` imports: M4's `versioning` kept next to NR-M1's `BodySizeLimit`. The middleware registration merged cleanly (before `request_id`, so a 413 carries the request ID). |
| b930143 | `fix/nr-h1-keystore` @ae52d4d | `app.py` imports: M4's `RateLimiter` and early-access `Mailer`/`DisabledMailer` kept next to NR-H1's `storage_from_env`/`require_durable_storage`. `local_storage` and `os` are no longer used. |

## Follow-up commits

- **f9c9383, nf-core `weights_source`:** AppSec M3 added a hashed, optional manifest member and two `ids-v2.json` cases (hashing.md §9.7 amendment). nf-core now reproduces all 5 `training_manifest` cases. Verified with Rust only: `cargo test -p nf-core --features stream` passes, and `clippy -p nf-core -D warnings` is clean. The public struct `TrainingManifestArgs` gained a field, so `bindings/c` (nfb-cabi) must add `weights_source` to its struct literal.
- **ae52d4d (infra, NR-H1), tofu-unvalidated.** The commit covers:
  - the platform env vars (NF_ENVIRONMENT, NF_S3_BUCKET_PREFIX, NF_KMS_BACKEND=aws, NF_KMS_KEY_ALIAS_PREFIX);
  - per-tenant KMS KEKs and aliases (`alias/nf/tenant/<id>`, prevent_destroy);
  - the zarr, artifacts and models buckets, and the task IAM policy.

  Neither tofu nor terraform is installed on this PC, so none of these have been run: `tofu fmt -check`, `validate`, `test` (a mocked plan, including the new `tenant_kek_alias_matches_platform` run) and the phi-guard test. Owner's options: trigger `.github/workflows/infra.yml`, or approve a local tofu install. The least certain part is the `kms:ResourceAliases` IAM condition when an alias is passed as the KeyId. The Python static check `test_gov_phi_placement.py` passed **16/16** on `fix/nr-h1-keystore` (ae52d4d + 0338691), run by nfb-fix-h1 in bci-queen lane C under hive-peakmem (wall 20.1 s, peak job commit 159.7 MB, exit 0). That includes `test_every_env_declares_its_modules_to_the_phi_guard[dev]`, so `modules_used` still matches with the `for_each` data_buckets module. It is a static check only; ae52d4d stays tofu-unvalidated. (Note provided by nfb-fix-h1.)
- **7828152, Alembic join `0016_merge_audit_roles_m4`:** down_revision is (`0015_audit_roles`, `0015_merge_m4_m6`).

## Alembic heads (checked by reading, not by running alembic)

The down_revision values were read with grep over `services/platform/nf_platform/db/migrations/versions/*.py`: 20 revisions, 21 down_revision references (19 unique), no dangling reference.

- Before the join there were two heads: `0015_audit_roles` (AppSec, revises `0014m6_key_shred_freeze`) and `0015_merge_m4_m6` (revises `0011m4_early_access` + `0014m6_key_shred_freeze`).
- After the join there is **exactly one head: `0016_merge_audit_roles_m4`**.
- Owed: `alembic heads` plus migrations up/down/up and the drift test on a real Postgres.

## After the ban was lifted (2026-09-27)

- **2d1934c:** `openapi/v1.yaml` and `api-reference.json` regenerated with the repo scripts; the console client came out byte-identical. openapi-diff: 0 breaking, 19 additive. `alembic heads` (ScriptDirectory): exactly `0016_merge_audit_roles_m4`, 20 revisions.
- **565cd34:** tests for the gaps the review found, 7 new tests, all passing when run on their own:
  - M1: cutoff event between due events; concurrent batchers write one batch.
  - M2: 0015 up/down/up with pre-existing rows.
  - M3: `weights_source` fallback.
  - NR-M1: duplicate or non-digit Content-Length; cap exceeded after the response started.
- **5d294b2:** merged `fix/nr-h1-keystore` @0338691 (review HIGH: `NF_ENVIRONMENT` is normalised and validated once). Conflict in `Settings.from_env`: kept `environment_from_env()` plus M4's early-access settings. 44 targeted tests pass (prod storage guard, runner, early access).
- The m4 `.venv` had been damaged during the ban (no `pyvenv.cfg`, packages missing). `pyvenv.cfg` was restored with the same content as m5's, then `uv sync --locked --offline` was run (local cache, lockfile only).

## Full verification (bci-queen lane A2, 2026-09-27): PASS

Tested commit: af5d43a. Its code is identical to c98fde6; the commits after c98fde6 change the notes only. Every step was wrapped in hive-peakmem. An earlier attempt was killed by the Claude Code low-memory reaper and is discarded.

| Step | Result | Wall time | Peak job commit |
|---|---|---|---|
| Alembic heads + upgrade head → downgrade base → upgrade head (throwaway pgserver) | 1 head `0016_merge_audit_roles_m4`; 51 tables after each upgrade, only `alembic_version` after the downgrade | 11.4 s | 95 MB |
| `tasks.mjs test --skip=web,rust` (full pytest, serial, OMP_NUM_THREADS=4; pytest-xdist is not installed, so no `-n4`) | **pytest 1254 passed, 14 skipped, 0 failed**; tool node tests 83/0 | 906.9 s | 874 MB |
| Web builds (clinical, cosmos), console build, `pnpm -r test` | builds exit 0; ui 10, themes 14, figures 6, repo-guard 20, copy-lint 14, content 25, web 52, console 67 (vitest) + 14 (node): all passed, 0 failed | 41.5 s | 724 MB |
| `tasks.mjs lint` | ok | | |

## Revert checks: the tests fail when the fixes are removed (2026-09-27, bci-queen lane C)

Each protected line was mutated temporarily, the targeted tests run through `hive-peakmem`, and the line restored with `git checkout` (the diff is clean afterwards).

| Fix | Mutation | Tests run (`-k`) | Result with the mutation |
|---|---|---|---|
| NR-H1 review HIGH | `config.parse_environment`: `env = raw` (no strip or lower) | `prod_storage or environment` | **6 failed**, 27 passed: `test_prod_spelling_variants_fail_closed[Prod, PROD, " prod ", "prod\n"]`, `test_stream_server_main_environment_variants[Prod]`, `test_signing_keys_environment_variants[Prod]` |
| NR-M1 | `body_limit._declared_length`: accept any first Content-Length value | `content_length_is_treated` | **2 failed** (duplicate, non-digit) |
| AppSec M1 | `audit/chain.py _batch_scope`: advisory lock removed | `concurrent_batcher_runs` | **1 failed** (`test_concurrent_batcher_runs_on_one_scope_write_one_batch`) |
| (restored) | none | all of the above | **36 passed** |

Measurements (hive-peakmem): the runs took 11.0 s, 11.2 s, 20.0 s and 24.5 s wall time, 66.7 s in total. Peak job commit was 297, 271, 303 and 328 MB.

## Known to fail until regenerated (needs Python, owed) — done in 2d1934c, kept for the record

AppSec changed the API surface:
- a new route, `GET /v1/audit/batches/{seq}/object`;
- `weights_source` fields and a `reason` field in the registry models.

NR-M1 changed a 413 title. The committed contract artifacts were NOT regenerated:
- `openapi/v1.yaml`: `python -m nf_platform.api.openapi_doc --write`. Until then the drift test and the SEC-077 route-enumeration test fail.
- `apps/console/src/api/generated.ts` + `authz.json`: `node apps/console/scripts/gen-api.mjs`. Git combined AppSec's generated additions textually; the generator output must replace them.
- `apps/web/src/docs/api-reference.json`: `python tools/doc-snippets/gen_api_reference.py`.
- Then `tools/openapi-diff` (expected: additive only), the full pytest suite, and the web and console tests.
