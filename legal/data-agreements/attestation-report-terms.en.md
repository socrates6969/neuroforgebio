> DRAFT – not legal advice. Must be reviewed by a Norwegian lawyer (advokat) before use.

# Consent-Coverage Attestation Report – Service Terms (A8)

Version [0.1] · [DATE] · Service schedule to the MSA.
Prevailing language: English [advokat choice] · Norwegian version: attestation-report-terms.no.md
Provider: [NeuroForge Bio AS] (ASSUMPTION: Norwegian AS, **not yet incorporated**) · Client: [●].

**Name rule.** The product is called a **"Consent-Coverage Attestation Report"** ("Report"). It must **never** be called a certificate, certification, seal, "verified", "compliant" or "approved", whether in the Report, on the website or in sales material.

## 1. What the Report is
1.1 The Report is a **factual statement, at a point in time, of what NeuroForge's systems record** about a dataset the Client names ("Dataset"). It covers:
- (a) **consent-ledger coverage:** per subject pseudonym and per scope, the consent form version, hash and grant/withdrawal status;
- (b) **jurisdiction classification** per channel and derived artefact, from rule set version [vN] (BLUEPRINT §8.2). Rules marked `unverified` are shown as unverified;
- (c) **lineage:** the hash-chain integrity of the provenance graph for the Dataset;
- (d) optionally, the results of a **re-identification risk scan** run with a stated method and parameters. The scan's efficacy is not claimed.
1.2 NeuroForge acts as the Client's **processor** for this service (DPA). It uses the Dataset only to produce the Report.

## 2. What the Report is NOT (mandatory disclaimers, printed on page 1 of every Report)
> 1. **Not a certification.** This Report is not a certification under GDPR Art. 42 or any other scheme, not a seal or mark, and not an audit opinion under any assurance standard.
> 2. **Not legal advice.** It does not state that any processing is lawful, that any consent is valid, or that any data is anonymous.
> 3. **Point in time.** It reflects the records in NeuroForge's systems as at [timestamp UTC] and rule set [vN]. Consent can be withdrawn and law can change after that time.
> 4. **Records, not reality.** It attests only to what the ledger and provenance graph record. It does not check that the underlying consents were properly obtained, understood or signed, that the uploaded data is what it claims to be, or anything that happened outside the platform.
> 5. **Unverified rules.** Jurisdiction rules marked "unverified" have not been reviewed by counsel.

## 3. Client obligations
3.1 The Client must give accurate inputs and must not alter or excerpt the Report in a misleading way. The Report may only be shared in full, with page 1 included.
3.2 The Client may not describe the Report as a certification, or imply that NeuroForge endorses the Dataset or its use.
3.3 The Client stays the controller. It is solely responsible for the lawfulness of its processing, sharing or sale of the Dataset.

## 4. Fees
[Per dataset: ●] [Due-diligence package: ●] per the Order Form. These are ESTIMATE bands from DATA-REVENUE-STRATEGY A8.

## 5. Liability
5.1 The Report is prepared with reasonable skill and care, from the records described. **No other warranty is given**, express or implied: none on accuracy of Client inputs, fitness for a purpose, or legal compliance.
5.2 **Cap.** NeuroForge's total liability for each Report is limited to **[the greater of the fees paid for that Report or NOK ●]**. The cap does not apply to intent or gross negligence, or where mandatory law says otherwise (avtaleloven § 36).
5.3 **No third-party reliance.** The Report is for the Client only. Third parties (acquirers, licensees, investors) who receive it may not rely on it against NeuroForge unless they sign a [reliance letter] with its own cap.
5.4 **Indemnity.** The Client indemnifies NeuroForge against third-party claims arising from the Client's misuse or misdescription of the Report (§ 3).

## 6. Records
NeuroForge keeps a hash of each Report and its inputs for [5] years, so that the Report can be verified against later questions. The Report itself contains no signal data and no direct identifiers.

## 7. Law
MSA governing law and venue apply (Norwegian law; Oslo tingrett).

## Hjemmel / Legal basis
- **Avtaleloven § 36:** https://lovdata.no/dokument/NL/lov/1918-05-31-4/KAPITTEL_3 (opened 2026-09-26 by nfb-legal-commercial).
- **GDPR Art. 28 processor role** (Lovdata, opened 2026-09-26): https://lovdata.no/lov/2018-06-15-38/gdpr/a28
- **GDPR Art. 42 (certification schemes):** named only to disclaim it. Its text was **not opened, UNVERIFIED**.
- **Markedsføringsloven (misleading claims):** **UNVERIFIED**.
- **Product facts and rules:** BLUEPRINT §3.6, §8.2–8.3 and BOARD rule "never state a control as certified"; investor\DATA-REVENUE-STRATEGY.md A8.
