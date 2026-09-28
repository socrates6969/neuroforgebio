> **NOT LEGAL ADVICE.** Planning document for product and investor use. Every legal statement below is a planning assumption that a Norwegian lawyer (advokat) and US counsel must review before anyone relies on it.
> **Risk ratings were reviewed by nfb-legal-privacy on 2026-09-26.** Its ratings and its answers to Q1–11 are in `investor\DATA-STRATEGY-QUESTIONS-FOR-PRIVACY.md`, and they override the ratings in this file where the two differ. Key rulings: A5 foundation model is HIGH on pool data and MEDIUM when trained on public data only, and broad consent alone is not enough. A7 is LOW for public tracks. A8 has LOW privacy risk but MEDIUM claim risk, so it is renamed 'attestation report' and the word 'certified' is not used. A9 and A6 are deferred. R1 and R2 are confirmed REJECT. The ratings are an AI legal-team draft, **not advokat advice**. A Norwegian lawyer must confirm them before we rely on them. **Update (nfb-legal, final ratings):** the ratings are now final. The *future biotech/neurobiology research* scope is narrowed to nervous-system research, and each health-research project still needs REK approval. The templates are in `legal\data-agreements\` (CONSENT-SCOPES, DPA addendum for compute-to-data and CRO work, attestation-report terms), the academic DSA §13, and `legal\commercial
esearch-pool-addendum.*`.

# NeuroForge Bio: lawful data-revenue strategy

Owner: Marius Carlsson · Prepared by nfb-data-strategy (an AI agent, not a team member) · 2026-09-26 · Status: pre-product. There are no customers, data, partners or revenue.

## 0. Principles (these govern every model below)

1. **We sell tools, governance and consented, aggregate outputs. We never sell people's data.** Today NeuroForge is a *processor*. DPA §3.4 says we do not use Customer Personal Data "for its own purposes; train models on it; sell it; or combine it with other customers' data". MSA §4.3 bans training on Customer Data unless the customer gives "a separate, specific, written opt-in" (legal\commercial\dpa.en.md, msa.en.md). Every model here either works inside that processor role or needs a **new, separate, opt-in legal channel** in which NeuroForge becomes a controller for a consented research copy.
2. **Default OFF.** Nothing flows into any pool unless the customer (the controller) opts in and the data subject has given the matching consent scope, recorded in the consent ledger (BLUEPRINT §8.3) and enforced by the single policy function (BUILD-GUIDE 5.4).
3. **Withdrawal always works.** Pooled data remains subject to deletion propagation, crypto-shredding and `retrain_required` flags on models (BLUEPRINT §8.4). We never claim certified unlearning.
4. **No data-broker optics.** We take no commission on raw personal data, sell no individual-level records, and serve no insurer, employer, advertiser or law-enforcement buyer.
5. All money figures are **ESTIMATE** with a stated method. The base-case finance model (investor\financial-model.csv; base Y5 end ARR $4.54M) **does not** include the pool-based revenue here. Part C is an **UPSIDE scenario**.

### Sources opened for this file (grade)
| Source | What it supports | Grade |
|---|---|---|
| gdpr-info.eu Art 5, Art 89, Recital 33 (unofficial consolidation; EUR-Lex failed to load for the legal team, per legal\BOARD.md) | Art 5(1)(b) research-compatibility clause; 5(1)(e) storage limitation; 89(1) safeguards, 89(2) derogations; Recital 33 broad consent to "certain areas of scientific research" | B (primary text via secondary host) |
| lovdata.no/dokument/NL/lov/2008-06-20-44 (helseforskningsloven) | §2 scope; §4 definition; §§9–10 REK pre-approval; §13 consent; §14 broad consent; §25 ff. research biobanks | A |
| lovdata.no/dokument/NL/lov/1993-04-02-38 (genteknologiloven) | §1 purpose; §2 scope; §4 definitions; §6 contained-use facility approval; §7 approval cases; §§9–10 release | A |
| forskningsetikk.no page on helseforskningsloven | Consent exceptions only where research is "of substantial interest to society" and participant welfare is safeguarded (§15, §28, §35) | B |
| forskningsradet.no/skattefunn | Eligibility: "registrert i Brønnøysundregisteret og er skattepliktig til Norge"; deduction "19 prosent av kostnadene"; apply before 1 Sep for same-year deduction | B (official programme page) |
| innovasjonnorge.no/tjeneste/oppstartstilskudd-1 | AS younger than 5 years; max NOK 150,000; market-test activities | B |
| eic.ec.europa.eu EIC Accelerator | SMEs/start-ups from EU and "countries associated to the Horizon Europe programme"; grant "below EUR 2.5 million", TRL 6–8; equity "€1 – €10 million" | B |
| aws.amazon.com/s3/pricing (US East N. Virginia) | S3 Standard first 50 TB $0.023; Standard-IA $0.0125; Glacier Instant Retrieval $0.004; Glacier Flexible Retrieval $0.0036; Glacier Deep Archive $0.00099 per GB-month | D |
| artificialintelligenceact.eu/article/5 | Emotion inference in "workplace and education institutions" prohibited "except … for medical or safety reasons" | B (the page's letter labels rendered inconsistently. We keep "5(1)(f)" as in market\regulation.md §5, and counsel must confirm it against EUR-Lex) |
| api.dandiarchive.org (queried 2026-09-26) | 434 published dandisets: **400 CC-BY-4.0, 33 CC0-1.0, 1 both** | A-level fact (live API) |
| openneuro.org GraphQL (queried 2026-09-26; **partial**: first 1,100 of ~1,902 datasets before a server error) | 975 "CC0" plus ~40 more public-domain variants (PDDL/PD/CCO), 51 with no licence field, a handful CC-BY / CC-BY-SA. Of those tagged EEG/iEEG/MEG: **297 of 299 CC0** | A-level fact (live API, partial) |
| Internal: market\regulation.md, sizing.md, new-ideas.md, pricing-and-gtm.md, landscape.md; architecture\BLUEPRINT.md §3.6, §3.7, §6, §8, §12; BUILD-GUIDE.md; legal\commercial\*.en.md; research\somatosensory\STATUS.md, RESULTS_*.md | As cited inline | internal |

**Not opened, so UNVERIFIED:** EUR-Lex official texts; SkatteFUNN annual cost cap (the page opened shows none); Forskningsrådet's "Innovasjonsprosjekt i næringslivet" (URL returned 404); Norway's Horizon Europe association (the EC PDF was not extractable); biobank regulations beyond §25 ff.; Montana SB 163 text; US state treatment of DP aggregates as a "sale".

---

## Part A: revenue models (15 evaluated, 2 rejected)

Key to fields. **Risk** = legal/regulatory risk (low/medium/high), per nfb-legal-privacy (see the banner above). **Scopes** = consent-ledger scopes. The designed scopes are collection, processing, sharing, model training and commercial use (BUILD-GUIDE 5.3). The proposed new scopes, *internal R&D* and *future biotech/neurobiology research*, are defined in Part B. **Deps** = BUILD-GUIDE step numbers. A "NEW" dependency is a step that is not yet in the guide. **Y5** = year-5 annual revenue, ESTIMATE. It is incremental to the base-case model unless it says "overlaps base".

### A1. Compute-to-data / federated analysis
- **How:** data never leaves the customer's tenant, or the customer's own cloud (VPC). A partner submits a versioned pipeline (BLUEPRINT §3.5). It runs where the data sits, and only outputs that pass policy (aggregates, model metrics) are released, with full provenance.
- **Who pays:** the analysing party (pharma, device maker, academic consortium) pays per run or per seat. The data holder pays a platform add-on.
- **Pricing (ESTIMATE):** add-on of $25k–$75k/yr per data-holding tenant, plus $2k–$10k per external study. Anchored to the Growth/Enterprise bands in pricing-and-gtm.md §2.
- **Y5 (ESTIMATE):** $0.1M–$1.5M. Method: 4–20 S1/S4 tenants (sizing.md §3 counts 80–150 S1 and 50–150 S4) × $25k–$75k.
- **Legal:** NeuroForge stays a **processor**. The data holder decides and has the lawful basis, and nothing is transferred. Art 9 still applies to the holder. Release outputs must not single out individuals. **Risk: LOW–MEDIUM.**
- **Scopes:** processing + sharing (aggregate outputs only) on the holder's subjects. No new scope needed.
- **Brand:** strongly positive ("your data never leaves").
- **Deps:** 2.1–2.3, 3.1–3.5, 4.1, 5.4. NEW: output-release policy (aggregate thresholds) and a partner-submission workflow.

### A2. Data clean rooms for CNS pharma trials
- **How:** a sponsor, sites and a CRO each keep their data in governed workspaces. Approved joins and analyses (EEG endpoint derivation, QC) run under a policy that only releases aggregate or sponsor-owned outputs. Every operation is logged and exported for audit.
- **Who pays:** CNS sponsors and CROs (sizing.md S4).
- **Pricing (ESTIMATE):** $50k–$150k per programme per year on top of an Enterprise tier ($100k–$300k, pricing-and-gtm.md §2).
- **Y5 (ESTIMATE):** $0.1M–$0.9M. Method: 2–6 programmes × $50k–$150k. **Overlaps the base model's S4 line.** Count only the add-on.
- **Legal:** processor or sub-processor to the sponsor. Clinical-trial data raises Part 11, GCP and national trial law (not researched). In Norway, research with a health purpose falls under helseforskningsloven and needs REK pre-approval (§§9–10, opened), which the sponsor obtains. **Risk: MEDIUM.**
- **Scopes:** processing + sharing (within the trial consent held by the sponsor).
- **Brand:** positive. It is the Flywheel pattern (landscape.md) applied to EEG.
- **Deps:** 2.1–2.8, 3.1, 5.2–5.4, 5.8. NEW: multi-party workspace, Part 11 e-signature (not in guide).

### A3. Differential-privacy query API + aggregated insight reports
- **How:** over the **opt-in research pool** (Part B-a), approved researchers run DP-noised queries, for example normative spectral distributions by age band and device class. Annual "State of neural data" reports publish only DP aggregates and metadata statistics (channel counts, formats, QC failure rates).
- **Who pays:** device makers (normative references), pharma (feasibility), academics (lab tier).
- **Pricing (ESTIMATE):** $1k–$5k/mo per API subscriber; report sponsorship not priced (no comparable opened).
- **Y5 (ESTIMATE):** $0–$0.6M. Method: 0–10 subscribers × $12k–$60k/yr. The low end is zero because the pool may never reach a useful size.
- **Legal:** the pool copy is personal data (Art 9), with NeuroForge as controller. DP outputs are probably anonymous if epsilon is chosen well, but that is **unverified**. Art 89(1) requires "appropriate safeguards". Under US CO/CA/CT, whether releasing DP aggregates is a "sale" of sensitive data is **unverified**. **Risk: MEDIUM.**
- **Scopes:** *future biotech/neurobiology research* (NEW) + sharing (aggregate only). Commercial use is required if the output is sold.
- **Brand:** neutral to positive if we publish the epsilon budget and methodology. Negative if it is framed as "we monetise your brain data".
- **Deps:** 5.3–5.5 and the pool. NEW: DP engine + privacy-budget accounting.

### A4. Synthetic neural datasets
- **How:** two products. (i) Simulator-based synthetic data from the BUILD-GUIDE 0.6 generator: no personal data, known ground truth, **zero privacy risk**. (ii) Pool-trained generative models that produce realistic multichannel EEG/ECoG. For (ii), the privacy value is a **hypothesis** (new-ideas.md #7 caveat), and nothing ships before membership-inference tests pass.
- **Who pays:** BCI software QA teams, device-maker regulatory/QA, educators.
- **Pricing (ESTIMATE):** $1k–$5k/mo (new-ideas.md #7), or $5k–$25k per curated dataset licence.
- **Y5 (ESTIMATE):** $0.05M–$0.6M. Method: 4–10 licensees × $12k–$60k.
- **Legal:** (i) **LOW**. (ii) **MEDIUM**: a generator trained on Art 9 data is itself possibly personal data until tested, and the training needs a *model training – internal* scope.
- **Scopes:** (i) none. (ii) *model training – internal* + *future biotech/neurobiology research*; commercial use when the output is sold.
- **Brand:** positive ("privacy-safe test data"), provided we publish the attack results.
- **Deps:** 0.6 for (i). 5.3–5.5, 6.1, 6.3 and NEW generative training plus an MIA test harness for (ii).

### A5. Neural foundation model on consented, licensed data (API / licensing)
- **How:** pre-train an EEG/ECoG representation model on the pool plus permissively licensed public data (DANDI CC-BY/CC0, OpenNeuro CC0; see Part B-c) and license it through the governed registry (BLUEPRINT §3.7). Customers fine-tune it inside their own tenant.
- **Who pays:** device makers and decoder vendors. Synchron already builds its own ("Chiral", landscape.md), so the buyer set is the long tail.
- **Pricing (ESTIMATE):** $100k–$150k/yr per licensee. No comparable price was opened, so this number is weak.
- **Y5 (ESTIMATE):** $0–$0.6M. Method: 0–4 licensees, available from year 4 at the earliest.
- **Legal:** **HIGH.** Commercial training on Art 9 data needs explicit consent that covers it. Recital 33 broad consent may not stretch to commercial licensing (question 3 to counsel). Weights can memorise data. Withdrawal forces a `retrain_required` flag on the model (SISA helps but is not certified; BUILD-GUIDE 6.4). The EU AI Act may impose GPAI provider duties (not researched). A licensee could fine-tune for prohibited emotion inference, so use restrictions (BUILD-GUIDE 6.2) are needed. In practice, the public-data-only version is the realistic first step.
- **Scopes:** *model training – licensed to third parties* (NEW split) + commercial use.
- **Brand:** high variance. It invites "they train AI on your brain" headlines.
- **Deps:** 6.1–6.5, 5.5, the pool. NEW: GPU training budget (not costed).

### A6. Data cooperative / data trust with contributor royalties
- **How:** contributors (labs, device users via their device maker) place data in a legally separate trust (for example a Norwegian stiftelse or cooperative; structure **UNVERIFIED**). The trust licenses aggregate access (A3/A4/A5), NeuroForge is paid as operator and processor, and contributors receive credits or royalties.
- **Who pays:** licensees pay the trust. NeuroForge earns an operator fee.
- **Pricing (ESTIMATE):** operator fee of 10–20% of trust licensing revenue, plus hosting at cost.
- **Y5 (ESTIMATE):** $0–$0.15M to NeuroForge.
- **Legal:** **MEDIUM–HIGH.** Cash to data subjects may compromise "freely given" consent (Art 7(4), not opened) and has tax implications. Governance is complex. Its brand value is the best of all models because it separates the data asset from the company.
- **Scopes:** *future biotech/neurobiology research* + commercial use + sharing.
- **Brand:** very positive if independent. It is also a strong answer to "are you a data broker?".
- **Deps:** as A3, plus NEW legal entity (owner-gated; counsel).

### A7. Curated benchmark datasets + held-out leaderboards (with sponsorship)
- **How:** a "MOABB-plus" benchmark (new-ideas.md #6). Public tracks use CC0/CC-BY data. Held-out tracks keep test data on our side (compute-to-data), so results cannot be overfit. Vendors pay for a signed evaluation report. Sponsors fund tracks.
- **Who pays:** decoder/AI vendors and device makers. Sponsors: no pricing opened.
- **Pricing (ESTIMATE):** $5k–$25k per evaluation (new-ideas.md #6).
- **Y5 (ESTIMATE):** $0.05M–$0.6M. Method: 8–30 evaluations/yr × $10k–$20k.
- **Legal:** public-data tracks carry **LOW** risk (licence compliance only: CC-BY needs attribution). Held-out private tracks carry **MEDIUM** risk (pool rules). Wording: "evaluation report", never "certified" (BOARD rule).
- **Scopes:** public tracks, none. Private tracks, *future biotech/neurobiology research* + *internal R&D*.
- **Brand:** very positive. It is credibility content for a math team and continues the public multiverse study (BUILD-GUIDE 3.9).
- **Deps:** 3.4–3.6, 3.9, 4.1. Held-out tracks also need 5.4 and the A1 release policy.

### A8. Consent and provenance attestation report (formerly "consent-verified"; renamed per nfb-legal-privacy) (provenance as a service)
- **How:** for a dataset about to be shared, published or sold by its owner, NeuroForge issues a signed attestation. It covers the consent-ledger coverage for each subject and scope, the jurisdiction classification (BLUEPRINT §8.2), the lineage hash chain (§3.6) and a re-identification risk scan (new-ideas.md #11, with no efficacy claim). **Name it an "attestation report", not a "certification"**, and scope it to what the ledger shows.
- **Who pays:** dataset owners (device makers selling data access, consortia, repositories) and acquirers doing due diligence (for example when a BCI company is bought).
- **Pricing (ESTIMATE):** $2k–$10k per dataset (new-ideas.md #11 band); due-diligence packages $10k–$40k (services band, pricing-and-gtm.md §2).
- **Y5 (ESTIMATE):** $0.05M–$0.6M.
- **Legal:** **LOW** privacy risk, because we process as the owner's processor. **MEDIUM** liability and misleading-claim risk if we overstate what is attested, so cap liability in the MSA.
- **Scopes:** none new. The attestation reads the existing scopes.
- **Brand:** very positive. It is the purest expression of "neural-data governance".
- **Deps:** 3.1, 3.7, 5.2, 5.3, 5.5. NEW: signed attestation format.

### A9. Governed marketplace commission on third-party datasets
- **How:** third parties list datasets that have passed A8 attestation. Access happens through compute-to-data (A1), never by download of identifiable data, and NeuroForge takes a commission.
- **Who pays:** dataset buyers, with a commission to NeuroForge.
- **Pricing (ESTIMATE):** 10–20% take rate (judgement; no comparable opened).
- **Y5 (ESTIMATE):** $0–$0.3M.
- **Legal:** **HIGH.** A commission on neural-data flows is the definition of brokerage optics, and CO/CA/CT sensitive-data "sale" rules apply to sellers (and possibly to us). market\validation.md #6 already rates the model marketplace WEAK. **Recommendation: DEFER.** Revisit only for CC0/CC-BY public data, or as the A6 trust's own marketplace.
- **Scopes:** sharing + commercial use + controller-to-controller agreements.
- **Brand:** negative.
- **Deps:** A1, A8, 6.1–6.2, plus billing (not in guide).

### A10. Research partnerships / co-authored studies
- **How:** joint studies with academic labs on public data or the partner's own data, for example multiverse robustness (BUILD-GUIDE 3.9) or a data descriptor. NeuroForge contributes the tooling and analysis, and grant money flows through the academic partner.
- **Who pays:** grant budgets. NIH DMS asks investigators to "plan and budget" data management (new-ideas.md #5).
- **Pricing (ESTIMATE):** $10k–$50k per partnership, or in kind.
- **Y5 (ESTIMATE):** $0–$0.3M.
- **Legal:** **LOW–MEDIUM.** The partner is the controller, and REK/IRB approval sits with the partner where required.
- **Scopes:** the partner's own.
- **Brand:** very positive (papers).
- **Deps:** 3.4–3.6, 3.9.

### A11. Grants and tax credits (non-dilutive; not revenue in ARR)
- **SkatteFUNN** (forskningsradet.no, opened): for companies "registrert i Brønnøysundregisteret og er skattepliktig til Norge". The deduction is "19 prosent av kostnadene" of approved R&D. Apply before 1 Sep for same-year certainty. **Annual cost cap not shown on the page, so UNVERIFIED.** The company is not yet incorporated (legal\BOARD.md assumption: AS), so this is available only after incorporation.
- **Innovation Norway oppstartstilskudd 1** (opened): AS younger than 5 years, **max NOK 150,000**, for customer-validation work. It fits the discovery interviews exactly.
- **EIC Accelerator** (opened): start-ups/SMEs in the EU or "countries associated to the Horizon Europe programme". Grant "below EUR 2.5 million" at TRL 6–8, plus equity of "€1 – €10 million". **Norway's association status was not verified in this pass (UNVERIFIED)**, and TRL 6–8 means years 2–3 at the earliest.
- **Forskningsrådet IPN** (Innovasjonsprosjekt i næringslivet): page returned 404, so **UNVERIFIED**.
- **Horizon Europe collaborative calls:** not opened, so **UNVERIFIED**.
- **5-yr value (ESTIMATE):** $0.2M–$3.5M cumulative. Low end: SkatteFUNN 19% × ~$0.2M/yr R&D for 4 years ≈ $0.15M + IN NOK 150k. High end adds one EIC grant of ~€2.5M. Grants are competitive. Treat as funding, not revenue.
- **Risk:** LOW legal. **Brand:** positive. **Deps:** none (owner-gated applications).

### A12. CRO / pharma EEG endpoint analytics
- **How:** services and software: Part 11-style EEG endpoint pipelines, multiverse robustness audits of biomarker endpoints (new-ideas.md #4, #10), and central-reading workflows. We act strictly as a processor on the sponsor's data.
- **Who pays:** CNS sponsors and CROs.
- **Pricing (ESTIMATE):** $10k–$40k per audit; $100k–$300k/yr platform (new-ideas.md #10).
- **Y5 (ESTIMATE):** $0.1M–$1.2M. **Largely overlaps the base model's S4 line.** Count only the incremental audits.
- **Legal:** **LOW–MEDIUM** (processor; trial rules sit with the sponsor). No clinical claims: the non-device boundary holds (regulation.md §4).
- **Scopes:** the sponsor's trial consent.
- **Brand:** positive.
- **Deps:** 3.4–3.6, 5.8. NEW: Part 11 controls.

### A13. Licensing the somatosensory research IP (honest assessment)
- **What exists:** simulation and theory only (research\somatosensory\STATUS.md). Cycle 1 verdicts: P4 pooling capacity **PASS**, with part A non-blind (disclosed). P2 **INCONCLUSIVE**. P3 **FAIL**. P1 **UNTESTED/ABANDONED**, because the model failed its own sanity check. Cycle 2 is running. **No patents exist, and no filing has been made.** Most results are negative or boundary results (for example, 64 pooled electrodes cannot reach natural force resolution; 81–5,806 would be needed).
- **Licensable value today:** close to zero as IP. Its real value is (a) credibility content (whitepaper), (b) open-source simulation code that attracts neuroprosthetics labs, and (c) a future research agenda for Part B's biotech team.
- **Pricing/Y5 (ESTIMATE):** $0–$0.05M (for example, paid workshops or consulting on stimulation-calibration simulation). **Do not present this as an IP asset in the pitch.**
- **Legal:** LOW privacy risk (computational). Any clinical follow-up needs IRB/REK/FDA (BRIEF rule).
- **Deps:** none.

### A14. Post-trial neural-data stewardship / escrow (added)
- **How:** neutral custody of implant-trial participants' data, device configurations and decoder models, so participants keep continuity if the sponsor fails (new-ideas.md #8; *BMC Med Ethics* 2026 consensus, cited there).
- **Who pays:** implant sponsors (as an IRB trust signal) and patient-advocacy funders.
- **Pricing (ESTIMATE):** $20k–$80k/yr per sponsor plus a per-participant fee.
- **Y5 (ESTIMATE):** $0.04M–$0.5M.
- **Legal:** **LOW–MEDIUM.** Processor, with a tri-party escrow agreement.
- **Scopes:** existing trial consent plus a stewardship clause.
- **Brand:** very positive (patient-first).
- **Deps:** 2.3, 3.1, 5.3, 5.5, 6.1.

### A15. Privacy-tech toolkit licensing (added: sell the shovel, not the data)
- **How:** license the DP engine, synthetic-data generator, clean-room policy engine and re-identification scanner so customers can run them on **their own** data for their own sharing needs. NeuroForge never touches a pool.
- **Who pays:** device makers and consortia that want to share their own data lawfully.
- **Pricing (ESTIMATE):** $300–$1,500/mo add-on (anchored to the new-ideas.md #12 add-on band).
- **Y5 (ESTIMATE):** $0.05M–$0.5M.
- **Legal:** **LOW** (processor). **Brand:** very positive. **Deps:** as A3/A4, but without the pool.

### REJECTED
| Model | Why rejected |
|---|---|
| **R1. Insurance and employer uses** (risk scoring, underwriting, workforce "attention/stress" analytics, hiring) | EU AI Act Art 5 prohibits emotion inference in "workplace and education institutions" except for medical or safety reasons (artificialintelligenceact.eu, B; 5(1)(f) per regulation.md). Neural data is sensitive data under CO HB24-1058, CA SB 1223 and CT PA 25-113 (regulation.md §1, A), so opt-in is needed and the power imbalance means consent is not credibly free. Insurance use of health-revealing data brings in further regimes (not researched). Brand: fatal for a privacy company. **Enforce in contract (AUP) and in the registry (BUILD-GUIDE 6.2 use restrictions).** |
| **R2. Selling or licensing raw, pseudonymised or individual-level customer data** | Breaches DPA §3.4 / MSA §4.3 as drafted. Pseudonymised data remains personal data under GDPR. It is exactly the data-broker model. |
| **R3. Advertising, neuromarketing profiling, law-enforcement or "lie-detection" uses** | AI Act Art 5(1)(a) manipulation and 5(1)(g) sensitive-trait categorisation (regulation.md §5); brand. |

---

## Part B: building a lawful neural-data asset

### Proposed consent-ledger scopes (for counsel review)
| Scope | Status | Meaning |
|---|---|---|
| collection, processing, sharing, model training, commercial use | Designed (BUILD-GUIDE 5.3) | As designed |
| **internal R&D** | **NEW** | NeuroForge may use the record to develop, test and benchmark its own software. No third-party access and no model weights leave NeuroForge |
| **future biotech/neurobiology research** | **NEW** | Broad consent (Recital 33: consent "to certain areas of scientific research when in keeping with recognised ethical standards") to future neuroscience, neurobiology and biotech research by NeuroForge or approved partners, under REK/IRB approval where required, with the option to exclude sub-areas |
| model training → split into **internal** and **licensed to third parties** | **NEW split** | Commercial licensing of trained weights needs its own explicit tick |

Each scope is versioned, hash-chained and enforced by `policy.check` (BUILD-GUIDE 5.4), and withdrawal of any scope triggers the 5.5 DeletionJob for that purpose.

### Legal frame shared by all options (planning reading, not advice)
- **Art 5(1)(b):** further processing for scientific research "shall, in accordance with Article 89(1), not be considered to be incompatible with the initial purposes" (gdpr-info.eu, B). This helps with *purpose limitation*. It does **not** by itself supply an Art 9(2) condition for special-category data, and it does not cover commercial, non-research use.
- **Art 89(1):** research processing "shall be subject to appropriate safeguards". Pseudonymisation, data minimisation and the ledger are our safeguards. **Art 5(1)(e)** lets research data be kept longer "solely for … scientific … research" with safeguards. That supports the cold/archive tiers below, but only for research-scoped data.
- **Recital 33:** supports broad research consent, but only to "certain areas".
- **Norway:** helseforskningsloven applies to "medisinsk og helsefaglig forskning på mennesker, humant biologisk materiale eller helseopplysninger" (§2), which needs REK pre-approval (§§9–10) and consent (§13), and allows broad consent (§14). **Whether computational research on neural signals aimed at knowledge "om helse og sykdom" (§4) triggers REK is UNVERIFIED** (question 4 to counsel). Assume yes for anything health-directed.
- **US:** CO/CA/CT treat neural data as sensitive (opt-in; CA right to limit use). Default-OFF pooling is consistent with that.
- **Contract:** MSA §4.3 already requires "a separate, specific, written opt-in" signed by the customer. Proposal: a **Research Pool Addendum** that defines datasets, purpose, de-identification, duration and revocation (the clause's own list).

### (a) Opt-in research pool (default OFF; customers own their data)
- **Mechanics:** a customer tenant ticks "contribute" per dataset. Only subjects whose ledger shows *future biotech/neurobiology research* (plus *commercial use* where licensed) are copied, pseudonymised under a pool-specific key, into a separate pool tenant where NeuroForge is controller. The customer keeps its own copy and ownership. Contributors receive **platform credits or a discount** (for example 10–20% off, ESTIMATE). Cash royalties are routed only through the A6 trust once counsel clears them.
- **Value:** normative references (A3), synthetic generators (A4), held-out benchmarks (A7), and pre-training (A5).
- **GDPR limits:** a new controller and a new purpose, so this needs explicit Art 9(2)(a) consent that names NeuroForge, or Art 9(2)(j) research with a Norwegian legal basis (UNVERIFIED). Art 5(1)(b) research compatibility applies only to research use.
- **Brand:** positive if default OFF, visible, and revocable in one click with a deletion certificate.
- **Deps:** 5.2–5.5, 2.3 (per-subject keys). NEW: pool tenant and addendum workflow.

### (b) Direct research programmes (NeuroForge-run cohorts)
- **Mechanics:** NeuroForge (later with an academic or hospital partner) recruits volunteers under REK-approved protocols with **broad consent** (§14) that covers AI training and future biotech/neurobiology research. It uses non-invasive EEG only. **No stimulation and no clinical procedures** (BRIEF science-safety rule).
- **Value:** the cleanest asset. We are the controller, consent is designed for reuse, and commercial licensing is possible if the consent says so.
- **Limits:** REK approval, the §13 consent standard, and possibly a data-protection impact assessment (DPIA, not opened). It costs participant time and hardware (not costed).
- **Brand:** positive (transparent, published protocols).
- **Deps:** 5.3 + NEW participant-facing consent UI. Owner-gated (recruiting = contacting people).

### (c) Curated public datasets (OpenNeuro / DANDI)
- **Licence facts (live APIs, 2026-09-26):** DANDI published dandisets are **400/434 CC-BY-4.0 and 33 CC0** (plus 1 dual), so attribution is required for most. On OpenNeuro, a partial scan (1,100 of ~1,902) found **~975 CC0**, ~45 other public-domain variants, and 51 with no licence field. EEG/iEEG/MEG datasets are 297/299 CC0.
- **Value:** zero-consent-risk training and benchmark corpus for A5 (public-only foundation model), A7 public tracks and A4-(i) validation. Curation (harmonised BIDS/NWB, QC scores, provenance) is our value-add.
- **Limits:** CC-BY requires attribution in derived datasets and model cards. Datasets with no licence field are **excluded** until clarified. Even CC0 data can be personal data under GDPR if it came from EU subjects and is linkable. The licence answers copyright, not privacy. Honour each dataset's data-use terms.
- **Brand:** very positive (open science).
- **Deps:** 2.5 converters, 3.4–3.6, 3.9.

### (d) Synthetic data from the pool
- See A4(ii). **Rule:** no synthetic release until a membership-inference and singling-out test (thresholds set with counsel, question 6) passes. Publish the test report.
- **Scopes:** *model training – internal* + *future biotech/neurobiology research*.

### (e) Derived features and embeddings
- **Still personal data if linkable.** Features and embeddings keyed to a subject pseudonym inherit the strictest label of their inputs (BLUEPRINT §8.2 inheritance rule). They count as anonymous only if the link is destroyed **and** re-identification from the vector itself is shown to be unlikely (unverified; new-ideas.md #11 calls neural re-identification a research question).
- **Value:** much cheaper to store and license (via A1 only) than raw data.
- **Deps:** 3.1 (lineage), 5.2 (inheritance), 5.5 (withdrawal also purges features).

### (f) Retention tiers: hot / cold / archive (AWS S3 US East prices opened; ESTIMATE volumes)
| Tier | Class | $/GB-month (opened) | 5 TB / month | 50 TB / month | 500 TB / month* |
|---|---|---|---|---|---|
| Hot (active analysis, 0–90 days) | S3 Standard | $0.023 | $115 | $1,150 | ≤ $11,500 |
| Warm (monthly access) | Standard-IA | $0.0125 | $62.50 | $625 | $6,250 |
| Cold (instant but rare) | Glacier Instant Retrieval | $0.004 | $20 | $200 | $2,000 |
| Archive (research retention) | Glacier Flexible Retrieval | $0.0036 | $18 | $180 | $1,800 |
| Deep archive (long-term research, Art 5(1)(e)) | Glacier Deep Archive | $0.00099 | $4.95 | $49.50 | $495 |

*Above 50 TB the Standard price we opened applies only to the first 50 TB. Higher-volume tiers were not opened, so ≤ is an upper bound. Retrieval, request, minimum-duration and egress fees **were not opened** and are excluded. The 5 TB and 50 TB columns match BLUEPRINT §12.1's pilot and M5 volumes (5 TB × $0.023 = $115; 50 TB = $1,150).
- **Reading:** moving the pool's cold 90% to Deep Archive cuts storage cost about 23× (0.023 / 0.00099). **Storage cost is not the constraint. Consent scope and deletion are.** Crypto-shredding (BLUEPRINT §8.4) makes archived copies unreadable on withdrawal without restoring the archive, which is why per-subject keys (BUILD-GUIDE 2.3) are a precondition for cheap archive tiers.
- **Limit:** archive only data whose scope is research (Art 5(1)(e)). Operational customer data follows the customer's retention policy.

### How this asset gives a future biotech/neurobiology team a head start (SCENARIO, no claims)
- **Biomarker discovery:** a harmonised, consented, provenance-tracked EEG/ECoG corpus with multiverse-robustness tooling (3.6) lets a team test candidate biomarkers against the preprocessing sensitivity that Kessler 2025 and Huang 2025 documented (landscape.md §3). It is not a claim that such biomarkers exist.
- **Target discovery:** only if the pool later links to consented phenotype or genetic data. That would bring in biobank law (helseforskningsloven §25 ff.) and major new consent. SCENARIO only.
- **Somatosensory / neuroprosthetics:** the existing simulation work (P4 pooling-capacity bounds; cycle-2 P5 spatial-channel capacity) gives a quantitative design agenda: electrode counts and calibration time budgets. Combined with the DANDI ICMS datasets already identified (for example 001868, 000774; research\somatosensory\notes\BOARD.md), a neuroprosthetics team starts with validated simulation code, a curated data list and negative results that save wasted experiments. SCENARIO.
- **Regulatory head start:** the provenance graph, consent ledger and FDA Evidence Kit (5.8) are the documentation spine a biotech programme needs.

### Licences and regulation for wet-lab / biotech work in Norway / EU (checklist; mostly UNVERIFIED)
| Activity | Instrument | Status of our check |
|---|---|---|
| Health research on humans, human biological material or health data | Helseforskningsloven §§2, 9–10 (REK pre-approval), §§13–14 (consent, broad consent) | **Opened (A)** |
| Research biobanks (storing human biological material) | Helseforskningsloven §25 ff. (establishment, responsible person, storage, transfer with committee approval) | **Opened, summary only (A)**. Details UNVERIFIED |
| Genetically modified organisms (for example viral vectors, optogenetics in animals or cells) | Genteknologiloven: §6 contained-use facility approval, §7 approval cases, §§9–10 release | **Opened (A)**. Implementing regulations (for example classification of contained use) UNVERIFIED |
| Animal experiments | Dyrevelferdsloven + forskrift om bruk av dyr i forsøk (Mattilsynet approval) | **UNVERIFIED** (not opened) |
| Clinical trials of medicinal products / devices | EU CTR 536/2014; MDR 2017/745 / clinical investigations; Norwegian implementing law | **UNVERIFIED** (EUR-Lex failed for the legal team) |
| Human cells / tissue (for example organoids) | Behandlingsbiobankloven / tissue and cells rules | **UNVERIFIED** |
| Personal data | GDPR (Art 5, 9, 89) + personopplysningsloven (legal\BOARD.md, A) | Partly opened |
| Ethics of non-health research | Forskningsetikkloven (NEM/NESH guidance) | **UNVERIFIED** |
| Export control of dual-use neurotech | Eksportkontrolloven (legal\BOARD.md, A) | Opened by the legal team |

**Recommendation:** no wet-lab work before a dedicated counsel review and a separately funded entity. The software company should stay computational (BRIEF rule).

---

## Part C: data-asset value in an UPSIDE scenario (not the base case)

**Method (income approach, bottom-up, ESTIMATE).** Revenue from the data asset = Σ over products of (licensees in year) × (price). Grants, processor services (A1, A2, A12, A14) and anything already in the base model are excluded. Only pool- and public-corpus-based products are counted:
- **Benchmark evaluations (A7), available from Y1 on public data:** evaluations per year low 0/2/4/6/8, mid 1/4/8/12/16, high 2/6/12/20/30, at $10k / $15k / $20k (new-ideas.md #6 band $5k–$25k).
- **DP API + synthetic licences (A3 + A4), from Y3, or Y2 in the high case (needs the pool, hence ledger M5 + counsel):** subscribers low 0/0/1/2/4, mid 0/0/3/6/10, high 0/1/5/12/20, at $12k / $36k / $60k per year (new-ideas.md #7: $1k–$5k/mo).
- **Foundation-model licences (A5), from Y4:** low 0; mid 0/0/0/1/2 at $100k; high 0/0/0/2/4 at $150k. No comparable opened, so this is the **weakest input**.

**Upside revenue from the data asset, USD thousands (ESTIMATE; import-ready)**
| scenario | Y1 | Y2 | Y3 | Y4 | Y5 | 5-yr total |
|---|---|---|---|---|---|---|
| low | 0 | 20 | 52 | 84 | 128 | 284 |
| mid | 15 | 60 | 228 | 496 | 800 | 1,599 |
| high | 40 | 180 | 540 | 1,420 | 2,400 | 4,580 |

CSV (same numbers, USD): `scenario,year,metric,value` → `upside_data_low,1..5,data_asset_revenue,0|20000|52000|84000|128000`; `upside_data_mid,…,15000|60000|228000|496000|800000`; `upside_data_high,…,40000|180000|540000|1420000|2400000`.

**Cost-based cross-check (ESTIMATE).** Replacement cost of the pool *infrastructure* beyond the base build: roughly 8 person-months (DP engine, pool tenant and addendum, MIA harness, attestation format; judgement against the BUILD-GUIDE S/M/L sizing). At the BLS median salary used by the finance model ($135,980/yr) that is ≈ $91k, or ≈ $118k with an assumed 1.3× overhead. Pool storage at 50 TB tiered 10% hot / 90% deep archive ≈ $115 + $45 ≈ $160/month (prices above). **The cost of acquiring the consented data itself was not sourced**, so no cost-based value of the data is claimed. Conclusion: the asset is cheap to hold. Its value depends entirely on consent quality and on getting to a useful size, and neither is proven.

**Caveats:** this scenario assumes counsel clears the new scopes, customers opt in (the rate is unknown and must be tested in discovery), and one year of runway beyond the base plan. Pool-based products double-count nothing in the base model only if the Growth/Enterprise tiers are not also credited with them.

---

## Part D: ranking and sequencing

**Ranking method:** expected Y5 revenue (midpoint of the Y5 range) × a risk factor (LOW 0.9, LOW–MEDIUM 0.75, MEDIUM 0.5, MEDIUM–HIGH 0.3, HIGH 0.15; judgement), with brand fit as the tie-breaker.

| Rank | Model | Y5 range (ESTIMATE) | Risk (nfb-legal-privacy) | Risk-adjusted Y5 | Why |
|---|---|---|---|---|---|
| 1 | **A1 Compute-to-data / federated analysis** | $0.1M–$1.5M | LOW–MEDIUM | ~$0.6M | Processor role kept; "data never leaves" is the brand |
| 2 | **A12 + A2 Pharma/CRO endpoint analytics and clean rooms** (add-on over base S4) | $0.2M–$2.1M | LOW–MEDIUM / MEDIUM | ~$0.6M | Highest ACV buyers (sizing.md: S1 + S4 ≈ 70–80% of SAM) |
| 3 | **A8 Consent/provenance attestation + A15 privacy-tech toolkit** | $0.1M–$1.1M | LOW | ~$0.5M | Pure governance, no pool needed, very positive brand |
| 4 | **A7 Benchmarks and held-out evaluations** | $0.05M–$0.6M | LOW–MEDIUM | ~$0.25M | Starts on CC0/CC-BY public data in Y1; credibility engine |
| 5 | **A11 Grants and tax credits** | $0.2M–$3.5M cumulative (non-dilutive, not ARR) | LOW | n/a (funding) | SkatteFUNN 19%; IN NOK 150k; EIC < €2.5M (association UNVERIFIED) |
| (next) | A4/A3 synthetic + DP from the pool | $0.05M–$1.2M | MEDIUM | ~$0.3M | Needs the pool; publish MIA tests |
| (upside) | A5 foundation model | $0–$0.6M | HIGH | ~$0.05M | Public-data-only version first |
| DEFER | A9 marketplace commission, A6 trust | — | HIGH / MEDIUM–HIGH | — | Brokerage optics; the trust only as a later spin-out |
| REJECT | R1 insurance/employer, R2 selling data, R3 ads/neuromarketing/law enforcement | — | Prohibited / high | — | AI Act Art 5; CO/CA/CT; brand |

**Sequencing (ties to BUILD-GUIDE milestones and the pricing-and-gtm.md §5 order):**
1. **Months 0–6:** apply for IN oppstartstilskudd 1 and SkatteFUNN once the AS exists (owner-gated). Build the A7 public benchmark on CC0/CC-BY data (3.4–3.6, 3.9), with attribution per dataset licence. Use the 0.6 simulator for synthetic fixtures (A4-i, no personal data).
2. **Months 3–9 (M5 ledger):** add the three scope changes to 5.3 **before** the first design partner, so consent is collected right from day one. Draft the Research Pool Addendum under MSA §4.3 with counsel (owner contacts counsel).
3. **Months 9–18:** A1 compute-to-data and A8 attestation, both processor-only. A12 audits for the first pharma pilot.
4. **Months 18–30:** open the opt-in pool (default OFF, credits not cash). Start DP reports (A3) only after the epsilon policy is reviewed. Release synthetic data (A4-ii) only after MIA tests pass and are published. Consider an EIC application if TRL 6–8 is reached and Norway's association is verified.
5. **Year 3+:** clean rooms (A2) for sponsors. A public-data-only foundation model (A5), with pool data added only under the *licensed* training scope. Revisit the trust (A6) as an independent entity.
6. **Never:** R1–R3.

### Bullets for the pitch and the scaling plan
- "We make money from governing neural data, not from selling it. Default-off pooling, one-click withdrawal, deletion certificates."
- "Compute-to-data: partners bring the pipeline to the data. Nothing identifiable leaves the customer's tenant." (roadmap)
- "Upside, not in the base case: a consented research asset built on CC0/CC-BY public data plus opt-in contributions. Data-asset revenue ESTIMATE of $0.13M–$2.4M in Y5."
- "Non-dilutive funding path: SkatteFUNN (19% of approved R&D costs), Innovation Norway start-up grant (up to NOK 150k), and EIC Accelerator later (grant < €2.5M)."
- "Hard no's in contract and in code: no insurer, employer, advertising or law-enforcement uses (EU AI Act Art 5; CO/CA/CT sensitive-data laws)."
