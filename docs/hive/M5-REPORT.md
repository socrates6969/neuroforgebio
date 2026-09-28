# M5 report: compliance ledger (branch `feature/m5-ledger`)

Date 2026-09-26. Branched from `feature/m3-pipelines` after step 3.1 (decision D5); M3 wave B and current main (@89c3ab9, incl. the M3 merge and `security/M2-REVIEW.md`) merged in. Queen: nfb-build-queen. Workers: m5-ledger (5.1–5.5), m5-evidence (5.6–5.8), m5-secfix (M2 security-review findings). Nothing deployed; no infra applied; nothing sent to counsel; CI dispatch-only.

## Verified locally by the queen

- `node tools/dev/tasks.mjs lint`: exit 0 (incl. hw-guard now scanning `services/`, licence-check, Prettier, ruff, import-linter).
- Both website builds: exit 0. `node tools/dev/tasks.mjs test`: exit 0. **pytest 802 passed, 13 skipped** (all CI-only); console 37/37; web 49 incl. the law-tracker rebuild test; cargo green.
- Real local PostgreSQL 16 (pgserver). Alembic heads merged: `0005_sweeps` + `0007m5_deletion` → `0008_merge_sweeps_m5` → `0009m5_phi`.

| Step | Acceptance test | Local result |
|---|---|---|
| 5.1 | Every governance-attribute change emits an audit event; artifacts inherit the strictest attributes through the lineage; writes only by data-steward/admin (SEC-022) | pass |
| 5.2 | Table-driven: EMG (peripheral) matched by CO and CA, not CT; CA with `derived_from_non_neural=true` not matched by CA; output says "not matched by RuleSet v1", never "not regulated"; draft/unverified badges; facts only from `market/regulation.md` (quoted definitions checked verbatim); nothing marked counsel-reviewed | pass |
| 5.3 | UPDATE/DELETE/TRUNCATE on the consent ledger rejected by the database; a modified row fails chain verification; a consistent rewrite is caught by the WORM anchor, which alerts | pass |
| 5.4 | Every data-touching route calls `policy.check` (route enumeration); 672-case matrix roles × classifications × consent scopes; training without `model_training` scope denied; fail closed on exceptions (SEC-026) | pass |
| **5.5** | **Key test:** subject → 3 recordings → 2 runs → group average → toy model; withdraw: objects crypto-shredded incl. the backup copy; group average re-run without the subject (or tombstoned per policy); model flagged `retrain_required`; signed certificate lists every affected node and states the DB-backup window end date; audit events; an unrelated subject untouched. **Duration 0.114 s** (13 nodes) vs the 24 h target | pass |
| 5.6 | `/law-tracker` table generated from `rules/*.yaml` at build time; a changed rule file changes the page at the next build; unverified rules shown as unverified | pass |
| 5.7 | `phi=true` tenants cannot be placed on non-listed services (platform placement guard + IaC guard, Python test over the OpenTofu files); draft policies delivered-to-counsel = pending; website keeps "BAA (planned)" | pass; `tofu test` CI-only |
| 5.8 | FDA Evidence Kit v0 zip (traceability matrix, SBOM or a CI pointer, release notes from open issues, PROV-JSON, SOUP), labelled "scaffold, not a submission"; every requirement ID has a test or is flagged (29 IDs, 2 flagged: SEC-104 process, SEC-110 owner action); **byte-identical regeneration** | pass |

## Security review of M2 (nfb-security, `security/M2-REVIEW.md`)

- **Closed with tests:**
  - F1 / SEC-034a: a shredded subject gets no new key, and open streams are aborted with an audit event.
  - F2 / SEC-017: revocation and expiry are re-checked mid-stream (60 s or 500 chunks) and the client resumes.
  - F3: the certificate states the backup-window end date, and a restore re-applies shreds.
  - F5: no token bytes in auth-failure audit rows.
- **hw-guard scope** broadened as decided:
  - SEC-091 applies in full to `services/`.
  - SEC-090 runs on the external surface: 46 OpenAPI paths (~1,180 names), gRPC descriptors, and outbound schemas.
  - The negative fixtures fail and the alembic/"Stimulus" cases pass. There are no allow markers.
- **MinIO:** CI-only, digest-pinned, and marked `nfb:supportLevel=unmaintained` in the SBOM.
- **Still open:** F4 (signed audit batches, on the M3 checklist), F6 (pepper rotation grace), F7 (**per-modality amplitude limits must be set before any real-data tenant**).

## CI-only

- `tofu test` for the phi-guard module and the dev env.
- The evidence kit with real CI JUnit/SBOM inputs.
- The platform integration job (Postgres + MinIO).

## Open issues (owner decisions marked 🔒)

1. 🔒 **No PHI tenant can be placed on today's stack.** The cited BAA list (`market/regulation.md` §3) names only S3, Timestream and SageMaker AI; RDS, ECS, KMS and others are not in the cited source. The owner needs to verify the provider's current HIPAA-eligible list or change the architecture. No BAA is signed.
2. 🔒 **Counsel:** the RuleSets and the draft BAA policies still need counsel review (nothing is counsel-reviewed). Regulatory-consultant review of the evidence kit is also pending.
3. 🔒 **Replace the MinIO CI image before M5 closes** (security condition).
4. **Missing pieces:**
   - no approval workflow for four-eyes (SEC-024 is enforced in policy only);
   - no raw-export endpoint;
   - no PDF certificate;
   - no cron scheduler for anchor/verify jobs;
   - the `phi` flag has no API (set at provisioning).
5. **Keys and hashing spec:**
   - certificate, anchor and provenance signing keys are KMS stubs;
   - new hashing-spec tags need spec v2: `nf.consent-record.v1`, `nf.ruleset.v1`, plus the M2/M3 tags.
6. **Backups and retention:**
   - the DB backup window (35 d) is an ESTIMATE until the owner sets PITR, and security asks for 14 d (SEC-120);
   - subject metadata rows are kept after withdrawal.
