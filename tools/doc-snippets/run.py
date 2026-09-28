"""Doctest-style runner for the docs quickstarts (BUILD-GUIDE 4.5).

Every code block of every quickstart in ``apps/web/src/docs/quickstarts/*.json`` is executed, in
page order, in one Python namespace per quickstart, in a scratch directory that holds the demo
recording the quickstarts name (synthetic EDF from ``tools/synth``). A block in any language other
than Python fails the run: every block on the pages must be executable.

Targets:
- default: an in-process platform (``bindings/python/tests/inprocess.py``: PostgreSQL via pgserver
  or ``NF_TEST_DATABASE_URL``, the FastAPI app, a worker, the gRPC ingest service);
- staging (CI-only): ``NF_DOCS_STAGING_URL`` + ``NF_DOCS_STAGING_TOKEN`` (+ ``NF_DOCS_SESSION``,
  ``NF_DOCS_INGEST_TARGET``).

    python tools/doc-snippets/run.py            # exit 0 when every block ran
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "apps/web/src/docs/quickstarts"
DEMO_FILE = "sub-01_task-motor_eeg.edf"


@dataclass
class Block:
    page: str
    section: str
    language: str
    code: str


def pkg_name() -> str:
    brand = json.loads((REPO / "packages/content/brand.json").read_text("utf-8"))
    return brand["codeIdentifiers"]["pythonImport"]


def quickstarts() -> list[tuple[str, list[Block]]]:
    pkg = pkg_name()
    pages = []
    for f in DOCS.glob("*.json"):
        doc = json.loads(f.read_text("utf-8"))
        blocks = [
            Block(
                f.stem,
                s["id"],
                s["code"]["language"],
                "\n".join(s["code"]["lines"]).replace("{pkg}", pkg),
            )
            for s in doc["sections"]
            if "code" in s
        ]
        pages.append((doc["order"], f.stem, blocks))
    return [(name, blocks) for _, name, blocks in sorted(pages)]


def run_quickstarts(configure: Callable[[], None], workdir: Path) -> list[str]:
    """Execute every block; returns failure messages (empty = all passed)."""
    sys.path.insert(0, str(REPO / "tools/synth"))
    from nf_synth.generate import SynthParams, generate
    from nf_synth.writers import write_edf

    failures: list[str] = []
    total = 0
    for page, blocks in quickstarts():
        d = workdir / page
        d.mkdir(parents=True, exist_ok=True)
        data, truth = generate(SynthParams(seed=7))
        write_edf(d / DEMO_FILE, data, truth)
        configure()
        scope: dict = {"__name__": f"docs_{page.replace('-', '_')}"}
        for b in blocks:
            total += 1
            where = f"{page}#{b.section}"
            if b.language != "python":
                failures.append(f"{where}: language {b.language!r} cannot be executed")
                continue
            out = io.StringIO()
            try:
                with contextlib.chdir(d), contextlib.redirect_stdout(out):
                    exec(compile(b.code, where, "exec"), scope)  # noqa: S102 - our own docs
            except Exception:  # noqa: BLE001 - report every failing block
                failures.append(f"{where}:\n{traceback.format_exc(limit=4)}")
                break  # later blocks of this page depend on this one
            print(f"[docs] ok {where}: {out.getvalue().strip()[:120]!r}")  # noqa: T201
    print(f"[docs] {total} code blocks, {len(failures)} failure(s)")  # noqa: T201
    return failures


def main() -> int:
    staging = os.environ.get("NF_DOCS_STAGING_URL")
    with tempfile.TemporaryDirectory(prefix="nf-docs-") as tmp:
        work = Path(tmp)
        if staging:
            import neuroforge as nf

            def configure() -> None:
                nf.configure(
                    api_url=staging,
                    token=os.environ["NF_DOCS_STAGING_TOKEN"],
                    session=os.environ.get("NF_DOCS_SESSION"),
                    ingest_target=os.environ.get("NF_DOCS_INGEST_TARGET"),
                    synthetic=True,
                )

            failures = run_quickstarts(configure, work)
        else:
            sys.path.insert(0, str(REPO / "bindings/python/tests"))
            import inprocess

            with inprocess.platform_stack(work / "platform", grpc=True) as stack:
                failures = run_quickstarts(lambda: configure_inprocess(stack), work / "pages")
    for f in failures:
        print(f"[docs] FAILED {f}", file=sys.stderr)  # noqa: T201
    return 1 if failures else 0


def configure_inprocess(stack) -> None:
    import neuroforge as nf

    nf.configure(
        http=stack.http,
        token=stack.token,
        session=stack.session_id,
        ingest_target=stack.extra["ingest_target"],
        poll_interval=0.1,
    )


if __name__ == "__main__":
    sys.exit(main())
