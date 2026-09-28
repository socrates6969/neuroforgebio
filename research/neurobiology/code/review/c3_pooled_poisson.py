"""Reviewer sensitivity check for C3 (D8 interpretation): instead of shifting each file's hypothesis within its own
file, place the model's merged alarm events (own durations) uniformly over ALL 19.66 test hours (file chosen with
probability proportional to duration). RESEARCH USE ONLY. NOT A MEDICAL DEVICE."""
import json
import numpy as np
from c3_analytic import prep, score
d = json.load(open(r"C:\Users\mariu\neuro-company\research\neurobiology\code\review\indep_n2_out.json"))
files, ev = [], []
for s in ("chb01", "chb03", "chb10"):
    for f, v in d[s]["hyp"].items():
        files.append((v["T"], [tuple(x) for x in v["ref_events"]]))
        ev += [b - a for a, b in prep(v["hyp_events"])]
T = np.array([t for t, _ in files]); w = T / T.sum(); N = sum(len(r) for _, r in files)
g = np.random.default_rng(np.random.SeedSequence(20261001, spawn_key=(99, 8)))
f1s = []
for _ in range(5000):
    hyp = [[] for _ in files]
    for L in ev:
        i = g.choice(len(files), p=w); a = int(g.integers(0, T[i] - L)); hyp[i].append((a, a + L))
    tp = fp = 0
    for (Ti, ref), h in zip(files, hyp):
        x = score(ref, h); tp += x[0]; fp += x[1]
    f1s.append(2 * tp / (2 * tp + fp + N - tp))
f1s = np.array(f1s)
out = {"n_merged_alarm_events": len(ev), "median_event_s": float(np.median(ev)), "mean_F1": float(f1s.mean()),
       "p95_F1": float(np.percentile(f1s, 95)), "P(F1<=0.05)": float(np.mean(f1s <= 0.05))}
print(json.dumps(out))
json.dump(out, open(r"C:\Users\mariu\neuro-company\research\neurobiology\code\review\c3_pooled_poisson_out.json", "w"), indent=1)
