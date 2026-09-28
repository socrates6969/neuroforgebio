# nf-core

The shared SDK core (BLUEPRINT §5, BUILD-GUIDE 4.2). Every SDK (Python today; the C ABI for
C++/Unity/Unreal is planned) uses this crate, so hashing, buffering and provenance rules cannot
drift between languages.

| Module | What | Spec / requirement |
|---|---|---|
| `cjson` | NF-CJSON v1: strict parser + canonical writer (RFC 8785 + NFC) | `docs/spec/hashing.md` §3 |
| `ids` | `blob`, `pv`, `chunk`, `provb` content IDs, chain verification | hashing.md §4-§5 |
| `model` | Channel, Recording, Segment, ProvRecord, Run, Artifact | BLUEPRINT §4 |
| `zarr` | Zarr v3 chunk read/write (regular grid, `bytes` codec), `nf-signal/1` level 0 | `docs/spec/zarr-layout.md` |
| `cache` | content-addressed local chunk cache, hash-verified on every read, LRU-bounded | BLUEPRINT §5 |
| `http` | API client core: bearer tokens (refresh once on 401), retries, RFC 9457 errors, URL policy | BLUEPRINT §4, SEC-030 |
| `prov` | offline provenance recorder: local hash chain, verified on open, synced later | hashing.md §5.3 |
| `stream` (feature) | encrypted write-ahead buffer, chunk building + Ed25519 signing, device tokens, resuming sender | `proto/ingest/v1`, SEC-016/037/040/093/094 |

Design choices, stated so they can be reviewed:

- **Transports are injected.** `http::HttpTransport` and `stream::sender::IngestTransport` are
  traits. The Python binding supplies `httpx` (TLS 1.3 minimum, verification on) and `grpcio`
  (raw bytes); the retry, auth and resume rules run here. A Rust-owned HTTPS/gRPC transport (for
  the C ABI) is planned, not built.
- **Protobuf is hand-encoded** (`stream::proto`): five small messages, no code generator.
- **Compressed Zarr codecs are reported as unsupported.** Local copies are written uncompressed;
  platform data reaches the SDK as `nf-window/1` responses, not as (encrypted) raw chunks.
- **WAL format equals the 2.7 prototype's** (`NFWAL1`, AES-256-GCM, same AAD), so both read each
  other's records. Keys: DPAPI on Windows (same sealed-file format as the prototype); on macOS and
  Linux the caller passes a key from the OS keystore (`StaticKey`), otherwise `EphemeralKey`.
- **No hardware control path.** Data flows device -> SDK -> platform only (SEC-090/091);
  `tools/hw-guard` scans this directory, and `deny.toml` bans device-access crates.

## Build and test (dev PC: debug only, one job)

```sh
CARGO_BUILD_JOBS=1 cargo test -p nf-core                    # default features
CARGO_BUILD_JOBS=1 cargo test -p nf-core --features stream  # + WAL, signing, sender
```

Release builds, `cargo deny check` and `cargo audit` run in CI only (`deny.toml` at the repo root).

Known spec quirk (reported for hashing spec v2): an integral double in [2^53, 1e21) prints as a
plain integer (RFC 8785), which §3.1 then refuses to parse. Pinned by the test
`integral_doubles_beyond_2_53`.

Licence: repository is all-rights-reserved until SDK code ships (D6 / docs/adr/0006).
