# M6 (governed model registry) build contracts

Branch `feature/m6-registry`, cut from `feature/m5-ledger` @0b3ec84 (pushed; includes main @89c3ab9), worktree
`C:\Users\mariu\neuro-worktrees\m5` (own `.venv` with editable nf_platform → m5; own node_modules).
General rules: `docs/hive/CONTRACTS.md`, `docs/hive/M2-CONTRACTS.md` §2 (local test strategy). Sources:
`architecture/BUILD-GUIDE.md` M6 (6.1–6.6), `architecture/BLUEPRINT.md` §3.7, §8.4, §8.6, `market/regulation.md` §5
(EU AI Act Art. 5), `docs/inputs/security/SECURITY-REQUIREMENTS.md` (6.1–6.2 → SEC-061, 092, 143–145; §G),
`docs/hive/M5-REPORT.md`. Inboxes: `docs/hive/inbox/<name>.md`.

**M4 runs in parallel** (nfb-build-lead-2, worktree `neuro-worktrees/m4`, branch `feature/m4-api-sdk`). Never touch that
worktree or `core/nf-core`, `bindings/`, `openapi/` (theirs). Their migrations `0006m4_*` chain from `0005_sweeps`; the
second to merge adds an Alembic merge revision.

## 1. Ownership

| Path | Owner | Steps |
|---|---|---|
| `nf_platform/registry/**` (Model, ModelVersion, model card schema, intended_use, use_restrictions, deployments, taint/retrain), `api/registry_routes.py`, migration `0010m6_registry` (down_revision `0009m5_phi`), `tests/registry/**` | m6-registry | 6.1, 6.2, 6.3 |
| `services/workers/steps/nf_train/**` (toy decoder + SISA sharded training), SOUP export `nf_platform/registry/soup.py` + its route, migration `0011m6_sisa` if needed (down_revision `0010m6_registry`), `tests/sisa/**`, `tests/soup/**` | m6-sisa | 6.4, 6.5 |
| `apps/console/**` registry views + regenerated client | m6-console | 6.6 |
| `docs/spec/hashing.md` (v2), `spec/test-vectors/ids-v2.json` (new file; `ids.json` stays frozen), `spec/reference/python/**`, MinIO prod note in `docs/` | m6-spec | spec v2 |
| `docs/hive/**`, M6-REPORT | queen | |

Shared registries (`api/routes.py`/`app.py` router list, `auth/authorize.py` actions, `governance/policy.py`
ACTION_SCOPES, `db/models.py` TENANT_COLUMN, `.importlinter`, tests/core authz matrix, policy route enumeration,
`apps/console/src/api` generated client): small append-only edits, re-read before editing, commit with the change.

## 2. Interfaces (m6-registry commits these signatures early; others code against them)

```python
# nf_platform/registry/service.py
def register_model(session, principal, *, name, card: ModelCard) -> Model
def register_version(session, principal, model_id, *, weights_object: ObjectRef, training_manifest: TrainingManifest,
                     pipeline_version_ids: list[str], code_commit: str, intended_use: str,
                     use_restrictions: list[str], parent_version_id=None) -> ModelVersion
    # TrainingManifest = hashed subject IDs (+ shard assignment for SISA), input recording/artifact prov node ids.
    # Registering without a manifest fails. Writes provenance (training activity used inputs, generated the version).
def request_deployment(session, principal, version_id, *, context: DeploymentContext) -> Deployment  # 6.2
def retrain_required(session, version_id) -> bool                                                   # reads M5 model_flag
```

## 3. Non-negotiables

- **No stimulation/actuator control** (SEC-092, §G): deployments with context `closed_loop_stimulation`,
  `neuromodulation_control` or `actuator_control` are refused and audited; the SOUP export states "not intended for
  real-time or safety-critical control". The hw-guard surface test must pass for every new route/schema (no `stim*`
  field names; use neutral names).
- EU AI Act Art. 5(1)(f): emotion/cognitive-state models in `workplace`/`education` contexts in the EU are refused
  unless a documented medical or safety exception record exists; the refusal is audited. Facts only from
  `market/regulation.md`.
- SISA is **not certified unlearning**; say so in docs; accuracy vs full retraining is measured, not claimed.
- policy.check on every data-touching route (M5 route-enumeration test), tenant isolation on every new table.
