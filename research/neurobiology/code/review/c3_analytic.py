"""Reviewer check for N1 (b) criterion 3 (C3 random-alarm F1 <= 0.05): is the limit achievable?

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
Input: code\\review\\indep_n2_out.json (the reviewer's independent N2 hypotheses, identical in TP/FP to the harness).
(1) EXACT expectation over ALL circular offsets of each test file (own any-overlap scorer, SzCORE defaults):
    E[TP], E[FP] per file -> pooled ratio-of-expectations F1; plus a Monte-Carlo of the pooled F1 (independent offset
    per file, 20,000 draws) to compare with the harness's reported mean 0.081.
(2) Closed-form approximation: a seizure of length d is hit by a randomly placed alarm of length L with probability
    (d + 30 + 60 + L)/T; pooled F1 ~= 2 E[TP] / (E[TP] + M + N_ref) with M = number of alarm events.
    Large-rate limit for alarms of length L: F1 -> 2 N c / (N c + H), c = (d + 90 + L)/3600 h.
"""
import json

import numpy as np

IN = r"C:\Users\mariu\neuro-company\research\neurobiology\code\review\indep_n2_out.json"
OUT = r"C:\Users\mariu\neuro-company\research\neurobiology\code\review\c3_analytic_out.json"


def prep(ev):
    mg = []
    for a, b in sorted(ev):
        if mg and a - mg[-1][1] < 90:
            mg[-1] = (mg[-1][0], b)
        else:
            mg.append((a, b))
    out = []
    for a, b in mg:
        while b - a > 300:
            out.append((a, a + 300)); a += 300
        out.append((a, b))
    return out


def score(ref, hyp):
    R, H = prep(ref), prep(hyp)
    ov = lambda r, h: h[0] < r[1] + 60 and h[1] > r[0] - 30
    return sum(any(ov(r, h) for h in H) for r in R), sum(not any(ov(r, h) for r in R) for h in H), len(R)


def roll_events(ev, o, T):
    m = np.zeros(T, bool)
    for a, b in ev:
        m[a:b] = True
    m = np.roll(m, o)
    d = np.diff(np.concatenate([[0], m.astype(int), [0]]))
    return list(zip(np.flatnonzero(d == 1).tolist(), np.flatnonzero(d == -1).tolist()))


def main():
    d = json.load(open(IN))
    files = []
    for s in ("chb01", "chb03", "chb10"):
        for f, v in d[s]["hyp"].items():
            files.append((s, f, v["T"], v["hyp_events"], [tuple(x) for x in v["ref_events"]]))
    per = {}
    tabs = {}
    for s, f, T, hyp, ref in files:
        offs = np.arange(0, T, 5)                     # every 5th offset (T/5 = 720-1440 offsets per file)
        r = np.array([score(ref, roll_events(hyp, int(o), T)) for o in offs])
        tabs[f] = r
        per[f] = {"subject": s, "T": T, "n_alarm_events": len(hyp), "alarm_s": int(sum(b - a for a, b in hyp)),
                  "n_ref": len(ref), "E_tp": float(r[:, 0].mean()), "E_fp": float(r[:, 1].mean()),
                  "obs": score(ref, hyp)}
    Etp = sum(v["E_tp"] for v in per.values()); Efp = sum(v["E_fp"] for v in per.values())
    N = sum(v["n_ref"] for v in per.values()); M = sum(v["n_alarm_events"] for v in per.values())
    f1_ratio = 2 * Etp / (2 * Etp + Efp + (N - Etp))
    g = np.random.default_rng(np.random.SeedSequence(20261001, spawn_key=(99, 7)))
    draws = []
    names = list(tabs)
    for _ in range(20000):
        tp = fp = 0
        for f in names:
            row = tabs[f][g.integers(0, len(tabs[f]))]
            tp += row[0]; fp += row[1]
        den = 2 * tp + fp + (N - tp)
        draws.append(2 * tp / den if den else 0.0)
    draws = np.array(draws)
    # closed form
    ctp = 0.0
    for v in per.values():
        pass
    cf = []
    for s, f, T, hyp, ref in files:
        for (a, b) in ref:
            p = sum((b - a) + 90 + (y - x) for x, y in hyp) / T
            cf.append(min(1.0, p))
    Etp_cf = float(sum(cf))
    f1_cf = 2 * Etp_cf / (Etp_cf + M + N)
    H = sum(v["T"] for v in per.values()) / 3600.0
    dbar = float(np.mean([b - a for *_, ref in files for a, b in ref]))
    lim = {L: 2 * N * ((dbar + 90 + L) / 3600) / (N * ((dbar + 90 + L) / 3600) + H) for L in (5, 10, 30, 60, 100, 150)}
    lam1 = {L: (2 * N * (dbar + 90 + L) / 3600) / (N * (dbar + 90 + L) / 3600 + H + N) for L in (5, 10)}
    obs_tp = sum(v["obs"][0] for v in per.values()); obs_fp = sum(v["obs"][1] for v in per.values())
    out = {"N_ref": N, "M_alarm_events": M, "H_hours": H, "mean_seizure_s": dbar,
           "mean_alarm_event_s": float(np.mean([y - x for *_, h, _r in files for x, y in h])) if M else None,
           "exact_E_tp": Etp, "exact_E_fp": Efp, "F1_ratio_of_expectations": f1_ratio,
           "F1_mc_mean": float(draws.mean()), "F1_mc_p95": float(np.percentile(draws, 95)),
           "P_F1_le_0.05_per_draw": float(np.mean(draws <= 0.05)),
           "closed_form_E_tp": Etp_cf, "closed_form_F1": f1_cf,
           "limit_F1_high_rate_by_alarm_len_s": lim, "F1_at_1_alarm_per_h_by_alarm_len_s": lam1,
           "model_pooled_F1": 2 * obs_tp / (2 * obs_tp + obs_fp + (N - obs_tp)), "per_file": per}
    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "per_file"}, indent=1))


if __name__ == "__main__":
    main()
