"""``python -m nf_repro`` -- the reproducibility harness CLI (BUILD-GUIDE 3.5).

    python -m nf_repro check --out DIR [--seeds 1,2] [--runner subprocess|inprocess]
                             [--pipeline extra.json ...] [--extra-library LIB --extra-path P ...]
                             [--label x86-64]
    python -m nf_repro compare-arch A_DIR B_DIR --out DIR [--label x86-64-vs-arm64]

``check`` runs every published pipeline twice on synthetic fixtures and writes
``repro-report.json`` + ``repro-report.md``; exit 1 when any step is not reproducible.
``compare-arch`` compares two ``check`` output trees from different CPU architectures.
"""

from __future__ import annotations

import os

# Thread pins before numpy/BLAS load (same values as nf_steps.PINNED_ENV).
# forced, not setdefault: RESOURCE-RULES sets OMP_NUM_THREADS=4 for other work
for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_k] = "1"
os.environ["PYTHONHASHSEED"] = "0"

import argparse  # noqa: E402
import sys  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    from nf_runner.steprunner import InProcessRunner, SubprocessRunner  # noqa: PLC0415

    from nf_repro import harness  # noqa: PLC0415

    ap = argparse.ArgumentParser(prog="nf-repro")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--out", required=True)
    c.add_argument("--seeds", default="1")
    c.add_argument("--runner", choices=("subprocess", "inprocess"), default="subprocess")
    c.add_argument("--pipeline", action="append", default=[], help="extra PipelineVersion JSON")
    c.add_argument("--only-extra", action="store_true", help="skip the bundled v1 pipelines")
    c.add_argument("--extra-library", action="append", default=[])
    c.add_argument("--extra-path", action="append", default=[])
    c.add_argument("--label", default="")
    x = sub.add_parser("compare-arch")
    x.add_argument("a")
    x.add_argument("b")
    x.add_argument("--out", required=True)
    x.add_argument("--label", default="")
    args = ap.parse_args(argv)

    if args.cmd == "check":
        libs = tuple(args.extra_library)
        if args.runner == "subprocess":
            runner = SubprocessRunner(extra_paths=tuple(args.extra_path), extra_libraries=libs)
        else:
            sys.path[:0] = list(args.extra_path)
            runner = InProcessRunner(extra_libraries=libs)
        specs = harness.published_pipelines(args.pipeline)
        if args.only_extra:
            specs = specs[len(specs) - len(args.pipeline) :]
        seeds = [int(s) for s in args.seeds.split(",") if s]
        report = harness.check(
            specs, harness.synth_fixtures(seeds), args.out, runner=runner, extra_libraries=libs
        )
    else:
        report = harness.compare_trees(args.a, args.b, harness.published_pipelines())
    jpath, mpath = harness.write_report(report, args.out, label=args.label)
    print(mpath.read_text(encoding="utf-8"))  # noqa: T201
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
