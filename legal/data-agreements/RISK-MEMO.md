> DRAFT – not legal advice. Must be reviewed by a Norwegian lawyer (advokat) before use.

# Risk memo: selling or licensing neural / biological data

To: owner (Marius Carlsson), nfb-legal queen · From: nfb-legal-privacy · Date: 2026-09-26 · Status: DRAFT
ASSUMPTION: NeuroForge Bio will be a Norwegian aksjeselskap (AS). It is **not yet incorporated**. Name, org.nr. and address are placeholders.

## 0. Question and short answer

**Question.** The owner asked for contracts to "sell biological data to other buyers (consumers)".

**Short answer.**
1. **NeuroForge cannot sell customer data.** Under the MSA and DPA, NeuroForge is a **processor** for the data customers upload. DPA § 3.4 already says NeuroForge will not use that data for its own purposes, train on it, sell it or combine it. A processor that decides its own purposes for customer data is treated as a controller in breach (GDPR Art. 28(10)). Selling it would breach the contract and the law, and it would end the business.
2. **Any data licensing can only cover datasets NeuroForge controls itself.** That means data NeuroForge collects **as controller** from its own consenting contributors, or data it is expressly authorised to share (for example a partner's dataset under a written agreement that allows it).
3. **Selling identifiable neural data to consumers or data brokers is not a route we will draft for.** Under GDPR it needs explicit, specific consent (Art. 9(2)(a)). Under Connecticut law a controller may "not sell the sensitive data of a consumer without the consumer's consent" (PA 25-113). It also contradicts the company's own positioning (D1) and its own AUP § 4.1.
4. **What is realistic, if anything:** consent-based **research licensing** of de-identified datasets that NeuroForge controls, academic data-sharing agreements, and **synthetic data**. Each needs a DPIA, advokat review and, for health research, REK approval.
5. **Recommendation: do not build a data-sales business line now.** Revisit only after incorporation, a DPIA, advokat review and an ethics-approved collection. The templates in this folder are prepared for that case only.

## 1. Is neural data personal data, and is it special-category data?

- **Personal data.** Personal data is "enhver opplysning om en identifisert eller identifiserbar fysisk person" (Art. 4(1), Norwegian text on Lovdata). Neural recordings linked to a subject pseudonym are personal data. **Pseudonymised data is still personal data**: Art. 4(5) defines pseudonymisation as data that can no longer be attributed to a person *without additional information kept separately*.
- **Special categories (Art. 9(1)).** GDPR has no category called "neural data". Neural data is special-category data when it is:
  - **health data** (Art. 4(15): data about physical or mental health that reveals health status). Many EEG, ECoG and intracortical datasets reveal a diagnosis or condition, for example epilepsy, paralysis or a clinical cohort label; or
  - **biometric data processed "med det formål å entydig identifisere en fysisk person"** (Art. 9(1); Art. 4(14)).
- **Working rule.** Treat all neural datasets as Art. 9 data. This matches DPA § 13.3, and the cost of a wrong "not special" call is high. Art. 9(4) also lets EEA states add conditions for health, genetic and biometric data. Norway has done so in helseforskningsloven (§ 5 below).

## 2. Conditions under Art. 9(2) for NeuroForge as controller

| Condition | Text (Lovdata, Norwegian GDPR) | Fit for data licensing |
|---|---|---|
| **9(2)(a) explicit consent** | "uttrykkelig samtykke … for ett eller flere spesifikke formål" | **The main route.** Each purpose (research, commercial licensing, model training, recontact) needs its own separate, unticked opt-in (see the consent form). Consent must be "frivillig, spesifikk, informert og utvetydig" (Art. 4(11)). Withdrawal must be possible at any time and as easy as giving consent (Art. 7(3)). Tying a service to unnecessary consent weighs against voluntariness (Art. 7(4)). |
| **9(2)(j) research** | necessary for scientific research "i samsvar med artikkel 89 nr. 1" on the basis of Union or national law with "egnede og særlige tiltak" | Norwegian law: personopplysningsloven § 9 allows Art. 9 data without consent if necessary for research, **"samfunnets interesse i at behandlingen finner sted, klart overstiger ulempene for den enkelte"**, with safeguards per Art. 89(1). The controller must first consult a DPO, unless a DPIA has been done (§ 9 second paragraph). § 10 applies the same consultation duty when research on Art. 9 data is based on consent. **This route supports research. It does not support selling data.** Whether commercial R&D counts as "vitenskapelig forskning" is **UNVERIFIED** and a question for the advokat. |
| Other 9(2) grounds | – | Not relevant to selling data. |

Every downstream **licensee is its own controller**. It needs its own Art. 6 and Art. 9 basis. NeuroForge's consent can at most cover *disclosure* to the categories of recipients the contributor opted into.

## 3. Anonymisation vs pseudonymisation, and why neural signals are hard to anonymise

- **Legal test.** Recital 26 takes truly anonymous information outside GDPR, judged by "all the means reasonably likely to be used, such as singling out". The recital also says: "Personal data which have undergone pseudonymisation … should be considered to be information on an identifiable natural person". *Verified later the same day against the official text from the Publications Office (see Hjemmel).* Pseudonymised data stays in scope (Art. 4(5)).
- **Neural-specific risk.** The signal itself can act as an identifier. Peer-reviewed reviews describe EEG as a **biometric modality for person authentication**:
  - Review on EEG-Based Authentication Technology, *Comput Intell Neurosci* 2021, doi:10.1155/2021/5229576 (grade B, abstract only);
  - Threats and Mitigation Strategies for EEG-Based Person Authentication, *Int J Telemed Appl* 2025, doi:10.1155/ijta/3946740 (grade B, abstract only).
  - The abstracts we opened give **no accuracy figures**, and we do not quote any. Re-identification rates for specific datasets are **UNVERIFIED**.
- **Consequence.** Stripping names and IDs does **not** make a raw or minimally processed neural time-series anonymous. It is at best **pseudonymised/de-identified**, and so still personal data (usually Art. 9). Claims of "anonymised neural data" need a documented re-identification risk assessment, with aggregation, feature reduction or synthetic generation. Even then the risk is not zero. The licence and consent templates assume **de-identified = still personal data**.
- **Synthetic data** lowers risk but does not remove it. Generative models can memorise and leak training records. Membership-inference risk has to be tested before release. (General ML knowledge. No study was opened for neural data specifically: **UNVERIFIED** magnitude.)

## 4. Norway: helseforskningsloven and REK

- **Scope.** The act covers "medisinsk og helsefaglig forskning på mennesker, humant biologisk materiale eller helseopplysninger" (§ 2). Such research is "virksomhet som utføres med vitenskapelig metodikk for å skaffe til veie ny kunnskap om helse og sykdom" (§ 4). Neural datasets gathered to study disease or health fall inside it. Pure engineering data from healthy volunteers (for example BCI signal quality) may fall outside it. **Borderline: advokat/REK to decide.**
- **REK.** The project needs prior approval from REK (§ 9).
- **Consent (§ 13)** must be "frivillig, spesifikk, informert og utvetydig" unless the law provides otherwise. (Broad consent: that section was not verified in this pass. **UNVERIFIED**.)
- **Withdrawal (§ 16).** The participant can withdraw at any time. Per the Lovdata summary we opened, the participant may then demand deletion within 30 days, with limited exceptions (e.g. anonymised data). Verify § 16 verbatim before use.
- **Transfer abroad.** § 29 needs REK approval to send **human biological material** out of the country. We did not find a similar clause for health *data*. GDPR Chapter V applies to the data. **UNVERIFIED** whether other rules apply.
- **Datatilsynet**: REK approval "tidligere vært et tilstrekkelig og nødvendig behandlingsgrunnlag … Dette gjelder ikke lenger". REK approval does **not** replace a GDPR legal basis.

## 5. United States (only if NeuroForge collects from US residents or sells to US buyers)

| State | What we opened | Effect on licensing |
|---|---|---|
| **Connecticut** PA 25-113 (CTDPA sections effective **1 Jul 2026**, so in force now) | "Neural data" means information generated by measuring the activity of an individual's **central nervous system**. Neural data is sensitive data item (G). A controller shall "(D) not process sensitive data … without obtaining the consumer's consent", shall "(G) provide an effective mechanism … to revoke … at least as easy as" giving consent, and cease processing within **15 days**, and shall "(H) **not sell the sensitive data of a consumer without the consumer's consent**". "Sale" means exchange "for monetary or other valuable consideration by the controller to a third party". The exceptions include disclosure to a processor and consumer-directed disclosure. | Licensing neural data for a fee = **sale** → opt-in consent specific to sale, revocation within 15 days. |
| **California** SB 1223 (Ch. 887, 2024) | Neural data = sensitive personal information: "generated by measuring the activity of a consumer's central or peripheral nervous system, and that is not inferred from nonneural information". The CCPA's "sell" is very broad: "selling, renting, releasing, disclosing, … making available … for monetary or other valuable consideration". Civ. Code § 1798.121: a consumer may "at any time" direct a business "to limit its use" of sensitive PI. | Licensing = "sale". Right-to-limit notice is needed. The opt-out-of-sale mechanics (§ 1798.120) and applicability thresholds were **not opened → UNVERIFIED**. |
| **Colorado** HB24-1058 (eff. 7 Aug 2024) | Adds "biological data" (incl. **neural data**: central **or peripheral** nervous system, processable by a device) to CPA "sensitive data". The definition covers data "used or intended to be used, singly or in combination with other personal data, **for identification purposes**". | Sensitive-data **consent** rule and the "sale" definition in the CPA statute itself: **not opened (403) → UNVERIFIED**. Note the identification-purpose qualifier: whether research datasets meet it is an advokat question. |
| **Montana** SB 163 (2025) | Statute text **not opened** (legislature site 404/JS). | **UNVERIFIED**. Assume opt-in. |
| **HIPAA** | Binds only covered entities and business associates (market\regulation.md §3). NeuroForge collecting from its own contributors is probably neither. If data comes **from** a covered entity, it must be de-identified under 45 CFR 164.514(b) (Expert Determination or Safe Harbor) or shared under an authorisation. **hhs.gov (403) and eCFR (bot block) failed → UNVERIFIED.** Whether neural signals are a "unique identifying characteristic" under Safe Harbor is **UNVERIFIED**. Expect Expert Determination to be needed. | Avoid PHI-sourced data until US counsel reviews. |

State-law applicability thresholds (revenue / number of consumers) are **UNVERIFIED** for all four states.

## 6. EU AI Act Art. 5: buyer uses we must forbid

*Verified later the same day against the official text* (Publications Office, CELEX 32024R1689):
- 5(1)(f) prohibits AI "to infer emotions of a natural person in the areas of workplace and education institutions, except where the use of the AI system is intended to be put in place or into the market for medical or safety reasons";
- 5(1)(a) prohibits subliminal or purposefully manipulative techniques;
- 5(1)(c) prohibits social scoring;
- 5(1)(g) prohibits biometric categorisation to infer race, political opinions, trade-union membership, religious or philosophical beliefs, sex life or sexual orientation;
- Chapters I and II (including Art. 5) apply from **2 February 2025** (Art. 113(a)). GPAI obligations (Chapter V, Art. 53) apply from **2 August 2025**.
- Later amendments were not checked: **UNVERIFIED**.

Whether and when the AI Act applies in Norway through the EEA Agreement is **UNVERIFIED**. The licence bans these uses anyway, wherever the buyer is.

## 7. Reputational and strategic conflict

- **D1 (DECISIONS.md)** repositions NeuroForge around **neural-data governance**. The owner accepted it at GATE B.
- DPA § 3.4 promises never to sell customer data. AUP § 4.1 forbids **customers** from selling identifiable (including pseudonymised) neural data.
- A governance vendor that sells neural data would:
  - undermine the trust its paying customers (clinical device makers, CNS pharma) rely on;
  - invite the question "is my data next?";
  - risk the ledger business, which is the one demand driver rated SUPPORTED.
- The Chile Supreme Court neural-data deletion order (regulation.md §5) shows how visible this topic is.

## 8. Routes

| Route | Status | Conditions |
|---|---|---|
| Consent-based **research licence** of de-identified datasets **NeuroForge controls** (own contributors) | **Lawful, higher-effort, medium risk** | Separate opt-in for commercial licensing; DPIA; REK approval if health research; licensee = controller with own basis; no re-identification; deletion on withdrawal; transfer safeguards. Template: data-licence-agreement.*. |
| **Academic data-sharing** (controller-to-controller or joint controllers, Art. 26) | **Lawful, lower risk** | Ethics approval; purpose limitation; Art. 26 arrangement if purposes/means are jointly set. Template: academic-data-sharing-agreement.*. |
| **Synthetic datasets** generated from consented data | **Lower risk, not zero** | Consent must cover model training/synthesis; test memorisation and membership inference before release; still treat as personal data until shown otherwise. |
| Aggregate statistics / benchmarks (no row-level data) | **Lowest risk** | Minimum cell sizes; DPIA note. |
| Selling **identifiable or pseudonymised** neural data to **consumers or data brokers** without specific opt-in for sale | **HIGH risk / likely unlawful** | Violates Art. 9 (no condition), CT PA 25-113 (H), CCPA sale/limit rules; contradicts AUP § 4.1. **Not drafted.** |
| Any sale or reuse of **customer data held as processor** | **Prohibited** | DPA § 3.4; Art. 28(10). **Not drafted.** |
| Secondary sale beyond the consent scope (new buyer or purpose the person did not opt into) | **Prohibited** | Art. 5(1)(b) purpose limitation / Art. 9(2)(a) specific purposes; re-consent required. |
| Buyers doing **emotion inference in EU workplace or education**, manipulation, sensitive biometric categorisation | **Prohibited use** | AI Act Art. 5(1)(f) (official text verified); licence bans it. |
| Insurance, credit, employment, law-enforcement or "lie-detection" uses | **Refuse** | AUP § 4.2, § 6.3 policy. |
| Data sourced from HIPAA covered entities | **High risk until US counsel** | 164.514 de-identification or authorisation; UNVERIFIED. |

## 9. DPIA requirement (Art. 35)

A DPIA is required before processing that is "sannsynlig … vil medføre en høy risiko" (Art. 35(1)). Art. 35(3)(b) names **large-scale processing of special categories**. A neural-data collection-and-licensing programme will almost certainly need one. A DPIA also discharges the DPO-consultation duty in personopplysningsloven § 9 and § 10.

Minimum content:
- description of flows (collection → ledger → de-identification → licence → licensee);
- necessity and proportionality;
- a re-identification risk test of each release;
- licensee vetting;
- withdrawal propagation, including the limits: exports already sent cannot be recalled, and models are retrained, not certifiably unlearned;
- transfers (AWS US at launch, D4);
- residual risk. Consult Datatilsynet if high risk remains (Art. 36).

## 10. Recommendation

1. **Do not start a data-sales line now.** The company is pre-product and not incorporated. It has no DPO, no DPIA, no REK approval and no contributor base.
2. If the owner still wants it later, allow only:
   - (a) consent-based research licensing of **NeuroForge-controlled** de-identified datasets;
   - (b) academic sharing;
   - (c) synthetic or aggregate data.
   In each case: DPIA → advokat review → REK/IRB approval → pilot with one vetted academic licensee.
3. **Never** sell customer (processor) data, identifiable data, or data to consumers or data brokers.
4. Put a line in the website and pitch: "NeuroForge does not sell customer data." It is true, and it is the brand.

## Sammendrag på norsk

- **Kundedata kan ikke selges.** NeuroForge er databehandler for kundenes data (DPA § 3.4). Salg ville gjort oss til behandlingsansvarlig i strid med forordningen (art. 28 nr. 10) og brutt avtalen.
- **Lisensiering er bare mulig for datasett NeuroForge selv er behandlingsansvarlig for**, samlet inn med gyldig samtykke, eller som vi uttrykkelig har fått lov til å dele.
- **Nevrale data behandles som særlige kategorier (art. 9).** Det krever uttrykkelig samtykke for spesifikke formål (art. 9 nr. 2 a), eller forskningsunntaket (art. 9 nr. 2 j, art. 89, personopplysningsloven § 9). Forskningsunntaket dekker ikke salg.
- **Avidentifiserte nevrale signaler er normalt fortsatt personopplysninger.** EEG brukes som biometrisk kjennetegn. Risikoen for reidentifisering kan ikke settes til null.
- **Medisinsk og helsefaglig forskning krever REK-godkjenning** (helseforskningsloven § 9), og REK-godkjenning er ikke lenger behandlingsgrunnlag (Datatilsynet).
- **I USA regnes lisensiering mot betaling som «sale».** Connecticut krever samtykke før salg av sensitive data, og nevrale data er sensitive (PA 25-113). California gir rett til å begrense bruk (Civ. Code § 1798.121).
- **KI-forordningen art. 5** forbyr blant annet følelsesgjenkjenning på arbeidsplass og i utdanning (ordlyd UVERIFISERT).
- **Salg av data strider mot selskapets posisjonering som styringsverktøy (D1).**
- **Anbefaling:** Ikke bygg en forretningslinje for datasalg nå. Hvis det vurderes senere, bare samtykkebasert forskningslisensiering av egne datasett, akademisk deling eller syntetiske data. Det krever DPIA (art. 35), advokatgjennomgang og etikkgodkjenning først.

## Hjemmel / Legal basis
- GDPR (EU) 2016/679, Norwegian text on Lovdata (incorporated by personopplysningsloven § 1). Opened 2026-09-26:
  - Art. 4: https://lovdata.no/lov/2018-06-15-38/gdpr/a4
  - Art. 7: https://lovdata.no/lov/2018-06-15-38/gdpr/a7
  - Art. 9: https://lovdata.no/lov/2018-06-15-38/gdpr/a9
  - Art. 17: https://lovdata.no/lov/2018-06-15-38/gdpr/a17
  - Art. 19: https://lovdata.no/lov/2018-06-15-38/gdpr/a19
  - Art. 26: https://lovdata.no/lov/2018-06-15-38/gdpr/a26
  - Art. 28: https://lovdata.no/lov/2018-06-15-38/gdpr/a28
  - Art. 35: https://lovdata.no/lov/2018-06-15-38/gdpr/a35
  - Art. 46: https://lovdata.no/lov/2018-06-15-38/gdpr/a46
  - Art. 89: https://lovdata.no/lov/2018-06-15-38/gdpr/a89
  - Quotes are as returned by the fetch tool (some are summaries): **advokat to check verbatim**. EUR-Lex EN (legal-content/EN/TXT and TXT/HTML, CELEX:32016R0679) returned an empty page / HTTP 202. **Recital 26 verbatim UNVERIFIED.**
- Personopplysningsloven LOV-2018-06-15-38. Opened 2026-09-26:
  - § 5: https://lovdata.no/lov/2018-06-15-38/§5
  - §§ 8–9: https://lovdata.no/lov/2018-06-15-38/§9
  - § 10: https://lovdata.no/lov/2018-06-15-38/§10
- Helseforskningsloven LOV-2008-06-20-44 §§ 2, 4, 9, 13, 16, 29: https://lovdata.no/dokument/NL/lov/2008-06-20-44 and https://lovdata.no/lov/2008-06-20-44/§4 (opened 2026-09-26). The broad-consent provision is **UNVERIFIED**.
- Datatilsynet, "Helse- og forskningsprosjekter": https://www.datatilsynet.no/personvern-pa-ulike-omrader/forskning-helse-og-velferd/helse-og-forskningsprosjekter/ (opened 2026-09-26). The Datatilsynet anonymisation guide URLs tried returned 404: **UNVERIFIED**.
- Connecticut PA 25-113: https://www.cga.ct.gov/2025/ACT/PA/PDF/2025PA-00113-R00SB-01295-PA.PDF (opened 2026-09-26 via download; site TLS certificate failed verification in the fetch tool). Covers the neural data definition, sensitive data (G), controller duties (D), (G), (H), and the sale definition.
- California SB 1223: https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202320240SB1223 and Civ. Code § 1798.121: https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CIV&sectionNum=1798.121 (opened 2026-09-26). § 1798.120 is **UNVERIFIED**.
- Colorado HB24-1058: https://leg.colorado.gov/bills/hb24-1058 (opened 2026-09-26). The CPA statute consent and sale text is **UNVERIFIED** (signed-bill PDFs returned 403).
- Montana SB 163: **UNVERIFIED** (archive.legmt.gov / leg.mt.gov 404).
- HIPAA 45 CFR 164.514: **UNVERIFIED** (hhs.gov de-identification page 403; eCFR redirected to a bot check).
- EU AI Act 2024/1689 Art. 5, 53, 113 and the GDPR Recitals: official texts obtained by content negotiation from the Publications Office (opened 2026-09-26 by nfb-legal-privacy):
  - http://publications.europa.eu/resource/celex/32024R1689
  - http://publications.europa.eu/resource/celex/32016R0679
  - request header Accept: application/xhtml+xml.
  EEA incorporation of the AI Act is **UNVERIFIED**.
- Follow-up documents: BROAD-CONSENT-ASSESSMENT.md, CONSENT-SCOPES.*, RETENTION-POLICY.*, investor\DATA-STRATEGY-QUESTIONS-FOR-PRIVACY.md (model ratings).
- EEG biometrics reviews via PubMed E-utilities (opened 2026-09-26): doi:10.1155/2021/5229576 (PMID 34976039) and doi:10.1155/ijta/3946740 (PMID 39949891); abstracts only.
- Product facts: architecture\BLUEPRINT.md §8.3–8.4 (consent ledger, deletion propagation, crypto-shredding, no certified unlearning, exports not recallable); DECISIONS.md D1, D4; legal\commercial\dpa.en.md § 3.4, § 11, § 13; aup.en.md § 1, § 2, § 4.
