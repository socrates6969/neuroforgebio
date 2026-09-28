"""Hashing spec v2 (docs/spec/hashing.md §8-§10): the PLATFORM code paths reproduce every vector in
spec/test-vectors/ids-v2.json, the file the stdlib reference (spec/reference/python) generates and
checks. If a platform function changes its bytes, this fails, so the spec and the code cannot drift.

No database, no network: only the pure functions that build each tag (and the real verification
paths where they take a store or a key).
"""

from __future__ import annotations

import base64
import copy
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from edge_prototype import wal
from nf_platform.audit import _canonical as cj
from nf_platform.audit import chain as audit_chain
from nf_platform.governance import certificate, consent, rules
from nf_platform.ingest.stream import protocol
from nf_platform.ingest.stream._proto import ingest_pb2 as pb
from nf_platform.provenance import chain as prov_chain
from nf_platform.provenance import integrity, signing
from nf_platform.sweeps import service as sweeps

ROOT = Path(__file__).resolve().parents[4]
V2 = json.loads((ROOT / "spec" / "test-vectors" / "ids-v2.json").read_text(encoding="ascii"))
V1 = json.loads((ROOT / "spec" / "test-vectors" / "ids.json").read_text(encoding="ascii"))
SECRET = bytes.fromhex(V2["test_key"]["secret_hex"])
PUBLIC = bytes.fromhex(V2["test_key"]["public_hex"])
KEY_ID = V2["test_key"]["key_id"]


def _dt(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)


def _keyring() -> signing.Keyring:
    return signing.Keyring(signing.Ed25519Signer.from_seed(SECRET, KEY_ID))


class _Store:
    """In-memory stand-in for the ObjectStore subset the anchor readers use."""

    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = objects

    def get(self, bucket: str, key: str) -> bytes:
        return self.objects[key]

    def list(self, bucket: str, prefix: str) -> Iterator[str]:
        return iter(k for k in self.objects if k.startswith(prefix))

    def put(self, bucket: str, key: str, data: bytes, *, metadata: Any = None) -> None:
        self.objects[key] = data


def test_test_key_matches_platform_signer() -> None:
    signer = signing.Ed25519Signer.from_seed(SECRET, KEY_ID)
    raw = Ed25519PrivateKey.from_private_bytes(SECRET).public_key()
    assert signer.public_key().public_bytes_raw() == PUBLIC == raw.public_bytes_raw()


def test_vendored_tagged_preimage_is_v1_construction() -> None:
    assert cj.tagged_preimage("nf.x.v1", b"{}") == b"nf.x.v1\x00{}"


# ---------------------------------------------------------------- §9 hash tags
def test_audit_batch_chain() -> None:
    batches = [c["batch"] for c in V2["audit_batch_chain"]]
    ids = [c["id"] for c in V2["audit_batch_chain"]]
    for c in V2["audit_batch_chain"]:
        assert audit_chain.batch_payload(c["batch"]).decode("utf-8") == c["payload"]
        assert audit_chain.batch_id(c["batch"]) == c["id"]
        assert audit_chain.ID_RE.match(c["id"])
    assert audit_chain.verify_chain(batches, expected_head=ids[-1]) == ids
    tampered = copy.deepcopy(batches)
    tampered[0]["events"][0]["outcome"] = "failure"
    with pytest.raises(audit_chain.AuditChainError):
        audit_chain.verify_chain(tampered)
    assert (audit_chain.SCHEMA, audit_chain.TAG, audit_chain.KIND) == (
        "nf.audit-batch/v1",
        "nf.audit-batch.v1",
        "auditb",
    )


@pytest.mark.parametrize("case", V2["prov_node"], ids=lambda c: c["name"])
def test_prov_node_hash(case: dict) -> None:
    a = case["args"]
    rec = prov_chain.node_record(
        a["node_id"], a["kind"], a["type"], a["ref"], a["content"], a["attrs"]
    )
    assert rec == case["record"]
    assert cj.canonicalize(rec).decode("utf-8") == case["payload"]
    assert prov_chain.node_hash(rec) == case["hash"]
    assert prov_chain.NODE_TAG == "nf.prov-node.v1"


def test_consent_record_chain() -> None:
    prev = None
    for seq, c in enumerate(V2["consent_record_chain"]):
        a = c["args"]
        doc = consent.record_doc(
            tenant_id=c["record"]["tenant"],
            seq=seq,
            prev=prev,
            record_id=a["record_id"],
            subject_id=a["subject_id"],
            kind=a["kind"],
            scopes=a["scopes"],
            document_id=a["document_id"],
            document_sha256=a["document_sha256"],
            basis=a["basis"],
            collector=a["collector"],
            evidence=a["evidence"],
            recorded_at=_dt(a["recorded_at"]),
        )
        assert doc == c["record"]
        assert cj.canonicalize(doc).decode("utf-8") == c["payload"]
        assert consent.record_hash(doc) == c["hash"]
        prev = c["hash"]
    assert (consent.TAG, consent.SCHEMA) == ("nf.consent-record.v1", "nf.consent-record/v1")


def test_consent_record_hash_canonicalises_scopes() -> None:
    """§9.3: ``scopes`` are de-duplicated and sorted before hashing (BUG-HUNT L6)."""
    case = V2["consent_record_noncanonical_scopes"]
    rec = dict(case["record"])
    assert rec["scopes"] != sorted(set(rec["scopes"]))
    assert consent.record_hash(rec) == case["hash"]
    assert rec == case["record"]  # the caller's record is not modified


def _rule(p: dict[str, Any]) -> rules.Rule:
    return rules.Rule(
        id=p["id"],
        jurisdiction=p["jurisdiction"],
        title=p["title"],
        instrument=p["instrument"],
        status_text=p["status_text"],
        effective_date=p["effective_date"],
        citation=p["citation"],
        predicate=p["predicate"],
        obligations=tuple(
            rules.Obligation(o["id"], o["text"], o.get("flag")) for o in p["obligations"]
        ),
        review_status=p["review_status"],
        review=p["review"],
        notes=p["notes"],
        assumptions=tuple(p["assumptions"]),
    )


def test_ruleset_content_hash() -> None:
    rs = V2["ruleset"]
    objs = [_rule(p) for p in rs["rules"]]
    assert [r.public() for r in objs] == rs["rules"]
    assert rules.content_hash(objs) == rs["content_sha256"]
    assert rules.HASH_TAG == "nf.ruleset.v1"


@pytest.mark.parametrize("case", V2["sweep_variant"], ids=lambda c: c["name"])
def test_sweep_variant_label(case: dict) -> None:
    assert sweeps.variant_label(case["base"], case["params"]) == case["label"]
    assert sweeps.VARIANT_TAG == "nf.sweep-variant.v1"


# ---------------------------------------------------------------- §10 signatures and AAD
def _chunk_msg(ch: dict[str, Any]) -> Any:
    samples = np.array(ch["samples"], dtype=ch["dtype"]).reshape(ch["n_samples"], ch["n_channels"])
    data = protocol.samples_to_bytes(samples, ch["dtype"])
    return pb.Chunk(
        stream_id=ch["stream_id"],
        seq=ch["seq"],
        n_samples=ch["n_samples"],
        n_channels=ch["n_channels"],
        dtype=ch["dtype"],
        samples=data,
        lsl_timestamps=ch["lsl_timestamps"],
        clock_offsets=[pb.ClockOffset(collection_time=a, offset=b) for a, b in ch["clock_offsets"]],
        local_clock=[
            pb.LocalClockSample(lsl_time=a, monotonic_time=b) for a, b in ch["local_clock"]
        ],
        chunk_id=protocol.chunk_id_bytes(ch["dtype"], samples.shape, data),
    )


def test_stream_chunk_signature() -> None:
    c = V2["stream_chunk_signature"]
    ch = c["chunk"]
    msg = _chunk_msg(ch)
    assert msg.chunk_id == ch["chunk_id"]
    assert (
        protocol.timing_sha256(ch["lsl_timestamps"], ch["clock_offsets"], ch["local_clock"])
        == c["timing_sha256"]
    )
    assert protocol.signing_payload(msg).hex() == c["preimage_hex"]
    protocol.sign_chunk(msg, Ed25519PrivateKey.from_private_bytes(SECRET))
    assert bytes(msg.signature).hex() == c["signature_hex"]
    assert protocol.verify_chunk_signature(msg, PUBLIC)
    msg.seq += 1
    assert not protocol.verify_chunk_signature(msg, PUBLIC)


def test_device_token() -> None:
    c = V2["device_token"]
    cl = c["claims"]
    token = protocol.make_device_token(
        Ed25519PrivateKey.from_private_bytes(SECRET),
        tenant_id=cl["tenant_id"],
        device_id=cl["device_id"],
        stream_id=cl["stream_id"],
        lifetime_s=cl["exp"] - cl["iat"],
        now=cl["iat"],
    )
    assert token == c["token"]
    claims, payload, sig = protocol.parse_device_token(token)
    assert payload.decode("utf-8") == c["payload"]
    assert sig.hex() == c["signature_hex"]
    protocol.verify_device_token(claims, payload, sig, PUBLIC, now=cl["iat"] + 1)
    assert protocol.TAG_DEVICE_TOKEN == "nf.device-token.v1"


def test_provb_signature() -> None:
    c = V2["provb_signature"]
    assert prov_chain.batch_id(V1["prov_batch_chain"][0]["batch"]) == c["batch_id"]
    kr = _keyring()
    # provenance/api.py signs and verifies exactly these bytes: batch_id.encode("ascii")
    assert kr.signer.sign(c["batch_id"].encode("ascii")).hex() == c["signature_hex"]
    assert kr.verify(KEY_ID, bytes.fromhex(c["message_hex"]), bytes.fromhex(c["signature_hex"]))


def test_prov_anchor() -> None:
    c = V2["prov_anchor"]
    doc = c["document"]
    assert integrity._signed_part(doc).decode("utf-8") == c["signed_part"]
    assert _keyring().signer.sign(integrity._signed_part(doc)).hex() == doc["sig"]
    key = integrity.anchor_key(doc["tenant"], _dt(doc["anchored_at"]))
    store = _Store({key: cj.canonicalize(doc)})
    assert integrity.latest_anchor(store, doc["tenant"], _keyring()) == doc
    assert doc["schema"] == integrity.SCHEMA


def test_consent_anchor() -> None:
    c = V2["consent_anchor"]
    doc = c["document"]
    assert consent._signed_part(doc).decode("utf-8") == c["signed_part"]
    assert _keyring().signer.sign(consent._signed_part(doc)).hex() == doc["sig"]
    key = consent.anchor_key(doc["tenant"], _dt(doc["anchored_at"]))
    store = _Store({key: cj.canonicalize(doc)})
    assert consent.latest_anchor(store, doc["tenant"], _keyring()) == doc
    assert doc["schema"] == consent.ANCHOR_SCHEMA


def test_deletion_certificate() -> None:
    doc = V2["deletion_certificate"]["document"]
    assert certificate._payload(doc).decode("utf-8") == V2["deletion_certificate"]["signed_part"]
    assert certificate.verify(doc, base64.b64encode(PUBLIC).decode())
    certificate.configure(signing.Ed25519Signer.from_seed(SECRET, KEY_ID))
    try:
        unsigned = {k: v for k, v in doc.items() if k != "signature"}
        assert certificate.sign(unsigned) == doc
    finally:
        certificate.configure(None)
    bad = copy.deepcopy(doc)
    bad["subject_pseudonym"] = "P-018"
    assert not certificate.verify(bad, base64.b64encode(PUBLIC).decode())


@pytest.mark.parametrize("case", V2["wal_aad"], ids=lambda c: str(c["seq"]))
def test_wal_aad(case: dict, tmp_path: Path) -> None:
    log = wal.WriteAheadLog(tmp_path, case["stream_id"], wal.EphemeralKeyProvider(), fsync=False)
    assert log._aad(case["seq"]).hex() == case["aad_hex"]


def test_cryptography_agrees_with_reference_signatures() -> None:
    # Independent of the platform wrappers: the library verifies what the stdlib reference signed.
    pub = Ed25519PublicKey.from_public_bytes(PUBLIC)
    c = V2["stream_chunk_signature"]
    pub.verify(bytes.fromhex(c["signature_hex"]), bytes.fromhex(c["preimage_hex"]))
