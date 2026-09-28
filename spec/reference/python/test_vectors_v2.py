"""The reference implementation reproduces every v2 vector in spec/test-vectors/ids-v2.json.

The platform code is checked against the same file in services/platform/tests/spec_v2.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
from pathlib import Path

import gen_vectors_v2
import nf_canonical as nc
import nf_ids_v2 as v2
import pytest

VEC = Path(__file__).resolve().parents[2] / "test-vectors"
V2 = json.loads((VEC / "ids-v2.json").read_text(encoding="ascii"))
V1 = json.loads((VEC / "ids.json").read_text(encoding="ascii"))
SECRET = bytes.fromhex(V2["test_key"]["secret_hex"])
PUBLIC = bytes.fromhex(V2["test_key"]["public_hex"])


# RFC 8032 §7.1 TEST 1-3 (secret, public, message, signature): checks the reference Ed25519.
RFC8032 = [
    (
        "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
        "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
        "",
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
        "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b",
    ),
    (
        "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
        "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
        "72",
        "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da"
        "085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00",
    ),
    (
        "c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
        "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025",
        "af82",
        "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac"
        "18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a",
    ),
]


@pytest.mark.parametrize("sk,pk,msg,sig", RFC8032)
def test_reference_ed25519_rfc8032(sk: str, pk: str, msg: str, sig: str) -> None:
    secret = bytes.fromhex(sk)
    assert v2.ed25519_public_key(secret).hex() == pk
    assert v2.ed25519_sign(secret, bytes.fromhex(msg)).hex() == sig
    assert v2.ed25519_verify(bytes.fromhex(pk), bytes.fromhex(msg), bytes.fromhex(sig))
    assert not v2.ed25519_verify(bytes.fromhex(pk), bytes.fromhex(msg) + b"x", bytes.fromhex(sig))


def test_test_key() -> None:
    assert v2.ed25519_public_key(SECRET) == PUBLIC


def test_audit_batch_chain() -> None:
    batches = [c["batch"] for c in V2["audit_batch_chain"]]
    ids = v2.verify_audit_chain(batches)
    assert ids == [c["id"] for c in V2["audit_batch_chain"]]
    for c in V2["audit_batch_chain"]:
        assert v2.audit_batch_payload(c["batch"]).decode("utf-8") == c["payload"]
        assert v2.ID_RE_V2.match(c["id"]) and not nc.ID_RE.match(c["id"])  # auditb is v2-only
        pre = nc.tagged_preimage(v2.TAG_AUDIT_BATCH, c["payload"].encode("utf-8"))
        assert c["id"] == "auditb:sha256:" + hashlib.sha256(pre).hexdigest()
    tampered = copy.deepcopy(batches)
    tampered[0]["events"][0]["outcome"] = "failure"
    with pytest.raises(nc.CanonicalError):
        v2.verify_audit_chain(tampered)


def test_audit_tag_separates_from_provb() -> None:
    # Same payload bytes under the v1 provb tag give a different digest (domain separation).
    payload = V2["audit_batch_chain"][0]["payload"].encode("utf-8")
    a = nc.sha256_hex(nc.tagged_preimage(v2.TAG_AUDIT_BATCH, payload))
    p = nc.sha256_hex(nc.tagged_preimage(nc.TAG_PROV_BATCH, payload))
    assert a != p


@pytest.mark.parametrize("case", V2["prov_node"], ids=lambda c: c["name"])
def test_prov_node_hash(case: dict) -> None:
    assert gen_vectors_v2.prov_node_record(case["args"]) == case["record"]
    assert nc.canonicalize(case["record"]).decode("utf-8") == case["payload"]
    assert v2.prov_node_hash(case["record"]) == case["hash"]
    assert v2.DIGEST_RE.match(case["hash"])


def test_consent_record_chain() -> None:
    recs = [c["record"] for c in V2["consent_record_chain"]]
    assert v2.verify_consent_chain(recs) == [c["hash"] for c in V2["consent_record_chain"]]
    for c in V2["consent_record_chain"]:
        assert nc.canonicalize(c["record"]).decode("utf-8") == c["payload"]
    tampered = copy.deepcopy(recs)
    tampered[0]["scopes"] = ["collection"]
    with pytest.raises(nc.CanonicalError):
        v2.verify_consent_chain(tampered)


def test_ruleset_content_sha256() -> None:
    rs = V2["ruleset"]
    assert nc.canonicalize(rs["rules"]).decode("utf-8") == rs["payload"]
    assert v2.ruleset_content_sha256(rs["rules"]) == rs["content_sha256"]


def test_sweep_variant_label() -> None:
    by = {c["name"]: c for c in V2["sweep_variant"]}
    assert by["one-factor"]["base"] == V1["pipeline_version"][0]["id"]
    for c in by.values():
        assert v2.sweep_variant_label(c["base"], c["params"]) == c["label"]
        full = nc.sha256_hex(nc.tagged_preimage(v2.TAG_SWEEP_VARIANT, c["payload"].encode()))
        assert c["label"] == full[:12]
    assert by["two-factors"]["label"] == by["factor-order-irrelevant"]["label"]


def test_training_subject_hash() -> None:
    cases = V2["training_subject"]
    for c in cases:
        assert v2.training_subject_hash(c["tenant_id"], c["subject_id"]) == c["hash"]
        pre = bytes.fromhex(c["preimage_hex"])
        assert pre.startswith(b"nf.training-subject.v1\x00")
        assert hashlib.sha256(pre).hexdigest() == c["hash"]
        assert v2.DIGEST_RE.match(c["hash"])
    # upper-case UUID input is folded to the lowercase canonical form
    assert cases[3]["tenant_id"] != cases[1]["tenant_id"]
    assert cases[3]["hash"] == cases[1]["hash"]
    assert len({c["hash"] for c in cases[:3]}) == 3
    with pytest.raises(nc.CanonicalError):
        v2.training_subject_hash("not-a-uuid", cases[0]["subject_id"])


@pytest.mark.parametrize("case", V2["training_manifest"], ids=lambda c: c["name"])
def test_training_manifest_digest(case: dict) -> None:
    assert v2.training_manifest(**case["args"]) == case["manifest"]
    assert nc.canonicalize(case["manifest"]).decode("utf-8") == case["payload"]
    assert v2.training_manifest_digest(case["manifest"]) == case["digest"]
    pre = nc.tagged_preimage(v2.TAG_TRAINING_MANIFEST, case["payload"].encode("utf-8"))
    assert hashlib.sha256(pre).hexdigest() == case["digest"]
    subjects = {c["hash"] for c in V2["training_subject"]}
    assert set(case["manifest"]["subjects"]) <= subjects
    assert case["manifest"]["n_subjects"] == len(case["manifest"]["subjects"])


def test_stream_chunk_signature() -> None:
    c = V2["stream_chunk_signature"]
    ch = c["chunk"]
    data = nc.chunk_bytes(ch["dtype"], ch["samples"])
    assert nc.chunk_id(ch["dtype"], [ch["n_samples"], ch["n_channels"]], data) == ch["chunk_id"]
    assert v2.stream_chunk_body(ch)["timing_sha256"] == c["timing_sha256"]
    assert nc.canonicalize(v2.stream_chunk_body(ch)).decode("utf-8") == c["body"]
    pre = v2.stream_chunk_preimage(ch)
    assert pre.hex() == c["preimage_hex"]
    assert pre.startswith(b"nf.stream-chunk.v1\x00")
    assert v2.ed25519_sign(SECRET, pre).hex() == c["signature_hex"]
    assert v2.ed25519_verify(PUBLIC, pre, bytes.fromhex(c["signature_hex"]))


def test_device_token() -> None:
    c = V2["device_token"]
    assert v2.device_token_payload(c["claims"]).decode("utf-8") == c["payload"]
    pre = v2.device_token_preimage(c["claims"])
    assert pre.hex() == c["preimage_hex"]
    assert v2.ed25519_sign(SECRET, pre).hex() == c["signature_hex"]
    assert v2.device_token(c["claims"], SECRET) == c["token"]
    prefix, p64, s64 = c["token"].split(".")
    assert prefix == "nfd1"
    assert base64.urlsafe_b64decode(p64 + "=" * (-len(p64) % 4)).decode() == c["payload"]
    assert base64.urlsafe_b64decode(s64 + "=" * (-len(s64) % 4)).hex() == c["signature_hex"]


def test_provb_signature() -> None:
    c = V2["provb_signature"]
    assert c["batch_id"] == V1["prov_batch_chain"][0]["id"]
    msg = v2.provb_signature_message(c["batch_id"])
    assert msg.hex() == c["message_hex"]
    assert v2.ed25519_verify(PUBLIC, msg, bytes.fromhex(c["signature_hex"]))


@pytest.mark.parametrize("name", ["prov_anchor", "consent_anchor"])
def test_anchor_signature(name: str) -> None:
    c = V2[name]
    part = v2.anchor_signed_part(c["document"])
    assert part.decode("utf-8") == c["signed_part"]
    assert v2.ed25519_verify(PUBLIC, part, bytes.fromhex(c["document"]["sig"]))
    assert c["document"]["key_id"] == V2["test_key"]["key_id"]


def test_consent_anchor_points_at_chain_head() -> None:
    assert V2["consent_anchor"]["document"]["head"] == V2["consent_record_chain"][-1]["hash"]


def test_deletion_certificate_signature() -> None:
    c = V2["deletion_certificate"]
    part = v2.certificate_signed_part(c["document"])
    assert part.decode("utf-8") == c["signed_part"]
    sig = base64.b64decode(c["document"]["signature"]["value"])
    assert v2.ed25519_verify(PUBLIC, part, sig)


def test_wal_aad() -> None:
    for c in V2["wal_aad"]:
        assert v2.wal_aad(c["stream_id"], c["seq"]).hex() == c["aad_hex"]


def test_v2_vectors_are_frozen() -> None:
    """Regenerating must not change a byte of ids-v2.json."""
    assert (VEC / "ids-v2.json").read_text(encoding="ascii") == gen_vectors_v2.dump_v2()


def test_training_manifest_inputs_are_deduplicated() -> None:
    """§9.7: ``inputs`` are de-duplicated and sorted (BUG-HUNT M5)."""
    a, b = "00000000-0000-4000-8000-000000000c01", "00000000-0000-4000-8000-000000000c02"
    by = {c["name"]: c for c in V2["training_manifest"]}
    args = dict(by["plain"]["args"], input_node_ids=[b, a, b, a.upper()])
    doc = v2.training_manifest(**args)
    assert doc["inputs"] == [a, b]
    dup = by["duplicate-inputs"]
    assert len(dup["args"]["input_node_ids"]) > len(set(dup["args"]["input_node_ids"]))
    assert dup["manifest"]["inputs"] == sorted(set(dup["manifest"]["inputs"]))
    assert dup["digest"] == by["plain"]["digest"]  # same set of inputs -> same digest


def test_consent_record_scopes_are_canonicalised_before_hashing() -> None:
    """§9.3: ``scopes`` are de-duplicated and sorted before hashing (BUG-HUNT L6)."""
    case = V2["consent_record_noncanonical_scopes"]
    rec = case["record"]
    assert rec["scopes"] != sorted(set(rec["scopes"]))  # the vector really is non-canonical
    assert v2.consent_record_hash(rec) == case["hash"]
    assert case["hash"] == V2["consent_record_chain"][0]["hash"]
    canon = dict(rec, scopes=sorted(set(rec["scopes"])))
    assert nc.canonicalize(canon).decode("utf-8") == case["payload"]
    assert rec["scopes"] == case["record"]["scopes"]  # the caller's record is not modified
