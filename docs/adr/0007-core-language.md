# ADR 0007: Rust for the shared SDK core

- Status: **Accepted**
- Date: 2026-09-26
- Deciders: owner (Marius Carlsson) at GATE B
- Source: `architecture/DECISIONS.md` D7, `BRIEF.md` "GATE B decision". Company name: NeuroForge Bio.

## Decision

`core/nf-core` is a Rust crate; Python via PyO3/maturin, C++/Unity/Unreal via a C ABI. Signal processing stays in Python/MNE.

## Consequences

The canonical hashing spec (`docs/spec/hashing.md`) is implemented in Python (reference) and Rust (nf-core) against shared test vectors. Local Rust builds are debug only with one job (`.cargo/config.toml`).
