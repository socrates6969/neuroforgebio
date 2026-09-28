"""Helpers for the m6-registry tests (uniquely named so they never collide with another directory's
helpers)."""

from __future__ import annotations

import base64
import json
import struct
import uuid
from typing import Any

from nf_platform.db.context import tenant_session
from nf_platform.provenance import api as prov
from nf_platform.storage.runtime import service_principal
from sqlalchemy import text

COMMIT = "0123456789abcdef0123456789abcdef01234567"


def measurement(metric: str = "accuracy", value: float = 0.5, method: str = "m") -> dict[str, Any]:
    return {"method": method, "metric": metric, "value": value}


def card(inferences=("motor_intent",), privacy: bool = False, **kw: Any) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "summary": "test model",
        "task": "decoding",
        "inferences": list(inferences),
        "modalities": ["EEG"],
        "limitations": "synthetic data only",
        "robustness": {
            "noise": measurement(method="additive gaussian noise, SNR 10 dB"),
            "channel_dropout": measurement(method="drop 1 of 2 channels"),
            "adversarial": measurement(method="FGSM, eps=0.01"),
        },
        **kw,
    }
    if privacy:
        doc["privacy_risk"] = {
            "membership_inference": measurement("auc", 0.51, "shadow-model attack"),
            "held_out_split": "subject-wise 20%",
        }
    return doc


def safetensors(n: int = 2) -> bytes:
    header = json.dumps({"w": {"dtype": "F32", "shape": [n], "data_offsets": [0, 4 * n]}}).encode()
    return struct.pack("<Q", len(header)) + header + b"\x00" * (4 * n)


def weights_upload(data: bytes | None = None, fmt: str = "safetensors") -> dict[str, Any]:
    return {"format": fmt, "data_base64": base64.b64encode(data or safetensors()).decode()}


def version_body(input_node_ids, **kw: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "weights": weights_upload(),
        "training_manifest": {"input_node_ids": [str(i) for i in input_node_ids]},
        "code_commit": COMMIT,
        "intended_use": "research decoding of motor intent",
        "use_restrictions": [],
    }
    body.update(kw)
    return body


def post(client, path: str, body: dict[str, Any], h, status: int = 201) -> dict[str, Any]:
    r = client.post(path, json=body, headers=h)
    assert r.status_code == status, (path, r.status_code, r.text)
    return r.json()


def new_model(client, h, *, name: str | None = None, **card_kw: Any) -> dict[str, Any]:
    return post(
        client,
        "/v1/models",
        {"name": name or f"m-{uuid.uuid4().hex[:8]}", "card": card(**card_kw)},
        h,
    )


def audit_rows(engine, **where) -> list[dict[str, Any]]:
    sql = "SELECT row_to_json(e) FROM audit_event e"
    if where:
        sql += " WHERE " + " AND ".join(f"{k} = :{k}" for k in where)
    with engine.connect() as c:
        return [r[0] for r in c.execute(text(sql + " ORDER BY seq"), where)]


def raw_chain(engine, tenant_id: str, recording_id: str) -> dict[str, uuid.UUID]:
    """raw_file --convert--> recording <-wasDerivedFrom- feature (single subject)."""
    svc = service_principal(tenant_id, "svc:test-fixture")
    with tenant_session(svc, engine=engine) as s:
        c = prov.record(
            s,
            svc,
            [
                prov.NodeSpec(prov.ProvKind.ENTITY, "raw_file", f"raw-{recording_id}"),
                prov.NodeSpec(prov.ProvKind.ACTIVITY, "convert"),
                prov.NodeSpec(prov.ProvKind.ENTITY, "recording", recording_id),
                prov.NodeSpec(prov.ProvKind.ENTITY, "feature", None, None, {"fixture": True}),
            ],
            [
                (1, prov.EdgeType.USED, 0),
                (2, prov.EdgeType.WAS_GENERATED_BY, 1),
                (3, prov.EdgeType.WAS_DERIVED_FROM, 2),
            ],
        )
    raw, _, rec, feat = c.node_ids
    return {"raw": raw, "recording": rec, "feature": feat}


def feature_of(engine, tenant_id: str, node_id) -> uuid.UUID:
    """A feature entity wasDerivedFrom ``node_id`` (e.g. the tree's recording node)."""
    svc = service_principal(tenant_id, "svc:test-fixture")
    with tenant_session(svc, engine=engine) as s:
        c = prov.record(
            s,
            svc,
            [prov.NodeSpec(prov.ProvKind.ENTITY, "feature", None, None, {"fixture": True})],
            [(0, prov.EdgeType.WAS_DERIVED_FROM, uuid.UUID(str(node_id)))],
        )
    return c.node_ids[0]
