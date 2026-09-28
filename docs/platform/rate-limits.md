# Rate limits and quotas (BUILD-GUIDE 4.8; SEC-075)

Two layers limit request rates, and quotas limit what a tenant can hold.

## 1. In-process token bucket (implemented, `nf_platform.limits.ratelimit`)

- One bucket per credential: an API key (by public id), a user or a device, within its tenant.
- Defaults (configuration, not measurements): `rate_limit_rps = 50`, `rate_limit_burst = 200`
  (`Settings`). An empty bucket gives `429` `application/problem+json`
  (`type: urn:nf:problem:rate-limited`) with `Retry-After` in whole seconds.
- Memory is bounded (100 000 buckets, least recently used evicted).
- Limitation: the bucket is per API process. With N replicas a client can get up to N times the
  rate. That is why layer 2 exists.

## 2. Gateway (to be configured with the infra step, not in this repository yet)

The edge gateway (managed API gateway or the ingress controller) must enforce:

- a global per-tenant limit (key: tenant id from the validated token or the API key's public id
  prefix; never a client-supplied header);
- a per-IP limit for unauthenticated routes (`/v1/health`, and `/v1/public/*` when 4.7 is enabled),
  with the client IP taken from the gateway's own connection, never from `X-Forwarded-For` sent by the
  client;
- request body size limits in line with the API (uploads use parts of at most 64 MiB);
- the same `429` problem+json shape and `Retry-After`.

The API never trusts `X-Forwarded-For` itself. Load tests of these limits run on staging only
(SEC-075).

## 3. Stream chunks (implemented, `nf_platform.ingest.stream.service`; P7.7 R1)

Devices sign one chunk per at least 20 ms of samples, never per packet. nf-core enforces that on the
device (`MIN_CHUNK_MS = 20`, chunk length set by `chunk_ms` from the stream's `sfreq`; the only
shorter chunk is the final one, and writing it closes the writer). The ingest server adds:

- **Chunk rate, enforcing.** A token bucket per stream on NEW chunks: `stream_chunk_rate = 150`/s,
  `stream_chunk_burst = 300` (`Settings`; env `NF_STREAM_CHUNK_RATE`, `NF_STREAM_CHUNK_BURST`).
  An empty bucket gives gRPC `RESOURCE_EXHAUSTED` and a `stream.rate_limited` audit event; the
  clients back off and resume from `next_seq`. A resent chunk that is already stored never takes a
  token, so a resume is never refused. The limit counts chunks, not seconds of signal: the per-chunk
  server work (signature check, transaction, audit) is what it bounds, and tiny chunks carry almost
  no signal time (nfb-security, 2026-09-27).
  **Drain time after an outage** (arithmetic, checked by a fake-clock test): WAL chunks the server
  never stored are NEW, so a backlog shares the limit with the live stream. At 20 ms chunks (50/s
  live) the headroom is 100/s: 60 s offline (3,000 chunks) catches up in about 27 s after the
  300-chunk burst. At the 100 ms default (10/s live) the headroom is 140/s: 600 chunks catch up
  within the burst plus about 2 s.
  **Idle state:** per-stream bucket and short-chunk state idle for more than 10 minutes is dropped
  (an open short-chunk window is written first), so abandoned streams do not leak memory.
- **Before multi-replica production (open, SEC-075):** the bucket is per ingest process, so N
  replicas allow N x 150/s per stream. Route each stream to one replica (sticky by `stream_id`) or
  keep the bucket in shared state (a Postgres row or Redis). Also add a per-tenant cap on
  concurrent streams to the quotas, so many streams cannot multiply the per-stream limit.
- **Short chunks, audit only.** A chunk under 20 ms at the registered `sfreq` that is not the final
  chunk is counted (it is known not to be final once the next new chunk is stored). Counts are
  aggregated per stream into one `stream.short_chunk` event (`count`, `min_duration_ms`) per minute
  while the stream is open, plus the open window at `FinishStream`. Nothing is refused: refusing
  would break the resend of a short final chunk.

Streams without a nominal rate (markers) have no chunk duration and are exempt from the 20 ms rule.

## Quotas (implemented, `nf_platform.limits.quotas`)

| Quota | Counted | Over the limit |
|---|---|---|
| `storage_bytes` | stored objects + declared size of uploads in flight | `403` `quota-exceeded` when an upload session would exceed it |
| `active_runs` | runs `queued` or `running` (a sweep counts all its runs) | `429` `quota-exceeded` + `Retry-After`; the request's transaction rolls back |

Limits come from the `tenant_quota` row (written by provisioning only; the API role can only read
it) or else from `Settings.quota_storage_bytes` / `quota_active_runs`. A per-tenant advisory lock
serialises checks. `GET /v1/quotas` shows the tenant's limits and usage.

## Revocation (SEC-017)

API keys are looked up on every request, so a revoked key is refused at once. Open streams
re-check their credential: server-sent events every 30 s (`Settings.reauth_interval_s`), gRPC
`StreamChunks` every 30 s or 1000 chunks for device revocation and on every chunk for token expiry.
Either way a revoked credential stops within 60 s.
