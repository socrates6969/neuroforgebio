"""nf-core's write-ahead buffer is byte-compatible with the 2.7 prototype's (SEC-037), and its
chunks, signatures and device tokens are accepted by the server's protocol rules."""

from __future__ import annotations

import sys

import numpy as np
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)
from inprocess import REPO
from neuroforge import _native
from neuroforge.streaming import DeviceKey

sys.path.insert(0, str(REPO / "services/platform"))
from edge_prototype.wal import DpapiKeyProvider, WalError, WriteAheadLog  # noqa: E402
from nf_platform.ingest.stream import protocol as rules  # noqa: E402
from nf_platform.ingest.stream._proto import ingest_pb2 as pb  # noqa: E402


class FixedKey:
    def __init__(self, k: bytes) -> None:
        self.k = k

    def key(self) -> bytes:
        return self.k


def test_prototype_and_core_read_each_others_records(tmp_path):
    key = bytes(range(32))
    proto = WriteAheadLog(tmp_path / "w", "stream-9", FixedKey(key), fsync=False)
    core = _native.Wal(str(tmp_path / "w"), "stream-9", key, None, False)
    proto.append(0, b"from-prototype")
    core.append(1, b"from-nf-core")
    fresh = _native.Wal(str(tmp_path / "w"), "stream-9", key, None, False)
    assert fresh.pending() == [0, 1]
    assert fresh.read(0) == b"from-prototype"
    assert WriteAheadLog(tmp_path / "w", "stream-9", FixedKey(key)).read(1) == b"from-nf-core"
    # ciphertext on disk, bound to the stream id (AAD)
    blob = (tmp_path / "w" / "0000000000000001.nfwal").read_bytes()
    assert blob.startswith(b"NFWAL1") and b"from-nf-core" not in blob
    other = _native.Wal(str(tmp_path / "w"), "stream-8", key, None, False)
    with pytest.raises(_native.WalCorrupt):
        other.read(1)
    assert fresh.ack(1) == 1 and fresh.pending() == [1]  # the index is scanned on open
    with pytest.raises(WalError):
        WriteAheadLog(tmp_path / "w", "stream-9", FixedKey(bytes(32))).read(1)


@pytest.mark.skipif(sys.platform != "win32", reason="DPAPI is Windows-only")
def test_dpapi_sealed_key_is_shared_with_the_prototype(tmp_path):
    kp = DpapiKeyProvider(tmp_path / "wal.key")
    proto = WriteAheadLog(tmp_path / "w", "s", kp, fsync=False)
    proto.append(0, b"sealed")
    core = _native.Wal(str(tmp_path / "w"), "s", None, str(tmp_path / "wal.key"), False)
    assert core.read(0) == b"sealed"
    assert kp.key() not in (tmp_path / "wal.key").read_bytes()


def _seed(k: Ed25519PrivateKey) -> bytes:
    return k.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())


def test_core_chunks_and_tokens_pass_the_server_rules(tmp_path):
    pk = Ed25519PrivateKey.generate()
    key = DeviceKey.from_seed(_seed(pk))
    pub = pk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    assert bytes(key.public_key) == pub
    wal = _native.Wal(str(tmp_path / "w"), "st-1", None, None, False)
    w = _native.StreamWriter("st-1", "float32", 3, 4, key, wal)
    data = (np.arange(30, dtype=np.float32).reshape(10, 3) * 0.25).astype("<f4")
    ts = (100.0 + np.arange(10) / 250.0).astype("<f8")
    w.add_clock_offset(100.0, 0.0015)
    w.add_local_clock(100.0, 55.5)
    assert w.push(data.tobytes(), ts.tobytes()) == 2
    assert w.flush() is True
    msgs = [pb.Chunk.FromString(wal.read(s)) for s in wal.pending()]
    assert [m.seq for m in msgs] == [0, 1, 2]
    for m in msgs:
        assert rules.verify_chunk_signature(m, pub)
        assert m.chunk_id == rules.chunk_id_bytes(m.dtype, [m.n_samples, m.n_channels], m.samples)
    assert np.array_equal(
        np.concatenate([np.frombuffer(m.samples, "<f4").reshape(-1, 3) for m in msgs]), data
    )
    assert [x for m in msgs for x in m.lsl_timestamps] == list(ts)
    assert (msgs[0].clock_offsets[0].collection_time, msgs[0].clock_offsets[0].offset) == (
        100.0,
        0.0015,
    )
    # a tampered timestamp breaks the signature (SEC-094)
    msgs[1].lsl_timestamps[0] += 1e-6
    assert not rules.verify_chunk_signature(msgs[1], pub)
    tok = key.token("tn", "dev", "st-1", 300)
    claims, payload, sig = rules.parse_device_token(tok)
    rules.verify_device_token(claims, payload, sig, pub)
    assert (claims.tenant_id, claims.device_id, claims.stream_id) == ("tn", "dev", "st-1")
    other = Ed25519PrivateKey.generate().public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    with pytest.raises(rules.ProtocolError):
        rules.verify_device_token(claims, payload, sig, other)
