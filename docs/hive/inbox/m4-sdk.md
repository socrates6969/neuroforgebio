# inbox: m4-sdk (M4 worker: 4.2 nf-core, 4.3 Python SDK, 4.4 LSL bridge, 4.5 docs)

Notes from m4-sdk to m4-api / lead. Newest last. Mark handled notes ACK.

## 2026-09-26 start

- I own: `core/nf-core/`, `bindings/python/`, `deny.toml` (root, new), `apps/web/src/pages/docs/**` + docs
  content, `tools/doc-snippets/` (new), `.github/workflows/sdk-wheels.yml` (new, dispatch-only).
- Shared-file edits (append only): root `Cargo.toml` members += `bindings/python`; root `pyproject.toml`
  dev group += `maturin`; `Cargo.lock`/`uv.lock` regenerated. I announce every `uv lock`/`uv sync` here
  before running it.
- m4-api: the SDK reads `openapi/v1.yaml` for the docs API reference; RFC 9457 errors are parsed in
  nf-core (`nf_core::http::Problem`), `Deprecation`/`Sunset` surface as Python `DeprecationWarning`.

## 2026-09-26 request to m4-api: provenance batch upload (designed, not needed for M4 acceptance)

nf-core's offline provenance recorder keeps a local hash chain (`provb` batches, hashing spec §5.3,
`tenant` = a caller-chosen chain name such as `local:<device>`) and syncs it later. There is no
endpoint to receive such batches today. Proposal, only if it fits 4.1 scope; otherwise I label the
sync "designed" in the docs:
`POST /v1/provenance/batches` body = the canonical batch bytes (`application/json`), header
`X-NF-Batch-Id: provb:sha256:...`; server recomputes the ID, checks `prev` against the last accepted
batch of that chain, stores the records as imported entities. Idempotent on the batch ID.

## 2026-09-26 uv lock + sync (m4-sdk)

Appending `maturin` to the root dev group, then `uv lock` and `uv sync --locked` in the m4 worktree.
After a sync, `neuroforge` (maturin develop) disappears from `.venv`; I reinstall it myself.

## 2026-09-26 for m4-api: docs API reference is generated from openapi/v1.yaml

`apps/web/src/docs/api-reference.json` is generated from `openapi/v1.yaml` (current as of 10355c8).
`apps/web/test/docs.test.mjs` compares its recorded SHA-256 with the spec, so **any change to v1.yaml
needs** `python tools/doc-snippets/gen_api_reference.py` (or ping me). `--check` exits 1 when stale.

## 2026-09-26 for the lead: shared-file / CI follow-ups (not done by me)

- `ci.yml` rust job: `cargo clippy --workspace` now also checks `bindings/python` (PyO3; needs a Python
  >= 3.12 on the runner, ubuntu-latest has one). `cargo test --workspace` does not build it (`test = false`).
  Please add `cargo test -p nf-core --features stream --locked` to the rust job (the stream tests only run
  with that feature; today they run in `sdk-wheels.yml`).
- The SDK tests are not in the root pytest `testpaths` (they need the maturin-built extension); they run
  in `sdk-wheels.yml` (`sdk-integration`) and locally via `pytest bindings/python/tests`.
- `architecture/BLUEPRINT.md` §2.6 still shows `eeg-basic@1.2.0`; the website now shows the published
  `eeg-basic@1.0.0` (the step library has no 1.2.0). Suggest aligning the BLUEPRINT text.
- Hashing spec v2 candidate: integral doubles in [2^53, 1e21) canonicalise to integer literals that §3.1
  rejects on input (both implementations agree; pinned by `integral_doubles_beyond_2_53`).
