DRAFT — not sent/posted. Owner review required. Placeholders in [brackets].

# LinkedIn series: 5 posts from the owner's account

**Poster:** Marius Carlsson only, after trademark clearance. One post every 1–2 weeks (MARKETING-PLAN.md §4, M1–M4). No tagging of companies or people who have not agreed. No customer, partner or user claims. Every status word is designed / planned / roadmap. Links go to our own site (no link shorteners with tracking).

---

## Post 1: "There is no single best pipeline"

Two peer-reviewed EEG studies from 2025 changed how I think about preprocessing.

Kessler et al. (Communications Biology) found that every artifact-correction step they tested reduced decoding performance, while higher high-pass cutoffs increased it.

Huang et al. (Psychophysiology) compared 43 pipelines and concluded there is "no single best pipeline".

If the pipeline changes the result, the pipeline is part of the result. It should be versioned, recorded and comparable, not a hidden default.

That is what I'm building NeuroForge Bio around: versioned, comparable pipelines and neural-data governance, from electrode to model. Nothing to sell yet. I'm talking to teams first.

If you work with EEG, ECoG or microelectrode data and have opinions on this, I'd like to hear them.

Sources: doi:10.1038/s42003-025-08464-3 · doi:10.1111/psyp.70197

---

## Post 2: "One in five"

A 2026 systematic review of EEG-BCI resources (Peksa et al., Sensors) looked at 129 publications.

Data availability was stated in 61.2% of them. Code or pipeline availability: 20.9%.

So most of the time we can get the data but not the exact steps that turned it into a result.

The plan: open-source tooling (Apache-2.0 planned) that records provenance automatically on top of MNE, BIDS, NWB and LSL, so sharing the pipeline takes no extra effort.

What stops your team from publishing its pipelines? [OWNER: add one honest sentence from your own experience]

Source: doi:10.3390/s26175562

---

## Post 3: "Is this recording neural data? Depends on the state"

Four US states now treat neural data as sensitive data: Colorado (HB24-1058), California (SB 1223), Connecticut (Public Act 25-113, with its privacy-law amendments effective 1 July 2026) and Montana (SB 163, 2025, per a peer-reviewed review; I haven't reviewed the statute text yet).

The definitions don't match:
- Colorado: central or peripheral nervous system, processable by a device.
- California: central or peripheral, but excluding data inferred from non-neural information.
- Connecticut: central nervous system only.

On a plain reading, a peripheral signal like EMG could be covered in one state and not in another. Interpretation, not legal advice.

Classification has to happen per channel and per derived feature, in software. That's the governance half of what we're designing.

Sources: state legislature texts, summarised with citations on our law tracker [LINK TO LAW-TRACKER PAGE].
NOT LEGAL ADVICE.

---

## Post 4: "Emotion inference at work is banned in the EU"

Since 2 February 2025, Article 5(1)(f) of the EU AI Act prohibits AI systems that infer emotions of people in workplaces and education institutions, except for medical or safety reasons.

For neurotech this is concrete: a "cognitive state" or emotion model can't simply be deployed into those settings in the EU.

Our view: models trained on neural data should carry use-restriction metadata alongside their provenance, so the restriction travels with the model. It's in our design, not yet in a product.

Source: artificialintelligenceact.eu/article/5 · NOT LEGAL ADVICE.

---

## Post 5: "What we're building, and what we're not" (announcement; publish only when true)

[OWNER: publish only after the open-source release actually exists; replace bracketed items with real facts]

Today we [released / are opening early access to] [PACKAGE NAME], an open-source [validator / multiverse runner] for [MNE / BIDS / NWB] workflows. [One sentence on what it does, verified against the release.]

What it is: R&D software that records and compares preprocessing pipelines.
What it is not: a medical device, a diagnostic tool, or a compliance certificate.

Next on the roadmap: a consent and deletion ledger for neural data (planned), then documentation tooling for regulated work (roadmap).

We're looking for [3–5] design partners among [clinical-stage device teams / neurotech companies selling in CO, CA, CT or MT]. If that's you, [CONTACT PATH ON OUR SITE].

Repo: [URL]
