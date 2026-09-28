"""The reference implementation reproduces every frozen vector in spec/test-vectors/."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import gen_vectors
import nf_canonical as nc
import pytest

VEC = Path(__file__).resolve().parents[2] / "test-vectors"


def load(name: str) -> dict:
    return json.loads((VEC / name).read_text(encoding="ascii"))


CANON = load("canonical-json.json")
NUMBERS = load("numbers.json")
IDS = load("ids.json")


@pytest.mark.parametrize("case", CANON["cases"], ids=lambda c: c["name"])
def test_canonical_json(case: dict) -> None:
    out = nc.canonicalize_text(case["input"])
    assert out.decode("utf-8") == case["canonical"]
    assert hashlib.sha256(out).hexdigest() == case["sha256"]
    # idempotent: canonical form is a fixed point
    assert nc.canonicalize_text(case["canonical"]) == out


@pytest.mark.parametrize("case", CANON["errors"], ids=lambda c: c["name"])
def test_canonical_errors(case: dict) -> None:
    with pytest.raises(nc.CanonicalError):
        nc.canonicalize_text(case["input"])


@pytest.mark.parametrize("case", NUMBERS["cases"], ids=lambda c: c["ieee754"])
def test_rfc8785_numbers(case: dict) -> None:
    assert nc.format_number(nc.float_from_bits(case["ieee754"])) == case["canonical"]


@pytest.mark.parametrize("case", NUMBERS["errors"], ids=lambda c: c["ieee754"])
def test_rfc8785_number_errors(case: dict) -> None:
    with pytest.raises(nc.CanonicalError):
        nc.format_number(nc.float_from_bits(case["ieee754"]))


def test_rfc8785_sort_order_matches_rfc() -> None:
    # Independent of our vectors: the order printed in RFC 8785 §3.2.3
    # (U+FB33 omitted because NFC changes it).
    case = next(c for c in CANON["cases"] if c["name"] == "rfc8785-sort-order")
    values = list(json.loads(case["canonical"]).values())
    assert values == [
        "Carriage Return",
        "One",
        "Control",
        "Latin Small Letter O With Diaeresis",
        "Euro Sign",
        "Emoji: Grinning Face",
    ]


def test_blob_ids() -> None:
    for v in IDS["blob"]:
        data = bytes.fromhex(v["data_hex"])
        assert nc.blob_id(data) == v["id"] == "blob:sha256:" + hashlib.sha256(data).hexdigest()


def test_pipeline_version_ids() -> None:
    pv = {v["name"]: v for v in IDS["pipeline_version"]}
    for v in pv.values():
        assert nc.pipeline_version_payload(v["spec"]).decode("utf-8") == v["payload"]
        assert nc.pipeline_version_id(v["spec"]) == v["id"]
    assert pv["eeg-basic@1.2.0"]["id"] == pv["renamed-same-content"]["id"]  # meta not hashed
    assert pv["eeg-basic@1.2.0"]["id"] != pv["highpass-changed"]["id"]


def test_pipeline_version_requires_pinned_images() -> None:
    spec = json.loads(json.dumps(IDS["pipeline_version"][0]["spec"]))
    spec["steps"][0]["image"] = "ghcr.io/example/nf-steps:latest"
    with pytest.raises(nc.CanonicalError):
        nc.pipeline_version_id(spec)


def test_chunk_ids() -> None:
    for v in IDS["chunk"]:
        data = nc.chunk_bytes(v["dtype"], v["values"])
        assert data.hex() == v["data_hex"]
        assert nc.chunk_preimage(v["dtype"], v["shape"], data).hex() == v["preimage_hex"]
        assert nc.chunk_id(v["dtype"], v["shape"], data) == v["id"]
        assert (
            v["id"]
            == "chunk:sha256:" + hashlib.sha256(bytes.fromhex(v["preimage_hex"])).hexdigest()
        )
    a, b = IDS["chunk"][1], IDS["chunk"][2]
    assert a["data_hex"] == b["data_hex"] and a["id"] != b["id"]  # shape is part of identity


def test_prov_batch_chain() -> None:
    batches = [v["batch"] for v in IDS["prov_batch_chain"]]
    assert nc.verify_chain(batches) == [v["id"] for v in IDS["prov_batch_chain"]]
    for v in IDS["prov_batch_chain"]:
        assert nc.prov_batch_payload(v["batch"]).decode("utf-8") == v["payload"]
    tampered = json.loads(json.dumps(batches))
    tampered[1]["records"][0]["label"] = "edited"
    with pytest.raises(nc.CanonicalError):
        nc.verify_chain(tampered)  # batch 2's prev no longer matches


def test_vectors_are_frozen() -> None:
    """Regenerating must not change a byte: a change means a new spec version, not an edit."""
    for name, obj in gen_vectors.build().items():
        assert (VEC / name).read_text(encoding="ascii") == gen_vectors.dump(obj), name
