"""Resumable, size-checked, SHA-256-verified download of the CHB-MIT subset (stdlib only).

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.

Reads notes/data/chbmit_selection.csv. Also fetches each subject's chbNN-summary.txt and the
.edf.seizures annotation files of the selected seizure EDFs (tiny).
Writes data/raw/chbmit/<subject>/... and data/manifests/chbmit_manifest.csv.
Aborts if (a) the planned bytes exceed BUDGET, or (b) free disk would drop below planned + 2 GB margin.
"""
from concurrent.futures import ThreadPoolExecutor
import csv, datetime, hashlib, os, shutil, sys, time, urllib.parse, urllib.request

BASE = "https://physionet.org/files/chbmit/1.0.0/"
ROOT = r"C:\Users\mariu\neuro-company\research\neurobiology"
RAW = os.path.join(ROOT, r"data\raw\chbmit")
SEL = os.path.join(ROOT, r"notes\data\chbmit_selection.csv")
SHAFILE = os.path.join(RAW, r"_meta\SHA256SUMS.txt")
MAN = os.path.join(ROOT, r"data\manifests\chbmit_manifest.csv")
BUDGET = 1.8e9
CHUNK = 1 << 20
WORKERS = 6


def head_len(url):
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "neuro-hive/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return int(r.headers["Content-Length"])


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(CHUNK), b""):
            h.update(b)
    return h.hexdigest()


def download(url, dest, expected):
    part = dest + ".part"
    if os.path.exists(dest) and os.path.getsize(dest) == expected:
        return "cached"
    for attempt in range(6):
        have = os.path.getsize(part) if os.path.exists(part) else 0
        if have > expected:
            os.remove(part)
            have = 0
        if have == expected:
            break
        req = urllib.request.Request(url, headers={"User-Agent": "neuro-hive/0.1"})
        if have:
            req.add_header("Range", "bytes=%d-" % have)
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                if have and r.status != 206:  # server ignored Range -> restart
                    have = 0
                with open(part, "ab" if have else "wb") as f:
                    while True:
                        b = r.read(CHUNK)
                        if not b:
                            break
                        f.write(b)
        except Exception as e:  # noqa
            print("  retry", attempt, type(e).__name__, e, flush=True)
            time.sleep(3 * (attempt + 1))
    if os.path.getsize(part) != expected:
        raise RuntimeError("size mismatch %s: %d != %d" % (dest, os.path.getsize(part), expected))
    os.replace(part, dest)
    return "downloaded"


def main():
    sums = {}
    for line in open(SHAFILE):
        if line.strip():
            h, p = line.split(None, 1)
            sums[p.strip()] = h
    sel = list(csv.DictReader(open(SEL)))
    items = []
    for s in sorted(set(r["subject"] for r in sel)):
        items.append("%s/%s-summary.txt" % (s, s))
    for r in sel:
        items.append("%s/%s" % (r["subject"], r["file"]))
        if r["n_seizures"] != "0":
            items.append("%s/%s.seizures" % (r["subject"], r["file"]))
    sizes = {rel: head_len(BASE + urllib.parse.quote(rel)) for rel in items}
    total = sum(sizes.values())
    free = shutil.disk_usage(RAW).free
    print("planned %d files, %.4f GB; free disk %.1f GB" % (len(items), total / 1e9, free / 1e9), flush=True)
    if total > BUDGET:
        sys.exit("ABORT: planned bytes exceed budget")
    if free < total + 2e9:
        sys.exit("ABORT: not enough free disk")
    for r in sel:  # listing size must equal HEAD Content-Length
        rel = "%s/%s" % (r["subject"], r["file"])
        if int(r["size_bytes"]) != sizes[rel]:
            sys.exit("ABORT: listing size != Content-Length for " + rel)
    def one(rel):
        dest = os.path.join(RAW, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        st = download(BASE + urllib.parse.quote(rel), dest, sizes[rel])
        h = sha256(dest)
        exp = sums.get(rel)
        ver = "yes" if exp == h else ("no-reference" if exp is None else "NO-MISMATCH")
        print(rel, st, ver, flush=True)
        return dict(file=rel, bytes=os.path.getsize(dest), sha256=h, sha256_expected=exp or "",
                    verified=ver, url=BASE + urllib.parse.quote(rel), status=st,
                    download_utc=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    with ThreadPoolExecutor(WORKERS) as ex:  # a few parallel connections; PhysioNet gives ~150 KB/s per connection here
        rows = list(ex.map(one, items))
    if sum(r["bytes"] for r in rows) > BUDGET:
        sys.exit("ABORT: budget exceeded")
    os.makedirs(os.path.dirname(MAN), exist_ok=True)
    with open(MAN, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    bad = [r["file"] for r in rows if r["verified"] != "yes"]
    print("DONE %d files, %.4f GB, not verified: %s" % (len(rows), sum(r["bytes"] for r in rows) / 1e9, bad))


if __name__ == "__main__":
    main()
