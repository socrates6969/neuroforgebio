"""NeuroForge Bio: 5-year financial model (stdlib only).

EVERY OUTPUT OF THIS MODEL IS AN ESTIMATE. The company is pre-product: there are no customers,
no revenue, no LOIs and no quotes. All prices are ESTIMATEs until validated in customer discovery.

Run:  C:\\Users\\mariu\\AppData\\Local\\Programs\\Python\\Python312\\python.exe financial-model.py
Writes financial-model.csv and prephase-runway.csv next to this file and prints a summary.

Structure
  1. ASSUMPTIONS   every input: name, value, unit, source or "ESTIMATE: <method>"
  2. SCENARIOS     base / bear / bull (growth), base+data_* (upside), as named overrides of the base assumptions
  3. ENGINE        monthly simulation, months 1..60 (model year 1 = months 1-12), cash-gated hiring
  4. PRE-PHASE     month-by-month runway of NOK 1M: "lean" (founder + AI tools + light contractors) vs
                   "small_team" (founder + 1 contractor at 50 %), each with and without grants
  5. OUTPUTS       yearly roll-up, printed summary, CSVs, sensitivity table

Funding path (corrected 2026-09-26, owner fix via the CEO agent)
  Model month 1 = the month the owner's FIRST round closes: NOK 1,000,000 PRE-SEED / ANGEL round (the owner's
  working name "Series A"; see investor/ROUND-ASSUMPTIONS.md and investor/FUNDING-ROUND.md). At the Norges Bank
  rate used here that is about USD 105k, NOT USD 1.0M. Until the seed closes the company runs in a PRE-PHASE
  (no employees: founder stipend + contractor + tools + pilot infra + essential assurance only).
  Then: seed N1 = NOK 10M at NOK 40M pre (ROUND-ASSUMPTIONS), a larger round N2 = USD 4.0M later, and a Series A.
  Paid launch = seed month + build months. Employees are hired only after the seed and only while cash covers
  HIRING_GATE_MONTHS of projected net burn (cash-gated hiring). Timing and sizes are ESTIMATE, not commitments.

SOM check. market/sizing.md §3 gives its SOM (~$2.4M ARR, 108 logos) for "year 3 after launch" = launch + 35.

Simplifications (stated, not hidden)
  * Cash = EBITDA + equity raised (+ grants only in the pre-phase table). Working capital, capex, interest and tax
    are ignored. Growth scenarios contain NO grants (conservative; grants are conditional and not guaranteed).
  * Fractional logos are allowed inside the engine; reported logo counts are rounded. Heads are whole people.
  * Churn and expansion are applied to aggregate ARR per segment each month.

Upside scenarios (base+data_low / base+data_mid / base+data_high)
  = base case + data-asset revenue from investor/DATA-REVENUE-STRATEGY.md Part C (USD thousands, Y1-Y5, ESTIMATE),
  with Part C's cost notes (pool infra ~8 person-months ~ $118k loaded over Y2-Y3; pool storage ~$160/month from Y3)
  and an ESTIMATE direct-cost share for that revenue. Base, bear and bull contain NO data-asset revenue.
  Simplification: data-asset revenue is recognised evenly within each year, and its year-end run rate (added to
  "End ARR incl. data") = that year's data revenue. ESTIMATE.
"""

import copy
import csv
import os

# =====================================================================================
# 1. ASSUMPTIONS  (name: (value, unit, source))
# =====================================================================================
# Source keys: files are under C:\Users\mariu\neuro-company\. Grades per BOARD.md.
BLS_SWE_URL = "https://www.bls.gov/ooh/computer-and-information-technology/software-developers.htm"
NB_FX_URL = "https://data.norges-bank.no/api/data/EXR/B.USD.NOK.SP?format=csv&lastNObservations=1"
FX = 9.5063   # NOK per USD, Norges Bank spot 2026-09-25 (NB_FX_URL, opened 2026-09-26; grade A)


def nok(x):
    """NOK -> USD at FX."""
    return x / FX


A = {
    # ---- FX -------------------------------------------------------------------------
    "fx_nok_per_usd": (FX, "NOK per USD",
        f"Norges Bank exchange rate USD/NOK, business-day spot, 2026-09-25 = 9.5063 ({NB_FX_URL}; opened 2026-09-26; grade A)"),

    # ---- timing -------------------------------------------------------------------------
    "build_months_after_seed": (8, "months",
        "ESTIMATE: BLUEPRINT §12.3 M0-M5 ~32 person-months; ~4 builders after the seed plus pre-phase founder work "
        "-> ~8 months from seed close to paid launch"),
    "services_start_month": (6, "model month",
        "ESTIMATE: pricing-and-gtm.md §2 'Services ... early revenue while the product matures'; founder-run "
        "multiverse audit on public data; first paid audit assumed month 6"),
    "hiring_gate_months": (9, "months of projected net burn that cash must cover before each hire",
        "ESTIMATE: judgement (owner fix: hiring gated on cash)"),

    # ---- pricing / ACV (list, annual) ------------------------------------------------
    "acv_S1_growth": (75_000, "USD/logo/yr",
        "market/sizing.md §3 SOM table (S1 ACV $75k); inside Growth tier band $50k-150k (pricing-and-gtm.md §2). ESTIMATE"),
    "acv_S2_startup_tier": (6_600, "USD/logo/yr",
        "ESTIMATE: midpoint of Startup tier $300-800/mo (pricing-and-gtm.md §2) = $550/mo x 12"),
    "acv_S2_volume_tier": (36_000, "USD/logo/yr",
        "ESTIMATE: top of ledger price $500-3,000/mo by data-subject volume (new-ideas.md #1) = $3,000 x 12"),
    "s2_startup_share": (0.55, "fraction of S2 logos",
        "ESTIMATE: chosen so blended S2 ACV = 0.55x6.6k + 0.45x36k = $19.8k, reconciling with sizing.md §3 S2 ACV $20k"),
    "acv_S3_lab": (4_000, "USD/logo/yr",
        "market/sizing.md §3 SOM (S3 $4k); Lab tier band $3k-10k/yr (pricing-and-gtm.md §2). ESTIMATE"),
    "acv_S4_enterprise": (150_000, "USD/logo/yr",
        "market/sizing.md §3 SOM (S4 $150k); Enterprise band $100k-300k+ (pricing-and-gtm.md §2). ESTIMATE"),
    "services_avg_fee": (20_000, "USD/engagement",
        "ESTIMATE: near midpoint of Services $5k-40k/engagement (pricing-and-gtm.md §2)"),

    # ---- design-partner offer ---------------------------------------------------------
    "design_partners": (5, "logos (first S1 logos)", "pricing-and-gtm.md §4: 5 design partners"),
    "design_partner_discount": (0.50, "fraction off Growth list", "pricing-and-gtm.md §4: 50% off Growth"),
    "design_partner_months": (12, "months", "pricing-and-gtm.md §4: for 12 months"),

    # ---- gross new logos per LAUNCH year (LY1 = first 12 months after launch) ----------
    "adds_S1": ([5, 6, 7, 9, 11], "logos per launch-year",
        "ESTIMATE: back-solved to reach ~15 active S1 logos 36 mo after launch (sizing.md §3 SOM) net of churn; "
        "LY1 = the 5 design partners"),
    "adds_S2": ([9, 13, 17, 19, 21], "logos per launch-year",
        "ESTIMATE: back-solved to reach ~30 active S2 logos at 36 mo after launch (sizing.md §3) net of churn"),
    "adds_S3": ([16, 26, 32, 35, 38], "logos per launch-year",
        "ESTIMATE: back-solved to reach ~60 paying institutions at 36 mo (sizing.md §3); "
        "= 3-7% of 900-1,750 labs (sizing.md §3 S3 count)"),
    "adds_S4": ([0, 1, 2, 3, 4], "logos per launch-year",
        "ESTIMATE: 'first pharma pilot' months 9-18 (pricing-and-gtm.md §5); Part 11 platform is roadmap; "
        "~3 at 36 mo (sizing.md §3 SOM)"),
    "services_engagements": ([2, 8, 12, 15, 18], "engagements per MODEL year",
        "ESTIMATE: judgement; services are the early-revenue bridge (pricing-and-gtm.md §2); Y1 only from month 6"),

    # ---- retention -----------------------------------------------------------------------
    "churn_S1": (0.10, "annual logo churn", "ESTIMATE: B2B regulated-workflow judgement; no churn data sourced"),
    "churn_S2": (0.20, "annual logo churn", "ESTIMATE: startups fail/pivot more often; no data sourced"),
    "churn_S3": (0.15, "annual logo churn", "ESTIMATE: grant-cycle dependence; no data sourced"),
    "churn_S4": (0.10, "annual logo churn", "ESTIMATE: judgement; no data sourced"),
    "expansion": (0.08, "annual ARR expansion on retained logos",
        "ESTIMATE: value metric = data subjects + devices under management (pricing-and-gtm.md §2) grows with customer trials"),

    # ---- people ------------------------------------------------------------------------
    "swe_base_salary": (135_980, "USD/yr (2025)",
        "BLS OOH, Software Developers, median annual wage May 2025 = $135,980 (" + BLS_SWE_URL + "; opened 2026-09-26; grade A)"),
    "salary_inflation": (0.03, "per year", "ESTIMATE: judgement; applied from model year 1 onward (2025 -> 2026 = 1 step)"),
    "loading_factor": (1.30, "x base salary",
        "ESTIMATE: payroll taxes + benefits + equipment; common small-company rule of thumb 1.25-1.4, not sourced"),
    "founder_salary": ([60_000, 90_000, 120_000, 130_000, 140_000], "USD/yr by model year, AFTER the seed",
        "ESTIMATE: below-market founder pay; owner decides. Before the seed the pre-phase stipend applies"),
    "commission_rate": (0.10, "of new list ARR booked (S1,S2,S4)", "ESTIMATE: judgement, no comp data sourced"),
    "recruiting_per_hire": (10_000, "USD/hire", "ESTIMATE: judgement (job ads, agency-free)"),
    "tools_per_head": (4_000, "USD/head/yr", "ESTIMATE: SaaS tools, laptops amortised"),

    # ---- infrastructure (BLUEPRINT §12.1 bands, monthly) --------------------------------
    "infra_prelaunch": (1_050, "USD/month",
        "BLUEPRINT.md §12.1 M2-M4 pilot band $500-1,600/mo, midpoint (ESTIMATE)"),
    "infra_postlaunch": (5_250, "USD/month",
        "BLUEPRINT.md §12.1 M5+ with BAA tenants, 50 TB band $3,000-7,500/mo, midpoint (ESTIMATE)"),
    "infra_variable": (0.05, "of subscription revenue",
        "ESTIMATE: extra hosting/storage beyond the 50 TB band as customers grow; S3 $0.023/GB-mo (BLUEPRINT §12)"),
    "single_tenant_per_S4": (2_500, "USD/month per S4 logo",
        "ESTIMATE: single-tenant/VPC deployment (pricing-and-gtm.md §2 Enterprise includes single-tenant)"),
    "services_delivery_cost": (0.40, "of services revenue", "ESTIMATE: contractors/extra compute for audits"),
    "cs_cogs_share": (0.50, "of customer-success cost in COGS", "ESTIMATE: standard SaaS allocation"),
    "devops_cogs_share": (0.30, "of devops/security cost in COGS", "ESTIMATE: standard SaaS allocation"),

    # ---- G&A and assurance AFTER the seed (NO PRICES SOURCED -> MUST BE QUOTED) ----------
    "ga_fixed": ([25_000, 40_000, 60_000, 80_000, 100_000], "USD/yr (monthly 1/12, from seed month)",
        "ESTIMATE: accounting, corporate legal; must be quoted"),
    "insurance": (15_000, "USD/yr from launch year", "ESTIMATE: cyber + E&O; must be quoted"),
    "privacy_counsel": ([40_000, 15_000, 20_000, 20_000, 25_000], "USD/yr (from seed month)",
        "ESTIMATE, MUST BE QUOTED: RuleSet + BAA review before first paying ledger customer (DECISIONS.md D10 #1; BLUEPRINT §12.2)"),
    "regulatory_consultant": ([0, 50_000, 25_000, 25_000, 25_000], "USD/yr",
        "ESTIMATE, MUST BE QUOTED: FDA Evidence Kit scaffold review before sale (DECISIONS.md D10 #2)"),
    "soc2": ([0, 70_000, 40_000, 40_000, 45_000], "USD/yr",
        "ESTIMATE, MUST BE QUOTED: SOC 2 Type II readiness+audit once 2-3 design partners ask (DECISIONS.md D10 #3)"),
    "pen_test": ([15_000, 25_000, 25_000, 30_000, 30_000], "USD/yr", "ESTIMATE, MUST BE QUOTED: external penetration test"),

    # ---- marketing programme (BOARD.md shared budget; from seed month) -----------------
    "marketing_programme": ([40_000, 100_000, 200_000, 350_000, 500_000], "USD/yr",
        "investor/BOARD.md 'Shared marketing budget' base case (ESTIMATE set by queen); spent only after the seed"),

    # ---- headcount TARGETS: END-OF-YEAR heads by role (founder separate); cash-gated ----
    "roles": ({
        # role:            (salary multiple, cost bucket, [Y1..Y5 end-of-year target heads])
        "software_engineer":   (1.00, "R&D", [3, 5, 7, 9, 11]),
        "neuro_data_scientist": (1.00, "R&D", [1, 1, 2, 2, 3]),
        "devops_security":     (1.10, "R&D", [0, 1, 1, 2, 2]),
        "product_designer":    (0.85, "R&D", [0, 1, 1, 1, 2]),
        "regulatory_qa":       (1.00, "R&D", [0, 1, 1, 2, 2]),
        "account_exec":        (0.90, "S&M", [0, 1, 2, 3, 4]),
        "customer_success":    (0.85, "S&M", [0, 1, 2, 3, 4]),
        "marketing_devrel":    (0.90, "S&M", [0, 1, 1, 2, 3]),
        "g_and_a_ops":         (0.60, "G&A", [0, 0, 1, 1, 2]),
    }, "heads (targets; actual hires are cash-gated and start after the seed)",
        "ESTIMATE: BLUEPRINT §12.3 (~32 person-months M0-M5 needs ~4 builders); later years scaled to ~$100k ARR/employee; "
        "salary multiples vs BLS SWE median are ESTIMATE (no other role sourced)"),

    # ---- funding plan (ESTIMATE; nothing raised, no investor contacted) ----------------
    "funding": ([("pre-seed/angel NOK 1M", 1, nok(1_000_000)),
                 ("seed N1 NOK 10M @ NOK 40M pre", 9, nok(10_000_000)),
                 ("round N2 USD 4.0M @ NOK 120M pre", 20, 4_000_000),
                 ("Series A USD 12M", 40, 12_000_000)],
        "(round, model month, USD)",
        "ESTIMATE: NOK 1M and N1/N2 from investor/ROUND-ASSUMPTIONS.md; Series A USD 12M (earlier plan); timing = judgement"),
    "prephase_mode": ("small_team", "lean | small_team", "ESTIMATE: team shape before the seed closes"),
    "opening_cash": (0, "USD", "ESTIMATE: owner has not committed personal capital in this model"),

    # ---- data-asset UPSIDE (OFF in base/bear/bull; on only in base+data_* scenarios) ------
    "data_scenario": (None, "None | low | mid | high", "base/bear/bull: no data-asset revenue"),
    "data_revenue": ({"low": [0, 20_000, 52_000, 84_000, 128_000],
                      "mid": [15_000, 60_000, 228_000, 496_000, 800_000],
                      "high": [40_000, 180_000, 540_000, 1_420_000, 2_400_000]}, "USD/yr by model year",
        "investor/DATA-REVENUE-STRATEGY.md Part C upside table (benchmarks A7 + DP API/synthetic A3+A4 + "
        "foundation-model licences A5; income approach, bottom-up). ESTIMATE"),
    "data_direct_cost_share": (0.20, "of data-asset revenue (COGS)",
        "ESTIMATE: judgement for DP query compute, synthetic-data generation, benchmark hosting and curation time; "
        "implies ~80% gross margin on this revenue before pool storage; no cost data sourced"),
    "data_pool_build": ([0, 59_000, 59_000, 0, 0], "USD/yr (R&D)",
        "DATA-REVENUE-STRATEGY.md Part C cost cross-check: ~8 person-months ~ $118k with 1.3x overhead "
        "(BLS $135,980), spread evenly over Y2-Y3. ESTIMATE"),
    "data_pool_storage": (160, "USD/month from model year 3 (COGS)",
        "DATA-REVENUE-STRATEGY.md Part C: 50 TB tiered 10% hot / 90% deep archive ~ $115 + $45 = $160/month. ESTIMATE"),
}

# ---- PRE-PHASE cost lines (before the seed). NOK unless stated. ALL ESTIMATE; owner decides; MUST BE QUOTED where noted.
PRE = {
    "founder_stipend_nok": (25_000, "NOK/month, all-in company cost",
        "ESTIMATE: owner decides (could be 0); incl. employer charges; no rate sourced"),
    "contractor_fte": ({"lean": 0.10, "small_team": 0.50}, "FTE of one contractor",
        "ESTIMATE: lean = ~2 days/month of specialist help; small team = one contractor at half time"),
    "contractor_cost_basis": ("BLS SWE median $135,980 x 1.03 x 1.30 / 12 per FTE-month",
        "USD", "BLS (grade A) x ESTIMATE inflation/loading; contractor day-rates not sourced"),
    "ai_tools_usd": ({"lean": 300, "small_team": 450}, "USD/month",
        "ESTIMATE: AI coding/assistant seats + code hosting + misc SaaS; no prices opened"),
    "accounting_nok": (3_000, "NOK/month", "ESTIMATE: regnskapsfører/bookkeeping; must be quoted"),
    "infra_usd": ({"lean": (25, 500), "small_team": (25, 1_050)}, "USD/month (months 1-3, month 4+)",
        "BLUEPRINT §12.1: M1 website-only band $0-50 (midpoint $25) for months 1-3; then pilot band $500-1,600 "
        "(lean = low end $500, small team = midpoint $1,050). ESTIMATE"),
    "one_offs_nok": ({1: ("AS set-up, registration, bank (fees UNVERIFIED)", 10_000),
                      2: ("initial trademark clearance search (MUST BE QUOTED)", 20_000),
                      4: ("first privacy-counsel review (MUST BE QUOTED)", 60_000)}, "NOK in model month",
        "ESTIMATE: essential assurance only (ROUND-ASSUMPTIONS 'Runway'); no prices opened"),
}

# ---- NON-DILUTIVE (pre-phase runway table only; conditional; NOT guaranteed) --------------
GRANTS = {
    "in_oppstart1_nok": (150_000, "NOK, received month 5",
        "innovasjonnorge.no/tjeneste/oppstartstilskudd-1 (via DATA-REVENUE-STRATEGY.md Sources, grade B): AS under 5 years, "
        "max NOK 150,000. Needs the AS to exist + approval. Payment month is ESTIMATE/UNVERIFIED"),
    "skattefunn_rate": (0.19, "of approved R&D costs",
        "forskningsradet.no/skattefunn (via DATA-REVENUE-STRATEGY.md Sources, grade B): '19 prosent av kostnadene'; "
        "company registered in Brreg and taxable in Norway; apply before 1 Sep; annual cap UNVERIFIED"),
    "skattefunn_eligible_share": (0.70, "of founder + contractor cost",
        "ESTIMATE: share of pre-phase personnel cost that is approved R&D"),
    "skattefunn_cash_month": (21, "model month when year-1 credit arrives",
        "ESTIMATE/UNVERIFIED: paid through the tax settlement (skatteoppgjør) the autumn AFTER the income year; "
        "month 21 assumes month 1 ~ January"),
    "forskningsradet_ipn": (0, "not modelled",
        "Forskningsrådet 'Innovasjonsprosjekt i næringslivet': page returned HTTP 404 on 2026-09-26 -> UNVERIFIED"),
}

SOM = {"S1": 15, "S2": 30, "S3": 60, "S4": 3, "ARR": 2_415_000}  # market/sizing.md §3


def v(a, k):
    return a[k][0]


# =====================================================================================
# 2. SCENARIOS (named overrides of A)
# =====================================================================================
def scale_list(xs, f):
    return [x * f for x in xs]


GROWTH = ("base", "bear", "bull")
LEAN = ("lean",)
UPSIDE = ("base+data_low", "base+data_mid", "base+data_high")


def make_scenario(name):
    a = copy.deepcopy(A)
    def put(k, val, why):
        a[k] = (val, a[k][1], f"{name.upper()} override: {why}")
    if name == "bear":
        put("build_months_after_seed", 10, "slower build")
        put("prephase_mode", "lean", "founder stays lean to stretch NOK 1M until a later seed")
        for s in ("S1", "S2", "S3", "S4"):
            put(f"adds_{s}", scale_list(v(A, f"adds_{s}"), 0.6), "gross adds x0.6")
            put(f"churn_{s}", v(A, f"churn_{s}") * 1.5, "churn x1.5")
        put("acv_S1_growth", 60_000, "S1 ACV toward low end of Growth band $50k-150k")
        put("s2_startup_share", 0.75, "more S2 logos stay on the cheap Startup tier")
        put("acv_S4_enterprise", 120_000, "S4 ACV toward low end of $100k-300k")
        put("expansion", 0.03, "weak expansion")
        put("services_engagements", scale_list(v(A, "services_engagements"), 0.6), "x0.6")
        put("infra_postlaunch", 7_500, "top of BLUEPRINT §12.1 band")
        put("marketing_programme", [25_000, 60_000, 120_000, 200_000, 300_000], "BOARD.md band low end")
        r = copy.deepcopy(v(A, "roles"))
        r["software_engineer"] = (1.00, "R&D", [2, 4, 5, 6, 7])
        r["neuro_data_scientist"] = (1.00, "R&D", [1, 1, 1, 2, 2])
        r["devops_security"] = (1.10, "R&D", [0, 1, 1, 1, 1])
        r["product_designer"] = (0.85, "R&D", [0, 0, 1, 1, 1])
        r["regulatory_qa"] = (1.00, "R&D", [0, 1, 1, 1, 1])
        r["account_exec"] = (0.90, "S&M", [0, 1, 1, 2, 2])
        r["customer_success"] = (0.85, "S&M", [0, 1, 1, 2, 2])
        r["marketing_devrel"] = (0.90, "S&M", [0, 1, 1, 1, 2])
        r["g_and_a_ops"] = (0.60, "G&A", [0, 0, 1, 1, 1])
        put("roles", r, "slower hiring matched to weaker revenue")
        put("funding", [("pre-seed/angel NOK 1M", 1, nok(1_000_000)),
                        ("seed N1 NOK 10M @ NOK 40M pre", 14, nok(10_000_000)),
                        ("round N2 USD 2.5M", 32, 2_500_000),
                        ("Series A USD 7M", 50, 7_000_000)], "later seed after a lean pre-phase; smaller, later rounds")
    elif name == "bull":
        put("build_months_after_seed", 7, "faster build")
        for s in ("S1", "S2", "S3", "S4"):
            put(f"adds_{s}", scale_list(v(A, f"adds_{s}"), 1.4), "gross adds x1.4")
            put(f"churn_{s}", v(A, f"churn_{s}") * 0.75, "churn x0.75")
        put("acv_S1_growth", 90_000, "S1 ACV higher in the Growth band")
        put("acv_S4_enterprise", 200_000, "S4 ACV mid-band")
        put("expansion", 0.12, "strong expansion")
        put("services_engagements", scale_list(v(A, "services_engagements"), 1.3), "x1.3")
        put("infra_postlaunch", 3_000, "low end of BLUEPRINT §12.1 band")
        put("marketing_programme", [60_000, 150_000, 300_000, 500_000, 750_000], "BOARD.md band high end")
        r = copy.deepcopy(v(A, "roles"))
        r["software_engineer"] = (1.00, "R&D", [3, 6, 9, 12, 15])
        r["neuro_data_scientist"] = (1.00, "R&D", [1, 2, 2, 3, 4])
        r["devops_security"] = (1.10, "R&D", [0, 1, 2, 2, 3])
        r["product_designer"] = (0.85, "R&D", [0, 1, 1, 2, 2])
        r["regulatory_qa"] = (1.00, "R&D", [0, 1, 2, 2, 3])
        r["account_exec"] = (0.90, "S&M", [0, 1, 3, 4, 6])
        r["customer_success"] = (0.85, "S&M", [0, 1, 2, 4, 6])
        r["marketing_devrel"] = (0.90, "S&M", [0, 1, 2, 3, 4])
        r["g_and_a_ops"] = (0.60, "G&A", [0, 1, 1, 2, 3])
        put("roles", r, "faster hiring funded by larger rounds")
        put("funding", [("pre-seed/angel NOK 1M", 1, nok(1_000_000)),
                        ("seed N1 NOK 10M @ NOK 40M pre", 8, nok(10_000_000)),
                        ("round N2 USD 5.0M", 20, 5_000_000),
                        ("Series A USD 18M", 36, 18_000_000)], "earlier seed, larger later rounds")
    elif name == "lean":
        put("prephase_mode", "lean", "founder-led: owner + AI tooling + light contractors, minimal cloud, all 60 months")
        put("funding", [("pre-seed/angel NOK 1M", 1, nok(1_000_000))], "NOK 1M only; no seed, no hires")
        put("services_engagements", [2, 4, 4, 4, 4],
            "ESTIMATE: founder-run audits only (~1 per quarter); unvalidated; no subscription product launched")
    elif name.startswith("base+data_"):
        level = name.split("_", 1)[1]
        if level not in v(A, "data_revenue"):
            raise ValueError(name)
        put("data_scenario", level, f"base + data-asset revenue '{level}' (DATA-REVENUE-STRATEGY.md Part C). UPSIDE")
    elif name != "base":
        raise ValueError(name)
    return a


# =====================================================================================
# 3. ENGINE
# =====================================================================================
SEGS = ("S1", "S2", "S3", "S4")


def acv(a, s):
    if s == "S1":
        return v(a, "acv_S1_growth")
    if s == "S2":
        sh = v(a, "s2_startup_share")
        return sh * v(a, "acv_S2_startup_tier") + (1 - sh) * v(a, "acv_S2_volume_tier")
    if s == "S3":
        return v(a, "acv_S3_lab")
    return v(a, "acv_S4_enterprise")


def contractor_month_usd(fte):
    return fte * PRE_BLS_MONTH


PRE_BLS_MONTH = A["swe_base_salary"][0] * 1.03 * 1.30 / 12   # USD per contractor FTE-month (see PRE)


def prephase_month(mode, m):
    """Pre-phase cost in USD for model month m (no revenue, no grants). Returns (total, parts)."""
    parts = {
        "founder_stipend": nok(PRE["founder_stipend_nok"][0]),
        "contractor": contractor_month_usd(PRE["contractor_fte"][0][mode]),
        "ai_tools": PRE["ai_tools_usd"][0][mode],
        "accounting": nok(PRE["accounting_nok"][0]),
        "infra": PRE["infra_usd"][0][mode][0 if m <= 3 else 1],
        "one_off": nok(PRE["one_offs_nok"][0][m][1]) if m in PRE["one_offs_nok"][0] else 0.0,
    }
    return sum(parts.values()), parts


def seed_month(a):
    f = v(a, "funding")
    return f[1][1] if len(f) > 1 else 10 ** 9


def run(a, funding_override=None):
    S_M = seed_month(a) if funding_override is None else seed_month({"funding": (funding_override,)})
    L = S_M + v(a, "build_months_after_seed")
    mode = v(a, "prephase_mode")
    roles = v(a, "roles")
    heads = {r: 0 for r in roles}
    logos = {s: 0.0 for s in SEGS}
    arr = {s: 0.0 for s in SEGS}
    dp_cohorts = []
    dp_total = 0.0
    cash = v(a, "opening_cash")
    fund_list = funding_override if funding_override is not None else v(a, "funding")
    funding = {m: (n, amt) for n, m, amt in fund_list}
    years = []
    Y = None
    min_cash = (float("inf"), 0)
    first_negative = None
    monthly = []
    last_net_burn = 0.0
    lvl = v(a, "data_scenario")
    for m in range(1, 61):
        y = (m - 1) // 12
        if (m - 1) % 12 == 0:
            Y = {k: 0.0 for k in ("sub_rev", "svc_rev", "revenue", "cogs", "rd", "sm", "ga", "mkt",
                                  "assurance", "ebitda", "raised", "new_list_arr", "dp_discount_rev", "data_rev",
                                  "prephase_cost")}
            Y["rounds"] = []
            Y["burn_months"] = []
            Y["hires"] = 0
        infl = (1 + v(a, "salary_inflation")) ** (y + 1)
        load = v(a, "loading_factor")
        def head_cost(r):
            return roles[r][0] * v(a, "swe_base_salary") * infl * load / 12
        # --- funding arrives at the start of the month (so hiring can use it)
        raised = 0.0
        if m in funding:
            raised = funding[m][1]
            Y["rounds"].append(f"{funding[m][0]} ${funding[m][1]/1e6:.2f}M (m{m})")
        cash += raised
        post_seed = m >= S_M
        # --- cash-gated hiring (only after the seed)
        new_hires = 0
        if post_seed:
            frac = ((m - 1) % 12 + 1) / 12
            for r, (_mult, _b, plan) in roles.items():
                prev = plan[y - 1] if y > 0 else 0
                target = int(prev + (plan[y] - prev) * frac + 1e-9)
                while heads[r] < target:
                    projected = last_net_burn + head_cost(r) + v(a, "tools_per_head") / 12
                    if projected > 0 and cash < v(a, "hiring_gate_months") * projected:
                        break
                    heads[r] += 1
                    new_hires += 1
                    last_net_burn += head_cost(r) + v(a, "tools_per_head") / 12
        Y["hires"] += new_hires
        # --- customers
        new_list = 0.0
        if m >= L:
            ly = min((m - L) // 12, 4)
            for s in SEGS:
                c_m = 1 - (1 - v(a, f"churn_{s}")) ** (1 / 12)
                e_m = (1 + v(a, "expansion")) ** (1 / 12) - 1
                add = v(a, f"adds_{s}")[ly] / 12
                logos[s] = logos[s] * (1 - c_m) + add
                arr[s] = arr[s] * (1 - c_m + e_m) + add * acv(a, s)
                if s != "S3":
                    new_list += add * acv(a, s)
                if s == "S1" and dp_total < v(a, "design_partners"):
                    n = min(add, v(a, "design_partners") - dp_total)
                    dp_total += n
                    dp_cohorts.append((m, n))
        c1 = 1 - (1 - v(a, "churn_S1")) ** (1 / 12)
        discount_arr = sum(n * (1 - c1) ** (m - st) * v(a, "acv_S1_growth") * v(a, "design_partner_discount")
                           for st, n in dp_cohorts if m - st < v(a, "design_partner_months"))
        list_arr = sum(arr.values())
        billed_arr = list_arr - discount_arr
        sub_rev = billed_arr / 12
        svc = 0.0
        if m >= v(a, "services_start_month"):
            months_active_this_year = 12 - max(0, v(a, "services_start_month") - (12 * y + 1))
            svc = v(a, "services_engagements")[y] * v(a, "services_avg_fee") / months_active_this_year
        data = v(a, "data_revenue")[lvl][y] / 12 if lvl else 0.0
        rev = sub_rev + svc + data
        # --- costs
        cogs_staff = 0.0
        bucket = {"R&D": 0.0, "S&M": 0.0, "G&A": 0.0}
        for r, (_mult, b, _plan) in roles.items():
            c = heads[r] * head_cost(r)
            share = v(a, "cs_cogs_share") if r == "customer_success" else (
                v(a, "devops_cogs_share") if r == "devops_security" else 0.0)
            cogs_staff += c * share
            bucket[b] += c * (1 - share)
        n_emp = sum(heads.values())
        pre_cost = 0.0
        if post_seed:
            infra = v(a, "infra_postlaunch") if m >= L else v(a, "infra_prelaunch")
            founder = v(a, "founder_salary")[y] * load / 12
            ga = (bucket["G&A"] + founder + v(a, "ga_fixed")[y] / 12 + new_hires * v(a, "recruiting_per_hire")
                  + (n_emp + 1) * v(a, "tools_per_head") / 12 + (v(a, "insurance") / 12 if (y + 1) * 12 >= L else 0.0))
            assurance = (v(a, "privacy_counsel")[y] + v(a, "regulatory_consultant")[y]
                         + v(a, "soc2")[y] + v(a, "pen_test")[y]) / 12
            mkt = v(a, "marketing_programme")[y] / 12
            rd = bucket["R&D"]
        else:
            pre_cost, parts = prephase_month(mode, m)
            infra = parts["infra"]
            rd = parts["contractor"] + parts["ai_tools"]
            ga = parts["founder_stipend"] + parts["accounting"]
            assurance = parts["one_off"]
            mkt = 0.0
        infra += v(a, "infra_variable") * sub_rev + v(a, "single_tenant_per_S4") * logos["S4"]
        cogs = infra + v(a, "services_delivery_cost") * svc + cogs_staff
        if lvl:
            cogs += v(a, "data_direct_cost_share") * data + (v(a, "data_pool_storage") if y >= 2 else 0.0)
            rd += v(a, "data_pool_build")[y] / 12
        sm = bucket["S&M"] + v(a, "commission_rate") * new_list
        ebitda = rev - cogs - rd - sm - mkt - ga - assurance
        last_net_burn = -ebitda
        cash += ebitda
        if cash < min_cash[0]:
            min_cash = (cash, m)
        if cash < 0 and first_negative is None:
            first_negative = m
        monthly.append({"m": m, "arr": billed_arr, "logos": sum(logos.values()), "cash": cash,
                        "heads": n_emp + 1, "net_burn": -ebitda})
        for k, val in (("sub_rev", sub_rev), ("svc_rev", svc), ("revenue", rev), ("cogs", cogs), ("rd", rd),
                       ("sm", sm), ("ga", ga), ("mkt", mkt), ("assurance", assurance), ("ebitda", ebitda),
                       ("raised", raised), ("new_list_arr", new_list),
                       ("dp_discount_rev", discount_arr / 12), ("data_rev", data), ("prephase_cost", pre_cost)):
            Y[k] += val
        Y["burn_months"].append(-ebitda)
        if m % 12 == 0:
            Y["year"] = y + 1
            Y["arr_end"] = billed_arr
            Y["list_arr_end"] = list_arr
            Y["arr_end_incl_data"] = billed_arr + data * 12
            Y["logos"] = {s: logos[s] for s in SEGS}
            Y["logos_total"] = sum(logos.values())
            Y["cash_end"] = cash
            Y["heads"] = dict(heads, founder=1)
            Y["headcount"] = n_emp + 1
            Y["gross_margin"] = (Y["revenue"] - Y["cogs"]) / Y["revenue"] if Y["revenue"] else None
            Y["opex"] = Y["rd"] + Y["sm"] + Y["mkt"] + Y["ga"] + Y["assurance"]
            Y["net_burn"] = -Y["ebitda"]
            recent = sum(Y["burn_months"][-3:]) / 3
            Y["runway_months"] = (cash / recent) if recent > 0 and cash > 0 else (0.0 if cash <= 0 else None)
            years.append(Y)
    cum = 0.0
    for Y in years:
        cum += Y["net_burn"]
        Y["cum_burn"] = cum
    years[0]["monthly"] = monthly
    years[0]["launch_month"] = L
    years[0]["seed_month"] = S_M
    years[0]["first_negative"] = first_negative
    return years, min_cash


def round_deadline(a, k):
    """Month in which cash first goes negative if only the first k rounds arrive (= round k+1 must close by then).
    Hiring in this counterfactual is also cash-gated."""
    f = list(v(a, "funding"))[:k]
    if k == 1:
        f.append(("(no seed)", 10 ** 9, 0.0))
    ys, _ = run(a, funding_override=f)
    return ys[0]["first_negative"]


# =====================================================================================
# 4. PRE-PHASE RUNWAY (NOK 1M, month by month; lean vs small team; with/without grants)
# =====================================================================================
def prephase_runway(mode, grants, months=36):
    cash = nok(1_000_000)
    rows = []
    sf_base = 0.0
    out_month = None
    for m in range(1, months + 1):
        cost, parts = prephase_month(mode, m)
        grant = 0.0
        if grants:
            if m == 5:
                grant += nok(GRANTS["in_oppstart1_nok"][0])
            if m <= 12:
                sf_base += GRANTS["skattefunn_eligible_share"][0] * (parts["founder_stipend"] + parts["contractor"])
            if m == GRANTS["skattefunn_cash_month"][0]:
                grant += GRANTS["skattefunn_rate"][0] * sf_base
        cash += grant - cost
        rows.append((m, cost * FX, grant * FX, cash * FX))
        if cash < 0 and out_month is None:
            out_month = m
    return rows, out_month


def months_lasted(out_month):
    return (out_month - 1) if out_month else ">36"


# =====================================================================================
# 5. OUTPUTS
# =====================================================================================
def fm(x):
    if x is None:
        return "n/a"
    return f"{x/1e6:,.2f}M" if abs(x) >= 1e5 else f"{x/1e3:,.0f}k"


def summary(name, years, min_cash, a):
    y0 = years[0]
    sm = y0["seed_month"] if y0["seed_month"] <= 60 else "none"
    lm = y0["launch_month"] if y0["launch_month"] <= 60 else "none"
    print(f"\n=== {name.upper()} (pre-phase {v(a,'prephase_mode')}; seed month {sm}; paid launch month {lm}) ===")
    print(f"{'metric':<26}" + "".join(f"{'Y'+str(y['year']):>11}" for y in years))
    rows = [("End ARR (billed)", lambda y: fm(y["arr_end"])),
            ("End ARR (list)", lambda y: fm(y["list_arr_end"])),
            ("Recognised revenue", lambda y: fm(y["revenue"])),
            ("  of which services", lambda y: fm(y["svc_rev"])),
            ("  DP discount given", lambda y: fm(y["dp_discount_rev"])),
            ("  of which data asset", lambda y: fm(y["data_rev"])),
            ("End ARR incl. data", lambda y: fm(y["arr_end_incl_data"])),
            ("COGS", lambda y: fm(y["cogs"])),
            ("Gross margin", lambda y: "n/a" if y["gross_margin"] is None else f"{y['gross_margin']*100:.0f}%"),
            ("Opex R&D", lambda y: fm(y["rd"])),
            ("Opex S&M (people+comm)", lambda y: fm(y["sm"])),
            ("Opex marketing prog.", lambda y: fm(y["mkt"])),
            ("Opex G&A", lambda y: fm(y["ga"])),
            ("Opex assurance (quote!)", lambda y: fm(y["assurance"])),
            ("EBITDA", lambda y: fm(y["ebitda"])),
            ("Net burn", lambda y: fm(y["net_burn"])),
            ("Cumulative burn", lambda y: fm(y["cum_burn"])),
            ("Equity raised", lambda y: fm(y["raised"])),
            ("Year-end cash", lambda y: fm(y["cash_end"])),
            ("Runway (months)", lambda y: "CF+" if y["runway_months"] is None else f"{y['runway_months']:.0f}"),
            ("Headcount (EoY, incl. founder)", lambda y: str(y["headcount"])),
            ("Logos S1/S2/S3/S4", lambda y: " " + "/".join(str(round(y["logos"][s])) for s in SEGS))]
    for label, f in rows:
        print(f"{label:<26}" + "".join(f"{f(y):>11}" for y in years))
    for y in years:
        if y["rounds"]:
            print(f"  Y{y['year']} rounds: " + "; ".join(y["rounds"]))
    print(f"  Minimum cash: {fm(min_cash[0])} in month {min_cash[1]}"
          + ("  <-- FUNDING GAP" if min_cash[0] < 0 else ""))


def sanity(name, years):
    issues = []
    for y in years:
        if any(h < 0 for h in y["heads"].values()):
            issues.append(f"Y{y['year']} negative headcount")
        gm = y["gross_margin"]
        if gm is not None and y["year"] >= 3 and not (0.5 <= gm <= 0.9):
            issues.append(f"Y{y['year']} gross margin {gm:.0%} outside 50-90%")
    return issues


def write_csv(path, all_results):
    with open(path, "w", newline="", encoding="utf-8") as f:
        f.write("# ALL VALUES ARE ESTIMATE (pre-product; no customers, revenue or commitments). "
                f"Generated by financial-model.py; see its ASSUMPTIONS section for sources. USD. FX {FX} NOK/USD "
                "(Norges Bank 2026-09-25).\n")
        w = csv.writer(f)
        w.writerow(["scenario", "year", "metric", "value"])
        for name, (years, _mc) in all_results.items():
            for y in years:
                rows = [("arr_end_billed", y["arr_end"]), ("arr_end_list", y["list_arr_end"]),
                        ("revenue_recognised", y["revenue"]), ("revenue_subscription", y["sub_rev"]),
                        ("revenue_services", y["svc_rev"]), ("design_partner_discount", y["dp_discount_rev"]),
                        ("cogs", y["cogs"]), ("gross_margin_pct",
                                              None if y["gross_margin"] is None else y["gross_margin"] * 100),
                        ("opex_rd", y["rd"]), ("opex_sm_people_commission", y["sm"]),
                        ("opex_marketing_programme", y["mkt"]), ("opex_ga", y["ga"]),
                        ("opex_assurance_must_be_quoted", y["assurance"]), ("opex_total", y["opex"]),
                        ("prephase_cost", y["prephase_cost"]),
                        ("ebitda", y["ebitda"]), ("net_burn", y["net_burn"]), ("cumulative_burn", y["cum_burn"]),
                        ("equity_raised", y["raised"]), ("cash_end", y["cash_end"]),
                        ("runway_months", "cash-flow-positive" if y["runway_months"] is None else y["runway_months"]),
                        ("headcount_end", y["headcount"]), ("logos_total", y["logos_total"])]
                rows += [(f"logos_{s}", y["logos"][s]) for s in SEGS]
                rows += [(f"heads_{r}", h) for r, h in y["heads"].items()]
                if name.startswith("base+data_"):
                    rows += [("revenue_data_asset_UPSIDE", y["data_rev"]),
                             ("arr_end_incl_data_UPSIDE", y["arr_end_incl_data"])]
                for k, val in rows:
                    if isinstance(val, float):
                        val = round(val, 2)
                    w.writerow([name, y["year"], k, val])


def sensitivity():
    """One-at-a-time swings on the base case."""
    base_years, _ = run(make_scenario("base"))
    base_arr5 = base_years[4]["arr_end"]
    base_cash5 = base_years[4]["cash_end"]
    tests = []
    def t(label, mutate):
        a = make_scenario("base")
        mutate(a)
        ys, mc = run(a)
        tests.append((label, ys[4]["arr_end"] - base_arr5, ys[4]["cash_end"] - base_cash5))
    def setk(k, val):
        return lambda a: a.__setitem__(k, (val, a[k][1], a[k][2]))
    t("S1 gross adds -30%", setk("adds_S1", scale_list(v(A, "adds_S1"), 0.7)))
    t("S1 ACV $75k -> $50k", setk("acv_S1_growth", 50_000))
    t("Build 6 months longer", setk("build_months_after_seed", v(A, "build_months_after_seed") + 6))
    t("All churn x2", lambda a: [a.__setitem__(f"churn_{s}", (v(A, f"churn_{s}") * 2, "", "")) for s in SEGS])
    t("Loading 1.30 -> 1.45", setk("loading_factor", 1.45))
    t("S2 all on Startup tier", setk("s2_startup_share", 1.0))
    t("S4 adds zero", setk("adds_S4", [0, 0, 0, 0, 0]))
    t("Expansion 8% -> 0%", setk("expansion", 0.0))
    tests.sort(key=lambda r: r[2])
    print("\n=== SENSITIVITY (base case, one at a time) ===")
    print(f"{'change':<26}{'dY5 ARR':>12}{'dY5 cash':>13}")
    for label, d_arr, d_cash in tests:
        print(f"{label:<26}{fm(d_arr):>12}{fm(d_cash):>13}")
    return tests


def prephase_report(here):
    print(f"\n=== PRE-PHASE: how far NOK 1,000,000 goes (NOK; FX {FX} NOK/USD Norges Bank 2026-09-25) ===")
    print("Lean = founder stipend + AI tools + contractor 0.1 FTE + minimal cloud; small team = founder + contractor 0.5 FTE.")
    print("Grants = Innovation Norway oppstartstilskudd 1 NOK 150k (month 5) + SkatteFUNN 19% of year-1 eligible cost "
          f"(cash month {GRANTS['skattefunn_cash_month'][0]}, via tax settlement). CONDITIONAL, NOT GUARANTEED.")
    cases = [(md, g) for md in ("lean", "small_team") for g in (False, True)]
    res = {c: prephase_runway(*c) for c in cases}
    print(f"{'month':>5} " + " ".join(f"{(md + (' +grants' if g else '')):>19}" for md, g in cases)
          + "   (cash at month end, NOK)")
    for i in range(24):
        print(f"{i+1:>5} " + " ".join(f"{res[c][0][i][3]:>19,.0f}" for c in cases))
    print(f"{'monthly run-rate (m6)':<22}" + " ".join(f"{res[c][0][5][1]:>12,.0f}" for c in cases))
    for c in cases:
        print(f"  {c[0]:<10} {'with grants' if c[1] else 'no grants  '}: NOK 1M lasts {months_lasted(res[c][1])} months")
    path = os.path.join(here, "prephase-runway.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        fh.write(f"# ALL VALUES ESTIMATE. NOK. FX {FX} NOK/USD (Norges Bank 2026-09-25). Grants conditional on the AS "
                 "existing and on approval; SkatteFUNN cash via tax settlement (month UNVERIFIED).\n")
        w = csv.writer(fh)
        w.writerow(["mode", "grants", "month", "cost_nok", "grant_in_nok", "cash_end_nok"])
        for c in cases:
            for m, cost, grant, cash in res[c][0]:
                w.writerow([c[0], "yes" if c[1] else "no", m, round(cost), round(grant), round(cash)])
    print(f"Wrote {path}")
    return {c: months_lasted(res[c][1]) for c in cases}


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    print("NeuroForge Bio financial model. ALL FIGURES ARE ESTIMATES (pre-product).")
    print(f"FX {FX} NOK/USD (Norges Bank, 2026-09-25). First round = NOK 1M pre-seed/angel = USD {nok(1e6):,.0f}.")
    runway = prephase_report(here)
    results = {}
    for name in GROWTH + LEAN + UPSIDE:
        a = make_scenario(name)
        years, mc = run(a)
        results[name] = (years, mc)
        summary(name, years, mc, a)
        if name in GROWTH:
            fl = v(a, "funding")
            for k in range(1, len(fl)):
                d = round_deadline(a, k)
                print(f"  Deadline for '{fl[k][0]}': cash < 0 in month {d if d else 'none <= 60'} without it; "
                      f"assumed month {fl[k][1]}.")
        for issue in sanity(name, years):
            print(f"  SANITY: {issue}")
    b = results["base"][0]
    L = b[0]["launch_month"]
    print("\n=== SOM CHECK (market/sizing.md §3: ~$2.4M ARR, 108 logos, 'year 3 after launch') ===")
    if L + 35 <= 60:
        mm = b[0]["monthly"][L + 35 - 1]
        print(f"  36 months after launch = model month {mm['m']}: ARR {fm(mm['arr'])}, "
              f"logos {round(mm['logos'])} vs SOM {fm(SOM['ARR'])} / 108")
    else:
        print(f"  Launch month {L}: 36 months after launch falls after month 60; Y5 ARR {fm(b[4]['arr_end'])}.")
    sensitivity()
    out = os.path.join(here, "financial-model.csv")
    write_csv(out, results)
    print(f"\nWrote {out}")
    return runway


if __name__ == "__main__":
    main()
