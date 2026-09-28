# ADR 0004: Hosting: static CDN for the website, AWS for the platform

- Status: **Accepted**
- Date: 2026-09-26
- Deciders: owner (Marius Carlsson) at GATE B
- Source: `architecture/DECISIONS.md` D4, `BRIEF.md` "GATE B decision". Company name: NeuroForge Bio.

## Decision

Website on any static CDN host (two projects). Platform on AWS, one US region at launch, EU region planned. Keep portable choices where cheap: Postgres, S3 API, OCI containers, OIDC, OpenTelemetry, OpenTofu. R2 may hold only public/non-PHI data (BAA not verified).

## Consequences

`infra/` holds OpenTofu modules for AWS (network, Postgres, bucket, KMS, container service). It is code only: creating the account and any apply or spend are owner actions.
