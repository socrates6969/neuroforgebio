# neuroforge C ABI

Stable C interface to nf-core for C, C++, Unity and Unreal. The design rules are in [ADR 0013](../../docs/adr/0013-c-abi.md); the contract of every function is in the header comments of [`include/neuroforge.h`](include/neuroforge.h).

## Build

```
cargo build -p neuroforge-c -j 2           # debug, on the dev PC
cargo build -p neuroforge-c --release      # CI / release builds
```

Outputs in `target/<profile>/`:
- MSVC: `neuroforge.dll` with import library `neuroforge.dll.lib`, and static `neuroforge.lib`. The static library also needs `crypt32 kernel32 bcrypt advapi32 ntdll userenv ws2_32 dbghelp` and the `/MD` runtime.
- Linux/macOS: `libneuroforge.so` / `.dylib` and `libneuroforge.a`.

## Use

```c
#include "neuroforge.h"

if ((nf_abi_version() >> 16) != NF_ABI_VERSION_MAJOR) { /* wrong library */ }

nf_buf id = {0};
if (nf_blob_id((const uint8_t *)"hello\n", 6, &id) == NF_OK) {
    puts((const char *)id.data);   /* blob:sha256:5891b5b5... */
    nf_buf_free(&id);
} else {
    fprintf(stderr, "%s\n", nf_last_error());
}
```

Rules in one breath: every call returns `nf_status` (`NF_OK` = 0) and sets a per-thread `nf_last_error()` on failure (empty again after any `NF_OK`; read it only after a failure); text and bytes come back in an `nf_buf` you release with `nf_buf_free` (always NUL-terminated); handles have one constructor and one `nf_*_free`; nothing panics across the boundary.

## What is exposed (ABI 1.2.1)

| Area | Functions |
|---|---|
| Version, errors, memory | `nf_abi_version`, `nf_core_version`, `nf_status_name`, `nf_last_error`, `nf_last_error_detail`, `nf_buf_free`, `nf_dtype_name/_itemsize/_parse` |
| Hashing spec v1 | `nf_canonicalize`, `nf_format_number`, `nf_blob_id`, `nf_blob_id_file`, `nf_pipeline_version_id`, `nf_chunk_id`, `nf_prov_batch_id`, `nf_verify_prov_chain`, `nf_is_valid_id` |
| Hashing spec v2 | `nf_is_valid_id_v2`, `nf_audit_batch_id`, `nf_verify_audit_chain`, `nf_prov_node_hash`, `nf_consent_record_hash`, `nf_verify_consent_chain`, `nf_ruleset_content_sha256`, `nf_sweep_variant_label`, `nf_training_subject_hash`, `nf_training_manifest_build`, `nf_training_manifest_digest`, `nf_timing_sha256` |
| Signature verification (Ed25519) | `nf_verify_stream_chunk`, `nf_verify_device_token`, `nf_verify_provb_signature`, `nf_verify_anchor`, `nf_verify_certificate` |
| Local recordings (read-only) | `nf_recording_open/_free/_get_info/_channel_name/_channel_unit/_read/_read_f64 (1.1)/_read_timestamps` |
| Chunk cache (read-only) | `nf_chunk_cache_open/_free/_get/_size`, `nf_chunk_dtype/_rank/_shape/_data/_free` |
| Provenance recorder | `nf_prov_recorder_open/_free/_record/_len/_head/_pending_count/_pending/_mark_synced` |
| Streaming | `nf_device_key_generate/_from_seed/_open_sealed/_public_key/_token/_free`, `nf_wal_open/_open_ephemeral (1.2)/_len/_free`, `nf_stream_writer_new/_push/_add_clock_offset/_add_local_clock/_flush/_next_seq/_buffered_samples/_get_stats/_free`, `nf_sender_config_default`, `nf_sender_new/_run/_stop/_reset/_state/_finish/_get_stats/_fatal_error/_free`, `nf_stream_state_free`, `nf_reply_set` |
| API client | `nf_check_base_url`, `nf_api_client_new/_request/_free`, `nf_http_reply_set_status/_add_header/_set_body`, `nf_http_response_status/_header_count/_header/_body/_free` |

Transports (gRPC for ingest, HTTP for the API) and token stores are supplied by the caller as C callback tables (`nf_ingest_transport`, `nf_http_transport`, `nf_token_source`), so each engine uses its own network stack.

Not exposed, on purpose: anything that sends data or instructions to acquisition hardware (SEC-090/091); writing recordings or cache entries; raw signing and key export; raw WAL access; the hashing-spec payload builders. See ADR 0013.

## Misuse: what is checked, what is undefined

**Checked**, returning a status and never crashing. `tests/c/test_misuse.c` and `tests/misuse.rs` cover these:
- NULL for any pointer argument gives `NF_ERR_NULL_ARG`. Pointers documented as optional (for example `out_size`, `config`, `user_agent`, `out_claims`) are the exception, and so are `(NULL, 0)` inputs, which are empty.
- A misaligned pointer, or a length whose byte size exceeds `isize::MAX`, gives `NF_ERR_INVALID_ARG`.
- NULL callbacks inside a transport or token table fail the call (`NF_ERR_TRANSPORT` / `NF_ERR_AUTH`).
- A read above 2^30 stored bytes gives `NF_ERR_INVALID_ARG`.
- `nf_buf_free` and `nf_stream_state_free` twice, or on a zeroed value, are no-ops.
- The free functions accept NULL.
- A callback may call any `nf_` function, including a nested request on the same client and `nf_sender_get_stats` on the sender that invoked it.
- `nf_sender_stop` and `nf_sender_get_stats` may be called from another thread while `nf_sender_run` blocks.
- `nf_sender_finish` while the WAL holds chunks, or while `nf_sender_run` is active, and a second concurrent `nf_sender_run`, give `NF_ERR_INVALID_ARG` (CABI-T2).
- Writers, senders and chunks stay valid after the key, WAL or cache handle they came from is freed.

**Undefined behaviour**, which the library cannot detect and does not try to:
- passing a handle of the wrong type (every handle is an opaque pointer), or a pointer that did not come from the matching constructor;
- using a handle after its `nf_*_free`, or freeing it twice;
- freeing a handle while another thread is using it, including `nf_sender_free` while `nf_sender_run` is running;
- pointers that are non-NULL and aligned but do not point to the promised number of readable or writable bytes, or strings that are not NUL-terminated;
- keeping a pointer the library lent out (`nf_http_response_header`, `nf_chunk_data`, `nf_last_error`, callback arguments) past the documented lifetime;
- using an `nf_reply` or `nf_http_reply` outside the callback it was passed to;
- a callback that unwinds, throws or longjmps into the library.

## Tests

```
cargo test -p neuroforge-c -j 2                 # Rust tests through the exported functions
bindings\c\tests\run-msvc.cmd                   # C test (DLL + static) and C++ wrapper test with MSVC
node bindings/c/tools/header.mjs --check        # header matches the sources (needs cbindgen)
```

- `tests/vectors.rs` recomputes every case of `spec/test-vectors/{canonical-json,numbers,ids,ids-v2}.json` through the ABI and keeps `tests/c/vectors.h` (the C copy) in sync: `NF_UPDATE_C_VECTORS=1 cargo test -p neuroforge-c --test vectors`.
- `tests/abi.rs` covers NULL and error paths, recordings and the cache, provenance, the streaming client against a fake ingest server and the API client against a fake HTTP stack.
- `tests/c/test_abi.c` repeats the vectors, error paths, NULL safety and memory round-trips in C.

After changing an exported item: `node bindings/c/tools/header.mjs` and commit the header. A breaking change bumps `NF_ABI_VERSION_MAJOR` (`src/lib.rs`) and must be announced to the engine SDK owners.
