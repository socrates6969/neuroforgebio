> DRAFT – not legal advice. Must be reviewed by a Norwegian lawyer (advokat) before use.

# Research Data Licence Agreement (de-identified neural datasets)

Version [0.1] · [DATE] · Prevailing language: English [advokat choice; Norwegian version: data-licence-agreement.no.md]

**Pre-conditions: do not use this template until all four are met.**
- a DPIA (GDPR Art. 35) covers the licensing programme;
- the dataset was collected by NeuroForge **as controller**, with contributor consent that includes **box (ii) (research pool) and the separate box (vii) "data licensed to companies"** (contributor-consent form; ledger scopes `nf.pool` + `nf.data_licence.commercial`, CONSENT-SCOPES.en.md). Non-paying academic recipients use the academic DSA and box (v) instead;
- REK/IRB approval covers the sharing, where required;
- an advokat has reviewed this agreement.

See legal\data-agreements\RISK-MEMO.md.

**Out of scope (this template must not be used for any of these):**
- identifiable data;
- sale or disclosure to consumers or to data brokers;
- any data NeuroForge holds as a **processor** for its customers (MSA/DPA § 3.4 forbids it);
- PHI from a HIPAA covered entity.

## Parties
1. **[NeuroForge Bio AS]** (ASSUMPTION: Norwegian AS, **not yet incorporated**), org.nr. [●], [address] ("Licensor").
2. **[Licensee legal name]**, [registration no.], [address], [country] ("Licensee").

## 1. Definitions
- **Dataset.** The de-identified dataset described in **Annex A**, including updates and derived subsets delivered by Licensor.
- **De-identified.** Direct identifiers are removed and subject codes replaced by licence-specific pseudonyms, with the key held only by Licensor. **The Parties agree that the Dataset is still personal data under GDPR (pseudonymised, Art. 4(5)) and is probably special-category data (Art. 9).** Neural signals can themselves identify people, so the risk of re-identification cannot be reduced to zero.
- **Permitted Purpose.** The purpose stated in Annex A, which must fall within the consent scopes recorded for every Contributor in the Dataset.
- **Contributor.** A person whose data is in the Dataset.
- **Withdrawal Notice.** A notice from Licensor's consent ledger that a Contributor has withdrawn consent, or that consent scope has changed.
- **Derived Material.** Features, annotations, statistics, models and other output made from the Dataset.

## 2. Roles
2.1 Each Party is a **separate controller** for its own processing. Licensee decides purposes and means within the Permitted Purpose. The Parties are not joint controllers unless they sign an Art. 26 arrangement.
2.2 Licensee must have and document its **own legal basis** under GDPR Art. 6 and an Art. 9(2) condition (and, where applicable, national research law, REK/IRB approval and US state law).

## 3. Licence grant
3.1 Licensor grants Licensee a **non-exclusive, non-transferable, non-sublicensable, revocable** licence to use the Dataset for the Permitted Purpose, during the Term, at the sites and by the named personnel in Annex B.
3.2 **Permitted uses** (only within consent scope):
- (a) scientific research;
- (b) development and validation of Licensee's own methods or products, **only** where every Contributor ticked box (vii) (`nf.data_licence.commercial`);
- (c) training of Licensee's own models, **only** where every Contributor ticked box (vii). Box (iii) covers only NeuroForge's internal training, and box (vi) covers only NeuroForge-trained models licensed out. Neither of them authorises this Agreement.
3.3 **Prohibited uses.** Licensee shall not, and shall not let anyone:
- (a) **re-identify** or attempt to re-identify any Contributor, **link** the Dataset with other data to single out a person, or contact a Contributor;
- (b) sell, rent, **resell**, sublicense, publish or otherwise disclose row-level data or Derived Material that allows singling out a person;
- (c) use the Dataset for any practice prohibited by **EU AI Act Art. 5**, including emotion inference in workplace or education settings (except for medical or safety reasons), manipulative or subliminal techniques, and biometric categorisation inferring sensitive traits. This applies wherever Licensee is established;
- (d) use it for **clinical decisions**, diagnosis or treatment of any individual, or to control stimulation or any device;
- (e) use it for decisions about individuals' employment, education, insurance, credit or housing, or for law enforcement, surveillance or "lie detection";
- (f) use it for advertising, marketing profiles, or sale to consumers or data brokers;
- (g) go beyond the Permitted Purpose or Contributors' consent scopes as notified by Licensor.

## 4. Licensor warranties
4.1 Licensor warrants that, to its knowledge after reasonable checks of its consent ledger:
- (a) each Contributor gave consent covering the disclosure to Licensee's recipient category and the Permitted Purpose;
- (b) the consent versions and scopes are recorded in the ledger and summarised in Annex A;
- (c) the required ethics approvals listed in Annex A were obtained;
- (d) the Dataset has been de-identified as described in Annex A, and a re-identification risk assessment was done [reference].
4.2 Otherwise the Dataset is provided "as is". Licensor gives no warranty that it is accurate, fit for a purpose, or clinically valid.

## 5. Licensee covenants
5.1 **Security.** Licensee must protect the Dataset with measures at least equivalent to Licensor's security schedule (MSA Schedule 2 / DPA Annex II, S1–S16), including:
- encryption at rest and in transit;
- role-based access limited to the Annex B personnel;
- access logging;
- no copies on personal devices;
- no upload to third-party AI services that keep or train on inputs.
5.2 **Onward transfer.** Licensee may not transfer or give access to the Dataset outside its organisation. Sub-processors (e.g. cloud hosting) are allowed only with Art. 28 contracts and Licensor's prior written consent. **Transfers outside the EEA** need Licensor's prior written consent and a GDPR Chapter V safeguard, e.g. the Commission's standard contractual clauses (Art. 46(2)(c)). [SCC module (controller-to-controller, Module 1) to be confirmed by advokat. **UNVERIFIED**: EUR-Lex text of Decision 2021/914 not opened.]
5.3 **Transparency and rights.** Licensee helps Licensor answer Contributors' requests. It forwards any request it receives to Licensor within [5] business days.
5.4 **Publication.** Only aggregate results that do not allow singling out a person may be published, with a citation of the Dataset and its ethics references.

## 6. Withdrawal and deletion
6.1 Licensor sends a **Withdrawal Notice** (identifying the affected licence pseudonyms) through its consent ledger. This reflects the controller's duty to tell recipients about erasure (Art. 19) and the contributor's right to erasure after withdrawal (Art. 17(1)(b)).
6.2 Within **[30] days** of a Withdrawal Notice, Licensee must:
- (a) delete the Contributor's records from all copies, including backups when they rotate. Backups must not be restored for use in the meantime;
- (b) stop using them in any ongoing analysis;
- (c) for trained models, **retrain without the Contributor**, or stop using the affected model versions, at the next scheduled retrain and no later than [90] days. The Parties acknowledge that **no certified machine unlearning exists or is promised**;
- (d) send a signed **deletion certificate** listing the actions taken.
6.3 Aggregate results already published need not be withdrawn. The exception in Art. 17(3)(d) for research may apply to specific cases, but only on Licensor's written confirmation.
6.4 On expiry or termination, Licensee must delete the Dataset and all row-level Derived Material within [30] days and certify deletion. Aggregate results and models retrained in line with § 6.2 may be kept [advokat/owner choice].

## 7. Breach notification
Licensee must notify Licensor **without undue delay, and within [24] hours of becoming aware**, of any personal-data breach or suspected re-identification involving the Dataset. It must cooperate so that each controller can meet its own Art. 33/34 duties.

## 8. Audit
Licensee must keep records of access and use. Once per [12] months, or after a breach, Licensor or an independent auditor bound by confidentiality may audit Licensee's compliance on [30] days' notice ([5] days after a breach).

## 9. Fees
[Fee / cost-recovery amount] per Annex C. [Owner choice. Advokat to check whether a fee makes this a "sale" under US state laws. If so, box (vii), which names the "sale", is required for US Contributors; see RISK-MEMO § 5.]

## 10. Term and termination
10.1 Term: [24] months from signature, unless ended earlier.
10.2 Licensor may terminate **with immediate effect** if Licensee breaches § 3.3, § 5 or § 7, or if continued sharing becomes unlawful or goes beyond consent. Either Party may terminate on [90] days' notice.
10.3 §§ 3.3, 5, 6, 7, 8, 11 and 13 survive.

## 11. Liability
11.1 Each Party is liable for its own processing as controller (Art. 82 GDPR is not limited).
11.2 Licensee **indemnifies** Licensor against claims, fines and costs caused by Licensee's breach of § 3.3 or § 5.
11.3 Otherwise, each Party's liability is capped at [the greater of fees paid in 12 months or NOK [●]]. The cap does **not** apply to breach of § 3.3 (re-identification, resale, prohibited uses), to intent or gross negligence, or where mandatory law says otherwise (avtaleloven § 36).

## 12. Confidentiality
The Dataset and Annex A are confidential information of Licensor.

## 13. Governing law and venue
Norwegian law. Oslo tingrett is the agreed venue. [Arbitration alternative per MSA: advokat choice.]

## Signatures
Not to be signed until the pre-conditions at the top are met. [Name, title, date] × 2.

---
### Annex A – Dataset and consent description
| Item | Content |
|---|---|
| Dataset name / version / hash | [●] |
| Modalities (EEG/ECoG/EMG …), channels, sampling, derived features | [●] |
| Number of Contributors; jurisdictions (EEA / CO / CA / CT / MT / other) | [●] |
| Consent form version(s) + hash; scopes present for **all** Contributors (boxes (ii) `nf.pool` and (vii) `nf.data_licence.commercial` required; list others present) | [●] |
| Ethics approvals (REK ref. [●] / IRB ref. [●]) | [●] |
| De-identification method; re-identification risk assessment ref. | [●] |
| Permitted Purpose (specific) | [●] |
| DPIA reference | [●] |

### Annex B – Licensee sites, named personnel, security contact
[●]

### Annex C – Fees
[●]

## Hjemmel / Legal basis
- GDPR (Norwegian text, Lovdata), opened 2026-09-26:
  - Art. 4 (definitions incl. pseudonymisation): https://lovdata.no/lov/2018-06-15-38/gdpr/a4
  - Art. 9 (special categories): https://lovdata.no/lov/2018-06-15-38/gdpr/a9
  - Art. 17(1)(b), (3)(d) (erasure): https://lovdata.no/lov/2018-06-15-38/gdpr/a17
  - Art. 19 (notice to recipients): https://lovdata.no/lov/2018-06-15-38/gdpr/a19
  - Art. 26 (joint controllers): https://lovdata.no/lov/2018-06-15-38/gdpr/a26
  - Art. 28 (processors): https://lovdata.no/lov/2018-06-15-38/gdpr/a28
  - Art. 35 (DPIA): https://lovdata.no/lov/2018-06-15-38/gdpr/a35
  - Art. 46 (transfers): https://lovdata.no/lov/2018-06-15-38/gdpr/a46
  - Arts. 33, 34, 82 not opened: **UNVERIFIED**.
- SCC Decision (EU) 2021/914 (module choice): **UNVERIFIED** (EUR-Lex failed).
- EU AI Act Art. 5: **UNVERIFIED** (EUR-Lex failed); per market\regulation.md §5.
- Connecticut PA 25-113 (sale of sensitive data needs consent): https://www.cga.ct.gov/2025/ACT/PA/PDF/2025PA-00113-R00SB-01295-PA.PDF (opened 2026-09-26).
- California "sell" definition, SB 1223: https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202320240SB1223 (opened 2026-09-26).
- Avtaleloven § 36: https://lovdata.no/dokument/NL/lov/1918-05-31-4/KAPITTEL_3 (opened by nfb-legal-commercial 2026-09-26).
- Helseforskningsloven § 9 (REK): https://lovdata.no/dokument/NL/lov/2008-06-20-44 (opened 2026-09-26).
- Product facts: BLUEPRINT.md §8.3–8.4 (ledger, withdrawal propagation, no certified unlearning); DPA § 3.4 (no sale of customer data).
