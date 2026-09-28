# Shared content spec for option-1..6.html (all options use the same facts; only design differs)

Brand: "NeuroForge" with a visible "(working name)" tag near the logo or in footer. Tagline ideas (pick/adapt per concept):
"The data layer for brain-computer interfaces." / "Neural data infrastructure, from electrode to model." / "Picks and shovels for neurotech."

## Honesty rules (binding)
- No medical/therapeutic claims ("treat", "diagnose", "restore", "cure"). Say "research and development use".
- No invented customers, logos, testimonials, user counts, uptime, or benchmarks. Any number shown in a mock UI is tagged "demo data" or "target".
- Compliance: do NOT claim certifications. Use "designed for HIPAA-aligned workflows", "BAA available for enterprise (planned)", "SOC 2 Type II: on roadmap", "AES-256 at rest, TLS 1.3 in transit", "RBAC + audit logs", "data residency options (planned)".
- Neural-data privacy laws: mention "built to support emerging US state neural-data privacy laws (e.g. Colorado, California, Connecticut, Montana)" — no bill numbers, no legal advice claim.
- No photos of people. Graphics only.

## Nav
Platform · Neuro-AI · SDKs · Research · Pricing · Docs  |  Sign in · "Start free" (primary CTA)

## Hero
Headline (adapt): "The data layer for brain-computer interfaces."
Sub: "Hardware-agnostic ingest, automated neuro-cleaning, and Neuro-AI models — so your team ships decoders, not data pipelines."
CTAs: "Start free (academic)" + "Talk to us / Book a demo". Small line: "Works with BIDS · LSL · EDF/BDF · NWB · XDF" (formats, not partners).

## Value props — pipeline (4 steps)
1. Ingest — Hardware-agnostic connectors for EEG, ECoG, and microelectrode arrays. BIDS, Lab Streaming Layer (LSL), EDF/BDF, NWB, XDF. Low-latency time-series storage.
2. Clean — Automated neuro-cleaning: filtering, ICA, artifact rejection, re-referencing, normalization. Versioned, reproducible pipelines with provenance.
3. Neuro-AI — Model marketplace: motor-intent decoding, cognitive-state estimation, plus bring-your-own-model. Benchmarked on public datasets (label: "benchmarks published with methods").
4. SDKs — Python, C++, Unity / Unreal. Stream in, get predictions out.
Optional code snippet (Python, illustrative):
```
import neuroforge as nf
stream = nf.connect("lsl://headset-01")
clean  = stream.pipeline("ica-default").run()
intent = nf.models.get("motor-intent/v1").predict(clean)
```
(label "Illustrative API — subject to change")

## Audience split
For researchers: free academic tier, BIDS-native, reproducible pipelines, export to MNE/EEGLAB-compatible formats, citation-ready provenance.
For hardware companies: white-label SDK, device connector program, cloud + edge deployment, compliance handled so you can focus on the device, usage-based pricing.

## Compliance & security
AES-256 at rest / TLS 1.3 in transit · RBAC & audit logs · HIPAA-aligned workflows, BAA (planned) · SOC 2 Type II (roadmap) · neural-data privacy laws support · data residency (planned) · de-identification tooling.

## Pricing teaser (no final prices)
Academic — Free (labs & students, fair-use limits)
Startup — "Usage-based" (for seed-stage BCI hardware teams) — "Pricing at launch"
Enterprise — "Custom" (BAA, SSO, dedicated support, on-prem/edge)
CTA "Join the early-access list".

## Whitepaper / Research page preview
Section "Research" with 1 featured + 2 cards:
- Featured: "Bidirectional closed-loop somatosensory feedback: a computational study" — "Modelling how patterned stimulation of somatosensory cortex could encode touch, pressure and proprioception. Computational/theoretical work; any clinical application requires IRB/FDA oversight." Status: "In preparation". Button "Read preview".
- "Benchmarking automated artifact rejection on public EEG datasets" — Status: "Planned".
- "A reference architecture for HIPAA-aligned neural data pipelines" — Status: "Planned".
Include a small interactive visual in the preview if it fits the concept (e.g. hover a figure).

## Footer
"NeuroForge (working name) — design concept, not a live product." Links: Docs, Status, Security, Privacy, Careers. "© 2026".

## Technical rules
Single self-contained HTML (inline CSS/JS). External scripts only cdn.jsdelivr.net/npm or cdnjs.cloudflare.com; fonts only Google Fonts. Inline the hero graphic code from design/assets/asset-N-*.html (adapt to the page), do not iframe it. Responsive (360px to 1440px+), no horizontal scroll, semantic landmarks, skip link, visible focus, WCAG AA contrast, alt/aria-labels on graphics, prefers-reduced-motion respected.
