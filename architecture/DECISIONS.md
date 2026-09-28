# GATE B: decisions for the owner

These are the questions only the owner can decide before building starts. Each has a recommendation. Section references point to `BLUEPRINT.md` (§) and `BUILD-GUIDE.md` (step numbers). Once decided, each answer becomes an ADR in `docs/adr/` (step 0.1).

**Fastest path:** reply with the decision numbers you accept as recommended, and write out only the ones you want changed.

---

### D1. Positioning: reposition from "automated cleaning" to "reproducible, comparable pipelines + neural-data governance"?

**Recommendation: YES.**

Evidence:
- Kessler 2025 (*Commun Biol*) found that all artifact-correction steps **reduced** decoding performance.
- Huang 2025 (*Psychophysiology*) compared 43 pipelines and found "no single best pipeline".

`market\validation.md` #5 therefore rates "automated cleaning as a value driver" **CONTRADICTED**. Neural-data privacy law is the one blueprint assumption rated **SUPPORTED** as a demand driver (`validation.md` #8): four state laws, with CT effective 1 Jul 2026. No neural-specific governance tool was found (`market\landscape.md` §3).

The GATE A copy fix already swaps the cleaning wording. This decision goes further and changes the **headline story**. Proposed hero sub-line:

> "Versioned, comparable pipelines and neural-data governance, from electrode to model."

- **If yes:** the website leads with provenance, multiverse comparison and the consent ledger. The architecture is already built around the provenance graph (§3.6).
- **If no:** the architecture is unchanged, but the copy keeps a cleaning story that the research contradicts.

### D2. (Decided) Company name

Name: NeuroForge (owner, 2026-09-26); clash check in market\names.md

The name is stored once, in the brand token `packages/content/brand.json` (`BLUEPRINT.md` §2.2), so a rename is a one-line change. The public launch (step 1.10) waits for the clash check to come back clean.

### D3. Which theme is canonical, and how is the theme chosen?

**Recommendation: build-time theme per deployment** (§2.3, approach A):
- **clinical** is the canonical public site on the primary domain.
- **cosmos** runs on a secondary host (for example, a subdomain for investors, conferences and campaigns). It has `rel=canonical` pointing to clinical.

Reasons:
- The clinical bundle never downloads three.js.
- Both builds are fully crawlable static HTML.
- There is no flash of the wrong theme.
- QA covers just two fixed builds.
- The paying segments are regulated buyers (clinical-stage device makers and CNS pharma, about 70–80% of the SAM range, `market\sizing.md` §4), which suits the clinical look.

A visitor-facing runtime toggle can be added later without refactoring, because tokens are scoped by `[data-theme]`. It is not in v1.

Alternative: make cosmos canonical if investor and brand impact matter more to you than regulated-buyer trust in year 1.

### D4. Hosting and cloud

**Recommendation:**
- **Website:** any static CDN host (two projects).
- **Platform:** AWS in one US region at launch. AWS lists "175+" HIPAA-eligible services, including S3, under its BAA (`market\regulation.md` §3). That is the shortest BAA path for clinical customers.
- **EU region:** planned for GDPR tenants.

Keep the stack portable wherever that is cheap: Postgres, the S3 API, OCI containers, OIDC, OpenTelemetry, OpenTofu (§7).

Supporting services:
- **Identity:** a managed IdP with SAML support (enterprise buyers expect SSO; W&B and Aptible gate SSO and audit behind enterprise tiers, `market\pricing-and-gtm.md` §1). Self-hosted Keycloak remains the on-prem option.
- **Observability:** a managed OpenTelemetry backend at first.

Options considered:
- **GCP or Azure:** equivalent, but not researched in this pass.
- **Cloudflare R2 for public or academic non-PHI data:** cheaper storage at $0.015/GB-month vs S3's $0.023, with free egress (pricing pages opened 2026-09-26). Whether a BAA is available was **not verified**, so R2 must not hold PHI.
- **Aptible:** a HIPAA PaaS at $499/mo on the Production tier (`market\regulation.md` §3). It is a simpler operations option if the team has no DevOps capacity.

Opening a cloud account and spending money are owner actions.

### D5. Build order: ship the consent ledger earlier?

**Recommendation: YES.** Run M5 (compliance ledger) in parallel once M2 and step 3.1 are done, rather than strictly after M4.

- `market\pricing-and-gtm.md` §5 puts the ledger MVP in months 3–9.
- `market\new-ideas.md` ranks it #1: the strongest why-now, with no neural-specific competitor found.
- The dependency graph in BUILD-GUIDE allows the parallel start.

Cost: M3 and M4 need more parallel staff. Without that, M3 and M4 slip by about the size of M5 (~6.75 person-months, ESTIMATE).

The website (M1) stays first either way.

### D6. Open-source licence for the SDK and core

**Recommendation:**
- **Apache-2.0** for `nf-core`, the SDKs, converters, the synthetic-data tool and the step library (the "Open Core" tier in `market\pricing-and-gtm.md` §2).
- **Proprietary** for the hosted platform: ledger, registry and evidence kit.

Reasons:
- The distribution channel runs through MNE, BIDS, NWB and LSL users (`pricing-and-gtm.md` §4), and that ecosystem is permissive: BSD, MIT and Apache licences (`market\landscape.md` §2).
- Apache-2.0 adds an explicit patent grant, which MIT lacks.
- The moat is governance and hosted evidence, not SDK code.

Alternative: MIT, which is simpler but has no patent clause.

### D7. Language for the shared SDK core

**Recommendation: Rust**, with PyO3/maturin for Python and a C ABI for C++, Unity and Unreal (§5).

Reasons:
- Memory safety for code that parses network input on customer machines.
- One implementation of the hashing, protocol and provenance rules across all SDKs.
- A smooth Python wheel toolchain.

Alternative: **C++ with pybind11**, if the team's C++ experience clearly outweighs its Rust experience. It also matches liblsl and BrainFlow.

In both cases, signal-processing algorithms stay in Python/MNE and are not reimplemented.

### D8. May the two themes have different headline wording?

**Recommendation: NO (one heading set).** Emphasis is marked once in content, and each theme paints it differently (§2.2). The option-1 and option-3 designs used different section headings, for example "One pipeline, from electrode to model." vs "From electrode to model, in one orbit."

If you want the cosmos "voice", allow at most **10 override strings per theme**, lint-checked. Anything beyond that starts turning into two websites.

### D9. Third-party requests on the website (fonts, analytics)

**Recommendation:**
- **Fonts:** self-host them (IBM Plex, Inter, Space Grotesk), after verifying each font's licence (expected: SIL Open Font License; not checked in this pass).
- **Analytics:** none, or cookieless aggregate analytics from the CDN.
- **Scripts:** no third-party scripts at all, which allows a strict Content-Security-Policy (`script-src 'self'`).

Reason: a company that sells neural-data privacy should not load trackers on its own site. `design\CONTENT-SPEC.md` currently allows Google Fonts. This would tighten that rule.

### D10. When to spend on external assurance (counsel, SOC 2, regulatory consultant)

**Recommendation, in order:**
1. **Privacy counsel** reviews the jurisdiction RuleSets (step 5.2) **before the first paying ledger customer**. This is the highest legal-risk item. Montana's statute text was never opened (`market\regulation.md` open items).
2. **A regulatory consultant** reviews the FDA Evidence Kit scaffold (step 5.8) before it is sold.
3. **SOC 2 Type II** starts once 2–3 design partners ask for it. Until a report exists, the website says "on roadmap".

No prices were opened for any of these. Get quotes before committing. They are the largest non-people costs (`BLUEPRINT.md` §12.2).

---

**Already decided, not re-opened here:**
- One codebase with two themes (GATE A).
- Website first.
- No medical claims.
- Status labels say designed/planned/roadmap.
- Computational-only research (`BRIEF.md`).
