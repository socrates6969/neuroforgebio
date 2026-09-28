> DRAFT – not legal advice. Must be reviewed by a Norwegian lawyer (advokat) before use.

# Academic Data Sharing Agreement (DSA)

Version [0.1] · [DATE] · Prevailing language: English [advokat choice; Norwegian: academic-data-sharing-agreement.no.md]

**Scope.** Sharing of pseudonymised/de-identified research data between NeuroForge and an academic institution, in either or both directions, for non-commercial research. It covers two uses:
- **(A10) research partnerships / co-authored studies**, under §§ 1–12;
- **(A7) held-out benchmark tracks**, under § 13.

**NeuroForge pool data** may be shared under this agreement only for subjects whose ledger shows **box (ii) `nf.pool` and box (v) `nf.share.research_partner`** (contributor-consent.*; CONSENT-SCOPES.*). If the Project is health research, **box (iv) `nf.research.future_neuro`** is needed as well, with a registered project record and REK/IRB reference.
- **Not** for data NeuroForge hosts as processor for its customers. That needs the customer's own agreement, and NeuroForge is not a party to it as data provider.
- **Not** for commercial licensing (use data-licence-agreement.*).
- **Not** for identifiable data.

A DPIA (GDPR Art. 35) is required before first transfer (RISK-MEMO § 9).

## Parties
1. **[NeuroForge Bio AS]** (ASSUMPTION: Norwegian AS, **not yet incorporated**), org.nr. [●], [address] ("NeuroForge").
2. **[University / institute]**, [org.nr.], [address], represented by [●] ("Institution"). Principal investigator: [name].

## 1. Project and purpose
1.1 Project: [title], described in **Annex 1** (research question, data, methods, duration).
1.2 **Purpose limitation.** Shared data may be used **only** for the Project. It may not be used for any purpose incompatible with the Contributors' consent scopes or the ethics approval. A new purpose needs a written amendment, and new consent or approval where required.

## 2. Roles – choose ONE option [advokat to confirm against the facts]
☐ **Option A – Separate controllers (controller-to-controller).** Each Party decides on its own why and how it processes the data it receives. Each Party is a separate controller, responsible for its own legal basis, transparency and security. **Default for one-way sharing.**

☐ **Option B – Joint controllers (GDPR Art. 26).** Use this when the Parties **jointly determine the purposes and means** (e.g. a jointly designed study with a shared protocol and a shared database). The Parties then set out their respective responsibilities in the arrangement in **Annex 2**:
- who informs data subjects (Arts. 13/14);
- who handles requests and who is the contact point;
- who does the DPIA;
- who notifies breaches;
- who holds the REK approval.

The essence of the arrangement must be made available to data subjects. **Data subjects may exercise their rights against each controller** whatever the arrangement says (Art. 26(3)).

☐ **Option C – Processor.** If one Party only processes data on the other's instructions (e.g. NeuroForge hosts the Institution's data), use the DPA (legal\commercial\dpa.*) instead of this agreement.

## 3. Legal basis and ethics
3.1 Each providing Party warrants that:
- (a) the data was collected lawfully, with an Art. 6 basis and an Art. 9(2) condition. That is either explicit consent covering sharing with the recipient for the Project (Art. 9(2)(a); for NeuroForge pool data, boxes (ii) and (v), and (iv) for health research), or research under Art. 9(2)(j) and Art. 89(1) together with national law (in Norway personopplysningsloven § 9, including the balancing test and prior DPO consultation or DPIA);
- (b) the required **ethics approvals** exist: REK approval under helseforskningsloven § 9 for medical and health research, or [IRB / other]. References are in Annex 1.
3.2 Each receiving Party confirms that the data use under the Project is covered by its own legal basis and by the approvals. Datatilsynet notes that REK approval alone is not a legal basis for processing.

## 4. Data protection obligations
4.1 **Minimisation.** Only the data fields in Annex 1 are shared. Direct identifiers are never shared. Code keys stay with the providing Party.
4.2 **No re-identification.** The receiving Party shall not re-identify, attempt to re-identify, link data to single out a person, or contact data subjects, except through the providing Party and with ethics approval.
4.3 **Security.** Measures appropriate to special-category data, at least:
- encryption at rest and in transit;
- access limited to named Project staff (Annex 3), with access logging;
- secure deletion;
- no upload to external AI services that keep or train on data.
NeuroForge's reference measures are MSA Schedule 2 / DPA Annex II (designed/planned; no certification claimed).
4.4 **Onward sharing.** No onward disclosure to third parties without the providing Party's prior written consent and a written agreement at least as protective as this one. **No sale or commercial licensing.**
4.5 **Data-subject rights.** The Parties help each other and forward requests within [5] business days.
4.6 **Breaches.** Notify the other Party without undue delay and within [24] hours of becoming aware. Each controller handles its own notifications to Datatilsynet and data subjects (Arts. 33/34, not opened: **UNVERIFIED**). Under Option B the lead is as set in Annex 2.

## 5. Withdrawal of consent and deletion
5.1 The providing Party notifies withdrawals (for NeuroForge data: via its consent-ledger Withdrawal Notice). The notice identifies the Project pseudonyms concerned (Arts. 17(1)(b) and 19).
5.2 Within [30] days the receiving Party deletes the records concerned, stops using them, and confirms deletion in writing.
- Trained models are retrained without the data or retired. **No certified machine unlearning is promised.**
- Results already published need not be withdrawn.
- The research exception in Art. 17(3)(d) is applied only by written agreement and in line with helseforskningsloven § 16 (the right to demand deletion within 30 days).

## 6. Publication
6.1 The Institution keeps academic freedom to publish Project results.
6.2 Publications may contain **only aggregate or de-identified results that do not allow singling out a person**. No row-level neural data is published unless:
- it is explicitly consented;
- it is approved by the ethics committee;
- it has passed a documented re-identification risk assessment; and
- the providing Party agrees in writing.
6.3 **Review period.** The providing Party gets a draft [30] days before submission, **only** to check for personal data and its own confidential information. It may not block publication for any other reason. The period may be extended once by [30] days to protect patentable subject matter [owner/Institution choice].
6.4 Acknowledgement of the data source and ethics references.

## 7. Transfers outside the EEA
No transfer of shared data outside the EEA without the providing Party's written consent and a GDPR Chapter V safeguard (e.g. an adequacy decision, or Commission standard contractual clauses under Art. 46(2)(c)).
- **Module choice (Module 1 C2C) and clause options: UNVERIFIED.** The EUR-Lex text of Decision (EU) 2021/914 was not opened; the advokat must confirm.
- NeuroForge note: its platform runs in an **AWS US region at launch; the EU region is planned** (D4). An EEA-only Project should not use the platform until the EU region exists, or must rely on SCCs plus a transfer impact assessment.
- Helseforskningsloven § 29 requires REK approval to send **human biological material** out of Norway. This agreement covers **data only**.

## 8. Intellectual property
- Each Party keeps its background IP and its datasets.
- Results belong to [the Party that creates them / jointly: advokat choice].
- NeuroForge's open-source SDK stays under Apache-2.0.
- No licence to the other Party's data beyond the Project.

## 9. Costs
No fees for the data. Each Party bears its own costs [unless Annex 1 says otherwise]. *(Keeping this agreement free of charge also keeps it out of US state "sale" definitions. Advokat to confirm for US-origin data.)*

## 10. Term, return and deletion
10.1 Term: until the Project end date in Annex 1 + [3] months.
10.2 At the end, or on termination, the receiving Party returns or deletes (at the providing Party's choice) all shared data and row-level derivatives within [30] days, and certifies this in writing. Exception: retention required by law or by the ethics approval (e.g. for research-integrity verification) for [●] years, kept secured and not used further.
10.3 Either Party may terminate on [60] days' notice, or immediately for a material breach of §§ 4–5.
10.4 §§ 4, 5, 6.2, 10.2 and 11 survive.

## 11. Liability
- Each Party is liable for its own processing. Art. 82 GDPR is not limited.
- Under Option B, liability allocation is set in Annex 2 and does not limit data subjects' rights (Art. 26(3)).
- Otherwise, liability is limited to direct loss, capped at [NOK ●]. The cap does not apply to breach of § 4.2 or § 4.4, or to intent or gross negligence (avtaleloven § 36).
- [Public institutions: check statutory limits on indemnities – **UNVERIFIED**.]

## 12. Governing law and venue
Norwegian law. Oslo tingrett. [For a foreign Institution: advokat to consider the Institution's home law or arbitration.]

## 13. Held-out benchmark tracks (A7) – optional schedule
13.1 **Purpose.** The Institution submits methods (decoders, pipelines) for evaluation on a held-out test set. The Institution never receives the test data. Or, where the Institution contributes a test set, NeuroForge hosts it without releasing it.
13.2 **Data.**
- (a) **Public tracks:** only datasets whose licence allows it (e.g. CC0 / CC-BY-4.0, with attribution as the licence requires). Where they contain data on EU/EEA persons, GDPR still applies, because a copyright licence does not settle data protection.
- (b) **Private held-out tracks:** only NeuroForge pool data with boxes (ii) and (iv) (and (v) if the Institution contributes the data or co-owns the track), or the Institution's own data, where the Institution warrants its legal basis and ethics approval.
13.3 **Compute-to-data only.**
- Submissions run inside NeuroForge's environment.
- Only scores and aggregate metrics are released, under the minimum-cell and no-row-level rules of dpa-addendum-compute-to-data-cro Annex A1.
- Submissions that try to extract test data (e.g. by encoding it into outputs) are disqualified. The attempt is treated as a breach of § 4.2.
13.4 **Results wording.** Leaderboards and reports are "evaluation reports", **never "certified" or "validated"**. They make no clinical claims.
13.5 **Withdrawal.** When a subject withdraws, their data is removed from the test set and affected scores are re-computed or marked. Past published scores may stay, with a note.
13.6 **Sponsorship.** A sponsor funds a track but gets no access to test data and no influence on scoring. The Institution's academic freedom (§ 6.1) applies to publishing benchmark findings.

## Signatures
[Name, title, date] × 2 – not to be signed before the ethics approvals and the DPIA exist.

---
### Annex 1 – Project description, data fields, ethics references, dates
### Annex 2 – Art. 26 arrangement (Option B only): responsibilities table (information, requests, contact point, DPIA, breach, REK, security, retention)
### Annex 3 – Named Project staff and security contacts

## Hjemmel / Legal basis
- GDPR, Norwegian text on Lovdata (opened 2026-09-26):
  - Art. 9 (special categories): https://lovdata.no/lov/2018-06-15-38/gdpr/a9
  - Art. 17 (erasure): https://lovdata.no/lov/2018-06-15-38/gdpr/a17
  - Art. 19 (notice to recipients): https://lovdata.no/lov/2018-06-15-38/gdpr/a19
  - Art. 26 (joint controllers): https://lovdata.no/lov/2018-06-15-38/gdpr/a26
  - Art. 28 (processors): https://lovdata.no/lov/2018-06-15-38/gdpr/a28
  - Art. 35 (DPIA): https://lovdata.no/lov/2018-06-15-38/gdpr/a35
  - Art. 46 (transfers): https://lovdata.no/lov/2018-06-15-38/gdpr/a46
  - Art. 89 (research safeguards): https://lovdata.no/lov/2018-06-15-38/gdpr/a89
  - Arts. 13, 14, 33, 34 and 82: **UNVERIFIED** (not opened).
- Personopplysningsloven § 9: https://lovdata.no/lov/2018-06-15-38/§9 (opened 2026-09-26).
- Helseforskningsloven §§ 2, 4, 9, 16, 29: https://lovdata.no/dokument/NL/lov/2008-06-20-44 (opened 2026-09-26).
- Datatilsynet, health and research projects (REK approval not a legal basis): https://www.datatilsynet.no/personvern-pa-ulike-omrader/forskning-helse-og-velferd/helse-og-forskningsprosjekter/ (opened 2026-09-26).
- SCC Decision (EU) 2021/914: **UNVERIFIED**.
- Avtaleloven § 36: https://lovdata.no/dokument/NL/lov/1918-05-31-4/KAPITTEL_3 (opened 2026-09-26 by nfb-legal-commercial).
- Product facts: BLUEPRINT.md §8.3–8.4; DECISIONS.md D4, D6.
