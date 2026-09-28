"""Reviewer check for N1 (a) / D10: recompute the C2a leaky AUROC with the harness's own functions and the same RNG
stream order, then ALSO restrict it to the honest causal test files (same window population as the honest AUROC).
RESEARCH USE ONLY. NOT A MEDICAL DEVICE. Read-only use of nfharness."""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"
import json, sys
import numpy as np
sys.path.insert(0, r"C:\Users\mariu\neuro-company\research\neurobiology\code")
from nfharness import config as C
from nfharness.data import load_records
from nfharness.features import file_features
from nfharness.pipeline import fit, predict
from nfharness.splits import causal_splits, random_window_split
from nfharness.windows import window_starts, window_labels_from_mask
from nfharness.labels import mask_from_events
from nfharness.stats import auroc
RAW = r"C:\Users\mariu\neuro-company\research\neurobiology\data\raw\chbmit"
S = ["chb01", "chb03", "chb10"]; P = {"chb01": 0.657, "chb03": 0.273, "chb10": 0.429}
recs, ann = load_records(RAW, S)
splits = causal_splits(recs, {f: len(v) for f, v in ann.items()})
g = C.rng(C.STREAM_LEAK_SPLIT)
out = {}
for s in S:
    rs = [r for r in recs if r.subject == s]
    feats = {r.name: file_features(r) for r in rs}
    wl = {r.name: window_labels_from_mask(mask_from_events(ann[r.name], r.duration)) for r in rs}
    is_tr = random_window_split({r.name: window_starts(r.duration).size for r in rs}, P[s], g, allow_random_split=True)
    tr = [(f, np.flatnonzero(m)) for f, m in is_tr.items()]; te = [(f, np.flatnonzero(~m)) for f, m in is_tr.items()]
    model = fit(feats, lambda f, i: wl[f][i], tr)
    p = predict(model, feats, te)
    y_all = np.concatenate([wl[f][i] for f, i in te]); s_all = np.concatenate([p[f] for f, _ in te])
    tn = set(splits[s].test_names)
    y_te = np.concatenate([wl[f][i] for f, i in te if f in tn]); s_te = np.concatenate([p[f] for f, _ in te if f in tn])
    out[s] = {"leak_auroc_all_heldout": auroc(y_all, s_all), "leak_auroc_causal_test_files_only": auroc(y_te, s_te)}
    print(s, out[s], flush=True)
    del feats
json.dump(out, open(r"C:\Users\mariu\neuro-company\research\neurobiology\code\review\c2a_sameset_out.json", "w"), indent=1)
