DRAFT — not sent/posted. Owner review required. Placeholders in [brackets].

# NeuroForge Bio
**Versioned, comparable pipelines and neural-data governance, from electrode to model.**

*Research and development software. Pre-product: every capability below is designed, planned or on the roadmap. Not a medical device; no diagnostic or therapeutic claims.*

---

## The problem
- **Pipelines change results.** Artifact-correction steps reduced decoding performance in Kessler et al., *Commun Biol* 2025. Huang et al., *Psychophysiology* 2025 tested 43 pipelines: "no single best pipeline".
- **Pipelines are rarely shared.** Code or pipeline availability: 20.9% of 129 EEG-BCI papers (Peksa et al., *Sensors* 2026).
- **Neural data is now regulated, inconsistently.** Colorado, California and Connecticut (effective 1 Jul 2026) treat neural data as sensitive data, with different definitions; Montana adopted SB 163 in 2025 (per a peer-reviewed review; statute text not yet reviewed). EU AI Act Art. 5(1)(f) bans emotion inference in workplaces and education (except medical/safety reasons). *Not legal advice.*
- **Regulated devices need documentation.** FDA's implanted-BCI guidance points to the Enhanced Documentation Level for device software.

## What we're building (one lineage graph, three views)
| | What | Status |
|---|---|---|
| **Open core** | Python SDK, validator, local provenance graph, multiverse runner; plug-ins for MNE, BIDS, NWB, LSL, BrainFlow | Planned (Apache-2.0 planned) |
| **Consent & Deletion Ledger** | Per-jurisdiction classification of each channel and derived feature; versioned opt-in consent; withdrawal propagated to derivatives and flagged on trained models; audit export | Planned |
| **Evidence Kit + latency harness** | Traceable lineage, test evidence and OTS/SOUP inventories for documentation work; reproducible timing reports | Roadmap |

## Who it's for
Clinical-stage neurotech teams · consumer EEG companies selling in CO/CA/CT/MT · university spinouts · CNS research sponsors and CROs · NIH-funded labs and core facilities.

## Security & compliance posture (planned)
Designed for HIPAA-aligned workflows · BAA for enterprise (planned) · SOC 2 Type II: on roadmap · AES-256 at rest, TLS 1.3 in transit (planned) · RBAC and audit logs (planned) · no third-party trackers on our website.

## Work with us
We are recruiting **[3–5] design partners** and holding short discovery conversations. [CONTACT EMAIL] · [WEBSITE]

---
*Sources: Kessler 2025 doi:10.1038/s42003-025-08464-3 · Huang 2025 doi:10.1111/psyp.70197 · Peksa 2026 doi:10.3390/s26175562 · state laws: CO HB24-1058, CA SB 1223, CT PA 25-113, MT SB 163 (via Cabrera et al., Bioethics 2026) · EU AI Act Art. 5 · FDA implanted-BCI guidance (fda.gov/media/120362/download). NeuroForge Bio: name subject to trademark clearance. © [YEAR]*
