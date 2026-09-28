# ADR 0005: Consent ledger (M5) runs in parallel after M2 and step 3.1

- Status: **Accepted**
- Date: 2026-09-26
- Deciders: owner (Marius Carlsson) at GATE B
- Source: `architecture/DECISIONS.md` D5, `BRIEF.md` "GATE B decision". Company name: NeuroForge Bio.

## Decision

Start M5 once M2 and the provenance tables (3.1) exist, in parallel with the rest of M3/M4. The website (M1) stays first.

## Consequences

M3/M4 need more parallel staff or they slip by roughly the size of M5 (ESTIMATE ~6.75 person-months).
