# ADR 0002: Company name via a single brand token

- Status: **Accepted**
- Date: 2026-09-26
- Deciders: owner (Marius Carlsson) at GATE B
- Source: `architecture/DECISIONS.md` D2, `BRIEF.md` "GATE B decision". Company name: NeuroForge Bio.

## Decision

The company name is NeuroForge Bio (GATE B). It is stored once, in `packages/content/brand.json`, and read from there by every page and component.

## Consequences

A rename is a one-line change. The copywriter's brand-token test fails if the literal name appears elsewhere under packages/, apps/ or openapi/. Public launch waits for the clash check in `market/names.md`.
