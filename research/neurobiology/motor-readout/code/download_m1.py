r"""M1 data download: size check (abort > 0.80 GB), download, SHA-256 vs DANDI / PhysioNet digests, manifest.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
Only the assets listed in notes\data_plan.md (plus MC_Maze_Small 000140 train, the dry-run file named in prereg A4/§8).
"""
import csv
import hashlib
import json
import os
import sys
import time

import httpx

ROOT = r"C:\Users\mariu\neuro-company\research\neurobiology\motor-readout"
RAW = os.path.join(ROOT, "data", "raw")
MAN = os.path.join(ROOT, "data", "manifests", "motor_manifest.csv")
PREREG = os.path.join(ROOT, "prereg", "M1_decoder_comparison.md")
PREREG_SHA_PREFIX = "9eada9d7"
INPUT_LOCK = ("000138|0.220113.0407|e67b57b2-e9ad-4d95-b9e3-1262997360dc\n"
              "001201|0.251023.2336|c002a9a1-664d-4a69-af02-ba810046c4fb,9d1820f1-7583-4faf-bbd0-7e9fb7001ca4,"
              "ea07a2e3-d5f4-4036-9b62-93d1f89cba64,9c0ac931-d97e-464b-a134-c366b7c84727,b424f116-7827-4ab0-80ed-1e8951eea67a,"
              "88039197-6170-4d06-ba3e-f58b68c6eb7f,b9868d49-f641-4b95-a8e3-6295111b958b,9db3b62a-6fea-493b-98bf-2f6ded6eefec,"
              "1a7aadf8-eb08-427b-93e3-8df11d71ae9e\n"
              "eegmmidb|1.0.0|S001-S020|R04,R08,R12")
INPUT_LOCK_SHA = "aa0f8e1b4e86c93b8bb14c108046dcab1d2ae798806cd21d74e5065388e65d7a"
D1 = ("000138", "0.220113.0407", ["e67b57b2-e9ad-4d95-b9e3-1262997360dc"])
D2 = ("001201", "0.251023.2336", INPUT_LOCK.split("\n")[1].split("|")[2].split(","))
DRY = ("000140", "0.220113.0408")
PN = "https://physionet.org/files/eegmmidb/1.0.0/"
CAP = 0.80e9
API = "https://api.dandiarchive.org/api"


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def plan(cl):
    items = []   # (arm, rel_path, url, size, expected_sha, source)
    for arm, (ds, ver, ids) in (("D1", D1), ("D2", D2)):
        for a in ids:
            m = cl.get("%s/assets/%s/" % (API, a)).json()
            items.append((arm, os.path.join(ds, os.path.basename(m["path"])), "%s/assets/%s/download/" % (API, a),
                          int(m["contentSize"]), m["digest"]["dandi:sha2-256"], "DANDI %s/%s asset %s" % (ds, ver, a)))
    r = cl.get("%s/dandisets/%s/versions/%s/assets/" % (API, DRY[0], DRY[1]), params={"page_size": 100}).json()
    tr = [x for x in r["results"] if "desc-train" in x["path"]]
    assert len(tr) == 1, tr
    m = cl.get("%s/assets/%s/" % (API, tr[0]["asset_id"])).json()
    items.append(("DRY", os.path.join(DRY[0], os.path.basename(m["path"])), "%s/assets/%s/download/" % (API, tr[0]["asset_id"]),
                  int(m["contentSize"]), m["digest"]["dandi:sha2-256"], "DANDI %s/%s asset %s" % (DRY[0], DRY[1], tr[0]["asset_id"])))
    sums = {}
    for line in cl.get(PN + "SHA256SUMS.txt").text.splitlines():
        parts = line.split()
        if len(parts) == 2:
            sums[parts[1]] = parts[0]
    for s in range(1, 21):
        for rr in (4, 8, 12):
            for ext in (".edf", ".edf.event"):
                rel = "S%03d/S%03dR%02d%s" % (s, s, rr, ext)
                h = cl.head(PN + rel)
                items.append(("D3", os.path.join("eegmmidb", rel.replace("/", os.sep)), PN + rel,
                              int(h.headers["content-length"]), sums.get(rel), "PhysioNet eegmmidb 1.0.0 SHA256SUMS"))
    return items


def main():
    ph = sha256_file(PREREG)
    if not ph.startswith(PREREG_SHA_PREFIX):
        sys.exit("prereg hash mismatch: %s" % ph)
    lock = hashlib.sha256(INPUT_LOCK.encode("utf-8")).hexdigest()
    if lock != INPUT_LOCK_SHA:
        sys.path.insert(0, r"C:\Users\mariu\neuro-company\research\neurobiology\code")
        from nfharness.errors import SplitHashError
        raise SplitHashError("input lock %s != %s" % (lock, INPUT_LOCK_SHA))
    print("prereg sha256", ph, "\ninput lock OK", lock)
    with httpx.Client(follow_redirects=True, timeout=120) as cl:
        items = plan(cl)
        tot = sum(i[3] for i in items)
        by = {}
        for i in items:
            by[i[0]] = by.get(i[0], 0) + i[3]
        print("planned bytes by arm", by, "total", tot)
        with open(os.path.join(ROOT, "data", "manifests", "motor_plan.json"), "w") as f:
            json.dump({"items": items, "total_bytes": tot, "by_arm": by, "prereg_sha256": ph, "input_lock_sha256": lock}, f, indent=1)
        if tot > CAP:
            sys.exit("ABORT: planned %d B > cap %d B" % (tot, CAP))
        if "--plan" in sys.argv:
            return
        rows = []
        for arm, rel, url, size, exp, src in items:
            dst = os.path.join(RAW, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if not (os.path.exists(dst) and os.path.getsize(dst) == size):
                t0 = time.time()
                with cl.stream("GET", url) as r, open(dst + ".part", "wb") as f:
                    r.raise_for_status()
                    for b in r.iter_bytes(1 << 20):
                        f.write(b)
                os.replace(dst + ".part", dst)
                print("got %s %.1f MB %.0fs" % (rel, size / 1e6, time.time() - t0), flush=True)
            h = sha256_file(dst)
            ok = (exp is None) or (h == exp)
            rows.append([arm, rel.replace("\\", "/"), os.path.getsize(dst), h, exp or "", "MATCH" if exp and ok else ("NO_REF" if exp is None else "MISMATCH"), src, url])
            if not ok:
                print("HASH MISMATCH", rel, h, exp)
    with open(MAN, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["arm", "path", "bytes", "sha256", "expected_sha256", "check", "source", "url"])
        w.writerows(rows)
    print("manifest rows", len(rows), "mismatches", sum(r[5] == "MISMATCH" for r in rows))


if __name__ == "__main__":
    main()
