# Security review of M2 (main @f4d2d61) + hw-guard scope decision

Reviewer: nfb-security, 2026-09-26. Method: read `docs/hive/M2-REPORT.md` and the security-relevant code in `services/platform/nf_platform`: `ingest/stream/{protocol,service}.py`, `auth/{oidc,api_keys}.py`, `api/deps.py`, `db/context.py`, the grants/RLS in migrations 0001/0002, `storage/{keyring,encrypted,sql_keystore}.py`, `audit/chain.py` and `ingest/uploads/archive.py`. **I did not run the tests.** The results table in the report is taken as given.

**Verdict: M2 is approved for synthetic/public data, subject to fixes F1 and F2 before any real subject data** (which is prod-only anyway, SEC-071). The design quality is high. Highlights:
- **Tenant isolation:** Postgres enforces row-level security on every table (`FORCE ROW LEVEL SECURITY`); the app runs as a non-owner role with `NOBYPASSRLS`; every query is also filtered by tenant in the app; writes to another tenant are refused before they reach the database; and each tenant has its own KMS encryption context.
- **Encryption and keys:** AES-GCM with the tenant, subject, object and version bound into the associated data; the key header records the algorithm (so it can be changed later); keys retire before the 2^32-encryption nonce limit; and decryption checks the key store before any cached key, so a shred takes effect across processes on the next read.
- **Streaming:** Ed25519 signatures over each chunk, covering both the samples and the full timing series (SEC-040/094); duplicate chunks are harmless, and a *different* chunk resent for the same sequence number is rejected with an audit event; suspect segments are recorded, never dropped.
- **Authorization:** every route must declare an action or it is denied; admin roles need a phishing-resistant login (`amr` claim); API keys are HMAC-hashed with a pepper and compared in constant time.
- **Uploads:** the zip extractor checks for path traversal and zip bombs.

## Findings

| ID | Sev | Finding | Required fix | SEC |
|---|---|---|---|---|
| **F1** | **High** | **Encryption for a shredded subject silently creates a new key.** After `shred_subject`, `SqlKeyStore.get_wrapped(…, None)` returns `None`, so `Keyring._active()` → `_new_dek()` mints a fresh DEK. Any later write (a still-open stream, a queued conversion, a worker retry) then stores new data for a withdrawn subject under a new key. Decryption correctly refuses (410), but the encrypt side has no tombstone check | `Keyring.encrypt` (via `_active`) MUST raise `SubjectKeyUnavailable` when **any** row for the subject has `state='shredded'` (a tombstone check in the KeyStore protocol, e.g. `is_shredded()`). An open stream for that subject must be aborted (`FAILED_PRECONDITION`) and an audit event emitted. Test: shred → encrypt raises; shred during an open stream → the next chunk is refused and no new `subject_key` row appears | 034, new **034a** |
| **F2** | Medium | **Revocation and expiry are checked only when an RPC starts.** `StreamChunks` calls `authenticate()` once and then runs as long as the client keeps it open. A revoked device, or an expired token (the 10-minute token lifetime), keeps streaming | Re-check `revoked_at` and `exp` at least every **60 s** of wall time (or every N chunks, whichever comes first) inside the loop, then abort with `UNAUTHENTICATED`. The client reconnects with a fresh token and resumes from `next_seq`. Test: revoke mid-stream → aborted within 60 s; the token expires mid-stream → aborted | 017 |
| **F3** | Medium (documented) | **A shred is incomplete in database backups** while the backup window lasts: a PITR or snapshot copy still holds the wrapped DEK, and the tenant KEK is still live. The keyring docstring records this. The M2 "backup copy unreadable" test covers object copies, not DB backups | No code change for M2. **Policy (binding):** (1) the deletion certificate (5.5) states "unrecoverable in all copies after the backup retention window of N days (ends YYYY-MM-DD)"; (2) the restore procedure re-applies all shreds before the DB serves traffic (SEC-124); (3) keep the DB backup window short (PITR 14 d, SEC-120) and do not take long-retention DB snapshots that contain `subject_key`. D4 design option for later: move `subject_key` to a separate store with a ≤ 14-day backup policy. I have updated SEC-034 to say this honestly | 034, 120, 124 |
| F4 | Low (for M2) | Audit batches are hash-chained but **not signed**. The chain head is held only in Postgres, and Object Lock exists only in CI. An attacker who can write to both the DB and the bucket can rewrite the whole chain | Planned: sign batches with a KMS key and anchor the head to the WORM bucket in step 3.1 (SEC-043). Keep it on the M3 checklist | 043 |
| F5 | Low | The device-auth failure audit has `tenant_id=None` and a free-text reason from the exception | OK. Make sure `reason` never contains token bytes. Today it carries only `ProtocolError` messages: keep it that way (add a test asserting the audit row contains no token substring) | 147 |
| F6 | Info | The API-key pepper rotation fails every old key at once (only one pepper version is accepted) | When pepper rotation is built, verify against `{current, previous}` for a grace period | 052 |
| F7 | Info | The sanity amplitude limits are 1 V placeholders | Set per-modality limits before any real-data tenant (SEC-041); record the source of each limit | 041 |

**Decision on the MinIO image (report open issue 6):** `bitnamilegacy/minio` is approved **for CI tests only**, with these conditions:
- pinned by digest (already done);
- used with synthetic data only;
- never in docker-compose files meant for staging or prod;
- a tracking issue to replace it before M5. Candidate replacements (not evaluated): another S3-compatible test server, or moto's S3 mode.
It is a frozen, unmaintained image, so it must be listed in the SBOM with `nfb:supportLevel=unmaintained` (SEC-083).

## hw-guard scope decision: YES, scan `services/`, with a split rule set

Rationale: the edge prototype and the gRPC servicer live under `services/`. A control path added there would bypass the guard that currently covers only `proto/`, `core/` and `sdk/`. This decision *broadens* coverage, so it does not need the owner's OK; only a narrowing does (§G).

1. **SEC-091 rules (hardware and actuator access): apply in full to `services/**`**, excluding `services/**/tests/**`, the same as in `core/`: `StreamOutlet`, `lsl_create_outlet`, `push_sample`/`push_chunk` on an outlet, imports of `serial`/`pyserial`, `usb`/`pyusb`, `hid`/`hidapi`, `bleak`, `bluetooth`, `ctypes`/`cffi` loading `liblsl` outlet symbols. I found no hits outside tests today (`test_edge_lsl.py` creates an outlet in a test, which is allowed).
2. **SEC-090 name denylist (`stim*`, `pulse*`, `command`, `actuat*`, `trigger_out`, `amplitude_set`, `write_register`): apply to the service's *external surface*, not to arbitrary Python identifiers.** Concretely:
   - generate the OpenAPI document from the FastAPI app in a test (`app.openapi()`) and run the denylist over the paths, operationIds, `x-nf-action` values, and schema property and enum names;
   - run it over the gRPC servicer method names and the generated `_pb2` descriptors (i.e. `proto/` again, from the runtime side);
   - run it over any outbound message/schema module (webhooks, from 4.6).
   This removes the `from alembic import command` and `subprocess` false positives structurally, with **no allow markers**.
3. **Recorded event markers are data, not identifiers.** XDF/BIDS/EDF annotations such as "Stimulus" are values inside recordings and fixtures; the guard never scans data files. API schema fields that carry them must use neutral names (`event_label`, `event_onset_s`, `annotation_text`), so the surface denylist needs no exception. Do **not** add a field named `stimulus*` to the API.
4. The rule sets and paths live in `tools/hw-guard` with CODEOWNERS = the security role. Adding rules or paths: security review. Removing or narrowing any rule or path: owner's written OK (§G).
5. Tests: fixture `bad-service-route` (a FastAPI route `/v1/devices/{id}/stimulate`) fails; fixture `bad-service-outlet` (a `pylsl.StreamOutlet` in `services/platform/nf_platform/`) fails; `from alembic import command` in migrations passes; an XDF fixture with "Stimulus" markers passes.

## Requirement updates made in `security/SECURITY-REQUIREMENTS.md`
- SEC-034 wording made honest about DB backups (F3).
- New **SEC-034a**: shredded subjects are tombstoned; encryption for a shredded subject is refused; open streams are aborted (F1).
- SEC-090/091 now name `services/` in scope, with the surface-scan method above.
