# M2 (ingest + storage) build contracts

Branch `feature/m2-ingest` (cut from main @da5fd0d). Queen: nfb-build-queen. General rules: `docs/hive/CONTRACTS.md`
(absolute paths, no `cd`, `git -C`, stage only your paths, never `git add -A`, commit often with the Co-Authored-By
line, do NOT push). Inbox files: `docs/hive/inbox/<name>.md`.

Sources: `architecture/BUILD-GUIDE.md` M2 (2.1–2.8), `architecture/BLUEPRINT.md` §3.1–3.4, §4.2, §6, §8.1, §8.4, §8.7,
`docs/inputs/security/SECURITY-REQUIREMENTS.md` (re-copy from `C:\Users\mariu\neuro-company\security\` if newer; the
step→SEC index at its end), `docs/spec/hashing.md`, `tools/synth` (fixtures).

## 1. Layout and ownership

Python package `nf_platform` (FastAPI modular monolith) at `services/platform/`:

| Path | Owner | Steps |
|---|---|---|
| `services/platform/pyproject.toml`, `nf_platform/app.py`, `nf_platform/config.py`, `nf_platform/db/**` (models, Alembic migrations, RLS, session/tenant context), `nf_platform/api/**` (routers, problem+json errors), `nf_platform/auth/**`, `nf_platform/audit/**`, `.importlinter`, `services/platform/docker-compose.ci.yml`, CI integration job wiring | m2-core | 2.1, 2.2, 2.8 |
| `nf_platform/storage/**` (object store, envelope crypto, KMS, keyring, crypto-shred), `nf_platform/signals/**` (Zarr layout, window reads, pyramids), `nf_platform/ingest/convert/**` (EDF/BDF, BrainVision, BIDS, NWB, XDF converters) | m2-data | 2.3, 2.4, 2.5 |
| `nf_platform/ingest/uploads/**`, `nf_platform/ingest/stream/**`, `proto/ingest/v1/**`, `services/platform/edge_prototype/**` | m2-stream (wave B) | 2.6, 2.7 |
| `services/platform/tests/<area>/**` | the owner of `<area>` | |
| `docs/hive/**`, `docs/hive/M2-REPORT.md` | queen | |

Import-linter layers (m2-core writes the config): `api` → (`ingest`, `signals`, `storage`, `auth`, `audit`) → `db`.
`storage`, `signals` must not import `api`. No module imports `governance`/`registry` yet (M5/M6).

## 2. Local test strategy (≈3 GB free RAM)

- No Docker locally. `docker-compose.ci.yml` (Postgres 16 + MinIO) and integration tests are **CI-only**
  (`@pytest.mark.integration`, skipped locally; the workflow job stays `workflow_dispatch`).
- **Postgres locally:** try an in-process/pip Postgres (e.g. `pgserver`, which ships Windows binaries) so RLS and
  migrations are tested for real. If it does not work on this machine within ~20 min of effort, fall back: SQLite for
  model/CRUD unit tests, and mark RLS/migration tests integration-only. Record which happened in the M2 report.
- **Object store locally:** `LocalObjectStore` (filesystem) implementing the `ObjectStore` protocol; the S3/MinIO
  implementation is tested in CI (optionally moto locally if light).
- **KMS locally:** `LocalKms` (AES-256 key-wrap with a master key kept in memory/tmp) implementing the `Kms` protocol.
- Every process < 1 GB RAM. No MNE/pynwb/pyxdf install locally unless the install stays small; readers that need them
  have CI-only tests. Fixtures come from `tools/synth` (EDF, BDF, BrainVision, XDF writers exist there).
- Python 3.12 in `.venv`; add deps to `services/platform/pyproject.toml` (exact pins) and install with
  `.venv\Scripts\python -m pip install` / uv. Only one install at a time: m2-core owns the first install; m2-data
  appends its deps to the pyproject and asks m2-core (inbox) or installs its own deps when m2-core is not installing.

## 3. Interfaces (both sides code against these; change only via the queen)

```python
# nf_platform/db/context.py (m2-core)
@dataclass(frozen=True)
class Principal: id: str; tenant_id: str; roles: frozenset[str]; scopes: frozenset[str]; kind: Literal["user","api_key","device"]; mfa_phr: bool
def tenant_session(principal) -> ContextManager[Session]   # sets app.tenant_id for RLS; app-level filter too

# nf_platform/auth/authorize.py (m2-core)  -- deny by default (SEC-020)
def authorize(principal: Principal, action: str, resource: ResourceRef) -> None  # raises Forbidden/Unauthorized

# nf_platform/storage/objects.py (m2-data)
class ObjectStore(Protocol):
    def put(self, bucket: str, key: str, data: bytes, *, metadata: dict[str,str] | None = None) -> None
    def get(self, bucket: str, key: str) -> bytes
    def delete(self, bucket: str, key: str) -> None
    def list(self, bucket: str, prefix: str) -> Iterator[str]
BUCKETS = ("raw", "zarr", "artifacts", "models", "audit")   # audit = WORM/object-lock in real S3

# nf_platform/storage/kms.py + keyring.py (m2-data)
class Kms(Protocol):
    def generate_data_key(self, key_id: str, context: dict[str,str]) -> tuple[bytes, bytes]  # (plaintext, wrapped)
    def decrypt(self, key_id: str, wrapped: bytes, context: dict[str,str]) -> bytes
    def schedule_key_deletion(self, key_id: str) -> None
class Keyring:  # tenant KEK -> per-subject DEK (wrapped DEKs stored via a KeyStore callback / table owned by m2-core)
    def encrypt(self, tenant_id, subject_id, object_key, version, plaintext) -> bytes   # AES-256-GCM, AAD per SEC-031
    def decrypt(self, tenant_id, subject_id, object_key, version, blob) -> bytes
    def shred_subject(self, tenant_id, subject_id) -> None                              # crypto-shred (2.3)

# nf_platform/signals/zarr_store.py (m2-data)
def write_recording(store, recording_id, data: np.ndarray, sfreq: float, ch_names, units, *, chunk_s=...) -> ZarrRef
def read_window(store, recording_id, start_s, end_s, channels=None, level=0) -> np.ndarray

# nf_platform/audit/log.py (m2-core)
def emit(event: AuditEvent) -> None   # every data read/export/admin action (2.8)
```

The DB tables for subjects' wrapped DEKs (`subject_key`) and object metadata are owned by m2-core; m2-data specifies
the columns it needs in m2-core's inbox early.

## 4. Non-negotiables in M2

- Tenant isolation (SEC-021): app check + RLS + per-tenant KMS key; a two-tenant test on every table/route.
- Crypto-shred (2.3): after subject key destruction, that subject's objects (incl. a "backup copy") are unreadable;
  other subjects unaffected; keys never logged (log-scan test).
- No-stimulation (SEC-090): no API/proto operation, message or field that sends anything to acquisition or stimulation
  hardware; `proto/` is scanned by `tools/hw-guard`. Stream ingest is device → platform only (SEC-093: acks carry no
  timing guarantee; SEC-094: original timestamps never rewritten).
- No real human neural data anywhere; fixtures are synthetic (`tools/synth`) or small public files with licence noted.
