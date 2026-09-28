# Inbox: queen

Others append dated notes below (newest last). The owner of this inbox marks each note "ACK" when handled.


## 2026-09-26 nfb-copywriter -> queen: step 1.2 done (commit 7743544), plus 1.8 page copy
- packages/content: brand.json (name "NeuroForge Bio", placeholder `.invalid` domain + `legalNameIsPlaceholder`), typed JSON for home/site/pages/law tracker/research index/whitepaper preview, loader + zero-dep validator, 18 node:test tests (schema, sources, binding copy fixes, brand-token scan, rename flow, copy-lint) all passing; copy-lint clean.
- Flag for research/owner: frontend plans to plot P1 (ABANDONED cycle-1) and P2 (INCONCLUSIVE) figures on the whitepaper page. I captioned them with a "shown for transparency, not as a result" note; whether to show them at all is a research/owner call.
- Owner copy review questions are listed in packages/content/README.md's status line ("pending") and in my final report.
- Open questions for the owner's copy review (the handback failed because the spawning agent had exited, so they are recorded here):
  1. Should the P1 figure (abandoned analysis) and P2 figure (inconclusive) appear on the whitepaper page at all?
  2. I removed "Sign in", "Book a demo", "Start free" and "Talk to us" (no product, contact channel or open list yet); every "Join..." CTA is disabled with "opens soon". OK?
  3. I kept the hero headline "The data layer for <em>brain-computer interfaces.</em>" and added a home Governance section (D1). The compliance heading is now "Neural data is sensitive. Our design starts there." (copy-lint bans "treat").
  4. Law tracker: Montana, the MIND Act and the other states' bills are verified:false. Please check the paraphrased definitions against regulation.md before release.

## 2026-09-26 nfb-platform-eng -> queen: M0 0.1-0.7 done (not pushed)
- Commits: ac944e5 copy-lint (+.gitattributes LF), 18ac100 monorepo/toolchains/ADRs, 873b551 repo-guard+SECURITY+CI, 825c39e hashing spec+vectors, 07e356f synth, d56461b infra, 9fd393c prettier fix.
- Root package renamed `nf-monorepo` (keeps the brand literal out of code). New dir docs/dev/toolchain.md (toolchain + uv decision: uv pip-installed into .venv and listed in the dev group; CI uses setup-uv).
- Local status: `node tools/dev/tasks.mjs test --skip=web` green (17 node tests, 72 pytest + 5 CI-only skips, 3 cargo tests). `lint` green for my paths; prettier currently fails on copywriter/designer/frontend files (told them in their inboxes).
- CI-only: all workflows (dispatch only), MNE/pynwb readers, tofu validate/test, gitleaks/SBOM/audits, Playwright/Lighthouse.
- Tooling note: `export PATH=".../node22/node_modules/node/bin:$PATH"` does not make Git Bash pick Node 22 (`which node` stays v24); call `/c/Users/mariu/.local/node22/node_modules/node/bin/node.exe` directly.

## 2026-09-26 nfb-frontend -> queen
- Commits 126c64c + 1856cbb (web, ui, figures, placeholder themes, pnpm-lock, web-e2e steps). Both builds green locally; outputs apps/web/dist/{clinical,cosmos}. I edited ONE line of docs/hive/CONTRACTS.md §3.3 (dist path); uncommitted for you.
- Research figures: 3 hash-pinned figures (p1 R_curves line, p4 capacity heatmap, p2 d' scatter), all "preliminary", with the copywriter's notes that P1 is from an abandoned cycle and P2 inconclusive. Whether P1/P2 should be shown at all is your/research's call: removing an entry from packages/figures/manifests/somatosensory-closed-loop.figures.json hides it.
- (later) Waited ~25 min: nfb-designer-3d has not delivered tokens/slots/three yet, so both builds still use my placeholder theme files and the cosmos lazy-three bundle test is skipped. When three@0.160.0 lands in packages/themes/package.json someone must run `pnpm install` (my job; re-spawn me or run: Node 22 + `npx -y pnpm@9.15.0 install`), then `pnpm --filter @nf/web build && pnpm --filter @nf/web test`.

## 2026-09-26 nfb-designer-3d -> queen
- Done 1.1, 1.4, 1.5: commits 15ec9d7 (packages/themes + pnpm-lock) and 8d41d7c (one-rule fix in nfb-frontend's apps/web/test/bundle.test.mjs; reason in nfb-frontend's inbox). Not pushed.
- I ran `pnpm install` myself (Node 22, pnpm 9.15.0 from the npx cache), both web builds, web dist tests (17/17), theme tests (14/14), copy-lint on both dists (clean), prettier on packages/themes (clean).
- Measured: cosmos home initial JS ~6 KB gzip; lazy three chunk 459 KB raw / 115 KB gzip; clinical home ~4 KB gzip.
- Open: `pnpm lint` still fails prettier --check on 11 files in packages/content (copywriter's), not mine. Playwright/Lighthouse not run (CI-only). Design deviations (clinical emphasis colour, cosmos on-accent dark, elevation shadow instead of blur) are listed in packages/themes/README.md for owner review.

## 2026-09-26 queen: ACK all notes above. P1/P2 figures hidden (verification gate), P4 kept as preliminary. Report: docs/hive/M1-REPORT.md

## 2026-09-26 nfb-platform-eng -> queen: S.6 done (commits 2588037, 47c31a2, c37e6d1, 389d182; not pushed)
- New zero-dep tools (no package.json, so the pnpm lockfile importers are unchanged): tools/hw-guard (SEC-090/091), tools/ci-lint (SEC-080/089), tools/sbom-props (SEC-083), tools/licence-check (SEC-084), tools/vuln-gate + security/vex OpenVEX (SEC-085). repo-guard: .npy/.zarr + >5 MB (SEC-087). All wired into `tasks.mjs lint|test` and ci.yml; coverage table docs/security/SEC-COVERAGE.md.
- Every action SHA-pinned (looked up with read-only `git ls-remote`), including the web-quality.yml `web-e2e` job (pins only, steps untouched). release.yml is dispatch-only, written, never run. gitleaks moved from gitleaks-action (needs a paid licence for org repos) to the checksum-pinned CLI.
- copy-lint: Norwegian negations + tools/copy-lint/allow.json exact-phrase allowlist for nfb-web-sec (banned list unchanged).
- Local: lint = all mine clean; prettier --check fails only on apps/web/e2e/security.spec.ts (nfb-web-sec's in-progress file). test: ok (69 tool tests, workspace, 72 pytest, cargo).
- Owner 🔒: branch-protection.md settings, a real security-role team for CODEOWNERS (placeholder `@PLACEHOLDER-ORG/security-role`), push protection, a `pull_request` trigger before required checks can work, running release.yml.
- Open: `.npz` not banned (2 research results tracked under research/somatosensory/code/results); hw-guard `command` rule will flag `std::process::Command` in a future core build.rs (no allow marker by design).
- BOARD row S.6 updated (uncommitted).

## 2026-09-26 nfb-web-sec -> queen: wave 2 S.1–S.5 done (commits b60843f, c896eec; not pushed)
- Local, Node 22: both builds exit 0 (copy-lint clean on both dists, inline check clean, _headers + security.txt emitted); `tasks.mjs lint` 0; `tasks.mjs test` 0 (web 42, content 25, ui 10, figures 6, themes 14, tools 69, pytest 72, cargo); linkcheck 562 links x2, 0 broken.
- CI-only (written, not run): apps/web/e2e/security.spec.ts (CSP violations on every page EN+NO, crossOriginIsolated, cosmos hero WebGL + fallback under COEP, same-origin requests, no cookies/storage). serve.mjs now applies dist/_headers (drops only upgrade-insecure-requests on loopback http).
- Decisions for owner review: HSTS includeSubDomains only at SITE_STAGE=public (with preload); `brand.json secondaryHost` placeholder `cosmos.<domain>` for the cosmos security.txt Canonical; nav/footer stay English (lang="en") on /no/ pages; ~12 NO UI strings (ui.no.json) are mine, not reviewed; imprint page removed per footer spec (ehandelsloven imprint duty is UNVERIFIED in the terms draft).
- BOARD.md S.1–S.5 status updated (uncommitted). My inbox: docs/hive/inbox/nfb-web-sec.md (uncommitted).

## 2026-09-26 nfb-channels-eng -> queen: channel estimator done on feature/channel-estimator (commits 9ac3beb, 37c6488; not pushed)
- Package services/workers/steps/channel_estimator (import nf_channel_estimator, numpy only; binomial CDF as exact sum instead of scipy). Wired via root pyproject pytest testpaths/pythonpath (not a uv workspace member: root is package=false). CLI `python -m nf_channel_estimator estimate|schema`, typed API, closed JSON Schemas in schemas/.
- Golden: K 4/2/4, K_terr 4/3/5, all rules x m=1..3 equal the P6 JSON; attrition exact DP to 1e-12 at all 6 sensitivity p; N_eff exact; Null A/B + no-wrist and relabelling BIT-EXACT for all 3 participants (C1 via the public API; P2/P3 need the research's shared-stream order, replayed in the test; a single-map call for P2/P3 gives statistically equivalent, not identical, nulls; documented).
- DATA: the research inputs (greenspon2025_ed1_extraction.json, pf_per_electrode_greenspon2025.csv) are NOT in git (research/.../notes/published-derived is ignored by `data/`); they exist only in ~/neuro-company. I vendored LF copies to services/.../tests/golden/ (hash-pinned; a test also checks the research copy when present). Added that dir to .prettierignore (byte-exact fixtures), 1 line.
- Baseline lint is RED before my change (not mine): repo-guard (tracked research/.../notes/published-derived/*.csv + legal/data-agreements/*), prettier (investor/*.html, marketing one-pager), ruff check/format (investor/*.py, legal/financing/*.py). My paths: ruff/prettier/copy-lint clean. `tasks.mjs test` exit 0 (pytest 226 passed, 7 skipped).
- Maths questions: none blocking. Notes: positions (x_mm/y_mm) are carried and hashed but unused (the research nulls are label-only; clustered-loss sensitivity not ported). Input hash is plain SHA-256 of NF-CJSON (no new ID kind; a `pf-map` kind would be a hashing-spec change). Handoff note da5fd0d on main (P2 "0.62^2 = 0.3844" is the D2 term alone; exact P = 0.383404 incl. D1).
- Optional /research page section NOT done (kept change surface minimal while baseline lint is red).

## 2026-09-26 queen: ACK nfb-channels-eng. Verified golden attrition independently (brute force), tests + CLI re-run; pushed feature/channel-estimator.
## 2026-09-26 from m2-data: 2.3 / 2.4 / 2.5 done (branch feature/m2-ingest, not pushed)
Commits: 4053968 storage (2.3), ef16653 signals (2.4), e233053 converters (2.5), 241d2a0 SqlKeyStore.
Local: 72 passed, 8 skipped (CI-only: MinIO, 1024ch/30kHz bench, MNE x3, pynwb, mne-bids, bids-validator); ruff clean; `tasks.mjs test` ok.
Round-trip locally: EDF, BDF (bit-exact, cross-checked with pyedflib), BrainVision (bit-exact), XDF (pyxdf, exact ts + clock offsets),
BIDS (EDF/BrainVision). CI-only: NWB (pynwb), MNE re-reads, mne-bids, bids-validator.
Crypto-shred: primary + pre-shred backup copy unreadable after shred_subject, other subjects fine; also on Postgres (RLS) via SqlKeyStore.
Benchmark (MEASUREMENT, 64ch/1kHz/300 s int16, encrypted): 1-s window read 13.0/10.3/7.9/8.4 ms for 1/2/4/10 s chunks;
stored 80 MB vs 38 MB raw (pyramid mean/min/max roughly doubles storage on this incompressible synthetic data).
SEC covered in code: 031, 032, 033, 034, 038 (header; CBOM doc missing), 121 (WORM/versioning config), 123 (7-day window in LocalKms/AwsKms),
060 (partial: size limits + static no-import test; sandbox = M3), 061 (static scan), 062 (short seeded fuzz), 140, 141.
Owner/infra-gated: 023 (IAM), 121/123 IaC + two-person approval, 122 restore drill, 042/064/071 (2.6).
Open: docs/security/crypto-inventory.md (SEC-038, not my path) missing; DB backups still hold wrapped DEKs until expiry (D4);
mixed-rate EDF and EDF+D unsupported; no GET /recordings/{id}/data route yet (api is m2-core's); NWB code untested locally.

## 2026-09-26 m2-core -> queen: 2.1, 2.2, 2.8 done (commits 2da4ef1, 8e53bb6, 5d5b33d, 1e94fca; not pushed)
- Postgres: REAL local Postgres 16.2 via `pgserver` (pip, bundled binaries) — no SQLite fallback needed. Tests
  migrate a template DB once and clone it per test; the cluster is stopped at session end.
- Local: `pytest services/platform` 171 passed / 9 skipped (all CI-only: MinIO, readers extra, bids-validator,
  1024ch bench); m2-core's own 99 passed + 1 skipped (@integration). `tasks.mjs test` ok (244 pytest). ruff +
  format clean on services/platform; import-linter 5 contracts kept; ci-lint clean.
- Passing locally: 2.1 migrations up/down/up + model drift check + two-tenant RLS per table (14 tables) + BOLA;
  2.2 matrix (7 roles x 21 authenticated operations + public health, routes enumerated from the OpenAPI doc, unmapped route fails), expired
  key 401, wrong scope 403, admin w/o phishing-resistant amr 403 everywhere; 2.8 every GET route emits an
  event, modified/removed batch fails verification, no secrets in audit rows/logs.
  SEC: 010, 011, 014, 020, 021 (app + RLS layers; KMS layer is m2-data's), 063 (ORM/bound params; no Semgrep
  rule yet), 100, 103 (seq + UTC), 105, 147 (log/audit scan).
- CI-only: `platform-integration` job (dispatch-only, compose Postgres 16 + MinIO pinned by digest) incl. the
  Object-Lock audit bucket test (not run anywhere yet).
- Open: SEC-025 break-glass (event type reserved; flow comes with the console), SEC-101 retention policy test
  only via object-lock put, SEC-102 alert rules not built, SEC-073 N/A (no container yet), SEC-012/013/015
  owner/IdP items. Upstream MinIO images are no longer publicly pullable: compose uses bitnamilegacy/minio
  (frozen 2025.7.23, test-only) — needs a decision. `auditb:` ID kind is outside hashing spec v1 (same
  construction as provb, own tag) → propose for spec v2. `tools/hw-guard/cli.mjs services` ignores the path
  argument (it only scans proto/openapi/core/bindings/sdk); applying its denylist to services/platform
  flags `from alembic import command` (db/migrate.py) and m2-data's XDF "Stimulus" marker fixtures.
  SEC-022 (governance attrs writable only by data-steward/admin) is M5: today any recording creator sets
  the initial channel attributes. Python job now also runs services/platform tests (pgserver on Linux).

## 2026-09-26 research-lab-lead -> queen: claiming research-algorithm step packages (owner request)
- Owner asked for the NeuroForge algorithms from the research-lab plans. To avoid colliding with M2, I am working ONLY in a separate worktree C:\Users\mariu\neuro-worktrees\algos on branch eature/research-algos (from main @6b0ef19), not in feature/m2-ingest.
- Paths claimed (new, nobody else's): services/workers/steps/eval_harness/** (nf_eval: leak-safe splits, SzCORE-style event scoring, Snyder chance/forecast metrics, cluster bootstrap, BH-FDR, prereg lock hashing) and services/workers/steps/biomarkers/** (nf_biomarkers: aperiodic-corrected spectra, beta bursts, EIS equivalent-circuit fit, C-index). Same precedent as nf_channel_estimator. Research use only, numpy/scipy only, synthetic fixtures only.
- The only shared-file touch will be adding the two test paths to the root pyproject.toml pythonpath/testpaths on MY branch; merge is yours to decide. Not pushed.

## 2026-09-26 m2-stream -> queen: 2.4 endpoint, 2.6, 2.7, SEC-038 CBOM done (commits 4eb5aef, 96fb39e, d7a2d43; not pushed)
- Partial earlier attempt: reviewed and kept most of it (schema 0002, upload service, stream servicer, protocol, proto). Fixed: zip "special file" false positive (writestr entries had no file-type bits), S3 resume ignored parts already in S3, hash-mismatch audited as success, JSON window had no own cap, dangling docs/spec/signal-window.md reference (format now documented in code/OpenAPI), shredded subject -> 410. Added all tests, edge_prototype, S3 moto test, live-attrs throttle (+40% stream throughput), CI env for the 10-min run.
- Test infra: pg_url/template_db moved to services/platform/tests/conftest.py (one cluster for all dirs); tests/ingest reuses core fixtures. TREE_SIGNAL now 2x4096 (pyramid level 1).
- Local: pytest services/platform 247 passed / 12 skipped (all CI-only: MinIO x3, readers x6, 1024ch bench, 10-min stream run); ruff + format clean; import-linter 5/5 kept; `tasks.mjs test` ok; hw-guard clean (proto/); ci-lint clean.
- Measured (MEASUREMENT, this PC, 64 ch x 1 kHz float32, 100 ms chunks): headroom 3.2x real time; 25 s run + two 2 s cuts: server == sent, no gaps/dupes (13 RPC errors retried); 5 s server stall: max acquisition gap 0.03 s, WAL peak 54 chunks, no loss. pylsl wheel works here: LSL outlet->inlet->server test passes locally.
- SEC: 016 (device tokens; mTLS option not built), 037 (WAL AES-GCM, DPAPI on Windows only), 038 (docs/security/crypto-inventory.md), 040, 041, 042 (app-level immutability; S3 versioning = m2-data config), 060 (worker-only parsing, import-linter), 064, 071, 090, 091 (edge prototype), 093, 094.
- Open: no job queue yet (worker is `process_upload/process_pending`, M3 3.3); LocalKms is per-process so a separate dev worker process cannot decrypt; converter `identifiers` (SEC-140/141) are dropped, no governed table yet; sanity amplitude limits are placeholders (1 V); live window reads lag <=1 s; `nf.device-token.v1`/`nf.stream-chunk.v1` tags (like auditb) proposed for hashing spec v2; SEC-COVERAGE.md not updated (platform-eng's file); no quarantine-release endpoint (M5 policy engine).

## 2026-09-26 research-lab-lead -> queen: research-algos ready for your review (branch feature/research-algos, not pushed, not merged)
- Commits 6d5f075 (nf_eval), 3c6e84c (pytest paths), 38da955 (nf_biomarkers). Worktree C:\Users\mariu\neuro-worktrees\algos.
- 110 new tests pass (synthetic only: planted truth, oracle, MC-vs-analytical chance, leakage, permutation nulls, 1/f recovery, EIS BIC, C-index). Full suite on the branch: 338 passed, 7 skipped, 2 errors = the pre-existing channel_estimator release-guard wheel/sdist errors, which also fail on main.
- Only shared-file change: root pyproject.toml pythonpath/testpaths (+2 lines each). Suggested home: M3 3.4 step library / 3.5 reproducibility harness / 3.9 multiverse study.

## 2026-09-26 m3-prov -> queen: 3.1, 3.2, 3.7 done (branch feature/m3-pipelines; not pushed)
- Commits: 73ff31b (0003 tables + provenance/pipelines interfaces), fc98032 (routes, JSON Schema, publish/resolve,
  authz), fc96b60 (upload worker -> graph), 10e73cd (fuzz/tamper/isolation/export/bench tests, WORM anchors +
  verification job), 5e2e257 (crypto-inventory rows 17-18), 30915b2 (test logger fix), daf202b (.prettierignore).
- Verified locally: `tasks.mjs lint` exit 0, `tasks.mjs test` exit 0 (pytest 658 passed, 13 skipped, all skips
  CI-only M2 items); ruff check/format clean; import-linter 5/5 kept. 89 new tests (tests/provenance, tests/pipelines).
- 3.1 (local, pass): graph fuzz (seeded random DAGs 40/300/1.5k/10k nodes written via record(); up/down,
  bounded + unbounded lineage == in-memory BFS: nodes, min depth, edges); tampering with a node (attrs/ref/content),
  edge, batch (time/prev/deleted), consistent rewrite without the key, re-sign with an untrusted key -> verify fails;
  removed tail caught by the WORM anchor + alert log; key rotation keeps old batches verifiable; two-tenant isolation
  (API 404, RLS on all 4 tables, no cross-tenant edges, independent chains).
- 3.1 MEASUREMENT (this PC, pgserver PG16, function level through tenant_session incl. SET ROLE; 100k run done
  locally, 15 s): 100,029 nodes / 145,428 edges, 200 samples each: ancestry of an artifact p95 1.87 ms (7 nodes);
  all descendants of a raw file p95 2.54 ms (<=33 nodes); report ancestry (fan-in + chains) p95 6.32 ms, max 85.7 ms
  (<=155 nodes); artifact ancestry depth 3 p95 1.79 ms; worst case: all runs+outputs of one PipelineVersion agent
  (depth 2, ~4.2k nodes, 40 samples) p95 223 ms. Proposed target (to review): p95 <= 10 ms for lineage results
  <= 200 nodes, <= 500 ms for ~5k-node fan-outs; revisit (graph DB) only if a measured traversal exceeds it.
- 3.2 (local, pass): frozen pv vectors (3/3) pass via the model; key order/whitespace/40 vs 40.0 -> same ID;
  re-publish with any change (params, seed, image, description) -> 409; identical -> 200; name@semver and pv id
  resolve; per-tenant. docs/spec/pipeline-version.schema.json (+ example); schema and model agree on 18 bad cases.
  m3-exec's nf_steps pipelines (eeg-basic, eeg-resample-features) validate against the schema and the model.
- 3.7 (local, pass): PROV-JSON parsed + round-tripped with `prov` 3.2.2 (MIT); OpenLineage RunEvents validated offline
  against the vendored OpenLineage 2-0-2 schema (Apache-2.0, source + sha256 in tests/provenance/vendor/README.md).
  Nothing CI-only in my steps.
- SEC: 043 (hash chain + Ed25519 signature per batch, trusted-keys-only verification, daily WORM anchor job body,
  hourly verification job body with alert log; scheduling = job queue, alert rules = SEC-102 not built);
  044 (PipelineVersions immutable + digest-addressed, images must be @sha256 without tag; cosign verification of
  step images is m3-exec's worker, 3.3); 074 is the worker sandbox (m3-exec, 3.3): nothing in my paths runs steps.
- Deps: jsonschema==4.26.0, prov==3.2.2 in services/platform test extra (uv.lock contains them).
- Open: (1) Ed25519 signing key is a KMS stub (env seed / dev ephemeral); a KMS-held asymmetric key is an infra
  step. (2) New tags `nf.prov-node.v1`, `nf.prov-anchor/v1` (like auditb) need hashing spec v2. (3) Anchor/verify
  jobs need scheduling on the 3.3 queue and SEC-102 alert rules. (4) import-linter's CLI (test_core_imports) calls
  dictConfig and disables every existing logger in the pytest process; M2 log-scan tests could be affected the same
  way. (5) Check-constraint names are doubled by the naming convention (e.g. ck_prov_batch_ck_prov_batch_prev),
  same as M2's migrations; harmless. (6) pytest `from conftest import` resolves to whichever conftest loaded last;
  my conftests re-export the core fixtures module to stay safe.

## 2026-09-26 m3-exec -> queen: 3.3, 3.4, 3.5 done (commits 8b4bc92, e20c629, 4e8ce97, 9fb2d5b; not pushed)
- 3.4 `services/workers/steps/nf_steps`: filter FIR/IIR, notch, re-reference, resample, bad channels (PREP
  deviation; no sklearn-free MNE equivalent), seeded ICA (infomax, EOG proxies), epochs, band power; every
  param explicit (pydantic extra=forbid, resolved defaults = run record); 2 published v1 PipelineVersions.
  **MNE 1.13.2 + scipy 1.18.1 installed locally** (import ~35 MB, ICA ~110 MB peak): the "equals direct MNE
  call" reference tests run LOCALLY. Notch: measured attenuation >= design attenuation (from MNE's FIR taps)
  - 3 dB, seeds 1-3 (measured ~52.5 dB vs design 52.3 dB, Hann-windowed DFT). Seeded ICA bit-identical
  in-process and across two processes.
- 3.3 migration 0004 (job, run, run_artifact; forced RLS; NOLOGIN `nf_worker` role reads/updates `job` only
  for the cross-tenant SKIP LOCKED claim). Lease tokens = fencing tokens; heartbeats; backoff retries;
  timeouts; cancel. Outputs encrypted with the subject key under a per-attempt staging prefix, staged
  invisible; finalize = provenance.record -> visible_at -> state in ONE txn. POST/GET /v1/runs,
  POST /v1/runs/{id}/cancel (authz matrix + audit + tenant). Upload complete enqueues `ingest.upload`
  (process_pending dispatch replaced). Worker `nf_runner`: in-process / sandboxed subprocess (scrubbed env,
  thread pins, in-interpreter network block, timeout, kill on cancel) / container runner (digest + cosign,
  --network none, read-only, non-root, cap-drop, limits) CI-only. services/workers/.importlinter: workers
  never import the API; nf_steps is standalone.
  Acceptance LOCAL: real worker process killed mid-run -> retried by another after lease expiry, 6 outputs,
  no duplicates, dead attempt's staging objects removed, 1 prov activity; provenance-commit fault injection
  -> outputs staged but invisible, retry publishes exactly one set; two-tenant isolation on job/run/artifact.
- 3.5 `tools/repro-check` (nf_repro): runs every published pipeline twice (fresh pinned process per step),
  exact = byte-identical, abs/rel tolerance; JSON + md report; compare-arch. `.github/workflows/repro-check.yml`
  (dispatch-only, SHA-pinned, uv sync --locked, ubuntu-24.04 + ubuntu-24.04-arm matrix, cross-arch job).
  Local: FAILS on an unseeded random step (exact and rel 1e-9), PASSES on the v1 library (11/11 steps).
  Cross-arch: CI-only (not run).
- Verify: pytest services/platform + services/workers 582+ passed, 12 skipped (CI-only); tasks.mjs lint 0,
  test 0 (665 passed, 13 skipped); ruff clean; import-linter 5/5 + workers 2/2.
- SEC: 044 (digest-only, cosign verify, unsigned -> refused; test with fake verifier), 074 (subprocess
  network block tested; full sandbox = container, CI-only), 073 (container flags; policy test on the
  command), 060 (conversion now only in the worker via the queue), 021 (RLS on new tables), 043 (anchor/
  verify job kinds).
- Open: no periodic scheduler (cron) for integrity jobs; container runner + cosign untested (no Docker);
  step image not built -> v1 pipelines use a `registry.invalid` placeholder digest the container runner
  refuses; local subprocess sandbox is not a security boundary (no memory limit, raw _socket reachable);
  StepLibraryCatalog not registered in the API (MNE import); LocalKms per-process (kill test hands the key
  set to the child, test-only); tree fixture now also creates one queued run (tests/core/conftest.py).

## 2026-09-26 m5-ledger -> queen: 5.1-5.5 done (branch feature/m5-ledger; 8 commits ed470c0..73861cd; not pushed)
- Own .venv in m5 (uv sync --locked); nf_platform resolves to m5. Migrations 0005m5_governance -> 0006m5_consent -> 0007m5_deletion (down_revision 0004; merge with M3's 0005_sweeps at integration). 9 new tables, forced RLS, TENANT_COLUMN + isolation seed updated.
- 5.1 governance/attributes: modality defaults on create (EMG -> peripheral, ECG/EOG/fNIRS -> unknown); SEC-022 writes owner/admin/data-steward only (also on create); PATCH /v1/recordings/{id}/channels, POST /v1/governance/channels/bulk, GET/PUT /v1/artifacts/{node}/governance; every change audited (governance.attributes, old/new); strictest inheritance through the lineage, explicit override flows downstream. LOCAL pass.
- 5.2 rules/*.yaml (CO, CA, CT, MT unverified w/o predicate, EU Art.9 flag) + manifest with content_sha256; facts only from market/regulation.md (test: quoted definitions verbatim); counsel-reviewed only with a reviewer record (none exists); GET /v1/classifications, /v1/jurisdiction-rules; "not matched by RuleSet v1", never "not regulated"; draft badges. LOCAL pass.
- 5.3 consent_document/consent_record append-only (trigger + nf_app SELECT/INSERT), per-tenant hash chain (tag nf.consent-record.v1), consent.anchor/consent.verify jobs on the 3.3 queue (WORM anchors, alert consent_chain_mismatch). LOCAL pass on real Postgres (UPDATE/DELETE/TRUNCATE rejected, modified row detected, consistent rewrite caught by anchor).
- 5.4 governance/policy.check = RBAC + quarantine + consent scope + classification (+ four-eyes for signal:export, SEC-024/142); fail closed (SEC-026); called by recording/signal reads, run create, provenance export, worker run start, aggregate/training. LedgerConsentPolicy replaces StubConsentPolicy as app default. Tests: route enumeration spy, 672-case matrix, training w/o model_training denied, fault injection. LOCAL pass.
- 5.5 POST /v1/subjects/{id}/withdrawals -> governance.deletion job: traverse, delete objects, aggregates re-run w/o subject or tombstoned (tenant policy), models flagged retrain_required (model_flag), exports listed, crypto-shred, WORM shred ledger + reapply_shreds (SEC-124 drill), Ed25519-signed JSON certificate (no PDF). KEY TEST LOCAL pass; MEASUREMENT: 0.114 s wall (job body 0.099 s) for 13 nodes vs 24 h target.
- SEC-034a now enforced in Keyring (M2 test test_crypto line ~198 updated: new write for shredded subject raises).
- Shared-file edits: routes.py/ingest_routes.py/runs_routes.py/provenance_routes.py/app.py/authorize.py (new actions)/audit DETAIL_KEYS/.importlinter (governance layer)/nf_runner worker+pipeline_job/core conftest (tree grants consent), authz matrix (EXPECTED, PUT/PATCH bodies, params_for), test_core_audit, test_stream_service (no-consent fixture keeps quarantine case), crypto-inventory rows 19-21, pyyaml==6.0.3 pinned (uv.lock +2 lines).
- Verify: ruff check/format clean; import-linter 5/5; tasks.mjs lint ok (prettier + licence-check skipped: no node_modules, so rules/*.yaml not prettier-checked). Full pytest services: previous full run 1 failure (logger disabled by import-linter CLI) fixed in 73861cd and re-verified; final full-run count was still running at hand-back.
- Open: certificate/anchor keys are KMS stubs; no PDF certificate; no cron scheduler for consent jobs; ruleset not loaded into Postgres (repo YAML, in-process); subject metadata rows (label, stored_object) kept after withdrawal; SEC-024 four-eyes only in policy (no approval workflow/endpoint, no raw export endpoint yet); DB backup window 35 d is an ESTIMATE (NF_DB_BACKUP_WINDOW_DAYS); open streams not explicitly aborted on shred (next encrypt fails); tags nf.consent-record.v1/nf.ruleset.v1 for hashing spec v2.
## 2026-09-26 m3-sweeps -> queen: 3.6 done, 3.9 scaffolded (commits 2da386a, 2c85f36, 82f116e; not pushed)
- 2da386a `nf_steps.decode_lda@1`: NumPy shrinkage-LDA (no sklearn on this PC; named for what it is),
  deterministic stratified CV, accuracy in step info AND in the output artifact's metadata. Edited m3-exec's
  EXPECTED_STEPS (+1 line) and nf_steps/__init__ (import registers the step).
- 2c85f36 3.6: migration `0005_sweeps` (down_revision "0004"; tables sweep, sweep_run; forced RLS),
  `nf_platform/sweeps/service.py`, `api/sweeps_routes.py`: POST /v1/sweeps (202), GET /v1/sweeps/{id},
  GET /v1/sweeps/{id}/report; actions sweep:create (writers, data:write) / sweep:read (readers, data:read).
  DECISION: each grid point is its own published content-addressed PipelineVersion (`<base>.mv-<12hex>`,
  same version), not a run-level override; runs stay described by (pv ID, input, image, seed); sweep = PROV
  activity wasAssociatedWith base+variants, used recordings. Report cells: run_id, run PROV activity, metric
  artifact node + sha256; aggregates list run_ids. Shared edits: app.py router, authorize.py, models.py
  (+TENANT_COLUMN), .importlinter (api -> (sweeps) -> (jobs)), core tests (authz matrix, tenant seed, audit
  read-route test creates a sweep, imports known-set).
- Planted effect (local, real in-process worker, 6 runs): class-2 Hann 5 Hz burst ([3,7] Hz) in white noise;
  expected ordering derived from MNE filter taps (retained energy l_freq 1/4 Hz >= 0.9, 10 Hz <= 1e-3; notch
  50/60 >= 0.999). Result: accuracy 1.0/1.0/0.4 at l_freq 1/4/10 for both notches; l_freq range 0.6, notch 0.0.
  Every cell checked against run record, run artifact, decrypted artifact content and its PROV node.
- 82f116e 3.9 scaffold `research/multiverse/` (study.json, datasets.json TODO placeholders only, base pipeline,
  run_study.py, README) + `.github/workflows/multiverse-study.yml` (dispatch-only + confirm input, SHA-pinned,
  uv sync --locked). Status "Planned / in preparation"; nothing downloaded/run/published.
- Verify: pytest services exit 0 (0 failed, 12 skips all CI-only); ruff + format clean on my paths;
  import-linter 5/5; ci-lint + repo-guard clean; tasks lint/test exit 0 with --skip=web(,prettier). Without the
  skip they fail ONLY on m3-console's in-progress apps/console (prettier 31 files, ruff e2e/stack.py, and the
  packages/content brand-token test hits apps/console/src/api/openapi.json:1601 "neuroforge.ingest...").
- Open: (1) 3.9 `ingest` not built (depends on chosen dataset format); `sweep` stage expects a CI platform
  instance (vars.NF_STUDY_API_URL / secrets.NF_STUDY_API_TOKEN) that does not exist; no dataset selected (no
  EEG decoding accession in repo docs). (2) No StepLibraryCatalog in the API: an override of a wrong type
  publishes fine and fails at the worker (non-retryable). (3) No sweep cancel/list endpoints. (4) The report
  reads the metric from the run record; the artifact holds the same number (tested), but the API does not
  re-read artifacts. (5) Merge with M5's revisions needs your merge revision (0005_sweeps down_revision 0004).

## 2026-09-26 m3-console -> queen: 3.8 console done (commits 53c6ce3, fe1fa12, b39c039, c7bfb37, f92f5e7; not pushed)
- `@nf/console` (apps/console): React 19.2.0 + Vite 6.4.3, exact pins; runtime deps react/react-dom only (+ @nf/themes clinical tokens/self-hosted IBM Plex, @nf/content brand). Login (OIDC code + PKCE, popup + same-origin BroadcastChannel, tokens memory-only), projects/datasets, upload (browser SHA-256, parts, poll), recording viewer (pyramid level choice, min/max envelope, canvas), runs, sweep report (m3-sweeps' generated types), lineage explorer (keyboard listbox + SVG).
- Typed client: scripts/gen-api.mjs -> src/api/generated.ts + authz.json from the FastAPI app and nf_platform.auth.authorize; drift test (needs .venv; CI required). Raw openapi.json NOT committed: it contains `neuroforge.ingest.v1.IngestService` (gRPC default), which the brand-token test bans in apps/.
- Local, Node 22: console tsc + vitest 37/37 + build + dist/drift/mock-IdP node tests 14/14; `tasks.mjs lint` exit 0 (licence-check, prettier, ruff incl. apps/console); `tasks.mjs test --skip=rust` workspace tests + pytest 712 passed/13 skipped (one run hit the brand-token failure above, fixed, workspace tests re-run green: `test --skip=rust,python` exit 0). Rust not run (untouched). Bundle: JS 76.2 KB gzip (251 KB raw), CSS 2.2 KB gzip, fonts self-hosted.
- CI-only (written, not run): e2e/console.spec.ts + a11y.spec.ts, e2e/stack.py (pgserver + API + worker thread in one process), e2e/serve.mjs, .github/workflows/console-e2e.yml (dispatch, SHA-pinned; ci-lint + repo-guard clean). No browsers installed locally. Mock IdP protocol tests (PKCE, rotation, reuse detection) run locally; a mock token was verified by the platform's OidcVerifier.
- Shared-file touches: tools/licence-check/lib.mjs (+1 root, apps/console; platform-eng's file) and the new workflow. tasks.mjs unchanged (`pnpm -r test` picks up @nf/console). docs/security/licences.md "Scope" still says apps/web only: owner of that doc should add apps/console.
- Open: (1) no GET /v1/runs or /v1/sweeps list routes: the runs page lists runs of this browser session + open by ID, sweeps open by ID. (2) uvicorn is not in uv.lock; the e2e stack uses `uv run --locked --with uvicorn==0.35.0` (unhashed, CI-only) until the platform adds an ASGI server dep. (3) SEC-015 parts only the IdP can do: <=15-min access tokens, reuse detection, 12-h family expiry, cookie flags; the console clamps/ends sessions but the IdP must be configured (owner). (4) Trusted Types (`require-trusted-types-for 'script'`) is in the CSP; only the CI e2e can confirm no runtime violation. (5) whoami/lineage/window responses are untyped in the OpenAPI (hand types in src/api/types.ts) until M4 4.1. (6) Pre-signed S3 part URLs would need the object-store origin in connect-src. (7) After any API route change, rerun `node apps/console/scripts/gen-api.mjs` or the drift test fails.

## 2026-09-26 m5-secfix -> queen: M2-REVIEW fixes done (branch feature/m5-ledger; 4 commits 4ddde86, 7285d6d, a1f73d4, cd4ad22; not pushed)
- **F1 / SEC-034a closed:** the stream checks the subject tombstone before each chunk (+ catches SubjectKeyUnavailable) -> FAILED_PRECONDITION + `stream.aborted` audit; `Keyring.is_shredded`. Test: shred between chunks of one call -> seqs stay [0,1], subject_key rows unchanged (all shredded), reconnect refused; encrypt still raises.
- **F2 / SEC-017 closed:** StreamChunks checks token exp per chunk and device revoked_at every 60 s or 500 chunks (injectable clock) -> UNAUTHENTICATED + audit; edge client treats the "token expired during the stream" abort as retryable (fresh token, resume from next_seq). Tests: revoke (time window and N-chunk), expiry + resume. Limit: checks run when a chunk arrives; an idle open stream is not closed server-side.
- **F3 closed (policy parts 1+2):** certificate (signed) states "Unrecoverable in all copies after the backup retention window of N days (ends YYYY-MM-DD)" from NF_DB_BACKUP_WINDOW_DAYS (default 35 = ESTIMATE, owner sets the real value); restore re-applies shreds = existing test_restore_drill_reapplies_shreds.
- **F5 closed:** test: 5 bad tokens, no token/part/claim value in auth.failure rows; audit validator also rejects `nfd1.` tokens.
- **F4 open** (M3 checklist, signed audit batches), **F6 open** (pepper {current, previous}), **F7 open: per-modality amplitude limits MUST be set before any real-data tenant.**
- **MinIO:** CI-only, digest-pinned; repo SBOM now includes security/sbom-ci-images.json and marks bitnamilegacy/minio nfb:supportLevel=unmaintained (tests: CLI, compose digest match, no other compose file). **Open for the owner: replace it before M5 closes** (SEC-COVERAGE known gaps).
- **hw-guard services/ scope:** lint scans 134 services files (SEC-091 in full outside tests/; SEC-090 on route literals / operation_id / action_extra); fixtures bad-service-route + bad-service-outlet fail, alembic `command` + test-generated XDF "Stimulus" markers pass; denylist shared in tools/hw-guard/denylist.json; pytest surface test over app.openapi() (46 paths, ~1,180 names), gRPC _pb2 + servicer (43 names), outbound schemas (none yet) with a negative control. SEC-COVERAGE rows updated/added.
- **Verify:** `tasks.mjs test`: node tools, workspace, cargo OK; pytest 789 passed, 1 failed = test_layers_cover_every_top_level_module (m5-evidence's placement.py, fixed by their df73ae3; re-run passes). `tasks.mjs lint`: all steps pass except licence-check `argparse@2.0.1 (Python-2.0) [apps/web > js-yaml]` from m5-evidence's 6337248 (told them in their inbox).

## 2026-09-26 m5-evidence -> queen: 5.6, 5.7, 5.8 done (branch feature/m5-ledger; commits 6337248, df73ae3, f782be8, 91ef216; not pushed)
- 5.6 (6337248, 91ef216): /law-tracker rules table generated at build time from rules/*.yaml (apps/web/src/lib/rules.mjs, js-yaml 4.3.2 as a devDependency = build-only, so licence-check stays clean; m5-secfix caught the first version). Columns: jurisdiction, citation/source (+ research ref, DOI link), effective date (or "Not stated in our research notes"), what it covers (title, quoted definition, obligations, notes), review badge (Draft / Unverified / Reviewed by counsel). Copy + hand-kept context rows (MIND Act, other states, HIPAA scope, AI Act, Chile) stay in @nf/content; banner kept; never "not regulated". Tests (apps/web/test/law-tracker.test.mjs): loader + temp-copy change; dist rows = RuleSet rules in both themes, MT shown unverified; NF_WEB_REBUILD_TEST=1 rebuild of clinical into a temp dir with a changed ct.yaml -> page changed (LOCAL pass; skipped by default because it is slow). astro.config gained NF_WEB_OUT_DIR (test only).
- 5.7 (df73ae3): infra/policy/phi-services.json = BAA-listed services ONLY as market/regulation.md §3 names them (S3, Timestream, SageMaker AI; grade D; the quote is checked verbatim). tenant.phi (migration 0009m5_phi -> 0008_merge_sweeps_m5) + nf_platform.placement: uploads, streams (storage + database) and runs (+ compute) of a phi tenant -> 403 + audited authz.denied (action phi:placement) unless every NF_PLACEMENT_* service is listed; fails closed. IaC: infra/modules/phi-guard (plan precondition), envs/dev declares its modules + pins phi=false; Python test proves phi=true cannot be placed on the env services (LOCAL); `tofu test` for the module + dev run are CI-only (added to infra.yml). docs/compliance/: README (service list, delivery record), risk-analysis, incident-response (PHI addendum to security/INCIDENT-RESPONSE.md), access-review (SEC-012/052/104/114), workforce-training; all DRAFT, "Delivered to counsel: pending (owner action)", no compliance claims (tested). Website BAA wording stays planned (tested).
- 5.8 (f782be8): POST /v1/exports/fda-evidence (action evidence:export: owner/admin/data-steward/auditor, not API keys; policy.check; audit data.export with the zip sha256; other tenant -> 404). Zip: traceability matrix (docs/requirements/platform.yaml, 29 IDs, 27 with tests, 2 flagged: SEC-104 process, SEC-110 owner action; results from CI JUnit via NF_EVIDENCE_JUNIT, else "no CI results supplied"), SBOM if NF_EVIDENCE_SBOM else "SBOM attached in CI", release notes = open issues of docs/hive/M*-REPORT.md, PROV-JSON lineage of the chosen node, SOUP entries (docs/requirements/soup.yaml, versions from manifests), manifest with per-file sha256. Labelled "SCAFFOLD, NOT A SUBMISSION"; IEC 62304 + both FDA guidances named only, UNVERIFIED. Byte-identical regeneration tested via API and builder (LOCAL). In the authz matrix + policy route-enumeration test; console client regenerated.
- Shared edits: routes.py (enforce_placement), ingest_routes.py (2 calls), runs_routes.py, app.py, authorize.py (+evidence:export), policy.py (ACTION_SCOPES), audit DETAIL_KEYS (+sha256), config.py (Placement), models.py (Tenant.phi), .importlinter (evidence, placement at the governance level) + test_core_imports known set, authz matrix, test_gov_policy DATA_TOUCHING, content schema/types/test, infra.yml.
- Verify (m5, Node 22): tasks.mjs lint exit 0; both web builds ok (copy-lint clean); web tests 49/49 incl. the rebuild test; tasks.mjs test exit 0 (pytest 802 passed / 13 skipped, cargo ok, workspace + console ok).
- Open: (1) no PHI tenant can be placed on the current stack (RDS/ECS/KMS/Secrets Manager/VPC endpoints are not in the cited list): owner must verify against the provider's HIPAA-eligible list or change the architecture; no provider BAA signed. (2) Policies not delivered to counsel (owner). (3) Kit inputs in a deployment need the source tree + CI JUnit/SBOM baked into the image (NF_EVIDENCE_ROOT/JUNIT/SBOM); node:test results only map by test name; regulatory-consultant review is an owner action. (4) phi flag has no API (set by provisioning SQL).

## 2026-09-26 m6-spec -> queen: hashing spec v2 needs nf-core (Rust) support: for nfb-build-lead-2 (M4)
- docs/spec/hashing.md is now v2 (e8e263d; v1 rules and spec/test-vectors/ids.json unchanged). New vectors:
  spec/test-vectors/ids-v2.json. Python reference + platform code reproduce all of them.
- nf-core does NOT read ids-v2.json yet. Adding it to `core/nf-core/tests/vectors.rs` (and any Rust builders for
  auditb / nf.prov-node.v1 / nf.stream-chunk.v1 / nf.device-token.v1 / nf.wal.v1 / nf.training-*.v1 that M4 needs)
  is owned by nfb-build-lead-2 in the m4 worktree. I did not touch core/. Please forward.

## 2026-09-26 m6-spec: done
- Kept from the stopped run (reviewed, tests green): hashing.md v2 §8-§12, nf_ids_v2.py (stdlib + RFC 8032 Ed25519),
  gen_vectors_v2.py, test_vectors_v2.py, tests/spec_v2, object-storage.md, CI compose note, crypto-inventory edit.
  Fixed: the M6 tags were only "reserved" with no vectors -> now §9.6/§9.7 with vectors + platform test against
  registry/manifest.py; §11 records two new departures (unkeyed training-subject hash; manifest `tenant` not
  normalised, suggested to m6-registry).
- Commits: e8e263d (spec v2), 88221d9 (MinIO CI-only + test), b4cdd32 (training-tag platform test), 73f414c
  (SEC-034a DB guard, migration 0012m6_key_tombstone on 0011m6_sisa, two-process race test, SEC-COVERAGE row).
- F1 hardening also found and closed two app-level gaps: shredding a subject that never had a key left no
  tombstone row (now inserted), and a concurrent "retire" UPDATE could write wrapped_dek back onto a shredded row
  (trigger refuses). tests/governance/test_gov_deletion.py restore drill now simulates the restore in replica mode
  (a real restore does not fire triggers); its assertions are unchanged.
- Open: nf-core v2 (above); v3 candidates in spec §11 (tag the untagged signatures, keyed training-subject hash).

## 2026-09-26 m6-registry -> queen: 6.1, 6.2, 6.3 done (feature/m6-registry; commits f67808c, 103a773, 0bd0087, 3573d1e; not pushed)
- Kept from the stopped run (reviewed): migration 0010m6_registry (6 tables, forced RLS, deployments/approvals
  append-only), ORM, manifest.py (subject/manifest hashing), vocab.py (Art. 5(1)(f)/(g)/(a), SEC-092, SEC-144 rules),
  weights.py (safetensors/ONNX structural checks), tenant-isolation seed. Fixed: one version per model node/weights
  object (unique), card values reject NaN/Inf, manifest tenant canonicalised, .importlinter contract replaced
  (registry layer beside sweeps, above governance; api may import it). Then wrote service.py, retrain.py,
  api/registry_routes.py (14 routes), actions model:read/create/deploy/approve/exception (+ existing model:train,
  model:publish), nf_runner handler `registry.retrain`, docs/spec/model-card.schema.json, SEC-COVERAGE M6 rows.
- Acceptance (all LOCAL, Postgres via pgserver): 6.1 no manifest -> 422 `manifest_required`; lineage from a version
  reaches every training subject's raw_file + recording node; manifest = lineage-computed hashed subject IDs.
  6.2 emotion/cognitive-state model, EU (and member state) workplace/education -> 403 `eu_ai_act_5_1_f`, stored
  `refused`, audited `registry.deployment`/denied; allowed with a documented medical/safety exception record (scoped
  to model+setting+jurisdiction); SEC-092 three control contexts x EU/US always refused + audited, even with an
  exception. 6.3 in the M5 5.5 world: withdrawal -> version retrain_required, approved deployment effective_state
  `blocked`, new deployments refused; POST .../retrain -> registry.retrain on the queue (toy recipe follows the
  re-run average) -> v2 manifest excluded_subjects=[A], subjects=[B], lineage reaches no A recording; v1 stays
  blocked. SEC-143 publish needs privacy section + four-eyes + commercial_use. m6-sisa's SISA recipe runs through it.
- Verify at HEAD 7578ddc: pytest 924 passed / 14 skipped; import-linter 5/5; ruff clean. `tasks.mjs lint` fails ONLY on
  prettier for m6-console's committed apps/console/src/pages/models.test.tsx + registry/context.ts; `tasks.mjs test`
  fails ONLY on the console drift test (m6-sisa's soup routes landed after m6-console's regen). Both told to m6-console.
- Open: retrain is API-triggered (a "template"), not auto-enqueued by the DeletionJob; no webhook to model owners
  (§8.4); no inference API, so the SEC-144 rate limit is recorded, not enforced; ToS wording for SEC-092 is an owner
  item; EU AI Act checks are machine rules from market/regulation.md, not counsel-reviewed; not certified unlearning.

## 2026-09-26 m6-fix: BUG-HUNT M2, M3, M4, M5+L6, M11+L4 fixed (branch feature/m6-registry, not pushed)

- Commits: bc76ccd M2 (migration 0013m6_retrain_active, partial unique index + savepoint job/row), fe28854 M3
  (publish locks the version row and re-checks taint; deletion.flag_models takes the same lock), 41905c3 M4
  (migration 0014m6_key_shred_freeze: any non-no-op UPDATE of a shredded subject_key row -> NF34A; bump_count test;
  SEC-034a row updated), e69fdd2 M5+L6 (manifest inputs deduped in reference + platform; consent scopes
  canonicalised before hashing; ids-v2.json +77/-0, existing vectors byte-identical), ad84586 M11+L4 (console).
- Every regression test was run and FAILED on the pre-fix code first (M4: the interleaving test passes on the
  shipped code because the filter works; it fails with the filter removed under the 0012 trigger, and the new
  trigger test failed before 0014).
- Deviation from brief (M2): the sequential second retrain request returns the existing active retrain (202, same
  id), not a 409, so the concurrent loser now gets that same answer. 409 only if the winner already finished.
- **nf-core (Rust, nfb-build-lead-2) must implement the same v2 rules:** dedupe (and lowercase-fold) training-manifest
  `inputs` (§9.7, vector case `duplicate-inputs`) and dedupe+sort consent `scopes` before hashing (§9.3, vector
  `consent_record_noncanonical_scopes`).
- Verify: `tasks.mjs lint` exit 0; `tasks.mjs test` exit 0 (pytest 938 passed / 14 skipped, console 58 vitest +
  build + drift, web, cargo). No routes/fields added, so no client regen. m4's pgserver postgres processes were left
  running (not mine).

## 2026-09-27 appsec-fix (m5, fix/appsec-m1-m3): WARNING, foreign commit in this worktree
A commit "4000-step results into papers" (a153c8d, author Marius Carlsson, 00:14) appeared on fix/appsec-m1-m3 in the m5
worktree's reflog. It contained ONLY my uncommitted M2 files (someone ran `git commit` with my staged/working changes,
probably a research agent whose cwd drifted into m5). I soft-reset it (unpushed, local) and recommitted the same content as
2284a65 "audit: AppSec M2 ...". Please check which agent committed papers work here; its own files did not land in m5.

## 2026-09-27 appsec-fix DONE (m5, fix/appsec-m1-m3, not pushed)
- b94910d M1 (SEC-105): audit.batch (hourly) + audit.verify (daily) on the 3.3 queue; signed nf.audit-anchor/v1 per scope in
  the WORM audit bucket; verify_chain checks scope + row count/first/last seq; GET /v1/audit/batches/{seq}/object. Tests:
  tests/governance/test_gov_audit_integrity.py (failed first: module/route missing).
- 2284a65 M2: migration 0015_audit_roles (nf_audit_writer / nf_audit_batcher, continuity trigger NF105, event insert policy +
  seq guard). Tests tests/core/test_core_audit_roles.py (13, all failed on the old code; forged 9e18 head accepted before).
  DEPLOYMENT REQUIREMENT: batcher needs its own DB login (NF_AUDIT_BATCHER_DATABASE_URL); API login must not get nf_audit_batcher.
- 1be4be1 M3 (SEC-146): weights_source in manifest/API/console/SOUP; four-eyes for upload deploy/publish; any withdrawal after
  registration taints upload versions. Tests tests/registry/test_reg_upload_lineage.py (attack test failed first).
- SPEC: hashing v2 §9.7 additive field weights_source + 2 new vectors in ids-v2.json (diff = additions only). nf-core
  (nfb-build-lead-2) must reproduce them when it adds ids-v2.json. Audit anchor documented in §10.4 without a vector.
- lint exit 0; full test: 968 passed, 1 failed = tools/repro-check test_harness_passes_on_the_v1_library, caused by
  OMP_NUM_THREADS=4 (RESOURCE-RULES) in the env (expects "1"); passes when re-run without the override. Not touched by me.
- Open: no scheduler enqueues audit.*/consent.*/provenance.* jobs; events deleted BEFORE batching are undetectable (no per-row
  DB hash chain); SEC-146 at upload registration still trusts declared inputs; foreign commit incident (note above).
