# NeuroForge Bio: investor pitch (text version)

Prepared 2026-09-26 by the CEO agent for the owner, Marius Carlsson. **DRAFT for owner review. Not sent to anyone.**

**Read this first**
- **Pre-product.** Nothing described here is built. Every capability is *designed*, *planned* or *roadmap*.
- **No traction is claimed.** There are no customers, LOIs, pilots, partners or users.
- **Every financial figure is an ESTIMATE** from `investor\financial-model.py` (method and sources are in its ASSUMPTIONS section). Every price is an ESTIMATE until customer discovery validates it (`investor\PRICING.md`).
- **Name.** "NeuroForge Bio" is subject to a **pending trademark clearance**. The plain name "NeuroForge" is crowded: Neuroforge GmbH & Co. KG operates in Germany in AI/Big-Data software, and other AI businesses use it (`market\names.md`). An attorney search is required before public launch.
- **Not a medical device.** NeuroForge Bio is designed as non-device research and development software. It makes no diagnostic or therapeutic claims (`market\regulation.md` §4).
- Source grades: A = peer-reviewed or primary law; B = reputable press or tertiary; C = preprint or theory; D = company marketing.

---

## Slide 1. Title

**NeuroForge Bio**
*Versioned, comparable pipelines and neural-data governance, from electrode to model.*

The evidence and governance layer for neurotechnology teams. Pre-product, 2026.
Marius Carlsson, founder.

---

## Slide 2. Problem

Neurotech teams cannot easily show **what was done to their data**, or **what they are allowed to do with it**.

1. **Results depend on preprocessing choices, and those choices are rarely recorded or shared.**
   - All artifact-correction steps *reduced* decoding performance, and higher high-pass cutoffs increased it (Kessler et al., *Commun Biol* 2025, doi:10.1038/s42003-025-08464-3, A).
   - Across 43 pipelines there was "no single best pipeline" (Huang et al., *Psychophysiology* 2025, doi:10.1111/psyp.70197, A).
   - Only **20.9%** of 129 EEG-BCI papers made code or pipelines available (Peksa et al., *Sensors* 2026, doi:10.3390/s26175562, A).
2. **Neural data is now regulated, and the rules conflict.** Colorado and California cover central *and* peripheral nervous-system data; Connecticut covers the central nervous system only; California excludes data inferred from non-neural information (`market\regulation.md` §1, A). One EMG or EEG recording can be "neural data" in one state and not in the next.
3. **Consent withdrawal has to reach derivatives and trained models.** No neural-specific tool for this was found (`market\landscape.md` §3).
4. **Clinical-stage device teams need documented evidence.** FDA says implanted BCIs "should generally address the recommendations for an Enhanced Documentation Level" (FDA BCI guidance, 2021, with an updated note; `market\regulation.md` §4, A).

*Not yet measured:* how many engineering weeks startups lose to this. That is discovery question #1 (`market\validation.md` #1, verdict WEAK).

---

## Slide 3. Why now

| Driver | Evidence | Grade |
|---|---|---|
| State neural-data laws are in force | CO HB24-1058 (effective 7 Aug 2024); CA SB 1223 (Ch. 887, 28 Sep 2024); MT SB 163 (May 2025, via a peer-reviewed review; statute text not yet opened); CT PA 25-113 (CTDPA sections effective **1 Jul 2026**) | A |
| Federal attention | MIND Act introduced Sep 2025; it directs an FTC study (Young, Simon & Evans, *Neurology* 2026) | A |
| EU restrictions | AI Act Art. 5(1)(f) bans emotion inference in workplace and education (except medical or safety reasons), applicable from 2 Feb 2025 | B |
| Implants are entering trials | Paradromics IDE approved Nov 2025 and first implant Jun 2026; Precision 510(k) Apr 2025; Science's PRIMA EU launch Jul 2026 (`market\landscape.md` §1) | B / D |
| Capital is flowing to the sector | Neurotech devices received $1.2B of VC in 2024, "more than any other type of medical device" (*Sci Adv* 2026, citing HSBC, A). HSBC 1H 2026: "Neuro remained the strongest medtech investment category" (B) | A / B |

Sources for all rows: `market\regulation.md`, `market\sizing.md` §1.

---

## Slide 4. Product

**One lineage graph over neural data, pipelines and models, with three products built on it** (`market\new-ideas.md`, top 5; `architecture\BLUEPRINT.md` §0).

| Product | What it does | Status |
|---|---|---|
| **Open Core SDK** (Apache-2.0, per D6) | Python SDK, converters, validators, local provenance; integrates MNE, BIDS, NWB, LSL and BrainFlow rather than replacing them | Planned, months 0–3 |
| **Multiverse audit** | Runs a grid of preprocessing pipelines and reports how results shift, with every parameter recorded | Planned, months 0–3 (on public DANDI/OpenNeuro data) |
| **Consent & Deletion Ledger** | Per-channel jurisdiction classification (CO/CA/CT/MT and EU flags); versioned opt-in consent; withdrawal propagated to raw data, derivatives and trained models; signed deletion certificate | Planned, months 3–9 |
| **FDA Evidence Kit + latency harness** | Traceability, SBOM and OTS/SOUP documentation scaffolds from the same graph; reproducible end-to-end timing reports | Roadmap, months 9–18 |
| **Governed model registry** | Model provenance with use-restriction flags (EU AI Act 5(1)(f)) | Roadmap, only on customer pull |

**What we do not claim:** certified unlearning, HIPAA compliance, SOC 2, or "automated cleaning". The deletion guarantee is "retrained without the subject, with a provenance proof" (`BLUEPRINT.md` §8.4). Legal rules ship with a `review_status` and need counsel review before customers rely on them.

---

## Slide 5. How it works

```
 devices / files ──► ingest (open readers: MNE, pynwb, pyxdf, liblsl)
                         │
                         ▼
          ┌──────── provenance graph (Postgres) ────────┐
          │ subjects · recordings · channels · pipeline │
          │ runs · artifacts · datasets · models        │
          └────────────────────────────────────────────┘
             │                 │                    │
             ▼                 ▼                    ▼
     Consent & Deletion   Multiverse audit    FDA Evidence Kit
     Ledger (governance)  (reproducibility)   (regulated evidence)
```

- Signals are stored as chunked Zarr arrays on S3-compatible storage. Commodity storage is deliberate: low-latency storage is not a differentiator (`market\validation.md` #7).
- One Rust core (`nf-core`) sits behind the Python and C/C++ SDKs (D7).
- Every read, pipeline run and training job passes one consent-policy check (`BLUEPRINT.md` §8.3).

---

## Slide 6. Market

All figures are **ESTIMATES** from `market\sizing.md`.

| Layer | Figure | Method |
|---|---|---|
| **TAM** (all neural-data software) | $0.1B–$1.1B | Top-down from analyst figures that disagree by about 11x. **Not decision-grade.** |
| **SAM** (reachable with this product) | **$10M–$86M ARR** | Bottom-up: segment count × ACV across four segments |
| **SOM** (3 years after launch) | **~$2.4M ARR, 108 logos** | Bottom-up logo count |

Segments (count × ACV, ESTIMATE):
- **S1** clinical-stage and implant neurotech: 80–150 × $50k–$150k
- **S2** consumer neurotech under state laws: 100–300 × $10k–$50k
- **S3** research labs, paid institutional plans: 900–1,750 labs × $2k–$10k (10–20% paying)
- **S4** CNS pharma and CROs with EEG endpoints: 50–150 × $100k–$300k

**Honest read:** "picks and shovels for BCI hardware makers" alone is a small market. S1 alone is $4M–$22M. The money sits with **regulated buyers**: S1 plus S4 make up about 70–80% of SAM (`market\sizing.md` §4).

---

## Slide 7. Business model

Open core for distribution, with a paid hosted platform. The value metric is **data subjects plus devices under management**, not GB. All prices are **ESTIMATE** (`investor\PRICING.md`).

| Tier | Buyer | Price (ESTIMATE) |
|---|---|---|
| Open Core | Individual researchers | $0 |
| Lab / Institution | Labs, core facilities (can be budgeted under the NIH DMS policy) | $3k–$10k/yr |
| Startup | Neurotech startups with ≤$2M raised | $300–$800/mo |
| Growth | Series A–C and clinical-stage neurotech | $50k–$150k/yr |
| Enterprise / Pharma | CNS sponsors, CROs, large device firms | $100k–$300k+/yr |
| Services | Multiverse audit, timing report, conversion | $5k–$40k per engagement |

Comparables (all D, vendor pages): NeuroPype startup $79–$99/mo; EmotivPRO $1,068–$2,689/yr; Aptible HIPAA Production $499/mo; W&B gates HIPAA to Enterprise; Flywheel quote-only in regulated imaging.

Model gross margin (base, ESTIMATE): 52% in year 2, rising to 74% in year 5.

---

## Slide 8. Go-to-market

Sequencing follows `market\pricing-and-gtm.md` §5:
1. **Months 0–3 (credibility, no customers needed):** release the open-core SDK and validator. Run the multiverse audit on public DANDI/OpenNeuro data and publish the results.
2. **Months 3–9:** ledger MVP and the Startup tier. Recruit **5 design partners** at 50% off Growth for 12 months, in exchange for case studies.
3. **Months 9–18:** FDA Evidence Kit and latency harness; Growth tier; first pharma pilot.

Channels:
- **Integrations** where users already are: MNE (308k downloads/month), pynwb (108k), pylsl (34k) (pypistats, Sep 2026).
- **Content:** a free neural-data law tracker (not legal advice); peer-reviewed benchmark papers.
- **Events:** International BCI Society Meeting, 7–10 Jun 2027, Šibenik; SfN.
- **Partners:** CatalystNeuro for NWB conversion (partner, do not compete); the OpenBCI/BrainFlow ecosystem.

**First step:** the owner runs 15–20 discovery interviews before building paid features. Full plan: `marketing\MARKETING-PLAN.md`.

---

## Slide 9. Competition

| Category | Examples (from `market\landscape.md` §2) | Where they stop |
|---|---|---|
| Open-source analysis libraries | MNE, EEGLAB, braindecode, pyRiemann, SpikeInterface | Libraries, with no governance or provenance service |
| Public archives | DANDI, OpenNeuro, brainlife | Sharing and academic compute. Free and publicly funded, so we integrate with them |
| Real-time pipeline products | NeuroPype / NeuroScale | Closest commercial analogue (academic free, startup $79–99/mo). No neural-data governance found |
| Conversion services | CatalystNeuro (69 labs) | Consulting, not compliance-grade. A partner, not a target |
| Regulated data platforms | Flywheel | Imaging-first. Shows that pharma pays for compliance-grade research data |
| HIPAA cloud | AWS (175+ eligible services), Aptible | Commodity infrastructure, with no neural formats or neural-law mapping |
| Vertically integrated BCI leaders | Neuralink, Synchron (Chiral model) | Build their own software. **Not our buyers** |

**Whitespace:** neural-specific governance (consent, deletion lineage, jurisdiction mapping) and regulated evidence. "None found in this pass" does not mean none exists.

---

## Slide 10. Moat (what compounds, and what does not)

What does **not** make a moat: HIPAA infrastructure (a commodity, `market\validation.md` #2), storage, cleaning algorithms or SDK code (open source by design).

What can compound:
1. **Machine-readable neural-law RuleSets.** Versioned, counsel-reviewed rules per jurisdiction, maintained as laws change. They also power the public law tracker. This gets harder to copy as more jurisdictions are added.
2. **The lineage graph as the system of record.** Once consent, pipeline runs and model versions live in one graph, the deletion certificate and the FDA evidence come from it, which creates switching cost.
3. **Published reproducibility evidence.** Multiverse results on public datasets become citable references.
4. **Trust posture.** Open-core code, no trackers on our own site (D9), and honest status labels.

All four are **plans**. None exists yet.

---

## Slide 11. Trust and security

Source: `security\STANDARDS-MAP.md` (draft by the security expert). **Nothing here is audited or certified.** Every control is *designed*, *planned* or *roadmap*.

| Area | Posture | Status |
|---|---|---|
| Application security | OWASP ASVS 5.0 **Level 2** as the release gate for everything internet-facing. **Level 3** for the chapters that guard neural data (authorisation, cryptography, data protection, logging). **Full L3** for the consent ledger, deletion and key management | designed |
| Secure development | NIST SSDF (SP 800-218) and IEC 81001-5-1 lifecycle for components offered as SOUP; SLSA Build L2 → L3 target; CycloneDX SBOM per release; signed artifacts | planned |
| EU law | GDPR Art. 32 controls; **EU Cyber Resilience Act** readiness for the SDKs (reporting obligations have applied since 11 Sep 2026); NIS2 supplier-ready controls for customers | designed / planned |
| Customers' device submissions | Evidence for FDA's premarket cybersecurity guidance (final, 3 Feb 2026) and EU MDR Annex I §17: SBOM, support levels, vulnerability status | planned |
| Certifications | ISO/IEC 27001, then 27701; SOC 2 Type II when 2–3 design partners ask | **roadmap** |
| Safety boundary | The platform and SDKs **never command stimulation or any actuator**. They are read-only toward acquisition hardware | designed (a permanent rule) |

Protecting data here matters more than usual, because a breach cannot be undone: "you cannot rotate a brain" (`security\STANDARDS-MAP.md` §1.1).

*Not legal or regulatory advice. Counsel and a regulatory consultant must confirm each applicability call.*

---

## Slide 12. A lawful neural-data asset (upside, not in the base case)

Source: `investor\DATA-REVENUE-STRATEGY.md`. Risk ratings: nfb-legal-privacy, 2026-09-26 (an AI legal-team draft, not advokat advice; counsel must confirm). Not legal advice.

**Principles**
- **Customers own their data.** Any contribution to a NeuroForge Bio research pool is opt-in, **OFF by default**, and needs explicit consent scopes.
- Proposed new consent-ledger scopes: *internal R&D* and *future biotech/neurobiology research*. Legal has narrowed the second scope to nervous-system research, and each health-research project still needs REK approval. The *model training* scope already exists. Draft consent templates exist in `legal\data-agreements\CONSENT-SCOPES.*`.
- **Withdrawal always works.** It propagates through the lineage graph into derivatives and models.
- **Never a data broker:** no sale of individual-level records; no insurer, employer, advertiser or law-enforcement buyers.

**How the asset builds up**
- Opt-in pool, in exchange for credits or discounts.
- Our own REK/IRB-approved research programmes with broad consent (non-invasive EEG only, no stimulation).
- Curated public datasets (OpenNeuro/DANDI, with licences checked).
- Synthetic data, released only after membership-inference tests pass.
- Tiered storage (S3 Standard $0.023 down to Glacier Deep Archive $0.00099 per GB-month; AWS pricing page, D).

**Top revenue models by risk-adjusted value** (ESTIMATE, year-5 range):
1. **Compute-to-data / federated analysis** (the data never leaves): $0.1M–$1.5M
2. **Pharma/CRO endpoint analytics and data clean rooms:** $0.2M–$2.1M
3. **Consent and provenance attestation** (attestation reports, not certification): $0.1M–$1.1M
4. **Benchmarks and held-out evaluations:** $0.05M–$0.6M
5. **Grants and tax credits (non-dilutive):**
   - SkatteFUNN: 19% of R&D costs.
   - Innovation Norway start-up grant: up to NOK 150k.
   - EIC Accelerator: grant below €2.5M; Norway's eligibility is UNVERIFIED.

**Rejected:** insurer or employer uses (AI Act Art. 5 and state-law risk), selling raw data, and advertising, neuromarketing or law-enforcement uses.

**Data-asset upside to base revenue**, year 5 (ESTIMATE): low $0.13M / mid $0.80M / high $2.40M. In the model (`financial-model.py`, scenarios base+data_*), year-5 recognised revenue is $3.46M / $4.14M / $5.74M, against $3.34M in the base case. Year-5 cash is $7.1M / $8.2M / $10.3M. **The base case excludes this revenue.**

---

## Slide 13. Traction

**Pre-product.** There are no customers, revenue, LOIs, pilots or partnerships.

What exists today (internal work, not traction):
- Market, regulation and pricing research with graded sources (`market\`).
- An enterprise architecture blueprint and build guide (`architecture\`).
- Website designs in two themes (`design\`).
- A computational research programme on closed-loop somatosensory feedback (`research\somatosensory\`). It is simulation only, with no human work.

**Next 90-day milestones** that would count as traction: 15–20 discovery interviews completed; the open-core SDK published; multiverse results on public data published; 3–5 design partners signed.

---

## Slide 14. Team

**Marius Carlsson, founder.** Background: [OWNER TO WRITE: must be factual].

**Hiring plan** (base case, `investor\financial-model.py`, ESTIMATE):

| Year-end | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| Employees, excl. founder | 4 | 12 | 13 | 25 | 33 |

- **First hires (after the seed, around month 9):** 3 software engineers (Rust/Python/platform) and 1 neuro-data scientist.
- **Year 2:** DevOps/security, regulatory/QA, product designer, account executive, customer success, and marketing/developer relations.
- **Advisors to recruit (not engaged):** privacy counsel, an FDA regulatory consultant, and a neuroscientist or clinician advisor.

Headcount totals in the model include the founder (5, 13, 14, 26, 34). **Nobody is hired before the seed closes.** Each hire needs cash covering 9 months of projected burn, so year 3 pauses hiring until the Series A.

Development tooling includes AI coding and research assistants. They are tools, not team members.

---

## Slide 15. Roadmap

| When (from funding) | Milestone | Status |
|---|---|---|
| Months 0–3 | Website (clinical theme); open-core SDK and validator; multiverse audit on public data | Planned |
| Months 3–9 | Consent & Deletion Ledger MVP; Startup tier; 3–5 design partners; privacy counsel reviews the RuleSets | Planned |
| Months 9–18 | FDA Evidence Kit and latency harness; Growth tier; first pharma pilot; SOC 2 Type II started when partners ask | Roadmap |
| Years 2–3 | EU region (GDPR); Part 11 workflows for CNS trials; governed model registry if customers pull for it | Roadmap |
| Years 3–5 | US + EU scale; Enterprise/Pharma tier; C++/Unity/Unreal SDKs only on customer pull; opt-in research pool (default OFF) | Scenario |
| Years 8–15 | **Biotech and neurobiology research arm.** It builds on the consented data asset and our models: biomarkers, target discovery, somatosensory and neuroprosthetic research. Wet-lab or clinical work needs REK/ethics approval and other licences (see `SCALING-PLAN.md` §10) | Scenario |

The 10–15 year view is in `investor\SCALING-PLAN.md`. Beyond year 2 it is scenarios, not forecasts.

---

## Slide 16. Financials (ESTIMATE, base case)

Source: `investorinancial-model.py` → `financial-model.csv`, with the funding path corrected on 2026-09-26.
- The first round is **NOK 1M** (≈ USD 105k at 9.5063 NOK/USD, the Norges Bank rate for 2026-09-25).
- The seed closes in month 9. The paid launch is in month 17.

| Model year | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| End ARR | $0.00M | $0.28M | $1.15M | $2.28M | **$3.63M** |
| Recognised revenue | $0.04M | $0.27M | $0.92M | $2.05M | **$3.34M** |
| Gross margin | 36% | 52% | 62% | 74% | 74% |
| Net burn | $0.35M | $1.35M | $2.32M | $2.66M | $3.45M |
| Year-end cash | $0.81M | $3.46M | $1.14M | $10.48M | $7.03M |
| Headcount (end of year) | 5 | 13 | 14 | 26 | 34 |
| Paying logos | 0 | 19 | 54 | 95 | 140 |

**Scenarios, year-5 end ARR:**
- Bear: $1.15M, with a funding gap of −$1.25M in month 49.
- Base: $3.63M.
- Bull: $7.00M.
- Lean (founder-led, no hires): no ARR. It relies on about one $20k audit per quarter, which is unvalidated.

**Data-asset upside (not in base):** year-5 revenue of $3.46M / $4.14M / $5.74M in the low / mid / high cases (slide 12).

**SOM check:** 36 months after launch (model month 52), base ARR is $2.66M with 109 logos, against the sizing SOM of $2.4M and 108 logos.

**Biggest sensitivities** (year-5 cash impact):
- a 1.45× loading factor: −$1.45M;
- a 6-month longer build: −$1.42M;
- all S2 customers on the Startup tier: −$0.83M.

**Not profitable by year 5 in any growth scenario.** Cost inputs still to be quoted: counsel, SOC 2, pen test and regulatory consultant. Salary base: BLS median $135,980 (A) × 1.30 (ESTIMATE).

---

## Slide 17. The ask

**Now: a first round of NOK 1,000,000** (≈ USD 105k). In market terms this is a **pre-seed (angel) round**, not a Series A. A Series A usually comes after revenue traction. The owner decides the amount and terms. See `investor\FUNDING-ROUND.md`, `dilution.py` and `ROUND-ASSUMPTIONS.md`; the draft contracts in `legal\` use the same numbers.

**Proposed structure** (ESTIMATE; lowest dilution that a real investor could still accept):
- A priced share issue of **NOK 1M at NOK 10M pre-money**, with a pro-rata right in the next round. Floor: NOK 8M pre-money.
- Fallback: a convertible loan with a NOK 12M cap and a 20% discount.

| Founder ownership along the base path (ESTIMATE) | Owner % |
|---|---|
| After this round | **90.9%** |
| After the seed: NOK 10M at NOK 40M pre-money, with a 10% option pool | 63.6% |
| After round N2: USD 4.0M (≈ NOK 38.0M) at NOK 120M pre-money | 48.3% |
| After the Series A: USD 12M | 36.2% |

**How far NOK 1M gets us** (no revenue assumed; `prephase-runway.csv`):

| Mode | Monthly burn | Runway | With grants |
|---|---|---|---|
| **Lean:** founder + AI tools + 0.1 FTE contractor, minimal cloud | ≈ NOK 50k | **18 months** | **22 months** |
| **Small team:** founder + 0.5 FTE contractor | ≈ NOK 114k | **8 months** | **9 months** |

The grants modelled are conditional on the AS existing and on approval, and none is guaranteed:
- Innovation Norway's start-up grant (oppstartstilskudd 1): up to NOK 150k.
- SkatteFUNN: 19% of eligible R&D costs. It is paid through the tax settlement, so the cash arrives around month 21 (UNVERIFIED).
- Forskningsrådet: not modelled, because its programme page could not be opened.

**What the round buys** (before the seed, which must close by months 9–10 in the base plan):
- 15–20 discovery interviews, with the pricing hypotheses tested;
- the open-core SDK and multiverse results on public data, published;
- a trademark clearance search and a first privacy-counsel review;
- 3–5 design partners recruited;
- grant applications.

If the seed is late, switch to lean mode: 18–22 months of runway.

**Top risks:**
1. Willingness to pay is unvalidated.
2. Seed timing: the small-team pre-phase has only about 8–9 months of runway, and the base plan's minimum cash is about $13k in month 8.
3. Neural-law RuleSets and consent scopes need a lawyer's review. The name needs trademark clearance (Neuroforge GmbH, Germany).
