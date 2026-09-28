"""Clean-runner smoke test of an installed `neuroforge` wheel (sdk-wheels.yml, install-test):
the frozen hashing vectors must pass through the installed extension. Standard library + the
wheel only.

    python tools/doc-snippets/smoke.py spec/test-vectors
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path


def main(vec: Path) -> int:
    import neuroforge as nf
    from neuroforge import _native

    cj = json.loads((vec / "canonical-json.json").read_text("utf-8"))
    for c in cj["cases"]:
        assert _native.canonicalize(c["input"]).decode("utf-8") == c["canonical"], c["name"]
    for e in cj["errors"]:
        try:
            _native.canonicalize(e["input"])
        except ValueError:
            continue
        raise AssertionError(f"error case accepted: {e['name']}")
    for c in json.loads((vec / "numbers.json").read_text("utf-8"))["cases"]:
        x = struct.unpack(">d", bytes.fromhex(c["ieee754"]))[0]
        assert nf.canonical.format_number(x) == c["canonical"]
    ids = json.loads((vec / "ids.json").read_text("utf-8"))
    for b in ids["blob"]:
        assert nf.canonical.blob_id(bytes.fromhex(b["data_hex"])) == b["id"]
    for p in ids["pipeline_version"]:
        assert nf.canonical.pipeline_version_id(p["spec"]) == p["id"]
    chain = ids["prov_batch_chain"]
    assert nf.canonical.verify_chain([e["batch"] for e in chain]) == [e["id"] for e in chain]
    print(f"neuroforge {nf.__version__} (nf-core {nf.core_version}): vectors OK")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else "spec/test-vectors")))
