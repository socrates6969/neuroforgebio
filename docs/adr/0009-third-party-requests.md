# ADR 0009: Self-hosted fonts, no trackers, no third-party scripts

- Status: **Accepted**
- Date: 2026-09-26
- Deciders: owner (Marius Carlsson) at GATE B
- Source: `architecture/DECISIONS.md` D9, `BRIEF.md` "GATE B decision". Company name: NeuroForge Bio.

## Decision

Fonts are self-hosted (licences checked before use). No analytics, or only cookieless aggregate CDN analytics. No third-party scripts, so the CSP can be `script-src 'self'`.

## Consequences

`design/CONTENT-SPEC.md`'s Google Fonts allowance is superseded. three.js is bundled, never loaded from a CDN.
