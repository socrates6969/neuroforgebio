"""Deterministic CHB-MIT subset selection (rule fixed before any EDF data download).

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.

Input : notes/data/chbmit_inventory.csv (built by chbmit_inventory.py from summaries + EDF headers)
Output: notes/data/chbmit_selection.csv (one row per selected EDF, in recording order)

RULE (see notes/data_subset.md):
 E1  every file of the subject has exactly the 23 labels of chb01, same order, no dummy '-' channels, fs = 256 Hz
 E2  >= 3 seizures in the subject (per chbNN-summary.txt)
 E3  file start times present in the summary (needed for chronological splits) -> excludes chb24
 E4  chb21 is the same patient as chb01 (PhysioNet description) -> never both; chb21 fails E1 anyway
 Per subject: ALL seizure files + the EARLIEST seizure-free files in RECORDS order until
   non-seizure time (file duration minus annotated seizure time, summed) >= 10 h.
 Subject set: maximise number of subjects (<= 4) with total bytes <= 1.8e9; ties broken by
   (more seizures, more seizure-containing files, fewer bytes, lexicographic subject ids).
"""
import csv, datetime, itertools, os
from collections import defaultdict


def edf_dt(r):
    """Surrogate (de-identified) EDF header date+time; only differences within a subject are meaningful."""
    d, m, y = (int(x) for x in r["edf_start_date"].split("."))
    hh, mi, ss = (int(x) for x in r["edf_start_time"].split("."))
    return datetime.datetime(1900 + y, m, d, hh, mi, ss)

ROOT = r"C:\Users\mariu\neuro-company\research\neurobiology"
INV = os.path.join(ROOT, r"notes\data\chbmit_inventory.csv")
OUT = os.path.join(ROOT, r"notes\data\chbmit_selection.csv")
BUDGET = 1.8e9
NONSZ_MIN_S = 10 * 3600


def szdur(r):
    return sum(int(b) - int(a) for a, b in (x.split("-") for x in r["seizures_start_end_s"].split(";") if x))


def main():
    rows = list(csv.DictReader(open(INV)))
    by = defaultdict(list)
    for r in rows:
        by[r["subject"]].append(r)
    plans = {}
    for s, L in sorted(by.items()):
        L.sort(key=lambda r: int(r["record_order"]))
        e1 = all(r["same_as_chb01_23"] == "1" and r["n_signals"] == "23" and r["fs_hz"] == "256" for r in L)
        nsz = sum(int(r["n_seizures"] or 0) for r in L)
        e3 = all(r["summary_start_time"] for r in L)
        if not (e1 and nsz >= 3 and e3 and s != "chb21"):
            continue
        sz = [r for r in L if r["n_seizures"] not in ("", "0")]
        non = sum(int(r["duration_s"]) - szdur(r) for r in sz)
        sel = list(sz)
        for r in L:
            if non >= NONSZ_MIN_S:
                break
            if r["n_seizures"] == "0":
                sel.append(r)
                non += int(r["duration_s"])
        if non < NONSZ_MIN_S:
            continue
        sel.sort(key=lambda r: int(r["record_order"]))
        plans[s] = dict(files=sel, bytes=sum(int(r["size_bytes"]) for r in sel), nsz=nsz,
                        nszf=len(sz), non=non, hours=sum(int(r["duration_s"]) for r in sel) / 3600)
    print("eligible:", {s: (p["nsz"], round(p["bytes"] / 1e6)) for s, p in plans.items()})
    best = None
    for k in (4, 3, 2, 1):
        for combo in itertools.combinations(sorted(plans), k):
            b = sum(plans[s]["bytes"] for s in combo)
            if b > BUDGET:
                continue
            key = (-sum(plans[s]["nsz"] for s in combo), -sum(plans[s]["nszf"] for s in combo), b, combo)
            if best is None or key < best:
                best = key
        if best:
            break
    combo = best[3]
    min4 = min((sum(plans[s]["bytes"] for s in c), c) for c in itertools.combinations(sorted(plans), 4))
    print("cheapest 4-subject set:", min4)
    out = []
    for s in combo:
        p = plans[s]
        print(s, "files", len(p["files"]), "seizures", p["nsz"], "hours %.2f" % p["hours"],
              "non-seizure h %.2f" % (p["non"] / 3600), "GB %.3f" % (p["bytes"] / 1e9))
        t_first = min(edf_dt(r) for r in by[s])
        for r in p["files"]:
            out.append(dict(edf_start_date=r["edf_start_date"], edf_start_time=r["edf_start_time"],
                            t_start_h_from_subject_first_file=round((edf_dt(r) - t_first).total_seconds() / 3600, 4),subject=s, file=r["file"], record_order=r["record_order"],
                            summary_start_time=r["summary_start_time"], summary_end_time=r["summary_end_time"],
                            duration_s=r["duration_s"], n_seizures=r["n_seizures"],
                            seizures_start_end_s=r["seizures_start_end_s"],
                            role="seizure" if r["n_seizures"] != "0" else "seizure-free (earliest)",
                            size_bytes=r["size_bytes"], sha256=r["sha256"]))
    print("TOTAL files %d GB %.3f" % (len(out), sum(int(r["size_bytes"]) for r in out) / 1e9))
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)


if __name__ == "__main__":
    main()
