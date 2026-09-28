> DRAFT – not legal advice. Must be reviewed by a Norwegian lawyer (advokat) before use.

# Consent scopes for the consent ledger (legal → engineering mapping)

Version [0.1] · 2026-09-26 · Owner: Marius Carlsson · Author: nfb-legal-privacy
Prevailing language: English (engineering spec) [advokat choice]
Norwegian version: CONSENT-SCOPES.no.md

**Status and deadline**
- These scopes must be in the ledger (BUILD-GUIDE 5.3; BLUEPRINT §8.3) **before the first design partner**.
- The participant-facing wording is in contributor-consent.{en,no}.md, Part 3.
- Every scope below with prefix `nf.` makes **NeuroForge a controller**. Such a scope is only collectable when **all** of these hold:
  - the customer has signed the Research Pool Addendum (MSA § 4.3);
  - a DPIA exists;
  - REK/IRB approval covers the purpose where it is health research.
- ASSUMPTION: NeuroForge Bio AS is not yet incorporated.

## 1. Scope table

| Ledger scope ID | Form box | Controller | Maps to designed scope(s) | Plain meaning (UI string) | Requires | Blocked by |
|---|---|---|---|---|---|---|
| `study.collection`, `study.processing` | (i) | Customer | collection, processing | "Record and use my data for [study]" | – | – |
| `nf.pool` | (ii) | NeuroForge | sharing (to NeuroForge) | "Keep a de-identified copy in NeuroForge's research pool" | `study.collection`; Research Pool Addendum | CA `limit_use` flag; missing DPIA/REK |
| `nf.internal_rnd` | (ii) (sub-purpose) | NeuroForge | processing | "Test and improve NeuroForge's own analysis software. No third-party access; no model weights leave NeuroForge" | `nf.pool` | as `nf.pool` |
| `nf.model_training.internal` | (iii) | NeuroForge | model training | "Train AI models that NeuroForge uses itself" | `nf.pool` | as `nf.pool` |
| `nf.research.future_neuro` | (iv) | NeuroForge | processing (research) | "Future research on how the nervous system works and on neurological conditions, with ethics approval where required" | `nf.pool` + a **project record** with REK/IRB ref. or an "outside helseforskningsloven" assessment | project area not in the allow-list (§ 2); subject opted out of that area |
| `nf.share.research_partner` | (v) | NeuroForge | sharing | "Share de-identified data with vetted universities/hospitals under contract" | `nf.pool` + signed academic DSA | – |
| `nf.model_training.licensed` | (vi) | NeuroForge | model training + commercial use | "Train AI models that are licensed to paying companies" | `nf.pool` + model-licence terms with use restrictions | CA `limit_use`; US "sale" opt-out |
| `nf.data_licence.commercial` | (vii) | NeuroForge | sharing + commercial use | "Share de-identified data with paying companies" | `nf.pool` + signed data-licence agreement | CA `limit_use`; US "sale" opt-out |
| `nf.recontact` | (viii) | NeuroForge | – (contact data) | "Contact me about future studies" | – | – |

**Design choice to confirm with the advokat.** `nf.internal_rnd` is bundled into box (ii) because testing software on pool data is part of what the pool is for. If the advokat wants it separate, split it into its own box. No code change is needed, because the scope already exists on its own.

## 2. Allow-list for `nf.research.future_neuro` (so that the broad consent stays "certain areas", Recital 33)

**Allowed areas:**
- basic neuroscience of brain and nerve signals;
- methods for recording, cleaning and analysing neural signals;
- neurological and neurodevelopmental conditions;
- brain–computer interface research;
- neuroprosthetics (computational).

**Excluded areas, which need new specific consent:**
- genetics and genomics, or linking to biobanks;
- drug development on the person's data;
- psychiatric or behavioural profiling of individuals;
- any commercial licensing (use (vi)/(vii) instead);
- anything outside the nervous system.

**Rules:**
- Each project is registered as a **project record**: title, area, REK/IRB ref., start date and public summary URL.
- `policy.check` denies access unless the project area is on the allow-list and the subject has not opted out of that area.
- Participants are notified of new projects, because helseforskningsloven § 14 gives "krav på jevnlig informasjon".

## 3. Enforcement rules (for `policy.check`, BUILD-GUIDE 5.4)

1. **Dependency.** Any `nf.*` scope except `nf.recontact` is inert without `nf.pool`. Withdrawing `nf.pool` cascades to all dependent scopes.
2. **Independent withdrawal.** Each scope can be withdrawn alone. Withdrawal is as easy as granting (GDPR Art. 7(3); CT PA 25-113 revocation "at least as easy"). For US subjects, processing under that scope must stop within **15 days** (CT). Target: immediately.
3. **Scope-specific DeletionJob** (BLUEPRINT §8.4). Withdrawing a scope runs deletion **for the processing under that scope only**:
   - `nf.pool` → delete the pool copy and destroy the pool-specific subject key;
   - `nf.model_training.*` → `retrain_required` on the affected models and a deployment block (configurable), with SISA shard retraining where enabled;
   - `nf.share.*` / `nf.data_licence.*` → send a Withdrawal Notice to recipients and collect deletion certificates within [30] days.
4. **Versioning.** Each grant records the form version and hash. Any change in meaning of a scope needs **re-consent**; old grants do not carry over to the new meaning.
5. **US flags.** A subject in CO/CA/CT/MT must never get a default grant. `limit_use` (CA 1798.121) blocks `nf.pool` and everything that depends on it.
6. **Processor data.** Customer tenant data (scope `study.*` only) is never readable by `nf.*` jobs. This is DPA § 3.4 and MSA § 4.3, and CI tests must prove it.
7. **Minors.** Grants of `nf.*` scopes from subjects under 18 are rejected unless a REK/IRB-approved minors process is flagged on the tenant.

## 4. Legal basis per scope (summary)
- **All `nf.*` scopes:** explicit consent, GDPR Art. 6(1)(a) + 9(2)(a) (specific purposes). Research scopes use Art. 89(1) safeguards: pseudonymisation and minimisation. Research data may be stored longer only under Art. 5(1)(e) and only while the research scope is live.
- **`nf.research.future_neuro`:** broad consent is allowed under GDPR Recital 33 and helseforskningsloven § 14 ("nærmere bestemte, bredt definerte forskningsformål"). REK may set conditions or require new consent.
- **`nf.model_training.licensed` / `nf.data_licence.commercial`:** these are **not** covered by broad research consent. In the US, sharing for a fee is a "sale" (CT PA 25-113; CA SB 1223), which requires opt-in.
- See BROAD-CONSENT-ASSESSMENT.md.

## Hjemmel / Legal basis
- **GDPR official text** (Publications Office, http://publications.europa.eu/resource/celex/32016R0679, opened 2026-09-26): Recital 33, Recital 42, Art. 5(1)(b),(e), Art. 89(1).
- **GDPR Norwegian text on Lovdata** (opened 2026-09-26): Art. 7(3) https://lovdata.no/lov/2018-06-15-38/gdpr/a7 and Art. 9(2)(a) https://lovdata.no/lov/2018-06-15-38/gdpr/a9.
- **Helseforskningsloven** §§ 14, 17: https://lovdata.no/lov/2008-06-20-44/§14 (opened 2026-09-26).
- **Connecticut PA 25-113:** https://www.cga.ct.gov/2025/ACT/PA/PDF/2025PA-00113-R00SB-01295-PA.PDF (opened 2026-09-26).
- **California Civ. Code 1798.121:** https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CIV&sectionNum=1798.121 (opened 2026-09-26).
- **Colorado and Montana** consent mechanics: **UNVERIFIED**.
- **Product facts:** BLUEPRINT §8.3–8.4; MSA § 4.3; DPA § 3.4.
