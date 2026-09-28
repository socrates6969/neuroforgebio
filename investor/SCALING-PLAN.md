# NeuroForge Bio: 10–15 year scaling plan

Prepared 2026-09-26 by the CEO agent for the owner, Marius Carlsson. **DRAFT for owner review.**

**How to read this document**
- **Years 1–2 are a plan.** They come from `investor\financial-model.py` and every figure is an ESTIMATE.
- **Years 3–5 are modelled ESTIMATEs,** from the same script.
- **Years 6–15 are SCENARIOS, not forecasts.** They extrapolate from the model's year-5 figures using the named growth assumptions in §3. No source supports any specific number that far out.
- **Pre-product.** No customers, revenue, partners or investors exist. Status words: *designed*, *planned*, *roadmap*.
- **Not a medical device.** The product line stays non-device research and development software unless the owner deliberately decides otherwise (see §6, regulatory decision R3).
- **Name.** NeuroForge Bio is pending trademark clearance (`market\names.md`).

---

## 1. Phases at a glance

| Phase | Years | Theme | Products (in order) | Markets | Exit from phase when… |
|---|---|---|---|---|---|
| **0. Prove** (NOK 1M angel round → seed) | 0–1 | Credibility with no customers needed, then first design partners | Open-core SDK + validator; multiverse audit on public data; **Consent & Deletion Ledger** MVP | US (CO/CA/CT/MT law exposure) | 3–5 design partners are active and at least one pays list price |
| **1. Wedge** | 1–3 | Governance and evidence for regulated neurotech | Ledger GA; **FDA Evidence Kit** + latency harness; Startup / Lab / Growth tiers | US first; EU data residency planned | ~$1.5–2M ARR and a repeatable S1 sale |
| **2. Platform** | 3–5 | One lineage graph serving four segments | **Governed model registry** (on pull); 21 CFR Part 11 workflows for CNS trials; Enterprise/Pharma tier | US + EU (GDPR, AI Act) | ~$3.5–4.5M ARR; pharma logos renewing |
| **3. Standard** | 5–10 | Become the default system of record for neural-data provenance and consent | Post-trial data stewardship/escrow; decoder benchmark and certification; payer/RWE data packages | + UK, then selected APAC or LatAm markets where neural-data law exists | A clear category position; Series B/C or profitability |
| **4. Expand or exit** | 10–15 | Adjacent biosignals, or a strategic combination | Extension to other biosignals regulated as sensitive data, if laws move that way | Global | See §7 |
| **5. Biotech / neurobiology arm** (SCENARIO) | 8–15 | Research that uses the consented data asset and our models | Biomarker and target-discovery research; somatosensory and neuroprosthetic research; licensing | Norway/EU first (REK) | See §10. Triggered only by the gates in §10 |

Sources for the product order:
- `market\pricing-and-gtm.md` §5 (months 0–18).
- `market\new-ideas.md`: top 5 in phases 0–2; ideas #8, #6 and #13 in phase 3.
- `architecture\DECISIONS.md` D5, which runs the ledger early.
- `market\validation.md` #6 and #10: marketplace and Unity/Unreal only on customer pull.

---

## 2. Milestones and gates

| # | Milestone | Target timing | Gate: evidence required before moving on |
|---|---|---|---|
| G1 | 15–20 discovery interviews done by the owner | Months 0–3 | Documented willingness to pay for the ledger and evidence kit (`market\validation.md`, riskiest questions 1–2) |
| G2 | Open-core SDK published; multiverse results on public data published | Months 0–3 | The owner approves publishing. The licence is Apache-2.0 (D6) |
| G3 | Privacy counsel reviews the CO/CA/CT RuleSets (MT after the statute text is opened) | Before the first paying ledger customer | Every RuleSet has `review_status: counsel-reviewed` (`BLUEPRINT.md` §8.2, D10) |
| G4 | 3–5 design partners | Months 3–9 | Signed agreements; the owner signs |
| G5 | Paid launch | Month 17 in the base model (month 24 bear, month 15 bull) | Ledger MVP meets the deletion-job target in `BLUEPRINT.md` §8.4 (a target, not yet measured) |
| G6 | Regulatory consultant reviews the Evidence Kit | Before the Evidence Kit is sold | D10 #2 |
| G7 | SOC 2 Type II started | When 2–3 design partners ask | D10 #3. Website says "on roadmap" until a report exists |
| G8 | Seed round (N1: NOK 10M at NOK 40M pre-money) | Month 9 (base); must close by months 9–10 | Results of G1, G2 and G4 |
| G8b | Round N2 (USD 4.0M ≈ NOK 38.0M) | Month 20 (base); must close by month 21 | Paid launch plus first paying customers |
| G9 | EU region live for GDPR tenants | Years 2–3 | A DPIA and EU counsel review |
| G10 | First pharma/CRO logo | Year 3 (base model: S4 = 1 at the end of year 3) | Part 11 workflows validated |
| G11 | Series A (USD 12M) | Month 40 (base); must close by month 44 | ~$1.5–2.3M ARR |
| G12 | Series B or profitability path | Years 6–7 (SCENARIO) | See §4 |

---

## 3. Numbers: modelled years 1–5 (ESTIMATE)

Source: `investor\financial-model.csv`. The assumptions, with sources, are in `financial-model.py` §1.

**The funding path was corrected on 2026-09-26.**
- The first round is **NOK 1,000,000** (≈ USD 105k at 9.5063 NOK/USD, the Norges Bank spot rate for 2026-09-25, data.norges-bank.no).
- It is not USD 1.0M.
- Nobody is hired before the seed. After that, each hire needs cash covering 9 months of projected burn.

### How far NOK 1M gets us (pre-phase, no revenue; `prephase-runway.csv`)

| Mode | Burn per month | Runway | With grants* |
|---|---|---|---|
| Lean: founder + AI tools + 0.1 FTE contractor, minimal cloud | ≈ NOK 50k | 18 months | 22 months |
| Small team: founder + 0.5 FTE contractor | ≈ NOK 114k | 8 months | 9 months |

\*Grants are conditional on the AS existing and on approval, and none is guaranteed:
- Innovation Norway oppstartstilskudd 1: NOK 150k, assumed in month 5.
- SkatteFUNN: 19% of eligible cost. It is paid through the tax settlement, so the cash is assumed around month 21 (UNVERIFIED).
- Forskningsrådet: not modelled, because its programme page could not be opened (UNVERIFIED).

### Base case (small-team pre-phase; seed in month 9; paid launch in month 17)
| Model year | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| End ARR | $0.00M | $0.28M | $1.15M | $2.28M | $3.63M |
| Recognised revenue | $0.04M | $0.27M | $0.92M | $2.05M | $3.34M |
| Gross margin | 36% | 52% | 62% | 74% | 74% |
| Net burn | $0.35M | $1.35M | $2.32M | $2.66M | $3.45M |
| Year-end cash | $0.81M | $3.46M | $1.14M | $10.48M | $7.03M |
| Headcount (incl. founder) | 5 | 13 | 14 | 26 | 34 |
| Logos S1/S2/S3/S4 | 0/0/0/0 | 3/6/10/0 | 8/15/30/1 | 14/26/53/2 | 20/38/77/5 |

The base case works, but it is tight: minimum cash is about $13k in month 8, just before the seed.

### Bear case (lean pre-phase; seed in month 14; paid launch in month 24)
| Model year | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| End ARR | $0.00M | $0.02M | $0.22M | $0.64M | $1.15M |
| Net burn | $0.06M | $0.89M | $1.60M | $2.18M | $3.25M |
| Year-end cash | $0.05M | $0.21M | $1.12M | **−$1.07M** | $2.69M |
| Headcount | 1 | 4 | 11 | 11 | 20 |

**The bear case has a funding gap of about $1.25M**, with minimum cash in month 49. Round N2 would have to close by month 27 rather than month 32; otherwise the company must cut hiring, bridge, or sell.

### Bull case (small-team pre-phase; seed in month 8; paid launch in month 15)
| Model year | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| End ARR | $0.00M | $0.59M | $2.28M | $4.32M | $7.00M |
| Net burn | $0.38M | $1.39M | $2.58M | $2.95M | $3.25M |
| Year-end cash | $0.77M | $4.38M | $19.81M | $16.86M | $13.61M |
| Headcount | 5 | 16 | 25 | 35 | 47 |

### Lean scenario (founder-led; no hires; no seed)
- The owner works with AI tooling and about 0.1 FTE of contractor help. No ARR product is launched.
- If the founder sells about one USD 20k audit or services engagement per quarter (unvalidated), net burn falls to about USD 15k a year.
- In that case NOK 1M lasts to about **month 59**.
- This keeps the company alive and fully owned, but it does not build the platform.

### Funding path (ESTIMATE; nothing raised, no investor contacted)
| Round | Base | Bear | Bull |
|---|---|---|---|
| Pre-seed / angel | NOK 1M (≈ $0.11M), month 1 | NOK 1M, month 1 | NOK 1M, month 1 |
| Seed N1 | NOK 10M at NOK 40M pre (≈ $1.05M), month 9 | NOK 10M, month 14 | NOK 10M, month 8 |
| Round N2 | USD 4.0M at NOK 120M pre, month 20 | USD 2.5M, month 32 | USD 5.0M, month 20 |
| Series A | USD 12M, month 40 | USD 7M, month 50 | USD 18M, month 36 |

Founder ownership along the base path, for the recommended structure (`dilution.py` PATH table):
- after the angel round: 90.91%;
- after the seed N1: 63.64%, including a 10% option pool;
- after round N2: 48.33%;
- after the Series A: 36.24%.

The owner calls the NOK 1M round "Series A". In market terms it is a pre-seed (angel) round.

---

## 4. Scenarios: years 6–15 (SCENARIO, not a forecast)

**Method.** Year-5 end ARR from the corrected model, compounded by the assumed annual growth rates below. Headcount is ARR divided by an assumed ARR per employee.

| Scenario | Growth rates, years 6→15 | ARR per employee |
|---|---|---|
| Bear | 30, 28, 25, 22, 20, 15, 12, 10, 10, 8% | $150k |
| Base | 50, 45, 40, 35, 30, 25, 22, 20, 18, 15% | $180k |
| Bull | 70, 60, 50, 40, 35, 30, 25, 22, 20, 18% | $220k |

The growth rates and ARR-per-employee values are judgement. No benchmark source was opened.

| End ARR (SCENARIO) | Y5 (model) | Y7 | Y10 | Y12 | Y15 |
|---|---|---|---|---|---|
| Bear | $1.15M | $1.9M | $3.5M | $4.5M | $5.9M |
| Base | $3.63M | $7.9M | $19.4M | $29.6M | $48.2M |
| Bull | $7.00M | $19.0M | $54.0M | $87.7M | $151.5M |

| Headcount (SCENARIO) | Y10 | Y15 |
|---|---|---|
| Bear | ~23 | ~39 |
| Base | ~108 | ~268 |
| Bull | ~245 | ~690 |

### What has to be true for each scenario

**Bear: stays a niche governance tool.**
- Only S1 and S2 adopt, and pharma never scales. No further state laws pass, and the MIND Act study does not lead to rules.
- Year-15 ARR (~$6M) is below today's SAM floor of $10M (`market\sizing.md` §3).
- Likely outcome: a small profitable company, the lean mode, or an early acquisition (§7).

**Base: category leader in neural-data governance.**
- By year 10, ARR is ~$19M, in the lower half of today's SAM.
- Beyond that, **SAM itself has to grow**: through more jurisdictions (the states considering bills: AL, MA, MN, IL, VT, per `market\regulation.md` §1, status unverified), EU tenants, and the S4 Part 11 product.
- $48M by year 15 is only possible if the market expands.

**Bull: standard system of record.**
- Neural-data regulation becomes federal or widespread. Implants reach commercial scale, and payers and FDA expect lineage evidence.
- Pharma adopts the Part 11 EEG platform (new-ideas #10).
- Year-12 ARR (~$88M) exceeds today's SAM ceiling, and year-15 (~$152M) approaches the low end of today's top-down TAM ($0.1–1.1B, not decision-grade).
- **This is the least-evidenced case.**

---

## 5. Headcount plan by function (base)

| Function | Y1 | Y2 | Y3 | Y5 | Y10 (SCENARIO) |
|---|---|---|---|---|---|
| Founder / CEO | 1 | 1 | 1 | 1 | 1 |
| Engineering (SWE, DevOps/security) | 3 | 6 | see note | 13 | ~44 |
| Neuro-data science | 1 | 1 | see note | 3 | ~10 |
| Regulatory / QA | 0 | 1 | see note | 2 | ~8 |
| Design | 0 | 1 | see note | 2 | ~5 |
| Sales (AE) / customer success | 0 | 2 | see note | 8 | ~24 |
| Marketing / developer relations | 0 | 1 | see note | 3 | ~8 |
| G&A / operations | 0 | 0 | see note | 2 | ~8 |
| **Total** | **5** | **13** | **14** | **34** | **~108** |

- Years 1, 2 and 5 come from the `roles` table in `financial-model.py`.
- The year-1 heads join only after the seed closes in month 9.
- In year 3 the cash-cover rule pauses hiring at 14 until the Series A in month 40. The split by function is not modelled for that year.
- The year-10 split is a SCENARIO: the year-5 mix, scaled up.
- **Key leadership hires (planned):**
  - Head of Engineering by year 2.
  - Head of Regulatory & Quality by year 3, before selling the Evidence Kit at scale.
  - VP Sales by year 3–4.
  - A CFO or finance lead before the Series B.

---

## 6. Regulatory steps

| # | Step | When | Notes |
|---|---|---|---|
| R1 | Counsel-reviewed RuleSets: CO, CA, CT; MT after its statute text is opened | Before the first paying ledger customer | Highest legal risk (D10 #1). Every rule carries its review status |
| R2 | HIPAA path: cloud BAA, our own BAA, policies, risk analysis | Before the first clinical or PHI customer | `BLUEPRINT.md` §8.5. HIPAA is table stakes, not the moat |
| R3 | **Stay non-device.** No diagnostic or treatment functions. Models only as governed SOUP components; the customer carries 510(k)/De Novo/PMA | Permanent, unless the owner decides otherwise | `market\regulation.md` §4. Crossing into device software would need a QMS, and possibly ISO 13485 (not researched) |
| R4 | IEC 62304-style lifecycle for SOUP components we market | Year 2, before the Evidence Kit is sold | IEC 62304 was not opened. Verify with a regulatory consultant |
| R5 | SOC 2 Type II | Year 2, when design partners ask | Budget in the model: must be quoted |
| R6 | EU: GDPR Art. 9 processes, DPIA, EU data residency; AI Act 5(1)(f) use restrictions in the registry | Years 2–3 | `market\regulation.md` §5 |
| R7 | 21 CFR Part 11 validation package (S4) | Year 3 | Needed for CNS-trial EEG endpoints (new-ideas #10) |
| R8 | Track new laws: state bills, MIND Act, LatAm constitutional provisions | Continuous | This work also feeds the public law tracker |

---

## 7. Exit options (the owner's decision; none explored or contacted)

| Option | Plausible when | Rationale | Evidence status |
|---|---|---|---|
| **Stay independent, profitable** | Bear or base | Governance software with 75%+ gross margin (model years 4–5) can reach break-even once growth slows | Model only |
| **Acquisition by a regulated research-data platform** (Flywheel-type, imaging-first) | Base, years 5–10 | Adds a neural modality and Part 11 EEG | Category inference from `market\landscape.md` §2. No acquirer interest is known |
| **Acquisition by an eQMS, regulatory or compliance software vendor** | Base, years 5–10 | Adds the Evidence Kit and neural-law RuleSets | Vendors were not verified in this pass |
| **Acquisition by a CRO or clinical-trial technology firm** | Base or bull, once S4 has traction | EEG-endpoint data platform | Inference only |
| **Acquisition by a neurotech device company** | Any | Unlikely for leaders, who build in-house (`market\validation.md` #4); more plausible for mid-size firms | Weak |
| **IPO** | Bull only, years 12–15 | Needs roughly $100M+ ARR (the bull case passes ~$108M by year 12) | The ARR threshold for an IPO is judgement, not sourced |

No valuation multiples were opened for this plan, so no exit values are given. Get them from sourced comparables before any investor conversation.

---

## 8. Markets: order and triggers

1. **US (years 0–3).** Four state neural-data laws are in force; FDA pathways exist for implants; most sector funding sits here (`market\sizing.md` §1).
2. **EU (years 2–4).** GDPR Art. 9 and AI Act Art. 5 apply. The International BCI Society Meeting (Jun 2027, Croatia) is the first EU presence. **Trademark clearance is required first**, because Neuroforge GmbH & Co. KG operates in Germany.
3. **UK (years 4–6).** The first UK Neuralink patient was reported in Oct 2025 (`market\landscape.md` §1, B-). The UK regulatory regime was not researched.
4. **LatAm and APAC (years 6+, SCENARIO).** Chile's constitutional neural-data protection, and bills in Brazil (Rio Grande do Sul), Mexico, Colombia, Ecuador and Uruguay (`market\regulation.md` §5, A) make them candidates for RuleSets. Entry would be by partner or remote sale, not local offices.

---

## 9. Building a lawful neural-data asset

Full analysis: `investor\DATA-REVENUE-STRATEGY.md` Part B. Its legal readings have been rated by nfb-legal-privacy (see `DATA-STRATEGY-QUESTIONS-FOR-PRIVACY.md`). The ratings are an AI legal-team draft, and counsel must confirm them. Not legal advice.

**Principle.** Customers own their data. NeuroForge Bio builds its own asset only from:
- data that subjects and customers **opt in** to share (the default is OFF);
- data from its own ethics-approved programmes;
- public datasets whose licences allow it.

Every record carries versioned consent scopes. Withdrawal propagates into derivatives and models (`BLUEPRINT.md` §8.4).

| Option | Value | Consent scope needed | GDPR limits (provisional) | Brand effect |
|---|---|---|---|---|
| (a) Opt-in research pool: credits or discount now, royalties only via a later data trust | AI training, normative references, synthetic data, benchmarks | *future biotech/neurobiology research* (NEW), + *commercial use* if licensed | NeuroForge becomes controller for a new purpose, so this needs explicit Art 9(2)(a) consent that names us, or Art 9(2)(j) with a national basis (UNVERIFIED). Art 5(1)(b) compatibility covers research only | Positive if default OFF and revocable in one click |
| (b) Own research programmes (non-invasive EEG, REK-approved, broad consent per helseforskningsloven §14) | The cleanest asset: consent designed for reuse and AI training | *model training – internal / licensed* (a NEW split), *future biotech/neurobiology research* | REK pre-approval (§§9–10); DPIA likely. Recruiting is owner-gated | Positive (published protocols) |
| (c) Curated public data (DANDI: 400/434 published dandisets CC-BY-4.0, 33 CC0; OpenNeuro EEG/iEEG/MEG mostly CC0 in a partial scan) | Zero-consent-risk corpus for benchmarks and a public-data-only foundation model | None (licence + attribution) | CC0 does not mean anonymous. Exclude datasets with no licence field | Very positive |
| (d) Synthetic data from the pool | Shareable test and training data | As in (a) | Released only after membership-inference tests pass | Positive if the tests are published |
| (e) Derived features and embeddings | Cheaper to store; licensed via compute-to-data only | Inherit the strictest input label | Still personal data if linkable | Neutral |
| (f) Retention tiers | S3 Standard $0.023 → Glacier Deep Archive $0.00099 per GB-month (AWS pricing page, D). A 50 TB pool, 10% hot and 90% deep archive, costs ≈ $160/month (ESTIMATE) | Research-scoped data only (Art 5(1)(e)) | Crypto-shredding makes archived copies unreadable on withdrawal | Neutral |

**Proposed new consent-ledger scopes** (for counsel):
- *internal R&D*;
- *future biotech/neurobiology research*, a broad consent in the sense of Recital 33, limited to "certain areas of scientific research". **Legal has narrowed this scope to research on the nervous system.** Each health-research project still needs its own REK approval. Draft templates: `legal\data-agreements\CONSENT-SCOPES.*` and `legal\commercial
esearch-pool-addendum.*`;
- a split of *model training* into **internal** and **licensed to third parties**.

**Sequencing**
- Scopes are added to the ledger (BUILD-GUIDE 5.3) **before the first design partner**.
- The pool opens in months 18–30, with credits rather than cash.
- Our own REK programmes start in year 3+.

**Financial treatment**
- The data asset is an **UPSIDE scenario only** (`financial-model.py`, scenarios base+data_low/mid/high).
- Year-5 upside revenue (ESTIMATE): $0.13M low, $0.80M mid, $2.40M high.
- The base case excludes it.

---

## 10. Biotech and neurobiology expansion (SCENARIO)

**Why the data asset gives a head start** (hypotheses, not claims):
1. **Biomarkers.** A harmonised, consented, provenance-tracked EEG/ECoG corpus plus multiverse tooling lets a team test candidate biomarkers against preprocessing sensitivity (Kessler 2025; Huang 2025). This does not claim that such biomarkers exist.
2. **Target discovery.** Only possible if the pool later links to consented phenotype or genetic data. That brings in biobank law (helseforskningsloven §25 ff.) and new consent.
3. **Somatosensory and neuroprosthetic research.** The computational programme in `research\somatosensory\` already gives design bounds from simulation (pooling capacity, spatial channel capacity) and a curated list of public ICMS datasets. A lab team would start with validated simulation code and documented negative results.
4. **Regulatory spine.** The provenance graph, consent ledger and FDA Evidence Kit are the documentation base a biotech programme needs.

**Licences and regulation (Norway/EU; source status per `DATA-REVENUE-STRATEGY.md` Part B)**

| Activity | Instrument | Checked? |
|---|---|---|
| Health research on humans, biological material or health data | Helseforskningsloven §§2, 9–10 (REK), 13–14 (consent, broad consent) | Opened (A) |
| Research biobanks | Helseforskningsloven §25 ff. | Opened, summary only; details UNVERIFIED |
| GMOs (e.g. viral vectors, optogenetics) | Genteknologiloven §6 contained-use approval, §7, §§9–10 | Opened (A); regulations UNVERIFIED |
| Animal experiments | Dyrevelferdsloven + forskrift om bruk av dyr i forsøk (Mattilsynet) | UNVERIFIED |
| Clinical trials / clinical investigations | EU CTR 536/2014; MDR 2017/745 | UNVERIFIED |
| Human cells and tissue (e.g. organoids) | Tissue and cells rules | UNVERIFIED |

**Timing gates.** Start only when all four hold:
- the software business is at least break-even or has funded runway of 24+ months;
- the data asset holds enough consented research-scope data to matter (a size threshold to be set with the research lead);
- counsel has reviewed the wet-lab and biobank obligations;
- a **separately funded and separately governed entity** is set up.

Under the base scenario that points to **years 8–12**. The software company itself stays computational (BRIEF science-safety rule).

**Funding need (SCENARIO, ESTIMATE):**
- People: 8–15 researchers. Using the model's loaded software-developer cost ($135,980 × 1.30 ≈ $177k) as a proxy, that is ≈ **$1.4M–$2.7M/yr**. Scientist salaries were not sourced.
- Lab space, equipment, GMO/animal facilities, and ethics and regulatory costs: **not sourced**. They must be quoted before any plan.
- Funding sources to evaluate:
  - a dedicated round for the new entity;
  - academic partnerships;
  - Forskningsrådet, Horizon Europe or EIC (eligibility of each to be verified);
  - licensing income from the data-asset models.

**What not to do:** no human stimulation, no clinical procedures and no medical claims from the software company. The biotech arm would be a separate regulated activity, subject to the licences above.

---

## 11. Top risks to the plan

1. **Willingness to pay is unvalidated.** Every revenue line rests on ESTIMATE ACVs. **Mitigation:** gate G1; the design-partner programme; services revenue as a bridge.
2. **Legal rules encoded wrongly, or laws changing.** **Mitigation:** counsel review (R1), `review_status` on every rule, and "not matched" never shown as "not regulated".
3. **Funding risk.** NOK 1M lasts only 8–9 months with a small team, and the base plan needs the seed by months 9–10. The bear case has a gap of about $1.25M. **Mitigation:** switch to lean mode if the seed slips (18–22 months of runway), apply for the grants, hire only with 9 months of cash cover, and use prepaid annual contracts. The model ignores prepay, so it is conservative here.
4. **Name and trademark.** **Mitigation:** an attorney clearance search before public launch, with a fallback name ready.
5. **Big-platform entry.** A cloud provider or incumbent could add neural-data governance. **Mitigation:** RuleSet depth, and the lineage graph as system of record.
6. **Key-person risk.** Everything depends on a single founder. **Mitigation:** early senior engineering hire; documented architecture.
