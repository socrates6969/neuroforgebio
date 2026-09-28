"""``python -m nf_train evaluate [--seeds 0 1 2] [--shards 4] [--slices 3]``: print the measured
SISA-vs-full-retraining comparison as JSON (tools/synth must be on PYTHONPATH)."""

from __future__ import annotations

import argparse
import json
import sys

from nf_train import evaluate


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="nf_train")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ev = sub.add_parser("evaluate", help="measure SISA vs full retraining on the toy dataset")
    ev.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    ev.add_argument("--shards", type=int, default=4)
    ev.add_argument("--slices", type=int, default=3)
    ev.add_argument("--n-train", type=int, default=48)
    ev.add_argument("--n-test", type=int, default=24)
    args = ap.parse_args(argv)
    results = [
        evaluate.run(
            s, n_train=args.n_train, n_test=args.n_test, shards=args.shards, slices=args.slices
        )
        for s in args.seeds
    ]
    json.dump(
        {"runs": results, "summary": evaluate.summary(results)}, sys.stdout, indent=2, default=list
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
