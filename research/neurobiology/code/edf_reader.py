"""Minimal pure-numpy EDF(+) reader (no install needed).

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.

read_header(path)            -> dict(ns, n_records, record_duration, labels, fs, phys_min/max, dig_min/max, units, start_date, start_time, header_bytes)
read_edf(path, channels=None, start_s=0, stop_s=None, physical=True)
                              -> (data float32 [n_ch, n_samp] in physical units (uV for CHB-MIT), fs, labels)
Assumes all selected channels share one sampling rate (true for CHB-MIT: 256 Hz).
Duplicate labels (CHB-MIT has 'T8-P8' twice) are kept; select channels by INDEX to be unambiguous.
Memory: reads only the requested records via np.memmap; 1 h x 23 ch float32 = 85 MB.
"""
import numpy as np


def _f(b, a, n):
    return b[a:a + n].decode("latin-1").strip()


def read_header(path):
    with open(path, "rb") as fh:
        b = fh.read(256)
        ns = int(_f(b, 252, 4))
        b += fh.read(256 * ns)
    h = dict(version=_f(b, 0, 8), start_date=_f(b, 168, 8), start_time=_f(b, 176, 8),
             header_bytes=int(_f(b, 184, 8)), reserved=_f(b, 192, 44),
             n_records=int(_f(b, 236, 8)), record_duration=float(_f(b, 244, 8)), ns=ns)
    o = 256

    def field(width, conv=str):
        nonlocal o
        vals = [conv(_f(b, o + width * i, width)) for i in range(ns)]
        o += width * ns
        return vals
    h["labels"] = field(16)
    h["transducer"] = field(80)
    h["units"] = field(8)
    h["phys_min"] = np.array(field(8, float))
    h["phys_max"] = np.array(field(8, float))
    h["dig_min"] = np.array(field(8, float))
    h["dig_max"] = np.array(field(8, float))
    h["prefilter"] = field(80)
    h["samples_per_record"] = np.array(field(8, int))
    h["fs"] = h["samples_per_record"] / h["record_duration"]
    if h["header_bytes"] != 256 * (ns + 1):
        raise ValueError("header size mismatch")
    return h


def read_edf(path, channels=None, start_s=0.0, stop_s=None, physical=True):
    h = read_header(path)
    spr = h["samples_per_record"]
    ch = list(range(h["ns"])) if channels is None else list(channels)
    if len(set(spr[ch])) != 1:
        raise ValueError("selected channels have different sampling rates")
    n = int(spr[ch[0]])
    rec_len = int(spr.sum())
    fs = n / h["record_duration"]
    mm = np.memmap(path, dtype="<i2", mode="r", offset=h["header_bytes"],
                   shape=(h["n_records"], rec_len))
    r0 = int(start_s // h["record_duration"])
    r1 = h["n_records"] if stop_s is None else int(np.ceil(stop_s / h["record_duration"]))
    offs = np.concatenate([[0], np.cumsum(spr)])
    out = np.empty((len(ch), (r1 - r0) * n), dtype=np.float32)
    for k, c in enumerate(ch):
        out[k] = mm[r0:r1, offs[c]:offs[c] + n].reshape(-1)
    if physical:
        g = (h["phys_max"] - h["phys_min"]) / (h["dig_max"] - h["dig_min"])
        off = h["phys_max"] - g * h["dig_max"]
        out = out * g[ch, None].astype(np.float32) + off[ch, None].astype(np.float32)
    # trim to exact seconds requested
    a = int(round((start_s - r0 * h["record_duration"]) * fs))
    e = out.shape[1] if stop_s is None else a + int(round((stop_s - start_s) * fs))
    del mm
    return out[:, a:e], fs, [h["labels"][c] for c in ch]


if __name__ == "__main__":
    import sys
    for p in sys.argv[1:]:
        h = read_header(p)
        x, fs, lab = read_edf(p, start_s=0, stop_s=10)
        print(p, h["ns"], h["n_records"], set(h["fs"]), x.shape, float(np.abs(x).mean()))
