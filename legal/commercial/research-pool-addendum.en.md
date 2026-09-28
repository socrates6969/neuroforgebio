> DRAFT – not legal advice. Must be reviewed by a Norwegian lawyer (advokat) before use.

# Research Pool Addendum (MSA § 4.3 opt-in) – PLANNED

**Status: PLANNED.** The NeuroForge research pool is planned to open in months 18–30 (ESTIMATE). This addendum must not be offered or signed until: (a) NeuroForge has completed a DPIA for the pool (legal\data-agreements\RISK-MEMO.md § 9); (b) the pool's de-identification method and technical controls are built and documented; (c) the contributor consent form (legal\data-agreements\contributor-consent.*) is final; (d) an advokat has reviewed this addendum. Prevailing language: English [advokat choice]. ASSUMPTION: NeuroForge Bio will be a Norwegian AS, not yet incorporated.

**Parties:** [Customer] ("Customer") and [NeuroForge Bio AS] ("NeuroForge"), under MSA [no./date] and Order Form [no.]. This addendum is the **separate, specific written opt-in** referred to in MSA § 4.3. Default: **OFF** – nothing in the MSA, Order Form or DPA allows pool contribution unless this addendum is signed and a dataset is enrolled under § 3.

## 1. Definitions
- **Research Pool**: NeuroForge's planned collection of de-identified neural-data copies used for the Pool Purposes.
- **Pool Purposes**: only the purposes matching the contributor consent boxes actually ticked by each data subject, namely: (ii) research pool – study of nervous-system signals and testing/improving NeuroForge analysis software; (iii) internal AI training; (iv) future nervous-system research by NeuroForge, subject to ethics approval per project; (v) sharing with vetted academic/hospital research partners under contract; (vi) training AI models licensed to companies (models, not data); (vii) licensing de-identified data to companies under a data licence agreement (legal\data-agreements\data-licence-agreement.*). Box numbers per legal\data-agreements\contributor-consent.en.md; ledger scope IDs per legal\data-agreements\CONSENT-SCOPES.en.md: (ii) `nf.pool` + `nf.internal_rnd`; (iii) `nf.model_training.internal`; (iv) `nf.research.future_neuro`; (v) `nf.share.research_partner`; (vi) `nf.model_training.licensed`; (vii) `nf.data_licence.commercial`; (viii) `nf.recontact` (contact only, no pool data).
- **Contributed Dataset**: a dataset Customer enrols under § 3.
- **De-identified**: direct identifiers removed and pseudonyms replaced by pool-specific keys that NeuroForge cannot link back without Customer's key. **Neural data de-identified this way is still treated as personal data** (re-identification risk; security\THREAT-MODEL.md P-03). Nothing in this addendum calls pool data "anonymous".

## 2. Roles
2.1 For the Service, NeuroForge remains Customer's processor under the DPA.
2.2 For the **copy** placed in the Research Pool, NeuroForge becomes a **separate controller** for the Pool Purposes, relying on the data subjects' explicit consent collected by Customer on NeuroForge's behalf (GDPR Art. 6(1)(a) and 9(2)(a)) [advokat: confirm roles and whether a joint-controller arrangement under Art. 26 is needed for the collection step – **UNVERIFIED**].
2.3 NeuroForge shall be named as controller for boxes (ii)–(viii) in the consent form used by Customer.

## 3. Enrolment (per dataset)
3.1 Customer enrols a dataset by ticking it in the console or listing it in Annex 1 (dataset ID, study, jurisdiction(s), ethics approval reference, consent-form version).
3.2 Only subjects whose ledger record shows the matching scopes are copied. The Service copies **only De-identified data**, and only for the scopes each subject ticked (e.g. a subject with (ii) but not (vi) is excluded from licensed-model training).

## 4. Customer warranties
Customer warrants, for each Contributed Dataset, that:
(a) every contributing data subject gave the matching consent using the current NeuroForge-approved consent form (legal\data-agreements\contributor-consent.*), each box separately, with no box pre-ticked and no payment depending on the choices;
(b) the consent record (form version, boxes, date) is in the consent ledger;
(c) any required ethics/REK/IRB approval covers contribution to the pool;
(d) the data was lawfully collected and Customer has the right to disclose it;
(e) Customer will promptly record every withdrawal in the ledger.

## 5. Ownership and licence
5.1 **Customer keeps ownership** of its data and Outputs (MSA § 4.1). Data subjects keep their rights.
5.2 Customer grants NeuroForge a non-exclusive, worldwide, non-transferable (except to a successor under MSA § 17.2) licence to copy, store and use the De-identified Contributed Datasets **only for the Pool Purposes permitted by each subject's consent**, for as long as that consent stands.
5.3 NeuroForge owns models, software and research results it creates from pool data, subject to § 6 (withdrawal) and the data subjects' rights. [Negotiable: Customer may request credit in publications or a licence to such models.]
5.4 **No sale of identifiable data.** NeuroForge shall never sell, rent or share data that identifies, or is reasonably likely to identify, a person. Data licensing under box (vii) is limited to De-identified data, under a data licence agreement forbidding re-identification and onward transfer. Prohibited uses in the AUP (advertising, data brokers, insurance, employment, credit, emotion inference at work or school) are excluded in every licence.

## 6. Withdrawal
6.1 Customer may withdraw a whole dataset, and a data subject may withdraw any box, **at any time**, without giving reasons.
6.2 Withdrawal is recorded in the consent ledger and propagated as designed (architecture\BLUEPRINT.md § 8.4):
   - pool copies of the withdrawn data are deleted and their pool keys destroyed (crypto-shredding);
   - models trained on it are flagged **`retrain_required`** and retrained without it or blocked; **NeuroForge does not offer certified machine unlearning**;
   - **copies already shared with partners or licensees (boxes (v)–(vii)) cannot be recalled by NeuroForge**; NeuroForge notifies those recipients, who are contractually required to delete, and lists them for Customer [in the deletion certificate];
   - published aggregate research results are not withdrawn.
6.3 Target: pool deletion within [30] days of the ledger entry; US state "sale" opt-outs within [15] days (per the consent form) [**UNVERIFIED** state deadlines].

## 7. Incentive: service credits (not cash)
7.1 In return, Customer receives **service credits** of [●] per [enrolled consented subject / GB / dataset] per [year] (ESTIMATE), capped at [●]% of annual Fees, applied to future invoices. **No cash payment, and credits cannot be converted into cash** (CEO decision).
7.2 Credits are not payment for the data subjects' consent, and Customer shall not pass any per-choice payment to data subjects (consent form: same payment whatever they choose).
7.3 **Credits already granted are not clawed back when data is withdrawn** [flag: negotiable – NeuroForge may prefer pro-rata reversal of unused credits].
7.4 Credits lapse at the end of the MSA [negotiable]; tax/MVA treatment of credits – **UNVERIFIED**, accountant to confirm.

## 8. Term
Runs with the MSA. Either party may end it on [30] days' notice. On ending, no new data is copied; NeuroForge may keep using already contributed data only as long as each subject's consent stands, unless Customer elects full withdrawal under § 6 [negotiable].

## 9. Liability
MSA § 12 applies. Breach of § 4 (Customer warranties) or § 5.4 (no sale of identifiable data) is excluded from the general cap [negotiable].

Annex 1 – Contributed Datasets: | Dataset ID | Study | Jurisdictions | Ethics ref. | Consent form version | Scopes enabled |

## Hjemmel / Legal basis
- GDPR Art. 6(1)(a), 7, 9(2)(a), 26 – via personopplysningsloven § 1 (https://lovdata.no/dokument/NL/lov/2018-06-15-38, opened 2026-09-26); verbatim wording **UNVERIFIED** (EUR-Lex failed). Helseforskningsloven/REK – **UNVERIFIED** by this author (see RISK-MEMO § 4).
- Colorado HB24-1058 (https://leg.colorado.gov/bills/hb24-1058, opened 2026-09-26). CA/CT "sale" rules – **UNVERIFIED**.
- Avtaleloven § 36 (https://lovdata.no/dokument/NL/lov/1918-05-31-4/KAPITTEL_3, opened 2026-09-26).
- Internal: legal\data-agreements\contributor-consent.en.md (boxes (i)–(viii)); architecture\BLUEPRINT.md § 8.3–8.4; security\LEGAL-HANDOFF.md A9 (neural data not anonymous).
