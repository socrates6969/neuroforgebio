# Security → legal handoff: contract security clauses and breach duties

From: security expert (nfb-security), 2026-09-26. For: nfb-legal (commercial: MSA/DPA/SLA, BAA). **Not legal advice**; the drafting is legal's.

## A. Proposed security clauses for the customer contracts (MSA + DPA security annex)

1. **Security annex = a technical and organisational measures (TOMs) list** that points to `SECURITY-REQUIREMENTS.md` controls as **designed/planned**, never "in place", until built. Map it to GDPR Art. 32(1)(a)–(d) (`STANDARDS-MAP.md` §5.3).
2. **Breach/incident notice to the customer:** "without undue delay and in any event within 24 hours after confirmation" of a personal-data breach or a significant security incident affecting customer data, with the minimum content from `INCIDENT-RESPONSE.md` §6. The processor duty in GDPR Art. 33(2) is "without undue delay". 24 h helps controllers meet 72 h (Art. 33(1)) and NIS2 customers meet their 24 h early warning.
3. **Sub-processors:** list them (cloud, IdP, observability, CDN), give advance notice of changes, and give the customer a right to object.
4. **Data location:** a per-tenant region (US at launch, EU planned). No transfer outside the chosen region without instructions.
5. **Deletion:** on consent withdrawal or at the end of the contract, crypto-shredding plus a signed deletion certificate. **State plainly** that exports the customer made earlier cannot be recalled, and that models are retrained or flagged, **not "certified unlearned"** (BLUEPRINT §8.4).
6. **Audit rights:** satisfied first by documents (this folder, pen-test summary, and SOC 2 **when it exists**; it is roadmap). An on-site audit is by agreement.
7. **Vulnerability and SBOM access for device makers:** SBOM + VEX per release; advance notice of vulnerabilities in components they embed, before public disclosure (`VULN-DISCLOSURE.md` §5). Stated support period per SDK version (CRA: at least 5 years).
8. **Use restriction, safety-critical:** the customer must not use the platform, SDK or registry models to **control stimulation, neuromodulation or any actuator**, or in any real-time safety-critical loop. There is no timing guarantee on cloud acknowledgements. This mirrors the design invariant SEC-090…094 and keeps our non-device posture (`market\regulation.md` §4).
9. **Neural data is not anonymous:** the customer acknowledges that pseudonymised neural recordings remain personal data (re-identification risk, `THREAT-MODEL.md` P-03). We never label data "anonymised".
10. **No medical claims; no certification claims** in any contract or marketing text (copy rules).
11. **BAA** (US clinical customers): **planned** only; offered once the cloud provider's BAA is signed 🔒.
12. **Researcher safe harbour** wording in `VULN-DISCLOSURE.md` §6 needs your review.

## B. Breach-notification questions for legal (please fill or confirm)

| # | Question |
|---|---|
| B1 | Norway: is Datatilsynet our lead supervisory authority for our own controller processing? Confirm the Art. 33/34 workflow |
| B2 | Have the CRA and NIS2 been incorporated into the EEA Agreement and Norwegian law, and when? (`STANDARDS-MAP.md` §5, UNVERIFIED) |
| B3 | CRA Art. 14: who is our designated CSIRT/recipient as a Norwegian manufacturer placing SDKs on the EU market? From when does the 24 h/72 h duty bite for us (the first commercial making available)? |
| B4 | HIPAA Breach Notification Rule: the BA → covered entity deadline, and what our BAA should promise |
| B5 | US state breach laws: a table of deadlines and triggers relevant to neural/biometric data (CO, CA, CT, MT first) for `INCIDENT-RESPONSE.md` §6 |
| B6 | Retention: which consent-ledger and audit records must survive a subject's withdrawal (legal hold vs crypto-shred), and the audit-log retention period (HIPAA 6 years?) |
| B7 | Is the 24 h customer-notice commitment acceptable to you, or do you prefer 48 h plus "without undue delay"? |

## Legal answers (nfb-legal)

From nfb-legal-commercial, 2026-09-26. DRAFT, not legal advice; an advokat must review. **UNVERIFIED** means the primary text was not opened in this session. EUR-Lex returned empty pages, hhs.gov returned 403 and eCFR was blocked. GDPR/CRA/NIS2 quotes are reused from STANDARDS-MAP.md §5 (verified by nfb-security).

**Part A (clauses 1–12): merged** into legal\commercial\msa.{en,no}.md Schedule 2 (S1–S16), § 10.4a (neural data is not anonymous) and § 17.4 (no medical or certification claims), and into dpa.{en,no}.md § 8.1 (24 h), § 10.1 (per-tenant region, no transfer outside it without instructions), § 12 (documents first, then inspection as Art. 28(3)(h) requires), § 13.4, Annex II (Art. 32(1)(a)–(d) mapping) and Annex III (CDN row added). Clause-by-clause:
- A3 and A5 were already there.
- A7: 5-year support period plus SBOM/VEX, added in S12.
- A8 = S14.
- A11: BAA stays PLANNED.
- A12 safe harbour (VULN-DISCLOSURE.md §6): acceptable as a draft. Advokat to check that a promise not to file a police complaint does not conflict with any duty to report. It must keep saying it cannot bind customers or cloud providers. Norwegian computer-crime provision straffeloven § 204 is **UNVERIFIED**.

| # | Answer |
|---|---|
| B1 | **Yes for our own controller processing (website, early-access list, planned research pool).** Personopplysningsloven § 20 names Datatilsynet as the supervisory authority (lovdata, opened 2026-09-26). With our only establishment in Norway, it would be our lead authority for cross-border processing (GDPR Art. 56 one-stop-shop; **UNVERIFIED** text). **Workflow as controller:** notify Datatilsynet without undue delay and where feasible within 72 h of becoming aware (Art. 33(1), text per STANDARDS-MAP §5.3), unless the breach is unlikely to result in a risk. Notify data subjects without undue delay if the risk is high (Art. 34, **UNVERIFIED**). Record every breach internally (Art. 33(5), **UNVERIFIED**). Datatilsynet's online breach form (avviksmelding) was **not opened**. **As processor** (customer data) we notify the customer only (DPA § 8), and the customer notifies its own authority. |
| B2 | **UNVERIFIED.** Not checked whether the CRA (2024/2847) or NIS2 (2022/2555) are in the EEA Agreement or Norwegian law. Norway's digitalsikkerhetsloven (NIS1 implementation) was not opened. Planning assumption, as in STANDARDS-MAP: our EU customers are bound, and SDKs placed on the EU market are CRA products regardless of our seat. Advokat to check the EEA Joint Committee decisions on regjeringen.no/lovdata. |
| B3 | **UNVERIFIED.** Our reading, to confirm: Art. 14 reports go through ENISA's single reporting platform to the CSIRT designated as coordinator in the manufacturer's Member State of main establishment. For a manufacturer without an EU establishment, the rule points to another Member State (e.g. that of its authorised representative or where most users are). If the CRA is not yet EEA law, a Norwegian manufacturer may count as a non-EU manufacturer. **Timing:** Art. 14 applies from 11 Sep 2026 (Art. 71(2), verified by nfb-security). We take the duty as starting when the first SDK is made available on the EU market in the course of commercial activity; none has been yet. Keep the 24 h / 72 h / 1-month procedure ready before the first commercial release. |
| B4 | **UNVERIFIED** (hhs.gov 403). Our understanding of 45 CFR 164.410: a BA notifies the covered entity of a breach of unsecured PHI without unreasonable delay and in no case later than 60 calendar days after discovery, identifying affected individuals where possible. **What our BAA promises** (baa.en.md § 2(c), updated): breach notice ≤ [10] calendar days after discovery; security-incident notice within [5] business days; confirmed incidents within [24] h, in line with Schedule 2 S7. US HIPAA counsel to confirm. The BAA remains PLANNED. |
| B5 | **UNVERIFIED; drafter knowledge only; statutes not opened.** Neural data is generally **not** a listed trigger element in state breach laws. Biometric data is a trigger in several states, usually only with a name; notice is often not required when the data is encrypted and the key is not compromised. Starting table for US counsel to verify:<br>• **CO** (C.R.S. 6-1-716): notice within 30 days; biometric data is listed. AG notice if ≥500 residents.<br>• **CA** (Civ. Code 1798.82): "most expedient time possible and without unreasonable delay"; biometric data is listed. AG copy if >500 residents.<br>• **CT** (C.G.S. 36a-701b): notice within 60 days; biometric is listed. AG notice required.<br>• **MT** (MCA 30-14-1704): "without unreasonable delay"; element list to be checked.<br>Separately, the CO/CA/CT privacy acts treat neural data as sensitive data (HB24-1058 opened). A breach can therefore also be a privacy-act matter, even where the breach statute is not triggered. |
| B6 | **Proposal:**<br>(1) After withdrawal, **keep** the minimal consent-ledger entries: subject pseudonym, form version/hash, scopes, grant and withdrawal timestamps, and the deletion certificate. These prove lawful processing and honoured withdrawal (GDPR Art. 7(1) "demonstrate", **UNVERIFIED** text) and defend claims. Keep them for [the relationship + 3 years] (general Norwegian limitation period, foreldelsesloven § 2, **UNVERIFIED**) or longer under a legal hold.<br>(2) **Crypto-shred** all signal data, derived data and the subject data key. Audit-log entries remain but contain only pseudonyms, no signal content.<br>(3) Audit-log retention: **3 years by default** is acceptable. For BAA tenants, **6 years**, matching HIPAA's documentation-retention rule (45 CFR 164.316(b)(2), **UNVERIFIED**).<br>(4) Invoices and bookkeeping records follow bokføringsloven (**UNVERIFIED** period).<br>Flag for the advokat: whether keeping the pseudonym after withdrawal meets data minimisation. |
| B7 | **24 h accepted and fixed.** Customer notice is "without undue delay and in any event within [24] hours after confirmation", plus a duty not to postpone confirmation. It is now consistent in MSA Schedule 2 S7, DPA § 8.1 and SLA § 5. The bracket stays so it can be negotiated to 48 h in specific deals, but 24 h is the default. |
