"""CHB-MIT inventory (no EDF data download).

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.

Sources (PhysioNet chbmit 1.0.0, ODC-By 1.0):
  RECORDS, RECORDS-WITH-SEIZURES, SUBJECT-INFO, SHA256SUMS.txt, chbNN/chbNN-summary.txt,
  per-subject directory listings (sizes), and the EDF *header only* of each file,
  fetched with an HTTP Range request (256*(ns+1) bytes, ~6-8 KB per file).
Output: notes/data/chbmit_inventory.csv  and  data/raw/chbmit/_meta/ (the small text files).
"""
import csv, hashlib, json, os, re, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "https://physionet.org/files/chbmit/1.0.0/"
ROOT = r"C:\Users\mariu\neuro-company\research\neurobiology"
META = os.path.join(ROOT, r"data\raw\chbmit\_meta")
OUT = os.path.join(ROOT, r"notes\data\chbmit_inventory.csv")
HDR_JSON = os.path.join(META, "edf_headers.json")


def get(url, rng=None, tries=4):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "neuro-hive/0.1"})
            if rng:
                req.add_header("Range", "bytes=%d-%d" % rng)
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as e:  # noqa
            if k == tries - 1:
                raise
            time.sleep(2 * (k + 1))


def fetch_text(rel):
    p = os.path.join(META, rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if not os.path.exists(p):
        with open(p, "wb") as f:
            f.write(get(BASE + rel))
    with open(p, "rb") as f:
        return f.read().decode("latin-1")


def parse_edf_header(b):
    ns = int(b[252:256].decode().strip())
    nrec = int(b[236:244].decode().strip())
    dur = float(b[244:252].decode().strip())
    start_date = b[168:176].decode("latin-1").strip()
    start_time = b[176:184].decode("latin-1").strip()
    labels = [b[256 + 16 * i:256 + 16 * (i + 1)].decode("latin-1").strip() for i in range(ns)]
    o = 256 + ns * (16 + 80 + 8 + 8 + 8 + 8 + 8 + 80)
    nsamp = [int(b[o + 8 * i:o + 8 * (i + 1)].decode().strip()) for i in range(ns)]
    return dict(ns=ns, nrec=nrec, rec_dur=dur, start_date=start_date, start_time=start_time,
                labels=labels, fs=[n / dur for n in nsamp])


def header_of(rel):
    b = get(BASE + rel, (0, 255))
    ns = int(b[252:256].decode().strip())
    b = get(BASE + rel, (0, 256 * (ns + 1) - 1))
    return rel, parse_edf_header(b)


def parse_summary(txt):
    """Return {file: dict(start, end, n_sz, sz=[(s,e)], montage_block)}; montage_block counts channel-list blocks."""
    out, block, cur = {}, 0, None
    for line in txt.splitlines():
        line = line.strip()
        if line.startswith("Channels in EDF Files") or line.startswith("Channels changed"):
            block += 1
        m = re.match(r"File Name:\s*(\S+)", line)
        if m:
            cur = m.group(1)
            out[cur] = dict(start="", end="", n_sz=None, sz=[], block=block)
            continue
        if cur is None:
            continue
        m = re.match(r"File Start Time:\s*(\S+)", line)
        if m:
            out[cur]["start"] = m.group(1)
        m = re.match(r"File End Time:\s*(\S+)", line)
        if m:
            out[cur]["end"] = m.group(1)
        m = re.match(r"Number of Seizures in File:\s*(\d+)", line)
        if m:
            out[cur]["n_sz"] = int(m.group(1))
        m = re.match(r"Seizure(?:\s+\d+)?\s+Start Time:\s*(\d+)\s*seconds", line)
        if m:
            out[cur]["sz"].append([int(m.group(1)), None])
        m = re.match(r"Seizure(?:\s+\d+)?\s+End Time:\s*(\d+)\s*seconds", line)
        if m:
            out[cur]["sz"][-1][1] = int(m.group(1))
    return out


def parse_listing(html):
    sizes = {}
    for m in re.finditer(r'href="([^"]+\.edf(?:\.seizures)?)".*?(\d+)\s*$', html, re.M):
        sizes[urllib.parse.unquote(m.group(1))] = int(m.group(2))
    return sizes


def main():
    os.makedirs(META, exist_ok=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    records = [r.strip() for r in fetch_text("RECORDS").splitlines() if r.strip()]
    rws = set(r.strip() for r in fetch_text("RECORDS-WITH-SEIZURES").splitlines() if r.strip())
    fetch_text("SUBJECT-INFO")
    sha = {}
    for line in fetch_text("SHA256SUMS.txt").splitlines():
        if line.strip():
            h, p = line.split(None, 1)
            sha[p.strip()] = h
    subjects = sorted(set(r.split("/")[0] for r in records))
    summ, sizes = {}, {}
    for s in subjects:
        summ.update(parse_summary(fetch_text("%s/%s-summary.txt" % (s, s))))
        html = get(BASE + s + "/").decode("latin-1")
        with open(os.path.join(META, s, "listing.html"), "w", encoding="latin-1") as f:
            f.write(html)
        for fn, sz in parse_listing(html).items():
            sizes["%s/%s" % (s, fn)] = sz
    if os.path.exists(HDR_JSON):
        hdrs = json.load(open(HDR_JSON))
    else:
        hdrs = {}
    todo = [r for r in records if r not in hdrs]
    with ThreadPoolExecutor(6) as ex:
        for rel, h in ex.map(header_of, todo):
            hdrs[rel] = h
    json.dump(hdrs, open(HDR_JSON, "w"), indent=0)

    ref23 = None
    rows = []
    for i, rel in enumerate(records):
        s, fn = rel.split("/")
        h = hdrs[rel]
        sm = summ.get(fn, {})
        dur_s = h["nrec"] * h["rec_dur"]
        real = [l for l in h["labels"] if l not in ("-", "", ".")]
        if ref23 is None and s == "chb01":
            ref23 = real
        n_sz_summary = sm.get("n_sz")
        rows.append(dict(
            subject=s, file=fn, record_order=i, in_summary=int(bool(sm)),
            summary_start_time=sm.get("start", ""), summary_end_time=sm.get("end", ""),
            edf_start_date=h["start_date"], edf_start_time=h["start_time"],
            duration_s=int(dur_s), n_seizures=n_sz_summary if n_sz_summary is not None else "",
            in_RECORDS_WITH_SEIZURES=int(rel in rws),
            seizures_start_end_s=";".join("%d-%s" % (a, b) for a, b in sm.get("sz", [])),
            n_signals=h["ns"], n_nondummy=len(real),
            fs_hz="/".join(sorted(set("%g" % f for f in h["fs"]))),
            montage_block=sm.get("block", ""),
            same_as_chb01_23=int(real == ref23),
            labels="|".join(h["labels"]),
            has_seizures_annotation_file=int((rel + ".seizures") in sizes),
            size_bytes=sizes.get(rel, ""), sha256=sha.get(rel, ""),
        ))
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("rows", len(rows), "->", OUT)


if __name__ == "__main__":
    main()
