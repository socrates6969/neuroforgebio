"""Dilution tables for NeuroForge Bio's pre-seed round (NOK 1M) and the following seed round.

DRAFT. Not legal or financial advice. ALL VALUATIONS ARE ESTIMATES (pre-product company).
Single source of truth for inputs: C:\\Users\\mariu\\neuro-company\\investor\\ROUND-ASSUMPTIONS.md
ASSUMPTION: NeuroForge Bio will be a Norwegian AS under aksjeloven; not yet incorporated.
Stdlib only. Run: python dilution.py

Conventions:
- S0 = founder shares before the round (placeholder; the percentages do not depend on it).
- Priced round: investor % = A / (pre + A).
- Seed round (ROUND-ASSUMPTIONS "Cap table"): new money X at pre-money V. A 10 % option pool is created
  PRE-MONEY at the seed. Interpretation used here: the pool is 10 % of the fully diluted capital AFTER the seed,
  and its shares are counted in the pre-money, so only the existing holders are diluted by it (seed investors
  are not). Then, for existing holders E (founder + pre-seed investor + converted shares):
      N/T = X/(V+X),  P/T = 0.10,  E/T = V/(V+X) - 0.10,  seed price p = (V+X)/T.
- Convertible / warrant cap price = cap / shares outstanding immediately before the seed, EXCLUDING the new pool.
- Convertible discount price = (1 - d) * seed price p; p itself depends on the conversion shares, so it is solved
  by fixed-point iteration.
- Convertible amount = principal + simple interest for the full maturity of 24 months (ROUND-ASSUMPTIONS (b)).
"""

import os

A = 1_000_000                    # NOK, pre-seed amount
S0 = 1_000_000                   # founder shares (placeholder)
PRE_GRID = [4e6, 6e6, 8e6, 10e6, 15e6, 20e6]
POOL = 0.10                      # option pool created pre-money at the seed
FX = 9.5063                      # NOK/USD, Norges Bank spot 2026-09-25 (ROUND-ASSUMPTIONS 'FINANCE:' note)
SEEDS = [                        # (label, X new money, V pre-money)
    ("N1 NOK 10M @ NOK 40M pre", 10e6, 40e6),
    ("N2 USD 4M (NOK 38.0M) @ NOK 120M pre", 4e6 * FX, 120e6),
    ("Stress NOK 10M @ NOK 10M pre", 10e6, 10e6),
    ("Stress NOK 10M @ NOK 20M pre", 10e6, 20e6),
    ("Stress NOK 10M @ NOK 40M pre", 10e6, 40e6),
]
SEED_IDS = ["N1", "N2", "S10", "S20", "S40"]   # same ids as investor/dilution.csv
CAP, DISC, RATE, MONTHS = 12e6, 0.20, 0.05, 24
W_PRE, W_AMOUNT, W_CAP = 8e6, 1_000_000, 20e6   # warrant structure (ROUND-ASSUMPTIONS (c))
E_AMOUNT, E_PRES = 500_000, [8e6, 10e6]           # smaller stake + pro-rata (ROUND-ASSUMPTIONS (d))
SERIES_A_USD, SERIES_A_PRE_USD = 12e6, 36e6         # later Series A (investor/dilution.py base ESTIMATE)


def pct(x):
    return f"{round(100 * x + 1e-9, 2):.2f} %"   # round() as in investor\dilution.py


def seed(existing, X, V):
    """existing: dict holder -> shares before seed. Returns (dict of % after seed incl. pool and seed, price)."""
    E = sum(existing.values())
    T = E / (V / (V + X) - POOL)
    out = {k: v / T for k, v in existing.items()}
    out["pool"] = POOL
    out["seed"] = X / (V + X)
    return out, (V + X) / T


def table_a():
    print("## (a) Priced share issue, NOK 1M, then seed (10 % pool pre-money at seed)")
    print("| Pre-money | Post-money | Investor % | Owner % after pre-seed | Owner % after N1 | Owner % after N2 |")
    print("|---|---|---|---|---|---|")
    for pre in PRE_GRID:
        inv_sh = A / (pre / S0)
        ex = {"owner": S0, "inv": inv_sh}
        o1 = seed(ex, SEEDS[0][1], SEEDS[0][2])[0]["owner"]
        o2 = seed(ex, SEEDS[1][1], SEEDS[1][2])[0]["owner"]
        print(f"| NOK {pre/1e6:g}M | NOK {(pre+A)/1e6:g}M | {pct(A/(pre+A))} | {pct(pre/(pre+A))} | {pct(o1)} | {pct(o2)} |")
    print()


def seed_rows(existing_fn):
    rows = []
    for label, X, V in SEEDS:
        rows.append((label, *existing_fn(X, V)))
    return rows


def conv_existing(amount, X, V, cap=CAP, d=DISC):
    c_cap = amount * S0 / cap
    c = c_cap
    for _ in range(200):  # fixed point for the discount price
        _, p = seed({"owner": S0, "inv": c}, X, V)
        c_disc = amount / ((1 - d) * p)
        c_new = max(c_cap, c_disc)
        if abs(c_new - c) < 1e-9:
            break
        c = c_new
    which = "cap" if c_cap >= c_disc - 1e-6 else "discount"
    return {"owner": S0, "inv": c}, which


def table_b():
    amt = A * (1 + RATE * MONTHS / 12)
    print(f"## (b) Convertible loan NOK 1M, {int(RATE*100)} % simple interest x {MONTHS} months = NOK {amt:,.0f} converts; "
          f"cap NOK {CAP/1e6:g}M pre-money; {int(DISC*100)} % discount; converts at the seed")
    print("| Seed | Price used | Lender % just before seed | Owner % after seed | Lender % after seed | Pool | Seed investors % |")
    print("|---|---|---|---|---|---|---|")
    for label, X, V in SEEDS:
        ex, which = conv_existing(amt, X, V)
        r, _ = seed(ex, X, V)
        print(f"| {label} | {which} | {pct(ex['inv']/(S0+ex['inv']))} | {pct(r['owner'])} | {pct(r['inv'])} | {pct(r['pool'])} | {pct(r['seed'])} |")
    print()
    print("Comparison, priced round (a) at NOK 10M pre (recommended) and NOK 8M pre, then the same seed:")
    print("| Seed | Owner % after seed, (a) @10M | Investor % | Owner % after seed, (a) @8M | Investor % |")
    print("|---|---|---|---|---|")
    for label, X, V in SEEDS:
        r10, _ = seed({"owner": S0, "inv": A * S0 / 10e6}, X, V)
        r8, _ = seed({"owner": S0, "inv": A * S0 / 8e6}, X, V)
        print(f"| {label} | {pct(r10['owner'])} | {pct(r10['inv'])} | {pct(r8['owner'])} | {pct(r8['inv'])} |")
    print()


def table_c_safe():
    print(f"## (s) SAFE-style (no interest; not in ROUND-ASSUMPTIONS), pre-money cap NOK {CAP/1e6:g}M, {int(DISC*100)} % discount (shown for comparison only)")
    print("| Seed | Price used | Investor % just before seed | Owner % after seed |")
    print("|---|---|---|---|")
    for label, X, V in SEEDS:
        ex, which = conv_existing(A, X, V)
        r, _ = seed(ex, X, V)
        print(f"| {label} | {which} | {pct(ex['inv']/(S0+ex['inv']))} | {pct(r['owner'])} |")
    print()


def table_warrant():
    price0 = W_PRE / S0
    inv0 = A / price0
    print(f"## (c) Warrant structure: NOK 1M at NOK {W_PRE/1e6:g}M pre + frittstående tegningsrett to invest up to NOK "
          f"{W_AMOUNT/1e6:g}M more in the seed at the lower of the seed price and a cap of NOK {W_CAP/1e6:g}M pre-money")
    print(f"After the pre-seed: owner {pct(S0/(S0+inv0))}, investor {pct(inv0/(S0+inv0))} (warrants unexercised).")
    print("| Seed | Warrant price used | Owner % after seed, warrant NOT exercised | Owner % after seed, warrant exercised | Extra owner dilution | Investor % (exercised) |")
    print("|---|---|---|---|---|---|")
    for label, X, V in SEEDS:
        base, _ = seed({"owner": S0, "inv": inv0}, X, V)
        r, which = warrant_result(inv0, X, V)
        print(f"| {label} | {which} | {pct(base['owner'])} | {pct(r['owner'])} | {round(100*(base['owner']-r['owner']),2):.2f} pp | {pct(r['inv'])} |")
    print("Note: exercise at the seed price itself only moves money in; the dilution cost appears when the cap applies"
          " (seed pre-money above NOK 20M on this basis) and when warrant shares are counted in the pre-money.")
    print()


def warrant_result(inv0, X, V):
    """Warrant shares W (exercise cash on top of X) are counted in the seed's fully diluted pre-money.
    Exercise price = min(cap price, seed price); the seed price depends on W, so iterate to a fixed point."""
    cap_price = W_CAP / (S0 + inv0)
    w_sh = 0.0
    for _ in range(500):
        _, p = seed({"owner": S0, "inv": inv0 + w_sh}, X, V)
        new = W_AMOUNT / min(cap_price, p)
        if abs(new - w_sh) < 1e-9:
            break
        w_sh = new
    r, p = seed({"owner": S0, "inv": inv0 + w_sh}, X, V)
    return r, ("cap" if cap_price < p else "seed price")


def check_against_finance():
    """Compare owner % after the next round with investor/dilution.csv (nfb-finance-ba). Prints mismatches."""
    import csv, os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "investor", "dilution.csv")
    if not os.path.exists(path):
        print("investor/dilution.csv not found; no cross-check.")
        return
    mine = {}
    for pre in PRE_GRID:
        for sid, (_, X, V) in zip(SEED_IDS, SEEDS):
            mine[(f"a{pre/1e6:g}", sid)] = seed({"owner": S0, "inv": A * S0 / pre}, X, V)[0]["owner"]
    amt = A * (1 + RATE * MONTHS / 12)
    for sid, (_, X, V) in zip(SEED_IDS, SEEDS):
        mine[("b", sid)] = seed(conv_existing(amt, X, V)[0], X, V)[0]["owner"]
        mine[("c", sid)] = warrant_result(A * S0 / W_PRE, X, V)[0]["owner"]
        for pre in E_PRES:
            mine[(f"d{pre/1e6:g}", sid)] = seed({"owner": S0, "inv": E_AMOUNT * S0 / pre}, X, V)[0]["owner"]
    n = bad = 0
    with open(path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            key = (row["option"], row["next_round"].split()[0])
            if key not in mine:
                continue
            n += 1
            if abs(round(100 * mine[key] + 1e-9, 2) - float(row["owner_pct_after_next"])) > 0.005:
                bad += 1
                print(f"MISMATCH {key}: legal {round(100*mine[key] + 1e-9, 2)} vs finance {row['owner_pct_after_next']}")
    print(f"Cross-check with investor/dilution.csv: {n} scenarios compared, {bad} mismatches (owner % after next round).")


def path_rows():
    """Sequential funding path (ROUND-ASSUMPTIONS 'FINANCE:' note): pre-seed -> N1 (pool 10 % created here)
    -> N2 USD 4.0M @ NOK 120M pre (no pool top-up) -> Series A USD 12M @ USD 36M pre. Returns (label, [4 owner fractions])."""
    X1, V1 = SEEDS[0][1], SEEDS[0][2]
    X2, V2 = SEEDS[1][1], SEEDS[1][2]
    amt = A * (1 + RATE * MONTHS / 12)
    cases = [
        ("(a) NOK 1M @ 8M pre", {"owner": S0, "inv": A * S0 / 8e6}, None),
        ("(a) NOK 1M @ 10M pre (recommended)", {"owner": S0, "inv": A * S0 / 10e6}, None),
        ("(b) convertible", None, "b"),
        ("(c) NOK 1M @ 8M pre + warrant", None, "c"),
        ("(d) NOK 500k @ 10M pre + pro-rata", {"owner": S0, "inv": E_AMOUNT * S0 / 10e6}, None),
    ]
    out = []
    for label, ex, kind in cases:
        if kind == "b":
            ex0 = {"owner": S0, "inv": 0.0}
            r1 = seed(conv_existing(amt, X1, V1)[0], X1, V1)[0]
        elif kind == "c":
            ex0 = {"owner": S0, "inv": A * S0 / W_PRE}
            r1 = warrant_result(A * S0 / W_PRE, X1, V1)[0]
        else:
            ex0 = ex
            r1 = seed(ex, X1, V1)[0]
        o0 = S0 / sum(ex0.values())
        o1 = r1["owner"]
        o2 = o1 * V2 / (V2 + X2)
        o3 = o2 * SERIES_A_PRE_USD / (SERIES_A_PRE_USD + SERIES_A_USD)
        out.append((label, [o0, o1, o2, o3]))
    return out


def table_path():
    print(f"## PATH: rounds in sequence (pre-seed -> N1 -> N2 USD 4.0M = NOK {SEEDS[1][1]/1e6:.1f}M @ NOK 120M pre -> "
          f"Series A USD 12M @ USD 36M pre); FX {FX} NOK/USD (Norges Bank 2026-09-25); pool 10 % created once, at N1")
    print("| Structure | Owner after pre-seed | after N1 | after N2 | after Series A |")
    print("|---|---|---|---|---|")
    for label, v in path_rows():
        print(f"| {label} | " + " | ".join(pct(x) for x in v) + " |")
    print()


def check_path_against_finance():
    """Runs investor/dilution.py and compares its PATH lines with path_rows() (tolerance 0.01 pp:
    finance chains 2-decimal rounded values)."""
    import subprocess, sys, re
    fin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "investor", "dilution.py")
    try:
        txt = subprocess.run([sys.executable, fin], capture_output=True, text=True, encoding="utf-8",
                             env={**os.environ, "PYTHONIOENCODING": "utf-8"}).stdout
    except Exception as e:  # pragma: no cover
        print(f"PATH cross-check not run: {e}")
        return
    lines = txt.split("PATH", 1)[-1].splitlines()
    fin_vals = [list(map(float, re.findall(r"([0-9.]+)%", ln)))[-4:] for ln in lines if ln.startswith("  (") and ln.count("->") == 3]
    mine = [v for _, v in path_rows()]
    bad = 0
    for a, b in zip(mine, fin_vals):
        for x, y in zip(a, b):
            if abs(100 * x - y) > 0.011:
                bad += 1
    print(f"PATH cross-check with investor/dilution.py: {len(fin_vals)} structures x 4 stages compared, {bad} differences > 0.01 pp.")


def table_e():
    print(f"## (d) Smaller stake + pro-rata: NOK {E_AMOUNT/1e3:g}k at NOK 8M or 10M pre, pro-rata right in the seed")
    print("| Pre-money | Investor % after pre-seed | Owner % after pre-seed | Seed | Pro-rata amount (NOK) | Owner % after seed |")
    print("|---|---|---|---|---|---|")
    for pre in E_PRES:
        inv = E_AMOUNT / (pre + E_AMOUNT)
        for label, X, V in SEEDS[:2]:
            r, _ = seed({"owner": S0, "inv": E_AMOUNT * S0 / pre}, X, V)
            print(f"| NOK {pre/1e6:g}M | {pct(inv)} | {pct(1-inv)} | {label} | {inv * X:,.0f} | {pct(r['owner'])} |")
    print("Pro-rata amount = investor's % before the seed x seed size, taken inside the fixed seed allocation: no extra owner dilution.")
    print()


if __name__ == "__main__":
    print("<!-- generated by legal\\financing\\dilution.py from investor\\ROUND-ASSUMPTIONS.md; ALL VALUES ESTIMATE -->\n")
    table_a()
    table_b()
    table_c_safe()
    table_warrant()
    table_e()
    table_path()
    check_against_finance()
    check_path_against_finance()
