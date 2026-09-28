# Copy claims recheck: /platform, /governance, /sdks, /pricing

2026-09-27, web-copy-2, branch `web/copy-verify` from main f14c44c. This rechecks every factual claim that web-copy
put on these pages, plus `docs/hive/FEATURE_STATUS_UPDATE.md` and the BuildStatePill labels.

Rules applied:
- "Built, tested internally" (`buildState: built-internal`) only where an M-report acceptance row says **pass**, the
  branch is merged to main, and the code is on main.
- CI-only work (written, not run) does not count as tested.
- Nothing in M2-M6 is deployed. Every report says "Nothing deployed", so built items never say "available".

Merge state checked with `git merge-base --is-ancestor origin/<branch> origin/main`:
- Merged to main: feature/m2-ingest, m3-pipelines, m4-api-sdk, m5-ledger, m6-registry.
- **Not merged:** feature/c-abi, feat/cabi-transport-hardening, fix/cabi-lows, swarm1/abi-conformance,
  feature/engine-sdks.

Verdicts: OK = correct as it stood; FIXED = was wrong, corrected in this branch; UPGRADED = was understated,
evidence meets the "built" bar.

## Cross-cutting finding

Every built-internal item also carried a lifecycle `status` of designed, planned or roadmap. So a card showed
"Status: Planned" next to "Built, tested internally", and /governance's body said "None is available yet" above
six "Built" pills. **FIXED:** `status` is removed from items that carry `buildState` (it is optional in the
schema), and the body and meta text now say "built and tested internally; not deployed".

## /platform (`pages/platform.json`)

| Claim | Source | Verdict |
|---|---|---|
| Meta: "...a governed model registry on the roadmap" | M6-REPORT 6.1-6.6 pass; M6 merged (12eb802) | FIXED: "Built and tested internally; not deployed yet" |
| Lede: every run pinned to a pipeline version, records parameters, versions, input hashes | M3-REPORT 3.2 pass (PipelineVersion IDs, name@semver); 3.1 pass | OK |
| 2025 study: artifact correction reduced decoding, higher high-pass increased it | market/landscape.md §3 item 2, Kessler et al. 2025, doi 10.1038/s42003-025-08464-3 (A) | OK |
| 43 pipelines, no single best | market/landscape.md §3 item 2, Huang et al. 2025, doi 10.1111/psyp.70197 (A) | OK |
| 129 publications, code availability 20.9% | market/landscape.md §3 item 1, Peksa et al. 2026, doi 10.3390/s26175562 (A) | OK |
| Ingest: EEG, ECoG, microelectrode connectors in open formats; standard time-series storage | M2-REPORT 2.4, 2.5 (Zarr, encrypted) | OK (general description, no metric) |
| Open formats: "BIDS, EDF/BDF, NWB and XDF import, with validation on the way in", status designed + built pill | M2-REPORT 2.5 pass: EDF, BDF, BrainVision, XDF, BIDS round-trips and corrupt-file fuzz. **NWB round-trip and BIDS validation are CI-only (not run)** | FIXED: "EDF/BDF, BrainVision, XDF and BIDS import, with typed errors for corrupt files. NWB import is written but not yet tested." Status removed |
| Streaming: LSL input, status planned | M2-REPORT 2.7 pass (LSL outlet to inlet to server via pylsl); M4-REPORT 4.4 pass on one host, inter-host offset untested | UPGRADED: built-internal, source M2 step 2.7; body adds "tested on a single host" |
| Existing tools: MNE-Python, BrainFlow, BIDS/NWB tooling integrations, planned | M3 3.4 uses MNE internally; no BrainFlow work in any report | OK, stays planned |
| Pinned versions, built | M3-REPORT 3.2 pass | OK. Status "designed" removed |
| Provenance graph, raw recording to trained model, built | M3-REPORT 3.1 pass (lineage fuzz, tamper checks); M6 6.1 pass (model lineage reaches raw nodes) | OK. Status "designed" removed. FEATURE_STATUS_UPDATE cited only latency figures; the functional row is the evidence |
| Pipeline grids, planned | M3-REPORT 3.6 pass (sweep report with planted effect, every cell linked to run and provenance) | UPGRADED: built-internal, source M3 step 3.6 |
| Code sample: "Illustrative API, subject to change" | M4-REPORT 4.3: snippet runs as published, pinned to eeg-basic@1.0.0 | OK (conservative; the note is still true since nothing is published) |
| Registry body: "Governed model registry (roadmap)" | M6-REPORT 6.1-6.6 pass | FIXED: "built and tested internally but not deployed". Homepage keeps its own "(roadmap)" wording (frozen, pinned by content test) |
| Intended use and restrictions, status roadmap + built | M6-REPORT 6.2 pass; 6.6 console card shows restrictions (unit tests local) | OK as built. Status "roadmap" removed |
| Component disclosure, status roadmap + built | M6-REPORT 6.5 pass with a fixture SBOM locally; real CycloneDX SBOM is CI-only | OK as built (fixture-tested). Status "roadmap" removed |
| Clinical/assistive outputs likely device software | market/regulation.md §4 (A) | OK |

## /governance (`pages/governance.json`)

| Claim | Source | Verdict |
|---|---|---|
| Meta: "...Planned." | M5 5.1-5.8 pass; M6 6.2 pass; both merged | FIXED: "Built and tested internally; not deployed yet" |
| Four US states with neural-data provisions and dates | market/regulation.md §1 table (A; Montana A secondary to statute, statute text not opened) | OK |
| Definitions differ (CO/CA central or peripheral, CT central only, CA excludes inferred) | market/regulation.md §1 "The definitions do not agree" | OK |
| No neural-specific privacy tool found | market/landscape.md §3 item 4 | OK |
| Body: "Each capability below is planned. None is available yet." | contradicted six built pills | FIXED: "built and tested internally. None is deployed or available to customers yet." |
| Per-jurisdiction classification against CO, CA, CT **and Montana** | M5-REPORT 5.2 pass for CO/CA/CT. `rules/mt.yaml`: `predicate: null`, `review_status: unverified`, "reported as not evaluated" | FIXED: CO, CA, CT; "Montana is shown as not evaluated until its statute text is verified". Built, M5 5.2 |
| Versioned consent ledger, audit trail | M5-REPORT 5.3 pass (ledger immutable in the DB, chain verification, WORM anchor); 5.4 pass (consent scopes) | OK. Status "planned" removed |
| Deletion follows data into derivatives and models, flags retraining | M5-REPORT 5.5 pass; M6 6.3 pass | OK. Status removed |
| Limit-use flag: "Mark California SPI whose use a consumer has limited" | Code: `rules/ca.yaml` obligation `limit_use`; tests `services/platform/tests/governance/test_gov_rules.py:75`, `test_gov_policy.py:187` (flag present iff CA matched), the M5 5.2 table-driven tests. The flag marks data **subject to** the right to limit; there is no record of a consumer's limit request | FIXED: "Flag data that counts as sensitive personal information in California, where consumers have the right to limit its use." Built, M5 5.2 |
| Model use restrictions (EU workplace/education emotion inference) | M6-REPORT 6.2 pass | OK. Status removed |
| Audit export: "classification, consent and deletion records", cited M5 5.8 | 5.8 is the FDA Evidence Kit (traceability, SBOM, PROV, SOUP), not these records. What exists: `GET /v1/audit/events` + `/audit/batches` (SEC-105, M2 "covered by local tests"); 5.1 audit events on classification changes; 5.5 audit events and a signed deletion certificate. No consent-record export found | FIXED: "Export the audit trail, including classification changes and deletion events, and signed deletion certificates". Source changed to M5 step 5.5 |
| EU AI Act Art. 5(1)(f), from 2 Feb 2025 | market/regulation.md §5 (B) | OK |

## /sdks (`pages/sdks.json`)

| Claim | Source | Verdict |
|---|---|---|
| Meta: "...with a C interface for C++ and game engines. Planned" | M4 merged (b0e5303), SDK 25 passed / 2 skipped; C ABI branches not merged | FIXED: Python SDK "built and tested internally"; C interface "planned" |
| Code sample, illustrative | M4-REPORT 4.3 | OK |
| Python SDK, status planned + built pill | M4-REPORT 4.2, 4.3 pass. Nothing published (M4: "no package uploaded"; wheels CI-only) | OK as built. Status removed; body adds "Not published yet." |
| C and C++: C interface, LSL and BrainFlow, planned | feature/c-abi and follow-ups not merged to main | OK, stays planned |
| Unity and Unreal: "Built when a customer needs them", roadmap | feature/engine-sdks not merged; C# bindings never compiled (web-copy handoff). The sentence was a commitment that no longer describes the plan | FIXED: "Planned, on the same C interface." Stays roadmap |
| MNE-Python ~308,000 PyPI downloads "a month in September 2026" | market/landscape.md §2 table: 308,276/month, pypistats "last month" fetched 2026-09-26 | FIXED to "in the month to 26 September 2026" (the window is not calendar September) |
| Licence: Apache-2.0 proposed, pending owner; hosted platform proprietary | web-copy commit c1b2f5a; owner decision pending | OK |
| "No SDK code is published yet" | M4: nothing published | OK |

## /pricing (`pages/pricing.json`)

| Claim | Source | Verdict |
|---|---|---|
| No final prices; nothing is an offer | no price exists anywhere in the repo | OK |
| Academic free; Startup usage-based; Enterprise custom (all planned) | market/pricing-and-gtm.md §2 "Recommended tiers (ESTIMATE, to test in discovery)" | OK: all planned, and the page shows none of the estimated prices |
| "BAA available for enterprise (planned)" | M5-REPORT 5.7: "website keeps 'BAA (planned)'" | OK |
| SSO, RBAC, single-tenant/on-prem/edge on the roadmap | plan only | OK, labelled planned/roadmap |
| Not collecting email until the privacy policy is published | M4-REPORT 4.7: early-access flag OFF, route not mounted; `legal/privacy.en.json` is `draft: true`; builds test: form disabled, no `action` | OK |

## BuildStatePill labels

| Item | Source | Verdict |
|---|---|---|
| en "Built, tested internally" | WEB-BOARD lead decision (label "Built, tested internally", never "available") | OK |
| no "Bygget, testet internt" | WEB-BOARD correction entry (proposed no label) | OK |
| Label rendered from `uiEn` on every page (`apps/web/src/components/PageBody.astro:43`) | no NO pages use PageBody yet | Not wrong today. Must switch to the page locale's ui before any NO inner page ships (task 2, web-a11y's file) |

## FEATURE_STATUS_UPDATE.md

`docs/hive/FEATURE_STATUS_UPDATE.md` is superseded by this file. Its errors:
- "designed/planned/roadmap → **built**": no "built" status exists; the lead decision is a separate `buildState` pill.
- Open formats: omits that NWB and BIDS validation are CI-only.
- Limit-use and audit-export rows cite evidence that does not show those features (5.2 text; 5.8 is the FDA kit).
- Montana is not evaluated by the classifier.
- "Status: COMPLETE" and "25 tests pass" are stale.
A superseded notice was added at its top; the body is left as the historical record.

## Addendum 2026-09-27: web-investor-2 audit fixes (branch web/copy-audit-fixes)

Source: `neuro-worktrees/web-investor-AUDIT-inner-pages.md`. Each fix is mirrored in the unpublished `*.no.json` twins.

| # | Page | Fix | Source |
|---|---|---|---|
| P1 | /pricing | Free tier is for individual researchers and students. Labs and core facilities are "planned for a separate paid plan; pricing at launch". Meta and hero changed to match. No price shown | investor/PRICING.md §3.1-3.2; market/pricing-and-gtm.md §2 |
| P2 | /pricing | Not changed: three vs five tiers is the lead's decision | - |
| P3 | /pricing | "Startup: banded subscription", priced in bands of data subjects and devices | investor/PRICING.md §3.3 |
| P4 | /pricing | "edge" removed; "single-tenant or on-prem" kept | pricing-and-gtm.md §2; BLUEPRINT |
| P5 | /pricing | "pipeline grids" removed from Startup (sources put multiverse audits in Growth) | pricing-and-gtm.md §2 |
| PL1 | /platform | Device-software row is now labelled "Our planning assumption, not legal advice" and has no grade | market/regulation.md §4 |
| PL2 | /platform | LSL buildSource adds M4 step 4.4 (the single-host caveat) | M4-REPORT 4.4 |
| PL3 | /platform | Provenance buildSource adds M6 step 6.1 (model end of the lineage) | M6-REPORT 6.1 |
| G1 | /governance | "Three US states ...; a peer-reviewed review reports a fourth (Montana)". Montana moved to its own ungraded evidence row that says the statute text is unchecked | market/regulation.md §1; rules/mt.yaml |
| G2 | /governance | Limit-use cites `services/platform/tests/governance/test_gov_rules.py`; audit export cites `.../test_gov_audit_integrity.py` | code + tests |
| G3 | /governance | Heading changed to "What the governance layer is built to do." | - |

buildSource may now hold several sources joined by "; ". The first must be an M-report step, and each later one is either
a report step or an existing repo test file. The content test enforces both.

Open, not changed here: `docs/adr/0006-licensing.md` is **Accepted** (owner, GATE B: Apache-2.0 for SDK/core, repo
all-rights-reserved until the SDK ships). The pages still say "Apache-2.0 proposed, pending the owner's decision"
per the lead's earlier ruling (WEB-BOARD). The lead should confirm which one stands.
