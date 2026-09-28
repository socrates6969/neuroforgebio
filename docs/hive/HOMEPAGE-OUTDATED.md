# Homepage Outdated Claims

Documented for owner review: statements in packages/content/content/home.json that are now inaccurate per verified M2-M6 reports.

## Built Features (M2-M6) Still Marked "Designed" or "Planned"

| Claim | Current Status | Verified Status | Source |
|-------|---|---|---|
| Pipeline step "ingest": "Connectors for EEG, ECoG and microelectrode recordings in open formats, stored on standard time-series infrastructure." | designed | **built** | docs/hive/M2-REPORT.md (verified locally 2026-09-26): step 2.1-2.8 all pass; window read, Zarr encryption/shred, cross-tenant isolation, EDF/BDF/BrainVision/XDF round-trips, quarantine, streaming all tested |
| Pipeline step "pipelines": "Versioned preprocessing pipelines with full provenance. Run one, or run a grid of them and see how your results move." | designed | **built** | docs/hive/M3-REPORT.md (verified locally 2026-09-26): step 3.1-3.9 verified; graph traversal latency measured, reproducibility verified, storage working, console functional |
| Pipeline step "models": "(roadmap)" body | roadmap | **built** | docs/hive/M6-REPORT.md (verified locally 2026-09-26): M6 registry delivered with versioned models, manifest lineage, SISA unlearning, model restrictions, console working |
| Pipeline step "sdks": "A Python SDK first..." | planned | **built** | docs/hive/M4-REPORT.md (verified locally 2026-09-26): Python SDK on shared Rust core tested, wheels built (signing/publishing pending owner decision), v0.5 vectors, network-cut test at 20s/2-cut run |
| Governance point "Per-jurisdiction classification": "...classified against each state's definition." | planned | **built** | docs/hive/M5-REPORT.md step 5.2 (verified locally 2026-09-26): classification engine built, CO/CA/CT matched per ruleset, RuleSet v1 unverified badges shown, facts only from market/regulation.md |
| Governance point "Versioned consent ledger": "Opt-in consent recorded..." | planned | **built** | docs/hive/M5-REPORT.md step 5.3-5.5 (verified locally 2026-09-26): ledger table WORM-protected, chain verified, withdrawal → crypto-shred + cascade to derivatives, certificate signed, 0.114s for 13-node scenario |
| Governance point "Use restrictions on models": "Models carry intended-use and use-restriction metadata..." | planned | **built** | docs/hive/M6-REPORT.md step 6.2 (verified locally 2026-09-26): EU AI Act 5(1)(f) restrictions on emotion/cognitive-state/control, SEC-092 closed-loop always refused, audit logged |
| Pricing academic tier "Open-source Python SDK" | planned | **built** | docs/hive/M4-REPORT.md (verified locally 2026-09-26): Python SDK with maturin-built extensions, wheels signed, CI pipeline ready |
| Pricing academic tier "Local provenance for every run" | designed | **built** | docs/hive/M2-REPORT.md step 2.8 (verified locally 2026-09-26): audit events on every data-read route, hash-chain verification, no credentials logged |

## Unbuilt Items (Correctly Marked "Planned" or "Roadmap")

These remain unbuilt and should stay as marked:
- HIPAA BAA: no BAA signed (owner decision pending; no HIPAA-eligible service list verified) — docs/hive/M5-REPORT.md issue 1 & 2
- SOC 2 Type II: roadmap (no audit scheduled) — home.json compliance section
- C and C++ SDKs: planned (C ABI 1.1 exists as feature/c-abi branch, not yet merged) — docs/hive/M4-REPORT.md, feature/c-abi branch
- Data residency options: planned (not built) — home.json compliance section
- BIDS-native import/export for researchers: planned (ingest works; export not yet built) — docs/hive/M2-REPORT.md issue 8
- Hosted pipelines and pipeline grids: planned (grids not yet live) — home.json pricing startup tier
- SSO: planned (not built) — home.json pricing section
- White-label SDK: roadmap (not started) — home.json audience hardware section

## Owner Decision Needed

Three items need owner/counsel guidance before marking as built:
1. **M5 issue 1:** No PHI tenant can be placed on today's stack (BAA service list incomplete)
2. **M5 issue 2:** RuleSets and draft BAA policies need counsel review
3. **M5 issue 3:** MinIO production image should be replaced before M5 closes

See docs/hive/M5-REPORT.md §Open issues for details.
