# NeuroForge (working name): 6 website design options (GATE A)

Open each file directly in a browser. Every option is one self-contained HTML file. It pulls fonts from Google Fonts, and option 3 also pulls three.js from jsDelivr. All six share the same copy and facts from `CONTENT-SPEC.md`, so they differ only in design. The same sections appear in every file: hero, the Ingest > Clean > Neuro-AI > SDKs pipeline, researchers / hardware split, compliance, pricing teaser, research/whitepaper preview and footer. None of them claims certifications, customers or medical benefit, and all mock numbers are tagged demo, target or ESTIMATE. The standalone hero graphics are in `assets/` (see `assets/README.md`). Research basis: `competitor-teardown.md`.

| # | File | Concept | Palette | Fonts | Echoes |
|---|---|---|---|---|---|
| 1 | option-1.html | Clinical precision (light) | #F7F9FB bg, #0B2540 ink, #0E7C86 teal, #5B8DEF blue, #DDE4EC hairlines | IBM Plex Sans + IBM Plex Mono | Precision Neuroscience, Kernel, Benchling |
| 2 | option-2.html | Dark developer-infra / terminal | #0A0E14 bg, #C9D1D9 fg, #39FF88 green, #7AA2F7 blue, #F7B955 warn | JetBrains Mono + Inter | Vercel, Supabase, OpenBCI docs, Stripe dev section |
| 3 | option-3.html | Immersive 3D neural cosmos | #05010F bg, #8B5CF6 violet, #22D3EE cyan, #F472B6 pink, glass cards | Space Grotesk + Inter | Neuralink, Paradromics, Emotiv |
| 4 | option-4.html | Editorial science journal | #FBF8F1 paper, #1A1A1A ink, #B3261E oxblood, #1F3A5F navy | Fraunces + Inter + IBM Plex Mono | Blackrock (GT Super serif), Databricks (Merriweather, warm paper), BrainFlow (Lora), journal layouts |
| 5 | option-5.html | Data-viz, dashboard-forward | #0F172A bg, #1E293B panels, #38BDF8 / #A3E635 / #FBBF24 / #F87171 | Inter Tight + DM Mono | Snowflake, Databricks, Stripe, Kernel data reports |
| 6 | option-6.html | Warm human / biotech | #FFF7F0 cream, #2B2118 ink, #E07A5F terracotta (text #B4532F), #3D8B7D teal, #F2CC8F sand | DM Serif Display + DM Sans | Synchron, Neurable, Benchling |

## Option 1: Clinical precision
- **Concept:** Medical-device calm. Hairline grids, spec-sheet tables, a numbered 01–04 pipeline, and a live 10-20 EEG montage hero with flowing traces. The research card has a clickable electrode-group figure.
- **Pros:** Reads as trustworthy and regulated, which suits the compliance moat and hospital or enterprise buyers. It is fast and very accessible, and the easiest of the six to build and maintain.
- **Cons:** It could blend in with clinical BCI companies and is the least memorable. It can also feel cold to hackers and students.
- **Pitch:** "The calm, auditable data layer that a regulated neurotech team can trust on day one."

## Option 2: Dark developer infrastructure / terminal
- **Concept:** Built for engineers. The hero is an oscilloscope stream where raw noisy traces become clean once they pass a `clean()` divider. It has a `pip install` copy button and tabbed Python / C++ / Unity code, shows the pipeline as a command log, and presents compliance as `security.yaml` plus plain text.
- **Pros:** Fills the gap the teardown found, since no BCI company speaks the Stripe/Vercel infra language. It converts developers and seed-stage hardware teams, the primary GTM, and signals "software company" clearly.
- **Cons:** It is less inviting to clinicians and non-coding scientists, the dark terminal look is common among dev tools, and it relies on real docs existing.
- **Pitch:** "Stripe for neural data: `pip install`, stream, clean, decode."

## Option 3: Immersive 3D neural cosmos
- **Concept:** A cinematic full-screen three.js point-cloud brain with firing arcs behind big gradient type, glass cards, orbit-node pipeline, and a "vault" compliance section. It has a WebGL fallback and honours reduced motion.
- **Pros:** The strongest wow factor and the most shareable. It suits investor demos and conferences, and it looks like the neurotech sector.
- **Cons:** It is the heaviest page (GPU, three.js ~600 KB from CDN) and the riskiest on low-end devices. It is closer to the style of Neuralink and other implant makers than to a data platform, and style can outrun substance.
- **Pitch:** "Every signal in the brain, made navigable."

## Option 4: Editorial science journal
- **Concept:** A journal-style masthead ("Vol. 1 · Issue 1"), an engraving-style brain plate as Fig. 1, a "Methods" §1–§4 pipeline, a formal Data Availability & Ethics statement for compliance, and an abstract-page research preview with an interactive raw/cleaned Figure 2.
- **Pros:** Speaks natively to scientists and to the free academic tier, and puts the Whitepaper/Research page at the centre, which fits the somatosensory research stream. Very distinctive in the sector and credible, not hype.
- **Cons:** It is less conversion-driven, some buyers may read it as academic or slow, and it has dense type on mobile.
- **Pitch:** "A neuro-data platform that reads like the papers it helps you write."

## Option 5: Data-viz, dashboard-forward
- **Concept:** The product is the hero: a live dashboard with a topomap, band-power bars, traces and a latency sparkline, all tagged demo data. Below it, a bento grid gives each pipeline stage its own live micro-chart, a segmented control swaps the researcher and hardware views, and compliance appears as an honest green/amber status board. It also has a usage sizer with no prices and an illustrative model slider in the research preview.
- **Pros:** Shows the product instead of describing it, and suits analytics buyers. The status board makes "roadmap, not certified" honesty look like a strength.
- **Cons:** It is the most complex to build and keep truthful, since it needs real product UI later. It could look busy, and demo charts may be mistaken for real results despite the labels.
- **Pitch:** "See your brain data working before you sign up."

## Option 6: Warm human / biotech
- **Concept:** A friendly, organic neuron network hero, cream and terracotta, rounded cards, and plain-language "Trust, by design" compliance. The academic tier is highlighted, and "From the lab" has a conceptual hand-to-cortex interactive figure.
- **Pros:** The most approachable option. It humanises a technical product, fits the academic-first GTM and community building, and stands apart from both dark-tech and clinical-blue.
- **Cons:** It may seem too soft for enterprise or hardware buyers who want "infrastructure". Its terracotta needed darkening for AA text contrast, and it looks less "deep tech".
- **Pitch:** "Neural data infrastructure with a human touch: tidy data, open science, fewer late nights."

## Design lead recommendation (non-binding)
If one site has to serve the GTM (free academic tier, then seed-stage BCI hardware startups), I'd pick **option 2 or 5 as the base, with option 4's Research page**. Options 2 and 5 claim the infra positioning no competitor holds, and option 4's format suits the whitepaper. Option 3's 3D brain works best as a single showcase section or investor-deck visual, not the whole site.

## Verification status
- All 6 pages: tags balance (Python html.parser), and the inline JS passes `node --check`. The only external hosts are Google Fonts, plus jsDelivr for three.js in option 3. A scan for banned claims (certified, HIPAA-compliant, treat/cure/diagnose, invented user counts) was clean.
- Option 3 was screenshotted in Edge at desktop and at 477 px width. The other five have **not been visually checked in a browser yet**. Mobile widths below 477 px have not been rendered for any option.
