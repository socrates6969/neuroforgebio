# M3 (pipelines + provenance) build contracts

Branch `feature/m3-pipelines`, **stacked on `feature/m2-ingest`** (M2 is not merged to main yet). General rules:
`docs/hive/CONTRACTS.md` and `docs/hive/M2-CONTRACTS.md` §2 (local test strategy: real Postgres via pgserver,
LocalObjectStore, LocalKms, no Docker locally, compose/integration CI-only, each process < 1 GB).
Sources: `architecture/BUILD-GUIDE.md` M3 (3.1–3.9), `architecture/BLUEPRINT.md` §3.5, §3.6, §3.8, §6, §10,
`docs/spec/hashing.md`, `docs/inputs/security/SECURITY-REQUIREMENTS.md` (3.1–3.3 → SEC-043, 044, 074; 3.8 → 015).
Inboxes: `docs/hive/inbox/<name>.md`.

## 1. Ownership

| Path | Owner | Steps |
|---|---|---|
| `nf_platform/provenance/**` (prov_node/prov_edge, hash-chained signed batches, lineage traversal, PROV-JSON + OpenLineage export), `nf_platform/pipelines/**` (PipelineVersion schema, canonical ID, publish, name@semver resolution), their API routes (`nf_platform/api/provenance_routes.py`, `pipelines_routes.py`), migration `0003_*`, `services/platform/tests/provenance/**`, `tests/pipelines/**`; wiring M2's convert provenance into the graph | m3-prov | 3.1, 3.2, 3.7 |
| `nf_platform/jobs/**` (Postgres SKIP LOCKED queue, retries, timeouts, cancel, heartbeats), `services/workers/runner/**` (worker process, step runner: in-process/subprocess locally, container runner CI-only), `services/workers/steps/nf_steps/**` (step library wrapping MNE), `nf_platform/api/runs_routes.py`, migration `0004_*`, `tests/jobs/**`, repro harness `tools/repro-check/**` + CI job | m3-exec | 3.3, 3.4, 3.5 |
| `nf_platform/sweeps/**`, sweep report, `apps/console/**` (React console), 3.9 study scaffolding | wave B (m3-sweeps, m3-console) | 3.6, 3.8, 3.9 |
| `docs/hive/**`, M3-REPORT | queen | |

Migration numbering: m3-prov owns `0003`, m3-exec owns `0004` (depends on 0003). Shared files (`api/routes.py` router
registration, `app.py`, authz matrix mapping, root/platform pyproject): append only, small edits, and commit them
together with the change that needs them; re-read before editing (the other worker may have changed them).

## 2. Interfaces

```python
# nf_platform/provenance/api.py (m3-prov) -- all calls run inside the caller's tenant session (RLS applies)
class ProvKind(StrEnum): ENTITY="entity"; ACTIVITY="activity"; AGENT="agent"
class EdgeType(StrEnum): USED="used"; WAS_GENERATED_BY="wasGeneratedBy"; WAS_DERIVED_FROM="wasDerivedFrom"; WAS_ATTRIBUTED_TO="wasAttributedTo"; WAS_ASSOCIATED_WITH="wasAssociatedWith"
@dataclass(frozen=True)
class NodeSpec: kind: ProvKind; type: str; ref_id: str | None; content_hash: str | None; attrs: dict
def record(session, principal, nodes: list[NodeSpec], edges: list[tuple[int, EdgeType, int]]) -> ProvCommit
    # atomically inserts nodes/edges, appends one hash-chained batch, returns node ids + batch hash
def lineage(session, node_id, direction: Literal["up","down"], depth: int | None) -> Graph
def verify_chain(session, tenant_id) -> VerifyResult

# nf_platform/pipelines/spec.py (m3-prov)
class PipelineSpec(BaseModel): name; version (semver); steps: list[StepSpec]  # StepSpec: id, step (library name@version), image (name@sha256:...), params (explicit, defaults filled), tolerance: Literal["exact","tolerance"], rtol/atol
def pipeline_version_id(spec) -> str   # per docs/spec/hashing.md PipelineVersion ID (test vectors must pass)
def publish(session, principal, spec) -> PipelineVersionRow   # immutable; re-publish with changes -> error
def resolve(session, ref: str) -> PipelineVersionRow           # "name@semver" or ID

# nf_platform/jobs/queue.py (m3-exec)
def enqueue(session, kind, payload, *, max_attempts=3, timeout_s=...) -> JobId
def claim(session, worker_id, kinds) -> Job | None        # FOR UPDATE SKIP LOCKED
def heartbeat / complete / fail / cancel
# Run lifecycle (m3-exec): outputs are written to object storage under a staging prefix, then
# provenance.record(...) commits, and only then the run's artifacts become visible (visible_at set in the same txn).
```

Until m3-prov's module exists, m3-exec codes against these signatures with a thin fake in its own tests and switches to
the real module once m3-prov commits it (check m3-exec's inbox / git log).

## 3. Non-negotiables

- Provenance before visibility (3.3 fault-injection test). Tenant isolation (RLS) on every new table + two-tenant tests.
- Determinism: seeds recorded, BLAS threads pinned (e.g. `OMP_NUM_THREADS=1`), every step default written to the run record.
- No stimulation output of any kind (SEC-090 spirit): steps produce analysis artifacts only.
- No real human data locally: synthetic fixtures (`tools/synth`). Public OpenNeuro/DANDI downloads (3.9) are CI-only,
  with licences recorded, never committed.
