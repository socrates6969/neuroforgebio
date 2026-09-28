# Canonical hashing and ID spec (v2)

Status: **v2, vectors frozen** (v2 approved by the team lead 2026-09-26: "freeze it with test vectors and bump the
spec version"). v2 is a strict superset of v1: §1-§7 below are the v1 text with every rule, tag and ID unchanged,
and the v1 vector files are byte-for-byte unchanged. v2 only **registers** the tags and signed documents the
platform introduced in M2-M6 (§8-§11) exactly as the code builds them today, with their own vector file
`spec/test-vectors/ids-v2.json`.

v1 status (unchanged): v1 draft, vectors frozen (BUILD-GUIDE 0.5). Review required: one backend and one SDK
engineer sign off in the PR. Any change to the rules or to `spec/test-vectors/*.json` is a new spec version (v2
tags), never an in-place edit.

Why this exists: the Python server writes content hashes in M2/M3, before nf-core (Rust, M4) exists. Both must
produce identical bytes, or stored IDs stop matching and runs are no longer reproducible (BLUEPRINT §3.5, §3.6, §5).

| Artefact | Path |
|---|---|
| Reference implementation (stdlib only) | `spec/reference/python/nf_canonical.py` |
| Test vectors (ASCII JSON, frozen) | `spec/test-vectors/canonical-json.json`, `numbers.json`, `ids.json` |
| Vector generator (run only for a new version) | `spec/reference/python/gen_vectors.py` |
| Python check | `pytest spec/reference/python` (also asserts regenerating changes no byte) |
| Rust check | `cargo test -p nf-core` (`core/nf-core/tests/vectors.rs`: every ID from its payload/preimage) |
| v2 reference (stdlib only, includes RFC 8032 Ed25519) | `spec/reference/python/nf_ids_v2.py` |
| v2 vectors (ASCII JSON, frozen) | `spec/test-vectors/ids-v2.json` |
| v2 vector generator (run only for a new version) | `spec/reference/python/gen_vectors_v2.py` |
| v2 Python checks | `pytest spec/reference/python/test_vectors_v2.py` (reference) and `pytest services/platform/tests/spec_v2` (the platform functions that build each tag) |
| v2 Rust check | `cargo test -p nf-core --features stream` (`core/nf-core/tests/vectors_v2.rs`, module `nf_core::ids_v2`) |

Key words MUST / MUST NOT are used as in RFC 2119.

## 1. Encoding

Canonical text is UTF-8 without a byte-order mark. Hashes are computed over those bytes.

## 2. Hash function

SHA-256 (FIPS 180-4). Digests are written as 64 lowercase hex characters.

## 3. Canonical JSON (NF-CJSON v1)

NF-CJSON v1 is **RFC 8785 (JSON Canonicalization Scheme, JCS) plus Unicode NFC normalisation of every string**.
JCS was chosen so that existing JCS libraries can be reused in other languages; the NFC pre-pass is the only
difference.

### 3.1 Input

- Input is a JSON value (RFC 8259). Parsers MUST reject duplicate object keys, `NaN`, `Infinity` and lone
  surrogates (`"\ud800"`).
- Integer literals (no fraction, no exponent) MUST satisfy |n| ≤ 2^53 − 1. Larger integers (for example sample
  counters or nanosecond timestamps) MUST be encoded as strings by the producer. This prevents silent rounding
  from making two different values hash the same.
- Every other number is an IEEE-754 double (as in JCS).

### 3.2 Strings and keys

1. Every string, **including object keys**, is normalised to Unicode NFC.
2. After NFC, keys in one object MUST be unique (`"é"` and `"é"` collide and are an error).
3. Escaping (JCS §3.2.2.2): `"` → `\"`, `\` → `\\`, U+0008 → `\b`, U+000C → `\f`, U+000A → `\n`,
   U+000D → `\r`, U+0009 → `\t`; any other U+0000–U+001F → `\u00xx` with **lowercase** hex. Everything else,
   including `/`, U+007F, U+2028 and all non-ASCII, is emitted as literal UTF-8.

### 3.3 Numbers

Numbers are serialised exactly as ECMAScript `Number.prototype.toString` (RFC 8785 §3.2.2.3): the shortest
digits that round-trip, no trailing `.0`, `-0` becomes `0`, exponent form `1e+21`, `1e-7` outside
[10^-6, 10^21). So `1.0`, `1` and `1e0` are the same value. The table in RFC 8785 Appendix B is reproduced in
`numbers.json` (source: rfc-editor.org/rfc/rfc8785.txt, opened 2026-09-26).

### 3.4 Structure

- No insignificant whitespace anywhere.
- Object members are sorted by key, comparing the keys as sequences of **UTF-16 code units** (JCS §3.2.3;
  in Python `key=lambda k: k.encode("utf-16-be")`). This differs from code-point order only for keys that mix
  U+E000–U+FFFF with supplementary-plane characters; the vector `rfc8785-sort-order` covers it.
- Arrays keep their order.
- Literals: `null`, `true`, `false`.

## 4. Content IDs

An ID has the form `<kind>:sha256:<64 lowercase hex>`. Kinds in v1:

| Kind | Identifies | Hash input |
|---|---|---|
| `blob` | raw bytes: an uploaded file, an export, a model weight file | the bytes themselves (so it equals `sha256sum`, and S3/SDK upload checks can use it directly) |
| `pv` | a PipelineVersion (§5.1) | tagged canonical JSON |
| `chunk` | one signal-array chunk (§5.2) | tagged header + raw little-endian array bytes |
| `provb` | one provenance batch in a hash chain (§5.3) | tagged canonical JSON |

**Domain separation.** Structured IDs hash `TAG || 0x00 || payload`, where `TAG` is the ASCII string below.
The tag makes it impossible for a pipeline spec and a provenance batch with identical JSON to share an ID.

| Kind | TAG |
|---|---|
| `pv` | `nf.pipeline-version.v1` |
| `chunk` | `nf.chunk.v1` |
| `provb` | `nf.prov-batch.v1` |

Regex for any v1 ID: `^(blob|pv|chunk|provb):sha256:[0-9a-f]{64}$`.

## 5. Structured objects

### 5.1 PipelineVersion (`pv`)

BLUEPRINT §3.5: a PipelineVersion is an ordered list of steps, each with a digest-pinned image, entrypoint,
explicit parameters and a declared tolerance. Its hash is its ID; `eeg-basic@1.2.0` is a label that resolves to it.

```json
{
  "schema": "nf.pipeline-version/v1",
  "meta": { "name": "eeg-basic", "version": "1.2.0", "description": "..." },
  "steps": [
    {
      "name": "filter",
      "image": "registry/steps@sha256:<64 hex>",
      "entrypoint": ["nf-step", "filter"],
      "params": { "l_freq": 0.1, "h_freq": 40.0, "method": "fir", "phase": "zero" },
      "tolerance": { "kind": "exact" }
    }
  ],
  "seed": 42
}
```

- `schema` MUST be `nf.pipeline-version/v1`.
- **`meta` is not hashed.** Payload = canonical JSON of the object with the top-level `meta` member removed.
  Renaming or re-describing a pipeline does not change its ID; changing any step, parameter, image or seed does
  (vectors `renamed-same-content`, `highpass-changed`).
- Every `image` MUST be pinned as `name@sha256:<64 hex>`; tags such as `:latest` are rejected.
- Every parameter MUST be explicit, including defaults (BLUEPRINT §3.5: "defaults are written into the run record").
- `tolerance.kind` is `exact` (byte-identical outputs) or `abs`/`rel` with a numeric `value`.
- ID = `pv:sha256:` + SHA-256(`nf.pipeline-version.v1` 0x00 payload).

### 5.2 Chunk (`chunk`)

A chunk is one block of a signal array (Zarr v3 storage, BLUEPRINT §3.4). Its identity is its **decoded**
content, not the compressed bytes: codec versions and compression levels can change the stored bytes without
changing the data.

- Header = canonical JSON of `{"dtype": <dtype>, "order": "C", "shape": [<dims>]}`.
- `dtype` ∈ `int8 uint8 int16 uint16 int32 uint32 int64 float32 float64`.
- Data = the array's elements in C (row-major) order, each **little-endian**, no padding. Length MUST equal
  product(shape) × itemsize. Floats are stored bit-exact (including `-0.0` and NaN payloads).
- Preimage = `nf.chunk.v1` 0x00 header 0x0A data. ID = `chunk:sha256:` + SHA-256(preimage).
- Shape is part of identity: the same bytes as `[4]` and `[2,2]` are different chunks (vectors `int16-4`,
  `int16-2x2-same-bytes-other-shape`).

### 5.3 Provenance batch (`provb`) and the hash chain

BLUEPRINT §3.6: every provenance batch is appended to a hash chain; each batch hash includes the previous one.

```json
{
  "schema": "nf.prov-batch/v1",
  "tenant": "tn_test",
  "seq": 1,
  "prev": "provb:sha256:<id of batch seq-1>",
  "created_at": "2026-09-26T12:00:01.000Z",
  "records": [ { "type": "activity", "id": "act-0002", "label": "run" } ]
}
```

- `schema` MUST be `nf.prov-batch/v1`. The chain is per tenant.
- `seq` starts at 0 and increases by 1. `prev` is `null` exactly when `seq` is 0, otherwise the ID of batch `seq − 1`.
- `created_at` MUST be UTC RFC 3339 with exactly millisecond precision: `YYYY-MM-DDTHH:MM:SS.sssZ`.
- `records` keep their order (arrays are not sorted). Record shapes (PROV node/edge types) are defined with the
  provenance tables in step 3.1; they only need to be valid NF-CJSON here.
- The whole batch object is hashed (nothing excluded). ID = `provb:sha256:` + SHA-256(`nf.prov-batch.v1` 0x00 payload).
- Verification recomputes every ID in order and checks each `prev`; editing any earlier batch breaks the next
  link (tested in `test_prov_batch_chain`). Periodic signing of the chain head is step 3.1/5.3 work, not v1 of
  this spec.

## 6. Timestamps and other conventions inside hashed objects

- Timestamps: UTC, `YYYY-MM-DDTHH:MM:SS.sssZ` (§5.3). Producers MUST NOT hash local times.
- Durations and sample rates: numbers in SI base units (seconds, hertz).
- Binary values inside JSON: lowercase hex strings.
- IDs referencing other objects use the §4 form.

## 7. Conformance

An implementation conforms to v1 when it reproduces every case in `canonical-json.json` (output bytes and
SHA-256), rejects every `errors` case, reproduces every row of `numbers.json`, and reproduces every ID in
`ids.json`. Vector files are ASCII with `\u` escapes so editors that normalise Unicode cannot corrupt them.

Current status: the Python reference passes all of it. nf-core (Rust, step 4.2) passes all of it too: every
`canonical-json.json` case and error case, every `numbers.json` row, and every `ids.json` ID recomputed from the
spec objects (`core/nf-core/tests/vectors.rs`). Observation for v2: an integral double in [2^53, 1e21) is written
as a plain integer (RFC 8785), which §3.1 rejects as input; both implementations behave the same.

---

# Spec v2 additions

Everything below was added in v2 (2026-09-26). It describes the platform code as built in M2-M6 (the M6 training tags as of the
m6-registry work of 2026-09-26); the code was not
changed to write it. Where the code departs from the v1 conventions the departure is recorded (§11), not fixed:
fixing it changes stored hashes or signatures and is a v3 decision.

## 8. Registry of tags and prefixes

Naming convention (already used by v1): `nf.<name>.vN` (dot) is a **domain tag** placed in front of a preimage;
`nf.<name>/vN` (slash) is a **document schema name** carried in a JSON `schema` member. A schema name is never a tag.

### 8.1 Hash tags (SHA-256 over `TAG || 0x00 || payload`, the §4 construction)

| Tag | Output | Payload | Section | Code (`services/platform/nf_platform/`) | Build/security item |
|---|---|---|---|---|---|
| `nf.pipeline-version.v1` | `pv:sha256:<hex>` | v1 §5.1 | v1 | `pipelines/spec.py` | BLUEPRINT §3.5 |
| `nf.chunk.v1` | `chunk:sha256:<hex>` | v1 §5.2 | v1 | `ingest/stream/protocol.py` `chunk_id_bytes` | BLUEPRINT §3.4 |
| `nf.prov-batch.v1` | `provb:sha256:<hex>` | v1 §5.3 | v1 | `provenance/chain.py` `batch_id` | BLUEPRINT §3.6 |
| `nf.audit-batch.v1` | `auditb:sha256:<hex>` | NF-CJSON of the audit batch | §9.1 | `audit/chain.py` `batch_id` | BUILD-GUIDE 2.8; SEC-100, SEC-105 |
| `nf.prov-node.v1` | 64 hex (bare digest) | NF-CJSON of a provenance node record | §9.2 | `provenance/chain.py` `node_hash` | BUILD-GUIDE 3.1; BLUEPRINT §3.6 |
| `nf.consent-record.v1` | 64 hex (bare digest) | NF-CJSON of a consent ledger record | §9.3 | `governance/consent.py` `record_hash` | BUILD-GUIDE 5.3; BLUEPRINT §8.3 |
| `nf.ruleset.v1` | 64 hex (bare digest) | NF-CJSON array of the public rule objects | §9.4 | `governance/rules.py` `content_hash` | BUILD-GUIDE 5.2; BLUEPRINT §8.2 |
| `nf.sweep-variant.v1` | first 12 hex of the digest (a label) | NF-CJSON `{"base", "params"}` | §9.5 | `sweeps/service.py` `variant_label` | BUILD-GUIDE 3.6 |
| `nf.training-subject.v1` | 64 hex (bare digest) | tenant UUID 0x00 subject UUID (ASCII, lowercase) | §9.6 | `registry/manifest.py` `subject_hash` | BUILD-GUIDE 6.1, 6.4; SEC-046 |
| `nf.training-manifest.v1` | 64 hex (bare digest) | NF-CJSON of the training manifest | §9.7 | `registry/manifest.py` `build`, `digest` | BUILD-GUIDE 6.1; BLUEPRINT §8.4 |

### 8.2 Signature tags (Ed25519, RFC 8032, over `TAG || 0x00 || payload`)

| Tag | Signed payload | Section | Code | Build/security item |
|---|---|---|---|---|
| `nf.stream-chunk.v1` | NF-CJSON of the chunk signing body | §10.1 | `ingest/stream/protocol.py` `signing_payload` | SEC-040, SEC-094 |
| `nf.device-token.v1` | NF-CJSON of the device-token claims | §10.2 | `ingest/stream/protocol.py` `make_device_token`, `verify_device_token` | SEC-016, SEC-017 |

### 8.3 Signed documents WITHOUT a domain tag (registered as built; see §11)

| Document | Signed bytes | Section | Code | Build/security item |
|---|---|---|---|---|
| provenance batch signature | ASCII bytes of the `provb` ID | §10.3 | `provenance/api.py` (sign/verify), `provenance/signing.py` | SEC-043 |
| `nf.prov-anchor/v1` | NF-CJSON of the anchor without `sig` | §10.4 | `provenance/integrity.py` | SEC-043 |
| `nf.consent-anchor/v1` | NF-CJSON of the anchor without `sig` | §10.4 | `governance/consent.py` | BUILD-GUIDE 5.3 (SEC-043 pattern) |
| `nf.audit-anchor/v1` | NF-CJSON of the anchor without `sig` | §10.4 | `governance/audit_integrity.py` | SEC-105 (AppSec M1, 2026-09-26) |
| `nf.deletion-certificate/v1` | NF-CJSON of the certificate without `signature` | §10.5 | `governance/certificate.py` | BUILD-GUIDE 5.5; BLUEPRINT §8.4; SEC-046 |

### 8.4 Other tags

| Tag | Use | Section | Code | Build/security item |
|---|---|---|---|---|
| `nf.wal.v1` | AES-256-GCM associated data of an edge WAL record | §10.6 | `services/platform/edge_prototype/wal.py` | BUILD-GUIDE 2.7; SEC-037, SEC-093 |

### 8.5 ID kinds and regexes

v2 adds one ID kind, `auditb`. Regex for any v2 ID:

```
^(blob|pv|chunk|provb|auditb):sha256:[0-9a-f]{64}$
```

The v1 regex (§4) is unchanged. Database constraints that use it (`CONTENT_ID_RE` in `db/models.py`) correctly
exclude `auditb`, which is stored only as an audit batch ID (`^auditb:sha256:[0-9a-f]{64}$`, `audit/chain.py`
`ID_RE`). Bare digests (§9.2-§9.4) match `^[0-9a-f]{64}$` (CHECK constraints on `node_hash` and `record_hash`);
they are digests of a record, not IDs, and are never written with a prefix. The same holds for the M6 training
digests (§9.6, §9.7; `model_version.manifest_sha256` has the CHECK `^[0-9a-f]{64}$`).

### 8.6 Schema names and fixed strings in use (not tags; listed so that names are not reused)

`nf.pipeline-version/v1`, `nf.prov-batch/v1`, `nf.audit-batch/v1`, `nf.consent-record/v1`, `nf.consent-anchor/v1`,
`nf.prov-anchor/v1`, `nf.audit-anchor/v1` (AppSec M1), `nf.deletion-certificate/v1`, `nf.shred-ledger/v1`, `nf.ruleset/v1`,
`nf.jurisdiction-rules/v1`, `nf.upload-manifest/v1`, `nf.run-record/v1`, `nf.phi-services/v1`, `nf.toy-model/v1`,
`nf.signal/v1`, `nf.repro-report/v1`, `nf.fda-evidence-kit/v0`, `nf.requirements/v1`, `nf.soup/v1`,
`nf.traceability/v0`, `nf.pf-map/v1`, `nf.channel-estimate/v1`, `nf.training-manifest/v1` (M6),
`nf.model-card/v1` (M6). Other fixed strings:
device-token prefix `nfd1` and audience `nf-ingest/v1`; WAL file magic `NFWAL1`; media type
`application/vnd.nf.window.v1`; API-key prefix `nfb_live_` (HMAC-SHA-256 with a pepper, not a content hash).

## 9. Hashed objects (v2)

All payloads are NF-CJSON v1 (§3). Timestamps use the §6 millisecond UTC form.

### 9.1 Audit batch (`auditb`)

```json
{"schema": "nf.audit-batch/v1", "scope": "<tenant uuid>|_platform", "seq": 0, "prev": null,
 "created_at": "YYYY-MM-DDTHH:MM:SS.sssZ", "period": {"start": "<ts>", "end": "<ts>"},
 "events": [{"seq": 1, "id": "<uuid>", "ts": "<ts>", "type": "...", "action": "...", "outcome": "...",
             "actor": {"kind": "...", "id": "...", "auth": "..."}, "resource": {"type": "...", "id": "..."},
             "request_id": null, "details": {}}]}
```

- Same rules as `provb` (§5.3): `seq` starts at 0, `prev` is `null` exactly when `seq` is 0 and otherwise the
  `auditb` ID of batch `seq − 1`; `created_at` in §6 form; the whole object is hashed.
- The chain is per `scope` (a tenant UUID, or `_platform` for events without a tenant); event `seq` values
  increase strictly across the whole chain.
- ID = `auditb:sha256:` + SHA-256(`nf.audit-batch.v1` 0x00 payload). The object stored in the WORM `audit` bucket
  (`chain/<scope>/<seq:012d>.json`) IS the payload.
- Verification (`audit/chain.py` `verify_chain`) takes an `expected_head`, so a modified last batch is caught too.
- Added 2026-09-26 (AppSec M1; verification rules only, no hashed byte changes): `verify_chain` also takes the
  `scope` being verified (every batch's `scope` member must equal it) and the scope's `audit_batch` rows, which must
  match the objects one to one (seq, batch ID, `prev`, event count, first and last event `seq`). The job
  `audit.verify` additionally compares every batched event with the row still in `audit_event` and the database
  head with the latest signed `nf.audit-anchor/v1` (§10.4). A batch covers a contiguous run of its scope's event
  `seq` values.

### 9.2 Provenance node hash (`nf.prov-node.v1`)

Node record (`provenance/chain.py` `node_record`): `{"type": "entity"|"activity"|"agent", "id": "<uuid>",
"label": "<node type>", "ref"?: "<platform id>", "content"?: "<content ID>", "attrs"?: {...}}`. `ref` and
`content` are omitted when null, `attrs` when null or empty (the same shape as the node records inside a v1 `provb`
batch).

Hash = lowercase hex SHA-256(`nf.prov-node.v1` 0x00 NF-CJSON(record)), stored in `prov_node.node_hash` and
recomputed by chain verification. Edge records are not hashed on their own (the batch covers them).

### 9.3 Consent ledger record (`nf.consent-record.v1`)

```json
{"schema": "nf.consent-record/v1", "tenant": "<uuid>", "seq": 0, "prev": null, "id": "<uuid>",
 "subject": "<uuid>", "kind": "grant", "scopes": ["collection", "processing"],
 "document": {"id": "<uuid>", "sha256": "<64 hex>"}, "basis": "...", "collector": "<principal id>",
 "evidence": null, "recorded_at": "YYYY-MM-DDTHH:MM:SS.sssZ"}
```

- Hash = lowercase hex SHA-256(`nf.consent-record.v1` 0x00 NF-CJSON(record)) = `consent_record.record_hash`.
- Chain per tenant: `prev` is `null` for `seq` 0, otherwise the **bare hex** `record_hash` of record `seq − 1`.
- `kind` is `grant` or `withdraw`; `document` is `null` for a withdrawal. `scopes` are de-duplicated and sorted
  before hashing (an implementation canonicalises them itself, so a record with unsorted or repeated scopes
  hashes like its canonical form; vector `consent_record_noncanonical_scopes`); `document.sha256` is the SHA-256
  of the consent document.

### 9.4 RuleSet content hash (`nf.ruleset.v1`)

`content_sha256` in `rules/ruleset.yaml` = lowercase hex SHA-256(`nf.ruleset.v1` 0x00 NF-CJSON(array)). The array
lists every rule's public object (`Rule.public()`) in manifest file order, then rule order within a file:
`{"id", "jurisdiction", "title", "instrument", "status_text", "effective_date", "citation", "predicate",
"assumptions", "obligations": [{"id", "text", "flag"?}], "review_status", "review", "draft", "badge", "notes"}`.
The loader collapses whitespace in free-text fields before hashing. `draft` and `badge` are derived from
`review_status` and are part of the hash (§11 item 5). The loader refuses a RuleSet whose hash does not match the
manifest.

### 9.5 Sweep variant label (`nf.sweep-variant.v1`)

Label = first 12 lowercase hex characters (48 bits) of SHA-256(`nf.sweep-variant.v1` 0x00
NF-CJSON(`{"base": "<pv ID of the base>", "params": {"<step>.<param>": value}}`)). It names the variant
PipelineVersion (`<base name>.mv-<label>`, inside `meta`, which §5.1 excludes from the `pv` ID). It is a label, not
an ID: the variant's identity is its own `pv` ID. The key order of `params` does not matter (NF-CJSON sorts keys).

### 9.6 Training subject hash (`nf.training-subject.v1`)

Hash = lowercase hex SHA-256(`nf.training-subject.v1` 0x00 T 0x00 S), where T and S are the tenant UUID and the
subject UUID in the 36-character lowercase hyphenated form (`^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$`),
ASCII-encoded. Upper-case hex input is folded to lower case first (the code parses both values with Python
`uuid.UUID` and writes `str()`). The preimage is raw bytes, not NF-CJSON. The digest names a training subject inside
one tenant without naming the subject (pseudonymous, SEC-046); including the tenant means the same subject UUID in
two tenants gives unrelated hashes. SISA shard assignments (`shards`) are keyed by it.

### 9.7 Training manifest digest (`nf.training-manifest.v1`)

Manifest (`registry/manifest.py` `build`; stored with the model version, digest in `model_version.manifest_sha256`):

```json
{"schema": "nf.training-manifest/v1", "tenant": "<uuid>", "inputs": ["<prov node uuid>", "..."],
 "subjects": ["<64 hex>", "..."], "n_subjects": 2, "n_source_recordings": 3, "excluded_subjects": ["<64 hex>"],
 "pipeline_version_ids": ["pv:sha256:<hex>"], "code_commit": "<git sha>", "recipe": null | "sisa",
 "parent_version": null | "<model version uuid>", "shards"?: {"<64 hex>": 0},
 "weights_source"?: "platform" | "upload"}
```

- `inputs`, `subjects`, `excluded_subjects` and `pipeline_version_ids` are de-duplicated and sorted (code-point
  order); `n_subjects` is the number of distinct `subjects`. The subject values are §9.6 hashes. Input IDs are
  folded to the lowercase canonical UUID form before de-duplication (vector case `duplicate-inputs`).
- `shards` is present only when non-empty (SISA); its values are integers. `recipe` and `parent_version` are
  always present (`null` when unset).
- Digest = lowercase hex SHA-256(`nf.training-manifest.v1` 0x00 NF-CJSON(manifest)).
- **Amendment 2026-09-26 (AppSec M3), additive v2 field `weights_source`:** `"platform"` when the weights are the
  output of a platform training job (the registry binds `inputs` to what the weights were derived from), `"upload"`
  when the bytes were uploaded (`inputs` are then the uploader's declaration; the platform cannot verify offline
  training). The registry writes it in every manifest built after the amendment; manifests built before it do not
  have the member and keep their digests (a verifier MUST NOT add it to an old manifest). When present it is a
  normal member of the hashed object (no other rule changes). Vectors: the cases `weights-source-upload` and
  `weights-source-platform` in `ids-v2.json` `training_manifest`, inserted before the frozen cases so every earlier
  byte of the file is unchanged (`git diff` shows additions only). nf-core reproduces both cases
  (`TrainingManifestArgs::weights_source`, `core/nf-core/tests/vectors_v2.rs`; 2026-09-27).

## 10. Signed objects and other tagged bytes (v2)

Signatures are Ed25519 (RFC 8032, pure, deterministic). The vectors use the RFC 8032 §7.1 TEST 1 key, a published
test key.

### 10.1 Stream chunk signature (`nf.stream-chunk.v1`)

Body (NF-CJSON; all members required):

```json
{"chunk_id": "chunk:sha256:<hex>", "n_channels": 2, "n_clock_offsets": 1, "n_local_clock": 2, "n_samples": 2,
 "seq": 7, "stream_id": "<uuid>", "t_first": 1000, "t_last": 1000.004, "timing_sha256": "<64 hex>"}
```

- `chunk_id` is the v1 §5.2 ID of the samples with shape `[n_samples, n_channels]`.
- `t_first`/`t_last`: first/last LSL timestamp (`0.0` when there are none).
- `timing_sha256` = plain (untagged) SHA-256 over every LSL timestamp, then every clock-offset pair
  `(collection_time, offset)`, then every local-clock pair `(lsl_time, monotonic_time)`, each as float64
  little-endian, concatenated.
- Signed bytes = `nf.stream-chunk.v1` 0x00 body. A `seq` above 2^53 − 1 or a NaN/Inf timestamp cannot be
  canonicalised, and the chunk is rejected.

### 10.2 Device token (`nf.device-token.v1`)

Token = `nfd1.` base64url(payload, no padding) `.` base64url(signature, no padding); payload = NF-CJSON of
`{"aud": "nf-ingest/v1", "device_id", "exp", "iat", "stream_id", "tenant_id"}` (`iat`/`exp` are integer Unix
seconds); signature = Ed25519 over `nf.device-token.v1` 0x00 payload. The verifier rejects a payload that is not
already canonical, a lifetime above 600 s and tokens outside a ±30 s clock leeway.

### 10.3 Provenance batch signature (no tag)

Ed25519 over the ASCII bytes of the batch's `provb` ID (for example `provb:sha256:7caf...`). The ID already commits
to the whole batch. Key: the provenance keyring (`NF_PROV_SIGNING_KEY`).

### 10.4 Chain-head anchors (no tag)

`{"schema": "nf.prov-anchor/v1" | "nf.consent-anchor/v1", "tenant", "seq", "head", "anchored_at", "key_id", "sig"}`;
`sig` = lowercase hex of Ed25519 over NF-CJSON of the document without `sig`. `head` is the `provb` ID (prov) or the
bare consent `record_hash` (consent). Both are signed with the provenance keyring and stored in the WORM `audit`
bucket (`prov-anchors/<tenant>/<YYYY-MM-DD>.json`, `consent-anchors/<tenant>/<YYYY-MM-DD>.json`).

Added 2026-09-26 (AppSec M1): `{"schema": "nf.audit-anchor/v1", "scope", "seq", "head", "anchored_at", "key_id",
"sig"}`, the same construction with `scope` (a tenant UUID or `_platform`, §9.1) in place of `tenant`; `head` is the
`auditb` ID of batch `seq`. Stored at `audit-anchors/<scope>/<seq:012d>.json` (one anchor per chain position, written
by the job `audit.batch` after each batch; the newest anchor is the one with the highest `seq`). No vector yet: the
signature construction is byte-for-byte the §10.4 one, which the `prov_anchor`/`consent_anchor` vectors cover.

### 10.5 Deletion certificate (no tag)

`signature` = `{"alg": "Ed25519", "key_id", "value": base64(signature)}` over NF-CJSON of the certificate without
`signature`; key `NF_CERT_SIGNING_KEY`. Anyone can verify it offline with the published raw public key.

### 10.6 Edge WAL associated data (`nf.wal.v1`)

AAD = `nf.wal.v1` 0x00 UTF-8(stream_id) 0x00 ASCII(decimal seq). Record file = `NFWAL1` ‖ 12-byte nonce ‖
AES-256-GCM(key, nonce, signed Chunk message, AAD). The nonce is random, so only the AAD has a vector.

## 11. Departures from the v1 conventions (recorded, not changed)

Flagged to the build queen on 2026-09-26. None of them changes a stored v1 ID.

1. **Untagged signatures (§10.3-§10.5).** v1 §4 separates domains with a tag. The stream-chunk and device-token
   signatures follow it; the provenance batch signature, both anchors and the deletion certificate sign untagged
   bytes, and the provenance key signs three of these message types. They cannot currently be confused (a batch
   message starts with `provb:`, the anchors are JSON objects with different `schema` values), but the separation
   rests on the payload shape, not on a tag. A v3 could sign `<tag> 0x00 payload` for each; that invalidates
   existing signatures, so it needs a migration (re-sign, or verify both forms for a period).
2. **Bare digests where §6 says "IDs referencing other objects use the §4 form".** `node_hash`, consent
   `record_hash` (and the consent `prev` and anchor `head` that reference it) and `content_sha256` are bare hex.
3. **Deletion-certificate timestamps** (`requested_at`, `started_at`, `completed_at`, `key_destruction.at`, …) use
   Python `isoformat()` (microseconds, `+00:00`), not the §6 millisecond `Z` form. They are signed, not used as IDs.
4. **Binary values in JSON:** §6 says lowercase hex; the deletion certificate carries its signature as base64
   (the anchors use hex).
5. **The RuleSet hash covers presentation text:** `draft` and `badge` (UI wording derived from `review_status`)
   are hashed, so rewording a badge changes `content_sha256` and requires a new RuleSet version.
6. **The sweep label is 48 bits.** The `sweeps/service.py` docstring says the label "cannot collide"; a 12-hex
   label can, with probability about n²/2⁴⁹ for n variants of one base (negligible at the 64-variant limit). It
   only names a variant; the `pv` ID is the identity.
7. **WAL AAD separators:** `stream_id` is not length-prefixed. The AAD is unambiguous only because stream IDs are
   UUIDs (no 0x00 byte). The same holds for the §9.6 training-subject preimage (two UUIDs joined by 0x00).
8. **The training-subject hash is unkeyed.** Anyone who knows a tenant UUID and a subject UUID can recompute it and
   find that subject in a manifest; it hides the subject from readers who do not hold the subject UUID, nothing
   more. A keyed form (HMAC with a per-tenant secret) would make manifests unlinkable outside the platform but
   changes every stored manifest digest, so it is a v3 decision.
9. **The manifest `tenant` member** is written as the caller passes it (`str(tenant_id)`), while `inputs` and the
   subject hashes are normalised through `uuid.UUID`. The spec requires the canonical lowercase form there (the
   vectors use it); a caller that passed an upper-case string would produce a different, non-conforming digest.
   Normalising in `build` would remove the trap without changing any conforming digest (note sent to m6-registry).

## 12. Conformance (v2)

An implementation conforms to v2 when it conforms to v1 (§7) and reproduces every case in `ids-v2.json`: every
`auditb` ID and chain link, every bare digest (§9.2-§9.4, §9.6, §9.7), every sweep label, every preimage (`preimage_hex`,
`payload`, `body`, `signed_part`, `aad_hex`), and verifies every signature with the listed test public key (with the
RFC 8032 key it also reproduces them, because Ed25519 is deterministic).

Current status: the Python reference (`test_vectors_v2.py`, which also checks its own Ed25519 against RFC 8032
§7.1 TEST 1-3) and the platform code (`services/platform/tests/spec_v2`, calling the functions listed in §8)
reproduce all of it. nf-core (Rust, `nf_core::ids_v2`) reproduces all of it too (`core/nf-core/tests/vectors_v2.rs`,
27 cases): every `auditb` ID and chain link, every bare digest, sweep label, preimage, payload, body, signed part
and AAD recomputed from the case inputs (prov-node records and training manifests rebuilt from `args`), and, with
the `stream` feature (Ed25519 via `ed25519-dalek`), every signature verified with the test public key and
reproduced from the RFC 8032 secret; tampered inputs fail. Property tests check that permuting, duplicating or
upper-casing manifest inputs and permuting or duplicating consent scopes never changes the digest. Without the
`stream` feature the signature checks are not compiled; the hash and byte checks still run.
