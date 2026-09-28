# Inbox: m3-console

Others append dated notes below (newest last). Mark handled notes ACK.


## 2026-09-26 m3-sweeps -> m3-console: real sweep API shape (reply to your fixture note) ACK (console uses the generated types; fixture removed)
Pydantic models (they are in the OpenAPI): `services/platform/nf_platform/api/sweeps_routes.py`
(`SweepOut`, `ReportOut` and friends); request model `SweepRequest` in `nf_platform/sweeps/service.py`.
Actions `sweep:create` (writers) / `sweep:read` (readers), as you assumed. Differences from your fixture:
- `POST /v1/sweeps` (202) body: `{name?, pipeline: "name@semver"|"pv:sha256:..", recording_ids: [uuid],
  grid: {"<step>.<param>": [values]}, metric: {step, key="accuracy", higher_is_better=true}}`.
- `GET /v1/sweeps/{id}` -> `{id, name, state, run_states: {state: n}, pipeline, pipeline_version_id,
  recording_ids, grid: {"<step>.<param>": [..]}, metric: {step, key, higher_is_better}, variants: [{variant,
  params: {"<step>.<param>": v}, pipeline_ref, pipeline_version_id}], run_ids, prov_node_id, created_by, created_at}`.
  state = queued | running | succeeded | partial | failed.
- `GET /v1/sweeps/{id}/report` -> `{sweep_id, state, complete, pipeline, pipeline_version_id,
  metric: {name: "<step>.<key>", step, key, higher_is_better}, factors: [{name, values}],
  cells: [{run_id, recording_id, variant, params, pipeline_ref, pipeline_version_id, state, value|null,
  prov_activity_id, prov_node_id (artifact holding the number), artifact: {id, step, name, sha256}|null}],
  variants: [{variant, params, pipeline_ref, pipeline_version_id, mean|null, n, run_ids}],
  sensitivity: [{factor, levels: [{value, mean|null, n, run_ids}], range|null}],
  best: {variant, params, mean, run_ids}|null, prov_node_id}`.
  Every number carries run IDs (cells: run_id; aggregates: run_ids). Each variant is its own published
  PipelineVersion (link `/v1/pipelines/{pipeline_ref}`).
