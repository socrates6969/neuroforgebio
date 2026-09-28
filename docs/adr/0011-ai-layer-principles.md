# ADR 0011: AI layer: principles

- Status: **Proposed**, except the LLM-provider point, which is **Accepted** (owner decision, 2026-09-26; see "Decision note" below)
- Date: 2026-09-26
- Deciders: owner (Marius Carlsson); proposed by the code architect
- Source: `architecture/AI-LAYER.md`; `architecture/BUILD-GUIDE.md` addendum M8; SEC-061, SEC-090–094, SEC-142–147; `legal/data-agreements/CONSENT-SCOPES.en.md`; `research/neurobiology/PLATFORM_FEATURES.md`. Company name: NeuroForge Bio.

## Context

The owner wants AI in three places:
- at ingest;
- in interpreting signals;
- after storage.

It has to be a real, verifiable capability. Independent 2025–26 benchmarks find that EEG foundation models are "largely on par" with simple baselines (`research-lab/ai/RAPPORT.md` §a.1). Pseudonymised neural signals remain identifying (`security/THREAT-MODEL.md` P-03). NeuroForge may not train on customer processor data (DPA § 3.4). So the AI layer's value has to come from being evaluated, traceable and governed, not from claims of model superiority.

## Decision

Every AI capability in NeuroForge Bio follows these nine rules. A feature that cannot meet them is not built.

1. **Always evaluated.** No model is promoted, deployed or shown to customers without an **evaluation card**:
   - It is produced by the leak-proof evaluation service (the nfharness port): locked patient-disjoint or causal splits, a leak meter, and CIs with the few-cluster rule.
   - Unvalidated parts, such as negative controls before N1b, are labelled on the card and never hidden.
   - Performance numbers are measurements with their conventions stated, never marketing claims.
2. **Always versioned.** Models are immutable and digest-addressed registry entries, in safetensors or ONNX only (SEC-061). Re-running a model means a new run, never an overwrite.
3. **Always provenance-tracked.** Every AI output records these as PROV nodes in the hash-chained graph:
   - model digest;
   - training-data manifest;
   - PipelineVersion;
   - input hashes;
   - card ID;
   - review status.
4. **Always consent-gated.** Every training or inference job passes `policy.check`:
   - Training needs the matching `model training` scope.
   - NeuroForge's own models need `nf.model_training.internal`, or else public/synthetic data only.
   - Licensing weights needs `nf.model_training.licensed`.
   - Withdrawal propagates to models: `retrain_required`, then retraining without the subject.
   - **We never claim certified unlearning.**
5. **Human in the loop.** AI writes **flags, scores and suggestions, never mutations or deletions**. A person accepts any change to governance attributes or data inclusion (`data-steward`). Deployment and cross-tenant publication need four-eyes approval (SEC-024). Promoting a retrained model needs human approval.
6. **No medical claims.** AI features are research-use tooling. Copy-lint bans diagnostic language ("diagnoses", "detects disease", "predicts seizures" as a product claim, "clinically validated", "SOTA"). A customer who gives a model a medical purpose takes the MDR/FDA route, and we supply SOUP documentation.
7. **No stimulation.** No AI output, API field or deployment context may control stimulation, neuromodulation or any actuator (SEC-090–094). The registry refuses those contexts. Changing this rule needs the owner's written approval and a new regulatory analysis, not just an ADR.
8. **Tenant boundary.** Models, fine-tunes, embeddings and evaluation data trained on or derived from a tenant's data **never leave that tenant without the data subjects' consent** (the relevant `nf.*` scopes) and four-eyes approval (SEC-143). Customer processor data never trains NeuroForge models (DPA § 3.4; CONSENT-SCOPES rule 6).
9. **LLM boundary.** A language model only sees metadata and provenance the requesting user can already read, retrieved with that user's token. It never sees raw signals, embeddings or free-text notes. It must cite a record ID for every factual statement, and it has no write tools.

## Consequences

- Every AI feature needs the M8.0 contract: the model step type, the PROV extension, the card schema and the copy-lint additions. Every feature is testable against rules 1–9 in CI.
- The layer is slower to show than "AI demos", but each result survives an investor's or regulator's audit. That is the product positioning in ADR 0001.
- **We do not pre-train our own foundation model** unless a consented longitudinal pool exists and the owner revisits this ADR.
- **Emotion or cognitive-state inference products are not built** (AI Act Art. 5(1)(f)).
- **Embedding-similarity search across tenants is not built** (re-identification risk).
- Using an external LLM API for the assistant makes that vendor a subprocessor. It must be listed in the DPA before enablement, and each tenant opts in.

## Decision note (2026-09-26, owner): assistant LLM = Anthropic API. Status of this point: **Accepted**

- **Provider and account.**
  - The Anthropic API, through a **NeuroForge Bio company API account**.
  - Sign-up, terms acceptance, billing and spend limits are owner actions 🔒.
  - The owner's Claude Code session credentials are **never** reused in the product.
  - Separate keys and workspaces per environment.
- **Model tiering behind config.**
  - `assistant.model.routine` = `claude-haiku-4-5-20251001` (Claude Haiku 4.5).
  - `assistant.model.complex` = `claude-sonnet-5` (Claude Sonnet 5).
  - A rule-based router escalates once to `complex` when a question is complex or a routine answer fails citation validation.
  - Any model change is a config change gated by re-running the golden-set evaluation. Haiku 4.5's published retirement is "not sooner than October 15, 2026".
- **Secrets.** The key lives only in the secrets manager and is injected into the LLM gateway only; it is never in the repo. CI uses a mock `LlmClient` with network egress blocked. A live smoke test is a manual, owner-approved job on synthetic data.
- **Data sent (binding redaction rule; `legal/data-agreements/ai-assistant-memo.md`).**
  - **Study-level metadata only**, retrieved with the user's token. Subject-, session- and recording-level nodes and per-subject clinical fields are redacted.
  - Diagnosis-revealing titles are dropped or generalised, because combined with subject-level data they would be Art. 9 health data.
  - **Derived signal features are never sent** (likely "neural data" under CO/CA/CT), nor are raw signals, embeddings, identifiers or free text.
  - A fail-closed redaction layer runs **before** any request is built.
  - Every call is a **transfer to the US**: EEA customers contract with Anthropic Ireland, Limited under SCC Module Three. The tenant opt-in shows a transfer notice, and enabling for any customer requires a completed transfer impact assessment and a DPIA update.
- **Audit per request.**
  - An `llm.request` audit event records the model requested and returned, the Anthropic request-id, token counts and the manifest of what was sent (record IDs, field paths, payload SHA-256).
  - The exact payload and response are stored encrypted under the tenant key.
- **Subprocessor.** Anthropic becomes a subprocessor for customers.
  - Official pages opened 2026-09-26: Commercial Terms, effective June 17, 2025 ("Anthropic may not train models on Customer Content from Services"; DPA incorporated by reference); DPA, effective February 24, 2025 (SCCs Module 2/3); 30-day default retention with zero data retention by agreement, and up to 2 years for Usage-Policy-flagged content; US-only workspace geo.
  - Anthropic's subprocessor list and any EU–US DPF certification are **UNVERIFIED**.
  - Legal must list Anthropic in the DPA annex, do a transfer impact assessment and decide on requesting ZDR **before** any customer enablement (AI-LAYER C2a "Legal notes").
- **Cost control.** Per-tenant monthly question and token quotas (429 when exceeded), Console spend limits, prompt caching of the frozen system prompt and tool list, and a scope-keyed answer cache that is invalidated when provenance changes. Unit cost ESTIMATE ≈ $0.012–$0.024 per question (AI-LAYER C2a).
- Details: `architecture/AI-LAYER.md` §C2a; build step: `architecture/BUILD-GUIDE.md` 8.7.
