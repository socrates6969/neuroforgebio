"""2.7 wire rules without a server: generated stubs in sync with the .proto, chunk IDs per the 0.5
spec vectors, device tokens (SEC-016), chunk signatures bind the timing series (SEC-040/094),
the proto is device -> platform only (SEC-090, hw-guard) and states the ack timing rule
(SEC-093), the edge prototype never creates LSL outlets (SEC-091), sanity checks (SEC-041)."""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from nf_platform.ingest.stream import gen, sanity
from nf_platform.ingest.stream import protocol as rules
from nf_platform.ingest.stream._proto import ingest_pb2 as pb

ROOT = Path(__file__).resolve().parents[4]
PROTO = ROOT / "proto" / "ingest" / "v1" / "ingest.proto"
EDGE = ROOT / "services" / "platform" / "edge_prototype"
NODE22 = Path(r"C:\Users\mariu\.local\node22\node_modules\node\bin\node.exe")


def _pub(k: Ed25519PrivateKey) -> bytes:
    return k.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def test_committed_stubs_match_the_proto(tmp_path):
    pytest.importorskip("grpc_tools")
    for out in gen.generate(tmp_path):
        committed = (gen.OUT_DIR / out.name).read_text(encoding="utf-8")
        assert out.read_text(encoding="utf-8") == committed, f"regenerate {out.name} (gen.py)"


def test_chunk_ids_reproduce_the_spec_vectors():
    vectors = json.loads((ROOT / "spec" / "test-vectors" / "ids.json").read_text())["chunk"]
    assert vectors
    for v in vectors:
        cid = rules.chunk_id_bytes(v["dtype"], v["shape"], bytes.fromhex(v["data_hex"]))
        assert cid == v["id"], v["name"]
    # samples_to_bytes is little-endian C order whatever the host order
    a = np.array([[0, 1], [-1, 32767]], dtype=">i2")
    assert rules.samples_to_bytes(a, "int16") == bytes.fromhex("00000100ffffff7f")


def test_device_token_roundtrip_and_rejections():
    key, other = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    ids = {"tenant_id": "t", "device_id": "d", "stream_id": "s"}
    tok = rules.make_device_token(key, **ids, now=1_000_000)
    claims, payload, sig = rules.parse_device_token(tok)
    assert (claims.tenant_id, claims.device_id, claims.stream_id) == ("t", "d", "s")
    rules.verify_device_token(claims, payload, sig, _pub(key), now=1_000_010)
    # SEC-016: a token signed by another key -> rejected
    with pytest.raises(rules.ProtocolError, match="signature"):
        rules.verify_device_token(claims, payload, sig, _pub(other), now=1_000_010)
    with pytest.raises(rules.ProtocolError, match="expired"):
        rules.verify_device_token(claims, payload, sig, _pub(key), now=1_000_000 + 400)
    long = rules.make_device_token(key, **ids, lifetime_s=3600, now=1_000_000)
    c2, p2, s2 = rules.parse_device_token(long)
    with pytest.raises(rules.ProtocolError, match="lifetime"):
        rules.verify_device_token(c2, p2, s2, _pub(key), now=1_000_010)
    # tampering with the payload (another stream) breaks the signature
    pre, body, sg = tok.split(".")
    forged = rules.make_device_token(other, **{**ids, "stream_id": "s2"}, now=1_000_000)
    mixed = ".".join([pre, forged.split(".")[1], sg])
    c3, p3, s3 = rules.parse_device_token(mixed)
    with pytest.raises(rules.ProtocolError):
        rules.verify_device_token(c3, p3, s3, _pub(key), now=1_000_010)
    for bad in ("", "nfd1.x", "jwt.a.b", "nfd1.!!.??", "nfd1." + "A" * 3000 + ".x"):
        with pytest.raises(rules.ProtocolError):
            rules.parse_device_token(bad)


def _chunk(key, **kw) -> pb.Chunk:
    x = np.arange(12, dtype=np.float32).reshape(4, 3)
    raw = rules.samples_to_bytes(x, "float32")
    msg = pb.Chunk(
        stream_id="s",
        seq=5,
        n_samples=4,
        n_channels=3,
        dtype="float32",
        samples=raw,
        lsl_timestamps=[10.0, 10.001, 10.002, 10.003],
        clock_offsets=[pb.ClockOffset(collection_time=9.9, offset=0.0015)],
        local_clock=[pb.LocalClockSample(lsl_time=10.003, monotonic_time=55.5)],
        chunk_id=rules.chunk_id_bytes("float32", [4, 3], raw),
    )
    for k, v in kw.items():
        setattr(msg, k, v)
    rules.sign_chunk(msg, key)
    return msg


def test_chunk_signature_binds_samples_and_timing():
    key = Ed25519PrivateKey.generate()
    msg = _chunk(key)
    assert rules.verify_chunk_signature(msg, _pub(key))
    assert not rules.verify_chunk_signature(msg, _pub(Ed25519PrivateKey.generate()))
    for mutate in (
        lambda m: m.lsl_timestamps.__setitem__(2, 10.0025),  # SEC-094: timing is signed
        lambda m: m.clock_offsets[0].__setattr__("offset", 0.5),
        lambda m: m.local_clock[0].__setattr__("monotonic_time", 1.0),
        lambda m: m.__setattr__("seq", 6),
        lambda m: m.__setattr__("chunk_id", "chunk:sha256:" + "0" * 64),
    ):
        m2 = pb.Chunk()
        m2.CopyFrom(msg)
        mutate(m2)
        assert not rules.verify_chunk_signature(m2, _pub(key))


def test_samples_from_bytes_validates_shape():
    raw = rules.samples_to_bytes(np.zeros((4, 3), np.int16), "int16")
    assert rules.samples_from_bytes(raw, "int16", 4, 3).shape == (4, 3)
    for args in ((raw, "int16", 4, 4), (raw, "uint8", 4, 3), (raw, "int16", 0, 3)):
        with pytest.raises(rules.ProtocolError):
            rules.samples_from_bytes(*args)


# ---------------------------------------------------------------- SEC-090 / 091 / 093
def test_proto_is_device_to_platform_only_hw_guard():
    node = str(NODE22) if NODE22.exists() else shutil.which("node")
    if not node:
        pytest.skip("node not available; CI runs tools/hw-guard over proto/")
    r = subprocess.run(
        [node, str(ROOT / "tools" / "hw-guard" / "cli.mjs"), "--root", str(ROOT)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_proto_has_no_platform_to_device_surface():
    """Every RPC's request is device data or a query about the device's own stream; nothing in the
    responses addresses hardware (names checked independently of hw-guard's denylist)."""
    text = PROTO.read_text(encoding="utf-8")
    rpcs = [
        line.split()[1].split("(")[0]
        for line in text.splitlines()
        if line.strip().startswith("rpc ")
    ]
    assert rpcs == ["StreamChunks", "GetStreamState", "FinishStream"]
    for msg in (pb.StreamAck, pb.StreamState):
        names = {f.name for f in msg.DESCRIPTOR.fields}
        assert names <= {
            "stream_id",
            "next_seq",
            "accepted",
            "duplicates",
            "suspect",
            "n_samples",
            "state",
        }


def test_ack_timing_rule_is_stated_in_the_contract():
    text = PROTO.read_text(encoding="utf-8")
    assert "carries NO timing guarantee" in text  # SEC-093 doc test
    assert "MUST NOT block acquisition" in text
    assert "never rewrites" in text  # SEC-094


def test_edge_prototype_is_inlet_only():
    """SEC-091: no LSL outlet and no device handles outside tests/."""
    banned = {"StreamOutlet", "lsl_create_outlet", "serial", "usb", "hid", "bluetooth"}
    for path in EDGE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in banned:
                pytest.fail(f"{path.name}: {node.attr}")
            if isinstance(node, ast.Name) and node.id in banned:
                pytest.fail(f"{path.name}: {node.id}")
            if isinstance(node, ast.Import | ast.ImportFrom):
                mods = [a.name for a in node.names] + [getattr(node, "module", None) or ""]
                assert not any(m.split(".")[0] in ("serial", "usb", "hid", "bleak") for m in mods)


# ---------------------------------------------------------------- SEC-041 sanity rules
LIM = [sanity.ChannelLimit("EEG", "uV", 1.0, 0.0)] * 2


def _ts(start: float, n: int, sf: float = 1000.0) -> np.ndarray:
    return start + np.arange(n) / sf


def test_sanity_ok_and_each_violation():
    x = np.zeros((100, 2), np.float32)
    assert sanity.check_chunk(x, _ts(1.0, 100), 1000.0, 0.999, LIM) == []
    assert "timestamp jump between chunks" in sanity.check_chunk(
        x, _ts(5.0, 100), 1000.0, 1.099, LIM
    )
    back = sanity.check_chunk(x, _ts(0.5, 100), 1000.0, 1.099, LIM)  # spliced replay
    assert any("backwards" in r for r in back)
    t = _ts(1.0, 100)
    t[50] = t[49]
    assert "non-monotonic timestamps" in sanity.check_chunk(x, t, 1000.0, None, LIM)
    assert any("rate" in r for r in sanity.check_chunk(x, _ts(1.0, 100, 500.0), 1000.0, None, LIM))
    big = x.copy()
    big[3, 1] = 2e6  # 2 V at an EEG electrode
    assert "physically impossible amplitude" in sanity.check_chunk(
        big, _ts(1.0, 100), 1000.0, None, LIM
    )
    nan = x.copy()
    nan[0, 0] = np.nan
    assert "non-finite sample values" in sanity.check_chunk(nan, _ts(1.0, 100), 1000.0, None, LIM)
