# ADR 0006: Licensing: Apache-2.0 for SDK/core later, proprietary platform

- Status: **Accepted**
- Date: 2026-09-26
- Deciders: owner (Marius Carlsson) at GATE B
- Source: `architecture/DECISIONS.md` D6, `BRIEF.md` "GATE B decision". Company name: NeuroForge Bio.

## Decision

nf-core, SDKs, converters, the synthetic-data tool and the step library will be Apache-2.0; the hosted platform (ledger, registry, evidence kit) is proprietary. Until SDK code ships the repository stays all-rights-reserved (see `LICENSE`).

## Consequences

No open-source licence file is added yet. Crates and packages are marked `publish = false` / `private: true`; publishing is an owner action.
