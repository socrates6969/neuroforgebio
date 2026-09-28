# BCI / Neurotech Software Market Landscape

Prepared 2026-09-26 by the BA/marketing agent. Research only, no contact made with any company.

**Evidence grades** (per BRIEF): A = peer-reviewed, or primary legal/regulatory text. B = reputable press, or a tertiary source such as Wikipedia (secondary, B-). C = preprint or theory. D = company marketing, newsroom or press release.
**How sources were accessed:** WebSearch was unavailable. Pages were opened with WebFetch, with curl (text extraction), or through the Wayback Machine (`web.archive.org/web/<year>id_/URL`), and each is marked accordingly. Figures seen only as a headline in an index, with the article body not opened, are marked **[headline only]**.

---

## 1. Hardware makers

### 1a. Invasive / implanted BCI

| Company | What they build | Funding / valuation (sourced) | Regulatory / clinical status (sourced) | Software: in-house vs bought |
|---|---|---|---|---|
| **Neuralink** | Implanted "Telepathy" BCI; "Blindsight" vision implant | $650M Series E, June 2025 (Neuralink blog title "Neuralink raises $650M Series E", neuralink.com/blog/neuralink-raises-650m-series-e/, D, body not extractable). HSBC puts the 2025 deal at a **$9B post-money** valuation (HSBC Innovation Banking, *2026 Mid-Year Healthcare Venture Report*, p.49, PitchBook data, B). Earlier: $158M total by 2019, $100M of it from Musk (Wikipedia "Neuralink", B-). $280M Series D in Aug 2023 (Reuters/CNN) **[headline only]**; $205M in Jul 2021 (CNBC) **[headline only]** | First human implant Jan 2024. 12 trial participants reported Sep 2025. Blindsight got FDA Breakthrough designation Sep 2024. First UK patient Oct 2025 (Wikipedia, B-) | **In-house.** Vertically integrated: implant, robot and app. Not a likely buyer of core pipeline software |
| **Synchron** | Endovascular "Stentrode" BCI | $75M Series C, Dec 2022, led by ARCH (Synchron newsroom listing of the BusinessWire release, D). **$200M Series D, 6 Nov 2025** (Synchron newsroom: BusinessWire, Bloomberg and MassDevice headlines, D/B) | JAMA Neurology trial publication is listed in its newsroom. First US patient Dec 2022 (FierceBiotech) **[headline only]** | **In-house plus big-tech partners.** "Chiral, the World's First Cognitive AI Brain Foundation Model" (19 Mar 2025). NVIDIA Holoscan and Apple Vision Pro demo (Mar 2025). Native BCI integration with iPhone/iPad/Vision Pro (May 2025) (all from the Synchron newsroom, D). Builds its own AI stack |
| **Paradromics** | "Connexus" fully implantable BCI, 421-channel microelectrode array | "Nearly $100 million as of February [2025], according to PitchBook" (CNBC, 2 Jun 2025, opened via curl, B). $33M venture round in 2023 led by Prime Movers Lab (Wikipedia, B-). Neom strategic partnership, amount undisclosed (CNBC, B) | Two FDA Breakthrough designations (2023, 2024), TAP pilot, IDE approved Nov 2025 (Wikipedia, B-). First Connexus implant in the Connect-One early feasibility study with Univ. of Michigan, 17 Jun 2026. Real-time speech announced 14 Sep 2026 (Paradromics newsroom, D) | Mostly in-house (clinical-stage). Possible buyer of tooling for FDA documentation and verification |
| **Precision Neuroscience** | "Layer 7" thin-film surface array, 1,024 electrodes | $12M Series A (May 2021). $41M Series B (Jan 2023). $102M Series C (Dec 2024). **$180M total as of Jan 2026** (Wikipedia, B-) | **FDA 510(k) clearance Apr 2025** for implantation of up to 30 days. More than 68 patients by Jan 2026. Medtronic partnership Jan 2026 (Wikipedia, B-) | Unknown. The short-duration clinical use suggests intra-operative data tooling needs |
| **Blackrock Neurotech** | Utah array / NeuroPort research systems; sells a research product catalog | **Tether invested $200M and became majority stakeholder, 29 Apr 2024** (Tether press release, opened via Wayback, D) | Long-standing research implant supplier. Its site sells "neurophysiology research tools built for animal and human use" (blackrockneurotech.com/products, D) | Ships its own acquisition software with its hardware. Its academic customers use MNE, SpikeInterface, etc. |
| **Science Corp.** | PRIMA retinal implant; biohybrid interfaces | **$230M Series C closed 5 Mar 2026** (Science newsroom, D). HSBC lists a $230M Q1 2026 Series C in Alameda, CA at a 2.3x step-up and **$1.5B post-money** (HSBC 1H26, p.49–50, B) | CE mark application Jun 2025. NEJM report Oct 2025. **European commercial launch of PRIMA** and FDA Humanitarian Use Device designations, 22 Jul 2026 (Science newsroom, D) | In-house |
| **Merge Labs** (new, non-invasive/molecular/ultrasound) | "Research lab". Molecules instead of electrodes; ultrasound | **$250M seed at $850M valuation**. OpenAI wrote the largest check, alongside Bain Capital and Gabe Newell (TechCrunch, 15 Jan 2026, B). HSBC: $252M seed Q1 2026, $850M post-money (B) | Pre-clinical | In-house research |

### 1b. Non-invasive (EEG / fNIRS / wearable)

For these companies, funding was **not verified in this pass**: the press URLs were not openable. Product descriptions come from each company's own homepage `<title>`/meta description, fetched 2026-09-26 (D).

| Company | What they sell (own description, D) | Software posture (sourced where possible) |
|---|---|---|
| **OpenBCI** | "Versatile and affordable bio-sensing microcontrollers" for EEG/EMG/ECG | Open-source **OpenBCI_GUI, MIT licence**, 959 GitHub stars (GitHub API, A-level fact). Relies on the community (BrainFlow, LSL) |
| **Emotiv** | "Wireless EEG hardware and software" | **Sells software subscriptions (EmotivPRO):** Lite $0; Standard **$89/mo billed annually ($1,068/yr)**; Standard Team **$224.08/mo ($2,689/yr)**; Performance by quote. "Organizational Data Sharing" for 2+ seats (emotiv.com/products/emotivpro, D). This is a working hardware-plus-SaaS model |
| **Muse (Interaxon)** | "World's most popular consumer EEG device" (own claim, D) | Consumer app. Research access via SDK (not verified) |
| **Neurable** | EEG headphones ("The Mind. Unlocked.") | Consumer/enterprise. Unknown |
| **Neurosity** | "Crown" focus device for developers | Has a developer SDK, device emulators and a developer console (neurosity.co, D) |
| **Bitbrain** | Neurotech combining "neuroscience, AI and hardware" | Unknown |
| **g.tec medical engineering** | BCIs for "invasive and non-invasive brain signal recording" | Sells its own BCI software (not priced publicly) |
| **Brain Products GmbH** | Amplifiers, electrodes, caps, and "hardware & software solutions" | Sells its own analysis software (price not public) |
| **Neuroelectrics** | Personalised brain-stimulation therapy "anywhere" | Clinical/therapy focus |
| **Cognixion** | "Accessible, non-invasive BCIs combining neuroscience, AI and spatial computing" | Assistive AR/BCI headset (IEEE Spectrum, Mar 2025) **[headline only]** |
| **Kernel** | Kernel Flow time-domain fNIRS (peer-reviewed system paper: J. Biomed. Opt. 27(7):074710, 2022) **[headline only]** | Unknown |

**Takeaway:** hardware makers split three ways.
- Well-funded implant leaders (Neuralink, Synchron, Science, Merge) build the software stack themselves.
- Clinical-stage implant startups (Paradromics, Precision) need regulated tooling.
- Non-invasive vendors already sell their own subscription software (Emotiv) or lean on open source (OpenBCI).

---

## 2. Software and data-infrastructure competitors and substitutes

GitHub figures come from `gh api repos/...` on 2026-09-26. PyPI downloads come from pypistats.org "recent" (last month) on 2026-09-26. Archive counts come from the live public APIs.

| Tool / service | What it does | Pricing | Licence (verified from LICENSE file where noted) | Adoption signal | Gaps (our read) |
|---|---|---|---|---|---|
| **BrainFlow** | Uniform SDK to acquire and parse EEG/EMG/ECG from many boards | Free | **MIT** (LICENSE file) | 1,761 stars; 8,299 PyPI downloads/month | Acquisition only. No storage, compliance or multi-tenant cloud |
| **Lab Streaming Layer (LSL / liblsl)** | Time-synchronised multi-modal streaming on a LAN | Free | **MIT-style** (liblsl LICENSE; super-repo: "most subprojects MIT") | 780 stars (super-repo); **pylsl 33,892 downloads/month** | LAN-scoped. No persistence, auth or audit |
| **MNE-Python** | M/EEG analysis (filtering, ICA, source, decoding) | Free | **BSD-3-Clause** | 3,528 stars; **308,276 PyPI downloads/month** | Library, not a platform. No data governance |
| **EEGLAB** | MATLAB EEG processing environment | Free (MATLAB licence needed) | **BSD-2-Clause** core; plugins vary | 797 stars | MATLAB dependency; desktop-centric |
| **OpenViBE** | Real-time BCI designer (Inria Rennes) | Free | Not confirmed on homepage | v3.7.0 current | Desktop; research-grade |
| **BCI2000** | General-purpose real-time BCI research system | Free, open source (bci2000.org) | Licence page not accessible | Windows-centric | Research only |
| **NeuroPype / NeuroScale (Intheon)** | Visual real-time biosignal pipelines; cloud deploy on NeuroScale | **Academic free; Startup/Individual $79–$99/mo** (for entities with ≤$200K revenue or funds raised); Enterprise by quote (neuropype.io/pricing via Wayback, D) | Commercial; "open-source visual pipeline designer" | — | **Closest commercial analogue to the owner's blueprint**, including the same academic-free / startup-tier GTM |
| **DANDI Archive** | Neurophysiology archive (NWB), BRAIN-Initiative funded | Free | Apache-2.0 (server) | **1,185 dandisets (434 published), 2,208 users, ~2.39 PB** (api.dandiarchive.org/api/stats, 2026-09-26) | Sharing/archiving, not real-time or product-grade |
| **OpenNeuro** | BIDS dataset sharing | Free | MIT | **1,902 datasets** (OpenNeuro GraphQL count) | Sharing only |
| **brainlife.io** | Cloud apps for MRI/EEG/MEG; "400+ data processing Apps" | **Free**; "publicly funded by NSF, DoD, Kavli Foundation and NIH" | Open | "over 2,000 users" (brainlife.io/about, D) | Academic imaging focus |
| **Pennsieve** | Public and private scientific data management and analysis (discover.pennsieve.io) | Not found | Python client licence unasserted | pennsieve-python has 3 stars | Pricing and compliance terms not public |
| **NWB (pynwb) / BIDS spec** | Data standards | Free | pynwb BSD-style (LBNL); BIDS spec CC-BY-4.0 | **pynwb 108,248 downloads/month** | Standards, not services |
| **CatalystNeuro** | **Services firm: converts lab data to NWB and publishes to DANDI** | Consulting (price not public) | "100% open source" output | "69 research labs supported, 17 grant-funded projects, 35 partner institutions" (catalystneuro.com, D) | **Incumbent for conversion-as-a-service.** Academic focus, not compliance-grade |
| **SpikeInterface / Kilosort** | Spike-sorting pipelines | Free | MIT / GPL-3.0 | 852 / 629 stars; spikeinterface 29,289 downloads/month | Invasive-ephys only |
| **braindecode / pyRiemann** | Deep learning / Riemannian decoders for EEG | Free | BSD-3-Clause | 22,316 / 64,175 downloads/month | Model code with no model registry or governance. Direct substitute for a "model marketplace" |
| **Neuromatch** | Education, courses, community | Free (NMA course content CC-BY-4.0, 3,136 stars) | — | — | Channel, not a competitor |
| **Datavyu** | Video coding/annotation | Free | GPL-3.0 | Last push Sep 2024 | Adjacent only |
| **Blackrock / Ripple software** | Acquisition software bundled with hardware | Bundled | Proprietary | — | Vendor-locked |
| **Flywheel** | Medical-imaging data platform: "Gears" containers, 21 CFR Part 11, de-identification | By quote | Proprietary | "1B+ images", "10 of the top 20 biopharma" (flywheel.io, D) | Imaging-first. **Shows that a compliance-grade research data platform sells to pharma** |
| **XNAT** | Open-source imaging informatics | Free | Open source | — | Imaging |
| **AWS (HealthLake + HIPAA-eligible services)** | FHIR store plus general cloud | HealthLake: $0.27/data-store-hour, $0.25–0.37/GB-month, and more (aws.amazon.com/healthlake/pricing, D) | — | **"175+" HIPAA-eligible services**, including S3, **Timestream** (time series) and SageMaker AI. A BAA is required before handling PHI (AWS HIPAA reference, updated 3 Sep 2026, D) | FHIR-centric. No neural formats. **But it makes HIPAA infrastructure a commodity** |
| **Google Cloud Healthcare API** | FHIR/DICOM/HL7v2 | Pricing page not extractable | — | — | No neural formats |

## 3. Gaps that are real (evidence-backed)

1. **Fragmentation and poor code sharing.** A PRISMA systematic review of EEG-BCI resources (Peksa et al., *Sensors* 2026, doi:10.3390/s26175562, A) retained 129 publications. Data availability was stated in **61.2%**, but code/pipeline availability in only **20.9%**. It documents heterogeneity in acquisition, channel layouts, tasks, preprocessing and evaluation.
2. **Preprocessing changes the results.** Kessler et al., *Commun Biol* 2025 (doi:10.1038/s42003-025-08464-3, A) found that **all artifact-correction steps reduced decoding performance**, while higher high-pass cutoffs increased it. Huang et al., *Psychophysiology* 2025 (doi:10.1111/psyp.70197, A) tested 43 pipelines and found "no single best pipeline". The consequence: pipeline provenance and sensitivity analysis matter more than one "automated cleaning" default.
3. **Inconsistent data formats hamper ML.** Ruiz-Mateos Serrano et al., *Sci Adv* 2026 (doi:10.1126/sciadv.aee8595, A): "Small studies with divergent designs also yield inconsistent data formats and variable data quality, complicating the creation of robust, generalizable machine learning algorithms."
4. **No neural-specific privacy tooling was found** among the tools above. Every open tool lacks consent, deletion and audit features. HIPAA infrastructure is a commodity (AWS, Aptible), but mapping to neural-data statutes is not (see regulation.md).

## 4. Implications for the blueprint (short)
- The acquisition, analysis and archive layers are **crowded with free, well-adopted open source**: MNE has about 308k downloads/month and DANDI/OpenNeuro are free and NIH-funded. Do not compete there; **integrate with them**.
- The open commercial whitespace sits in **governance** (consent, deletion, audit, state-law mapping), **regulated evidence** (FDA software documentation, latency verification) and **reproducibility services**, not in storage or cleaning.
- NeuroPype already runs the exact "academic free / startup $79–99/mo" playbook. Differentiation has to be compliance and regulated workflows, not pipelines.
