"""Typed response shapes for routes that build their JSON by hand (M4 4.1; M3 open issue 5).

These models exist so the OpenAPI document (``openapi/v1.yaml``) types every response. The routes
keep producing the same JSON as in M2/M3; the models only describe (and, where the route returns a
plain dict, validate) it. Timestamps that the provenance routes format with ``isoformat()`` stay
strings with ``format: date-time`` so the wire format does not change.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, RootModel

DATE_TIME = {"format": "date-time"}


class WhoAmIOut(BaseModel):
    id: str
    tenant_id: str
    kind: str = Field(description="user | api_key | device | service")
    roles: list[str] = Field(
        description="Effective roles: admin-class roles count only after a phishing-resistant "
        "login."
    )
    scopes: list[str]
    mfa_phishing_resistant: bool
    auth_method: str


# ---------------------------------------------------------------- provenance (3.1, 3.7)
ProvKind = Literal["entity", "activity", "agent"]
ProvRel = Literal[
    "used",
    "wasGeneratedBy",
    "wasDerivedFrom",
    "wasAttributedTo",
    "wasAssociatedWith",
    "wasInformedBy",
]


class ProvNodeOut(BaseModel):
    id: uuid.UUID
    kind: ProvKind
    type: str = Field(description="raw_file, convert, recording, run, artifact, ...")
    ref_id: str | None
    content_hash: str | None
    node_hash: str
    attrs: dict[str, Any]
    batch_seq: int | None
    created_at: str = Field(json_schema_extra=DATE_TIME)
    depth: int | None = Field(default=None, description="Hops from the root (lineage only).")


class ProvEdgeOut(BaseModel):
    src: uuid.UUID
    rel: ProvRel
    dst: uuid.UUID


class ProvNodeDetailOut(BaseModel):
    node: ProvNodeOut
    edges_out: list[ProvEdgeOut]
    edges_in: list[ProvEdgeOut]


class LineageOut(BaseModel):
    root: uuid.UUID
    direction: Literal["up", "down"]
    depth: int | None
    truncated: bool = Field(description="True when the graph hit the node cap.")
    nodes: list[ProvNodeOut]
    edges: list[ProvEdgeOut]


class ProvExportOut(RootModel[dict[str, Any] | list[dict[str, Any]]]):
    """A PROV-JSON object (format=prov-json) or a list of OpenLineage RunEvents (openlineage)."""


# ---------------------------------------------------------------- pipelines (3.2)
class PipelineVersionOut(BaseModel):
    id: str = Field(description="pv:sha256:<64 hex>, the content address")
    name: str
    version: str
    ref: str = Field(description="name@version")
    spec: dict[str, Any] = Field(description="The published PipelineVersion document.")
    created_by: str
    created_at: str = Field(json_schema_extra=DATE_TIME)


# ---------------------------------------------------------------- window reads (2.4)
class WindowJsonOut(BaseModel):
    """``nf-window/1`` JSON form: header + ``data[channel][sample]`` in stored units
    (physical = value * scale + offset)."""

    byte_order: str
    channels: list[str]
    chunk_id: str
    decimation: int
    dtype: str
    kind: Literal["samples", "mean", "min", "max"]
    level: int
    offset: list[float]
    order: str
    physical: str
    scale: list[float]
    sfreq: float
    shape: list[int] = Field(min_length=2, max_length=2)
    start_index: int
    start_s: float
    units: list[str]
    data: list[list[float]]
