"""Command-line interface.

Usage::

    python -m nf_channel_estimator estimate <map.json|map.csv> [--m 2] [--survival 0.62] [--rule R1]
        [--seed 20260926] [--null-draws 10000] [--relabel] [--relabel-draws 5000]
        [--format auto|json|csv] [--compact]
    python -m nf_channel_estimator schema input|output

The result (JSON) goes to stdout; errors go to stderr as one line ``error: <message>``.

Exit codes:
    0  success
    1  unexpected internal error
    2  usage error or parameter out of range
    3  input file cannot be read or parsed (missing file, invalid JSON/CSV syntax)
    4  input parsed but fails validation (schema, labels, duplicates)
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from .estimate import (
    DEFAULT_SEED,
    DEFAULT_SURVIVAL,
    EstimateParams,
    ParameterError,
    estimate,
)
from .labels import RULES
from .pfmap import PFMapError, PFMapReadError, load_map
from .schema import input_schema, output_schema

EXIT_OK, EXIT_INTERNAL, EXIT_USAGE, EXIT_READ, EXIT_INVALID = 0, 1, 2, 3, 4


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="python -m nf_channel_estimator",
        description="Distinct-channel count estimator for projected-field maps. Research use "
        "only. Not a medical device. Not a stimulation protocol.",
    )
    sub = ap.add_subparsers(dest="action", required=True)
    est = sub.add_parser("estimate", help="estimate channel counts for one PF map")
    est.add_argument("path", help="PF map (.json, schema nf.pf-map/v1; or .csv)")
    est.add_argument("--m", type=int, default=2, help="electrodes per channel (default 2)")
    est.add_argument(
        "--survival",
        type=float,
        default=DEFAULT_SURVIVAL,
        help="independent electrode survival fraction for attrition (default 0.62)",
    )
    est.add_argument("--rule", choices=RULES, default="R1", help="rule for attrition (default R1)")
    est.add_argument("--seed", type=int, default=DEFAULT_SEED, help="seed (default 20260926)")
    est.add_argument(
        "--null-draws", type=int, default=10000, help="draws per null (default 10000; 0 = skip)"
    )
    est.add_argument("--relabel", action="store_true", help="also run the relabelling check")
    est.add_argument(
        "--reference-dir",
        default=None,
        help="directory with the third-party reference tables (not shipped; see "
        "THIRD_PARTY_NOTICE.md); default: $NF_CHANNELS_REFERENCE_DIR",
    )
    est.add_argument("--relabel-draws", type=int, default=5000, help="draws per fraction")
    est.add_argument("--format", choices=("auto", "json", "csv"), default="auto")
    est.add_argument("--compact", action="store_true", help="single-line JSON")
    sch = sub.add_parser("schema", help="print a JSON Schema")
    sch.add_argument("which", choices=("input", "output"))
    return ap


def _fail(code: int, msg: str) -> int:
    sys.stderr.write(f"error: {msg}\n")
    return code


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI; returns the exit code."""
    args = _parser().parse_args(argv)
    try:
        if args.action == "schema":
            doc = input_schema() if args.which == "input" else output_schema()
            sys.stdout.write(json.dumps(doc, indent=2) + "\n")
            return EXIT_OK
        params = EstimateParams(
            m=args.m,
            survival=args.survival,
            rule=args.rule,
            seed=args.seed,
            null_draws=args.null_draws,
            relabel=args.relabel,
            relabel_draws=args.relabel_draws,
        )
        params.validate()
        pf_map = load_map(args.path, args.format)
        result = estimate(pf_map, params, reference_dir=args.reference_dir).to_dict()
    except ParameterError as exc:
        return _fail(EXIT_USAGE, str(exc))
    except PFMapReadError as exc:
        return _fail(EXIT_READ, str(exc))
    except PFMapError as exc:
        return _fail(EXIT_INVALID, str(exc))
    except Exception as exc:  # last-resort handler, reported as exit 1
        return _fail(EXIT_INTERNAL, f"internal error: {type(exc).__name__}: {exc}")
    text = json.dumps(
        result,
        indent=None if args.compact else 2,
        ensure_ascii=True,
        allow_nan=False,
    )
    sys.stdout.write(text + "\n")
    return EXIT_OK
