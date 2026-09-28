"""REVIEW N1b: C3' internal consistency from the card pmf (mass 1, mean = mu*, q95/q99/a* re-derived, criteria (i)/(ii)
and the PL-C trip recomputed) and agreement with the N1 review's independent enumeration (c3_analytic_out.json).
RESEARCH USE ONLY. NOT A MEDICAL DEVICE. Writes n1b_c3_pmf_out.json."""
import json
import math
import os

ROOT = r"C:\Users\mariu\neuro-company\research\neurobiology"
c = json.load(open(os.path.join(ROOT, "results", "N1b_card.json")))["C3prime"]
prev = json.load(open(os.path.join(ROOT, "code", "review", "c3_analytic_out.json")))
pmf = sorted(c["exact_pmf"])
tot = sum(m for _, m in pmf)
mu = sum(v * m for v, m in pmf)
sd = math.sqrt(sum(v * v * m for v, m in pmf) - mu * mu)
cum, q95 = 0.0, None
for v, m in pmf:
    cum += m
    if q95 is None and cum >= 0.95 - 1e-12:
        q95 = v
a = sum(m for v, m in pmf if v > q95 + 1e-15)
ex = c["exact"]
M = c["mc"]["M"]
out = {"mass": tot, "mu_pmf": mu, "mu_card": ex["mu_star"], "sd_pmf": sd, "sd_card": ex["sigma_star"], "q95_pmf": q95,
       "q95_card": ex["q95"], "a_pmf": a, "a_card": ex["a_star"],
       "crit_i": abs(c["mc"]["mean_mc"] - ex["mu_star"]) <= 3 * ex["sigma_star"] / math.sqrt(M),
       "bound_ii": ex["a_star"] + 3 * math.sqrt(ex["a_star"] * (1 - ex["a_star"]) / M),
       "crit_ii": c["mc"]["frac_above_q95"] <= ex["a_star"] + 3 * math.sqrt(ex["a_star"] * (1 - ex["a_star"]) / M),
       "PLC_trip": c["PL-C"]["frac_above_q95"] > ex["a_star"] + 3 * math.sqrt(ex["a_star"] * (1 - ex["a_star"]) / M),
       "prev_review_ratio_of_expectations": prev["F1_ratio_of_expectations"], "prev_review_mc_mean": prev["F1_mc_mean"],
       "prev_review_P_F1_le_0.05": prev["P_F1_le_0.05_per_draw"], "card_P_F1_le_0.05": ex["P_F1_le_0.05"]}
json.dump(out, open(os.path.join(ROOT, "code", "review", "n1b_c3_pmf_out.json"), "w"), indent=1)
print(json.dumps(out, indent=1))
