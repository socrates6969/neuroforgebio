"""Synthetic EDFs with the chb23/chb24 R2 layout for the N3 dry run (prereg §3 step 3, stream 26).

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. The data are synthetic.
Signal model = n1b.synth.synth_signal (unchanged, imported). Layout (EDF header start date/time, duration, seizure
on/off) of the 7 R2 files is taken from notes\\data\\chbmit_inventory.csv (annotations + headers only): chb23 -> syn23,
chb24 -> syn24. Randomness: generator (26, 0, subject_index).
write_edf_chunked writes the SAME bytes as nfharness.data.write_edf (tests/test_n3.py checks equality) but converts the
signal in 600-s chunks, so the 4-h file stays inside the RAM budget.
"""
import csv
import os

import numpy as np

from n1b.synth import FS, _start, synth_signal
from nfharness.config import CHANNEL_LABELS_23

from . import K_DRY, rng

R2 = {"chb23": ["chb23_06.edf", "chb23_08.edf", "chb23_09.edf"],
      "chb24": ["chb24_01.edf", "chb24_03.edf", "chb24_04.edf", "chb24_06.edf"]}
SUBJECT_MAP = (("chb23", "syn23"), ("chb24", "syn24"))


def read_layout(inventory_csv):
    rows = {(r["subject"], r["file"]): r for r in csv.DictReader(open(inventory_csv, newline=""))}
    out = {}
    for s, files in R2.items():
        lst = []
        for f in files:
            r = rows[(s, f)]
            sz = []
            for part in r["seizures_start_end_s"].split(";"):
                if part.strip():
                    a, b = part.split("-")
                    sz.append((int(a), int(b)))
            lst.append({"file": f, "start": _start(r["edf_start_date"], r["edf_start_time"]),
                        "duration": int(r["duration_s"]), "seizures": sz})
        lst.sort(key=lambda x: x["start"])
        out[s] = lst
    return out


def _hdr(n_ch, n_rec, fs, labels, start):
    pmin, pmax, dmin, dmax = -800.0, 800.0, -2048, 2047

    def f(s, w):
        s = str(s)[:w]
        return s + " " * (w - len(s))
    hdr = f("0", 8) + f("X", 80) + f("synthetic", 80) + f(start.strftime("%d.%m.%y"), 8) + f(start.strftime("%H.%M.%S"), 8)
    hdr += f(256 * (n_ch + 1), 8) + f("", 44) + f(n_rec, 8) + f(1, 8) + f(n_ch, 4)
    for w, vals in [(16, labels), (80, [""] * n_ch), (8, ["uV"] * n_ch), (8, [pmin] * n_ch), (8, [pmax] * n_ch),
                    (8, [dmin] * n_ch), (8, [dmax] * n_ch), (80, [""] * n_ch), (8, [fs] * n_ch), (32, [""] * n_ch)]:
        hdr += "".join(f(v, w) for v in vals)
    return hdr.encode("latin-1")


def write_edf_chunked(path, data_uv, fs, labels, start, chunk_s=600):
    """Byte-identical to nfharness.data.write_edf (same header text and the same float32 arithmetic), chunked."""
    n_ch, n = data_uv.shape
    n_rec = n // fs
    pmin, pmax, dmin, dmax = -800.0, 800.0, -2048, 2047
    g = (pmax - pmin) / (dmax - dmin)
    with open(path, "wb") as fh:
        fh.write(_hdr(n_ch, n_rec, fs, labels, start))
        for r0 in range(0, n_rec, chunk_s):
            r1 = min(n_rec, r0 + chunk_s)
            x = data_uv[:, r0 * fs:r1 * fs]
            dig = np.clip(np.round((x - (pmax - g * dmax)) / g), dmin, dmax).astype("<i2")
            fh.write(dig.reshape(n_ch, r1 - r0, fs).transpose(1, 0, 2).tobytes())


def make_layout_dataset(root, inventory_csv):
    lay = read_layout(inventory_csv)
    subjects = []
    for si, (real, syn) in enumerate(SUBJECT_MAP):
        g = rng(K_DRY, 0, si)
        sdir = os.path.join(root, syn)
        os.makedirs(sdir, exist_ok=True)
        lines = ["Data Sampling Rate: 256 Hz", ""]
        for row in lay[real]:
            fn = row["file"].replace(real, syn)
            x = synth_signal(g, row["duration"], row["seizures"])
            write_edf_chunked(os.path.join(sdir, fn), x, FS, CHANNEL_LABELS_23, row["start"])
            del x
            lines += ["File Name: %s" % fn, "Number of Seizures in File: %d" % len(row["seizures"])]
            for k, (a, b) in enumerate(row["seizures"]):
                lines += ["Seizure %d Start Time: %d seconds" % (k + 1, a), "Seizure %d End Time: %d seconds" % (k + 1, b)]
            lines.append("")
        with open(os.path.join(sdir, "%s-summary.txt" % syn), "w") as fh:
            fh.write("\n".join(lines))
        subjects.append(syn)
    return subjects
