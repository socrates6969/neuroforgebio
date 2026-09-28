"""N1 harness controls.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
  python run_n1.py --phase synthetic   # (c) determinism on synthetic EDFs, (d) 12 deliberate violations, (e) scorer
                                       #  equivalence -> results\\N1_cde_synthetic.json  (runs BEFORE any real-data fit)
  python run_n1.py --phase final       # after run_n2.py and run_n2.py --rerun: (c) on real data + overall N1 verdict
                                       #  -> results\\N1_verdict.json
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"

import argparse  # noqa: E402
import datetime as dt  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
import xml.etree.ElementTree as ET  # noqa: E402

CODE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(CODE)
sys.path.insert(0, CODE)

import numpy as np  # noqa: E402

from nfharness import config as C  # noqa: E402
from nfharness.data import make_synthetic_dataset, sha256_file  # noqa: E402
from nfharness.provenance import card_hash, code_hashes, dumps, environment, peak_rss_mb  # noqa: E402
from nfharness.scoring import event_score, latencies, reimpl_event_score  # noqa: E402

PY = sys.executable
RES = os.path.join(ROOT, "results")


def _prov():
    return {"seed": C.SEED, "environment": environment(),
            "code_sha256": code_hashes(CODE, extra=[os.path.abspath(__file__)] +
                                       [os.path.join(CODE, "tests", f) for f in sorted(os.listdir(os.path.join(CODE, "tests"))) if f.endswith(".py")]),
            "prereg_sha256": {n: sha256_file(os.path.join(ROOT, "prereg", n)) for n in ("N1_harness_controls.md", "N2_baseline_detection.md")}}


def part_e():
    sys.path.insert(0, os.path.join(CODE, "tests"))
    from test_units import FIXTURE, mask
    fx = {}
    ok = True
    for k, (T, r, h, tp, fp, nref, fa) in FIXTURE.items():
        a = event_score(mask(T, r), mask(T, h))
        b = reimpl_event_score(mask(T, r), mask(T, h))
        fa_a = 24 * a["fp"] / (a["dur_s"] / 3600)
        fa_b = 24 * b["fp"] / (b["dur_s"] / 3600)
        good = ((a["tp"], a["fp"], a["n_ref"]) == (tp, fp, nref) == (b["tp"], b["fp"], b["n_ref"])
                and abs(fa_a - fa) < 1e-9 and abs(fa_b - fa) < 1e-9)
        fx[k] = {"expected": [tp, fp, nref, fa], "timescoring": [a["tp"], a["fp"], a["n_ref"], fa_a],
                 "reimpl": [b["tp"], b["fp"], b["n_ref"], fa_b], "match": good}
        ok &= good
    lat_ok = latencies(mask(3600, [(1000, 1060)]), mask(3600, [(1004, 1030)])) == [4] and \
        latencies(mask(3600, [(1000, 1060)]), mask(3600, [(985, 990)])) == [-15]
    g = C.rng(C.STREAM_SYNTHETIC)
    n_same, dis = 0, []
    for it in range(1000):
        T = int(g.integers(3600, 4 * 3600 + 1))
        ref = np.zeros(T, np.int8)
        hyp = np.zeros(T, np.int8)
        for _ in range(int(g.integers(0, 6))):
            d = int(g.integers(10, 401))
            a0 = int(g.integers(0, T - d))
            ref[a0:a0 + d] = 1
        for _ in range(int(g.integers(0, 21))):
            d = int(g.integers(1, 501))
            a0 = int(g.integers(0, T - d))
            hyp[a0:a0 + d] = 1
        x, y = event_score(ref, hyp), reimpl_event_score(ref, hyp)
        same = (x["tp"], x["fp"], x["n_ref"]) == (y["tp"], y["fp"], y["n_ref"]) and \
            abs(24 * x["fp"] / (x["dur_s"] / 3600) - 24 * y["fp"] / (y["dur_s"] / 3600)) <= 1e-9
        n_same += same
        if not same and len(dis) < 10:
            dis.append({"i": it, "timescoring": x, "reimpl": y})
    return {"fixture": fx, "fixture_all_match": bool(ok), "latency_X12_ok": bool(lat_ok),
            "random_pairs": 1000, "random_identical": int(n_same), "disagreements": dis,
            "verdict": "PASS" if (ok and lat_ok and n_same == 1000) else "FAIL",
            "prediction": "fixture exact; 1000/1000 identical; P(PASS)=0.85"}


def part_d(tmp):
    xml = os.path.join(tmp, "junit.xml")
    t = time.time()
    r = subprocess.run([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--junitxml", xml, os.path.join(CODE, "tests")],
                       capture_output=True, text=True)
    sys.path.insert(0, os.path.join(CODE, "tests"))
    from test_violations import TEST_IDS, VIOLATION_IDS
    root = ET.parse(xml).getroot()
    cases = []
    for tc in root.iter("testcase"):
        failed = any(ch.tag in ("failure", "error") for ch in tc)
        skipped = any(ch.tag == "skipped" for ch in tc)
        cases.append((tc.get("classname"), tc.get("name"), "fail" if failed else ("skip" if skipped else "pass")))
    by_id = {v: [] for v in VIOLATION_IDS}
    for cls, name, st in cases:
        base = name.split("[")[0]
        if base in TEST_IDS:
            by_id[TEST_IDS[base]].append(st)
    caught = {v: bool(sts) and all(s == "pass" for s in sts) for v, sts in by_id.items()}
    n_pass = sum(s == "pass" for _, _, s in cases)
    return {"pytest_returncode": r.returncode, "tests_total": len(cases), "tests_passed": n_pass,
            "tests_failed": sum(s == "fail" for _, _, s in cases), "violation_tests_by_id": by_id,
            "caught": caught, "n_caught": sum(caught.values()), "n_required": len(VIOLATION_IDS),
            "verdict_synthetic": "PASS" if all(caught.values()) else "FAIL", "wall_s": time.time() - t,
            "pytest_tail": r.stdout.strip().splitlines()[-1:]}


def part_c_synthetic(tmp):
    syn = os.path.join(tmp, "synthetic_edf")
    make_synthetic_dataset(syn, C.rng(C.STREAM_SYNTHETIC, 1))
    hashes, runs = [], []
    for k in (1, 2):
        out = os.path.join(tmp, "run%d" % k)
        t = time.time()
        r = subprocess.run([PY, os.path.join(CODE, "run_n2.py"), "--synthetic", syn, "--out", out, "--replicates", "2"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            return {"verdict": "FAIL", "error": r.stderr[-3000:]}
        cards = sorted(f for f in os.listdir(os.path.join(out, "cards")) if f.endswith(".json")) + ["N2_run_card.json"]
        h = {}
        for f in cards:
            p = os.path.join(out, "cards", f) if f != "N2_run_card.json" else os.path.join(out, f)
            with open(p) as fh:
                c = json.load(fh)
            c.pop("card_sha256_excl_runtime", None)
            h[f] = card_hash(c)
        hashes.append(h)
        runs.append({"stdout": r.stdout.strip()[-800:], "wall_s": time.time() - t})
    same = hashes[0] == hashes[1]
    return {"card_hashes_run1": hashes[0], "card_hashes_run2": hashes[1], "identical": bool(same), "runs": runs,
            "note": "synthetic EDFs (stream (5,1)), 3 subjects x 8 files x 1200 s, R = 2 shuffle replicates",
            "verdict_synthetic": "PASS" if same else "FAIL"}


def phase_synthetic():
    t0 = time.time()
    tmp = tempfile.mkdtemp(prefix="nfh_n1_")
    try:
        e = part_e()
        d = part_d(tmp)
        c = part_c_synthetic(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    out = {"status_label": "RESEARCH USE ONLY. NOT A MEDICAL DEVICE.", "N1c_synthetic": c, "N1d": d, "N1e": e,
           "provenance": _prov(), "runtime": {"wall_s": time.time() - t0, "peak_ram_mb": peak_rss_mb(),
                                               "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat()}}
    with open(os.path.join(RES, "N1_cde_synthetic.json"), "w", newline="\n") as fh:
        fh.write(dumps(out))
    print(json.dumps({"c": c.get("verdict_synthetic", c.get("verdict")), "d": "%d/%d" % (d["n_caught"], d["n_required"]),
                      "tests": "%d/%d" % (d["tests_passed"], d["tests_total"]), "e": e["verdict"],
                      "random": e["random_identical"]}))


def phase_final():
    with open(os.path.join(RES, "N1_cde_synthetic.json")) as fh:
        cde = json.load(fh)
    with open(os.path.join(RES, "N1_ab.json")) as fh:
        ab = json.load(fh)
    h = {}
    for tag, base in (("run1", RES), ("run2", os.path.join(RES, "rerun"))):
        h[tag] = {}
        for f in ["N2_run_card.json"] + ["cards/%s_card.json" % s for s in ("chb01", "chb03", "chb10")]:
            with open(os.path.join(base, *f.split("/"))) as fh:
                c = json.load(fh)
            stored = c.pop("card_sha256_excl_runtime", None)
            h[tag][f] = {"recomputed": card_hash(c), "stored": stored}
    identical = all(h["run1"][f]["recomputed"] == h["run2"][f]["recomputed"] for f in h["run1"])
    with open(os.path.join(RES, "N2_results.json")) as fh:
        n2 = json.load(fh)
    prov = n2["provenance"]
    guards = ab["guard_calls_real_run"]
    c_parts = {
        "c1_input_hashes": {"verified": prov.get("n_inputs_verified"), "all_match_manifest_and_SHA256SUMS": True,
                            "note": "run_n2.py raises InputHashError on any mismatch; the run completed"},
        "c2_split_hash": {"value": prov["split_hash"], "matches": prov["split_hash"] == C.EXPECTED_SPLIT_HASH},
        "c3_rerun_identity": {"identical": bool(identical), "hashes": h},
        "c4_prereg_before_first_label_read": ab["prereg_hash_precedes_first_label_read"],
    }
    c_pass = bool(c_parts["c2_split_hash"]["matches"] and identical and c_parts["c4_prereg_before_first_label_read"]
                  and cde["N1c_synthetic"].get("identical"))
    needed = ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "S5", "S7", "S1"]
    silent = {g: guards.get(g, 0) for g in needed}
    d_pass = bool(cde["N1d"]["n_caught"] == 12 and all(v > 0 for v in silent.values()))
    parts = {"a": ab["N1a"]["verdict"], "b": ab["N1b"]["verdict"], "c": "PASS" if c_pass else "FAIL",
             "d": "PASS" if d_pass else "FAIL", "e": cde["N1e"]["verdict"]}
    verdict = "PASS" if all(v == "PASS" for v in parts.values()) else "FAIL"
    out = {"status_label": "RESEARCH USE ONLY. NOT A MEDICAL DEVICE.", "N1_verdict": verdict, "parts": parts,
           "N1c": c_parts, "N1d_real_run_guard_calls_all_silent": silent,
           "consequence": None if verdict == "PASS" else "harness not validated: N2 reported as 'not verifiable: code'",
           "provenance": _prov(), "runtime": {"finished_utc": dt.datetime.now(dt.timezone.utc).isoformat()}}
    with open(os.path.join(RES, "N1_verdict.json"), "w", newline="\n") as fh:
        fh.write(dumps(out))
    n1_figure(ab, verdict, parts)
    print(json.dumps({"N1": verdict, "parts": parts}))


def n1_figure(ab, verdict, parts):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    subs = ["chb01", "chb03", "chb10"]
    fig, axs = plt.subplots(1, 3, figsize=(13, 4.2))
    a = ab["N1a"]["per_subject"]
    x = np.arange(3)
    hv = [a[s]["honest_auroc"] for s in subs]
    lv = [a[s]["leak_auroc_C2a"] for s in subs]
    axs[0].vlines(x, hv, lv, color="#b8b7b2", lw=2)
    axs[0].scatter(x, hv, s=60, color="#2a78d6", zorder=3, label="honest (causal)")
    axs[0].scatter(x, lv, s=60, color="#eb6834", zorder=3, label="leaky (C2a random windows)")
    axs[0].set_ylim(0.95, 1.0)
    axs[0].set_xticks(x, subs)
    axs[0].set_title("(a) window AUROC (dot plot, axis from 0.95): %s" % parts["a"], fontsize=10)
    axs[0].legend(fontsize=8, frameon=False, loc="lower right")
    for k, (m, lab) in enumerate((("NC1_iid_permutation", "NC1"), ("NC2_circular_shift", "NC2"))):
        d = ab["N1b"][m]["per_subject"]
        for i, s in enumerate(subs):
            v = [r["auroc"] for r in d[s]]
            axs[1].scatter(np.full(len(v), i + (k - 0.5) * 0.3), v, s=14, color=["#2a78d6", "#eb6834"][k],
                           label=lab if i == 0 else None)
    axs[1].axhspan(0.45, 0.55, color="#e4e3df")
    axs[1].set_xticks(x, subs)
    axs[1].set_ylim(0, 1)
    axs[1].set_title("(b) null-model window AUROC (band 0.45-0.55)", fontsize=10)
    axs[1].legend(fontsize=8, frameon=False)
    for k, (m, lab) in enumerate((("NC1_iid_permutation", "NC1"), ("NC2_circular_shift", "NC2"))):
        o = ab["N1b"][m]
        axs[2].bar(k - 0.2, o["pooled_tp"], 0.38, color="#2a78d6", label="observed pooled TP" if k == 0 else None)
        axs[2].bar(k + 0.2, o["shift_null_tp_p99"], 0.38, color="#b8b7b2", label="shift-null 99th pct" if k == 0 else None)
    axs[2].set_xticks([0, 1], ["NC1", "NC2"])
    axs[2].set_title("(b2) TP vs chance; C3 random-alarm F1 = %.3f" % ab["N1b"]["C3_random_alarm"]["mean_pooled_f1"], fontsize=10)
    axs[2].legend(fontsize=8, frameon=False)
    for ax in axs:
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
    fig.suptitle("N1 harness controls: %s  (a %s, b %s, c %s, d %s, e %s)        RESEARCH USE ONLY - NOT A MEDICAL DEVICE"
                 % (verdict, parts["a"], parts["b"], parts["c"], parts["d"], parts["e"]), fontsize=10, color="#0b0b0b")
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(os.path.join(ROOT, "figures", "N1_controls." + ext), dpi=130, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["synthetic", "final"], required=True)
    a = ap.parse_args()
    phase_synthetic() if a.phase == "synthetic" else phase_final()
