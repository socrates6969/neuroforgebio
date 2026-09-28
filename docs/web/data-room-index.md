# Data-room index (investor-relevant repository documents)

Owner: web-investor-2. Compiled 2026-09-27 from main @f14c44c. Internal index; not published and not linked from the site.
Each description restates what the document says about itself (its status line or header). Paths are relative to
the repository root. Company status on that date: pre-release, nothing deployed, no customers, and the company
(a planned Norwegian AS) is not yet incorporated (`legal/commercial/msa.en.md` header).

Some planning documents were written on 2026-09-26, before modules M2 to M6 were built, and their status lines still
say "nothing is built". The build reports below take precedence for what exists; plan documents take precedence for
what is intended.

## 1. Company and plan

| Path | What it is |
|---|---|
| `README.md` | One-paragraph company description and folder map. Status line: "pre-product". |
| `BRIEF.md` | The owner's master brief (started 2026-09-26): the gated build plan and the rules agents follow. |
| `LICENSE` | Proprietary, all rights reserved (Marius Carlsson). |
| `investor/PITCH.md` | Investor pitch, text version. "DRAFT for owner review. Not sent to anyone." Financial figures are marked ESTIMATE. |
| `investor/PRICING.md` | Pricing tiers. Every price is an ESTIMATE until customer discovery; no customers, quotes or LOIs. |
| `investor/AI-ADVANTAGES.md` | What the AI layer would do for investors and its limits. The AI layer is designed, not built. |
| `docs/adr/` | Architecture decision records (0001 to 0011 and 0014), e.g. 0006 licensing (Apache-2.0 for SDK/core later, proprietary platform, Accepted) and 0010 order of external assurance spend (Accepted). |
| `architecture/DECISIONS.md` | The GATE B owner decisions (D1 to D10), each with a recommendation. |

## 2. Market and regulation (the sources for public claims)

The content tests only accept `market/*.md` and `research/` as sources for claims shown on the website.

| Path | What it is |
|---|---|
| `market/regulation.md` | Neural-data regulation map: US states, US federal, HIPAA, FDA, EU. Each row has a primary source and an evidence grade. "Not legal advice." Open items listed at the end (Montana statute text, MIND Act status). |
| `market/landscape.md` | Hardware makers, software tools, and the evidence-backed gaps (§3). Sources graded A to D, with notes on how each was accessed. |
| `market/sizing.md` | Funding figures that could be verified (§1) and TAM/SAM/SOM. Every derived number is labelled ESTIMATE. |
| `market/pricing-and-gtm.md` | Comparable vendor prices (grade D), proposed tiers (ESTIMATE, untested) and go-to-market sequencing (§5). |
| `market/validation.md` | Blueprint assumptions scored SUPPORTED / WEAK / CONTRADICTED against the opened sources. |

## 3. What is built: build reports (built and tested locally; nothing deployed; CI is dispatch-only)

| Path | What it is |
|---|---|
| `docs/hive/M1-REPORT.md` | M0 and M1: repository baseline and the website. The deploy/publish step (1.10) was not started; it is owner-gated. |
| `docs/hive/M2-REPORT.md` | Ingest and storage: encryption at rest, crypto-shredding, format round-trips, streaming with network cuts, audit hash chain. |
| `docs/hive/M3-REPORT.md` | Pipelines and provenance: signed lineage graph, reproducibility check, preprocessing sweeps, console. The public-data multiverse study is a scaffold only (step 3.9). |
| `docs/hive/M4-REPORT.md` | Public API and Python SDK: contract tests, SDK, quickstart blocks executed. Nothing published; no package uploaded. |
| `docs/hive/M5-REPORT.md` | Compliance ledger: jurisdiction classifier, append-only consent ledger, policy check on every data route, withdrawal end to end, law tracker, FDA Evidence Kit v0 ("scaffold, not a submission"). |
| `docs/hive/M6-REPORT.md` | Governed model registry: training-set manifests, EU AI Act use restrictions, retrain-on-withdrawal, SISA unlearning, SOUP/OTS export. |
| `docs/hive/M2-CONTRACTS.md`, `M3-CONTRACTS.md`, `M6-CONTRACTS.md` | Interface contracts the build workers coded against. |

## 4. Security

| Path | What it is |
|---|---|
| `SECURITY.md` | Security policy. "Nothing in this repository runs in production." Items marked *(owner)* need an owner action. |
| `security/THREAT-MODEL.md` | STRIDE + LINDDUN threat model, DRAFT v0.1, written against the design. Residual ratings are design targets, not measurements. |
| `security/SECURITY-REQUIREMENTS.md` | Testable requirements SEC-nnn, DRAFT v0.1, each with a verify line and owning build step. |
| `security/STANDARDS-MAP.md` | Security and compliance standards map, DRAFT. "Nothing here is built, audited or certified." Not legal or regulatory advice. |
| `security/M2-REVIEW.md` | Security review of M2: approved for synthetic/public data, subject to fixes F1 and F2 before any real subject data. |
| `docs/hive/INTEGRATE-SECURITY-FIXES.md` | Merge notes for the security-fix integration branch; status line "VERIFIED 2026-09-27" with one open item. |
| `docs/security/SEC-COVERAGE.md` | Which SEC requirements have local tests and which are CI-only (M0, M1 website, stimulation exclusion, M2-REVIEW fixes). |
| `docs/security/crypto-inventory.md` | Cryptography inventory (CBOM-style) for M2, draft for review; each row names the implementing file. |
| `docs/security/licences.md` | Licence policy for browser-shipped code (SEC-084), DRAFT v0.1. |
| `docs/security/branch-protection.md` | Code-host settings the owner applies. Status: NOT APPLIED. |
| `security/INCIDENT-RESPONSE.md` | Incident response plan, DRAFT policy v0.1, not yet adopted. Not legal advice. |
| `security/VULN-DISCLOSURE.md` | Vulnerability disclosure policy, DRAFT v0.1; safe-harbour wording awaits legal review. |
| `security/vex/README.md` | How VEX exceptions to the CI vulnerability gate are recorded (SEC-085). |

## 5. SBOM and supply chain

No SBOM file is committed. SBOMs are produced by `.github/workflows/ci.yml`, which runs only on manual dispatch:

| Path | What it is |
|---|---|
| `.github/workflows/ci.yml` | Generates a CycloneDX 1.6 SBOM per website theme bundle and a repository SBOM (JS + Python + Rust) (SEC-083). |
| `security/sbom-ci-images.json` | Container images the SBOM generator does not discover, added to the repository SBOM with pinned digests. |
| `tools/sbom-props/` | Adds and asserts support-level properties in the SBOMs; has its own tests. |
| `deny.toml` | cargo-deny configuration for Rust dependencies: advisories, licences, bans and sources. |

## 6. Compliance and legal drafts (all "DRAFT – not legal advice"; need review by a Norwegian lawyer before use)

| Path | What it is |
|---|---|
| `docs/compliance/README.md` | BAA-readiness pack, DRAFT for counsel review. No provider BAA is signed and no BAA of our own is offered; claims no HIPAA compliance. |
| `legal/commercial/` | Customer contract templates, EN + NO: MSA, DPA, SLA, BAA, AUP, order form, SDK licence, research-pool addendum. |
| `legal/data-agreements/CONSENT-SCOPES.en.md` | Legal-to-engineering mapping of the consent scopes the ledger enforces. |
| `legal/data-agreements/RETENTION-POLICY.en.md` | Data retention and deletion policy, version 0.1. |
| `legal/data-agreements/RISK-MEMO.md` | Risk memo on selling or licensing neural and biological data. |
| `legal/website/` | Privacy policy, terms of use, cookie statement and company information for the website. |

## 7. Website quality audits

| Path | What it is |
|---|---|
| `docs/hive/CLAIMS-AUDIT.md` | Audit of every number and factual statement on the live inner pages (main @7355277, 2026-09-27). |
| `docs/hive/INVESTOR-PAGE-SOURCES.md` | Claim-by-claim sources for the draft /investors page, including a list of removed claims. |
| `docs/hive/A11Y-AUDIT.md` | WCAG 2.2 AA audit of the inner pages in both themes. |
| `docs/hive/PERF-AUDIT.md` | Web performance audit; per-page numbers in `docs/web/perf-baseline.md`, budgets enforced by a test. |
| `docs/hive/HEADERS-MATRIX.md` | Security headers each host would send, generated from a local build. Nothing is deployed and no host is chosen. |

## Deliberately not indexed

Financing documents (`legal/financing/`, `investor/FUNDING-ROUND.md`, `investor/ROUND-ASSUMPTIONS.md`, the financial
model and dilution CSVs) are left out: the lead has ruled out fundraising content in the investor work, and using
them needs the owner.
