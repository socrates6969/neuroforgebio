"""CLI: python -m nf_synth [--seed N] [--channels N] [--duration S] [--formats edf,bdf,vhdr,xdf]
[--out DIR]. Output defaults to .synth-out/ (git-ignored; data files must never be committed)."""

from __future__ import annotations

import argparse
from pathlib import Path

from .generate import SynthParams, generate
from .writers import WRITERS, write_truth


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="nf_synth", description=__doc__)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--channels", type=int, default=8)
    ap.add_argument("--sfreq", type=int, default=256)
    ap.add_argument("--duration", type=int, default=20, help="seconds (whole number)")
    ap.add_argument("--formats", default="edf,vhdr", help=f"comma list of {','.join(WRITERS)}")
    ap.add_argument("--out", default=".synth-out")
    a = ap.parse_args(argv)
    params = SynthParams(seed=a.seed, n_channels=a.channels, sfreq=a.sfreq, duration_s=a.duration)
    data, truth = generate(params)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"synth-seed{a.seed}"
    for fmt in filter(None, a.formats.split(",")):
        ext, writer = WRITERS[fmt]
        print(writer(out / f"{stem}{ext}", data, truth))
    print(write_truth(out / f"{stem}.truth.json", truth))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
