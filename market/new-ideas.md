# New Product / Business Ideas Beyond the Blueprint

Prices are **ESTIMATEs**. Each one is anchored to comparable prices we opened: EmotivPRO $1,068–$2,689/yr; NeuroPype $79–99/mo startup; Aptible $499/mo; W&B Pro $60+/mo, with HIPAA on Enterprise; Flywheel by quote. "Competitors" lists only tools we verified exist. "None found" means none found in this pass, not that none exist.

Ranking: ★ = recommended top 5, ordered by why-now strength × fit with a code+math team × low regulatory drag.

---

### 1 ★ Neural-Data Consent & Deletion Ledger (API + dashboard)
- **What:** Classifies every channel and derived feature per jurisdiction: CO/CA central + peripheral, CT CNS-only, CA excludes inferred data, MT. Records versioned opt-in consent. Propagates withdrawal to raw data, derivatives, **and trained models** (lineage graph, with a model "unlearning/retrain required" flag). Produces an audit export.
- **Buyer:** Consumer/wellness EEG firms (Muse, Neurable, Neurosity, Emotiv class), BCI startups, and research sponsors.
- **Why now:** CO (effective Aug 2024), CA (Sep 2024), MT (May 2025) and **CT PA 25-113 (CTDPA sections effective 1 Jul 2026)**. The federal MIND Act (Sep 2025) directs an FTC study. HIPAA often does not cover these firms, so state law is the binding constraint.
- **Competitors:** No neural-specific tool found. Generic privacy/consent platforms exist but were not verified in this pass.
- **Price (ESTIMATE):** $500–$3,000/mo by data-subject volume, plus enterprise tiers.

### 2 ★ FDA Evidence Kit for BCI Software ("submission-ready data packages")
- **What:** Traceable data lineage, versioned datasets and pipelines, test evidence, and OTS/SOUP inventories for neural decoders. Generates document scaffolds aligned to FDA's "Content of Premarket Submissions for Device Software Functions" (Jun 2023), which implanted BCIs "should generally" follow at the **Enhanced Documentation Level** (FDA BCI guidance, 20 May 2021, updated note).
- **Buyer:** Clinical-stage implant companies (Paradromics-type: IDE Nov 2025, first implant Jun 2026), non-invasive medical-claim startups, and university spinouts heading to IDE.
- **Why now:** Several companies are moving into trials (Paradromics Connect-One EFS; Precision 510(k) Apr 2025; Science's PRIMA HUD designations, Jul 2026).
- **Competitors:** Regulatory consultancies and generic eQMS tools (not verified). Nothing neural-data-specific found.
- **Price (ESTIMATE):** $50k–$150k/yr platform, plus a per-submission package fee.

### 3 ★ Closed-Loop Latency & Timing Verification Harness
- **What:** Software plus reference-signal method to measure end-to-end latency and jitter (acquisition → decode → actuation) and clock-sync error across LSL/BrainFlow devices. Output is a signed, reproducible timing report.
- **Buyer:** BCI/neurostim makers, closed-loop research labs, and VR/neurofeedback vendors.
- **Why now:** Real-time speech BCIs are appearing (Paradromics real-time speech announcement, Sep 2026). Documentation expectations apply (FDA device-software guidance).
- **Competitors:** LSL provides the sync infrastructure but no certification report. None found for certification.
- **Price (ESTIMATE):** $15k–$60k/yr per product line; $5k per one-off report.
- **Note:** Computational/bench work only, no human stimulation. Clinical validation needs IRB/FDA.

### 4 ★ Preprocessing Multiverse / Robustness Audit
- **What:** Automatically runs a grid of preprocessing pipelines on a customer's (or a published) dataset and reports how decoding metrics and ERPs shift. Produces a reproducibility certificate with every parameter recorded.
- **Buyer:** CNS pharma teams using EEG biomarkers, BCI startups defending decoder claims, journals and reviewers.
- **Why now:** Kessler 2025 (*Commun Biol*): artifact correction **reduced** decoding performance. Huang 2025 (*Psychophysiology*): 43 pipelines, "no single best pipeline". Multiverse EEG papers are proliferating (eLife 2026, bioRxiv 2026).
- **Competitors:** MNE and EEGLAB are libraries. No commercial audit service found.
- **Price (ESTIMATE):** $10k–$40k per audit; $2k/mo self-serve.

### 5 ★ NWB/BIDS Conversion + Validation as a Product (not consulting)
- **What:** Self-serve and automated conversion of proprietary acquisition formats to NWB/BIDS, with validation. Includes "DANDI/OpenNeuro-ready" publishing and NIH DMS-plan evidence.
- **Buyer:** NIH-funded labs, core facilities, and companies contributing to consortia.
- **Why now:** NIH DMS Policy (effective 25 Jan 2023) expects investigators to "plan and budget for the managing and sharing of scientific data". DANDI holds 1,185 dandisets and ~2.39 PB, and is growing.
- **Competitors:** **CatalystNeuro** (69 labs, open-source consulting), NeuroConv (BSD-3, 81 stars), NWB GUIDE (MIT desktop app), bids-validator (MIT). It is a crowded but services-heavy space. **Partner with CatalystNeuro rather than fight it.**
- **Price (ESTIMATE):** Free open-source core; $3k–$15k per lab/yr for hosted automation and support.

### 6 Governed Decoder Benchmark & Certification ("MOABB-plus")
- **What:** Held-out, access-controlled test sets; standardised scoring; a signed certificate for vendors' decoders. Test data is never released, so results cannot be overfit.
- **Buyer:** Decoder/AI vendors, device makers, and procurement teams.
- **Why now:** Only 20.9% of EEG-BCI papers share code (Peksa 2026); cross-dataset comparison is hard.
- **Competitors:** **MOABB** ("Mother of All BCI Benchmarks", BSD-3, 1,057 stars) is an open, public-data benchmark. Ours differs through held-out data plus certification.
- **Price (ESTIMATE):** $5k–$25k per certification.

### 7 Synthetic Neural Data for Testing & Privacy-Safe Sharing
- **What:** Generative simulators, including biophysically constrained and statistical ones, that produce realistic multichannel EEG/ECoG/spike data with known ground truth. Used for pipeline testing, CI fixtures, and sharing where real data is restricted.
- **Buyer:** BCI software teams, the QA/regulatory functions of device makers, and educators (Neuromatch-type).
- **Why now:** State laws restrict sharing real neural data. Teams need ground truth to validate pipelines (ties to #4).
- **Competitors:** None commercial found. Academic simulators exist (not verified in this pass).
- **Caveat:** The privacy value of synthetic data is a **hypothesis**. Membership-inference risk must be tested before any privacy claim.
- **Price (ESTIMATE):** $1k–$5k/mo.

### 8 Post-Trial Neural Data Stewardship / Escrow
- **What:** Neutral custody of implant participants' data, device-configuration records and decoder models, so users keep continuity if a company pivots or fails. Includes consent-governed access.
- **Buyer:** Implant companies (as a trust signal to IRBs), trial sites, and patient-advocacy funders.
- **Why now:** "Recommendations on post-trial responsibility in implantable neural device research: a multidisciplinary consensus study" (*BMC Med Ethics* 2026, doi:10.1186/s12910-026-01475-7). Capital is concentrated in a few high-valuation BCI firms (HSBC calls BCI "the highest risk category").
- **Competitors:** None found.
- **Price (ESTIMATE):** $20k–$80k/yr per sponsor, plus a per-participant fee.

### 9 Remote Neural-Data Pipeline for Sensing-Enabled Neuromodulation Clinics
- **What:** Ingest, de-identify and QA chronic recordings from recording-enabled DBS and neurostim devices, collected remotely at scale for research networks.
- **Buyer:** Academic medical centres and neuromodulation research consortia.
- **Why now:** "Feasibility of Nationwide Remote Chronic Neural Data Collection from Recording-Enabled Deep Brain Stimulation Systems" (*Stereotact Funct Neurosurg* 2026, doi:10.1159/000552017). 4 neurostim first financings, $60M, in 1H26 (HSBC).
- **Competitors:** Device-vendor clinician portals (not verified).
- **Price (ESTIMATE):** $30k–$120k/yr per site network.

### 10 21 CFR Part 11 EEG-Endpoint Data Platform for CNS Trials
- **What:** Flywheel-style regulated platform, but for EEG and other biosignal endpoints: audit trails, e-signatures, de-identification, and central reading workflows.
- **Buyer:** CNS biotech sponsors and CROs.
- **Why now:** Neuro biopharma raised $1.8B (1H25), $2.5B (2H25) and $1.2B (1H26) (HSBC). Flywheel proves the model in imaging ("10 of the top 20 biopharma", Part 11).
- **Competitors:** Flywheel (imaging-first); EEG core-lab vendors (not verified).
- **Price (ESTIMATE):** $100k–$300k/yr.

### 11 Neural-Data Re-identification Risk Scanner
- **What:** Tests whether a dataset or feature set allows re-identification or linkage (e.g., via subject-specific signal signatures) before sharing, and outputs a risk score plus mitigation.
- **Buyer:** Data-sharing consortia, repositories, and companies subject to CO's biological-data "identification" language.
- **Why now:** Colorado defines biological data by use "for identification purposes". GDPR Art. 9 covers biometric data for unique identification.
- **Caveat:** Whether neural signals re-identify people at useful rates is a **research question to verify**. Do not claim it.
- **Price (ESTIMATE):** $2k–$10k per dataset scan.

### 12 EU AI-Act Use-Restriction Registry for Neuro-AI Models
- **What:** Metadata and enforcement layer that blocks deployment of emotion or cognitive-state models into workplace/education contexts (Art. 5(1)(f)) unless a medical or safety exception is documented.
- **Buyer:** Neurotech firms selling into the EU, and model vendors.
- **Why now:** Art. 5 has applied since 2 Feb 2025.
- **Price (ESTIMATE):** An add-on to #1 at $300–$1,500/mo.

### 13 Payer / Real-World-Evidence Data Packages for BCI Reimbursement
- **What:** Structured outcome and usage datasets (usage hours, task performance, adverse-event linkage) packaged for payer and HTA discussions.
- **Buyer:** Commercial-stage implant companies (Precision, Science's EU launch, Synchron).
- **Why now:** "Payers, Proof, and Public Trust: Lessons From Deep Brain Stimulation for Scaling BCIs" (*Mayo Clin Proc Digit Health* 2026). PRIMA's EU commercial launch (Jul 2026) means payer evidence is needed now.
- **Price (ESTIMATE):** $75k–$250k per program.

---

## Top 5 recommendation
1. **#1 Consent & Deletion Ledger.** Strongest why-now (4 state laws, one effective Jul 2026), no neural-specific competitor found, and pure software.
2. **#2 FDA Evidence Kit.** Highest ACV. It follows the clinical-trial wave, and the FDA's written "Enhanced Documentation Level" expectation makes the need concrete.
3. **#4 Preprocessing Multiverse Audit.** Directly backed by 2025 peer-reviewed findings and a strong fit for a math-heavy team. It also doubles as content marketing.
4. **#3 Latency Verification Harness.** A technical wedge into device makers that complements #2.
5. **#5 Conversion + Validation (partner with CatalystNeuro).** Acquisition channel into academia, with near-zero regulatory drag.

These five share one core: **a lineage/provenance graph over neural data, pipelines and models.** That graph is the actual platform. Consent (#1), FDA evidence (#2) and reproducibility (#4) are views over it.
