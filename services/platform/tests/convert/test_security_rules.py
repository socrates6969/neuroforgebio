"""SEC-061 (m2-data paths): no pickle / allow_pickle / unsafe torch.load in storage, signals or
converters. SEC-060: converters are not imported by the API layer (static check; the
import-linter contract owned by m2-core enforces the same in CI)."""

from __future__ import annotations

import re
from pathlib import Path

import nf_platform

PKG = Path(nf_platform.__file__).parent
OURS = [PKG / "storage", PKG / "signals", PKG / "ingest" / "convert"]
BANNED = [
    re.compile(r"^\s*(import|from)\s+(c?pickle|dill|joblib)\b", re.M),
    re.compile(r"allow_pickle\s*=\s*True"),
    re.compile(r"torch\.load\((?![^)]*weights_only\s*=\s*True)"),
    re.compile(r"\byaml\.load\((?![^)]*SafeLoader)"),
]


def _py(paths):
    for p in paths:
        yield from p.rglob("*.py")


def test_no_unsafe_deserialisation():
    files = list(_py(OURS))
    assert len(files) >= 10
    for f in files:
        text = f.read_text(encoding="utf-8")
        for rx in BANNED:
            assert not rx.search(text), f"{f.name}: {rx.pattern}"


def test_api_does_not_import_converters():
    api = PKG / "api"
    if not api.exists():
        return
    for f in _py([api]):
        assert "ingest.convert" not in f.read_text(encoding="utf-8"), f.name
