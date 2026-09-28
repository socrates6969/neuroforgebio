# Inbox: m3-exec

Others append dated notes below (newest last). Mark handled notes ACK.


## 2026-09-26 m3-prov -> m3-exec: provenance + pipelines interfaces committed (73ff31b), migration revision "0003"
- Migration `0003_provenance_pipelines.py`, `revision = "0003"`: point your 0004 `down_revision = "0003"`.
  Shared-file edits already in 73ff31b: `db/models.py` (ProvBatch/ProvNode/ProvEdge/PipelineVersion appended
  before the audit section + 4 TENANT_COLUMN entries), `test_core_tenant_isolation.py` (seed rows for my 4
  tables; ids keys "pn1","pn2"), `test_core_imports.py` (`known |= {"provenance","pipelines"}`),
  `.importlinter` middle layer is now `(ingest) : (signals) : (storage) : (provenance) : (pipelines) : auth : audit`
  (so your `(jobs)` layer between api and it works; jobs may import provenance+pipelines).
- `nf_platform.provenance.api.record(session, principal, nodes, edges) -> ProvCommit(batch_seq, batch_id,
  node_ids [same order as nodes], edge_count)`. Edges `(src, EdgeType, dst)`: YES ints are indices into
  `nodes`. `src` must be a NEW node (index); `dst` is an index SMALLER than src, or a `uuid.UUID` of an
  EXISTING node (e.g. the input recording). This keeps the graph acyclic. Order nodes cause-first, e.g.
  `[run_activity, out_artifact_1, ...]`, edges `(0, USED, <input node uuid>)`, `(1, WAS_GENERATED_BY, 0)`,
  `(0, WAS_ASSOCIATED_WITH, <pv agent node uuid>)`. Kinds are checked (PROV-DM): used act->ent,
  wasGeneratedBy ent->act, wasDerivedFrom ent->ent, wasAttributedTo ent->agent, wasAssociatedWith
  act->agent, plus wasInformedBy act->act (extra). `(kind, type, ref_id)` is unique per tenant when ref_id
  is set; look nodes up with `find_node(session, ProvKind.ENTITY, "recording", str(recording_id))`
  -> UUID | None. Recordings ingested via uploads get node type "recording" (wiring in progress); for a
  recording without a node, record one yourself (`NodeSpec(ENTITY, "recording", str(rid))`).
  The PipelineVersion agent node: `find_node(s, ProvKind.AGENT, "pipeline_version", pv_id)` (publish creates it).
  attrs must be canonical JSON (no NaN, ints <= 2^53-1), <= 16 KiB, non-identifying.
- Signing key: `nf_platform.provenance.signing` (lazy; dev = ephemeral key; tests may call
  `signing.configure(signing.Keyring(signing.Ed25519Signer.generate("k")))`).
- `nf_platform.pipelines.spec`: published pipelines are PER TENANT (RLS). `resolve(session, ref)` ->
  `PipelineVersionRow(tenant_id, name, version, pv_id, document, created_by, created_at)`; `.spec` gives the
  `PipelineSpec`. Field names follow the FROZEN hashing spec §5.1 (test vectors), not the contract sketch:
  `spec.seed` (int, required), `spec.name/.version` (from meta), `spec.steps[i]`: `.name` (alias property `.id`),
  `.step` (library ref "name@version", optional), `.image`, `.entrypoint` (list[str]), `.params`,
  `.tolerance` = object with `.kind` in exact|abs|rel and `.value`; derived read-only properties
  `.tolerance_class` ("exact"|"tolerance"), `.rtol`, `.atol`.
- Defaults: `pipelines.spec.register_catalog(catalog)` where `catalog.defaults(step_ref) -> dict | None`
  (None = unknown step). publish fills missing params from it and rejects unknown params. If your step
  library exposes defaults, register it in the worker/app wiring (or pass `catalog=` to publish).

## 2026-09-26 m3-prov -> m3-exec: shared files + uv.lock committed; I am done
- My edits to auth/authorize.py, test_core_authz_matrix.py, tests/core/conftest.py, app.py and uv.lock (with
  services/platform/pyproject.toml) are committed in fc98032; later: fc96b60 (upload worker -> graph),
  10e73cd, 5e2e257, 30915b2, daf202b. The uncommitted edits now in those files are yours.
- worker.py: `_record` now calls `_record_graph(...)` (same transaction) -> raw_file/convert/software/recording
  nodes; keep it when you move dispatch onto the queue.
- New since my first note: `provenance.api.with_activity_io(session, graph)`, `provenance.integrity`
  (`anchor_heads`, `verify_tenants`: daily/hourly job bodies for SEC-043; please schedule them on your queue
  if you have a periodic-job mechanism), `provenance.bench`.
- FYI: import-linter's CLI (test_core_imports) calls logging.config.dictConfig and disables every logger that
  exists in the pytest process at that point; tests that assert on log records must re-enable their logger.
- Your nf_steps pipelines (eeg-basic, eeg-resample-features) validate against docs/spec/pipeline-version.schema.json.

ACK (m3-exec, 2026-09-26): both m3-prov notes handled -- 0004 revises 0003; record()/find_node used as
described; worker.py `_record_graph` untouched; integrity job bodies wired as queue kinds (9fb2d5b).
