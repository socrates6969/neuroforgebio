# /investors: claim sources

Owner: web-investor-2. Rewritten 2026-09-27 after re-verifying every claim on the page. This replaces the
earlier mapping, which cited `investor/PITCH.md` (a draft pitch, not an allowed evidence source) and graded
internal plans as "A".

How the page tags evidence:
- **Facts about the world** go in each section's `evidence` list, with `source` = `market/<file>.md §N` (the
  only form the content tests accept) and the grade from that document (A = peer-reviewed or primary law,
  B = reputable secondary, B- = tertiary such as Wikipedia, D = company marketing).
- **Things we built** carry `buildState: built-internal` plus `buildSource: docs/hive/M*-REPORT.md step N`
  (checked by the content test `buildSource`). "Built" means built and tested locally; nothing is deployed.
- **Plans** carry a `status` pill (planned / designed / roadmap). Plan text comes from `investor/PITCH.md`
  Slides 4, 8 and 10 and `market/pricing-and-gtm.md` §5; it is labelled as a plan on the page.

Page-level facts: banner "Pre-release. Not deployed. No customers yet." (PITCH.md "Read this first"; M2 to M6
reports: "Nothing deployed"). noindex via `<Base noindex>`; not in `sitemapRoutes()` (apps/web/src/lib/site.ts),
so it is in neither sitemap; not linked from `/` or the nav.

## Evidence rows (facts)

| Section | Claim on page | Source | Grade | Checked against |
|---|---|---|---|---|
| hero | State neural-data laws are in force | market/regulation.md §1 | A | CO effective 7 Aug 2024; CA chaptered 28 Sep 2024; CT CTDPA sections effective 1 Jul 2026 (today 2026-09-27) |
| hero + problem evidence | None of the 22 neural-data tools and services reviewed offers neural-specific consent, deletion and audit | market/landscape.md §3 item 4 (the 22 rows of §2) | none given (our own review; the listed tools carry their own B/D sources) | "No neural-specific privacy tooling was found among the tools above. Every open tool lacks consent, deletion and audit features." Evidence row added 2026-09-27 (review finding F1) |
| problem | Artifact correction and filters change decoding | market/landscape.md §3 item 2 | A | Kessler et al. 2025 |
| problem | No single best pipeline among 43 | market/landscape.md §3 item 2 | A | Huang et al. 2025 |
| problem | 20.9% of 129 EEG-BCI papers shared code | market/landscape.md §3 item 1 | A | Peksa et al. 2026 |
| problem | CO/CA vs CT definitions; CA excludes inferred data | market/regulation.md §1 | A | statute text quoted there |
| problem | FDA implanted BCI guidance: Enhanced Documentation Level | market/regulation.md §4 | A | fda.gov/media/120362 |
| regulatory | CO, CA, CT dates | market/regulation.md §1 | A | |
| regulatory | Montana SB 163 (May 2025) | market/regulation.md §1 | A (secondary to statute) | statute text not opened; page says "a peer-reviewed review reports" |
| regulatory | MIND Act introduced Sep 2025 | market/regulation.md §2 | A | bill number/status not verified; page says so |
| regulatory | EU AI Act 5(1)(f) | market/regulation.md §5 | B | |
| regulatory | Precision 510(k) Apr 2025; Paradromics IDE Nov 2025 | market/landscape.md §1 | B- | both Wikipedia-sourced; grade shown on page |
| regulatory | $1.2B VC to neurotech devices in 2024, more than any other device type | market/sizing.md §1 | A | Sci Adv 2026 citing HSBC |

## Build rows (built and tested internally, not deployed)

| Item | buildSource | What the step shows |
|---|---|---|
| Open Core SDK | M4 step 4.2–4.3 | SDK vectors and published snippet run; not uploaded to any index |
| Multiverse audit | M3 step 3.6 | sweep with a planted effect; the public-data study (3.9) is a scaffold only, and the page says it has not been run |
| Consent & Deletion Ledger | M5 step 5.5 | withdrawal crypto-shreds, re-runs derivatives, flags the model, signed certificate |
| FDA Evidence Kit | M5 step 5.8 | v0 zip labelled "scaffold, not a submission" |
| Governed model registry | M6 step 6.2 | emotion model in EU workplace/education refused |
| Crypto-shredding | M2 step 2.3 | primary and backup copy unreadable, other subjects fine |
| Tamper-evident lineage | M3 step 3.1 | node/edge/batch tampering fails verification |
| Consent check on every data route | M5 step 5.4 | route enumeration; training without scope denied |
| Neural-law rules / law tracker | M5 step 5.6 | /law-tracker generated from `rules/*.yaml`; unverified rules shown as unverified |

## Plans (status pills, no evidence claimed)

| Item | Source |
|---|---|
| Lineage graph with products on it; product descriptions | investor/PITCH.md Slide 4 |
| Moat items; "None is established yet" | investor/PITCH.md Slide 10 ("All four are plans. None exists yet.") |
| Go-to-market sequence (SDK + study, then ledger + startup tier + design partners, then FDA kit + first pharma pilot) | investor/PITCH.md Slide 8; market/pricing-and-gtm.md §5 |

## Demos section

| Claim | Source |
|---|---|
| Playground is an offline demo on open monkey motor-cortex data, not the platform's evaluation engine | packages/content/content/pages/playground.json banner ("Offline replay of a past recording") |
| Decoder Arena is in development | main f14c44c "stub until CI-built pkg". No indexing statement: the page drops noindex once the CI-built pkg is present (`noindex={!wasmAvailable}`), so "not indexed" was time-bound and was removed (finding F2) |
| Law tracker generated at build time from rule files | M5 step 5.6 |

## Removed from the previous version (unsourced or overstated)

- "Leak-proof" / "Leak-checked evaluation" feature card: the cited `PLATFORM_FEATURES.md` describes designs, and no leak-control test was cited for the platform. Removed.
- "tested" claim for the playground and the `playground.test.mjs` reference: dropped; the page makes no test claim.
- "C ABI ... for low-latency inference in implanted devices": no M-report step, and M6 step 6.5 states the stack is "not intended for real-time or safety-critical control". Removed.
- "Record levels" of VC: not in the source. Replaced by the sourced "more than any other type of medical device".
- "Four US states have moved neural data into protected categories": Montana is secondary-sourced only; now worded as such.
- "Counsel-reviewed" rules: counsel review is pending. Now says so.
- "Latency harness" in the FDA kit: not built; removed.
- "Out-of-the-Shelf (OTS)": wrong term; now "off-the-shelf software".
- `docs/web/investor-claims.md`: deleted; it cited PITCH.md as primary for facts that live in market/.
