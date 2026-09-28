# NeuroForge Bio: business-pack task board (STEP 4)

Queen: CEO agent. Workers report to the queen and may message each other by name with SendMessage.
Update your own rows only (status + one-line note). Statuses: TODO / DOING / DONE / BLOCKED.

## Shared rules (from BRIEF.md; apply to every file)
- Cite only sources actually opened: files in `market\` (quote the file + section) or URLs you open. Grade A–D (A peer-reviewed/primary law, B reputable press/tertiary, C preprint/theory, D company marketing).
- Every derived or assumed number says **ESTIMATE** plus its method. All prices say ESTIMATE until validated in customer discovery.
- Never invent customers, LOIs, quotes, traction, partnerships, team members or results. Traction = "pre-product".
- Team = owner Marius Carlsson + hiring plan. AI agents are not team members and are never presented as people.
- No medical claims. Product = non-device research & development software (market\regulation.md §4).
- Name: NeuroForge Bio. Trademark clearance pending (market\names.md; Neuroforge GmbH & Co. KG exists in Germany).
- Status language: designed / planned / roadmap. Never "live", "built-in", "certified", "HIPAA-compliant", "SOC 2".
- Never publish, send, post, sign up, spend or contact anyone. No git. Absolute paths, never cd.
- Python: C:\Users\mariu\AppData\Local\Programs\Python\Python312\python.exe (stdlib; numpy only if needed).

## Key inputs
- Positioning (DECISIONS.md D1): "Versioned, comparable pipelines and neural-data governance, from electrode to model."
- Product order: open-core SDK + validator + multiverse audit (m0–3) -> Consent & Deletion Ledger (m3–9) -> FDA Evidence Kit + latency harness (m9–18) -> governed model registry (on pull) (market\pricing-and-gtm.md §5; new-ideas.md top 5).
- Sizing: SAM ESTIMATE $10M–$86M ARR; SOM yr3 after launch ~$2.4M ARR, 108 logos (market\sizing.md §3). TAM $0.1B–$1.1B (top-down, not decision-grade).
- Costs: BLUEPRINT.md §12 (infra bands, ~40 person-months M0–M7; no salary data sourced).

## Shared marketing budget (set by queen; both marketing plan and financial model use it)
Non-people marketing programme spend, base case, ESTIMATE (method: small-B2B-SaaS judgement anchored on the channel list in
pricing-and-gtm.md §4; no booth/sponsorship prices were opened; owner approves every spend):
Y1 $40k (band $25k–$60k) · Y2 $100k ($60k–$150k) · Y3 $200k ($120k–$300k) · Y4 $350k ($200k–$500k) · Y5 $500k ($300k–$750k).
Bear = low end of band, bull = high end. Marketing headcount is in the financial model, not in this line.

## Tasks
| # | Deliverable | Owner | Status | Note |
|---|---|---|---|---|
| 1 | investor\PITCH.md | queen | DONE | 15 slides, pre-product traction, founder + hiring plan, ask = pre-seed $1.0M ESTIMATE |
| 1b | investor\pitch-deck.html | nfb-pitch-designer | DONE | Rev 2: 17 slides matching revised PITCH.md (new 11 Trust & security "not audited or certified", 12 data asset PROVISIONAL/not legal advice, roadmap Y8–15 biotech arm = Scenario, Financials data-upside bullet, 17 ask = NOK 1M pre-seed @ NOK 10M pre + founder-% SVG bar chart ESTIMATE; old $1.0M use-of-funds table removed); clinical palette, Google Fonts only; tags balanced, JS node --check OK, no ext URLs, print = 17 pages. **Sync 2026-09-26 (pitch sync worker):** slides 7/12/14/16/17 re-synced to corrected PITCH.md (GM 52→74 %; data upside $3.46/4.14/5.74M vs $3.34M, cash $7.1/8.2/10.3M; hiring 4/12/13/25/33, none before seed; new base table + year-end cash row; ARR SVG 0.00/0.28/1.15/2.28/3.63, bear 1.15/bull 7.00; ownership SVG 90.9/63.6/48.3/36.2; new runway bars lean 18/22 vs small team 8/9 mo; grants conditional; NOK 1M ≈ USD 105k @ 9.5063 Norges Bank); tags balanced, JS OK, no ext URLs, 17 slides, headless render checked, stale-number grep clean |
| 2 | investor\PRICING.md | nfb-finance-ba | DONE | 6 tiers (all ESTIMATE), comparables graded D, design-partner offer, 8 discovery hypotheses (owner-run), 7 risks |
| 3 | investor\SCALING-PLAN.md | queen (numbers from nfb-finance-ba) | DONE | Y1–5 from model; Y6–15 SCENARIO bear/base/bull, named growth + ARR/employee assumptions; no exit multiples (unsourced) |
| 4 | investor\financial-model.py + .csv | nfb-finance-ba | DONE | SUPERSEDED by row 10 (corrected funding path). Old: base Y5 ARR $4.54M, 34 heads, burn $3.25M; SOM hit ~month 45 ($2.66M); bear shows $2.8M funding gap; salary = BLS May 2025 median $135,980 |
| 5 | marketing\MARKETING-PLAN.md | nfb-marketing | DONE | D1 positioning, 5 graded pillars, banned-claims list, 6 ICPs + 2 partner types, M0–M12 calendar (BCI Soc 7–10 Jun 2027; SfN dates unverified), Y1 $40k budget in 10 ESTIMATE lines (no prices opened), tracker-free KPIs, 15–20 owner-run interviews; DP/ARR KPIs aligned to financial model |
| 6 | marketing\templates\ (7 drafts) | nfb-marketing | DONE | 7 drafts + one-pager.html (clinical palette, Google Fonts only; self-host per D9 before public use); all headed DRAFT, placeholders, no quotes/customers; MT flagged "statute text not yet reviewed" |
| 7 | investor\FUNDING-ROUND.md + dilution.py (+ dilution.csv) | nfb-finance-ba | DONE | NOK 1M = pre-seed/angel; 10 scenarios × 5 next rounds, 10 % pool pre-money at seed; REC priced NOK 1M @ NOK 10M pre + pro-rata: owner 90.91 % → 63.64 % (N1) / 59.94 % (N2); sequential N1→N2 48.33 %; FX 9.5063 Norges Bank 2026-09-25 (rev 2026-09-26); 4 mismatches vs legal listed in §10 |
| 8 | investor\DATA-REVENUE-STRATEGY.md | nfb-data-strategy | DONE | 15 models + 3 rejected (insurer/employer, data sale, ads/LE); top5 A1 compute-to-data, A12+A2 pharma analytics/clean rooms, A8+A15 attestation/toolkit, A7 benchmarks, A11 grants; upside Y5 $128k/$800k/$2.4M; 3 new consent scopes; all risk ratings PROVISIONAL (nfb-legal-privacy unreachable; questions in DATA-STRATEGY-QUESTIONS-FOR-PRIVACY.md, forwarded via nfb-legal, receipt confirmed; ratings pending) |
| 9 | investor\PITCH.no.md + pitch-deck.no.html | nfb-pitch-no | DONE | Bokmål, all 17 slides from PITCH.md, no new claims; Norwegian number format (USD/NOK kept); ESTIMAT/PROVISORISK/før produkt kept; SVG: TAM/SAM/SOM, ARR Y1–Y5 + bear/bull, founder-ownership bars (ESTIMAT); tags balanced, JS node --check OK, only Google Fonts external; links to English deck. **Sync 2026-09-26 (pitch sync worker):** PITCH.no.md + pitch-deck.no.html slides 7/12/14/16/17 brought in line with corrected PITCH.md (same numbers as row 1b, decimal comma; ESTIMAT kept; "Marius Carlsson"); runway bars added; tags balanced, JS OK, only Google Fonts external, 17 slides, stale-number grep clean |
| 10 | financial-model.py rework (NOK 1M first round, cash-gated hiring, lean scenario, grants) + prephase-runway.csv; dilution.py/FUNDING-ROUND.md §7a; ROUND-ASSUMPTIONS FINANCE edits | nfb-finance-ba | DONE | FX 9.5063 NOK/USD (Norges Bank 2026-09-25); NOK 1M lasts lean 18 mo (22 w/ grants), small team 8 mo (9 w/ grants); base: seed N1 NOK 10M by m9–10, N2 USD 4.0M by m21, Series A m40; Y5 ARR $3.63M / cash $7.03M; bear $1.15M / gap -$1.25M; bull $7.00M / $13.61M; PITCH/deck ARR figures ($4.54M) now stale |
