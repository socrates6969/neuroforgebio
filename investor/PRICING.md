# NeuroForge Bio: Pricing

Prepared 2026-09-26 by the finance/BA worker for the CEO queen. Owner: Marius Carlsson.

**Status: pre-product. Every price on this page is an ESTIMATE until it is validated in customer discovery.** There are no customers, quotes, LOIs or paying users. Product features are **designed / planned / roadmap**; nothing is live.

Sources are files in `C:\Users\mariu\neuro-company\market\` (section cited). Comparable prices were opened on the vendors' own pages by the market BA (`market\pricing-and-gtm.md` §1) and are graded **D** (company marketing/pricing page). Numbers in the financial model come from `investor\financial-model.py`.

---

## 1. Principles

1. **Academic use is free.** Every comparable gives individual academics a free tier: NeuroPype Academic, W&B free academic Pro licence, and DANDI/OpenNeuro/brainlife (`pricing-and-gtm.md` §1, patterns 1). The Open Core is our distribution channel, not a revenue line (`validation.md` #3).
2. **Compliance and governance are the upsell gate.** W&B and Aptible both gate HIPAA/SSO/audit logs behind higher tiers (`pricing-and-gtm.md` §1, pattern 2). For us the gate is neural-data governance: consent/deletion lineage, jurisdiction flags and FDA-facing evidence (`validation.md` #2, #8).
3. **Value metric = data subjects + devices under management**, not GB. Consent obligations scale with data subjects; timing/evidence work scales with devices. Storage is a commodity (AWS HealthLake $0.25–$0.37/GB-month, S3 $0.023/GB-month), so it is not the metric (`pricing-and-gtm.md` §2; `architecture\BLUEPRINT.md` §12).
4. **Regulated buyers pay by quote.** Flywheel is quote-only (`pricing-and-gtm.md` §1, pattern 4). Our Growth and Enterprise tiers publish a "from" band and are quoted.

## 2. Comparables (all grade D, from `market\pricing-and-gtm.md` §1)

| Vendor | What it is | Public price | What we take from it |
|---|---|---|---|
| EmotivPRO | EEG analysis SaaS bundled with hardware | Lite $0; Standard $89/mo billed annually ($1,068/yr); Standard Team $224.08/mo ($2,689/yr); Performance by quote | Ceiling for per-seat EEG analysis; Lab tier must beat it on institutional value, not seats |
| NeuroPype (Intheon) | Real-time biosignal pipelines + cloud | Academic free; Startup/Individual $79–99/mo (≤$200K revenue or raised); Enterprise by quote | The price floor we will be compared with; eligibility-gated startup pricing |
| Weights & Biases | ML dev-infra | Free (≤5 seats); Pro from $60/mo; Enterprise custom (HIPAA, SSO, audit logs); academic free Pro | Compliance as enterprise gate |
| Aptible | HIPAA PaaS | Dev $0 + usage; Production $499/mo + usage; Enterprise custom | Anchor that small teams already pay ~$500/mo for compliance infrastructure |
| AWS HealthLake | Managed FHIR | $0.27/data-store-hour; $0.25–$0.37/GB-month; $0.19/GB export | Storage is usage-priced commodity; do not sell GB |
| Flywheel | Regulated imaging research data platform | Quote only (claims 21 CFR Part 11; "10 of the top 20 biopharma") | Model for Enterprise/Pharma: quote, validation packages |

## 3. Tiers (all prices ESTIMATE)

### 3.1 Open Core: **$0**
- **Target:** individual researchers, students, open-source users (MNE/BIDS/NWB/LSL ecosystem).
- **Value metric:** none (free, self-hosted).
- **Included (planned):** Apache-2.0 SDK (Python first), converters, validators, local provenance graph, MNE/BIDS/NWB/LSL/BrainFlow integrations, multiverse runner (`pricing-and-gtm.md` §2; `DECISIONS.md` D6).
- **Reasoning:** matches the free academic norm (NeuroPype, W&B, DANDI). Distribution via PyPI where users already are (MNE 308k downloads/month, `pricing-and-gtm.md` §4).
- **Comparables:** NeuroPype Academic $0 (D); W&B academic Pro $0 (D); EmotivPRO Lite $0 (D).

### 3.2 Lab / Institution: **$3,000–$10,000 per lab per year** (ESTIMATE; model uses $4,000)
- **Target:** EEG/ephys labs and core facilities, paid by the institution or a grant.
- **Value metric:** per lab (site licence for cores), with a data-subject band; not per seat.
- **Included (planned):** hosted provenance, DANDI/OpenNeuro publishing, NIH DMS reporting, team seats (`pricing-and-gtm.md` §2).
- **Reasoning:** NIH DMS policy asks investigators to budget for data management and sharing, so the fee can be written into grants (`pricing-and-gtm.md` §2; `new-ideas.md` #5). The model uses $4k (sizing.md §3 SOM S3 ACV) because individual academics expect free.
- **Comparables:** EmotivPRO Standard $1,068/yr and Team $2,689/yr (D) set the per-seat reference; hosted automation for conversion is ESTIMATE $3k–15k/lab/yr (`new-ideas.md` #5).

### 3.3 Startup: **$300–$800 per month** (ESTIMATE; billed annually)
- **Target:** neurotech startups with ≤$2M raised; university spinouts.
- **Value metric:** data subjects + devices under management, in bands (band edges are a discovery hypothesis, see §6 H3).
- **Included (planned):** Consent & Deletion Ledger core states, hosted pipelines, latency harness (self-serve), SSO (`pricing-and-gtm.md` §2).
- **Reasoning:** priced between NeuroPype ($79–99/mo) and Aptible ($499/mo). The compliance value (four state neural-data laws; CT effective 1 Jul 2026, `validation.md` #8) justifies a premium over NeuroPype.
- **Upgrade path:** consumer neurotech with many data subjects moves to ledger volume pricing, ESTIMATE $500–$3,000/mo (`new-ideas.md` #1). The model blends S2 as 55% Startup tier ($550/mo) + 45% volume ($3,000/mo) = ~$19.8k ACV, matching `sizing.md` §3 S2 ACV $20k.
- **Comparables:** NeuroPype Startup $79–99/mo (D); Aptible Production $499/mo + usage (D).

### 3.4 Growth: **$50,000–$150,000 per year** (ESTIMATE; model uses $75,000)
- **Target:** Series A–C and clinical-stage neurotech (IDE/EFS stage device makers).
- **Value metric:** data subjects + devices under management; plus product lines under the latency harness.
- **Included (planned/roadmap):** full ledger (all covered jurisdictions + EU AI-Act flags), FDA Evidence Kit, multiverse audits, BAA-capable deployment, audit exports (`pricing-and-gtm.md` §2).
- **Reasoning:** the ACV band from `sizing.md` §3 S1. The Evidence Kit targets FDA's Enhanced Documentation Level expectation for implanted BCIs (`new-ideas.md` #2). The model uses $75k (sizing.md SOM).
- **Comparables:** Flywheel quote-only (D); Aptible Production + usage (D) as the infrastructure floor; W&B Enterprise custom (D) as the compliance-gated tier.

### 3.5 Enterprise / Pharma: **$100,000–$300,000+ per year** (ESTIMATE, quote; model uses $150,000)
- **Target:** CNS pharma sponsors, CROs, large device firms.
- **Value metric:** per programme/study, scaled by data subjects and sites.
- **Included (roadmap):** 21 CFR Part 11 workflows, single-tenant/VPC, validation packages, SLAs (`pricing-and-gtm.md` §2; `new-ideas.md` #10).
- **Reasoning:** Flywheel-style quote. S1+S4 are ~70–80% of the SAM range (`sizing.md` §4).
- **Comparables:** Flywheel quote only (D); AWS HealthLake usage pricing (D) as the underlying cost floor.

### 3.6 Services (add-on): **$5,000–$40,000 per engagement** (ESTIMATE; model uses $20,000 average)
- **Target:** any tier.
- **Included:** multiverse robustness audit (ESTIMATE $10k–40k, `new-ideas.md` #4), timing report (ESTIMATE $5k one-off, `new-ideas.md` #3), submission package, format conversion.
- **Reasoning:** early revenue while the product matures (`pricing-and-gtm.md` §2). Not counted in ARR.
- **Comparables:** CatalystNeuro offers NWB conversion services to 69 labs (`new-ideas.md` #5); we partner with rather than compete against it.

## 4. Design-partner offer

- **5 design partners at 50% off Growth for 12 months**, in exchange for case studies and anonymised metrics (`pricing-and-gtm.md` §4).
- At the model's $75k Growth list price: $37,500 for year 1 per partner; list price from month 13.
- Model effect (base): discount of ~$8k in Y1 and ~$130k in Y2 of recognised revenue; billed ARR at end of Y1 is $0.11M vs $0.15M list.
- Conditions to test: written consent to publish a case study; eligibility (clinical-stage or IDE-bound); annual prepay. Case studies are only published with the partner's written approval.

## 5. Mapping to the financial model

| Segment (sizing.md §3) | Tier | Model ACV (ESTIMATE) | SOM logos | Churn/yr (ESTIMATE) |
|---|---|---|---|---|
| S1 clinical-stage neurotech | Growth | $75,000 | 15 | 10% |
| S2 consumer neurotech | Startup + ledger volume | ~$19,800 blended | 30 | 20% |
| S3 labs | Lab | $4,000 | 60 | 15% |
| S4 pharma/CRO | Enterprise | $150,000 | 3 | 10% |
| Services | Services | $20,000/engagement | n/a | n/a |

Base case reaches ~$2.66M billed ARR and ~109 logos 36 months after paid launch (model month 45), about 10% above the $2.4M SOM because of the 8%/yr expansion assumption.

## 6. Pricing hypotheses to test in discovery

The **owner** runs every interview. Agents contact no one. "Test" means an interview question, a public-document review, or a mock price page shown in an interview.

| # | Hypothesis | How to test | Pass signal (ESTIMATE threshold) |
|---|---|---|---|
| H1 | Clinical-stage device makers will pay ≥$50k/yr for FDA evidence + latency verification | 10 interviews with clinical-stage firms (`validation.md` riskiest Q1). Ask current spend on regulatory consultants and in-house evidence work; show the Growth band | ≥4 of 10 say the band fits budget or current spend exceeds it |
| H2 | Consumer neurotech firms lack neural-specific consent tracking and will pay $300–3,000/mo | Review public privacy policies for neural-data consent language (no contact, `validation.md` Q2); then owner interviews 8–10 firms | ≥50% of policies lack neural-specific language; ≥3 interviewees accept the band |
| H3 | Data subjects + devices is an understood, acceptable value metric | Show 2 price-page mocks (per-subject bands vs flat per-seat) in interviews | Majority prefer or accept the subject/device metric |
| H4 | Labs can budget $3k–10k/yr under NIH DMS | Owner interviews 10 PIs/core managers; ask what their DMS budget line covers | ≥3 of 10 would write it into a grant |
| H5 | 50% off for 12 months is enough to secure 5 design partners | Offer in interviews with H1 qualifiers | 5 partners from ≤15 qualified prospects |
| H6 | Startups accept a premium over NeuroPype ($79–99/mo) because of compliance value | Ask startups which tools they pay for today; test $300 vs $550 vs $800 anchors (Van Westendorp-style questions) | Acceptable range overlaps $300–800 |
| H7 | Pharma/CROs buy a Part 11 EEG platform at $100k+ | 5 owner interviews with CNS sponsor/CRO data leads; ask about current EEG core-lab spend | ≥1 pilot interest |
| H8 | Services at ~$20k per audit sell before the platform | Offer multiverse audit on the published DANDI/OpenNeuro results (`pricing-and-gtm.md` §5) | ≥2 paid engagements in first 9 months |

## 7. Pricing risks

1. **NeuroPype undercuts at $79–99/mo** for startups (`pricing-and-gtm.md` §1). Mitigation: do not compete on pipelines alone; the Startup tier's value is the Consent & Deletion Ledger, which has no neural-specific competitor found (`new-ideas.md` #1). If H6 fails, drop Startup to ~$199/mo and push upgrades via the ledger volume metric (model sensitivity: all S2 on Startup tier lowers Y5 ARR by ~$0.66M).
2. **Academics expect free** (DANDI, OpenNeuro, brainlife, W&B academic, NeuroPype academic). Mitigation: sell to institutions and grant budgets, not individuals; keep Open Core free.
3. **Leaders build in-house** (Synchron Chiral, Neuralink; `validation.md` #4). Mitigation: target the long tail of clinical-stage startups and pharma, not the top 7.
4. **HIPAA is a commodity** (Aptible $499/mo; AWS 175+ eligible services; `validation.md` #2). Never price "HIPAA" as the premium; price governance and evidence.
5. **Long regulated sales cycles** delay Growth/Enterprise revenue. The model's largest sensitivity is a 6-month launch slip (−$1.78M year-5 cash).
6. **Design-partner anchoring:** partners may resist the jump to list at month 13. Put the list price and step-up in the design-partner agreement.
7. **Legal-accuracy liability:** a ledger that mislabels a jurisdiction is a product risk. Privacy counsel review before the first paying ledger customer (`DECISIONS.md` D10) is in the model as an ESTIMATE that must be quoted.
