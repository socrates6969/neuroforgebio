"""Generate spec/test-vectors/*.json from the reference implementation.

Run only when the spec changes on purpose (vectors are FROZEN; a change is a new spec version):
    .venv/Scripts/python.exe spec/reference/python/gen_vectors.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import nf_canonical as nc

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "spec" / "test-vectors"

# (name, JSON input text, note). The expected output is computed, then frozen in the vector file.
CANONICAL_CASES: list[tuple[str, str, str]] = [
    (
        "sort-keys-nested",
        '{"b":1,"a":2,"c":{"z":null,"y":[true,false]}}',
        "keys sorted at every level",
    ),
    ("whitespace", ' {\n "a" : [ 1 , 2 ] ,\t"b":"x y" } ', "insignificant whitespace removed"),
    (
        "rfc8785-sort-order",
        '{"\\u20ac":"Euro Sign","\\r":"Carriage Return","1":"One",'
        '"\\ud83d\\ude00":"Emoji: Grinning Face","\\u0080":"Control",'
        '"\\u00f6":"Latin Small Letter O With Diaeresis"}',
        "RFC 8785 §3.2.3 example without U+FB33: UTF-16 code-unit order",
    ),
    ("nfc-value", '{"name":"Caf\\u0065\\u0301"}', "e + U+0301 becomes U+00E9"),
    ("nfc-key", '{"\\u0041\\u030a":1}', "A + U+030A becomes U+00C5"),
    (
        "nfc-composition-exclusion",
        '{"\\ufb33":"x"}',
        "U+FB33 decomposes to U+05D3 U+05BC under NFC",
    ),
    (
        "string-escapes",
        '"\\u0000\\u001f\\b\\f\\n\\r\\t\\"\\\\\\/\\u007f\\u2028\\u00e9"',
        "short escapes; other controls as \\u00xx; '/', DEL, U+2028, non-ASCII literal",
    ),
    (
        "numbers",
        "[1.0,-0,0.0,1e21,1E-7,100,123456789012345,0.1,-2.5e-3,9007199254740991]",
        "RFC 8785 number form",
    ),
    ("empty-containers", '{"a":{},"b":[],"c":""}', "empty object, array, string"),
    ("array-order-kept", '[3,1,2,["b","a"]]', "arrays are not sorted"),
    ("utf8-literal", '"\\u65e5\\u672c\\u8a9e \\ud83e\\udde0"', "non-ASCII is emitted as UTF-8"),
    ("literals", "[null,true,false]", "literals"),
]

ERROR_CASES: list[tuple[str, str, str]] = [
    ("duplicate-key", '{"a":1,"a":2}', "duplicate key"),
    ("duplicate-after-nfc", '{"\\u00e9":1,"e\\u0301":2}', "keys equal after NFC"),
    ("unsafe-integer", "9007199254740992", "integer literal above 2^53-1"),
    ("nan", "NaN", "NaN is not JSON"),
    ("infinity", "[Infinity]", "Infinity is not JSON"),
    ("lone-surrogate", '"\\ud800"', "lone surrogate"),
]

# RFC 8785 Appendix B (rfc-editor.org/rfc/rfc8785.txt, opened 2026-09-26).
RFC8785_NUMBERS = [
    ("0000000000000000", "0"),
    ("8000000000000000", "0"),
    ("0000000000000001", "5e-324"),
    ("8000000000000001", "-5e-324"),
    ("7fefffffffffffff", "1.7976931348623157e+308"),
    ("ffefffffffffffff", "-1.7976931348623157e+308"),
    ("4340000000000000", "9007199254740992"),
    ("c340000000000000", "-9007199254740992"),
    ("4430000000000000", "295147905179352830000"),
    ("44b52d02c7e14af5", "9.999999999999997e+22"),
    ("44b52d02c7e14af6", "1e+23"),
    ("44b52d02c7e14af7", "1.0000000000000001e+23"),
    ("444b1ae4d6e2ef4e", "999999999999999700000"),
    ("444b1ae4d6e2ef4f", "999999999999999900000"),
    ("444b1ae4d6e2ef50", "1e+21"),
    ("3eb0c6f7a0b5ed8c", "9.999999999999997e-7"),
    ("3eb0c6f7a0b5ed8d", "0.000001"),
    ("41b3de4355555553", "333333333.3333332"),
    ("41b3de4355555554", "333333333.33333325"),
    ("41b3de4355555555", "333333333.3333333"),
    ("41b3de4355555556", "333333333.3333334"),
    ("41b3de4355555557", "333333333.33333343"),
    ("becbf647612f3696", "-0.0000033333333333333333"),
    ("43143ff3c1cb0959", "1424953923781206.2"),
]
RFC8785_NUMBER_ERRORS = ["7fffffffffffffff", "7ff0000000000000"]

IMG = "ghcr.io/example/nf-steps@sha256:" + "ab" * 32


def pipeline_spec(name: str, version: str, highpass: float) -> dict[str, Any]:
    return {
        "schema": "nf.pipeline-version/v1",
        "meta": {"name": name, "version": version, "description": "Illustrative test vector"},
        "steps": [
            {
                "name": "filter",
                "image": IMG,
                "entrypoint": ["nf-step", "filter"],
                "params": {"l_freq": highpass, "h_freq": 40.0, "method": "fir", "phase": "zero"},
                "tolerance": {"kind": "exact"},
            },
            {
                "name": "rereference",
                "image": IMG,
                "entrypoint": ["nf-step", "reref"],
                "params": {"ref_channels": "average"},
                "tolerance": {"kind": "abs", "value": 1e-9},
            },
        ],
        "seed": 42,
    }


def prov_chain() -> list[dict[str, Any]]:
    records = [
        [
            {
                "type": "entity",
                "id": "ent-0001",
                "label": "raw",
                "content": nc.blob_id(b"synthetic recording 1"),
            },
            {"type": "activity", "id": "act-0001", "label": "ingest"},
            {"type": "edge", "rel": "wasGeneratedBy", "from": "ent-0001", "to": "act-0001"},
        ],
        [{"type": "activity", "id": "act-0002", "label": "run"}],
        [{"type": "edge", "rel": "used", "from": "act-0002", "to": "ent-0001"}],
    ]
    batches: list[dict[str, Any]] = []
    prev = None
    for seq, recs in enumerate(records):
        b = {
            "schema": "nf.prov-batch/v1",
            "tenant": "tn_test",
            "seq": seq,
            "prev": prev,
            "created_at": f"2026-09-26T12:00:0{seq}.000Z",
            "records": recs,
        }
        batches.append(b)
        prev = nc.prov_batch_id(b)
    return batches


def build() -> dict[str, Any]:
    canonical = {
        "spec": "docs/spec/hashing.md §3",
        "cases": [
            {
                "name": n,
                "note": note,
                "input": text,
                "canonical": nc.canonicalize_text(text).decode("utf-8"),
                "sha256": nc.sha256_hex(nc.canonicalize_text(text)),
            }
            for n, text, note in CANONICAL_CASES
        ],
        "errors": [{"name": n, "note": note, "input": text} for n, text, note in ERROR_CASES],
    }
    numbers = {
        "spec": "docs/spec/hashing.md §3.3; source: RFC 8785 Appendix B",
        "cases": [{"ieee754": h, "canonical": s} for h, s in RFC8785_NUMBERS],
        "errors": [{"ieee754": h} for h in RFC8785_NUMBER_ERRORS],
    }
    blobs = [b"", b"hello\n", bytes(range(256))]
    specs = [
        ("eeg-basic@1.2.0", pipeline_spec("eeg-basic", "1.2.0", 0.1)),
        ("renamed-same-content", pipeline_spec("my-copy", "9.9.9", 0.1)),
        ("highpass-changed", pipeline_spec("eeg-basic", "1.2.1", 1.0)),
    ]
    chunks = [
        ("float32-2x3", "float32", [2, 3], [0.0, 1.5, -2.25, 1e-7, 3.4028234663852886e38, -0.0]),
        ("int16-4", "int16", [4], [0, 1, -1, 32767]),
        ("int16-2x2-same-bytes-other-shape", "int16", [2, 2], [0, 1, -1, 32767]),
    ]
    chain = prov_chain()
    ids = {
        "spec": "docs/spec/hashing.md §4-§5",
        "blob": [{"data_hex": b.hex(), "id": nc.blob_id(b)} for b in blobs],
        "pipeline_version": [
            {
                "name": n,
                "spec": s,
                "payload": nc.pipeline_version_payload(s).decode("utf-8"),
                "id": nc.pipeline_version_id(s),
            }
            for n, s in specs
        ],
        "chunk": [
            {
                "name": n,
                "dtype": dt,
                "shape": shape,
                "values": vals,
                "data_hex": nc.chunk_bytes(dt, vals).hex(),
                "preimage_hex": nc.chunk_preimage(dt, shape, nc.chunk_bytes(dt, vals)).hex(),
                "id": nc.chunk_id(dt, shape, nc.chunk_bytes(dt, vals)),
            }
            for n, dt, shape, vals in chunks
        ],
        "prov_batch_chain": [
            {
                "batch": b,
                "payload": nc.prov_batch_payload(b).decode("utf-8"),
                "id": nc.prov_batch_id(b),
            }
            for b in chain
        ],
    }
    return {"canonical-json.json": canonical, "numbers.json": numbers, "ids.json": ids}


def dump(obj: Any) -> str:
    # ASCII-only file with \u escapes: editors that normalise Unicode cannot corrupt the vectors.
    return json.dumps(obj, ensure_ascii=True, indent=2) + "\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, obj in build().items():
        (OUT / name).write_text(dump(obj), encoding="ascii", newline="\n")
        print("wrote", OUT / name)


if __name__ == "__main__":
    main()
