# NeuroForge Bio: the first round of about NOK 1,000,000, explained

Author: nfb-finance-ba (AI draft for Marius Carlsson) · 2026-09-26 · **DRAFT. Every number is an ESTIMATE.**
Not financial, tax or legal advice. **The owner decides. Nothing has been sent to anyone.**
Numbers: `investor\dilution.py` → `investor\dilution.csv` (inputs from `investor\ROUND-ASSUMPTIONS.md`).
Legal drafts: `legal\financing\` (nfb-legal). Legal questions go to nfb-legal and a Norwegian advokat.

---

## 1. First, the name of the round

You have called this round "Series A". In market terms, **NOK 1M from one first investor is a pre-seed or angel
round** (*første runde / pre-seed*). It is a normal and good first step, just under a different name. The usual order is:

1. **Pre-seed / angel round** (this one): a small cheque, often from one private investor (*business angel*), before
   there is a product or revenue.
2. **Seed round** (what you called "Series B"): a larger round once there are early signals such as design partners.
3. **Series A**: later, usually led by a venture fund, when the business shows it can grow. The financial model
   assumes a USD 12M Series A (ESTIMATE).

Using the right name helps you. An investor or advokat who sees "Series A" on a NOK 1M term sheet may expect fund-style
terms (liquidation preference, anti-dilution, veto lists) that a round of this size does not need.

## 2. The words, in plain language

| Term | Norwegian | What it means for you |
|---|---|---|
| Shares | *aksjer* | The company issues new shares and sells them to the investor. You own a smaller slice of a bigger company. |
| Pre-money valuation | *pre-money (verdi før emisjon)* | What the company is agreed to be worth **before** the new money comes in. |
| Post-money valuation | *post-money (verdi etter emisjon)* | Pre-money + the new money. Investor % = new money ÷ post-money. |
| Priced round | *rettet emisjon* | You and the investor agree the pre-money now. The dilution is known on day one. |
| Convertible loan | *konvertibelt lån* | The investor lends money that later turns into shares at the next round, at a better price than new investors pay (a **cap** on the valuation and/or a **discount**). The valuation is decided later. |
| Warrant | *tegningsrett / frittstående tegningsrett* | A right to buy more shares later at a fixed or capped price. |
| Pro-rata right | *pro rata-rett* | A right for the investor to invest again in the next round so it keeps its percentage. |
| Option pool | *opsjonsprogram / opsjonspott* | Shares set aside for future employees. Seed investors usually ask for it to be created **before** their money comes in, so it dilutes you and the first investor, not them. |
| Dilution | *utvanning* | Your % goes down when new shares are issued. The value of your stake can still rise. |

## 3. What the numbers assume (all ESTIMATE)

- Today you own 100 % (assumed; please confirm there are no other holders).
- **Next round (seed)**, from ROUND-ASSUMPTIONS: **N1** = NOK 10M at NOK 40M pre-money; **N2** = USD 4.0M
  (≈ NOK 38.0M at the Norges Bank rate; was ≈ NOK 42M at the old 10.5 estimate) at NOK 120M pre-money. **Stress tests**: NOK 10M at NOK 10M, 20M and 40M pre-money.
- At the seed, a **10 % option pool is created pre-money** (it dilutes you and the first investor).
- Seed pre-money is counted *fully diluted*: it includes the pool, converted loans and exercised warrants. This is the
  harder case for you, and the one a seed investor will usually ask for.
- **Series A later**: USD 12M (financial-model.py) at a pre-money of **USD 36M (base ESTIMATE**, method: judgement that
  a Series A investor buys about 25 %; no market source opened) and USD 24M (stress). No extra pool top-up modelled.
- **FX: 9.5063 NOK per USD**, Norges Bank USD/NOK spot rate for **2026-09-25**, from
  https://data.norges-bank.no/api/data/EXR/B.USD.NOK.SP?format=csv&lastNObservations=1 (opened 2026-09-26; the raw
  data file was read, grade A). NOK 1M ≈ **USD 105k**. FX does not change the percentages of options (a)–(d); it only
  changes the NOK size of N2 (USD 4.0M ≈ NOK 38.0M).

## 4. Summary of all scenarios (from dilution.py; all ESTIMATE)

Owner % after this round, then after the seed (N1, N2, and stress S10/S20/S40 = NOK 10M at NOK 10/20/40M pre).

| Option | Money in now | Owner % after this round | N1 | N2 | S10 | S20 | S40 |
|---|---|---|---|---|---|---|---|
| (a) Shares, NOK 1M at NOK 4M pre | NOK 1.0M | 80.00 % | 56.00 % | 52.75 % | 32.00 % | 45.33 % | 56.00 % |
| (a) Shares, NOK 1M at NOK 6M pre | NOK 1.0M | 85.71 % | 60.00 % | 56.52 % | 34.29 % | 48.57 % | 60.00 % |
| (a) Shares, NOK 1M at NOK 8M pre | NOK 1.0M | 88.89 % | 62.22 % | 58.61 % | 35.56 % | 50.37 % | 62.22 % |
| (a) Shares, NOK 1M at NOK 10M pre | NOK 1.0M | 90.91 % | 63.64 % | 59.94 % | 36.36 % | 51.52 % | 63.64 % |
| (a) Shares, NOK 1M at NOK 15M pre | NOK 1.0M | 93.75 % | 65.63 % | 61.82 % | 37.50 % | 53.13 % | 65.63 % |
| (a) Shares, NOK 1M at NOK 20M pre | NOK 1.0M | 95.24 % | 66.67 % | 62.80 % | 38.10 % | 53.97 % | 66.67 % |
| (b) Convertible loan, cap NOK 12M, 20 % discount, 5 %/yr (24 months) | NOK 1.0M | 100 % (until conversion) | 64.12 % | 60.40 % | 33.13 % | 51.91 % | 64.12 % |
| (c) Shares at NOK 8M pre + warrant for NOK 1M more at a NOK 20M cap | NOK 1.0M (+1.0M at seed) | 88.89 % | 59.26 % | 55.82 % | 31.11 % | 47.41 % | 59.26 % |
| (d) NOK 500k at NOK 8M pre + pro-rata right | NOK 0.5M | 94.12 % | 65.88 % | 62.06 % | 37.65 % | 53.33 % | 65.88 % |
| (d) NOK 500k at NOK 10M pre + pro-rata right | NOK 0.5M | 95.24 % | 66.67 % | 62.80 % | 38.10 % | 53.97 % | 66.67 % |

**Which price binds** (dilution.py):
- (b) Convertible: the **cap** binds when the seed pre-money is NOK 20M or more (N1, N2, S20, S40); the **discount**
  binds in the weak NOK 10M seed (S10). Then the convertible is *worse* for you than selling shares at NOK 8M today
  (33.13 % vs 35.56 %).
- (c) Warrant: the **NOK 20M cap** binds when the seed is priced above it (N1, N2, S40), so the investor buys cheap
  shares exactly when the company does well. In S10/S20 it pays the seed price.

**Owner % after a later Series A** (USD 12M at USD 36M base / 24M stress pre-money, ESTIMATE):

| Option | via N1 seed | via N2 seed |
|---|---|---|
| (a) NOK 1M at NOK 8M pre | 46.67 % / 41.48 % | 43.96 % / 39.07 % |
| **(a) NOK 1M at NOK 10M pre (recommended, + pro-rata)** | **47.73 % / 42.42 %** | **44.96 % / 39.96 %** |
| (b) Convertible, cap NOK 12M | 48.09 % / 42.75 % | 45.30 % / 40.27 % |
| (c) NOK 8M pre + warrant | 44.44 % / 39.51 % | 41.86 % / 37.21 % |
| (d) NOK 500k at NOK 8M pre | 49.41 % / 43.92 % | 46.54 % / 41.37 % |
| (d) NOK 500k at NOK 10M pre | 50.00 % / 44.44 % | 47.10 % / 41.86 % |

**Sequential path** (financial-model.py now raises the rounds one after another: NOK 1M → N1 → N2 → Series A;
pool created once at N1; dilution.py "PATH" table, ESTIMATE):

| Option | after pre-seed | after N1 | after N2 (USD 4.0M @ NOK 120M pre) | after Series A (USD 12M @ USD 36M pre) |
|---|---|---|---|---|
| (a) NOK 1M at NOK 8M pre | 88.89 % | 62.22 % | 47.25 % | 35.44 % |
| **(a) NOK 1M at NOK 10M pre (recommended)** | **90.91 %** | **63.64 %** | **48.33 %** | **36.24 %** |
| (b) Convertible, cap NOK 12M | 100 % | 64.12 % | 48.69 % | 36.52 % |
| (c) NOK 8M pre + warrant | 88.89 % | 59.26 % | 45.00 % | 33.75 % |
| (d) NOK 500k at NOK 10M pre | 95.24 % | 66.67 % | 50.63 % | 37.97 % |

Reading: the choice made in this small round moves your final stake by only a few percentage points. **The seed
price and the option pool matter much more** (compare the S10 column with N1). So the first round should be simple,
cheap, and should not make the seed harder.

## 5. Would a real angel accept it? (my judgement, not market data)

No Nordic pre-seed valuation dataset was opened, so these are **judgements, UNVERIFIED**. nfb-legal's memo
(`legal\financing\STRUCTURES.md` §2) reached a similar view by the same kind of reasoning (angels commonly take roughly
10–20 % for a first cheque; also UNVERIFIED).

- **(a) Shares at NOK 4–6M pre (14–20 %)**: easy to accept, but more dilution than you need. Keep NOK 6M as a floor.
- **(a) Shares at NOK 8–10M pre (9–11 %)**: plausible for a pre-product, one-founder company with a clear plan, if the
  investor believes in the founder and the market work. NOK 10M is the ambitious end; NOK 8M is the middle.
- **(a) Shares at NOK 15–20M pre (5–6 %)**: likely hard to accept without traction (no product, no customers yet).
  It also risks a **down round** if the seed is priced lower, which hurts both of you.
- **(b) Convertible loan**: familiar to many investors and it postpones the valuation talk. The cap of NOK 12M is
  higher than the priced options an angel would likely take, so the investor may push for a lower cap. It carries
  interest, a 24-month maturity, and a bad outcome for you if the seed is weak.
- **(c) Shares + warrant**: attractive for the investor (cheap upside), costly for you (3–4 extra points after the
  seed). Accept only if the investor insists, and then cap it small and price it at the seed price less a small
  discount (as legal's draft `term-sheet-warrant.en.md` does).
- **(d) NOK 500k + pro-rata**: the lowest dilution, and a small cheque is easier for an angel to say yes to. But it
  raises only half the money: about 4 months with a small team or about 8 months lean (ESTIMATE, from §7a), which is
  probably too short to reach the milestones with a team.

## 6. RECOMMENDATION (owner decides)

**Priced share issue (*rettet emisjon*) of NOK 1,000,000 at a pre-money of NOK 10M, with a one-round pro-rata right
in the seed (*pro rata-rett*). Walk-away floor NOK 8M pre; below that, offer the convertible loan (b) instead.**

- Owner % **after this round: 90.91 %** (investor 9.09 %).
- Owner % **after the next round: 63.64 % (N1)** or **59.94 % (N2 as a single next round)**, with the 10 % pool. Stress range 36.36–63.64 %.
- On the sequential path in financial-model.py (N1 then N2): 63.64 % after N1, **48.33 % after N2**. The exact value is 48.32 %; the table rounds before multiplying (a rounding note from nfb-legal).
- Owner % after a later Series A: about **47.7 % (N1 only) / 45.0 % (N2 only) / 36.2 % (N1 then N2)** at the base USD 36M pre-money ESTIMATE.
- Why: it is the lowest-dilution option that still raises the full NOK 1M and that I judge a real angel could accept.
  The pro-rata right gives the investor something it values without costing you extra, as long as it is taken inside
  a fixed seed size. It fixes the dilution today, with no interest, maturity cliff or hidden warrant dilution.
  This matches nfb-legal's recommendation (STRUCTURES.md §5: priced round at NOK 8–10M + pro-rata).
- The convertible (b) gives you slightly more at N1/N2 (64.12 % vs 63.64 %) but less if the seed is weak, and an
  angel may not accept a NOK 12M cap. It is a good fallback, not the first offer.

## 7. What the NOK 1M buys (per ROUND-ASSUMPTIONS; ESTIMATE)

NOK 1M ≈ USD 105k. It funds about **8–9 months with a small team, or about 18–22 months lean** (see §7a) of: the founder part-time or on a low salary, tooling, the first cloud
spend, an initial trademark clearance search and a first privacy-counsel review. It does **not** fund the year-1 plan
in financial-model.py (about USD 0.64M burn). It is a bridge to the milestones that make a seed possible:
1. 15–20 customer-discovery interviews (pricing hypotheses tested).
2. The open-core SDK released.
3. 3–5 design partners.
Then the seed round (N1), then a larger round (N2), then a Series A.

## 7a. How far NOK 1M gets us (financial-model.py pre-phase table; `investor\prephase-runway.csv`; all ESTIMATE)

Two ways to spend the NOK 1M before the seed (NOK per month; one-offs in months 1, 2 and 4):

| Cost line | Lean (founder-led) | Small team |
|---|---|---|
| Founder stipend, all-in (owner decides; could be 0) | 25,000 | 25,000 |
| Contractor (BLS US software-developer median ×1.03 inflation ×1.3 loading, per FTE) | 0.1 FTE ≈ 14,000 | 0.5 FTE ≈ 72,000 |
| AI tools + code hosting + SaaS (no prices opened) | USD 300 ≈ 2,850 | USD 450 ≈ 4,300 |
| Accounting (must be quoted) | 3,000 | 3,000 |
| Cloud (BLUEPRINT §12.1: M1 website band months 1–3, then pilot band) | ≈ 240 → 4,750 (low end) | ≈ 240 → 10,000 (midpoint) |
| **Monthly run-rate from month 4** | **≈ NOK 50,000** | **≈ NOK 114,000** |
| One-offs (must be quoted): AS set-up NOK 10k (m1), trademark clearance search NOK 20k (m2), first privacy-counsel review NOK 60k (m4) | 90,000 | 90,000 |

**Months NOK 1M lasts (cash stays ≥ 0; no revenue assumed):**

| | No grants | With grants (IN oppstartstilskudd 1 + SkatteFUNN) |
|---|---|---|
| **Lean** | **18 months** | **22 months** |
| **Small team** (founder + 1 contractor at 50 %) | **8 months** | **9 months** |

Cash at month end (NOK): lean 623k (m6), 323k (m12), 23k (m18); small team 253k (m6), then negative from month 9.
With grants the small team reaches month 9 (60k left) and runs out in month 10.

**Grant assumptions (conditional; NOT guaranteed):**
- **Innovation Norway oppstartstilskudd 1**: up to **NOK 150,000** for an AS younger than 5 years (innovasjonnorge.no
  page, as recorded in `DATA-REVENUE-STRATEGY.md` Sources, grade B). Modelled as NOK 150k in month 5. It needs the AS
  to exist and an approved application; the payment month is ESTIMATE/UNVERIFIED.
- **SkatteFUNN**: **19 %** of approved R&D costs; the company must be registered in Brønnøysund and taxable in Norway;
  apply before **1 September** for the same year (forskningsradet.no/skattefunn, as recorded in the same Sources table,
  grade B). Modelled on 70 % of year-1 founder + contractor cost (ESTIMATE): ≈ NOK 63k (lean) / ≈ NOK 155k (small team).
  **Cash timing:** it is paid through the tax settlement (*skatteoppgjør*) the autumn **after** the income year, so it
  arrives around **month 21** (if month 1 ≈ January; UNVERIFIED). It extends the lean runway but comes far too late to
  save the small team; for them it is a receivable, not cash in the first year.
- **Forskningsrådet "Innovasjonsprosjekt i næringslivet"**: I tried the programme page on 2026-09-26 and it returned
  HTTP 404, so it is **UNVERIFIED** and not modelled.

**What this means:**
- **Small team**: the seed (N1) must **close by month 9** (month 10 at the latest if the first paid audits land, per
  the base growth scenario). That is tight for 15–20 interviews, an SDK and 3–5 design partners.
- **Lean**: 18–22 months gives time to reach the milestones before raising, at the cost of slower building. If the
  founder also sells about one paid audit per quarter (USD 20k each, unvalidated), the "lean" scenario in
  financial-model.py roughly breaks even (burn about USD 15k/year) and cash lasts to about month 59.
- A sensible middle path (judgement): start lean, switch to the small team once the grant and the first design partner
  are confirmed, and open the seed process around month 6–9.

**Growth scenarios with the corrected funding path (financial-model.py; USD; ESTIMATE):**

| Scenario | Pre-phase | Seed N1 (NOK 10M) | N2 | Series A | Y5 ARR | Y5 year-end cash | Minimum cash |
|---|---|---|---|---|---|---|---|
| Base | small team | month 9 (must close by 9–10) | USD 4.0M, month 20 (must close by 21) | USD 12M, month 40 (by 44) | $3.63M | $7.03M | $13k (month 8) |
| Bear | lean | month 14 | USD 2.5M, month 32 (needed by 27) | USD 7M, month 50 | $1.15M | $2.69M | **−$1.25M (month 49): funding gap** |
| Bull | small team | month 8 (by 11) | USD 5.0M, month 20 (by 21) | USD 18M, month 36 | $7.00M | $13.61M | $23k (month 7) |

Hiring is cash-gated: nobody is employed before the seed, and each hire needs cash for 9 months of projected burn.
Paid launch moves to seed + 8 months (base month 17), so base Y5 ARR falls from $4.54M (old path) to $3.63M.

## 8. Risks

- **Convertible stacking**: several convertible loans in a row add up to hidden dilution that is only seen at the seed.
  Keep at most one, with the same cap.
- **Warrant overhang**: warrants that can be used later make the cap table uncertain, and seed investors dislike that.
- **Down round**: a high pre-money now and a low seed price later hurts you and the first investor.
- **Option pool shuffle**: a pool created pre-money at the seed costs you about 9 points after the seed (N1 with the
  recommended option: 63.64 % with the pool vs 72.73 % without it). Negotiate the pool size against a hiring plan.
- **Short runway**: with a small team NOK 1M lasts about 8–9 months. If the milestones slip, you raise again from a weak position. Lean stretches it to 18–22 months.
- **Norwegian company law formalities**: the company is not yet incorporated as an AS. Share issues, convertible
  loans and warrants each need general-meeting resolutions, registration in Foretaksregisteret and other steps.
  **I give no legal advice here; see nfb-legal's drafts in `legal\financing\` and a Norwegian advokat.**
- **Tax**: the treatment for you, the company and the investor is not checked (UNVERIFIED).

## 9. Non-dilutive money to check first

**SkatteFUNN** (19 % of approved R&D costs, paid via the tax settlement the year after) and **Innovation Norway
oppstartstilskudd 1** (up to NOK 150k for an AS under 5 years) are modelled in §7a. Both need the AS to exist and an
approved application; neither is guaranteed. Forskningsrådet's "Innovasjonsprosjekt i næringslivet" page returned
404 (UNVERIFIED). Every krone from these is a krone you do not have to sell shares for, so apply as soon as the AS
exists (SkatteFUNN before 1 September).

## 10. Differences from the legal drafts (for the CEO and nfb-legal)

- Legal's `dilution.py` models the seed as NOK 8M at NOK 10/20/40M pre-money **with no option pool**; this file uses
  ROUND-ASSUMPTIONS (N1/N2 + NOK 10M stress) **with a 10 % pool**. So owner % after the seed differs between the two.
- Legal's convertible example uses 18 months of interest (NOK 1.075M converts); this model uses the 24-month maturity
  (NOK 1.10M converts).
- Warrant: ROUND-ASSUMPTIONS (c) is **up to NOK 1M at a NOK 20M pre-money cap**; legal's STRUCTURES.md models NOK 500k
  at the round-1 price, and `term-sheet-warrant.en.md` caps it at NOK 250–500k at the seed price less 10 %, 24 months.
- Option (d): ROUND-ASSUMPTIONS uses NOK 500k; legal's (e) uses NOK 1M at NOK 10M + pro-rata (= my recommendation).
No number in ROUND-ASSUMPTIONS.md was changed.

---
*Owner decides; nothing is sent. All figures ESTIMATE.*
