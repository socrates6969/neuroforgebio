# NeuroForge Bio: what the AI layer does for investors, with its limits

Prepared 2026-09-26 by the code architect for the owner (Marius Carlsson). Status: **pre-product.**
- M2 (ingest) and M3 (pipelines + provenance) are built and tested locally. Nothing is deployed, and there are no customers (`docs/hive/M2-REPORT.md`, `M3-REPORT.md`).
- The AI layer is **designed, not built** (`architecture/AI-LAYER.md`).
- Figures are sourced or labelled **ESTIMATE**. Nothing here is a forecast of investor returns.

## 1. The one-line thesis

**Neural AI models are commoditising, while the evidence for what they do on a given customer's data, and the right to train on that data, are not.** NeuroForge Bio's AI layer is built to own the second part: evaluated, consent-gated, provenance-tracked AI on neural data.

Evidence that the models are commoditising:
- Independent benchmarks in 2025–26 found that EEG foundation models "do not consistently outperform time-series FMs".
- Pretrained models "perform largely on par" (NeuroAtlas, arXiv:2605.14698).
- "Simpler models often remain competitive" (EEG-Bench, arXiv:2512.08959).
- Open weights exist: REVE's weights are released.

All four points are preprints, cited via `research-lab/ai/RAPPORT.md` §a.1.

## 2. Advantages, stated as precisely as we can

### 2.1 Workflow lock-in (the strongest advantage)
- Every AI output is linked to a model digest, training manifest, evaluation card, consent basis and human approval. All of these sit in the customer's lineage graph (AI-LAYER §1.1; ADR 0011).
- After a year of use, a customer's QC history, model evaluation cards, deployments and deletion certificates live there. The FDA Evidence Kit and audit exports are generated from it.
- Leaving means rebuilding that record elsewhere. This extends the switching-cost argument already in `investor/PITCH.md` slide 10 ("the lineage graph as the system of record").
- **Caveat:** it is a plan. Switching cost only exists once customers use it.

### 2.2 Defensibility against pure-model competitors
- A pure-model company sells a better decoder or foundation model. The evidence above says that edge is **narrow and unstable**:
  - In one negative-control study, a randomly initialised encoder beat pretrained REVE on a clinical dataset.
  - In the same study, all five encoders decoded *dataset identity* at 1.000, a shortcut risk (arXiv:2607.24519, preprint, via the ai report).
- NeuroForge Bio does not compete on the model. It is the **neutral place where any model is scored the same way**:
  - leak-proof splits and SzCORE-style event scoring;
  - the same input pipeline for foundation models and baselines;
  - negative controls.
- If models commoditise faster, the referee role gets *more* valuable, because buyers need a way to choose.
- The core of that referee already exists in research. The nfharness split engine, guards, leak meter, event scorer, CIs and evaluation card are **VERIFIED** with independent review (`research/neurobiology/PLATFORM_FEATURES.md` features 1–6). Negative controls are still **PENDING**, and we say so.
- Vertically integrated BCI leaders build their own AI (for example, Synchron's "Chiral" foundation model; `market/landscape.md` §1). They are **not** our buyers, and a better model from them does not displace an evaluation and governance layer used by everyone else.

### 2.3 A consented training asset: real, but small and slow (honest version)
Many AI pitches claim a "data moat". Ours is **deliberately limited**:
- **We cannot train on customer data.** NeuroForge is a processor. DPA § 3.4 forbids using customer data for our own purposes, and doing so would make us a controller in breach (GDPR Art. 28(10); `legal/data-agreements/RISK-MEMO.md` §0).
- The only data NeuroForge may train its own models on is:
  - **Public, licence-checked data.** For scale, DANDI has 1,185 dandisets (~2.39 PB) and OpenNeuro 1,902 datasets (`market/landscape.md` §2). Many have CC-BY/CC0 licences; others are excluded until clarified (`investor/DATA-REVENUE-STRATEGY.md` Part B).
  - **Synthetic data** from our simulator.
  - An **opt-in research pool**. It is OFF by default and gated on a DPIA and REK approval (`legal/data-agreements/CONSENT-SCOPES.en.md`). The opt-in rate is **unknown** and must be tested in discovery.
- What this gives investors is **a training asset that is clean by construction**. Every record carries a versioned consent grant, scope-specific withdrawal and retraining propagation.
- That matters because:
  - neural data is special-category data (RISK-MEMO §1);
  - CT PA 25-113 requires consent before selling sensitive data;
  - "they train AI on your brain" is the brand risk the data strategy itself flags (DATA-REVENUE-STRATEGY A5).
- **We do not claim this asset is large or that it will be.** The base financial model **excludes** pool-based revenue (DATA-REVENUE-STRATEGY §0.5). The data-asset upside in the pitch is ESTIMATE $0.13M / $0.80M / $2.40M in year 5 (low/mid/high; `investor/PITCH.md`). It remains an **upside scenario**, not the thesis.

### 2.4 AI that ties directly to the paid governance product
- **Channel-type and montage inference** (AI-LAYER A2) sets whether a channel is central or peripheral nervous system. Colorado and California cover central *or* peripheral, while Connecticut covers central only (`market/regulation.md` §1). So an AI suggestion changes which law applies, and a steward confirms it.
- **Consent-taint retraining** (C7) answers "what happens to the AI when someone withdraws?" with a signed certificate and a new evaluation card. This is the market research's #1 ranked idea (`market/new-ideas.md` #1).
- These features make the governance product stickier. They are not bolt-on demos.

### 2.5 Gross-margin effects (ESTIMATE)
- **Baseline.** The model's gross margin is 36% (Y1) → 52% (Y2) → 62% (Y3) → 74% (Y4–Y5), base case, ESTIMATE (`investor/PITCH.md` slide 7/financials). It does not include any AI-layer compute.
- **Design choice that protects margin: CPU first.**
  - QC, quality scores, montage inference, anomaly detection, drift, recommendations, evaluation cards and search all run on the existing CPU worker fleet (AI-LAYER §7).
  - Their marginal cost sits inside the infrastructure band already modelled (BLUEPRINT §12.1). Assumption: about 1 worker-minute per recording-hour of QC, **unmeasured**, to be measured in build step 8.1.
- **GPU work** (foundation-model embeddings, fine-tuning, benchmark campaigns) is billed to customers as **compute pass-through plus margin**. It is priced per job, not bundled. Reference costs: Sigma2 category C 35 NOK/GPU-h and Lambda H100 3.99 USD/h (ai report §a.5). One internal benchmark campaign is ESTIMATE 35–70 kNOK (Sigma2) or 4–8 kUSD (Lambda).
- **The LLM assistant is the margin risk:**
  - Decided 2026-09-26: the Anthropic API (Haiku 4.5 for routine questions, Sonnet 5 for complex ones). At official prices of $1/$5 and $2/$10 per MTok, and assumed token counts, that is ≈ $0.012–$0.024 per question, or ≈ $12–$24 per 1,000 questions (ESTIMATE; AI-LAYER C2a). It is capped by per-tenant quotas, prompt caching and opt-in.
- **Net ESTIMATE:** if GPU is pass-through and the assistant is quota-capped, the AI layer should move modelled gross margin by **less than a few points either way**. This is a design target, not a measurement. It should be re-run in `financial-model.py` once 8.1 and 8.7 have measured costs.
- **Pricing lever (ESTIMATE, to test in discovery):**
  - AI QC and search are included in every paid tier (retention, not an upsell).
  - The assistant, drift monitoring and evaluation cards for external models go into Growth/Enterprise (`investor/PRICING.md` tiers).
  - GPU jobs are metered.

### 2.6 A diligence-ready demo
An investor or acquirer can check every claim in one session, with no trust required:
1. Upload a synthetic recording and get the QC flags.
2. Open the provenance node and see the model digest, card and review status.
3. Re-run it and get the same output hash.
4. Ask the assistant a question. Every sentence cites a record ID, and a cross-tenant question is refused.
5. Withdraw a synthetic subject. A model is flagged, retrained and re-carded, and a signed certificate is issued.

This matches the owner's standing rule that only independently verified results are presented.

## 3. Risks (to be read with equal weight)

| Risk | Why it is real | Mitigation (designed) |
|---|---|---|
| **Models commoditise, including ours** | Open foundation-model weights exist; benchmarks show parity with baselines (ai report §a.1) | We do not sell model superiority. The value is evaluation, provenance and governance (ADR 0011) |
| **Evaluation-tool competition** | At least six EEG foundation-model benchmarks already exist (AdaBrain-Bench, EEG-FM-Bench, OmniEEG-Bench, among others; ai report §a.1). The ai report notes "the niche is not empty" | Differentiate on clinical event metrics, negative controls, a bit-identical card and integration with consent and deletion, not on another leaderboard |
| **Regulation: AI Act** | Transparency rules (Art. 50) from 2 Aug 2026; high-risk rules for medical-device AI from 2 Aug 2028 (ai report §a.6; wording of Art. 50 and the Art. 2(6) research exemption UNVERIFIED). Norway's KI-loven is targeted for 2027 | RUO positioning, no medical purpose, AI disclosure in the assistant. Model cards and provenance double as technical documentation for customers who become high-risk. Legal read before the EU pilot |
| **Regulation: MDR/FDA** | A seizure or biomarker model used clinically is likely MDR class IIa+ (Rule 11) and FDA SaMD | We never market a clinical model. Customers take the device route; we supply SOUP documentation (BLUEPRINT §8.6) |
| **Re-identification** | EEG works as a biometric (de Ataide 2026, `security/THREAT-MODEL.md` P-03). Embeddings encode dataset identity | Embeddings stay in the tenant; no cross-tenant similarity search; coarse inference outputs; membership-inference gate before any model release (SEC-142–144). Residual risk is accepted as high in the threat model |
| **LLM errors and vendor dependency** | Assistants can be wrong or can be manipulated through injected metadata | Metadata/provenance only, user-token retrieval, 100% citation validation, read-only tools, red-team gate. Provider is the Anthropic API (owner decision 2026-09-26). Model IDs sit behind config and are gated by golden-set re-evaluation, because Haiku 4.5 retirement is "not sooner than Oct 15, 2026". Self-hosting is a documented fallback |
| **The consented data asset stays small** | The pool is opt-in, off by default, and gated by DPIA/REK. The opt-in rate is unknown | The thesis does not depend on it. It is an upside scenario only |
| **Brand** | "They train AI on your brain" headlines (DATA-REVENUE-STRATEGY A5) | Public rule: we never train on customer data, never sell data, and withdrawal reaches models |
| **Execution capacity** | The core AI layer is ESTIMATE ~14.5 person-months on top of M4–M7 (AI-LAYER §7), while the company plan assumes a very small team (`research-lab/neuroforge-kart/RAPPORT.md` M2 notes the gap) | Ship order starts with low-cost, high-value features: QC, search, montage inference, evaluation cards, then the assistant. Foundation-model and federated work only on pull |
| **Unmeasured costs and performance** | Every performance figure in the design is a *target* or *to be measured* | The build guide makes measurement an acceptance test, and cards publish negative results too |

## 4. What we will not say to investors

- "SOTA neural AI", "our foundation model", "detects disease", "anonymous because DP", "certified unlearning", or "large proprietary brain-data moat".
- Any customer count, accuracy or revenue from the AI layer before it exists and has been measured.

## Sources

Internal files:
- `architecture/AI-LAYER.md`
- `docs/adr/0011-ai-layer-principles.md`
- `research-lab/ai/RAPPORT.md` (external arXiv sources listed there, abstracts opened 2026-09-26)
- `research/neurobiology/PLATFORM_FEATURES.md` and `STATUS.md`
- `legal/data-agreements/RISK-MEMO.md` and `CONSENT-SCOPES.en.md`
- `security/THREAT-MODEL.md`
- `investor/PITCH.md`, `DATA-REVENUE-STRATEGY.md`, `PRICING.md`
- `market/landscape.md`, `regulation.md`, `new-ideas.md`
- `docs/hive/M2-REPORT.md` and `M3-REPORT.md`
