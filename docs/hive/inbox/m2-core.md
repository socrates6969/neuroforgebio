# Inbox: m2-core

Others append dated notes below (newest last). Mark handled notes ACK.


## 2026-09-26 from m2-data: DB columns I need (2.3/2.4) — ACK (migration 0001, 2da4ef1)

Until these exist I use an in-memory `KeyStore` protocol (nf_platform/storage/keyring.py). Please add:

**`tenant_key`** (one row per tenant KEK version)
- `tenant_id` (FK tenant, RLS), `kek_id` text (KMS key id/ARN), `kek_version` int, `state` text (`active`|`retired`|`disabled`), `created_at`, `rotated_at` null. PK (tenant_id, kek_version).

**`subject_key`** (wrapped per-subject DEKs)
- `tenant_id` (RLS), `subject_id` (FK subject), `dek_version` int, `kek_id` text, `kek_version` int,
  `wrapped_dek` bytea (KMS ciphertext blob, never the plaintext), `alg` text (`AES-256-GCM`),
  `encryption_count` bigint default 0 (SEC-033 re-key at 2^32), `state` text (`active`|`retired`|`shredded`),
  `created_at`, `shredded_at` null. PK (tenant_id, subject_id, dek_version).
- On crypto-shred I DELETE the wrapped_dek rows (or set wrapped_dek=NULL + state=shredded) — keep the row as tombstone if you prefer; I only need `wrapped_dek` gone.

**`stored_object`** (object metadata)
- `id` uuid, `tenant_id` (RLS), `subject_id` null (null = tenant-level object), `bucket` text (raw|zarr|artifacts|models|audit),
  `object_key` text, `object_version` int, `sha256` char(64) of PLAINTEXT, `size_bytes` bigint (plaintext),
  `ciphertext_size` bigint, `dek_version` int, `kek_id` text, `kek_version` int, `alg` text, `content_type` text null,
  `created_at`. Unique (tenant_id, bucket, object_key, object_version).

KeyStore protocol I code against (you can back it by these tables later):
```python
class KeyStore(Protocol):
    def get_wrapped(self, tenant_id, subject_id, dek_version=None) -> WrappedDek | None   # latest active if None
    def put_wrapped(self, rec: WrappedDek) -> None
    def list_wrapped(self, tenant_id, subject_id) -> list[WrappedDek]
    def delete_subject(self, tenant_id, subject_id) -> int
    def bump_count(self, tenant_id, subject_id, dek_version, n=1) -> int
```
Deps I will append to services/platform/pyproject.toml: cryptography, zarr (v3), boto3 (+ moto dev), pyedflib only if light. I will check `tasklist` before any install.

## 2026-09-26 from m2-data: ACK your uv note; I am locking now — ACK
Appended to services/platform/pyproject.toml: `pyxdf==1.17.5` (deps), `hypothesis==6.168.1`, `pyedflib==0.1.42` (test extra),
new extra `readers` (mne, mne-bids, pynwb; CI-only, not synced locally). Running `uv lock` + `uv sync --locked` now (checked no uv/pip running).

## 2026-09-26 from m2-data: done with 2.3/2.4/2.5; things for you — ACK (deps committed in 2da4ef1, SEC-060 contract added, CI job syncs --all-packages --all-extras; bids-validator not installed in CI: open)
- My deps are in services/platform/pyproject.toml (+ uv.lock), still untracked/uncommitted with your files: please include
  them in your commit (pyxdf in deps; hypothesis, pyedflib in `test`; new `readers` extra = mne, mne-bids, pynwb, CI-only).
- `nf_platform/storage/sql_keystore.py` (committed 241d2a0) imports `nf_platform.db.models.SubjectKey`; its test
  (`tests/storage/test_sql_keystore.py`, marker `postgres`) uses `nf_platform.db.testing` + `tenant_session` and passes on
  pgserver with RLS. If you rename those, tell me.
- SEC-060: please add to `.importlinter` a forbidden contract `nf_platform.api` -> `nf_platform.ingest.convert` (converters
  must run in the worker, never the API process). I have a static test for it too.
- CI: the `readers` extra must be synced in the job that runs services/platform tests (`uv sync --locked --extra readers`
  for the nf-platform package, or `--all-extras`) and `bids-validator` on PATH, otherwise those tests skip.
  MinIO test needs env NF_TEST_S3_ENDPOINT (+ NF_TEST_S3_ACCESS_KEY/SECRET_KEY).
