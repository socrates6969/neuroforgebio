# M6 report: governed model registry (branch `feature/m6-registry`)

Date 2026-09-26. Cut from `feature/m5-ledger` @0b3ec84 (merged to main by the lead). Queen: nfb-build-queen. Workers: m6-registry (6.1–6.3), m6-sisa (6.4, 6.5), m6-console (6.6), m6-spec (hashing spec v2, MinIO note, SEC-034a DB guard). The first worker run was stopped by mistake; the relaunched workers reviewed and finished the partial work. Nothing deployed; CI dispatch-only. M4 is owned by nfb-build-lead-2 (not in this branch).

## Verified locally by the queen

- `node tools/dev/tasks.mjs lint`: exit 0 (incl. hw-guard services/ surface scan). Both website builds: exit 0.
- `node tools/dev/tasks.mjs test`: exit 0. **pytest 924 passed, 14 skipped** (all CI-only); console 55/55 (8 files); web/tools green; cargo green.
- Migrations: `0010m6_registry` → `0011m6_sisa` → `0012m6_key_tombstone` (chain from `0009m5_phi`).

| Step | Acceptance test | Local result |
|---|---|---|
| 6.1 | Registering without a training-set manifest fails (422 `manifest_required`); the lineage from a model version reaches every training subject's raw node; the manifest holds lineage-computed hashed subject IDs | pass |
| 6.2 | Emotion/cognitive-state model in EU workplace/education → refused (`eu_ai_act_5_1_f`) and audited, allowed only with a documented medical/safety exception record; **SEC-092:** `closed_loop_stimulation`, `neuromodulation_control`, `actuator_control` always refused and audited, even with an exception | pass |
| 6.3 | In the M5 5.5 scenario: withdrawal → version `retrain_required`, approved deployments `blocked`; retrain job → new version's manifest excludes the subject and its lineage reaches no recording of that subject; old version stays blocked | pass |
| 6.4 | SISA: after a real withdrawal only one shard is retrained; other shards' checkpoints byte-identical and untouched; the retrained ensemble is bit-identical to SISA trained from scratch without the subject. Accuracy vs full retraining MEASURED (`docs/features/sisa.md`): mean 0.691 (SISA) vs 0.679 (monolithic) in one configuration, the opposite sign in another. **Configuration-dependent, not generalised. Not certified unlearning** | pass / measured |
| 6.5 | Per-version SOUP/OTS export includes every dependency of the model's container SBOM (fixture locally, real CycloneDX SBOM in CI) and states "not intended for real-time or safety-critical control" | pass (real SBOM = CI) |
| 6.6 | Console model list/detail: card, lineage, restrictions, taint with reason, deployment requests; control contexts never offered; unit tests local | pass; Playwright taint scenario + axe = CI-only |

## Also delivered

- **Hashing spec v2** (owner-approved): `docs/spec/hashing.md` v2. The v1 rules and `spec/test-vectors/ids.json` are unchanged. New `spec/test-vectors/ids-v2.json` covers the tags introduced in M2–M6. The Python reference and the platform code both reproduce every vector. **The nf-core (Rust) v2 support belongs to nfb-build-lead-2 (M4).**
- **MinIO:** production uses the cloud provider's S3 (Object Lock for audit), never MinIO (`docs/security/object-storage.md`). A test guards the non-CI files.
- **SEC-034a DB guard (nfb-security F1 hardening):**
  - A trigger refuses creating a subject key after a shred.
  - A two-process race test on real Postgres (shred vs encrypt) leaves no active key, and the encrypt side fails loudly.
  - It also closed two gaps: a shred without a prior key now writes a tombstone, and a concurrent retire cannot restore a wrapped key.

## CI-only

- Console Playwright + axe (6.6).
- The SOUP check against a real CycloneDX SBOM (`NF_MODEL_SBOM`).
- Platform integration (Postgres + MinIO).

## Open issues

1. **Retraining is only started through the API.** The DeletionJob flags the model but doesn't queue a retrain, and no webhook notifies model owners yet (webhooks are M4, step 4.6).
2. **No inference API,** so the SEC-144 rate limit is recorded, not enforced.
3. 🔒 **Terms-of-service wording** for the SEC-092 prohibition is an owner/legal item.
4. **EU AI Act checks** are machine rules from `market/regulation.md`, not counsel-reviewed.
5. **SISA is not certified unlearning.** The measured accuracy numbers are toy data only.
6. **Hashing spec v3 candidates** are listed in spec §11: tagging the untagged signatures, and a keyed training-subject hash.
7. **Carried over from M5:** KMS-held signing keys; scheduler + alert rules; PHI service list; counsel review.
