# First round: shared assumptions (CEO ↔ nfb-legal ↔ finance). ALL ESTIMATE, owner decides.

Owner-set 2026-09-26. Single source of truth for the contracts (legal\financing\) and investor\dilution.py.
If you change a number, change it HERE and tell the CEO agent.

## Terms
- The owner calls this round "Series A". At NOK ~1M it is a **pre-seed / angel round** ("første runde / pre-seed").
  Materials use: pre-seed (this round) → seed (next) → Series A (later). The owner's "Series B" warrant =
  a right to invest in the **next priced round (seed)**.
- **Currency: NOK.** The round is NOK 1,000,000. investor\financial-model.csv models a separate, larger
  USD 1.0M pre-seed plan; that is NOT this round. FX: finance takes USD/NOK from Norges Bank if opened
  (norges-bank.no exchange rates); otherwise 10.5 NOK/USD, labelled ESTIMATE/UNVERIFIED.

- **FINANCE: (nfb-finance-ba, 2026-09-26) FX = 9.5063 NOK per USD**, Norges Bank USD/NOK spot for 2026-09-25,
  https://data.norges-bank.no/api/data/EXR/B.USD.NOK.SP?format=csv&lastNObservations=1 (opened 2026-09-26). This
  replaces the 10.5 ESTIMATE everywhere. At this rate NOK 1M ≈ USD 105k and USD 4.0M ≈ NOK 38.0M.

## This round (grid adopted from nfb-legal-corporate)
- Amount: NOK 1,000,000.
- (a) Priced round, pre-money NOK 4 / 6 / 8 / 10 / 15 / 20M.
- (b) Convertible loan (konvertibelt lån): cap NOK 12M pre-money; 20% discount; converts at the next
  priced round; interest ESTIMATE 5%/yr accrued, converts with principal; maturity 24 months.
- (c) Shares + warrant (frittstående tegningsrett) on the next round at a fixed/capped price: base case priced
  at NOK 8M pre + warrant for up to NOK 1M more at a cap of NOK 20M pre-money, 24–36 months.
  LEGAL: numbers kept. asl §11-12 requires the GF resolution to state the NUMBER of warrants and a deadline ≤ 5 years.
  Because the price is "lower of seed price and cap", the drafts issue a MAXIMUM number of warrants (NOK 1M ÷ a floor
  price ≥ nominal value) usable only up to NOK 1M. Advokat to confirm. See legal\financing\warrant-terms.en.md §2.1.
- (d) Smaller stake + pro-rata right: e.g. NOK 500k at NOK 8–10M pre plus a pro-rata right in the next round.

## Runway
- **FINANCE: (2026-09-26)** NOK 1M ≈ USD 105k (Norges Bank FX above). Runway per financial-model.py pre-phase
  table (ESTIMATE): **lean** (founder + AI tools + ~0.1 FTE contractor) ≈ 18 months, ≈ 22 with grants;
  **small team** (founder + 0.5 FTE contractor) ≈ 8 months, ≈ 9 with grants. Grants = Innovation Norway
  oppstartstilskudd 1 (≤ NOK 150k) + SkatteFUNN 19 %; conditional on the AS existing and approval, not guaranteed.
- (original text) NOK 1M ≈ USD 95k (ESTIMATE FX). It funds about 6–9 months of the founder part-time/low salary, tooling,
  first cloud spend, an initial trademark clearance search and a first privacy-counsel review.
  It does NOT fund the year-1 plan in financial-model.py (USD ~0.64M burn). It is a bridge to discovery
  milestones (15–20 interviews, open-core SDK, 3–5 design partners), then the seed.

## Cap table
- Today: founder 100% (assumed; the owner confirms there are no other holders).
- Option pool: none before this round. A 10% pool is created pre-money at the next (seed) round (ESTIMATE, typical).
- Next round, modelled two ways (ESTIMATE):
  - N1 small Norwegian seed: NOK 10M at NOK 40M pre-money.
  - N2 financial-model seed: USD 4.0M (≈NOK 42M) at NOK 120M pre-money.
    **FINANCE: (2026-09-26)** ≈ NOK 38.0M at the Norges Bank rate. financial-model.py now runs the rounds IN SEQUENCE:
    NOK 1M pre-seed (month 1) → N1 NOK 10M @ 40M pre (base month 9; must close by month 9–10) → N2 USD 4.0M @ NOK 120M
    pre (base month 20; must close by month 21) → Series A USD 12M (base month 40). ESTIMATE.
  - Plus sensitivity pre-money NOK 10 / 20 / 40M from legal's grid (down/flat-round stress).
