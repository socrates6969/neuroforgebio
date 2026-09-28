"""Read every selected local EDF with code/edf_reader.py and report labels / fs / duration / montage changes.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
Output: notes/data/chbmit_selected_channels.csv
"""
import csv, os, sys
import numpy as np

ROOT = r"C:\Users\mariu\neuro-company\research\neurobiology"
sys.path.insert(0, os.path.join(ROOT, "code"))
import edf_reader  # noqa: E402

SEL = os.path.join(ROOT, r"notes\data\chbmit_selection.csv")
OUT = os.path.join(ROOT, r"notes\data\chbmit_selected_channels.csv")
RAW = os.path.join(ROOT, r"data\raw\chbmit")

rows, ref = [], None
for r in csv.DictReader(open(SEL)):
    p = os.path.join(RAW, r["subject"], r["file"])
    h = edf_reader.read_header(p)
    x, fs, lab = edf_reader.read_edf(p, start_s=0, stop_s=60)  # read 1 min of data to prove decodability
    ref = ref or h["labels"]
    dur = h["n_records"] * h["record_duration"]
    rows.append(dict(subject=r["subject"], file=r["file"], ns=h["ns"], fs="/".join(sorted({"%g" % f for f in h["fs"]})),
                     duration_s=int(dur), duration_matches_inventory=int(int(dur) == int(r["duration_s"])),
                     same_labels_as_first=int(h["labels"] == ref),
                     units="/".join(sorted(set(h["units"]))),
                     phys_range="%g..%g" % (h["phys_min"].min(), h["phys_max"].max()),
                     dig_range="%g..%g" % (h["dig_min"].min(), h["dig_max"].max()),
                     first_min_std_uV_median=round(float(np.median(x.std(1))), 2),
                     dup_T8P8_identical=int(np.array_equal(x[14], x[22])),
                     labels="|".join(h["labels"])))
with open(OUT, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print("files", len(rows), "all 23ch:", all(r["ns"] == 23 for r in rows), "all 256:", all(r["fs"] == "256" for r in rows),
      "montage changes:", [r["file"] for r in rows if not r["same_labels_as_first"]],
      "dur mismatches:", [r["file"] for r in rows if not r["duration_matches_inventory"]],
      "T8-P8 dup identical in all:", all(r["dup_T8P8_identical"] for r in rows))
print("labels:", rows[0]["labels"])
