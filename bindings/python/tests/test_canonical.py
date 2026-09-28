"""nf-core (through the binding) against the frozen vectors and, differentially, against the
stdlib Python reference (``spec/reference/python/nf_canonical.py``) on random values."""

from __future__ import annotations

import json
import math
import struct
import sys

import neuroforge as nf
import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from inprocess import REPO
from neuroforge import _native

sys.path.insert(0, str(REPO / "spec/reference/python"))
import nf_canonical as ref  # noqa: E402

VEC = REPO / "spec/test-vectors"


def test_canonical_json_vectors():
    doc = json.loads((VEC / "canonical-json.json").read_text("utf-8"))
    for c in doc["cases"]:
        out = _native.canonicalize(c["input"])
        assert out.decode("utf-8") == c["canonical"], c["name"]
    for e in doc["errors"]:
        with pytest.raises(nf.canonical.CanonicalError):
            _native.canonicalize(e["input"])


def test_number_vectors():
    doc = json.loads((VEC / "numbers.json").read_text("utf-8"))
    for c in doc["cases"]:
        x = struct.unpack(">d", bytes.fromhex(c["ieee754"]))[0]
        assert nf.canonical.format_number(x) == c["canonical"]


def test_id_vectors():
    doc = json.loads((VEC / "ids.json").read_text("utf-8"))
    for b in doc["blob"]:
        assert nf.canonical.blob_id(bytes.fromhex(b["data_hex"])) == b["id"]
    for p in doc["pipeline_version"]:
        assert nf.canonical.pipeline_version_id(p["spec"]) == p["id"]
    for c in doc["chunk"]:
        arr = np.frombuffer(
            bytes.fromhex(c["data_hex"]), dtype=np.dtype(c["dtype"]).newbyteorder("<")
        )
        arr = arr.reshape(c["shape"]).astype(c["dtype"])
        assert nf.canonical.chunk_id(arr) == c["id"], c["name"]
    batches = [e["batch"] for e in doc["prov_batch_chain"]]
    assert nf.canonical.verify_chain(batches) == [e["id"] for e in doc["prov_batch_chain"]]


def test_blob_id_file_streams(tmp_path):
    p = tmp_path / "x.bin"
    data = bytes(range(256)) * 5000
    p.write_bytes(data)
    assert nf.canonical.blob_id_file(p) == (ref.blob_id(data), len(data))


# ---------------------------------------------------------------- differential
finite = st.floats(allow_nan=False, allow_infinity=False)
safe_ints = st.integers(min_value=-(2**53 - 1), max_value=2**53 - 1)
text = st.text(alphabet=st.characters(exclude_categories=("Cs",)), max_size=8)
json_values = st.recursive(
    st.none() | st.booleans() | safe_ints | finite | text,
    lambda inner: st.lists(inner, max_size=5) | st.dictionaries(text, inner, max_size=5),
    max_leaves=25,
)


@settings(max_examples=400, deadline=None)
@given(finite)
def test_numbers_match_reference(x):
    assert nf.canonical.format_number(x) == ref.format_number(x)


@settings(max_examples=100, deadline=None)
@given(st.integers(min_value=0, max_value=2**64 - 1))
def test_numbers_from_raw_bits_match_reference(bits):
    x = struct.unpack("<d", struct.pack("<Q", bits))[0]
    if not math.isfinite(x):
        return
    assert nf.canonical.format_number(x) == ref.format_number(x)


@settings(max_examples=300, deadline=None)
@given(json_values)
def test_values_match_reference(v):
    try:
        want = ref.canonicalize(v)
    except ref.CanonicalError:
        with pytest.raises(ValueError):
            nf.canonical.canonical(v)
        return
    assert nf.canonical.canonical(v) == want
