"""Dataset records: manifest hash verification, summary parsing, EDF-header ordering, synthetic EDF writer.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
Seizure annotations are parsed here but handed ONLY to labels.LabelVault; FileRecord carries no labels.
"""
import csv
import datetime as dt
import hashlib
import os
import re
from dataclasses import dataclass

import numpy as np

from .errors import InputHashError


def sha256_file(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


@dataclass(frozen=True)
class FileRecord:
    subject: str
    name: str            # e.g. chb01_03.edf
    path: str
    t_start: float       # seconds from the subject's first selected file (EDF header clock)
    duration: int        # seconds (integer for CHB-MIT)

    @property
    def t_end(self):
        return self.t_start + self.duration


def _edf_start(path):
    with open(path, "rb") as fh:
        b = fh.read(256)
    d = b[168:176].decode("latin-1").strip()
    t = b[176:184].decode("latin-1").strip()
    dd, mm, yy = [int(x) for x in d.split(".")]
    year = 1900 + yy if yy >= 85 else 2000 + yy
    hh, mi, ss = [int(x) for x in t.split(".")]
    n_rec = int(b[236:244].decode("latin-1").strip())
    rec_dur = float(b[244:252].decode("latin-1").strip())
    return dt.datetime(year, mm, dd, hh, mi, ss), int(round(n_rec * rec_dur))


def parse_summary(path):
    """-> {file_name: [(onset_s, offset_s), ...]} for every file listed in a CHB-MIT summary."""
    out, cur = {}, None
    starts = []
    with open(path, "r", encoding="latin-1") as fh:
        for line in fh:
            line = line.strip()
            m = re.match(r"File Name:\s*(\S+)", line)
            if m:
                cur = m.group(1)
                out[cur] = []
                continue
            m = re.match(r"Seizure(?:\s+\d+)?\s+Start Time:\s*(\d+)\s*seconds", line)
            if m and cur:
                starts.append(int(m.group(1)))
                continue
            m = re.match(r"Seizure(?:\s+\d+)?\s+End Time:\s*(\d+)\s*seconds", line)
            if m and cur:
                out[cur].append((starts.pop(0), int(m.group(1))))
    return out


def verify_inputs(raw_root, manifest_csv, sha256sums_txt, want_suffixes=(".edf", ".edf.seizures", "-summary.txt"),
                  subjects=None):
    """Recompute SHA-256 of every EDF / .seizures / summary listed in the manifest (under subject dirs) and compare
    with the manifest AND with PhysioNet's SHA256SUMS.txt. Raises InputHashError on any mismatch (N1 c1).
    Returns {relative_path: sha256}."""
    ref = {}
    with open(sha256sums_txt, "r", encoding="latin-1") as fh:
        for line in fh:
            p = line.split()
            if len(p) == 2:
                ref[p[1]] = p[0]
    got = {}
    with open(manifest_csv, newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        rel = r["file"]
        if rel.startswith("_meta"):
            continue
        if not rel.endswith(want_suffixes):
            continue
        if subjects is not None and rel.split("/")[0] not in subjects:
            continue
        p = os.path.join(raw_root, *rel.split("/"))
        h = sha256_file(p)
        if h != r["sha256"] or r["sha256_expected"] != r["sha256"] or ref.get(rel) != h:
            raise InputHashError("hash mismatch for %s" % rel)
        got[rel] = h
    return got


def load_records(raw_root, subjects):
    """FileRecords (ordered by EDF header start) + raw annotations {name: [(on, off)]} for the given subjects.
    Only EDFs present on disk are used (the selected subset)."""
    recs, ann = [], {}
    for s in subjects:
        sdir = os.path.join(raw_root, s)
        summ = parse_summary(os.path.join(sdir, "%s-summary.txt" % s))
        items = []
        for fn in sorted(os.listdir(sdir)):
            if fn.endswith(".edf"):
                start, dur = _edf_start(os.path.join(sdir, fn))
                items.append((start, fn, dur))
        items.sort()
        t0 = items[0][0]
        for start, fn, dur in items:
            recs.append(FileRecord(s, fn, os.path.join(sdir, fn), (start - t0).total_seconds(), dur))
            ann[fn] = list(summ[fn])
    return recs, ann


# ---------------------------------------------------------------- synthetic EDFs (N1: code is built on these first)
def write_edf(path, data_uv, fs=256, labels=None, start=dt.datetime(2000, 1, 1, 0, 0, 0)):
    """Minimal EDF writer: data_uv float [n_ch, n_samp], 1-s records, int16 with +/-800 uV <-> -2048..2047."""
    n_ch, n = data_uv.shape
    n_rec = n // fs
    labels = labels or ["CH%d" % i for i in range(n_ch)]
    pmin, pmax, dmin, dmax = -800.0, 800.0, -2048, 2047
    g = (pmax - pmin) / (dmax - dmin)
    dig = np.clip(np.round((data_uv - (pmax - g * dmax)) / g), dmin, dmax).astype("<i2")

    def f(s, w):
        s = str(s)[:w]
        return s + " " * (w - len(s))
    hdr = f("0", 8) + f("X", 80) + f("synthetic", 80) + f(start.strftime("%d.%m.%y"), 8) + f(start.strftime("%H.%M.%S"), 8)
    hdr += f(256 * (n_ch + 1), 8) + f("", 44) + f(n_rec, 8) + f(1, 8) + f(n_ch, 4)
    for w, vals in [(16, labels), (80, [""] * n_ch), (8, ["uV"] * n_ch), (8, [pmin] * n_ch), (8, [pmax] * n_ch),
                    (8, [dmin] * n_ch), (8, [dmax] * n_ch), (80, [""] * n_ch), (8, [fs] * n_ch), (32, [""] * n_ch)]:
        hdr += "".join(f(v, w) for v in vals)
    body = dig[:, :n_rec * fs].reshape(n_ch, n_rec, fs).transpose(1, 0, 2).tobytes()
    with open(path, "wb") as fh:
        fh.write(hdr.encode("latin-1"))
        fh.write(body)


def make_synthetic_dataset(root, rng, subjects=("syn01", "syn02", "syn03"), n_files=8, dur=1200, fs=256):
    """Write synthetic 23-channel EDFs + summaries. Background = pink-ish noise; seizures = 3-8 Hz rhythmic,
    higher-amplitude bursts of 30-90 s. Files 1 h apart. Returns nothing; use load_records(root, subjects)."""
    from .config import CHANNEL_LABELS_23
    for si, s in enumerate(subjects):
        sdir = os.path.join(root, s)
        os.makedirs(sdir, exist_ok=True)
        lines = ["Data Sampling Rate: 256 Hz", ""]
        for fi in range(n_files):
            fn = "%s_%02d.edf" % (s, fi + 1)
            t = np.arange(dur * fs) / fs
            x = rng.standard_normal((23, dur * fs)).cumsum(axis=1)
            x -= np.convolve(x.mean(axis=0), np.ones(fs) / fs, mode="same")[None, :]
            x = x - np.array([np.convolve(r, np.ones(64) / 64, mode="same") for r in x])
            x *= 8.0
            x += 3.0 * rng.standard_normal((23, dur * fs))
            szs = []
            if fi >= 1:
                on = int(rng.integers(100, dur - 200))
                ln = int(rng.integers(30, 90))
                f0 = rng.uniform(3, 8)
                seg = slice(on * fs, (on + ln) * fs)
                x[:, seg] += 60.0 * np.sin(2 * np.pi * f0 * t[seg])[None, :] * rng.uniform(0.5, 1.5, (23, 1))
                szs.append((on, on + ln))
            x[22] = x[14]
            write_edf(os.path.join(sdir, fn), x, fs, CHANNEL_LABELS_23,
                      dt.datetime(2000, 1, 1 + si, 0, 0, 0) + dt.timedelta(hours=fi))
            lines += ["File Name: %s" % fn, "Number of Seizures in File: %d" % len(szs)]
            for k, (a, b) in enumerate(szs):
                lines += ["Seizure %d Start Time: %d seconds" % (k + 1, a), "Seizure %d End Time: %d seconds" % (k + 1, b)]
            lines.append("")
        with open(os.path.join(sdir, "%s-summary.txt" % s), "w") as fh:
            fh.write("\n".join(lines))
