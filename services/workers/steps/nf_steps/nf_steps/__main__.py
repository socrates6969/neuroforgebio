"""Step entrypoint (the step image's ``nf-step`` command; also used by the subprocess runner).

    python -m nf_steps run --step nf_steps.filter@1 --params params.json --seed 42 --in IN --out OUT
    python -m nf_steps list

``IN`` holds ``signal.npy`` + ``signal.json``; ``OUT`` receives the output signal and ``step.json``
(resolved parameters, step info, environment). Exit codes: 0 ok, 2 step/parameter error (not
retryable), 1 anything else.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from nf_steps.base import StepError
from nf_steps.pipeline import run_step_files
from nf_steps.signal import SignalError

EXTRA_LIBRARIES_ENV = "NF_STEP_EXTRA_LIBRARIES"


def _extra_libraries() -> list[str]:
    return [x for x in os.environ.get(EXTRA_LIBRARIES_ENV, "").split(",") if x]


def cmd_run(args: argparse.Namespace) -> int:
    params = json.loads(Path(args.params).read_text("utf-8")) if args.params else {}
    try:
        run_step_files(args.step, params, args.seed, args.inp, args.out, _extra_libraries())
    except (StepError, SignalError) as e:
        print(f"step error: {e}", file=sys.stderr)  # noqa: T201
        return 2
    return 0


def cmd_list(_args: argparse.Namespace) -> int:
    from nf_steps import LIBRARY  # noqa: PLC0415

    for ref, st in sorted(LIBRARY.steps.items()):
        defaults = json.dumps(st.resolve({}), sort_keys=True)
        print(f"{ref}\t{st.tolerance}\t{defaults}")  # noqa: T201
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="nf-step")
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("--step", required=True)
    run.add_argument("--params")
    run.add_argument("--seed", type=int)
    run.add_argument("--in", dest="inp", required=True)
    run.add_argument("--out", required=True)
    run.set_defaults(fn=cmd_run)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
