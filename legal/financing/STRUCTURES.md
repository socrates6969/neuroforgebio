> DRAFT – not legal advice. Must be reviewed by a Norwegian lawyer (advokat) before use.

# NeuroForge Bio: structures for the first external round (NOK 1,000,000)

Version: [dato/date] · Author: nfb-legal-corporate (AI draft for Marius Carlsson) · Status: DRAFT TEMPLATE, rev. 2 (reconciled with ROUND-ASSUMPTIONS)

**ASSUMPTION (flag):** NeuroForge Bio will be a Norwegian aksjeselskap (AS) under aksjeloven (lov 13. juni 1997 nr. 44).
It is **not yet incorporated**. Company name, org.nr., share capital, number of shares, nominal value and vedtekter are
placeholders: [SELSKAP AS], [org.nr.], [aksjekapital NOK ___], [antall aksjer], [pålydende NOK ___]. The minimum share
capital is NOK 30,000 (asl §3-1, verified).

**Single source of truth for numbers:** `C:\Users\mariu\neuro-company\investor\ROUND-ASSUMPTIONS.md` (CEO + finance +
legal). If a number here differs from that file, the file wins, unless a "LEGAL:" note there says otherwise.
**Language:** English is the working text of this memo; the Norwegian summary is at the end. For the corporate documents
(GF-protokoll, vedtekter, tegningsvilkår), the Norwegian version prevails (choice for the advokat).

---

## 0. Terminology (a polite correction)

The owner calls this round "Series A" and the next one "Series B". **NOK 1M from one first investor is a pre-seed /
angel round.** "Series A" normally means a larger, institutional round led by a venture fund (ESTIMATE; no source
opened). All documents use: **pre-seed (this round) → seed (next round; the owner's "Series B") → Series A (later).**
The owner's "Series B warrant" means a right to invest in the next priced round (the seed).

**Currency:** the round is **NOK 1,000,000**. The USD 1.0M in `investor\financial-model.csv` is a separate, larger plan
and is **not** this round (ROUND-ASSUMPTIONS "Terms"). FX: **9.5063 NOK/USD** (Norges Bank spot 2026-09-25, per the
'FINANCE:' note in ROUND-ASSUMPTIONS; not opened by legal). NOK 1M ≈ USD 105k; USD 4.0M ≈ NOK 38.0M.

## 1. Coordination status

- ROUND-ASSUMPTIONS.md (owner-set 2026-09-26) adopts the legal grid: pre-money NOK 4/6/8/10/15/20M; convertible cap NOK
  12M, 20 % discount, 5 % interest, 24-month maturity; no option pool now, and a **10 % pool created pre-money at the
  seed**; seed N1 = NOK 10M at NOK 40M pre-money, N2 = USD 4.0M (≈ NOK 38.0M) at NOK 120M pre-money, plus stress
  pre-money NOK 10/20/40M (NOK 10M raised).
- Runway (ROUND-ASSUMPTIONS 'FINANCE:' note, ESTIMATE): NOK 1M ≈ USD 105k. It lasts about **18 months lean** (≈ 22 with
  grants) or **8 months with a small team** (≈ 9 with grants). It is a bridge to discovery milestones, then the seed.
- **Rounds in sequence** (financial-model.py): pre-seed → N1 (base month 9) → N2 (base month 20) → Series A USD 12M
  (base month 40). The N1/N2 columns below show each seed **on its own**; the PATH table in §4 shows the sequence.
- **Cross-check:** `legal\financing\dilution.py` reads the same inputs and compares itself with
  `investor\dilution.csv` (nfb-finance-ba). Result (re-run after the FINANCE edits): **50 scenarios, 0 mismatches**
  (owner % after the next round), and the **PATH table: 5 structures × 4 stages, 0 differences > 0.01 pp**.
- Letters follow ROUND-ASSUMPTIONS: **(a) priced, (b) convertible, (c) shares + warrant, (d) smaller stake + pro-rata.**
  The SAFE-style variant is shown as **(s)**; it is not in ROUND-ASSUMPTIONS. rev. 1 of this memo used (d) = warrant and
  (e) = pro-rata; those labels are withdrawn.

## 2. Valuation grid: ESTIMATE, UNVERIFIED

No public Norwegian or Nordic pre-seed valuation dataset could be opened. innovasjonnorge.no loaded but had no valuation
data. Method: angel investors commonly take about 10–20 % for a first ticket (judgement, UNVERIFIED), which gives a
pre-money of about NOK 4–9M for NOK 1M. The grid brackets that range.

**Pool convention (as ROUND-ASSUMPTIONS: "created pre-money"):** the pool is 10 % of the fully diluted capital
**after** the seed, and its shares count in the seed pre-money. Only existing holders (founder, pre-seed investor,
converted lender, warrant holder) are diluted by it; seed investors are not. Formula: owner % after seed = owner % before
× (V/(V+X) − 0.10). Example: 90.91 % × (40/50 − 0.10) = **63.64 %** (N1 alone); 90.91 % × (120/158.0 − 0.10) = **59.94 %** (N2 alone).
In sequence, N2 has no new pool: 63.64 % × 120/158.0 = **48.33 %** (exact 48.32 %; finance's table chains rounded
values), then × 36/48 = **36.24 %** after the Series A.

## 3. Side-by-side comparison

| | (a) Rettet emisjon (priced) | (b) Konvertibelt lån (asl kap. 11) | (c) Shares + frittstående tegningsrett (§11-12) | (d) Smaller stake + pro-rata right | (s) SAFE-style agreement |
|---|---|---|---|---|---|
| Owner dilution now | Fixed: 1M/(pre+1M); 9.09 % at NOK 10M pre | None until conversion | Same as (a) at NOK 8M (11.11 %), **plus hidden dilution** when the warrant is exercised | 500k/(pre+500k): 4.76–5.88 % | None until conversion |
| Owner dilution later | Seed + pool only | Set by cap/discount; **a low cap or weak seed can cost more than a priced round** | +2.7 to 4.4 pp at the seed (§4c) | Seed + pool only (pro-rata taken inside the seed) | As (b), without interest |
| Investor protection | Shareholder from day 1; SHA rights | Creditor until conversion; conversion right registered | Shares + an option on the upside at a capped price | Shareholder + contractual pro-rata right | Weak: a contract claim only; no statutory right to shares |
| Complexity / cost | Low–medium: GF resolution, subscription, payment confirmation, Foretaksregisteret | Medium: §11-2 resolution, registration §11-6, conversion registration §11-7 | Medium–high: §11-12 resolution (9 items), term ≤ 5 years, registration | Low: as (a) + one SHA clause | Looks simple but is legally messy: conversion later needs a GF resolution, a pre-emption waiver and possibly a §2-6 statement confirmed by a revisor |
| Norwegian legal basis | asl §§10-1, 10-3, 10-4, 10-5, 10-7, 10-9 | asl §§11-1, 11-2, 11-4, 11-6, 11-7, 11-8 | asl §§11-12, 11-13 | asl kap. 10 + contract (SHA) | **No statutory instrument**; implemented via kap. 11 or an advance subscription |
| Tax / registration notes (UNVERIFIED unless stated) | Payment confirmed by a revisor or, for cash, a finansforetak, advokat or statsautorisert regnskapsfører (§10-9, verified); report within 3 months (§10-9, verified); Brreg fee UNVERIFIED | Interest is a cost for the company and income for the lender (UNVERIFIED); conversion by set-off (§11-1, verified) | Tax on exercise and premium UNVERIFIED | As (a) | Tax treatment uncertain (UNVERIFIED) |
| Attractiveness to an investor | High: a clear % | High: downside protection + upside | High for the investor, costly for the owner | Medium: smaller ticket, but the pro-rata right is valued | Low–medium with Norwegian angels (UNVERIFIED) |

**SAFE under Norwegian law.** The Y Combinator SAFE is a US-law instrument (ycombinator.com was not opened; not an
allowed source). Aksjeloven has no SAFE concept. The kap. 11 instruments (konvertible lån, tegningsrettsaksjer,
frittstående tegningsretter, lån med særlige vilkår) are the statutory forms for rights to new shares. In practice
(UNVERIFIED), a SAFE-type deal would be done as one of:
1. a zero-interest kap. 11 convertible loan;
2. an advance subscription, where money is not share capital until a GF resolution and registration, and set-off needs
   the §10-2/§2-6 revisor-confirmed statement;
3. a §11-12 warrant.
**Not recommended.**

## 4. Dilution tables (all ESTIMATE; generated by dilution.py; identical to investor\dilution.csv)

Seeds: **N1** NOK 10M @ NOK 40M pre · **N2** NOK 38.0M (USD 4.0M) @ NOK 120M pre · **S10/S20/S40** NOK 10M @ NOK 10/20/40M
pre. The 10 % pool is created pre-money at the seed in all cases.

### (a) Priced rettet emisjon, NOK 1M
| Pre-money | Post-money | Investor % | Owner % after pre-seed | Owner % after N1 | Owner % after N2 |
|---|---|---|---|---|---|
| NOK 4M | NOK 5M | 20.00 % | 80.00 % | 56.00 % | 52.75 % |
| NOK 6M | NOK 7M | 14.29 % | 85.71 % | 60.00 % | 56.52 % |
| NOK 8M | NOK 9M | 11.11 % | 88.89 % | 62.22 % | 58.61 % |
| **NOK 10M** | **NOK 11M** | **9.09 %** | **90.91 %** | **63.64 %** | **59.94 %** |
| NOK 15M | NOK 16M | 6.25 % | 93.75 % | 65.63 % | 61.82 % |
| NOK 20M | NOK 21M | 4.76 % | 95.24 % | 66.67 % | 62.80 % |
Stress, owner % after the seed with (a) at NOK 10M pre: S10 36.36 %, S20 51.52 %, S40 63.64 %.

### (b) Konvertibelt lån: NOK 1M, 5 % simple interest × 24 months (the maturity) = **NOK 1,100,000 converts**; cap NOK 12M pre-money; 20 % discount
The cap price is based on the shares before the seed, excluding the new pool. The seed pre-money includes the conversion
shares.
| Seed | Price used | Lender % before seed | Owner % after seed | Lender % after seed |
|---|---|---|---|---|
| N1 | cap | 8.40 % | 64.12 % | 5.88 % |
| N2 | cap | 8.40 % | 60.40 % | 5.54 % |
| S10 | discount | 17.19 % | 33.13 % | 6.88 % |
| S20 | cap | 8.40 % | 51.91 % | 4.76 % |
| S40 | cap | 8.40 % | 64.12 % | 5.88 % |
Compared with (a) at NOK 10M (owner 63.64 % N1 / 59.94 % N2 / 36.36 % S10 / 51.52 % S20), the convertible is
slightly better for the owner if the seed is strong (+0.4–0.5 pp). It is **much worse if the seed is weak** (S10:
33.13 % vs 36.36 %). Interest at 24 months adds 10 % more conversion shares. At maturity without a seed, the template
converts at the cap (8.40 %; ≈ a priced round at NOK 12M pre-money plus interest).

### (s) SAFE-style for comparison (no interest, pre-money cap NOK 12M, 20 % discount)
Owner % after seed: N1 64.62 %, N2 59.15 %, S10 33.75 %, S20 52.31 %.

### (c) Shares at NOK 8M pre + frittstående tegningsrett for **up to NOK 1M** more, exercisable at the seed at the **lower of the seed price and a NOK 20M pre-money cap**, term [24–36] months (legal maximum 5 years, §11-12)
Warrant shares count in the seed's fully diluted pre-money; the exercise cash comes on top of the seed money.
| Seed | Warrant price | Owner % after seed, not exercised | Owner % after seed, exercised | Extra owner dilution | Investor % (exercised) |
|---|---|---|---|---|---|
| N1 | cap | 62.22 % | 59.26 % | 2.96 pp | 10.74 % |
| N2 | cap | 58.61 % | 55.82 % | 2.79 pp | 10.12 % |
| S10 | seed price | 35.56 % | 31.11 % | 4.44 pp | 8.89 % |
| S20 | seed price | 50.37 % | 47.41 % | 2.96 pp | 9.26 % |
| S40 | cap | 62.22 % | 59.26 % | 2.96 pp | 10.74 % |
Warrants are **hidden dilution**, and they are exercised when the company does well. Compared with the recommendation
(63.64 % after N1), structure (c) leaves the owner 4.4 pp lower.

### (d) Smaller stake: NOK 500k at NOK 8M or 10M pre + pro-rata right in the seed
| Pre-money | Investor % | Owner % after pre-seed | Owner % after N1 | Owner % after N2 | Pro-rata amount N1 / N2 |
|---|---|---|---|---|---|
| NOK 8M | 5.88 % | 94.12 % | 65.88 % | 62.06 % | NOK 588k / NOK 2.24M |
| NOK 10M | 4.76 % | 95.24 % | 66.67 % | 62.80 % | NOK 476k / NOK 1.81M |
The pro-rata right is taken inside a fixed seed size, so it costs the owner no extra dilution. However, the company then
has only NOK 500k, i.e. about half the runway (about 4–9 months instead of 8–18; ESTIMATE).

### PATH: rounds in sequence (pre-seed → N1 → N2 → Series A USD 12M @ USD 36M pre; pool created once, at N1)
| Structure | Owner after pre-seed | after N1 | after N2 | after Series A |
|---|---|---|---|---|
| (a) NOK 1M @ 8M pre | 88.89 % | 62.22 % | 47.25 % | 35.44 % |
| **(a) NOK 1M @ 10M pre (recommended)** | **90.91 %** | **63.64 %** | **48.33 %** | **36.24 %** |
| (b) convertible | 100.00 % | 64.12 % | 48.69 % | 36.52 % |
| (c) NOK 1M @ 8M pre + warrant | 88.89 % | 59.26 % | 45.00 % | 33.75 % |
| (d) NOK 500k @ 10M pre + pro-rata | 95.24 % | 66.67 % | 50.63 % | 37.97 % |
Figures as in investor\dilution.py's PATH table. dilution.py computes the exact values, which differ by ≤ 0.01 pp
(48.32 % and 50.62 % exact) because finance chains rounded percentages.

## 5. Recommendation (matches finance / ROUND-ASSUMPTIONS)

**Recommended: (a) with a pro-rata right. A priced rettet emisjon of NOK 1,000,000 at a pre-money of NOK 10,000,000
(ESTIMATE): investor 9.09 %, owner keeps 90.91 %**. With the rounds in sequence, the owner then holds 63.64 % after N1 (incl. the 10 % pool), 48.33 %
after N2 and 36.24 % after the Series A (ESTIMATE).
The investor gets a pro-rata right **in the seed round only**. There is no liquidation preference, no anti-dilution
beyond statutory pre-emption, and an observer seat rather than a board seat.
- **Acceptable range:** down to NOK 8M pre-money (owner 88.89 %).
- **Fallback (b):** if the investor will not accept at least NOK 8M pre-money, offer the convertible loan: cap NOK 12M,
  20 % discount, 5 % interest, 24-month maturity, conversion at the cap at maturity.
- **Avoid (c) and (s)** (reasons in §3–4). (d) keeps more ownership but halves the runway.
- Trade-offs: a high pre-money now makes a down-round seed more painful. The seed will add a 10 % pool that dilutes the
  owner and the pre-seed investor alike. The owner keeps ≥ 2/3 of the votes after the round, so the investor cannot block
  §5-18 decisions; expect it to ask for a short veto list in the SHA.

## 6. Open issues for the advokat
1. Confirm the valuation and instrument with the owner (ROUND-ASSUMPTIONS says "owner decides").
2. Check the Foretaksregisteret procedure and fees, and whether the company needs a revisor (UNVERIFIED).
3. Check tax for each instrument, for the company and the investor (Skatteetaten not opened; UNVERIFIED), and whether the
   investor is a company (fritaksmetoden) or an individual.
4. Check the prospectus/offer rules if more than a few people are approached (verdipapirhandelloven; UNVERIFIED).
5. Check that automatic or maturity conversion of the loan fits the lender's "right to demand" shares in §11-1.

---

## Sammendrag på norsk

**FORUTSETNING:** NeuroForge Bio blir et norsk AS etter aksjeloven og er ennå ikke stiftet. Alle tall kommer fra
investor\ROUND-ASSUMPTIONS.md og er ANSLAG (ESTIMATE).

**Begreper:** NOK 1 mill. er en **pre-seed/engle-runde**, ikke "Series A". Neste runde er **seed** (eierens "Series B").
Runden er i NOK. USD 1 mill. i finansmodellen er en annen, større plan.

**Alternativer:**
- (a) Rettet emisjon (asl. §§ 10-1, 10-4, 10-5, 10-9).
- (b) Konvertibelt lån (asl. kap. 11): cap NOK 12 mill., 20 % rabatt, 5 % rente over 24 måneder, så NOK 1 100 000
  konverteres.
- (c) Aksjer til NOK 8 mill. pre-money pluss frittstående tegningsrett (§ 11-12) på inntil NOK 1 mill. til laveste av
  seed-kurs og cap NOK 20 mill. pre-money, med løpetid [24–36] måneder (maks fem år). Dette gir 2,7–4,4 prosentpoeng
  skjult utvanning.
- (d) NOK 500 000 til NOK 8–10 mill. pre-money med pro-rata-rett.
- SAFE har ikke noe lovgrunnlag og anbefales ikke.

**Opsjonspool:** 10 % opprettes pre-money i seed-runden.

**Anbefaling:** NOK 1 000 000 til pre-money NOK 10 mill. **Eieren beholder 90,91 %**. Med rundene i rekkefølge har eieren 63,64 % etter N1, 48,33 % etter N2 og
36,24 % etter Series A (ANSLAG). Valutakurs: 9,5063 NOK/USD (Norges Bank), så USD 4,0 mill. ≈ NOK 38,0 mill. Investor får pro-rata-rett kun i seed-runden. Konvertibelt lån er reserveløsning hvis investor ikke
aksepterer minst NOK 8 mill. pre-money.

**Kontroll:** Legal og finans sine beregninger er identiske (50 scenarier, 0 avvik; PATH-tabellen avviker ≤ 0,01
prosentpoeng på grunn av avrunding).

---

## Hjemmel / Legal basis

- Aksjeloven (lov 13. juni 1997 nr. 44), main page (opened 2026-09-26; table of contents only):
  https://lovdata.no/dokument/NL/lov/1997-06-13-44
  - §3-1: https://lovdata.no/lov/1997-06-13-44/§3-1 (opened 2026-09-26)
  - §2-6: https://lovdata.no/lov/1997-06-13-44/§2-6 (opened 2026-09-26)
  - §4-15: https://lovdata.no/lov/1997-06-13-44/§4-15 (opened 2026-09-26); §§4-16 to 4-23 **UNVERIFIED**
  - §§5-17 to 5-21: https://lovdata.no/lov/1997-06-13-44/§5-18 (opened 2026-09-26)
  - §§10-1 to 10-13: https://lovdata.no/lov/1997-06-13-44/§10-1, …/§10-2, …/§10-4, …/§10-9 (opened 2026-09-26)
  - §§11-1 to 11-9: https://lovdata.no/lov/1997-06-13-44/§11-1 (opened 2026-09-26)
  - §§11-10, 11-11: https://lovdata.no/lov/1997-06-13-44/§11-10 (opened 2026-09-26)
  - §§11-12, 11-13: https://lovdata.no/lov/1997-06-13-44/§11-12 (opened 2026-09-26)
- Innovasjon Norge: https://www.innovasjonnorge.no/seksjon/starte (opened 2026-09-26); no valuation data.
- Brønnøysundregistrene: https://www.brreg.no/bedrift/aksjeselskap/endre-aksjekapitalen/ (404) and
  https://www.brreg.no/aksjeselskap/ (failed). Procedure and fees **UNVERIFIED**.
- Not opened: Skatteetaten (tax **UNVERIFIED**), verdipapirhandelloven (**UNVERIFIED**), the Y Combinator SAFE, and any
  valuation dataset (valuations **ESTIMATE + UNVERIFIED**).
- Internal: investor\ROUND-ASSUMPTIONS.md; investor\dilution.py / dilution.csv (finance); legal\financing\dilution.py.
- Method: lovdata pages were read through an automated fetch tool that summarises the page; the advokat must check the
  quoted wording against the official text.
