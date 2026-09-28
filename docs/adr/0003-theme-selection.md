# ADR 0003: Build-time theme per deployment; clinical canonical

- Status: **Accepted**
- Date: 2026-09-26
- Deciders: owner (Marius Carlsson) at GATE B
- Source: `architecture/DECISIONS.md` D3, `BRIEF.md` "GATE B decision". Company name: NeuroForge Bio.

## Decision

Two static builds from one codebase: `THEME=clinical` (canonical, primary domain) and `THEME=cosmos` (secondary host, `rel=canonical` to clinical). No runtime theme toggle in v1.

## Consequences

The clinical bundle never downloads three.js; QA covers two fixed builds; tokens are scoped by `[data-theme]` so a runtime toggle can be added later.
