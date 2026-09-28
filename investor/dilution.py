"""Owner dilution for NeuroForge Bio's first external round (NOK 1,000,000; a PRE-SEED / ANGEL round).

Author: nfb-finance-ba (AI draft for Marius Carlsson). EVERY VALUE IS AN ESTIMATE. Not financial or legal advice.
Owner decides; nothing is sent. Stdlib only.
Run:  C:\\Users\\mariu\\AppData\\Local\\Programs\\Python\\Python312\\python.exe dilution.py
Writes investor\\dilution.csv next to this file and prints a readable table.

Inputs come from investor\\ROUND-ASSUMPTIONS.md (shared with nfb-legal). Terms: pre-seed (this round, the owner's
"Series A") -> seed (next round, the owner's "Series B") -> Series A (later).

CONVENTIONS (read before relying on any number)
- Shares are counted "fully diluted". S0 = founder shares (placeholder 1,000,000; percentages do not depend on it).
- Priced round: new shares = A * S / pre; investor % = A / (pre + A).
- Next round (seed) with new money X at pre-money V. The pre-money is FULLY DILUTED and INCLUDES
  (i) a new option pool P sized to 10 % of the post-money cap table ("pool created pre-money"),
  (ii) convertible-loan conversion shares C, (iii) warrant shares W exercised at that round.
  Seed price p = V / (S + C + W + P). This is the usual seed-investor demand and the harder case for the owner
  (same convention as legal\\financing\\dilution.py). Solved by fixed-point iteration.
- Convertible loan: amount converted = principal * (1 + 5 % * years); years = 2.0 (24-month maturity; the seed
  is assumed to close at maturity -> ESTIMATE, the worst case for interest). Price = min(cap price, (1-20 %) * p).
  Cap price = CAP / S, where S = shares outstanding before the seed (excluding the new pool and conversion shares).
- Warrant (frittstående tegningsrett): up to NOK 1M exercised at the seed at price min(20M / S, p). Exercise cash is
  extra money on top of X. Seed investors count the warrant shares in their fully diluted pre-money.
- Pro-rata right: investor buys its % of X INSIDE a fixed seed size X, so the owner is not diluted further.
- Series A (later): USD 12M (financial-model.py). Pre-money ESTIMATE USD 36M (method: judgement that a Series A
  investor buys ~25 % of post-money; no market source opened). Stress: USD 24M. No further pool top-up modelled.
- FX: 9.5063 NOK/USD, Norges Bank USD/NOK spot 2026-09-25,
  https://data.norges-bank.no/api/data/EXR/B.USD.NOK.SP?format=csv&lastNObservations=1 (opened 2026-09-26, grade A).
  N2 = USD 4.0M = about NOK 38.0M at this rate (was NOK 42M at the earlier 10.5 ESTIMATE).
- FUNDING PATH (financial-model.py, corrected 2026-09-26): NOK 1M pre-seed -> N1 seed -> N2 -> Series A, in sequence.
  The table 'PATH' shows owner % along that sequence (pool created once, at N1).
"""
import csv
import os

A = 1_000_000.0            # NOK, this round
S0 = 1_000_000.0           # founder shares (placeholder)
FX = 9.5063                # NOK per USD, Norges Bank 2026-09-25 (grade A)
POOL = 0.10                # option pool, % of seed post-money, created pre-money (ESTIMATE)
PRE_GRID = [4e6, 6e6, 8e6, 10e6, 15e6, 20e6]
CAP, DISC, RATE, YEARS = 12e6, 0.20, 0.05, 2.0
W_AMT, W_CAP, W_PRE = 1e6, 20e6, 8e6
D_AMT, D_PRES = 500_000.0, [8e6, 10e6]
# Next-round scenarios (name, new money NOK, pre-money NOK). N1/N2 from ROUND-ASSUMPTIONS; S* = stress.
NEXT = [("N1 seed NOK10M@40M", 10e6, 40e6), ("N2 NOK38M(USD4.0M)@120M", 4.0e6 * FX, 120e6),
        ("S10 stress NOK10M@10M", 10e6, 10e6), ("S20 stress NOK10M@20M", 10e6, 20e6),
        ("S40 stress NOK10M@40M", 10e6, 40e6)]
SERIES_A_USD = 12e6
SERIES_A_PRE_USD = {"base": 36e6, "stress": 24e6}


def seed(S, founder, inv, X, V, conv=None, warrant=None, prorata=False):
    """Returns dict of fractions after the seed. conv = amount converting; warrant = (amount, cap)."""
    C = W = P = 0.0
    binds = ""
    for _ in range(500):
        p = V / (S + C + W + P)
        if conv:
            p_cap, p_disc = CAP / S, (1 - DISC) * p
            price, binds = (p_cap, "cap") if p_cap <= p_disc else (p_disc, "discount")
            C = conv / price
        if warrant:
            amt, wcap = warrant
            p_w = min(wcap / S, p)
            binds = "warrant cap" if wcap / S < p else "seed price (cap not binding)"
            W = amt / p_w
        N = X / p
        T = S + C + W + P + N
        P_new = POOL * T
        if abs(P_new - P) < 1e-6:
            break
        P = P_new
    inv_sh = inv + C + W + (inv / S * N if prorata else 0.0)
    return {"owner": founder / T, "investor": inv_sh / T, "pool": P / T, "seed_new": (N - (inv / S * N if prorata else 0)) / T,
            "price": p, "binds": binds}


def series_a(owner_after_seed, pre_usd):
    return owner_after_seed * pre_usd / (pre_usd + SERIES_A_USD)


def scenarios():
    """Yields (option_id, label, S, founder, inv_shares, amount_raised_now, kwargs_for_seed)."""
    for pre in PRE_GRID:
        inv = A * S0 / pre
        yield f"a{pre/1e6:g}", f"(a) priced NOK1M @ {pre/1e6:g}M pre", S0 + inv, S0, inv, A, {}
    yield "b", "(b) convertible NOK1M cap12M/20%/5%", S0, S0, 0.0, A, {"conv": A * (1 + RATE * YEARS)}
    inv = A * S0 / W_PRE
    yield "c", "(c) NOK1M @ 8M pre + warrant NOK1M @20M cap", S0 + inv, S0, inv, A, {"warrant": (W_AMT, W_CAP)}
    for pre in D_PRES:
        inv = D_AMT * S0 / pre
        yield f"d{pre/1e6:g}", f"(d) NOK500k @ {pre/1e6:g}M pre + pro-rata", S0 + inv, S0, inv, D_AMT, {"prorata": True}


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    rows = []
    for oid, label, S, f, inv, raised, kw in scenarios():
        owner_now = f / S
        inv_now = inv / S
        for nname, X, V in NEXT:
            r = seed(S, f, inv, X, V, **kw)
            row = {"option": oid, "label": label, "raised_now_nok": int(raised),
                   "owner_pct_after_round": round(100 * owner_now, 2),
                   "investor_pct_after_round": round(100 * inv_now, 2),
                   "next_round": nname, "next_new_money_nok": int(X), "next_pre_money_nok": int(V),
                   "binds": r["binds"],
                   "owner_pct_after_next": round(100 * r["owner"], 2),
                   "investor_pct_after_next": round(100 * r["investor"], 2),
                   "pool_pct_after_next": round(100 * r["pool"], 2)}
            for k, pre_usd in SERIES_A_PRE_USD.items():
                row[f"owner_pct_after_seriesA_{k}"] = round(100 * series_a(r["owner"], pre_usd), 2)
            row["status"] = "ESTIMATE"
            rows.append(row)
    path = os.path.join(here, "dilution.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print("NeuroForge Bio: first round (pre-seed / angel, NOK 1M). ALL VALUES ESTIMATE. Owner decides; nothing is sent.")
    print(f"FX {FX} NOK/USD (Norges Bank 2026-09-25; NOK 1M ~ USD {A/FX:,.0f}). Pool {POOL:.0%} created pre-money at the seed.")
    print(f"Series A later: USD {SERIES_A_USD/1e6:g}M at pre-money USD {SERIES_A_PRE_USD['base']/1e6:g}M (base ESTIMATE) / "
          f"{SERIES_A_PRE_USD['stress']/1e6:g}M (stress ESTIMATE).\n")
    names = [n for n, _, _ in NEXT]
    short = ["N1", "N2", "S10", "S20", "S40"]
    print(f"{'Option':46} {'Raised':>8} {'Own now':>8} {'Inv now':>8} | owner % after next round: " + " ".join(f"{s:>6}" for s in short))
    for oid, label, *_ in scenarios():
        rs = [r for r in rows if r["option"] == oid]
        r0 = rs[0]
        print(f"{label:46} {r0['raised_now_nok']:>8,} {r0['owner_pct_after_round']:>7.2f}% {r0['investor_pct_after_round']:>7.2f}% | "
              + " ".join(f"{r['owner_pct_after_next']:>5.2f}%" for r in rs))
    print("\nWhich price binds (b convertible; c warrant):")
    for r in rows:
        if r["option"] in ("b", "c"):
            print(f"  {r['option']} {r['next_round']:24} -> {r['binds']:30} investor % after next = {r['investor_pct_after_next']:.2f}%")
    print("\nOwner % after a later Series A (from N1 and N2 seed paths), base / stress pre-money:")
    for oid in ("a8", "a10", "b", "c", "d8", "d10"):
        for r in rows:
            if r["option"] == oid and r["next_round"].startswith(("N1", "N2")):
                print(f"  {r['label']:46} {r['next_round'][:2]}: {r['owner_pct_after_seriesA_base']:.2f}% / "
                      f"{r['owner_pct_after_seriesA_stress']:.2f}%")
    # PATH: pre-seed -> N1 -> N2 -> Series A in sequence (financial-model.py funding path)
    n2_new, n2_pre = 4.0e6 * FX, 120e6
    print(f"\nPATH (sequential, as in financial-model.py): owner % after pre-seed -> N1 NOK 10M @ 40M pre (pool 10%) "
          f"-> N2 NOK {n2_new/1e6:.1f}M (USD 4.0M) @ NOK 120M pre -> Series A USD {SERIES_A_USD/1e6:g}M @ USD "
          f"{SERIES_A_PRE_USD['base']/1e6:g}M pre (all ESTIMATE)")
    for oid in ("a8", "a10", "b", "c", "d10"):
        r = [x for x in rows if x["option"] == oid and x["next_round"].startswith("N1")][0]
        after_n2 = r["owner_pct_after_next"] * n2_pre / (n2_pre + n2_new)
        after_a = series_a(after_n2 / 100, SERIES_A_PRE_USD["base"]) * 100
        print(f"  {r['label']:46} {r['owner_pct_after_round']:6.2f}% -> {r['owner_pct_after_next']:6.2f}% -> "
              f"{after_n2:6.2f}% -> {after_a:6.2f}%")
    print(f"\nWrote {path} ({len(rows)} rows).")


if __name__ == "__main__":
    main()
