> DRAFT – not legal advice. Questions from nfb-data-strategy to nfb-legal-privacy. Must be reviewed by a Norwegian lawyer (advokat) before any reliance.

# Data-revenue strategy: questions for the privacy lawyer

From: nfb-data-strategy · To: nfb-legal-privacy · 2026-09-26
Main deliverable: C:\Users\mariu\neuro-company\investor\DATA-REVENUE-STRATEGY.md

**How to answer:** put a one-line receipt under "Receipt", then fill the "Lawyer rating" column (low / medium / high / REJECT) and add notes under each question. A SendMessage reply to nfb-data-strategy also works.

## Receipt
- [x] nfb-legal-privacy: received 2026-09-26 via nfb-legal; answered below the same day. The ratings are an **AI legal-team draft, not advokat advice**.

## Context you need (from the drafts that already exist)
- NeuroForge Bio is a **processor** for customer data.
  - DPA §3.4: no use for own purposes, no training, no selling, no combining.
  - MSA §4.3: **no training on Customer Data without a separate, specific, written opt-in**.
  - MSA §4.4: limits Aggregated Service Metrics to content-free operational data.
- The consent-ledger scopes designed today (BLUEPRINT §8.3; BUILD-GUIDE 5.3) are: collection, processing, sharing, model training, commercial use.
- Deletion: crypto-shredding; models flagged `retrain_required`; no certified unlearning (BLUEPRINT §8.4).

## Models and provisional risk ratings
| # | Model | My provisional rating | Lawyer rating (nfb-legal-privacy) |
|---|---|---|---|
| 1 | Compute-to-data / federated analysis (data stays in the customer tenant; only approved aggregate outputs leave) | Low–medium | **LOW–MEDIUM**: lawful as proposed |
| 2 | Data clean rooms for CNS pharma trials (sponsor + site data joined under policy; outputs aggregate only) | Medium | **MEDIUM**: lawful if sponsor bases cover the joins |
| 3 | Differential-privacy query API + aggregated insight reports over the opt-in pool | Medium | **MEDIUM**: lawful only once the pool is lawful (consent ii) |
| 4 | Synthetic neural datasets generated from the pool | Medium (membership-inference risk untested) | **(i) simulator: LOW. (ii) pool-trained: MEDIUM**: no release before tests |
| 5 | Neural foundation model trained on consented, licensed data (API / licence) | High | **HIGH** (pool data); **MEDIUM** (public-data-only). Not lawful on broad consent alone |
| 6 | Data cooperative / trust with contributor royalties | Medium–high | **MEDIUM–HIGH**: DEFER; payments must be designed carefully |
| 7 | Curated benchmark datasets + held-out leaderboards with sponsorship | Low–medium | **LOW** (public tracks) / **MEDIUM** (held-out pool tracks) |
| 8 | Dataset certification / "consent-verified" label | Low (liability/misleading-claim risk) | **LOW** privacy / **MEDIUM** claim risk: rename to "attestation report" |
| 9 | Governed marketplace commission on third-party datasets | High | **HIGH**: DEFER (only public/CC0 or aggregate outputs) |
| 10 | Research partnerships / co-authored studies | Low–medium | **LOW–MEDIUM**: use academic DSA |
| 11 | Grants | Low | **LOW** (no data issue) |
| 12 | CRO / pharma endpoint analytics (processor) | Low–medium | **LOW–MEDIUM**: no PHI until BAA exists |
| 13 | Licensing somatosensory research IP | Low privacy risk | **LOW** |
| 14 | Insurance / employer uses | **REJECT** | **REJECT** (confirmed; AI Act Art. 5(1)(f) verified) |
| 15 | Selling/licensing raw or pseudonymised customer data | **REJECT** | **REJECT** (confirmed; DPA §3.4, GDPR Art. 28(10)) |
| 16 | Post-trial data stewardship / escrow | Low–medium | **LOW–MEDIUM**: needs a successor-controller mechanism |

### Per-model legal basis, safeguards, verdict (nfb-legal-privacy)

**Common legal frame.** All article numbers refer to the official GDPR / AI Act texts, which were opened this time; see "Sources" below.
- **Anonymisation.** Pseudonymised data "should be considered to be information on an identifiable natural person". The test is "all the means reasonably likely to be used, such as singling out" (Recital 26). Only truly anonymous output leaves GDPR.
- **Research counts broadly.** Scientific research "should be interpreted in a broad manner including … technological development and demonstration … applied research and privately funded research" (Recital 159). NeuroForge's R&D *can* be scientific research. That is not the same as commercial exploitation.
- **Art. 9 condition.** Every NeuroForge-as-controller use needs one: explicit consent (9(2)(a)) or 9(2)(j) plus personopplysningsloven § 9. § 9 requires that "samfunnets interesse … klart overstiger ulempene", plus DPO consultation or a DPIA.
- **Health research in Norway.** Health-directed research falls under helseforskningsloven (REK approval § 9, consent § 13/§ 14).
- **US.** Connecticut PA 25-113 (neural data is sensitive data; consent to process; no sale without consent; "sale" means exchange for consideration). California SB 1223 plus Civ. Code 1798.121 (right to limit; broad "sell"). Colorado HB24-1058 (sensitive "biological data" used for identification). **The CPA text and Montana SB 163 are UNVERIFIED.**
- **HIPAA.** Only relevant for data from US covered entities or business associates. 164.514 is **UNVERIFIED** (hhs.gov and eCFR blocked).

| # | Legal basis (who is controller) | Required safeguards | Lawful as proposed? |
|---|---|---|---|
| 1 | **Holder is controller**; NeuroForge is processor (Art. 28) with the holder's Art. 6/9 basis. The analysing partner receives only outputs. If outputs are anonymous (Recital 26), GDPR does not apply to them. If not, the release is a disclosure needing the holder's basis and the subject's "sharing" scope. US: disclosure for consideration of non-anonymous outputs could be a "sale" (CT/CA). | Minimum cell sizes and an output-checking policy; code review / sandboxing of submitted pipelines (exfiltration risk); no row-level export; a partner terms addendum (AUP, no re-identification, AI Act Art. 5 ban); audit log of every release. | **Yes**, with a release policy (a NEW step). The best-fit model. |
| 2 | **Sponsor/sites are controllers** under trial consent and trial law (CTR/national law **UNVERIFIED**). NeuroForge is processor to each. Joining sponsor and site data may make them **joint controllers (Art. 26)**; they must arrange that. REK approval (helseforskningsloven § 9) sits with the sponsor. | A DPA per party; a written join policy approved by all controllers; aggregate-only outputs; Part 11 / GCP controls (**UNVERIFIED**); no NeuroForge secondary use. | **Yes**, if the sponsor's consent and approvals cover the joins. |
| 3 | **NeuroForge is controller of the pool.** Needs Art. 9(2)(a) explicit consent naming NeuroForge (consent box ii) or 9(2)(j) + pol. § 9 (weak for a company, so use consent). DP outputs *may* be anonymous; not assessed against any regulator guidance, so **UNVERIFIED**. US: DP aggregates are probably not "personal data", so probably not a "sale", but **UNVERIFIED** (CT/CA de-identified-data definitions not opened). | A published epsilon policy and privacy-budget accounting per querier; DPIA (Art. 35); researcher vetting; query terms banning re-identification and Art. 5 uses; pool data only from subjects with box (ii) and, if sold, the commercial box. | **Only after the pool is lawful** (consent, DPIA, REK where health research). |
| 4 | (i) No personal data. (ii) Training a generator on Art. 9 data needs a training scope (box iii) and, if sold, the commercial box. The generator and its output count as personal data until tests show otherwise (Recital 26 "singling out"). | Membership-inference and nearest-record / singling-out tests with thresholds set in the DPIA; publish the report; no release on failure; a licence banning re-identification. | (i) **Yes**. (ii) **Yes, after tests pass.** |
| 5 | Pool version: Art. 9(2)(a) consent **specifically** for training models licensed to third parties, plus commercial use (**broad consent is not enough**; see BROAD-CONSENT-ASSESSMENT). Public-data version: CC0/CC-BY answers copyright, **not** GDPR. EU-subject public EEG remains personal data. NeuroForge needs its own basis (9(2)(j) + pol. § 9 for research, and the original dataset's consent/terms must permit reuse). **AI Act:** a "general-purpose AI model" is one that "displays significant generality and is capable of competently performing a wide range of distinct tasks" (Art. 3(63)). If placed on the market, Art. 53 applies: technical documentation, downstream information, a copyright policy, and a "sufficiently detailed summary about the content used for training". Chapter V has applied since 2 Aug 2025. Pure research models are excluded (Art. 2(6)). Whether an EEG representation model meets "significant generality" is an open question. | Model-licence terms carrying consent restrictions downstream (template deferred by CEO ranking; use data-licence § 3.3 restrictions); a registry use-restriction flag; `retrain_required` on withdrawal; SISA shards; memorisation tests; Art. 53 documentation if GPAI; the licensee's Art. 5 ban. | **Not as "broad consent"**. Yes only with the specific licensed-training + commercial opt-ins. Public-data-only first is right. |
| 6 | The trust/cooperative is its own controller, with Art. 9(2)(a) consent to the trust. Payments raise voluntariness issues: consent is not free if the person "is unable to refuse or withdraw consent without detriment" (Recital 42), and Art. 7(4) covers conditionality. Payments are "valuable consideration", so US "sale" rules apply. Tax/NAV treatment and cooperative law are **UNVERIFIED**. | No clawback of paid royalties on withdrawal; modest, non-contingent amounts; independent governance; a contributor agreement (template deferred together with A6). | **Possibly**, but DEFER until advokat, tax advice and entity choice. |
| 7 | Public tracks: licence compliance (CC-BY attribution); GDPR still applies to EU-subject data. Held-out tracks: pool rules (as #3). | Attribution; no redistribution of held-out data; compute-to-data only; "evaluation report", never "certified". | **Yes**. |
| 8 | NeuroForge is processor for the dataset owner. Claim risk: GDPR has a formal certification scheme (Art. 42, **not opened, UNVERIFIED**). Markedsføringsloven is **UNVERIFIED**. | Title: "Consent-coverage attestation report"; state what the ledger records at time T; not a legal opinion or certification; liability cap. | **Yes**, with that wording. |
| 9 | NeuroForge taking a commission for "making available" data risks being a party to a "sale" (CA "sell" includes "making available … for … valuable consideration"; CT sale definition). It also risks controller status. | Only public/CC0 datasets or aggregate outputs via compute-to-data. | **Not as proposed**. DEFER. |
| 10 | Partner is controller, or joint controllers (Art. 26). REK/IRB with the partner. | academic-data-sharing-agreement.*; publication de-identification. | **Yes**. |
| 11 | n/a | n/a | **Yes** (after incorporation). |
| 12 | Processor (Art. 28) for the sponsor. HIPAA: no PHI until a BAA exists (BAA PLANNED). | DPA; sponsor's approvals; no clinical claims. | **Yes**. |
| 13 | No personal data (simulation). | Keep it computational (BRIEF). | **Yes**. |
| 14 | AI Act Art. 5(1)(f) bans AI "to infer emotions of a natural person in the areas of workplace and education institutions, except where … for medical or safety reasons". 5(1)(c) social scoring. CT/CA/CO sensitive data. Power imbalance means consent is not free (Recital 42). | — | **REJECT**. |
| 15 | DPA § 3.4; a processor that sets its own purposes "skal … anses for å være en behandlingsansvarlig" (Art. 28(10)); pseudonymised data is personal data (Recital 26). | — | **REJECT**. |
| 16 | NeuroForge is processor for the sponsor. If the sponsor fails, someone must become controller: name a successor controller (e.g. a hospital) in the trial consent, or get participant consent to transfer to NeuroForge as custodian-controller. | Tri-party escrow agreement; trigger events; participant notice. | **Yes**, with a successor-controller clause. |

**Proposed new scopes.**
- *internal R&D*: acceptable as a **separate** scope. For customer (processor) data it also needs the MSA §4.3 written opt-in, and NeuroForge then becomes controller for that copy, so the subject's consent must name NeuroForge.
- *Future biotech/neurobiology research*: **too vague as worded.** Narrow it, and never let it cover commercial licensing or third-party model training. See legal\data-agreements\BROAD-CONSENT-ASSESSMENT.md.
- *Model training split (internal / licensed to third parties)*: **agreed**.

## Proposed new consent scopes (additions to the ledger)
- **internal R&D**: NeuroForge may use the record to develop and test its own software (pipelines, QC, benchmarks). No third-party access.
- **future biotech/neurobiology research**: broad consent to future scientific research in neuroscience, neurobiology and biotech, including AI training, by NeuroForge or approved research partners, under ethics approval where required.
- Also proposed: split existing "model training" into **model training – internal** and **model training – licensed to third parties**; keep "commercial use" as a separate explicit tick.

## Questions
1. **Controller role for the pool.** For an opt-in research pool, NeuroForge must become a (joint?) controller for the pooled copy. Is the correct structure: customer (controller) obtains Art 9(2)(a) explicit consent covering transfer to NeuroForge as an independent controller for research, plus a separate data-sharing agreement? Or should contributors consent directly to NeuroForge?
   - **Answer:**
     - **Both layers are needed.** (a) The data subject gives explicit consent that **names NeuroForge as a separate controller** for the pool (consent box ii). The customer may collect it on NeuroForge's behalf through the ledger, but consent must identify the controller: the person should be "aware at least of the identity of the controller and the purposes" (Recital 42). (b) The customer signs a **Research Pool Addendum** (the MSA §4.3 written opt-in) authorising the disclosure.
     - NeuroForge and the customer are **separate controllers**, not joint, unless they jointly set the pool's purposes and means.
     - Existing consents that name only the customer **do not suffice**.
2. **Art 5(1)(b) compatibility / Art 89.** Can pooled data collected for a customer's study be re-used for NeuroForge research under the "further processing for scientific research … shall not be considered incompatible" rule, or does the Art 9 status force fresh explicit consent? Which Norwegian law (personopplysningsloven §9? helseforskningsloven?) supplies the Art 9(2)(j) basis and safeguards?
   - **Answer:**
     - Art. 5(1)(b) (verified) solves **purpose limitation only**. A **new controller** still needs its own Art. 6 basis and Art. 9(2) condition.
     - The Norwegian 9(2)(j) basis is personopplysningsloven § 9. It requires necessity, that society's interest "klart overstiger ulempene for den enkelte", Art. 89(1) safeguards, and prior DPO consultation or a DPIA.
     - For a commercial company's pool that balancing is **weak**, so use fresh explicit consent.
     - If the research is health research, helseforskningsloven also applies: REK approval (§ 9) and consent (§ 13), unless REK grants an exemption (not opened: **UNVERIFIED**).
3. **Recital 33 broad consent.** Is "future biotech/neurobiology research" narrow enough to be valid broad consent in Norway? Does it cover AI training for commercial models, or does commercial licensing need its own specific tick?
   - **Answer:** **Not as worded.**
     - Recital 33 allows consent "to certain areas of scientific research when in keeping with recognised ethical standards".
     - helseforskningsloven § 14 allows broad consent to "nærmere bestemte, bredt definerte forskningsformål". REK "kan sette vilkår" and "pålegge … nytt samtykke", and participants have "krav på jevnlig informasjon".
     - "Biotech" is too open. Name the areas, e.g. "research on brain and nerve signals to understand how the nervous system works and neurological conditions".
     - It does **not** cover commercial licensing or third-party model training. Each needs its own tick.
4. **Helseforskningsloven scope.** Is research on neural signals (EEG/ECoG) whose purpose is "new knowledge about health and disease" medical/health research requiring REK pre-approval, even if performed purely computationally on existing data?
   - **Answer:** **Probably yes**, as a literal reading.
     - § 2 covers research on "helseopplysninger", and § 4 defines the research by its aim: "ny kunnskap om helse og sykdom". The method (computational or not) is not the test.
     - Pure engineering work (signal quality, compression) on healthy volunteers is probably outside the Act.
     - Borderline cases: ask REK for a remit assessment (**UNVERIFIED** procedure).
5. **Derived features / embeddings.** Are embeddings from a model trained on neural data personal data if linkable via a subject pseudonym? Does deleting the key (crypto-shredding) make the rest anonymous?
   - **Answer:**
     - **Linkable embeddings are personal data** (Art. 4(5); Recital 26).
     - Distinguish two keys. **Destroying the encryption key** (crypto-shredding) makes the ciphertext unreadable, which is effectively deletion. **Destroying only the pseudonym-mapping key** leaves plaintext vectors. Those are **not automatically anonymous**, because neural features can themselves single out a person: EEG is used as a biometric (doi:10.1155/2021/5229576). An anonymity claim needs a documented test.
6. **Synthetic data.** What test (e.g. membership-inference / singling-out) would you accept before treating synthetic neural data as anonymous?
   - **Answer:** A documented Recital 26 assessment with four tests:
     - (a) membership-inference advantage close to chance against a strong attacker;
     - (b) distance-to-closest-record / near-duplicate checks against training data;
     - (c) a linkage test: run an EEG biometric matcher against held-out recordings of the training subjects;
     - (d) attribute-inference checks.
     Thresholds go in the DPIA; publish the report. The EDPB/Art. 29 WP anonymisation criteria (singling out, linkability, inference) are **UNVERIFIED** (not opened).
7. **Royalties to contributors.** Do payments to data subjects undermine "freely given" consent (Art 7(4)) or create tax/employment issues? Credits vs cash?
   - **Answer:**
     - Payment itself is not banned. What matters is that the person can refuse or withdraw "without detriment" (Recital 42).
     - Rules: no clawback of accrued amounts; the same pay whatever optional boxes are ticked; modest amounts; no bonus for the commercial box.
     - Credits paid to B2B customers are simpler than cash paid to individuals.
     - Tax and NAV treatment: **UNVERIFIED**.
     - In the US, payment may make the flow a "sale" that needs opt-in (CT/CA).
8. **US states.** Under CO/CA/CT, is a DP-aggregate report "sale" of sensitive data? Does CA "limit use" block pool contribution by default?
   - **Answer:**
     - **Sale:** probably not, if the output is not personal data. The de-identified/aggregate definitions were not opened, so **UNVERIFIED**.
     - **CA "limit use":** **yes, treat it as blocking.** 1798.121 lets a consumer direct a business to limit use to what is "necessary to perform the services … reasonably expected". Pool contribution is not that, so the default-OFF design is right, and the `limit_use` flag must exclude the subject.
9. **AI Act.** Is a neural foundation model a general-purpose AI model with provider obligations? Any Art 5 exposure if a licensee fine-tunes for emotion inference?
   - **Answer:**
     - **GPAI:** possibly (see #5). If it is placed on the market, Art. 53 applies.
     - **Art. 5:** it prohibits "placing on the market, putting into service … or use" of emotion-inference AI in workplace or education. A licensee doing that breaches Art. 5.
     - NeuroForge should ban it by contract, flag it in the registry, and terminate on breach. Knowingly supplying for that purpose is a serious risk.
     - EEA incorporation into Norwegian law: **UNVERIFIED**.
10. **MSA §4.3 opt-in.** Is the drafted written opt-in sufficient as the contractual gate for pool contribution, or should a separate "Research Pool Addendum" exist?
    - **Answer:** Use a **separate Research Pool Addendum**. It is the §4.3 written opt-in, listing datasets, purpose, de-identification, duration and revocation. Ledger consent per subject is still needed; the contract does not replace it.
11. **Brand/misleading-claim.** Is a "consent-verified" label a certification claim that conflicts with BOARD rule "never certified"? Suggested wording?
    - **Answer:** Yes, it reads like a certification (compare GDPR Art. 42 schemes, **UNVERIFIED**). Suggested wording: "Consent-coverage attestation report: records in NeuroForge's consent ledger for dataset [X] as at [date]. Not a certification or legal opinion."

## Lawyer notes
- Consent boxes (i)–(v) plus a separate commercial box are implemented in legal\data-agreements\contributor-consent.{en,no}.md.
- Broad-consent limits: legal\data-agreements\BROAD-CONSENT-ASSESSMENT.md.
- Retention: legal\data-agreements\RETENTION-POLICY.{en,no}.md.
- Scope mapping for engineering: legal\data-agreements\CONSENT-SCOPES.{en,no}.md.
- Model clauses (CEO ranking):
  - A1/A12: legal\data-agreements\dpa-addendum-compute-to-data-cro.{en,no}.md
  - A8: legal\data-agreements\attestation-report-terms.{en,no}.md
  - A10/A7: academic-data-sharing-agreement.{en,no}.md § 13
  - Research Pool Addendum: legal\commercial\research-pool-addendum.* (nfb-legal-commercial)
- Clean-room, royalty/cooperative and model-licence templates are deferred (A6/A9 deferred). For #5, the consent restrictions for downstream model licences are box (vi) plus data-licence § 3.3; a full model-licence template is still to do.

**Sources (opened 2026-09-26 by nfb-legal-privacy):**
- GDPR official text, obtained by content negotiation from the Publications Office (http://publications.europa.eu/resource/celex/32016R0679, Accept: application/xhtml+xml): Recitals 26, 33, 42, 159; Art. 5(1)(b),(e); 12(3); 35(1).
- GDPR Norwegian text on Lovdata: Art. 7, 9, 26, 28 (https://lovdata.no/lov/2018-06-15-38/gdpr/a9 etc.).
- AI Act official text (http://publications.europa.eu/resource/celex/32024R1689): Art. 2(6), 3(63), 5(1), 53(1), 113.
- Personopplysningsloven § 9: https://lovdata.no/lov/2018-06-15-38/§9
- Helseforskningsloven §§ 2, 4, 14, 16, 17: https://lovdata.no/lov/2008-06-20-44/§14
- CT PA 25-113: https://www.cga.ct.gov/2025/ACT/PA/PDF/2025PA-00113-R00SB-01295-PA.PDF
- CA SB 1223 and Civ. Code 1798.121 (leginfo.legislature.ca.gov)
- CO HB24-1058: https://leg.colorado.gov/bills/hb24-1058

**UNVERIFIED:** CO CPA text; MT SB 163; HIPAA 164.514; CT/CA de-identified-data definitions; GDPR Art. 42; tax/NAV; clinical-trial law; AI Act EEA status.
