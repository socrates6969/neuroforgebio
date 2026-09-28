# NeuroForge Bio: security and compliance standards map

Status: **DRAFT**, written 2026-09-26 by the security expert (STEP 4). Nothing here is built, audited or certified. Every control is labelled **designed** (specified in `architecture\BLUEPRINT.md` or in this folder), **planned** (a build step exists in `architecture\BUILD-GUIDE.md` or in `SECURITY-REQUIREMENTS.md`), or **roadmap** (needs owner spend, an external party, or customer pull).

> Not legal or regulatory advice. Counsel and a regulatory consultant must confirm every applicability call below before anyone relies on it (DECISIONS.md D10). The company is assumed to become a Norwegian AS (`legal\BOARD.md`), which is not yet incorporated.

Companion files: `THREAT-MODEL.md`, `SECURITY-REQUIREMENTS.md` (the IDs `SEC-nnn` used below), `INCIDENT-RESPONSE.md`, `VULN-DISCLOSURE.md`, `website-security-page.md`.

**Evidence convention.** "Opened" means the primary text was fetched on 2026-09-26 and the quoted words were read. **UNVERIFIED** means the source could not be opened, so the statement relies on general knowledge and must be checked. The source list is in §9.

---

## 0. Summary: what applies, and our posture

| # | Standard / law | Applies to NeuroForge Bio? | Our posture | Status |
|---|---|---|---|---|
| 1 | OWASP ASVS 5.0.0 | Voluntary; the verification yardstick for platform, console, API and website | **Target L2 for everything, plus selected L3 chapters for neural-data paths** (§1.1) | designed |
| 2 | OWASP Top 10:2025 | Voluntary awareness list | Mapped to controls (§1.2) | designed |
| 3 | OWASP API Security Top 10:2023 | Voluntary; the API is the product | Mapped to controls (§1.3) | designed |
| 4 | NIST SSDF (SP 800-218 v1.1) | Voluntary; US federal buyers and FDA-adjacent customers expect it | Practice groups PO/PS/PW/RV mapped (§2.1) | designed |
| 5 | NIST CSF 2.0 | Voluntary; used as the organisation-level programme frame | Six Functions mapped (§2.2) | designed |
| 6 | ISO/IEC 27001:2022 | Voluntary certification; enterprise buyers ask for it | ISMS built to it from day one; certification is **roadmap** | roadmap |
| 7 | ISO/IEC 27701:2025 | Voluntary privacy extension | **Roadmap**, after 27001 | roadmap |
| 8 | SOC 2 Type II | Voluntary attestation; US buyers ask for it | **Roadmap** (D10: starts when 2–3 design partners ask) | roadmap |
| 9 | IEC 62304 | Applies to **customers'** device software; applies to us only if we market components as SOUP for devices | Lifecycle for SOUP-candidate components (§4.1) | planned |
| 10 | IEC 81001-5-1:2021 | Health-software security lifecycle; named by FDA as a possible SPDF framework | Adopt as our secure lifecycle for SOUP-candidate components (§4.2) | planned |
| 11 | FDA premarket cybersecurity guidance (final, 3 Feb 2026) | Binds **customers'** device submissions; we supply the evidence they need (SBOM, support levels, vulnerability status) | Evidence Kit + SBOM with FDA's extra fields (§4.3) | planned |
| 12 | EU Cyber Resilience Act (Reg. 2024/2847) | **Likely applies** to our SDKs and nf-core once made available on the EU market in a commercial activity, and possibly to the API as their "remote data processing solution" | CRA readiness track (§5.1); **reporting obligations have applied since 11 Sep 2026** | planned |
| 13 | NIS2 (Dir. 2022/2555) | **Probably not us** while we are below the medium-sized ceiling; **yes for many customers** (hospitals, device makers), who will push supply-chain clauses to us | Supplier-ready controls (§5.2) | designed |
| 14 | GDPR Art. 32 / 33 / 34 | **Applies** (EEA company, special-category data) | Art. 32(1)(a)–(d) mapped (§5.3) | designed |
| 15 | EU MDR Annex I §17 | Binds **customers** whose products are devices; we supply §17.4-style minimum IT-security requirements | "Customer security requirements" sheet (§5.4) | planned |
| 16 | HIPAA Security Rule (45 CFR 164.312) | Only when we act as a business associate of a covered entity | Technical safeguards designed in; BAA **planned** (§6) | designed / planned |
| 17 | US state neural-data laws (CO, CA, CT, MT) | Yes, for US subjects' data | Classification engine; legal owns interpretation (`market\regulation.md`) | designed |
| 18 | SLSA v1.2 | Voluntary supply-chain framework | **Build L2 at M0, Build L3 target at M4** (§7.1) | planned |
| 19 | CycloneDX (ECMA-424) SBOM | De facto format; FDA "encourages industry-accepted formats"; CRA requires a "machine-readable" SBOM | CycloneDX 1.6+ JSON per release (§7.2) | planned |
| 20 | RFC 9116 security.txt | Voluntary; FDA and CRA both expect a disclosure channel | Draft in `VULN-DISCLOSURE.md` | planned |

**Out of scope, by design, and it must stay that way.** The platform, SDKs and API never command, configure or trigger **stimulation** or any other actuator. They are read-only toward acquisition hardware (BLUEPRINT §1 "Out of scope"; `SEC-090`–`SEC-094`). This one design rule keeps us outside the most dangerous class of BCI threat. It also keeps the "non-device software function" posture (`market\regulation.md` §4) believable.

---

## 1. OWASP application-security standards

### 1.1 ASVS 5.0.0: target level and why

**Verified facts** (github.com/OWASP/ASVS README; `5.0/en/0x03-What-is-the-ASVS.md`, opened):
- The current stable release is **5.0.0, dated May 2025**.
- L1 is "the minimum requirements … around 20% of the ASVS requirements".
- L2: "**Most applications should be striving to achieve this level of security.** Around 50% of the requirements in the ASVS are L2", so compliance with L2 means about 70% of all requirements.
- L3 "should be the goal for applications looking to demonstrate the highest levels of security", mostly "defense-in-depth mechanisms or other useful but hard-to-implement controls".
- ASVS asks organisations to choose "depending on the sensitivity of the application". Its own example: "a bank may have difficulty justifying anything less than Level 3".

**Decision (recommendation): ASVS 5.0 Level 2 as the release gate for every internet-facing component, plus Level 3 for the chapters that guard neural data.**

| Component | Target | Reasoning |
|---|---|---|
| Platform API, gRPC ingest, console | **L2 + L3 in V8 Authorization, V11 Cryptography, V14 Data Protection, V16 Security Logging** | Neural data is special-category personal data under GDPR Art. 9 when health-revealing or used to identify people (`market\regulation.md` §5), and "sensitive data" under CO/CA/CT law. Our buyers sell into FDA- and MDR-regulated products. A breach is not reversible: you cannot rotate a brain. That is bank-grade sensitivity for the data paths. For the whole application, L3 is not affordable for a seed-stage team, so the hard L3 controls go where the data is |
| Governance module (consent ledger, deletion, KMS wrapper) | **L3 in full** for those modules | They are the product's promise. A defect there turns into a false deletion certificate |
| Marketing website (static) | **L1 + the V3 Web Frontend Security header controls at L2** | No login, no data, no third-party scripts (D9). The only form (early access, M4.7) is covered by L2 V2 business-logic and rate-limit requirements |
| SDKs (nf-core, Python, C++) | ASVS is not a native fit. Use **L2 V1 Encoding, V5 File Handling, V11, V12** where applicable, plus fuzzing (`SEC-060`) | They parse untrusted files and network input on customer machines |

**Verification method (planned):** a tailored ASVS checklist (ASVS itself recommends forking and "omitting irrelevant sections", e.g. WebRTC V17) lives in `docs/security/asvs-5.0-tailored.csv`. Each row points to a test or an evidence file. It is re-run before each milestone exit and before each pen test (`SEC-110`). **We never claim "ASVS compliant" in marketing.** ASVS is a verification standard, not a certificate.

### 1.2 OWASP Top 10:2025 → controls

Categories as listed on top10.owasp.org/2025 (opened).

| ID | Category | Primary controls (see `SECURITY-REQUIREMENTS.md`) |
|---|---|---|
| A01:2025 | Broken Access Control | Central `authorize()` + `policy.check()`; RLS; authz matrix tests (SEC-020…026) |
| A02:2025 | Security Misconfiguration | IaC-only infra, CIS-style baselines, header tests, no default creds (SEC-070…079, SEC-150…159) |
| A03:2025 | Software Supply Chain Failures | Lockfiles, pinned digests, SBOM, SLSA provenance, cosign (SEC-080…089) |
| A04:2025 | Cryptographic Failures | TLS 1.3, AES-256-GCM envelope encryption, KMS, rotation (SEC-030…039) |
| A05:2025 | Injection | Parameterised SQL, schema validation at every boundary, no shell-outs with user input (SEC-060…064) |
| A06:2025 | Insecure Design | This threat model; design review gate per milestone (SEC-001…003) |
| A07:2025 | Authentication Failures | Passkeys/WebAuthn for admins, OIDC, MFA, key hashing (SEC-010…017) |
| A08:2025 | Software or Data Integrity Failures | Hash chains, signed provenance batches, signed stream chunks, signed webhooks (SEC-040…046) |
| A09:2025 | Security Logging and Alerting Failures | Allow-listed logs, WORM audit, alert rules (SEC-100…106) |
| A10:2025 | Mishandling of Exceptional Conditions | Fail-closed policy function, RFC 9457 errors without internals, fuzzing (SEC-026, SEC-062) |

### 1.3 OWASP API Security Top 10:2023 → controls

IDs as listed on api-security.owasp.org (opened).

| ID | Risk | Control |
|---|---|---|
| API1:2023 | Broken Object Level Authorization | Every object lookup is tenant-scoped by RLS **and** checked by `policy.check`. Two-tenant tests on every route (SEC-021) |
| API2:2023 | Broken Authentication | OIDC, hashed scoped expiring keys, device-bound tokens, mTLS option (SEC-010…017) |
| API3:2023 | Broken Object Property Level Authorization | Response schemas are allow-lists. Governance fields (`classification`, `consent_scope`) are writable only by `data-steward` (SEC-022) |
| API4:2023 | Unrestricted Resource Consumption | Per-tenant quotas, gateway rate limits, max window size on `readWindow`, sweep-size caps (SEC-075) |
| API5:2023 | Broken Function Level Authorization | Role × endpoint matrix generated from OpenAPI, tested in CI (SEC-020) |
| API6:2023 | Unrestricted Access to Sensitive Business Flows | Exports and model deployments need a second approver by default (SEC-024) |
| API7:2023 | Server Side Request Forgery | Webhook targets and DANDI/OpenNeuro fetches go through an egress proxy with a deny-list for private and metadata IPs (SEC-076) |
| API8:2023 | Security Misconfiguration | See A02 |
| API9:2023 | Improper Inventory Management | OpenAPI is the source of truth, and undocumented routes fail CI (BUILD-GUIDE 4.1; SEC-077) |
| API10:2023 | Unsafe Consumption of APIs | IdP, KMS and archive responses are schema-validated, with timeouts and TLS verification (SEC-078) |

---

## 2. NIST frameworks

### 2.1 NIST SSDF, SP 800-218 v1.1 (Feb 2022)

Verified: title "Secure Software Development Framework (SSDF) Version 1.1", Feb 2022 (csrc.nist.gov/pubs/sp/800/218/final, opened). The practice groups are **PO** Prepare the Organization, **PS** Protect the Software, **PW** Produce Well-Secured Software and **RV** Respond to Vulnerabilities (csrc.nist.gov/projects/ssdf, opened). Companion SP 800-218A (the generative-AI profile) exists (same page). It matters for us only if we ship generative models, and we do not plan to.

| Group | How we meet it | Evidence artefact | Status |
|---|---|---|---|
| PO | Security roles in BUILD-GUIDE role table; this standards map; security requirements with IDs; toolchain pinning (0.1); CI gates (0.2, 0.3) | `SECURITY-REQUIREMENTS.md`, CI config | designed |
| PS | Branch protection with signed commits; least-privilege CI tokens; signed releases (cosign); SLSA provenance; release archive retention | Rekor entries, provenance attestations | planned |
| PW | Threat model; secure defaults; code review (2 reviewers on security-labelled paths); SAST, SCA, fuzzing; reuse of maintained readers (MNE, pynwb) instead of new parsers | `THREAT-MODEL.md`, CI reports | planned |
| RV | `VULN-DISCLOSURE.md`; security.txt; triage SLA; VEX statements; root-cause reviews in the incident process | Advisory log, VEX docs | planned |

### 2.2 NIST CSF 2.0 (26 Feb 2024)

Verified: CSF 2.0 dated February 26, 2024, with Functions GOVERN (GV), IDENTIFY (ID), PROTECT (PR), DETECT (DE), RESPOND (RS), RECOVER (RC) (NIST CSWP 29 PDF, opened; text extracted locally).

| Function | Our programme element | Status |
|---|---|---|
| GOVERN | Owner is the accountable executive. A named security lead role. Risk register = `THREAT-MODEL.md` ratings, reviewed each milestone. Supplier inventory (cloud, IdP, CDN) with DPAs | designed |
| IDENTIFY | Asset inventory from IaC state + SBOM; data inventory from the classification engine (every channel labelled) | planned |
| PROTECT | Identity (SEC-010…), crypto (SEC-030…), secure SDLC (SEC-080…), training for every engineer with prod access | planned |
| DETECT | OpenTelemetry + security alert rules; audit-chain verification job; anomaly rules on stream ingest (SEC-100…106) | planned |
| RESPOND | `INCIDENT-RESPONSE.md` with GDPR/CRA/state clocks | designed |
| RECOVER | PITR, versioned objects, quarterly restore drills, crypto-shred-aware backup design (SEC-120…124) | planned |

---

## 3. ISO/IEC management systems and SOC 2 (all roadmap)

| Item | Verified facts | Plan | Status |
|---|---|---|---|
| **ISO/IEC 27001:2022** "Information security management systems", Edition 3, 2022 (iso.org/standard/27001, opened) | — | Run the ISMS the 27001 way from M0 (scope, risk assessment, Statement of Applicability against Annex A, internal audit), so certification later is an audit, not a rebuild. **Certification needs an accredited certification body and owner spend.** | roadmap |
| **ISO/IEC 27701:2025** "Information security, cybersecurity and privacy protection — Privacy information management systems — Requirements and guidance", Edition 2, published 2025-10 (iso.org/standard/27701, opened) | The 2025 title reads as a standalone PIMS requirements standard. Whether it can now be certified **without** 27001 is **UNVERIFIED** (the standard text was not opened) | After 27001; it is the natural frame for the GDPR controller/processor duties and the consent ledger | roadmap |
| **SOC 2 Type II** | The AICPA page (opened) confirms SOC reports cover "Security, Availability, Processing Integrity, Confidentiality, or Privacy". The Type 1 vs Type 2 distinction (point-in-time design vs operating effectiveness over a period) was **not on the page opened: UNVERIFIED** | Criteria in scope: Security, Availability, Confidentiality, and Privacy later. Readiness when 2–3 design partners ask (D10). Website says "SOC 2 Type II: on roadmap" until a report exists | roadmap |

**Copy rule (binding, from the copy-lint list):** never "ISO certified", "SOC 2 compliant", or "HIPAA-compliant".

---

## 4. Medical-device software standards (for customers who build devices)

Our product is designed as a **non-device** data function (`market\regulation.md` §4). These standards matter because (a) customers put nf-core, the pipeline step library or registry exports **into devices**, and (b) the "FDA Evidence Kit" (BUILD-GUIDE 5.8) sells evidence that fits these frameworks.

### 4.1 IEC 62304 (medical device software lifecycle): **UNVERIFIED**

iso.org/standard/38421 returned 403 and a bot challenge, so the text and edition status were **not opened**. The plan rests on the blueprint's assumption (§8.6) and must be confirmed by a regulatory consultant:
- The components we offer as SOUP (nf-core, the step library, registry SOUP exports) get a 62304-style lifecycle: plan, requirements, architecture, verification, configuration management, problem resolution.
- For each such component we publish what a device maker needs to treat it as SOUP: functional and performance requirements, known anomalies, version pinning and an SBOM (BUILD-GUIDE 6.5).
- **We do not assign customers' software safety classes.** That is the manufacturer's job.

### 4.2 IEC 81001-5-1:2021

Verified title: "Health software and health IT systems safety, effectiveness and security — Part 5-1: Security — Activities in the product life cycle", Edition 1, 2021 (iso.org/standard/76097, opened). FDA's Feb 2026 guidance names "IEC 81001-5-1" among the frameworks manufacturers may use as a Secure Product Development Framework (SPDF) that satisfies the QMSR (FDA guidance text, opened).

**Plan:** adopt 81001-5-1's activity structure as the security lifecycle for SOUP-candidate components. Its clause-level content was **not opened** (paywalled), so the mapping below is to activity *themes*, not clause numbers. A consultant verifies it.

| Lifecycle theme | Our artefact |
|---|---|
| Security risk management + threat modelling | `THREAT-MODEL.md`, per-release delta |
| Security requirements | `SECURITY-REQUIREMENTS.md` |
| Secure design / implementation | Design review gate; coding standards; SAST |
| Verification (incl. fuzzing, pen test) | SEC-060…064, SEC-110 |
| Release, SBOM, secure update | SEC-080…089 |
| Vulnerability handling, CVD, advisories | `VULN-DISCLOSURE.md` |

### 4.3 FDA "Cybersecurity in Medical Devices: Quality Management System Considerations and Content of Premarket Submissions"

**Verified from the full text (fda.gov/media/119933/download, opened; 64 pages extracted):**
- "Document issued on February 3, 2026". It supersedes the 27 Jun 2025 version. Docket FDA-2021-D-1158. Nonbinding recommendations.
- It "addresses FDA's recommendations regarding section 524B of the FD&C Act for cyber devices". A **cyber device** is one that "(1) includes software validated, installed, or authorized by the sponsor as a device or in a device; (2) has the ability to connect to the internet; and (3) contains any such technological characteristics … that could be vulnerable to cybersecurity threats".
- The security objectives are "Authenticity, which includes integrity; Authorization; Availability; Confidentiality; and Secure and timely updatability and patchability". They apply broadly, "including … devices containing artificial intelligence (AI) and **cloud-based services**".
- **SBOM:** "For cyber devices, an SBOM is required (see section 524B(b)(3))". Manufacturers "should provide machine-readable SBOMs consistent with the minimum elements" from NTIA. For each component they should also give "the software level of support … (e.g., the software is actively maintained, no longer maintained, abandoned)" and "the software component's end-of-support date". "Industry-accepted formats of SBOMs are encouraged".
- Known vulnerabilities must be identified, including those in "CISA's Known Exploited Vulnerabilities Catalog".
- Threat modelling is recommended "throughout the design process", with a rationale for the chosen method. The guidance cites the MDIC/MITRE Playbook for Threat Modeling Medical Devices.
- Security Architecture Views are expected in submissions.
- For cyber devices a postmarket plan "including coordinated vulnerability disclosure and related procedures" is required under 524B(b)(1). Its listed elements include CVD, a patch timeline, periodic security testing and customer communication.

**What that means for us (planned):**
1. Every release SBOM (CycloneDX) carries two extra properties per component: `nfb:supportLevel` and `nfb:endOfSupport` (SEC-083). The customer can then drop our SBOM into a 524B submission without rework.
2. Every release ships a **VEX** document that states the exploitability status of each known CVE in our components, including KEV-listed ones (SEC-085).
3. We publish a **supplier security package** per component: the threat-model extract, a security architecture view, the SBOM, the VEX and our CVD policy (the SOUP pack, BUILD-GUIDE 6.5).
4. Our CVD policy (`VULN-DISCLOSURE.md`) is written so a device maker can cite it in their own 524B(b)(1) plan.
5. **We never state that our components make a customer's device compliant.** The Evidence Kit is labelled "scaffold, not a submission" (BUILD-GUIDE 5.8).

The FDA BCI guidance (2021) and the 2023 premarket software guidance (Enhanced Documentation Level) are already summarised in `market\regulation.md` §4. They were not re-opened here.

---

## 5. EU and EEA law

> **EEA note (UNVERIFIED):** GDPR applies in Norway through the EEA Agreement. Whether and when the CRA and NIS2 have been incorporated into the EEA Agreement and Norwegian law was **not checked**. Our EU customers are directly bound either way, and our SDKs placed on the EU market fall under the CRA regardless of our seat. Legal (nfb-legal) to confirm.

### 5.1 Cyber Resilience Act, Regulation (EU) 2024/2847

**Verified (OJ L 2024/2847 of 20.11.2024; full text from publications.europa.eu, opened):**
- Art. 71(2): "This Regulation shall apply from **11 December 2027**. However, **Article 14 shall apply from 11 September 2026** and Chapter IV (Articles 35 to 51) shall apply from 11 June 2026."
- **Art. 14 reporting**, for an actively exploited vulnerability and for a severe incident:
  - an early warning "without undue delay and in any event **within 24 hours**";
  - a notification "**within 72 hours**";
  - a final report "within one month" after the incident notification. For vulnerabilities, the final report is due after a corrective measure is available.
- A "product with digital elements" is "a software or hardware product **and its remote data processing solutions**".
- Recitals (recital numbers not recorded): where an app "requires access to an application programming interface or to a database provided by means of a service developed by the manufacturer … the service falls within the scope of this Regulation as a remote data processing solution". A later recital adds that "Directive (EU) 2022/2555 applies to cloud computing services and cloud service models, such as Software as a Service (SaaS)", and that "websites that do not support the functionality of a product with digital elements" are out of scope.
- Medical devices: products "to which [Regulations (EU) 2017/745 or 2017/746] apply should not therefore be subject to this Regulation".
- Annex I Part II: manufacturers must identify components "including by drawing up a software bill of materials in a commonly used and machine-readable format covering at the very least the top-level dependencies".
- Support period: "the support period shall be at least five years" (with an exception for shorter expected use).
- Open-source software stewards get a "light-touch" regime. Free software "intended for commercial activities" is in view.

**Applicability analysis (for counsel to confirm):**
| Artefact | Likely CRA status | Why |
|---|---|---|
| `nf-core`, Python wheel, C/C++ SDK, Unity/Unreal packages | **In scope as products with digital elements** once made available on the EU market in the course of a commercial activity. Apache-2.0 licensing (D6) does not by itself take them out, because we monetise the platform they connect to | We are their manufacturer |
| Platform API used by the SDKs | **Possibly in scope** as the SDKs' "remote data processing solution" (the recital on apps that require "access to an application programming interface"). The rest of the hosted platform is SaaS → NIS2 territory, not CRA | Design the API to CRA Annex I security properties anyway |
| Marketing website | Out of scope ("websites that do not support the functionality of a product") | — |
| A customer's CE-marked medical device that embeds nf-core | The **device** falls under MDR, not CRA. Our separately placed component remains our CRA product | — |

**Consequences (planned):** the CRA track (SEC-083…089, SEC-130…134):
- a CE-conformity self-assessment before first EU commercial release (the default class, unless nf-core is in an Annex III category; **UNVERIFIED**, not checked);
- a 5-year default support period stated on every SDK release;
- an SBOM per release;
- Art. 14 24 h / 72 h / final-report procedures in `INCIDENT-RESPONSE.md` §6. **Art. 14 is already in application (since 11 Sep 2026).** It bites the day the first SDK is made available on the EU market commercially. No SDK has been released yet.

### 5.2 NIS2, Directive (EU) 2022/2555

**Verified (full text, opened):**
- Transposition by **17 October 2024**. Member States "shall apply those measures from 18 October 2024".
- **Size-cap:** it applies to Annex I/II entity types "which qualify as medium-sized enterprises … or exceed the ceilings for medium-sized enterprises". The Art. 2(2) exceptions regardless of size cover electronic-communications providers, trust services, TLD/DNS, sole providers and others. Cloud providers are **not** in the size-independent list we read.
- Annex I digital infrastructure includes "Cloud computing service providers". Annex II includes "Manufacture of medical devices and in vitro diagnostic medical devices".
- Art. 23 reporting: early warning "within 24 hours", notification "within 72 hours", final report "not later than one month".
- Art. 21(2)(d) requires "supply chain security, including security-related aspects concerning the relationships between each entity and its direct suppliers or service providers".

**Analysis:** as a start-up below the medium-sized ceiling we are **probably outside NIS2 directly**. We re-check when we pass 50 staff or €10 m turnover/balance sheet (the Recommendation 2003/361 thresholds, **UNVERIFIED**, not opened). Our **customers** (hospitals, device makers) are often in scope and must manage us as a supplier under Art. 21(2)(d). So we design to be an **easy NIS2 supplier**: a security annex in contracts; customer notification of a significant incident **without undue delay and at most 24 h** after we confirm it, which gives them a chance to meet their own 24 h early warning (this is tight, so the IR plan pre-drafts the notice); audit rights via reports; and SBOM access. Coordinated with nfb-legal.

### 5.3 GDPR Article 32 (and 33/34)

**Verified text (Reg. 2016/679, opened).** Art. 32(1) requires "appropriate technical and organisational measures to ensure a level of security appropriate to the risk, including inter alia as appropriate: (a) the pseudonymisation and encryption of personal data; (b) the ability to ensure the ongoing confidentiality, integrity, availability and resilience of processing systems and services; (c) the ability to restore the availability and access to personal data in a timely manner …; (d) a process for regularly testing, assessing and evaluating the effectiveness of technical and organisational measures". Art. 33(1): the controller notifies "without undue delay and, where feasible, not later than 72 hours after having become aware". Art. 33(2): "The processor shall notify the controller without undue delay".

| Art. 32(1) | Our measure | Status |
|---|---|---|
| (a) pseudonymisation + encryption | Subject pseudonyms only (no names in the platform by default); AES-256-GCM envelope encryption with per-subject keys; TLS 1.3 | designed |
| (b) confidentiality, integrity, availability, resilience | RBAC + RLS + policy function; hash chains; multi-AZ managed Postgres; SLOs | designed |
| (c) timely restore | PITR, object versioning, restore drills with measured RTO/RPO (SEC-120…124) | planned |
| (d) regular testing | CI security tests, yearly pen test, quarterly access review, ASVS re-verification (SEC-110…114) | planned / roadmap |

**Role:** for customer data we are usually a **processor**. Art. 33(2) means we tell the customer "without undue delay"; they own the 72 h clock. Our contractual commitment (proposed to nfb-legal) is **≤ 24 h** after confirmation of a personal-data breach (`INCIDENT-RESPONSE.md` §6). A DPIA template for customers is **planned** (neural data = special category, likely high risk).

### 5.4 EU MDR Annex I §17 (for customers)

**Verified text (Reg. 2017/745, opened):**
- §17.2: software "shall be developed and manufactured in accordance with the state of the art taking into account the principles of development life cycle, risk management, including information security, verification and validation".
- §17.4: "Manufacturers shall set out minimum requirements concerning hardware, IT networks characteristics and IT security measures, including protection against unauthorised access, necessary to run the software as intended".
- §18.8: devices shall "protect, as far as possible, against unauthorised access that could hamper the device from functioning as intended".

**Our support (planned):** for each SOUP-candidate component we publish a **"minimum operating-environment and IT-security requirements" sheet** (supported OS and toolchains, network ports, TLS requirements, key storage expectations, update channel). A device maker can then adopt it into their own §17.4 documentation. Our lifecycle evidence (§4.1–4.2) supports their §17.2 argument. MDCG 2019-16 (EU medical device cybersecurity guidance) was **not opened: UNVERIFIED.**

---

## 6. HIPAA Security Rule (only as a business associate)

Applicability is in `market\regulation.md` §3 and BLUEPRINT §8.5. **Verified technical safeguards, 45 CFR 164.312** (law.cornell.edu, opened; hhs.gov returned 403):

| §164.312 | Spec (R = required, A = addressable) | Our control | Status |
|---|---|---|---|
| (a) Access control | Unique user identification (R); emergency access procedure (R); automatic logoff (A); encryption/decryption (A) | OIDC unique IDs; break-glass role with alerting (SEC-025); 15-minute idle / 12 h absolute session limits (SEC-015); AES-256-GCM | designed |
| (b) Audit controls | — | WORM audit log, every read/export (SEC-100…) | designed |
| (c) Integrity | Mechanism to authenticate ePHI (A) | Content hashes, hash-chained batches, signed chunks | designed |
| (d) Person or entity authentication | — | OIDC + MFA; passkeys for admins; device tokens / mTLS | designed |
| (e) Transmission security | Integrity controls (A); encryption (A) | TLS 1.3 only, mTLS option; HSTS | designed |

Administrative and physical safeguards (§164.308/310: risk analysis, workforce training, contingency plan, BAAs) are **planned** as policy documents (BUILD-GUIDE 5.7). Physical safeguards are inherited from the cloud provider under its BAA.
**UNVERIFIED:** the status of HHS's proposed Security Rule update (NPRM, reportedly January 2025, which would make encryption and MFA effectively mandatory). federalregister.gov blocked us. We design as if it were final: encryption and MFA are already mandatory in our design.

**US state breach-notification laws** (all 50 states; timelines vary) are owned by nfb-legal. `INCIDENT-RESPONSE.md` §6 leaves a per-state timeline table for legal to fill. **UNVERIFIED here.**

---

## 7. Software supply chain

### 7.1 SLSA

Verified (slsa.dev, opened): **v1.2 is the current version**, with a **Build track** and a **Source track**. Build levels (v1.0 levels page): L0 none; **L1 "Provenance exists"**; **L2 "Hosted build platform"**, with signed provenance; **L3 "Hardened builds"**, which prevent run interference and secret exposure. Source-track level names were not on the pages opened: **UNVERIFIED.**

| Milestone | Target | How |
|---|---|---|
| M0 (0.2/0.3) | **Build L2** | All release builds on hosted CI; provenance generated and signed by the CI identity |
| M4 (first public wheel) | **Build L3** | Isolated, ephemeral builders; provenance produced by the platform, not by user steps; no long-lived secrets in build jobs (OIDC-federated publishing) |
| Source track | Protected branches, signed commits, 2-person review on `main`; map to Source-track levels after verification | planned |

### 7.2 SBOM: CycloneDX

Verified (cyclonedx.org, opened): the current spec is **CycloneDX 1.7 (2025-10-21)**, standardised as **ECMA-424**. It covers "software, hardware devices, machine learning models", with SBOM/SaaSBOM/HBOM varieties.

- **Format:** CycloneDX JSON, spec 1.6 or later (whatever the chosen generators emit; pin in CI).
- One SBOM per build artefact (wheel, container image, site bundle) plus an aggregated release SBOM.
- FDA extra fields (support level, end-of-support) as CycloneDX `properties` (§4.3).
- **ML-BOM for registry models** (weights hash, training-set manifest hash, pipeline digests). This is a natural fit for the governed registry (BLUEPRINT §3.7). Planned in M6.
- A **SaaSBOM** for the hosted platform's external services (IdP, KMS, CDN, observability). This is our NIS2 supplier story.
- SBOMs are attached to releases and signed with cosign as attestations.

### 7.3 Signing: Sigstore / cosign

Verified (docs.sigstore.dev, opened): cosign signs "containers, blobs, and attestations". Keyless mode uses OIDC, with "Fulcio issues short-lived certificates binding an ephemeral key to an OpenID Connect identity". The signing event is recorded in the Rekor transparency log, and "Artifact owners should monitor the log for their identity". Requirements SEC-081…082.

---

## 8. Post-quantum readiness (notes, not a claim)

Verified: **FIPS 203 (ML-KEM), published 13 Aug 2024**, with companions FIPS 204 and 205 (csrc.nist.gov/pubs/fips/203/final, opened). Neural data has a very long sensitivity lifetime ("harvest now, decrypt later" is a real concern for recordings that stay identifying for decades). So:
- **Crypto-agility is required (SEC-038):** algorithms are named in config and in every stored envelope header, never hard-coded.
- At-rest AES-256-GCM is considered adequate against known quantum attacks at the 256-bit key size. The **exposure is in key exchange (TLS)**. We prefer hybrid ML-KEM key exchange at the edge (CDN / load balancer) once our providers support it. Provider support was **not verified**.
- Signatures (cosign, provenance, deletion certificates) stay classical until the ecosystem (Sigstore, KMS) supports ML-DSA. Tracked as roadmap.

---

## 9. Sources opened (2026-09-26)

| Source | URL |
|---|---|
| OWASP ASVS repo (5.0.0, May 2025) | https://github.com/OWASP/ASVS |
| ASVS 5.0 "What is the ASVS" (levels) | https://raw.githubusercontent.com/OWASP/ASVS/master/5.0/en/0x03-What-is-the-ASVS.md |
| OWASP Top 10:2025 | https://top10.owasp.org/2025 |
| OWASP API Security Top 10:2023 | https://api-security.owasp.org/editions/2023/en/0x11-t10 |
| NIST SP 800-218 | https://csrc.nist.gov/pubs/sp/800/218/final |
| NIST SSDF project page | https://csrc.nist.gov/projects/ssdf |
| NIST CSF 2.0 (page + CSWP 29 PDF) | https://www.nist.gov/cyberframework ; https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf |
| NIST SP 800-63B-4 | https://pages.nist.gov/800-63-4/sp800-63b.html |
| FIPS 203 | https://csrc.nist.gov/pubs/fips/203/final |
| ISO/IEC 27001:2022 | https://www.iso.org/standard/27001 |
| ISO/IEC 27701:2025 | https://www.iso.org/standard/27701 |
| IEC 81001-5-1:2021 | https://www.iso.org/standard/76097.html |
| FDA cybersecurity guidance page + full text | https://www.fda.gov/regulatory-information/search-fda-guidance-documents/cybersecurity-medical-devices-quality-management-system-considerations-and-content-premarket ; https://www.fda.gov/media/119933/download |
| CRA, Reg. (EU) 2024/2847 (full text) | https://publications.europa.eu/resource/celex/32024R2847 (EUR-Lex returned an empty challenge page) |
| NIS2, Dir. (EU) 2022/2555 | https://publications.europa.eu/resource/celex/32022L2555 |
| GDPR, Reg. (EU) 2016/679 | https://publications.europa.eu/resource/celex/32016R0679 |
| MDR, Reg. (EU) 2017/745 | https://publications.europa.eu/resource/celex/32017R0745 |
| 45 CFR 164.312 | https://www.law.cornell.edu/cfr/text/45/164.312 |
| SLSA levels / v1.2 | https://slsa.dev/spec/v1.0/levels ; https://slsa.dev/spec/v1.2/ |
| CycloneDX | https://cyclonedx.org/specification/overview/ |
| Sigstore cosign | https://docs.sigstore.dev/cosign/signing/overview/ |
| RFC 9116 | https://www.rfc-editor.org/rfc/rfc9116 |
| HSTS preload requirements | https://hstspreload.org/ |
| AICPA SOC page | https://www.aicpa-cima.com/topic/audit-assurance/audit-and-assurance-greater-than-soc-2 |

**Could not open (UNVERIFIED):** IEC 62304 (iso.org 403), hhs.gov Security Rule pages (403), the federalregister.gov HIPAA NPRM, EUR-Lex HTML (empty; used the Publications Office copies instead), ISO/IEC 27701 and 81001-5-1 clause text (paywalled), MDCG 2019-16, SLSA Source-track level names, EEA incorporation of CRA/NIS2, SME thresholds of Recommendation 2003/361.
