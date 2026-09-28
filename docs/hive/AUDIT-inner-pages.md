# Read-only claims audit: /platform, /governance, /security, /pricing (EN)

By web-investor-2, 2026-09-27, against main 9b96a80. No files edited. Format: page | claim | source | verdict.
Severity: HIGH = wrong or unsourced public claim; MED = claim/source mismatch or a stale status; LOW = cite precision.

## Findings

| # | Sev | Page | Claim on page | Source checked | Verdict |
|---|---|---|---|---|---|
| P1 | HIGH | /pricing | "Academic: free. For labs and students doing research…"; meta "Free for academic research" | investor/PRICING.md §3.1–3.2; market/pricing-and-gtm.md §2 | CONFLICT: the free tier (Open Core, $0) is for individual researchers and students. Labs and core facilities are a separate paid Lab/Institution tier (ESTIMATE $3k–$10k/yr). The page promises labs a free tier that the pricing docs don't have. |
| S1 | MED | /security | Rows marked "designed" (legend: "specified in our architecture, not yet built"): encryption at rest with per-subject keys; deletion with key destruction and a signed certificate; admin phishing-resistant sign-in; tenant separation; tamper-evident audit log | M2-REPORT 2.1, 2.2, 2.3, 2.8; M5-REPORT 5.5 | STALE: these are built and tested internally (not deployed). /platform and /governance label the same capabilities "Built, tested internally". The labels now understate and contradict the other pages. Owner-reviewed copy (nfb-security), so nfb-security decides. |
| G1 | MED | /governance | Body: "Four US states have added neural data to the sensitive data their privacy laws protect" | market/regulation.md §1 | OVERSTATED: Montana's statute text was not opened; the source is a peer-reviewed review (A, secondary to the statute), and rules/mt.yaml marks it unverified. Suggest "Three US states have…, and a peer-reviewed review reports a fourth (Montana)", as on /investors. The evidence row also grades the Montana date A without the "secondary" caveat. |
| PL1 | MED | /platform | Evidence: "Outputs that drive a clinical or assistive BCI are likely device software in the customer's product…", grade A | market/regulation.md §4 | GRADE: §4 labels this bullet a "planning assumption, not legal advice". The A grade belongs to the FDA page, not to our inference. Suggest dropping the grade or quoting the FDA fact itself. |
| P2 | MED | /pricing | "Three tiers, one platform": Academic / Startup / Enterprise | investor/PRICING.md §3; pricing-and-gtm.md §2 | MISMATCH: the sources define five tiers plus services (Open Core, Lab/Institution, Startup, Growth, Enterprise/Pharma). Lab and Growth are missing from the page. |
| P3 | LOW | /pricing | "Startup: usage-based" | investor/PRICING.md §3.3 | IMPRECISE: the source has a monthly subscription (ESTIMATE $300–$800/mo, billed annually) in bands of data subjects + devices; the value metric is banded, not metered usage. |
| P4 | LOW | /pricing | Enterprise: "single-tenant, on-prem or edge deployment on the roadmap" | pricing-and-gtm.md §2 (single-tenant/VPC); BLUEPRINT (self-host / MinIO on-prem) | "edge deployment": MISSING. No source found in investor/, market/ or architecture/. Single-tenant and on-prem are sourced. |
| P5 | LOW | /pricing | Startup includes "pipeline grids" | pricing-and-gtm.md §2 | Sources put multiverse audits (pipeline grids) in the Growth tier; Startup lists hosted pipelines, ledger, latency harness, SSO. |
| PL2 | LOW | /platform | "LSL input … tested on a single host", buildSource M2 step 2.7 | M2 2.7; M4 4.4 | The "one host" statement is in M4 step 4.4 ("pass on one host … two hosts: not tested"); M2 2.7 shows the LSL path but not the host caveat. Suggest citing M4 step 4.4. |
| PL3 | LOW | /platform | "Provenance graph … from raw recording to trained model", buildSource M3 step 3.1 | M3 3.1; M6 6.1 | The model end of the lineage is M6 step 6.1 (model version reaches every training subject's raw node); M3 3.1 covers the graph itself. |
| G2 | LOW | /governance | "Limit-use flag" (buildSource M5 5.2); "Audit export" (buildSource M5 5.5) | M5 5.2/5.5; rules/ca.yaml `limit_use`; services/platform governance tests; api/evidence_routes.py | Supported by code and tests, but the cited report steps don't name either feature. Cite precision only. |
| G3 | LOW | /governance | Heading "What the governance layer will do." over items labelled built | M5 | Tense mismatch (copy, not a number). |

## Verified OK (numbers, dates, named standards)

- /platform: Kessler 2025; Huang 2025 (43 pipelines); Peksa (129 publications, 20.9%); all DOIs appear in market/landscape.md §3. Formats EDF/BDF, BrainVision, XDF, BIDS (M2 2.5). "NWB import written but not yet tested" (M2: CI-only list). Pinned versions (M3 3.2), pipeline grids (M3 3.6), use restrictions (M6 6.2), component disclosure (M6 6.5). `eeg-basic@1.0.0` in the illustrative code is real (M4 4.3).
- /governance: CO effective 7 Aug 2024; CA Ch. 887, 28 Sep 2024; MT May 2025 (secondary, see G1); CT signed 24 Jun 2025, sections effective 1 Jul 2026; CO/CA/CT definitions; the "no neural-specific privacy tool" row (landscape §3, ungraded); EU AI Act Art. 5(1)(f) from 2 Feb 2025 (B, sourceUrl present in regulation.md). "Montana shown as not evaluated" matches rules/mt.yaml (predicate null, review_status unverified). Build steps 5.2, 5.3, 5.5, 6.2 exist.
- /security: every figure is in security/website-security-page.md (the owner-reviewed copy source), and each has an underlying source:
  - TLS 1.3; AES-256-GCM; passkeys for admins; Sigstore; CycloneDX; SLSA; VEX: SECURITY-REQUIREMENTS.md / STANDARDS-MAP.md
  - 24 hours to customer; 72-hour GDPR: INCIDENT-RESPONSE.md, LEGAL-HANDOFF.md
  - 3 business days: VULN-DISCLOSURE.md
  - OWASP ASVS 5.0 L2 with L3 for neural paths; NIST SP 800-218; NIST CSF 2.0; IEC 81001-5-1; GDPR Art. 32; EU CRA; ISO/IEC 27001 and 27701; SOC 2 Type II: STANDARDS-MAP.md
  - Yearly pen test: SEC-110
  - Quarterly recovery drills: SECURITY-REQUIREMENTS / STANDARDS-MAP
  - One US region at launch, EU planned: ADR 0004
  - Memory-safe core SDK: ADR 0007 (Rust nf-core)
  - "We test for that in every build" (no device control): hw-guard runs in lint (SEC-091)
- /pricing: no numbers on the page. "Python SDK (licence pending)" is consistent with ADR 0006 (Apache-2.0 decided, not applied until the SDK ships). "BAA (planned)" matches docs/compliance/README.md.

## Owners (for routing; I changed nothing)

/platform, /governance, /pricing content: packages/content/content/pages/*.json (web-copy lane). /security: security.en.json, nfb-security's owner-reviewed copy (security/website-security-page.md).
