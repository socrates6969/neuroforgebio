"""Synthetic EDFs with the REAL file and seizure layout (prereg §5.2), for the N1b dry run.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. The data are synthetic.
Signal model = nfharness.data.make_synthetic_dataset (random walk minus the 1-s channel-mean average, minus a 64-sample
moving average, x8, + 3 uV white noise; seizures = 60 uV x U(0.5, 1.5) per channel, 3-8 Hz sine; channel 22 = channel 14),
written with nfharness.data.write_edf. Layout (EDF header start date/time, duration, seizure on/off) is copied from
notes\\data\\chbmit_selection.csv: chb01 -> syn01, chb03 -> syn02, chb10 -> syn03. Generated in float32, one file at a
time, to stay under the RAM budget. Randomness: stream (16, 0, subject_index) (DEVIATIONS N1b-4, N1b-12).
"""
import csv
import datetime as dt
import os

import numpy as np

from nfharness.config import CHANNEL_LABELS_23
from nfharness.data import write_edf

from . import K_SYN, rng

SUBJECT_MAP = (("chb01", "syn01"), ("chb03", "syn02"), ("chb10", "syn03"))
FS = 256


def _start(d, t):
    dd, mm, yy = [int(x) for x in d.split(".")]
    year = 1900 + yy if yy >= 85 else 2000 + yy
    hh, mi, ss = [int(x) for x in t.split(".")]
    return dt.datetime(year, mm, dd, hh, mi, ss)


def read_layout(selection_csv):
    rows = list(csv.DictReader(open(selection_csv, newline="")))
    out = {}
    for r in rows:
        sz = []
        for part in r["seizures_start_end_s"].replace("|", ";").split(";"):
            part = part.strip()
            if part:
                a, b = part.split("-")
                sz.append((int(a), int(b)))
        out.setdefault(r["subject"], []).append({"file": r["file"], "start": _start(r["edf_start_date"], r["edf_start_time"]),
                                                 "duration": int(r["duration_s"]), "seizures": sz,
                                                 "order": int(r["record_order"])})
    for s in out:
        out[s].sort(key=lambda x: x["order"])
    return out


def synth_signal(g, dur, seizures, fs=FS):
    n = dur * fs
    x = np.empty((23, n), dtype=np.float32)
    for c in range(23):
        x[c] = g.standard_normal(n).cumsum()
    cm = np.convolve(x.mean(axis=0, dtype=np.float64), np.ones(fs) / fs, mode="same")
    k = np.ones(64) / 64
    for c in range(23):
        r = x[c].astype(np.float64) - cm
        r -= np.convolve(r, k, mode="same")
        x[c] = 8.0 * r + 3.0 * g.standard_normal(n)
    for on, off in seizures:
        f0 = g.uniform(3, 8)
        amp = g.uniform(0.5, 1.5, (23, 1)).astype(np.float32)
        t = np.arange(on * fs, off * fs) / fs
        x[:, on * fs:off * fs] += (60.0 * np.sin(2 * np.pi * f0 * t)).astype(np.float32)[None, :] * amp
    x[22] = x[14]
    return x


def make_layout_dataset(root, selection_csv, key_prefix=(K_SYN, 0)):
    lay = read_layout(selection_csv)
    subjects = []
    for si, (real, syn) in enumerate(SUBJECT_MAP):
        g = rng(*key_prefix, si)
        sdir = os.path.join(root, syn)
        os.makedirs(sdir, exist_ok=True)
        lines = ["Data Sampling Rate: 256 Hz", ""]
        for row in lay[real]:
            fn = row["file"].replace(real, syn)
            x = synth_signal(g, row["duration"], row["seizures"])
            write_edf(os.path.join(sdir, fn), x, FS, CHANNEL_LABELS_23, row["start"])
            del x
            lines += ["File Name: %s" % fn, "Number of Seizures in File: %d" % len(row["seizures"])]
            for k, (a, b) in enumerate(row["seizures"]):
                lines += ["Seizure %d Start Time: %d seconds" % (k + 1, a), "Seizure %d End Time: %d seconds" % (k + 1, b)]
            lines.append("")
        with open(os.path.join(sdir, "%s-summary.txt" % syn), "w") as fh:
            fh.write("\n".join(lines))
        subjects.append(syn)
    return subjects
