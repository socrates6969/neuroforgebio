"""Hashing spec v2 §9.6-§9.7 (docs/spec/hashing.md): the M6 registry's training-subject hash and
training-manifest digest (``nf_platform.registry.manifest``) reproduce
spec/test-vectors/ids-v2.json.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pytest
from nf_platform.registry import manifest

ROOT = Path(__file__).resolve().parents[4]
V2 = json.loads((ROOT / "spec" / "test-vectors" / "ids-v2.json").read_text(encoding="ascii"))


def test_tags_and_schema() -> None:
    assert manifest.SUBJECT_TAG == b"nf.training-subject.v1"
    assert manifest.MANIFEST_TAG == b"nf.training-manifest.v1"
    assert manifest.SCHEMA == "nf.training-manifest/v1"


@pytest.mark.parametrize("case", V2["training_subject"], ids=lambda c: c["subject_id"][-4:])
def test_training_subject_hash(case: dict) -> None:
    assert manifest.subject_hash(case["tenant_id"], case["subject_id"]) == case["hash"]
    # also when the caller passes uuid.UUID objects (how the registry calls it)
    t, s = uuid.UUID(case["tenant_id"]), uuid.UUID(case["subject_id"])
    assert manifest.subject_hash(t, s) == case["hash"]


@pytest.mark.parametrize("case", V2["training_manifest"], ids=lambda c: c["name"])
def test_training_manifest_digest(case: dict) -> None:
    a: dict[str, Any] = dict(case["args"])
    a["input_node_ids"] = [uuid.UUID(x) for x in a["input_node_ids"]]
    if a["parent_version_id"] is not None:
        a["parent_version_id"] = uuid.UUID(a["parent_version_id"])
    doc, digest = manifest.build(**a)
    assert doc == case["manifest"]
    assert digest == case["digest"]
    assert manifest.digest(case["manifest"]) == case["digest"]


def test_training_manifest_inputs_are_deduplicated() -> None:
    """§9.7: ``inputs`` are de-duplicated and sorted (BUG-HUNT M5); the vector case with duplicate
    inputs is reproduced by the parametrised test above."""
    case = {c["name"]: c for c in V2["training_manifest"]}["duplicate-inputs"]
    a: dict[str, Any] = dict(case["args"])
    ids = [uuid.UUID(x) for x in a["input_node_ids"]]
    assert len(ids) > len(set(ids))
    a["input_node_ids"] = ids + [str(ids[0]).upper()]
    doc, digest = manifest.build(**a)
    assert doc["inputs"] == sorted({str(i) for i in ids})
    assert (doc, digest) == (case["manifest"], case["digest"])
