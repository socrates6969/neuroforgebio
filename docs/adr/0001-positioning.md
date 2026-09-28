# ADR 0001: Positioning: reproducible, comparable pipelines and neural-data governance

- Status: **Accepted**
- Date: 2026-09-26
- Deciders: owner (Marius Carlsson) at GATE B
- Source: `architecture/DECISIONS.md` D1, `BRIEF.md` "GATE B decision". Company name: NeuroForge Bio.

## Decision

Reposition away from "automated neuro-cleaning". The product story leads with versioned, comparable pipelines (multiverse comparison), provenance and neural-data governance (consent ledger), from electrode to model. Grounds: Kessler 2025 and Huang 2025 as summarised in `market/validation.md` #5 and `market/landscape.md` §3.

## Consequences

Website copy follows BLUEPRINT §2.6; copy-lint (`tools/copy-lint`) bans "automated neuro-cleaning". Architecture is unchanged: it is already built around the provenance graph (BLUEPRINT §3.6).
