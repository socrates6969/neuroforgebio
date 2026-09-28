# Pricing Models & Go-To-Market

Prepared 2026-09-26. Comparable prices were opened on the vendors' own pages (grade D). Our tiers are **ESTIMATEs** for testing, not validated.

## 1. Comparable pricing seen

| Vendor | Category | Model | Public prices |
|---|---|---|---|
| **EmotivPRO** | EEG analysis SaaS bundled with hardware | Per-seat subscription, annual prepay (up to 40% saving) | Lite **$0**; Standard **$89/mo billed annually ($1,068/yr)**; Standard Team **$224.08/mo ($2,689/yr)**; Performance by quote. Data sharing for 2+ seat licences |
| **NeuroPype (Intheon)** | Real-time biosignal pipelines + cloud (NeuroScale) | Eligibility-gated tiers | Academic **free** (non-commercial); Startup/Individual **$79–$99/mo** (for ≤$200K revenue or raised); Enterprise by quote |
| **Weights & Biases** | ML dev-infra | Freemium seat-based; HIPAA gated to Enterprise | Free $0 (≤5 model seats); Pro **from $60/mo** (<50 employees, 100 GB); Enterprise custom (HIPAA, single-tenant, CMEK, SSO, audit logs). **Academic: free Pro licence** |
| **Aptible** | HIPAA PaaS | Base fee + usage | Development $0 + usage; Production **$499/mo** + usage (HIPAA, SOC 2); Enterprise custom (HITRUST, PCI) |
| **AWS HealthLake** | Managed FHIR | Pure usage | $0.27 per data-store-hour; storage $0.25–$0.37/GB-month; $0.19/GB export |
| **Flywheel** | Regulated imaging research data platform | Enterprise quote | Not public (claims 21 CFR Part 11; "10 of the top 20 biopharma") |
| **brainlife / DANDI / OpenNeuro** | Public research platforms | Free (grant-funded) | $0 |

**Patterns**
1. Academic is free everywhere, so academic revenue comes from institutions, not individuals.
2. Compliance (HIPAA, SSO, audit logs) is the standard **enterprise upsell gate** (W&B, Aptible).
3. Eligibility-gated startup pricing below $100/mo is common (NeuroPype).
4. Regulated pharma platforms are quote-only.

## 2. Recommended tiers (ESTIMATE, to test in discovery)

| Tier | Target | Price (ESTIMATE) | Includes | Gate / rationale |
|---|---|---|---|---|
| **Open Core** | Individual researchers, students | **$0** | Open-source SDK (Python first), converters, validators, local provenance graph, MNE/BIDS/NWB/LSL/BrainFlow integrations | Distribution. Matches the NeuroPype/W&B academic norm |
| **Lab / Institution** | Labs, core facilities | **$3k–$10k/yr** per lab (site licences for cores) | Hosted provenance, DANDI/OpenNeuro publishing, NIH DMS reporting, team seats | NIH DMS policy asks investigators to budget for data management and sharing, so this can be written into grants |
| **Startup** | Neurotech startups ≤$2M raised | **$300–$800/mo** | Consent & deletion ledger (core states), hosted pipelines, latency harness (self-serve), SSO | Priced between NeuroPype ($79–99) and Aptible ($499). Compliance value justifies a premium |
| **Growth** | Series A–C neurotech / clinical-stage | **$50k–$150k/yr** | Full ledger (all jurisdictions + EU AI-Act flags), FDA Evidence Kit, multiverse audits, BAA-capable deployment, audit exports | The ACV band from sizing.md S1 |
| **Enterprise / Pharma** | CNS sponsors, CROs, large device firms | **$100k–$300k+/yr** | 21 CFR Part 11 workflows, single-tenant/VPC, validation packages, SLAs | Flywheel-style quote |
| **Services (add-on)** | Any | $5k–$40k per engagement | Multiverse audit, timing certification, submission package, conversion | Early revenue while the product matures |

Price metric: bill **Startup/Growth by data subjects plus devices under management** (it scales with consent obligations), not by GB. Storage is a commodity (AWS usage prices), so do not price it as the value metric.

## 3. First-customer list: types only (no personal contact data)
1. **Clinical-stage implant BCI companies entering IDE/EFS trials**: the Paradromics/Precision stage profile. Offer: FDA Evidence Kit + latency harness.
2. **Consumer and wellness EEG/neurotech companies selling in CO/CA/CT/MT**: the Muse/Neurable/Neurosity/Emotiv class. Offer: Consent & Deletion Ledger. Qualification signal (public, no contact): a privacy policy with no neural-data-specific consent language.
3. **University BCI spinouts** from labs that publish on DANDI/OpenNeuro. Offer: startup tier.
4. **CNS biotech sponsors using EEG endpoints**, and the CROs that serve them. Offer: Part 11 EEG platform + multiverse audit.
5. **Neuromodulation research networks** with sensing-enabled DBS. Offer: remote data pipeline.
6. **Core facilities / EEG labs on NIH grants.** Offer: Lab tier, budgeted under the DMS policy.
7. **Channel partners, not customers:** CatalystNeuro (NWB conversion services, 69 labs) and hardware vendors that ship open SDKs (OpenBCI, BrainFlow ecosystem).

## 4. Channels
| Channel | Why (sourced where possible) | Tactic |
|---|---|---|
| **GitHub / PyPI integrations** | Where users already are: MNE 308k downloads/month, pynwb 108k, pyRiemann 64k, pylsl 34k, braindecode 22k (pypistats, Sep 2026) | Ship MNE/BIDS/NWB/LSL plug-ins that emit provenance to our graph. Open-source the validator and multiverse runner |
| **SfN annual meeting** | "Over 30,000 members" / "nearly 35,000" (two SfN pages differ); annual meeting ">30,000 attendees", **536 exhibiting companies** (sfn.org/about) | Poster on multiverse findings and a booth demo. Budget TBD, and the owner must approve any purchase |
| **International BCI Society Meeting** | 12th meeting **7–10 Jun 2027, Šibenik, Croatia**. Sponsorship/exhibits offered (bcisociety.org) | Workshop: "Neural-data governance under CO/CA/CT/MT + EU AI Act". Sponsor tier if approved |
| **Neuromatch** | Global computational-neuro education community; NMA course content has 3,136 GitHub stars | Contribute free tutorials using the open core |
| **Peer-reviewed content** | Our wedge rests on peer-reviewed results (Kessler 2025, Huang 2025, Peksa 2026) | Publish a reproducibility/benchmark paper and a data descriptor. Target journals: *J Neural Eng*, *Sci Data*, *Neuroinformatics* (channel choices, not claims) |
| **Regulatory content** | CT effective 1 Jul 2026; MIND Act FTC study | A free "neural-data law tracker" page (with a not-legal-advice banner) as SEO and lead magnet |
| **Design-partner programme** | High-ACV segments need proof | 5 design partners at 50% off Growth for 12 months, in exchange for case studies and anonymised metrics |

## 5. Sequencing (proposal for GATE A/B)
1. **Months 0–3:** Open-core provenance SDK + validator. Run the multiverse audit on public DANDI/OpenNeuro data and publish results (credibility, no customers needed).
2. **Months 3–9:** Consent & Deletion Ledger MVP (CO/CA/CT/MT + EU AI-Act flag); Startup tier; 3–5 design partners.
3. **Months 9–18:** FDA Evidence Kit + latency harness; Growth tier; first pharma pilot.
4. Defer the model marketplace and Unity/Unreal SDKs until a customer pulls for them (validation.md #6, #10).
