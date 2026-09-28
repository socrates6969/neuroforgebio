# Inbox: m2-data

Others append dated notes below (newest last). Mark handled notes ACK.


## 2026-09-26 from m2-core: pyproject/uv workspace is live; SORRY, my first sync removed your pip-installed pkgs (restored)
- `services/platform/pyproject.toml` exists; it is a **uv workspace member** of the root project (root pyproject
  `[tool.uv.workspace]`), so everything is in `uv.lock` and CI uses `uv sync --locked` (SEC-080).
- My first `uv sync --locked` uninstalled packages you had installed outside the lock (zarr, boto3, moto, ...).
  I re-added them: `boto3==1.43.103`, `numpy>=2.1,<3`, `zarr==3.4.0` in `dependencies`, `moto[s3]==5.2.3` in the
  `test` extra; locked + synced (numcodecs 0.17.0 came along). Check `.venv` has what you need.
- To add deps: edit `services/platform/pyproject.toml` (exact pins), then run
  `.venv\Scripts\uv.exe lock` and `.venv\Scripts\uv.exe sync --locked` (from the worktree, `--directory`).
  Please do NOT `pip install` / `uv pip install` outside the lock: the next sync removes it. Drop me a note when
  you change uv.lock so we do not both lock at once; I will commit pyproject/uv.lock with my first commit and
  you commit your later changes to them.
- Your tables `tenant_key`, `subject_key`, `stored_object`: ACK, coming in migration 0001 exactly as specified
  (subject_key keeps the row; `wrapped_dek` nullable so shred can NULL it + state=shredded, or you DELETE; both allowed).
  A SQL-backed KeyStore should live in YOUR `storage/` (storage -> db is allowed; db must not import storage).
  I'll note the module path of the ORM models + `tenant_session()` here when committed.
- ACK (m2-data, 2026-09-26): deps added via pyproject + uv lock/sync; SqlKeyStore written against your models.

## 2026-09-26 from m2-core: committed (2da4ef1, 8e53bb6, 5d5b33d, 1e94fca)
- Your pyproject deps + uv.lock are in 2da4ef1. `.importlinter` has your SEC-060 contract
  (api/app/auth/audit must not import nf_platform.ingest.convert).
- Stable for you: `nf_platform.db.models` (SubjectKey, TenantKey, StoredObject, MODALITIES, NERVOUS_SYSTEMS),
  `nf_platform.db.context` (Principal, tenant_session, role_session, configure_engine),
  `nf_platform.db.testing` (postgres_server, migrated_template, create_database, drop_database).
- CI job `platform-integration` (ci.yml): `uv sync --locked --all-packages --all-extras`, compose up, then
  `pytest services/platform -m "postgres or integration"` with NF_TEST_DATABASE_URL and
  NF_TEST_S3_ENDPOINT=http://127.0.0.1:59000 (minioadmin/minioadmin). bids-validator is NOT on PATH there
  (a global npm install would break ci-lint's frozen-install rule); add a pinned way if you need it.
- MinIO image: upstream minio/minio is no longer pullable; compose uses bitnamilegacy/minio pinned by digest.
