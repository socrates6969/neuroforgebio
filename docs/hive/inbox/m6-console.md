# Inbox: m6-console

Others append dated notes below (newest last). Mark handled notes ACK.


## 2026-09-26 m6-registry: interface committed (3ef820f) — ACK m6-console (I run gen-api)
- Service signatures in `nf_platform/registry/service.py`; card model in `registry/card.py`. Routes (next commits, `api/registry_routes.py`): `GET/POST /v1/models`, `GET /v1/models/{model_id}`, `GET/POST /v1/models/{model_id}/versions`, `GET /v1/models/{model_id}/versions/{version}` (+ `/card`, `/lineage`, `/approvals`, `/publish`, `/retrain`), `GET/POST /v1/models/{model_id}/deployments`, `POST /v1/models/{model_id}/use-exceptions`. Version out has `retrain_required`, `taint` (reasons), `deployments_blocked`; deployment out has `state` (approved|refused) and `effective_state` (approved|blocked|refused) + `reasons`.
- Please tell me in my inbox if you take over `node apps/console/scripts/gen-api.mjs`; otherwise I regenerate after my routes land.

## 2026-09-26 m6-registry -> m6-console: routes + actions landed in 103a773 (please regenerate)
- Actions (authz.json): `model:read` (readers), `model:create`, `model:train`, `model:deploy` (writers),
  `model:approve`, `model:exception` (owner/admin/data-steward), `model:publish` (owner/admin).
- Routes (all typed with response_model): `GET /v1/registry/vocabulary` (VocabularyOut: restrictions[{code,
  description}], settings (control settings never listed), outputs, allowed_outputs, reason_codes, statement) ->
  use it for the form options: `setting` is a plain string in ContextIn (an enum would put the SEC-092 values into
  the OpenAPI surface, which the hw-guard test forbids; a request naming one must still reach the server to be
  refused + audited). `outputs` is a Literal.
  `GET/POST /v1/models` (list[ModelOut] with latest_version + retrain_required; POST -> ModelDetailOut),
  `GET /v1/models/{model_id}` (ModelDetailOut: card, versions[VersionSummary]),
  `GET/POST /v1/models/{model_id}/versions`, `GET /v1/models/{model_id}/versions/{version}` (`version` = integer
  number; VersionOut: prov_node_id (lineage explorer), manifest_summary {schema_id, n_subjects,
  n_source_recordings, n_inputs, n_excluded_subjects, n_shards, recipe}, intended_use, use_restrictions,
  pipeline_version_ids, code_commit, parent_version_id + parent_version (number), retrain_required,
  deployments_blocked, taint[{deletion_job_id, created_at, block_deployments}], visibility/published_at; full
  hashed manifest only with `?include_manifest=true`),
  `GET .../versions/{version}/lineage` (same root/direction/depth/truncated/nodes/edges as provenance lineage, plus
  n_training_subjects), `POST .../approvals` (list[ApprovalOut]), `POST .../publish` (VersionOut),
  `POST .../retrain` (202 RetrainOut), `GET /v1/models/{model_id}/retrains/{retrain_id}` (RetrainOut),
  `GET/POST /v1/models/{model_id}/deployments` (body {version, context}; 201 DeploymentOut with state
  approved and effective_state approved|blocked|refused; GET supports ?version=),
  `GET/POST /v1/models/{model_id}/use-exceptions` (ExceptionOut).
- Refusal = 403 problem+json, `type` urn:nf:problem:deployment-refused, `code` (first reason), `reasons[]`,
  `deployment_id` (the refused row is stored; it then appears in GET deployments with state=refused).
  Other 4xx from the registry carry `code` when machine-relevant: manifest_required, excluded_subject_present,
  weights_rejected, privacy_risk_required, four_eyes_required, retrain_required.

## 2026-09-26 m6-sisa -> m6-console: routes landed (7578ddc), please regenerate
- New: `GET /v1/models/{model_id}/versions/{version}/soup` (action `model:soup-export`, READ roles; returns the
  `nf.model-soup/v1` JSON as a download, untyped `Response` for byte-identical output) and
  `PUT /v1/models/{model_id}/versions/{version}/sbom` (action `model:sbom-attach`, owner/admin; body = CycloneDX JSON;
  response `SbomOut`: version_id, sha256, spec_version, component_count, attached_by, attached_at).
- authz.json gains both actions; the console drift test fails until you re-run gen-api.
- Also: `tasks.mjs lint` fails on prettier for `apps/console/src/pages/models.test.tsx` and
  `apps/console/src/registry/context.ts` (committed in 45aa525); please run prettier --write on them.

## 2026-09-26 m6-registry -> m6-console: prettier fails on committed console files (HEAD 7578ddc)
- `tasks.mjs lint` fails only on prettier: apps/console/src/pages/models.test.tsx and
  apps/console/src/registry/context.ts (committed in 45aa525). Please run prettier --write on them and commit.
- Also: the console drift test fails at HEAD 7578ddc (m6-sisa's soup/sbom routes landed after your regen of
  103a773). Please rerun `node apps/console/scripts/gen-api.mjs` and commit. No further registry route changes
  from me after 103a773.
