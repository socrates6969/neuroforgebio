# NeuroForge Bio: Marketing Plan (Year 1)

Prepared 2026-09-26 by the marketing worker (an AI agent, not a team member) for owner Marius Carlsson. **DRAFT for owner review.** Nothing in this plan has been sent, posted, bought or booked. The owner approves every spend, every contact and every publication.

**Status of the company:** pre-product. No customers, no LOIs, no partners, no users. Every product capability below is **designed / planned / roadmap**.
**Name:** NeuroForge Bio. **Trademark clearance pending** (market\names.md: Neuroforge GmbH & Co. KG trades under the identical name in Germany; trademark databases were not searchable). No public launch material goes out until clearance comes back.
**Grades** (BOARD.md): A peer-reviewed / primary law, B reputable press / tertiary, C preprint / theory, D company marketing. **ESTIMATE** = derived or assumed, with method.

---

## 1. Positioning

### 1.1 Positioning line (architecture\DECISIONS.md D1, owner-approved at GATE B)
> **Versioned, comparable pipelines and neural-data governance, from electrode to model.**

### 1.2 Positioning statement
For **teams that must defend what they did with neural data** (clinical-stage BCI and neurotech companies, consumer EEG companies subject to state neural-data laws, CNS research sponsors and NIH-funded labs), **NeuroForge Bio** is a **planned research-and-development software layer** that records every pipeline parameter, compares pipelines side by side, and tracks neural-data classification, consent and deletion across jurisdictions. Unlike analysis libraries (MNE, EEGLAB) and archives (DANDI, OpenNeuro), which are free and excellent but have no governance layer, and unlike generic HIPAA infrastructure (AWS, Aptible), which is a commodity, NeuroForge Bio is **designed around one lineage graph** that links electrode, pipeline, dataset, consent and model (market\landscape.md §2–§4; market\new-ideas.md "Top 5").

It is **non-device R&D software**: it does not diagnose, treat or recommend treatment (market\regulation.md §4).

### 1.3 Who we are not (from validation.md)
- Not an "automated neuro-cleaning" product (validation.md #5: CONTRADICTED as a one-size default).
- Not selling core pipelines to vertically integrated implant leaders (validation.md #4: CONTRADICTED for leaders).
- Not a model app store (validation.md #6: WEAK; deferred until a customer pulls).
- Not competing with free academic archives or with CatalystNeuro's conversion services (validation.md #3; new-ideas.md #5: partner, don't fight).

### 1.4 Messaging pillars and their evidence

| # | Pillar | Message (draft) | Evidence (as cited in market files, with grade) | Product status |
|---|---|---|---|---|
| P1 | **Comparable pipelines** | "There is no single best preprocessing pipeline, so record all of them and compare." | Kessler et al., *Commun Biol* 2025, doi:10.1038/s42003-025-08464-3 (**A**): all artifact-correction steps reduced decoding performance; higher high-pass cutoffs increased it. Huang et al., *Psychophysiology* 2025, doi:10.1111/psyp.70197 (**A**): 43 pipelines, "no single best pipeline" (landscape.md §3 item 2) | Open-core SDK, validator and multiverse runner: **planned**, product months 0–3 |
| P2 | **Reproducible by default** | "Only about one in five EEG-BCI papers shared code. Provenance should be automatic." | Peksa et al., *Sensors* 2026, doi:10.3390/s26175562 (**A**): 129 publications; data availability stated in 61.2%, code/pipeline availability 20.9% (landscape.md §3 item 1). Ruiz-Mateos Serrano et al., *Sci Adv* 2026, doi:10.1126/sciadv.aee8595 (**A**): inconsistent formats complicate ML | Local provenance graph: **designed** |
| P3 | **Neural-data governance across jurisdictions** | "One EEG or EMG recording can be neural data in one state and not in the next. Classification has to live in software." | Colorado HB24-1058, signed 17 Apr 2024, effective 7 Aug 2024 (leg.colorado.gov, **A**). California SB 1223, Ch. 887, 28 Sep 2024 (leginfo, **A**). Connecticut PA 25-113, signed 24 Jun 2025, CTDPA sections effective 1 Jul 2026 (cga.ct.gov, **A**). Montana SB 163 (May 2025) via Cabrera et al., *Bioethics* 2026, doi:10.1111/bioe.70062 (**A**, secondary to statute; **statute text not reviewed**). MIND Act (Sep 2025) via Young, Simon & Evans, *Neurology* 2026, doi:10.1212/wnl.0000000000214942 (**A**; bill number and status not verified). EU AI Act Art. 5(1)(f), applicable from 2 Feb 2025 (artificialintelligenceact.eu, **B**) (all regulation.md §1, §2, §5) | Consent & Deletion Ledger: **planned**, product months 3–9 |
| P4 | **Evidence for regulated work** | "Implanted-BCI software is expected to meet FDA's Enhanced Documentation Level. Lineage makes that documentation traceable." | FDA "Implanted BCI Devices ..." guidance, issued 20 May 2021, update note pointing to the **Enhanced Documentation Level** in "Content of Premarket Submissions for Device Software Functions" (14 Jun 2023) (fda.gov/media/120362/download, **A**; regulation.md §4) | FDA Evidence Kit + latency harness: **roadmap**, product months 9–18. We supply documentation tooling; the device maker carries its own submission |
| P5 | **Fits the stack you already use** | "Plug-ins for MNE, BIDS, NWB and LSL, not a new silo." | PyPI downloads/month (pypistats, Sep 2026, as cited in pricing-and-gtm.md §4): MNE 308k, pynwb 108k, pyRiemann 64k, pylsl 34k, braindecode 22k. Ecosystem licences are permissive (landscape.md §2) | Integrations **planned**; Apache-2.0 for SDK/core **planned** (D6); repo stays all-rights-reserved until SDK code exists |

### 1.5 Honest proof points available today (none are about customers)
1. The peer-reviewed findings behind P1–P2 (third-party research, not our results).
2. A cited regulation map of four state laws, the MIND Act and EU AI Act Art. 5 (market\regulation.md), which becomes the public law-tracker page.
3. A market review that found **no neural-specific consent/deletion tool** among the tools examined (landscape.md §3 item 4). Wording must stay "none found in our review", never "the only".
4. Published product designs and an architecture (architecture\), described as designed/planned.
5. A research programme with computational whitepapers in preparation (research\somatosensory\; "in preparation", computational only, any clinical application needs IRB/FDA oversight).
6. **To be created in months 1–4 (planned):** an open-source validator and a multiverse audit run on **public** DANDI/OpenNeuro data, published with methods (pricing-and-gtm.md §5 step 1). This is the first proof point we own.

### 1.6 Banned claims (every asset is checked against this list before owner review)
| Banned | Why | Say instead |
|---|---|---|
| "live", "built-in", "available now", "certified" | BOARD.md status rule; pre-product | "designed", "planned", "on the roadmap" |
| "HIPAA-compliant", "SOC 2", "SOC 2 certified" | No audit exists (DECISIONS.md D10) | "designed for HIPAA-aligned workflows", "BAA for enterprise (planned)", "SOC 2 Type II: on roadmap" |
| "Compliant with Colorado/California/Connecticut/Montana law", "makes you compliant" | Not legal advice; counsel review pending (D10) | "designed to support classification, consent and deletion under emerging state neural-data laws" |
| Any medical or therapeutic wording: "diagnose", "treat", "restore", "cure", "clinical-grade", "improves outcomes" | BRIEF rule; non-device positioning (regulation.md §4) | "research and development use" |
| "FDA-cleared", "FDA-approved", "FDA-ready", "guarantees submission" | We are not a device; evidence kit is roadmap | "documentation tooling designed around FDA's Enhanced Documentation Level" |
| "Automated cleaning improves decoding", "one-click clean data" | Contradicted by Kessler 2025, Huang 2025 | "compare pipelines; record every parameter" |
| "Teams spend months rebuilding pipelines" | Not measured (validation.md #1) | Use only after discovery measures it, with the measured figure |
| "The only", "first", "no competitor exists" | We searched once, without WebSearch | "no neural-specific tool found in our review (Sep 2026)" |
| Customer, partner or user names; logos; "trusted by"; "used by N labs"; testimonials; invented quotes | BOARD.md: never invent traction; pre-product | "[placeholder]" until real and written consent exists |
| CatalystNeuro, OpenBCI, BrainFlow, MNE etc. as "partners" | No contact made | "integrates with (planned) open formats and libraries" |
| Latency, uptime or accuracy numbers | Nothing measured | "planned measurement method" |
| "De-identifies", "re-identification-proof", "synthetic data is private" | Research questions, unverified (new-ideas.md #7, #11) | Do not claim |
| "Unlearning guaranteed" | Retrain/unlearn flag is a design, not a guarantee | "flags derived data and models affected by a withdrawal (planned)" |
| MIND Act bill number/sponsors; Montana statute details | Not verified (regulation.md open items) | Cite the peer-reviewed secondary source only |
| Presenting AI agents as staff | BOARD.md | Team = owner + hiring plan |
| "NeuroForge" on public material before clearance | names.md verdict "risky / crowded" | Hold public launch until attorney clearance |

---

## 2. Ideal customer profiles (types only)

Source: market\pricing-and-gtm.md §3, with sizing.md §3–§4 and validation.md #4. Company names appear **only** where the market files use them as examples of a profile. **None of them is a prospect, customer or contact; no one has been contacted.**

| ICP | Profile | Trigger / pain | Offer (status) | Tier (ESTIMATE) | Priority |
|---|---|---|---|---|---|
| **1. Clinical-stage implant BCI companies** entering IDE / early-feasibility trials | Profile illustrated in the market files by the Paradromics/Precision stage (not prospects) | FDA Enhanced Documentation Level; traceable lineage; latency evidence | FDA Evidence Kit + latency harness (**roadmap**, product m9–18); multiverse audit service earlier | Growth $50k–$150k/yr | High ACV, later product. Start discovery now |
| **2. Consumer / wellness EEG and neurotech companies selling in CO/CA/CT/MT** | The "Muse/Neurable/Neurosity/Emotiv class" in the market files (not prospects) | Neural data is "sensitive" data under four state laws; CT effective 1 Jul 2026 already passed. Public qualification signal (desk review, no contact): a privacy policy with no neural-data-specific consent language | Consent & Deletion Ledger (**planned**, product m3–9) | Startup $300–$800/mo; Growth | **First revenue wedge** |
| **3. University BCI spinouts** from labs that publish on DANDI/OpenNeuro | Seed stage, ≤$2M raised | Need investor-grade reproducibility and early governance | Open core + Startup tier (**planned**) | Startup $300–$800/mo | Volume, fast cycles |
| **4. CNS biotech sponsors using EEG endpoints, and their CROs** | Regulated research buyers | Part 11 expectations; pipeline sensitivity of endpoints | Multiverse audit (service), Part 11 EEG platform (**roadmap**) | Enterprise $100k–$300k+/yr | High ACV, long cycle |
| **5. Neuromodulation research networks** with sensing-enabled DBS | Academic medical centres, consortia | Remote chronic data collection at scale | Remote data pipeline (**roadmap**) | $30k–$120k/yr per network | Later |
| **6. NIH-funded core facilities and EEG labs** | Labs budgeting under the NIH DMS policy | Data management and sharing plans | Lab / Institution tier (**planned**) | $3k–$10k/yr | Channel + small revenue |
| **Partners (not customers)** | CatalystNeuro (NWB conversion services); hardware vendors shipping open SDKs (OpenBCI, BrainFlow ecosystem) | Complement, not compete | Integration and referral **proposal**; no contact made | — | Owner decides whether to approach |

**De-prioritised:** vertically integrated implant leaders (validation.md #4); individual academics as a revenue source (validation.md #3).

**Pricing** above is ESTIMATE from pricing-and-gtm.md §2 and must not appear in outreach as a quote until discovery validates it. The financial model (nfb-finance-ba) owns revenue forecasts.

---

## 3. Channels (pricing-and-gtm.md §4)

| Channel | Why (as sourced in §4) | Year-1 tactic | Owner gate |
|---|---|---|---|
| **GitHub / PyPI integrations** | Users already work in MNE (308k downloads/month), pynwb, pyRiemann, pylsl, braindecode (pypistats, Sep 2026) | Open-source the validator and multiverse runner; MNE/BIDS/NWB/LSL plug-ins that emit provenance. PyPI name: `neuroforge` is taken; use `neuroforge-data` or a distinct short name (names.md) | Owner publishes packages (never agents) |
| **Law-tracker page** | CT effective 1 Jul 2026; MIND Act FTC study | Free public page with NOT LEGAL ADVICE banner, change log, citations; monthly newsletter issue (templates\law-tracker-newsletter-issue-01.md) | Owner publishes; counsel review recommended before launch (D10) |
| **Peer-reviewed content** | The wedge rests on Kessler 2025, Huang 2025, Peksa 2026 | Multiverse audit on public data → preprint → submission to *J Neural Eng*, *Sci Data* or *Neuroinformatics* (channel choices, not claims) | Owner is author of record |
| **International BCI Society Meeting** | 12th meeting **7–10 Jun 2027, Šibenik, Croatia**; sponsorship/exhibits offered (bcisociety.org, as cited in §4) | Workshop proposal: "Neural-data governance under CO/CA/CT/MT + EU AI Act"; optional sponsor tier | Owner approves any fee; submission deadlines **not yet checked** |
| **SfN annual meeting** | ">30,000 attendees", 536 exhibiting companies (sfn.org/about, as cited in §4) | Year 1: poster on multiverse findings (attend, no booth). Booth considered for Year 2 | 2027 dates and fees **not opened**; owner approves |
| **Neuromatch** | NMA course content has 3,136 GitHub stars | Contribute a free tutorial using the open core (reproducible pipelines) | Owner submits |
| **Design-partner programme** | High-ACV segments need proof | 5 partners (min. 3), 50% off Growth for 12 months (investor\PRICING.md §4), in exchange for case studies and anonymised metrics (§4, §5) | Owner negotiates and signs; counsel on terms |
| **Owner's LinkedIn** | Low-cost reach to founders and engineering leads (judgement; no source) | 5-post series (templates\linkedin-series.md), then one post per month | Owner posts |
| **Direct outreach (owner only)** | Discovery before selling (validation.md #1) | Cold email / academic outreach templates, sent by the owner to people he chooses | Owner sends; agents never contact anyone |

**Website rules (D9):** no third-party scripts, no trackers, self-hosted fonts, cookieless CDN aggregate analytics only.

---

## 4. 12-month calendar

M1 = month of public website launch (date TBD; gated on trademark clearance and owner approval). Product months follow pricing-and-gtm.md §5 and BOARD.md; the plan **assumes product month 0 ≈ M1** (ASSUMPTION, queen to confirm against the build plan).

**Known dated items**
- **1 Jul 2026** (past): Connecticut PA 25-113 CTDPA sections effective (regulation.md §1). Use as "already in force" in content.
- **7–10 Jun 2027**: International BCI Society Meeting, Šibenik, Croatia. If M1 = Nov 2026 (illustrative only), this falls in **M8**.
- **SfN annual meeting 2027**: dates **not opened**. Place provisionally in M11–M12 and verify on sfn.org before any commitment.
- Workshop/abstract deadlines for both meetings: **not checked**; owner/agent to check on the public sites (read-only) before M2.

| Month | Product state (planned) | Marketing actions | Output / KPI checkpoint |
|---|---|---|---|
| **M0 (pre-launch)** | Website built (both themes) | Owner: trademark clearance; banned-claims review of site; set up cookieless CDN analytics; prepare discovery list from own network | Discovery interview guide final |
| **M1** | Open-core SDK in progress | Launch website (clinical canonical) + **law-tracker page v1**; LinkedIn post 1; start discovery interviews (target 5 in M1) | Site published; 5 interviews |
| **M2** | SDK/validator alpha | LinkedIn posts 2–3; law-tracker newsletter issue 01; check BCI Society workshop and SfN abstract deadlines; 5 more interviews | 10 interviews cumulative |
| **M3** | Validator + multiverse runner released open source (owner publishes) | GitHub/PyPI release; announcement post 4; Neuromatch tutorial draft; finish interviews (15–20); **synthesis memo → pricing & ICP update** | 15–20 interviews; first PyPI stats |
| **M4** | Multiverse audit run on public DANDI/OpenNeuro data | Preprint of audit results (methods + code); LinkedIn post 5; newsletter issue 02; design-partner programme page (planned) | Preprint posted (owner) |
| **M5** | Ledger MVP design / build | Submit BCI Society workshop proposal (if deadline allows); first 1:1 design-partner conversations with interviewees who opted in | 5 qualified design-partner conversations |
| **M6** | Ledger MVP (CO/CA/CT/MT + EU AI-Act flag) in private preview | Law tracker update; case-study template ready (no content until real); journal submission of audit paper | 1st design partner signed (target) |
| **M7** | Ledger preview with design partners | Prepare BCI Society materials (booth brief, one-pager, demo on public/synthetic data) | Materials approved by owner |
| **M8** | Startup tier (planned) | **BCI Society Meeting (7–10 Jun 2027)** if M1 = Nov 2026: workshop / attendance; privacy-respecting lead capture | Leads with explicit opt-in |
| **M9** | Ledger MVP GA target; FDA Evidence Kit design starts | Post-conference follow-ups (owner); newsletter; 3–5 design partners target | 3 design partners signed (5 by M12) |
| **M10** | Evidence Kit + latency harness design | Content series on FDA documentation (no regulatory claims); webinar pilot (self-hosted or no-tracker platform) | Pipeline review |
| **M11** | Growth tier planned | SfN poster prep (dates to verify); first case study **only if** a partner approves real text | Poster accepted (if submitted) |
| **M12** | — | SfN (if dates fall here); Year-1 review; set Year-2 budget within $60k–$150k band | KPI review vs targets below |

---

## 5. Budget (Year 1)

**Shared marketing budget (BOARD.md, set by the queen): Y1 $40k base (band $25k–$60k), non-people programme spend, ESTIMATE.** Marketing headcount is in the financial model, not here. **No booth, sponsorship, registration, APC or travel prices were opened**; every line is an ESTIMATE by small-B2B-SaaS judgement anchored on the channel list in pricing-and-gtm.md §4. **The owner approves every spend.** Get quotes before committing.

| Line item | Base (ESTIMATE) | Method / assumption | Bear ($25k) | Bull ($60k) |
|---|---|---|---|---|
| Conference registration + travel: BCI Society 2027 + SfN 2027 (1 person each, poster/workshop, no SfN booth) | $12,000 | 2 trips × ~$6k (registration, flights, 4–5 nights). Judgement; no prices opened | $8,000 (one meeting) | $14,000 |
| BCI Society sponsor / exhibit tier (optional) | $8,000 | Placeholder for a small tier; bcisociety.org offers sponsorship, price not opened | $0 | $12,000 |
| SfN booth | $0 | Deferred to Y2 in base case | $0 | $12,000 (small booth, price not opened) |
| Open-access publication fee (audit paper / data descriptor) | $4,000 | One APC; journal fees not opened | $3,000 | $6,000 |
| Design + print (one-pager, poster, pull-up banner, demo screen assets) | $3,000 | Freelance design + print run | $2,000 | $4,000 |
| Content production (demo video capture/editing, figures, copy-edit) | $4,000 | ~4 freelance deliverables × ~$1k | $2,500 | $4,000 |
| Web + email tooling (CDN hosting for site/law tracker, privacy-respecting newsletter tool, domain renewals) | $2,000 | Commodity hosting and email; no prices opened | $1,500 | $2,000 |
| Discovery tooling (scheduling, transcription with consent, CRM-lite) | $1,000 | SaaS seats for 3–4 months | $500 | $1,000 |
| Conference materials / demo hardware (laptop display, cables; **no** attendee EEG recording) | $2,000 | One-off | $1,000 | $2,000 |
| Contingency (10%) | $4,000 | 10% of base | $6,500 remainder buffer | $3,000 |
| **Total** | **$40,000** | | **$25,000** | **$60,000** (rounded) |

Bear case note: drop the sponsor tier and one trip; the bear column's "contingency" is the unallocated remainder. Bull case adds a small SfN booth. Not included: counsel review of the law tracker and outreach compliance (D10; legal budget sits outside marketing), salaries, paid ads (none planned in Y1).

---

## 6. KPIs and measurement without third-party trackers (D9)

All targets are **ESTIMATE** (method: judgement for a pre-product open-core B2B company with one founder, anchored on reference numbers in landscape.md §2; not forecasts). Revisit after M3 interviews.

| Funnel stage | KPI | M3 | M6 | M12 | How measured (no trackers) |
|---|---|---|---|---|---|
| Awareness | Law-tracker page views / month | 200 | 600 | 1,500 | CDN cookieless aggregate request logs (page path, count; no cookies, no fingerprinting, no IP retention beyond CDN default). Counts include bots: report trend, not people |
| Awareness | Newsletter subscribers (double opt-in) | 30 | 80 | 150 | Subscriber count in the email tool; no open/click pixels (disable tracking) |
| Adoption | SDK installs (PyPI downloads / month) | 150 | 800 | 3,000 | pypistats.org public aggregates for our package. Mirrors and CI inflate counts: compare month to month. Reference: braindecode ~22k/month, BrainFlow ~8.3k/month (landscape.md §2) |
| Adoption | GitHub stars (cumulative) | 50 | 150 | 300 | GitHub repo page / API. Reference: MOABB 1,057; BrainFlow 1,761 (market files) |
| Engagement | GitHub issues/PRs from outside contributors | 2 | 8 | 20 | GitHub API, public |
| Discovery | Discovery interviews held (owner) | **15–20** | 25 | 35 | Owner's interview log (date, ICP type, consent to notes) |
| Conversion | Qualified design-partner conversations | 2 | 5 | 10 | Owner's log; "how did you hear about us" free-text field on forms |
| Conversion | Design partners signed | 0 | 1 | **3–5** (model base: 5 in launch year 1) | Signed agreements (owner) |
| Revenue | Qualified pipeline (sum of proposed ACV) | $0 | $100k | $400k | Owner's spreadsheet; ESTIMATE ACVs from pricing-and-gtm.md §2 |
| Revenue | Signed (billed) ARR | $0 | $0–$40k | **~$110k** | Taken from investor\financial-model.csv / PRICING.md §4 base case (design partners at 50% of the $75k Growth list = $37.5k each; billed ARR end of Y1 $0.11M). Marketing does not forecast revenue independently |

**Attribution without trackers:** UTM-style query tags on links we control are read only as aggregate path counts in CDN logs; forms ask "How did you hear about us?" as optional free text; conference leads carry a source field typed at capture. No pixels, no third-party analytics, no session replay, no ad retargeting.

---

## 7. Discovery plan (owner-run)

**Rule: the owner conducts every interview. Agents never contact anyone.** Agents may prepare the guide, do desk review of public pages, and synthesise notes the owner shares.

**Goal:** test validation.md #1 ("startups spend months rebuilding pipelines", WEAK) and the three riskiest questions:
1. Will clinical-stage BCI startups pay $50k+/yr for FDA-facing data evidence and latency verification?
2. Do consumer neurotech firms currently track neural-data consent per state? (Start with a **desk review of public privacy policies**, no contact needed.)
3. Is CatalystNeuro-style conversion a business worth entering, or a partner channel?

**Sample (15–20 interviews, types only):**
| ICP | Interviews | Who (role type) |
|---|---|---|
| 1 Clinical-stage implant/device | 6–8 | Engineering lead, regulatory/quality lead |
| 2 Consumer EEG/neurotech | 3–4 | Privacy/legal lead, data/ML lead |
| 3 University spinouts | 2–3 | Technical co-founder |
| 4 CNS pharma / CRO | 2 | Biomarker or data-management lead |
| 6 NIH-funded core lab | 2 | Core director, lab data manager |

**Sourcing:** owner's own network, introductions, inbound from the law tracker / GitHub, and conference conversations. No purchased lists, no scraping of personal contact data.

**Guide (30 min, no pitch in the first 20 minutes):**
1. Walk me through the last time you took data from the electrode to a model or report. Which tools? (MNE, BIDS, NWB, LSL, BrainFlow, in-house?)
2. **How many engineer-weeks** went into ingest, sync and format conversion on your last project? (measures validation.md #1)
3. When results changed after a preprocessing change, how did you find out and document it?
4. How do you currently classify neural data and record consent by state? What happens when someone withdraws? (Q2)
5. What does an FDA reviewer or investor ask you to prove about your data and software? Who writes it today, and what does it cost? (Q1)
6. Do you use external conversion services? What would you pay to do it yourself? (Q3)
7. What budget line would a tool like this come from, and who signs?
8. Show the planned design (not a product) and price bands **labelled ESTIMATE**; ask for reaction, not commitment.
9. Would you consider a design-partner arrangement? (Only record "interested / not interested"; no terms.)

**Ethics and data handling:** ask consent before note-taking or recording; store notes without personal data beyond name/company in the owner's own log; delete on request; no neural data collected. Output: synthesis memo at M3 that updates validation.md verdicts, ICP priority and pricing ESTIMATEs.

---

## 8. Templates (marketing\templates\, all DRAFTS, not sent/posted)
cold-email-bci-startup.md · academic-lab-outreach.md · linkedin-series.md · press-release-launch.md · one-pager.md + one-pager.html · conference-booth-brief.md · law-tracker-newsletter-issue-01.md

## 9. Open items for the owner / queen
1. Trademark clearance before any public use of the name (names.md).
2. Privacy counsel review of the law tracker and of cold-outreach compliance (e.g. anti-spam and GDPR rules for B2B email) before launch (D10). Not legal advice.
3. D9 vs CONTENT-SPEC: one-pager.html loads IBM Plex from Google Fonts as instructed for this draft; the public site must self-host fonts (D9).
4. Confirm the mapping of product months to M1 (website launch date).
5. Verify SfN 2027 dates and both meetings' submission deadlines.
6. CONTENT-SPEC.md still carries pre-D1 copy ("automated neuro-cleaning", "Neuro-AI marketplace", "(working name)"); it conflicts with D1 and the banned-claims list and should be updated by the design lead.
