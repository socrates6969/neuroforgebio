# Webhooks and run events (BUILD-GUIDE 4.6; SEC-045, SEC-076)

## Events

| Event | When | Payload schema |
|---|---|---|
| `run.finished` | a run reaches `succeeded`, `failed` or `cancelled` | `RunFinishedEvent` in `openapi/v1.yaml` (`webhooks.runFinished`) |

Events only report what happened on the platform. No event, field or endpoint addresses a device
(SEC-090; hw-guard scans the payload schemas). Consent-withdrawn and model-tainted events arrive
with M5/M6.

## Signing (SEC-045)

```
NF-Webhook-Id: <event id; the same on every retry>
NF-Webhook-Timestamp: <unix seconds>
NF-Webhook-Signature: t=<unix seconds>,v1=<hex HMAC-SHA-256(secret, "<t>." + raw body)>[,v1=...]
```

- The secret (`nfb_whk_...`) is shown once when the endpoint is created or rotated. The HMAC key is
  its UTF-8 bytes. The platform stores it AES-256-GCM-encrypted.
- Receivers verify the raw body, reject timestamps more than 5 minutes from their clock, compare in
  constant time and deduplicate on the event id. Sample verifier (standard library only):
  `services/platform/examples/verify_webhook.py`.
- Rotation (`POST /v1/webhooks/{id}/rotate-secret`): the old secret stays valid for 24 h
  (`Settings.webhook_rotation_overlap_s`); meanwhile every delivery carries one `v1=` per valid
  secret.

## Delivery

- Deliveries are queued in the same transaction as the state change (`webhook_delivery`).
- A dispatcher (`nf_platform.webhooks.service.deliver_due`, run by the scheduler) leases due rows
  (role `nf_webhook`, which sees only that table), then delivers each in the tenant's own session.
- 2xx = delivered. Anything else (or a network error) is retried with exponential backoff
  (30 s, 60 s, 120 s, ... capped at 1 h) up to 8 attempts, then `failed`.
- `GET /v1/webhooks/{id}/deliveries` shows the history. Deleting an endpoint disables it and fails
  its pending deliveries.

## SSRF protection (SEC-076)

- Registration: `https` only, a DNS host name (no IP literals, no `localhost`, `.local`,
  `.internal`, single-label names), no user-info, port 443 or 1024-65535.
- Every delivery resolves the host once; if any address is private (RFC 1918), loopback,
  link-local, a cloud metadata address (169.254.169.254, fd00:ec2::254, ...), CGNAT, multicast,
  reserved, or an IPv6 form that embeds one of these (IPv4-mapped, NAT64, 6to4), nothing is sent.
- The connection goes to the checked address (TLS SNI and `Host` carry the name), so a second DNS
  answer (rebinding) is never used. Redirects are not followed; the timeout is 10 s.
- Deployment layer (infra step): webhook egress also goes through the egress proxy with the same
  deny list.

## Server-sent events

`GET /v1/runs/{run_id}/events` streams `run.state` events (then `end`, `timeout` or `error`). The
stream re-checks the caller's credential every 30 s (SEC-017).
