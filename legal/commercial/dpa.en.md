> DRAFT – not legal advice. Must be reviewed by a Norwegian lawyer (advokat) before use.

# Schedule 3 – Data Processing Agreement (DPA) under GDPR Article 28

Part of the MSA (msa.en.md). Prevailing language: English [advokat choice]. In a conflict on personal-data matters this DPA prevails over the MSA; the SCC (if incorporated, § 10) prevail over this DPA.

**Controller:** [Customer] ("Customer"). **Processor:** [NeuroForge Bio AS] (ASSUMPTION: Norwegian AS, **not yet incorporated**), org.nr. [●] ("NeuroForge"). Where Customer is itself a processor for a third-party controller (e.g. a hardware company processing for a hospital), NeuroForge is a sub-processor and Customer passes on the obligations below.

## 1. Subject matter, duration, nature and purpose (Art. 28(3), first sentence)
Described in **Annex I**. Duration = MSA term + the retrieval/deletion period in § 11.

## 2. Map of Art. 28(3) requirements to this DPA
| GDPR Art. 28(3) | Requirement (summary) | Clause |
|---|---|---|
| (a) | Process only on documented instructions, incl. on transfers; inform controller of legal requirements to process otherwise | § 3 |
| (b) | Persons authorised to process are bound by confidentiality | § 4 |
| (c) | Take all measures required under Art. 32 | § 5, Annex II |
| (d) | Respect conditions in Art. 28(2) and (4) for engaging sub-processors | § 6, Annex III |
| (e) | Assist the controller with data-subject rights requests (Chapter III) | § 7 |
| (f) | Assist the controller with Art. 32–36 (security, breach notification, DPIA, prior consultation) | § 8, § 9 |
| (g) | Delete or return all personal data at end of services, at controller's choice, unless law requires storage | § 11 |
| (h) | Make available information to demonstrate compliance; allow and contribute to audits; inform controller if an instruction infringes law | § 12, § 3.3 |
| Art. 28(2)/(4) | Prior written authorisation; flow-down of equivalent obligations; processor liable for sub-processors | § 6 |
| Art. 33(2) | Processor notifies controller without undue delay after becoming aware of a breach | § 8 |
| Art. 44–46 | Transfers only with Chapter V safeguards | § 10 |

## 3. Instructions (Art. 28(3)(a))
3.1 NeuroForge processes Customer Personal Data only on Customer's documented instructions. The MSA, Order Form, this DPA and Customer's configuration and use of the Service (including consent scopes, retention and deletion policies set in the console/API) are Customer's complete documented instructions. Additional instructions must be in writing and, if they cause material extra cost, may be charged by agreement.
3.2 If EU/EEA or Member State law requires other processing, NeuroForge informs Customer before processing unless that law prohibits it.
3.3 NeuroForge shall immediately inform Customer if, in its opinion, an instruction infringes GDPR or other data-protection law (Art. 28(3) last subparagraph), and may suspend that instruction until confirmed or changed.
3.4 NeuroForge shall not: use Customer Personal Data for its own purposes; train models on it (MSA § 4.3); sell it; or combine it with other customers' data.

## 4. Confidentiality (Art. 28(3)(b))
Only personnel who need access to provide the Service get it, under written confidentiality undertakings or statutory duties that survive employment. Access is logged (Annex II S5).

## 5. Security (Art. 28(3)(c), Art. 32)
NeuroForge implements the measures in **Annex II** (= MSA Schedule 2 Security). They are **designed/planned controls**; no certification is claimed. Customer has assessed that they give a level of security appropriate to the risk of its processing, including Special Categories, and is responsible for its own controls (user management, device security, what data it uploads, pseudonymisation before upload where possible).

## 6. Sub-processors (Art. 28(2), (3)(d), (4))
6.1 Customer gives **general written authorisation** for the sub-processors in **Annex III**.
6.2 NeuroForge notifies Customer of any intended addition or replacement at least **[30] days** in advance [by email to the privacy contact and/or a subscribable list]. Customer may object on reasonable data-protection grounds within that period; the Parties discuss in good faith; if unresolved, Customer may terminate the affected Service with a pro-rata refund of prepaid unused Fees.
6.3 NeuroForge imposes on each sub-processor, by written contract, data-protection obligations providing at least equivalent protection (Art. 28(4)) and remains fully liable to Customer for their performance.

## 7. Data-subject rights (Art. 28(3)(e))
7.1 The Service is designed with tools for Customer to handle requests itself: export per subject, withdrawal and deletion propagation (§ 11.4), consent-ledger history, restriction via consent scopes, and the California "limit use" flag [designed/planned].
7.2 NeuroForge forwards to Customer without undue delay any request it receives directly and does not respond except to redirect, unless instructed.
7.3 Further assistance on request, at [reasonable cost] where beyond the Service's tools.

## 8. Personal-data breach (Art. 28(3)(f), Art. 33(2))
8.1 NeuroForge notifies Customer **without undue delay** after becoming aware of a personal-data breach affecting Customer Personal Data, and **in any event within [24] hours after confirmation** of the breach (NeuroForge investigates suspected breaches without undue delay and does not postpone confirmation to extend the period), so Customer can meet its own 72-hour deadline to notify the supervisory authority (Art. 33(1)).
8.2 The notice includes, as far as then known (Art. 33(3)): nature of the breach, categories and approximate number of data subjects and records, likely consequences, measures taken or proposed, and a contact point. Information may be given in phases.
8.3 NeuroForge takes reasonable steps to contain and remedy the breach, keeps a record, and does not notify authorities or data subjects on Customer's behalf unless instructed or legally required.
8.4 Notification is not an admission of fault.

## 9. DPIA and prior consultation (Art. 28(3)(f), Art. 35–36)
NeuroForge provides reasonable information about the Service (architecture, security, sub-processors, data flows) to support Customer's data-protection impact assessment – which Customer should expect to need for large-scale neural/health data – and any prior consultation with an authority.

## 10. International transfers (Art. 44–46)
10.1 NeuroForge processes and stores Customer Personal Data in the hosting region in the Order Form. **At launch the only region is AWS [US region]; an EU region is planned** (D4). Customers who require EEA-only storage should wait for the EU region or not upload personal data. The region is chosen **per tenant**; NeuroForge does not move or transfer Customer Personal Data outside the chosen region without Customer's documented instructions, except for remote access by the sub-processors and support personnel listed in Annex III under § 10.2 safeguards.
10.2 Where processing involves a transfer to a country without an adequacy decision, the Parties rely on the **Standard Contractual Clauses** adopted by Commission Implementing Decision (EU) 2021/914, which are incorporated by reference as follows [advokat to confirm module choice and whether SCC are appropriate where the importer is already subject to GDPR under Art. 3(2)]:
   - **Module 2 (controller → processor):** where an EEA Customer transfers to a NeuroForge entity outside the EEA [e.g. a future US affiliate].
   - **Module 3 (processor → processor):** between NeuroForge (EEA processor) and sub-processors outside the EEA (e.g. AWS US region), in NeuroForge's contracts with them. Customer authorises this.
   - **Module 4 (processor → controller):** where the Customer (controller) is outside the EEA and NeuroForge returns data to it.
   - SCC options: Clause 7 (docking) [included]; Clause 9 option 2 (general authorisation, [30] days' notice); Clause 11 optional redress [not selected]; Clause 13 supervisory authority: [Datatilsynet, Norway]; Clause 17 governing law: [Norwegian law]; Clause 18 forum: [Norwegian courts]. Annexes I–III of the SCC = Annexes I–III of this DPA.
10.3 NeuroForge maintains a transfer impact assessment for each non-EEA sub-processor [planned] and supports Customer's own assessment. [EU–US Data Privacy Framework certification of a US recipient may alternatively be relied on – **UNVERIFIED**.]

## 11. Return and deletion (Art. 28(3)(g)) – and honest limitations
11.1 At the end of the Service, Customer may export its data during the retrieval period (MSA § 15.2, [30] days). Then NeuroForge deletes Customer Personal Data from production within [30] days and makes backup copies unreadable by destroying tenant and subject keys (crypto-shredding), with backups expiring within [35] days (ESTIMATE). Retention required by EU/EEA or Member State law is excepted and kept confidential. Written confirmation on request.
11.2 **During the term**, when Customer records a withdrawal for a data subject, the Service's designed deletion workflow runs:
   - raw files, recordings and subject-only artefacts → deleted, subject data key destroyed;
   - aggregated artefacts mixing subjects → marked stale and re-run without the subject, or tombstoned, per Customer's policy;
   - **trained models → flagged `retrain_required`, new deployments blocked (configurable), owners notified, and retrained without the subject. No certified machine unlearning is offered or promised**; model weights trained before retraining may still reflect the subject until retrained and old versions deleted by Customer;
   - **exports already taken outside the platform (downloads, API pulls, shared datasets) cannot be recalled by NeuroForge**; they are listed for Customer's follow-up;
   - a signed deletion certificate lists each node and action. Target completion 24 h for ≤10k descendant nodes (ESTIMATE, not SLA-backed).

## 12. Information and audits (Art. 28(3)(h))
12.1 NeuroForge makes available the information necessary to demonstrate compliance with Art. 28: this DPA, Annex II, sub-processor list, a security questionnaire response [planned], a penetration-test summary under NDA once a test has been performed (roadmap), and third-party reports **when they exist** (SOC 2 Type II is on the roadmap; none exists today). Documents are the first means of audit.
12.2 If that is not sufficient (Art. 28(3)(h) requires the processor to allow and contribute to audits, including inspections), Customer (or an independent auditor bound by confidentiality, not a NeuroForge competitor) may audit once per [12] months on [30] days' notice, during business hours, without access to other customers' data, at Customer's cost; additional audits after a breach or on an authority's request. Audits of sub-processors (e.g. AWS) are satisfied by their published reports.

## 13. Special Categories and neural data (Art. 9)
13.1 Customer determines whether uploaded data are Special Categories (e.g. health data, biometric data processed to uniquely identify a person) and warrants a valid Art. 9(2) condition (e.g. explicit consent (a) or scientific research with safeguards (j) under Union/national law) and, where relevant, compliance with national research law [e.g. helseforskningsloven in Norway – **UNVERIFIED**].
13.2 Customer should pseudonymise before upload; the Service is designed to store subject pseudonyms, not direct identifiers. Customer shall not upload direct identifiers (names, national ID numbers) into signal or metadata fields except where needed and configured in dedicated protected fields [designed].
13.3 NeuroForge applies Annex II controls to all Customer Personal Data as if it were Special Category data.
13.4 **Neural data is not anonymous.** The Parties acknowledge that pseudonymised or de-identified neural recordings remain personal data because of re-identification risk (security\THREAT-MODEL.md P-03). Neither Party shall describe such data as "anonymised" in contracts, notices or marketing.

## 14. Liability
Governed by MSA § 12 (including the data-protection super-cap § 12.3), without prejudice to data subjects' rights under GDPR Art. 82.

## 15. Records and cooperation
NeuroForge keeps a record of processing activities as processor (Art. 30(2)) and cooperates with supervisory authorities on request (Art. 31).

---
## Annex I – Description of processing
| Item | Description |
|---|---|
| Data subjects | Research participants / study subjects; patients (only if Customer has a lawful basis; no PHI under HIPAA without a BAA); Customer's Authorised Users (account data) |
| Categories of personal data | Neural and physiological signals (EEG, ECoG, EMG, intracortical/microelectrode, etc.) and derived features; recording and device metadata; subject pseudonyms; consent records (document version/hash, scopes, timestamps, collector identity, evidence reference); demographic/phenotypic metadata supplied by Customer; model weights trained on the above; user account data (name, email, role, logs) |
| Special Categories | Possible: health data; biometric data if used for unique identification; data possibly revealing other Art. 9 categories. Customer to specify in the Order Form |
| Nature of processing | Hosting/storage, ingest and format conversion, processing pipelines, provenance tracking, consent-scope enforcement, jurisdiction classification, model training and registry functions at Customer's instruction, export, deletion, backup, support, security monitoring |
| Purpose | Providing the Service to Customer under the MSA |
| Duration / frequency | Continuous during the MSA term + retrieval/deletion period |
| Retention | As configured by Customer; deletion per § 11 |
| Location | [AWS US region] at launch; EU region planned |

## Annex II – Technical and organisational measures
= MSA Schedule 2 (Security), S1–S16 (msa.en.md). Designed/planned; no certification claimed.

Mapping to GDPR Art. 32(1) (Art. 32 text quoted by nfb-security from the official text, security\STANDARDS-MAP.md §5.3):
| Art. 32(1) | Measures (Schedule 2) | Status |
|---|---|---|
| (a) pseudonymisation and encryption | Subject pseudonyms, no names by default (DPA § 13.2); AES-256-GCM with per-subject keys; TLS 1.3 (S1–S3) | designed |
| (b) ongoing confidentiality, integrity, availability and resilience | Access control, tenant isolation, personnel access, hash-chained audit log, environments (S4–S6, S11) | designed |
| (c) timely restore of availability and access | Backup and recovery with RPO/RTO targets (S10) | planned |
| (d) regular testing, assessing and evaluating effectiveness | Security testing, vulnerability management, quarterly access review (S5, S8, S9) | planned / roadmap |

## Annex III – Authorised sub-processors (placeholder – to be completed before signature)
| Sub-processor | Service | Location of processing | Transfer mechanism |
|---|---|---|---|
| Amazon Web Services [EMEA SARL / Inc. – entity to confirm] | Cloud hosting, storage, KMS, managed Postgres | [US region, e.g. us-east-1]; [EU region – planned] | [SCC Module 3 via AWS DPA] / [DPF – **UNVERIFIED**] |
| [Managed identity provider, e.g. ●] | Authentication / SSO | [●] | [●] |
| [Managed observability provider] | Logs/metrics (no signal data or subject identifiers – Annex II S6) | [●] | [●] |
| [CDN provider] | Content delivery for console/static assets (no Customer Data at rest) [confirm] | [●] | [●] |
| [Email provider] | Transactional email (account notices) | [●] | [●] |
| [Support ticketing, if any] | Customer support | [●] | [●] |
| **Anthropic Ireland, Limited** (Dublin, Ireland – the contracting entity for EEA/UK/Swiss customers under Anthropic's Commercial Terms) – **PLANNED**, used only if the tenant enables the AI assistant (MSA § 4.6) | AI assistant inference via the Claude API | Location of processing **UNVERIFIED** (Anthropic's DPA does not state it); assume the United States unless Anthropic confirms otherwise | Anthropic DPA incorporates SCC 2021/914 **Module Two / Module Three** (Irish law); NeuroForge relies on Module Three (processor → sub-processor). EU–US DPF: not mentioned in Anthropic's DPA or privacy policy – do **not** rely on it (**UNVERIFIED**) |

**Anthropic – details (planned sub-processor; verified on Anthropic's pages 2026-09-26 unless marked):**
- *Data categories sent:* pseudonymised study/dataset descriptors, pipeline and provenance-graph metadata, channel classifications, and the user's question. **Never** raw neural signals, derived signal features, direct identifiers, free-text notes or per-subject clinical fields (server-side allow-list and redaction; legal\data-agreements\ai-assistant-memo.md § 6).
- *Training use:* Commercial Terms: "Anthropic may not train models on Customer Content from Services." Retention docs: "Retained data is never used for model training without your express permission."
- *Retention:* standard commercial policy – inputs and outputs deleted "within 30 days of receipt or generation". Exceptions: longer retention if agreed, legal requirements, and Usage Policy flags (inputs/outputs up to 2 years, classification scores up to 7 years). **Zero data retention (ZDR)** is available on request per organisation via Anthropic sales, for eligible features and models only (some models require 30-day retention). NeuroForge intends to request ZDR [planned]; until confirmed in contract, assume 30 days.
- *Breach notice to NeuroForge:* "without undue delay, but in any event within 48 hours" (Anthropic DPA). NeuroForge's own 24 h commitment to Customer (§ 8.1) runs from NeuroForge's confirmation [advokat: check the gap].
- *Sub-processor changes:* Anthropic gives notice before new sub-processors, with a 15-day objection period (Anthropic DPA). Anthropic's own sub-processor list (trust.anthropic.com/subprocessors) **could not be read** (JS page) – **UNVERIFIED**.
- *Deletion at end of contract:* within 30 days after termination, subject to legal-retention exceptions (Anthropic DPA).

## Hjemmel / Legal basis
- GDPR (EU) 2016/679 Art. 3(2), 9, 28, 30–36, 44–46, 82 – incorporated in Norwegian law by personopplysningsloven § 1: https://lovdata.no/dokument/NL/lov/2018-06-15-38 (opened 2026-09-26). EUR-Lex GDPR text failed to load (https://eur-lex.europa.eu/eli/reg/2016/679/oj, 2026-09-26) – the Art. 28(3) (a)–(h) mapping and Art. 33 wording are from drafter knowledge – **verbatim UNVERIFIED**, advokat to check against the official text.
- Commission Implementing Decision (EU) 2021/914 (SCC), modules and clause options – EUR-Lex failed to load (CELEX and ELI URLs) – **UNVERIFIED**.
- EU–US Data Privacy Framework – **UNVERIFIED**. Helseforskningsloven – **UNVERIFIED**.
- Product facts: architecture\BLUEPRINT.md §8.1–8.5 (keys, audit, consent ledger, deletion propagation, no certified unlearning, exports not recallable), DECISIONS.md D4 (AWS US first, EU planned).
- **Update 2026-09-26:** the official GDPR text was opened via http://publications.europa.eu/resource/celex/32016R0679 (XHTML, English). Verified: Recital 26; Art. 4(1), (5) and (15); Art. 9(1); Art. 28(2), 28(3)(a) and 28(4); Art. 33(2); Art. 44; Art. 46(2)(c). The rest of the Art. 28(3) mapping is still to be proof-read against that text.
- Anthropic (Annex III row): Commercial Terms https://www.anthropic.com/legal/commercial-terms (opened 2026-09-26; effective 17 Jun 2025); DPA https://www.anthropic.com/legal/data-processing-addendum (opened 2026-09-26; effective 24 Feb 2025); privacy policy https://www.anthropic.com/legal/privacy (opened 2026-09-26); commercial retention article https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data (opened 2026-09-26); API and data retention / ZDR https://platform.claude.com/docs/en/docs/build-with-claude/zero-data-retention (opened 2026-09-26). Sub-processor list https://trust.anthropic.com/subprocessors – not readable – **UNVERIFIED**.
