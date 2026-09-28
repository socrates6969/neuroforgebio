"""Tests for tools/sbom-validate (offline CycloneDX 1.6 validation, EXC-150-1 condition 4)."""

from __future__ import annotations

import json
import shutil
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import validate  # noqa: E402

GOOD = {
    "bomFormat": "CycloneDX",
    "specVersion": "1.6",
    "version": 1,
    "components": [
        {
            "type": "file",
            "name": "arena_core_bg.wasm",
            "version": "0" * 40,
            "bom-ref": "arena:arena_core_bg.wasm",
            "hashes": [{"alg": "SHA-256", "content": "a" * 64}],
            "properties": [{"name": "nfb:supportLevel", "value": "maintained"}],
        },
        {
            "type": "library",
            "name": "serde",
            "version": "1.0.228",
            "purl": "pkg:cargo/serde@1.0.228",
            "bom-ref": "pkg:cargo/serde@1.0.228",
            "externalReferences": [
                {"type": "distribution", "url": "https://crates.io/crates/serde/1.0.228"}
            ],
            # A license with an SPDX id exercises the $ref into spdx.schema.json.
            "licenses": [{"license": {"id": "MIT"}}],
        },
    ],
    "dependencies": [
        {"ref": "arena:arena_core_bg.wasm", "dependsOn": ["pkg:cargo/serde@1.0.228"]},
        {"ref": "pkg:cargo/serde@1.0.228", "dependsOn": []},
    ],
}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Any socket use during validation fails the test: the validator must be fully offline."""

    def refuse(*a, **k):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)


def test_valid_bom_passes_offline():
    assert validate.errors(GOOD) == []


def test_invalid_boms_fail():
    bad_hash = json.loads(json.dumps(GOOD))
    bad_hash["components"][0]["hashes"][0]["content"] = "not-a-hash"
    assert validate.errors(bad_hash)
    bad_spdx = json.loads(json.dumps(GOOD))
    bad_spdx["components"][1]["licenses"][0]["license"]["id"] = "NOT-AN-SPDX-ID"
    assert validate.errors(bad_spdx), "the $ref into the vendored spdx schema must be enforced"
    bad_type = json.loads(json.dumps(GOOD))
    bad_type["components"][0]["type"] = "wasm"
    assert validate.errors(bad_type)


def test_tampered_schema_is_refused(tmp_path):
    d = tmp_path / "schema"
    shutil.copytree(validate.SCHEMA_DIR, d)
    p = d / "spdx.schema.json"
    p.write_bytes(p.read_bytes() + b" ")
    with pytest.raises(validate.IntegrityError):
        validate.validator(d)


def test_cli_exit_codes(tmp_path, capsys):
    good = tmp_path / "good.cdx.json"
    good.write_text(json.dumps(GOOD), "utf-8")
    bad = tmp_path / "bad.cdx.json"
    bad.write_text(json.dumps({**GOOD, "specVersion": 1.6}), "utf-8")
    assert validate.main([str(good)]) == 0
    assert validate.main([str(bad)]) == 1
    assert validate.main([]) == 2
