# Perf report 2: budget headroom after report 23 (web-perf, 2026-09-27)

Measured on web/integration 81f533e. Both themes were built in bci-queen's lane B, taking 10.6 s at 600 MB peak commit. The measurements come from `tools/web/perf-audit.mjs`. No budget was changed.

- **Effective budget:** `tools/web/perf-budgets.json` plus `tools/web/perf-budget-adjustments.json`. The adjustments file is empty, so the effective budget is the generated one.
- **Units:** sizes are bytes, gzip -9, unless the metric is `htmlRaw`, `imageBytes` or `requests`.
- **Cells:** each cell is `measured / budget (headroom %)`.
- **Routes without their own budget:** /arena/, /docs/c-abi/ and /docs/python-sdk/ have no page budget yet. They fall back to `"*"`, the theme's largest inner page +10%. That fallback is loose, so these three should get page budgets at the next regeneration from main.

## Table

| /arena/ | clinical | "*" (new page) | 575 / 9108 (94%) | 0 / 142354 (100%) | 4380 / 9118 (52%) | 0 / 1024 (100%) | 0 / 154690 (100%) | 9986 / 190754 (95%) | 108417 / 134496 (19%) | 13 / 25 (48%) |
| /docs/ | clinical | page | 575 / 1599 (64%) | 0 / 1024 (100%) | 4037 / 5032 (20%) | 0 / 1024 (100%) | 0 / 1024 (100%) | 13251 / 13455 (2%) | 108483 / 118970 (9%) | 13 / 15 (13%) |
| /docs/api/ | clinical | page | 575 / 1599 (64%) | 0 / 1024 (100%) | 4024 / 5048 (20%) | 0 / 1024 (100%) | 0 / 1024 (100%) | 173789 / 190754 (9%) | 121625 / 133679 (9%) | 12 / 14 (14%) |
| /docs/c-abi/ | clinical | "*" (new page) | 575 / 9108 (94%) | 0 / 142354 (100%) | 4029 / 9118 (56%) | 0 / 1024 (100%) | 0 / 154690 (100%) | 16464 / 190754 (91%) | 109568 / 134496 (19%) | 13 / 25 (48%) |
| /docs/changelog/ | clinical | page | 575 / 1599 (64%) | 0 / 1024 (100%) | 3799 / 4823 (21%) | 0 / 1024 (100%) | 0 / 1024 (100%) | 9629 / 10221 (6%) | 107486 / 118115 (9%) | 12 / 14 (14%) |
| /docs/python-sdk/ | clinical | "*" (new page) | 575 / 9108 (94%) | 0 / 142354 (100%) | 4029 / 9118 (56%) | 0 / 1024 (100%) | 0 / 154690 (100%) | 37785 / 190754 (80%) | 112018 / 134496 (17%) | 13 / 25 (48%) |
| /docs/quickstart/file-ingest/ | clinical | page | 575 / 1599 (64%) | 0 / 1024 (100%) | 3973 / 4968 (20%) | 0 / 1024 (100%) | 0 / 1024 (100%) | 11505 / 12129 (5%) | 108079 / 118739 (9%) | 13 / 15 (13%) |
| /docs/quickstart/lineage-export/ | clinical | page | 575 / 1599 (64%) | 0 / 1024 (100%) | 3973 / 4968 (20%) | 0 / 1024 (100%) | 0 / 1024 (100%) | 11353 / 11942 (5%) | 108047 / 118707 (9%) | 13 / 15 (13%) |
| /docs/quickstart/pipeline-run/ | clinical | page | 575 / 1599 (64%) | 0 / 1024 (100%) | 3973 / 4968 (20%) | 0 / 1024 (100%) | 0 / 1024 (100%) | 10694 / 11235 (5%) | 107836 / 118466 (9%) | 13 / 15 (13%) |
| /docs/quickstart/streaming/ | clinical | page | 575 / 1599 (64%) | 0 / 1024 (100%) | 3973 / 4968 (20%) | 0 / 1024 (100%) | 0 / 1024 (100%) | 12157 / 12846 (5%) | 108353 / 119037 (9%) | 13 / 15 (13%) |
| /interface/ | clinical | page | 7721 / 8244 (6%) | 129439 / 142354 (9%) | 4737 / 5723 (17%) | 0 / 1024 (100%) | 140627 / 154690 (9%) | 26106 / 27329 (4%) | 118729 / 129671 (8%) | 16 / 17 (6%) |
| /playground/ | clinical | page | 8521 / 9108 (6%) | 0 / 1024 (100%) | 5216 / 6240 (16%) | 0 / 1024 (100%) | 140627 / 154690 (9%) | 33329 / 35282 (6%) | 121209 / 132542 (9%) | 16 / 17 (6%) |
| /arena/ | cosmos | "*" (new page) | 575 / 9108 (94%) | 0 / 145690 (100%) | 4571 / 9897 (54%) | 0 / 1024 (100%) | 0 / 154690 (100%) | 10145 / 190929 (95%) | 150185 / 184406 (19%) | 15 / 28 (46%) |
| /docs/ | cosmos | page | 575 / 1599 (64%) | 0 / 1024 (100%) | 4228 / 5223 (19%) | 0 / 1024 (100%) | 0 / 1024 (100%) | 13410 / 13630 (2%) | 150254 / 164921 (9%) | 15 / 17 (12%) |
| /docs/api/ | cosmos | page | 575 / 1599 (64%) | 0 / 1024 (100%) | 4215 / 5239 (20%) | 0 / 1024 (100%) | 0 / 1024 (100%) | 173948 / 190929 (9%) | 163490 / 179728 (9%) | 14 / 16 (13%) |
| /docs/c-abi/ | cosmos | "*" (new page) | 575 / 9108 (94%) | 0 / 145690 (100%) | 4220 / 9897 (57%) | 0 / 1024 (100%) | 0 / 154690 (100%) | 16623 / 190929 (91%) | 151338 / 184406 (18%) | 15 / 28 (46%) |
| /docs/changelog/ | cosmos | page | 575 / 1599 (64%) | 0 / 1024 (100%) | 3990 / 5014 (20%) | 0 / 1024 (100%) | 0 / 1024 (100%) | 9788 / 10380 (6%) | 149258 / 164061 (9%) | 14 / 16 (13%) |
| /docs/python-sdk/ | cosmos | "*" (new page) | 575 / 9108 (94%) | 0 / 145690 (100%) | 4220 / 9897 (57%) | 0 / 1024 (100%) | 0 / 154690 (100%) | 37944 / 190929 (80%) | 153880 / 184406 (17%) | 15 / 28 (46%) |
| /docs/quickstart/file-ingest/ | cosmos | page | 575 / 1599 (64%) | 0 / 1024 (100%) | 4164 / 5159 (19%) | 0 / 1024 (100%) | 0 / 1024 (100%) | 11664 / 12304 (5%) | 149845 / 164680 (9%) | 15 / 17 (12%) |
| /docs/quickstart/lineage-export/ | cosmos | page | 575 / 1599 (64%) | 0 / 1024 (100%) | 4164 / 5159 (19%) | 0 / 1024 (100%) | 0 / 1024 (100%) | 11512 / 12117 (5%) | 149814 / 164650 (9%) | 15 / 17 (12%) |
| /docs/quickstart/pipeline-run/ | cosmos | page | 575 / 1599 (64%) | 0 / 1024 (100%) | 4164 / 5159 (19%) | 0 / 1024 (100%) | 0 / 1024 (100%) | 10853 / 11408 (5%) | 149605 / 164413 (9%) | 15 / 17 (12%) |
| /docs/quickstart/streaming/ | cosmos | page | 575 / 1599 (64%) | 0 / 1024 (100%) | 4164 / 5159 (19%) | 0 / 1024 (100%) | 0 / 1024 (100%) | 12316 / 13021 (5%) | 150120 / 164982 (9%) | 15 / 17 (12%) |
| /interface/ | cosmos | page | 7936 / 8457 (6%) | 132469 / 145690 (9%) | 4928 / 5914 (17%) | 0 / 1024 (100%) | 140627 / 154690 (9%) | 26253 / 27491 (5%) | 160716 / 175850 (9%) | 19 / 20 (5%) |
| /playground/ | cosmos | page | 8521 / 9108 (6%) | 0 / 1024 (100%) | 5407 / 6431 (16%) | 0 / 1024 (100%) | 140627 / 154690 (9%) | 33476 / 35444 (6%) | 162980 / 178485 (9%) | 18 / 19 (5%) |

## Flags

**How to read "within 10%":** budgets are the value at generation +10%. A page that has not changed since then therefore sits at 9.09% headroom by construction. Most of the flags under 10% are exactly that. None of those pages grew.

| Route (both themes) | Metric | Headroom | Growth since budgets were set | Cause |
|---|---|---|---|---|
| /docs/ | htmlRaw | **1.5% / 1.6% (204 / 220 B)** | ≈ +1,019 B (+8.2%) | JSON-LD + overview links (web-docs). A measured adjustment is pending in the process agreed with web-queen. |
| /interface/ | htmlRaw | 4.5% (1,223 / 1,238 B) | ≈ +1,261 B (+5%) | web-seo T5b JSON-LD: 1,253 B measured on f4a160e |
| /playground/ | htmlRaw | 5.5% (1,953 / 1,968 B) | ≈ +1,254 B (+3.9%) | web-seo T5b JSON-LD: 1,246 B |
| /docs/quickstart/* | htmlRaw | 4.8–5.4% | ≈ +480 B (+4.3%) | docs JSON-LD / DocSections |
| /docs/changelog/ | htmlRaw | 5.7–5.8% | ≈ +340 B (+3.6%) | same |
| /interface/, /playground/ | jsInitialGzip | 6.2–6.4% (≈ 520–590 B) | ≈ +3% | page script growth, fallback logic |
| /interface/, /playground/ | requests | 1 request | +0 | the +1 floor on a count, not growth |

- **Nearest to its budget:** /docs/ htmlRaw. One more ~200 B addition fails it.
- **Other growth:** everything else that grew still has at least 4.5% left.
- **Totals:** total page weight (fonts dominate) is unchanged at 8.4–9.1%.
- **Growth figures are approximate:** "≈" means the value at budget time was back-computed as budget / 1.1. The +1 KB / +1 floors make it approximate.

## Pending effect: compact replay asset (nfb-playground f9b6667, not in 81f533e)

I built f9b6667 read-only in the same slot (792 MB). The built hashed `mc-rtt-playground.*.json` is byte-identical to the source asset: 286,556 B raw, sha256 9e0718ec…, gzip -9 105,739 B (node zlib).

It replaces the 140,627 B that /interface/ and /playground/ fetch today, so dataGzip headroom goes from 9% to about 32% on both. Decode cost, measured over 20 runs in node: `expandCompact` median 2.4 ms (max 5.1 ms), and parse + expand + validate median 7.0 ms. Page weight excluding data is unchanged.

## Recommendations (no budget raised here)

1. **/docs/:** web-docs trims first. Any remainder becomes a measured `perf-budget-adjustments.json` entry, per the lead's rule.
2. **Next regeneration from main:** after the compact asset, T5b and the docs changes land, regenerate from main. That gives /arena/, /docs/c-abi/ and /docs/python-sdk/ real page budgets. It also moves the dataGzip budgets for /interface/ and /playground/ down to about 116 KB.
