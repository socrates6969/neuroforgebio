"""REVIEW N1b: PL-A on real data.
(1) Reproduce PL-A chb01 r0 with the unchanged n1b code and compare sha256(s, h), T_A, T_E, p-values with the card.
(2) Verify leak alignment independently: every leaked training window's feature row equals the ORIGINAL file's window
    (parent file, offset a + i) and its label equals the phantom window label recomputed from the drawn test phantoms.
(3) Alternative literal reading R2 of §4 PL-A ("25% of the test PHANTOM windows"): floor(0.25 x n_pos) of the
    phantom-POSITIVE allowed test windows (stream 13) leaked with label 1; everything else as in NC-P/PL-A (t_rm,
    degeneracy, M=999, Fisher). 5 replicates x 3 subjects. The patch is in memory only; no file is modified.
RESEARCH USE ONLY. NOT A MEDICAL DEVICE. Writes n1b_pla_alt_out.json."""
import math
import os
import sys
import time

for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[v] = "1"
import json  # noqa: E402

import numpy as np  # noqa: E402

ROOT = r"C:\Users\mariu\neuro-company\research\neurobiology"
sys.path.insert(0, os.path.join(ROOT, "code"))
import run_n1b as RN  # noqa: E402
from n1b import ncp  # noqa: E402
from nfharness.data import FileRecord  # noqa: E402
from nfharness.labels import mask_from_events  # noqa: E402
from nfharness.windows import window_labels_from_mask  # noqa: E402
from nfharness.provenance import peak_rss_mb  # noqa: E402

t0 = time.time()
card = json.load(open(os.path.join(ROOT, "results", "N1b_card.json")))
cardA = {(r["subject"], r["replicate"]): r for r in card["PL-A"]["replicates"]}
raw = os.path.join(ROOT, "data", "raw", "chbmit")
st = {}
records, ann, splits, shash, feats, fhash, pseudo, table = RN.prepare(raw, RN.SUBJECTS, True, st)
orig_plant = ncp.plant_label_leak
captured = []


def spy(sp, fe, test_ann, g13, allow_planted_leak=False):
    out = orig_plant(sp, fe, test_ann, g13, allow_planted_leak=allow_planted_leak)
    captured.append((sp, test_ann, out))
    return out


def alt_plant(sp, fe, test_ann, g13, allow_planted_leak=False):
    """R2: 25% of the phantom-POSITIVE test windows, label 1."""
    ncp.require_flag(allow_planted_leak, "PL-A alt R2")
    te = sp.split.test
    pos = []
    for j, r in enumerate(te):
        wl = window_labels_from_mask(mask_from_events(test_ann[r.name], r.duration))
        pos += [(j, int(i)) for i in np.flatnonzero(wl)]
    k = int(math.floor(0.25 * len(pos)))
    sel = np.sort(g13.choice(len(pos), size=k, replace=False))
    recs, fx, an = [], {}, {}
    for n, q in enumerate(sel.tolist()):
        j, i = pos[q]
        r = te[j]
        name = "PLA2|%s|w%d" % (r.name, i)
        recs.append(FileRecord(r.subject, name, "<planted PL-A R2>", -1.0e7 + 10.0 * n, 2))
        fx[name] = fe[r.name][i:i + 1]
        an[name] = [(0, 2)]
    return recs, fx, an, {"n_test_windows": int(sum(r.duration - 1 for r in te)), "n_leak_windows": k,
                          "n_leak_positive": k, "n_test_positive": len(pos)}


out = {"prepare_s": time.time() - t0}
# (1)+(2) literal reproduction of chb01 r0
ncp.plant_label_leak = spy
pub, _ = ncp.run_replicate(pseudo["chb01"], feats, 0, plant="PL-A", allow_planted_leak=True)
ncp.plant_label_leak = orig_plant
c = cardA[("chb01", 0)]
out["repro_chb01_r0"] = {k: [pub[k] if not isinstance(pub[k], dict) else pub[k].get("p_up"), c[k] if not isinstance(c[k], dict) else c[k].get("p_up")]
                         for k in ("sha256_scores_hyps", "T_A", "p_A_up", "t_rm", "E_rm")}
out["repro_identical"] = all(a == b for a, b in out["repro_chb01_r0"].values())
sp, test_ann, (recs, fx, lann, info) = captured[0]
bad_feat = bad_lab = 0
for rr in recs:
    _, pname, w = rr.name.split("|")
    i = int(w[1:])
    parent, a, b = sp.parent[pname]
    if not np.array_equal(fx[rr.name], feats[parent][a + i:a + i + 1]):
        bad_feat += 1
    lab = int(any(on <= i and i + 2 <= off for on, off in test_ann[pname]))
    if (lab == 1) != bool(lann[rr.name]):
        bad_lab += 1
out["alignment"] = {"n_leak": len(recs), "n_leak_pos": info["n_leak_positive"], "feature_row_mismatch": bad_feat,
                    "label_mismatch": bad_lab}
# (3) alternative reading R2
ncp.plant_label_leak = alt_plant
reps = []
for s in RN.SUBJECTS:
    for rep in range(5):
        pub, _ = ncp.run_replicate(pseudo[s], feats, rep, plant="PL-A", allow_planted_leak=True)
        reps.append(pub)
        print(s, rep, pub["t_rm"], pub["degeneracy_rm"]["n_events"], pub["E_rm"]["tp"], pub["E_rm"]["fp"], pub["E_rm"]["p_up"],
              round(pub["T_A"], 3), flush=True)
ncp.plant_label_leak = orig_plant
agg = ncp.aggregate(reps)
out["alt_R2"] = {"fisher": agg["fisher"], "fisher_n": agg["fisher_n"], "n_degenerate": agg["n_degenerate_event_arm"],
                 "T_A_mean": agg["T_A_mean"], "T_E_rm_mean": agg["T_E_rm_mean"], "pooled": agg["T_E_rm_pooled_tp_fp_nref"],
                 "t_rm": agg["t_rm_values"], "trip": bool(agg["fisher"]["T_A_up"] < 0.0025 and agg["fisher"]["T_E_up"] < 0.0025),
                 "per_rep": [(r["subject"], r["replicate"], r["t_rm"], r["E_rm"]["tp"], r["E_rm"]["fp"], r["E_rm"]["p_up"],
                              r["leak"]["n_leak_windows"]) for r in reps]}
out["wall_s"] = time.time() - t0
out["peak_ram_mb"] = peak_rss_mb()
json.dump(out, open(os.path.join(ROOT, "code", "review", "n1b_pla_alt_out.json"), "w"), indent=1, default=str)
print(json.dumps({k: v for k, v in out.items() if k != "alt_R2"}, indent=1, default=str))
print(json.dumps(out["alt_R2"], default=str))
