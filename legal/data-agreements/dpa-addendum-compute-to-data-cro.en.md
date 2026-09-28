> DRAFT – not legal advice. Must be reviewed by a Norwegian lawyer (advokat) before use.

# DPA Addendum A: Compute-to-Data (A1) and CRO / Pharma Endpoint Analytics (A12)

Version [0.1] · [DATE] · Addendum to the Data Processing Agreement (legal\commercial\dpa.en.md, "DPA") and the MSA.
Prevailing language: English [advokat choice] · Norwegian version: dpa-addendum-compute-to-data-cro.no.md

**Parties**
- **Customer (controller):** the data holder (A1), or the sponsor / CRO (A12).
- **Processor:** [NeuroForge Bio AS] (ASSUMPTION: Norwegian AS, **not yet incorporated**).
- Where the Customer is itself a processor (for example a CRO acting for a sponsor), NeuroForge is a sub-processor (DPA preamble).

**Order of precedence:** SCC (where used) > this Addendum > DPA > MSA, for the services named below.

## 1. Services covered
- **(A1) Compute-to-Data.** Customer Personal Data stays in Customer's tenant (or Customer's VPC deployment). Third-party analysts ("Analysts") approved by Customer submit versioned pipelines. The pipelines run where the data sits, and only outputs that pass the Output Release Policy leave the tenant.
- **(A12) CRO / Pharma Endpoint Analytics.** EEG/neural endpoint pipelines, robustness audits of endpoints and central-reading workflows, run on sponsor or trial data **for the Customer**.

## 2. Processor role only (both services)
2.1 NeuroForge acts **only as processor** on Customer's documented instructions (DPA § 3). The instructions for these services are: this Addendum, the approved pipeline list, and the Output Release Policy (Annex A1).
2.2 **No own purposes.** DPA § 3.4 and MSA § 4.3 apply without change. NeuroForge shall not:
- use Customer Personal Data or outputs for its own purposes, benchmarks, research pool or model training;
- sell, license or combine them;
- keep them after the service ends.
No consent-ledger `nf.*` scope (CONSENT-SCOPES) is ever applied to data under this Addendum.
2.3 **Analysts are not NeuroForge's sub-processors.** They are recipients chosen by Customer. Customer decides whether a release to an Analyst is lawful: whether it has its own basis and Art. 9(2) condition, the subjects' "sharing" scope, and any US "sale" rules. NeuroForge enforces Customer's release decisions technically.

## 3. Compute-to-Data safeguards (A1)
3.1 **Pipeline approval.** Only pipelines approved by Customer in the console may run.
- Pipelines are hashed and versioned. NeuroForge provides [static checks / sandboxing] against exfiltration (network egress blocked, file writes limited to the output area) [designed].
- A pipeline changed after approval needs re-approval.
3.2 **Output Release Policy (Annex A1).** Outputs leave the tenant only if they meet the Customer-set rules. Defaults:
- aggregates only;
- minimum cell size of [10] subjects;
- no row-level values, no subject pseudonyms, no raw or near-raw time series;
- model outputs limited to metrics and weights where Customer has approved weight release;
- optional differential-privacy noise with a stated budget.
3.3 **Analyst terms.** Customer must bind each Analyst (template clauses in Annex A2) to:
- no re-identification or linkage;
- use only for the stated study;
- AI Act Art. 5 bans, including emotion inference in workplace or education except for medical or safety reasons;
- no clinical decisions;
- no onward sale.
3.4 **Logging.** Every run, approval and release is written to the audit log (MSA Schedule 2 S6). Customer can export it.
3.5 **Anonymous outputs.** Where released outputs are anonymous in the sense of Recital 26 (no singling out by "means reasonably likely to be used"), they fall outside GDPR. **Customer, as controller, makes that assessment.** NeuroForge provides the release statistics that support it but gives no warranty that outputs are anonymous.

## 4. CRO / Pharma safeguards (A12)
4.1 **Trial approvals are Customer's.** Customer warrants that it has:
- the trial approvals and consents covering NeuroForge's processing (ethics / REK approval under helseforskningsloven § 9 where Norwegian health research; IRB/regulator elsewhere);
- clinical-trial law compliance (EU CTR / national law: **UNVERIFIED** in this draft).
4.2 **No PHI before a BAA.** Customer shall **not** upload Protected Health Information subject to HIPAA until a Business Associate Agreement between the Parties is signed. **NeuroForge's BAA is PLANNED, not available** (legal\commercial\baa.*). Until then, US covered-entity data must be de-identified by Customer before upload. Customer is responsible for the method (45 CFR 164.514: **UNVERIFIED**).
4.3 **No clinical claims.** Outputs are research and trial-analysis outputs. They are not diagnosis or treatment of any individual, and NeuroForge makes no clinical-validity claim (MSA § 10.1; AUP § 5).
4.4 **Part 11 / GCP.** Electronic-record controls needed for regulated trials (audit trail, e-signatures) are [designed / planned] and are not claimed as compliant. Customer must validate the system for its intended use.
4.5 **Blinding and data segregation.** Unblinded and blinded data, and different sponsors' data, are kept in separate workspaces. Access to them follows Customer's role mapping.

## 5. Security, breach, transfer, deletion
5.1 **Security.** DPA Annex II / MSA Schedule 2 (S1–S16) applies. These are designed/planned controls, and no certification is claimed. Encryption and pseudonymisation support GDPR Art. 32(1)(a): "the pseudonymisation and encryption of personal data" (verified text as quoted in security\STANDARDS-MAP.md §5.3).
5.2 **Breach.** NeuroForge notifies Customer "without undue delay" (Art. 33(2)), with a target of **[24] hours after confirmation**, so Customer can meet the controller's "72 hours" (Art. 33(1)) (DPA § 8).
5.3 **Transfers.** Processing happens in the hosting region in the Order Form: AWS US at launch, EU region planned (D4). Transfers follow DPA § 10. The SCC module choice for this service is [Module 2/3] [advokat].
5.4 **Deletion.** DPA § 11 applies. Pipeline containers and temporary files are destroyed after each run. Outputs held for Customer follow Customer's retention (RETENTION-POLICY row 1).

## 6. Audit and liability
DPA § 12 and § 14 apply. The data-protection super-cap (MSA § 12.3) applies. Breach of § 2.2 (use for own purposes) is uncapped [advokat choice].

---
### Annex A1 – Output Release Policy (Customer fills in)
| Setting | Default | Customer value |
|---|---|---|
| Minimum cell size (subjects) | [10] | [●] |
| Row-level output | Blocked | [●] |
| Subject pseudonyms in output | Blocked | [●] |
| Model weights release | Blocked unless approved per pipeline | [●] |
| DP noise / epsilon budget per Analyst per [period] | Off / [●] | [●] |
| Approvers (roles) | data-steward | [●] |

### Annex A2 – Clauses Customer must place in Analyst terms
1. No re-identification, linkage or contact of data subjects.
2. Use only for [study]. No onward sale or disclosure of row-level outputs.
3. No AI Act Art. 5 practices, including emotion inference in workplace or education except for medical or safety reasons. No clinical decisions.
4. Breach notice to Customer within [24] hours of becoming aware.
5. Deletion of outputs at study end, with a certificate.

## Hjemmel / Legal basis
- **GDPR official text** (Publications Office, http://publications.europa.eu/resource/celex/32016R0679, opened 2026-09-26): Recital 26; Art. 33(1). Art. 28(10) via Lovdata https://lovdata.no/lov/2018-06-15-38/gdpr/a28 (opened 2026-09-26).
- **GDPR Art. 32(1)(a) and 33(2):** verified text as quoted by nfb-security in C:\Users\mariu\neuro-company\security\STANDARDS-MAP.md §5.3 (source https://publications.europa.eu/resource/celex/32016R0679, opened by nfb-security 2026-09-26; reuse authorised).
- **AI Act Art. 5(1)(f):** official text, http://publications.europa.eu/resource/celex/32024R1689 (opened 2026-09-26).
- **Helseforskningsloven § 9:** https://lovdata.no/dokument/NL/lov/2008-06-20-44 (opened 2026-09-26).
- **UNVERIFIED:**
  - HIPAA 45 CFR 164.514 (hhs.gov 403; eCFR bot check);
  - EU Clinical Trials Regulation and 21 CFR Part 11;
  - SCC module choice.
- **Product and contract facts:** DPA §§ 3, 8, 10–14; MSA § 4.3, § 10.1, § 12.3, Schedule 2; BAA marked PLANNED; BLUEPRINT §8; DECISIONS D4.
