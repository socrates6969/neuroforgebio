r"""M1 finalisation: reproducibility check (run1 vs fresh-process rerun card hash), harness verdict (prereg §6) and
final H1-H6 verdicts (harness-gated, A2). Writes results\M1_verdict.json.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from m1lib import NB_CODE  # noqa: E402,F401
from nfharness.provenance import card_hash, dumps  # noqa: E402

RES = r"C:\Users\mariu\neuro-company\research\neurobiology\motor-readout\results"


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main():
    c1 = json.load(open(os.path.join(RES, "M1_card_run1.json"), encoding="utf-8"))
    c2 = json.load(open(os.path.join(RES, "M1_card_rerun.json"), encoding="utf-8"))
    h1 = card_hash({k: v for k, v in c1.items() if k != "card_sha256_excl_runtime"})
    h2 = card_hash({k: v for k, v in c2.items() if k != "card_sha256_excl_runtime"})
    assert h1 == c1["card_sha256_excl_runtime"] and h2 == c2["card_sha256_excl_runtime"]
    repro = h1 == h2
    diff = [k for k in c1 if k != "runtime" and c1.get(k) != c2.get(k)]
    ctrl = c1["controls"]
    items = {
        "NC1": ctrl["NC1"]["pass_"],
        "NC2a": ctrl["NC2a"]["pass_"],
        "PL1": ctrl["PL1"]["pass_"],
        "PL2": ctrl.get("PL2", {}).get("pass_"),
        "PL3_gru": ctrl["PL3"]["pass_"],
        "guard_suite": c1["guard_suite"]["pass_"],
        "reproducibility": repro,
    }
    harness = all(v is True for v in items.values())
    H = c1["hypotheses_pre_harness"]
    final = {}
    for k, v in H.items():
        nt = str(v["verdict"]).startswith("NOT TESTED")
        final[k] = dict(verdict=v["verdict"] if (harness or nt) else "not verifiable: harness",
                        conditional_verdict_if_harness_passed=v["verdict"],
                        **{kk: vv for kk, vv in v.items() if kk != "verdict"})
    out = dict(
        ruo=c1["ruo"], prereg_sha256=c1["prereg_sha256"], input_lock_sha256=c1["input_lock_sha256"],
        inputs=c1["inputs"], code_sha256=c1["code_sha256"], nfharness_sha256_readonly=c1["nfharness_sha256_readonly"],
        packages=c1["packages"], python=c1["python"], seed=c1["seed"], rng_streams=c1["rng_streams"],
        A4_cuts=c1["A4_cuts"], A3=c1["A3"], split_lock_sha256=c1["split_lock_sha256"],
        frozen_models_sha256=c1["frozen_models_sha256"],
        card_run1_sha256=h1, card_rerun_sha256=h2, reproducible=repro, differing_top_level_keys=diff,
        card_files_sha256={"M1_card_run1.json": sha(os.path.join(RES, "M1_card_run1.json")),
                           "M1_card_rerun.json": sha(os.path.join(RES, "M1_card_rerun.json"))},
        harness_items=items, harness="PASS" if harness else "FAIL",
        abandonment=dict(A1="all files present, no sign-up, all hashes MATCH (D3 dropped by A4, not A1)",
                         A2="harness FAIL -> no decoder verdicts; exploratory; new prereg needed" if not harness else "harness PASS",
                         A3=c1["A3"], A4=dict(cuts=c1["A4_cuts"], runtime=c1["runtime"]),
                         A5="torch %s CPU wheel installed -> GRU tested" % c1["packages"].get("torch"),
                         A6="not evaluated (D3 cut by A4)" if not c1["D3"].get("tested") else "confirmed"),
        hypotheses=final,
        runtime_run1=c1["runtime"], runtime_rerun=c2["runtime"],
        this_script_sha256=sha(os.path.abspath(__file__)),
    )
    with open(os.path.join(RES, "M1_verdict.json"), "w", encoding="utf-8", newline="\n") as f:
        f.write(dumps(out))
    print("reproducible", repro, h1[:12], h2[:12], "harness", out["harness"], items)
    for k, v in final.items():
        print(k, v["verdict"], "| conditional:", v["conditional_verdict_if_harness_passed"])


if __name__ == "__main__":
    main()
