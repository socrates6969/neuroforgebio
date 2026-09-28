"""N3 download (prereg\\N3_harness_validation_fresh.md §2.2-2.4, data decision B relayed by the queen).

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
Downloads ONLY the prereg R2 subset: chb23_06/08/09 and chb24_01/03/04/06 (7 EDFs) + their .edf.seizures files + the two
summaries into data\\raw\\chbmit\\<subject>\\. Reuses the HEAD/hash helpers of code\\chbmit_download.py by IMPORT (that
file is unchanged; its main() is not called because it would rewrite the manifest). Every file is checked against
PhysioNet's SHA256SUMS.txt; the manifest is APPENDED (never rewritten). Aborts BEFORE any transfer if the total raw data
after the download would exceed 2.10e9 bytes (cap given by the queen), or if the listed sizes differ from HEAD.
Usage: python code\\n3\\download.py [--check-only]
"""
import csv
import datetime
import os
import sys

CODE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(CODE)
sys.path.insert(0, CODE)

import chbmit_download as D  # noqa: E402  (unchanged cycle-1 downloader; helpers only)

RAW = os.path.join(ROOT, "data", "raw", "chbmit")
MAN = os.path.join(ROOT, "data", "manifests", "chbmit_manifest.csv")
SUMS = os.path.join(RAW, "_meta", "SHA256SUMS.txt")
INV = os.path.join(ROOT, "notes", "data", "chbmit_inventory.csv")
CAP_TOTAL_RAW = 2.10e9
EDFS = {"chb23": ["chb23_06.edf", "chb23_08.edf", "chb23_09.edf"],
        "chb24": ["chb24_01.edf", "chb24_03.edf", "chb24_04.edf", "chb24_06.edf"]}
PREREG_R2_BYTES = 549440512


def items():
    out = []
    for s, fs in EDFS.items():
        out.append("%s/%s-summary.txt" % (s, s))
        for f in fs:
            out.append("%s/%s" % (s, f))
            out.append("%s/%s.seizures" % (s, f))
    return out


RANGE = 8 << 20
WORKERS = 12


def ranged_download(url, dest, expected):
    """Parallel HTTP Range download of one file in 8-MiB pieces (PhysioNet gives ~50-150 KB/s per connection here).
    Pieces go to dest.pNNNN, are size-checked, then concatenated; the caller verifies the SHA-256."""
    import time
    import urllib.request
    from concurrent.futures import ThreadPoolExecutor
    if os.path.exists(dest) and os.path.getsize(dest) == expected:
        return "cached"
    pieces = [(i, a, min(a + RANGE, expected) - 1) for i, a in enumerate(range(0, expected, RANGE))]

    def one(pc):
        i, a, b = pc
        part = "%s.p%04d" % (dest, i)
        n = b - a + 1
        for attempt in range(8):
            if os.path.exists(part) and os.path.getsize(part) == n:
                return part
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "neuro-hive/0.1", "Range": "bytes=%d-%d" % (a, b)})
                with urllib.request.urlopen(req, timeout=120) as r:
                    if r.status != 206:
                        raise RuntimeError("no 206")
                    data = r.read()
                if len(data) != n:
                    raise RuntimeError("short piece")
                with open(part, "wb") as f:
                    f.write(data)
                return part
            except Exception as e:  # noqa
                print("  retry", os.path.basename(part), attempt, type(e).__name__, flush=True)
                time.sleep(3 * (attempt + 1))
        raise RuntimeError("piece failed " + part)
    with ThreadPoolExecutor(WORKERS) as ex:
        parts = list(ex.map(one, pieces))
    with open(dest + ".part", "wb") as out:
        for pt in parts:
            with open(pt, "rb") as f:
                out.write(f.read())
    if os.path.getsize(dest + ".part") != expected:
        raise RuntimeError("size mismatch " + dest)
    os.replace(dest + ".part", dest)
    for pt in parts:
        os.remove(pt)
    return "downloaded (ranged)"


def raw_bytes():
    return sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(RAW) for f in fs
               if ".part" not in f and not f[-6:-4] == ".p")


def main(check_only=False):
    sums = {}
    for line in open(SUMS):
        if line.strip():
            h, p = line.split(None, 1)
            sums[p.strip()] = h
    inv = {(r["subject"], r["file"]): int(r["size_bytes"]) for r in csv.DictReader(open(INV, newline=""))}
    rel = items()
    import urllib.parse
    sizes = {r: D.head_len(D.BASE + urllib.parse.quote(r)) for r in rel}
    edf_bytes = sum(v for r, v in sizes.items() if r.endswith(".edf"))
    for r in rel:
        if r.endswith(".edf") and inv[tuple(r.split("/"))] != sizes[r]:
            sys.exit("ABORT: inventory size != Content-Length for " + r)
        if r not in sums:
            sys.exit("ABORT: no PhysioNet SHA256 for " + r)
    already = {r for r in rel if os.path.exists(os.path.join(RAW, *r.split("/")))
               and os.path.getsize(os.path.join(RAW, *r.split("/"))) == sizes[r]}
    now = raw_bytes()
    new = sum(v for r, v in sizes.items() if r not in already)
    plan = {"n_files": len(rel), "edf_bytes": edf_bytes, "edf_bytes_equal_prereg": edf_bytes == PREREG_R2_BYTES,
            "all_bytes": sum(sizes.values()), "raw_bytes_now": now, "raw_bytes_after": now + new, "cap": CAP_TOTAL_RAW}
    print(plan, flush=True)
    if now + new > CAP_TOTAL_RAW:
        sys.exit("ABORT: total raw data would exceed %.2e bytes" % CAP_TOTAL_RAW)
    if not plan["edf_bytes_equal_prereg"]:
        sys.exit("ABORT: EDF bytes differ from the prereg R2 total")
    if check_only:
        return
    rows = []
    for r in rel:
        dest = os.path.join(RAW, *r.split("/"))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        st = ranged_download(D.BASE + urllib.parse.quote(r), dest, sizes[r])
        h = D.sha256(dest)
        exp = sums.get(r)
        ver = "yes" if exp == h else "NO-MISMATCH"
        print(r, st, ver, flush=True)
        rows.append(dict(file=r, bytes=os.path.getsize(dest), sha256=h, sha256_expected=exp or "", verified=ver,
                         url=D.BASE + urllib.parse.quote(r), status=st,
                         download_utc=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")))
    bad = [x["file"] for x in rows if x["verified"] != "yes"]
    if bad:
        sys.exit("ABORT: SHA256 mismatch: %s (manifest NOT appended)" % bad)
    with open(MAN, newline="") as fh:
        rd = csv.DictReader(fh)
        fields = rd.fieldnames
        have = {x["file"] for x in rd}
    with open(MAN, "rb") as fh:
        fh.seek(-1, 2)
        ends_nl = fh.read(1) in (b"\n", b"\r")
    with open(MAN, "a", newline="") as fh:
        if not ends_nl:
            fh.write("\r\n")
        w = csv.DictWriter(fh, fieldnames=fields)
        for x in rows:
            if x["file"] not in have:
                w.writerow(x)
    print("DONE %d files, %d bytes, raw total now %d bytes, all SHA256-verified" % (len(rows), sum(x["bytes"] for x in rows),
                                                                                   raw_bytes()))


if __name__ == "__main__":
    main("--check-only" in sys.argv)
