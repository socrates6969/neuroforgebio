"""PipelineVersion model, canonical ID, publish and resolve (BUILD-GUIDE 3.2; SEC-044).

Document shape = docs/spec/hashing.md §5.1 (frozen test vectors) + JSON Schema
``docs/spec/pipeline-version.schema.json``::

    {"schema": "nf.pipeline-version/v1",
     "meta": {"name": "eeg-basic", "version": "1.2.0", "description": "..."},   # not hashed
     "steps": [{"name": "filter", "step": "nf.filter@1.0.0",                     # step: optional
                "image": "registry/steps@sha256:<64 hex>", "entrypoint": ["nf-step", "filter"],
                "params": {...every parameter, defaults filled...},
                "tolerance": {"kind": "exact"} | {"kind": "abs"|"rel", "value": 1e-9}}],
     "seed": 42}

``step`` is the step-library reference (``name@semver``). When a :class:`StepCatalog` is registered
(the step library, 3.4), publishing fills every missing parameter with the library default and
rejects unknown parameters, so the hashed document always carries explicit values.

Mapping to the M3-CONTRACTS §2 sketch: ``StepSpec.id`` = ``name``; ``tolerance`` is an object
(``kind`` exact/abs/rel + ``value``) because the frozen spec says so; ``tolerance_class``,
``rtol`` and ``atol`` are derived read-only properties.
"""

from __future__ import annotations

import math
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from nf_platform.audit import _canonical as cj
from nf_platform.db import models as m
from nf_platform.db.context import Principal
from nf_platform.provenance import api as prov

SCHEMA = "nf.pipeline-version/v1"
TAG = "nf.pipeline-version.v1"
KIND = "pv"
PV_ID_RE = re.compile(r"^pv:sha256:[0-9a-f]{64}$")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,99}$")
# semver.org 2.0.0 regex (numbered-groups variant, anchored)
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)
# repository[:port]/path@sha256:<64 hex>; no tag (":latest" etc. is rejected, hashing.md §5.1)
_COMP = r"[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*"
IMAGE_RE = re.compile(
    rf"^(?:[a-zA-Z0-9.-]+(?::[0-9]+)?/)?{_COMP}(?:/{_COMP})*@sha256:[0-9a-f]{{64}}$"
)
STEP_REF_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,99}@[0-9A-Za-z.+-]+$")


class PipelineError(ValueError):
    """The spec is invalid (422)."""


class PipelineConflict(PipelineError):
    """``name@version`` is already published with different content (409)."""


class PipelineNotFound(LookupError):
    """No such pipeline version in this tenant (404)."""


def _check_json(v: Any) -> Any:
    try:
        cj.canonicalize(v)
    except cj.CanonicalError as e:
        raise ValueError(str(e)) from e
    return v


class Tolerance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["exact", "abs", "rel"]
    value: float | None = None

    @model_validator(mode="after")
    def _value(self) -> Tolerance:
        if self.kind == "exact":
            if self.value is not None:
                raise ValueError("tolerance 'exact' takes no value")
        elif self.value is None or not math.isfinite(self.value) or self.value <= 0:
            raise ValueError(f"tolerance '{self.kind}' needs a finite value > 0")
        return self

    def to_document(self) -> dict[str, Any]:
        return (
            {"kind": self.kind}
            if self.kind == "exact"
            else {"kind": self.kind, "value": self.value}
        )


class StepSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str = Field(min_length=1, max_length=100)
    step: str | None = Field(default=None, max_length=200)
    image: str = Field(max_length=500)
    entrypoint: list[str] = Field(min_length=1, max_length=32)
    params: dict[str, Any]
    tolerance: Tolerance

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        if not NAME_RE.match(v):
            raise ValueError("step name must match ^[a-z0-9][a-z0-9._-]{0,99}$")
        return v

    @field_validator("step")
    @classmethod
    def _step(cls, v: str | None) -> str | None:
        if v is not None and not STEP_REF_RE.match(v):
            raise ValueError("step must be a library reference name@version")
        return v

    @field_validator("image")
    @classmethod
    def _image(cls, v: str) -> str:
        if not IMAGE_RE.match(v):
            raise ValueError("image must be pinned by digest: name@sha256:<64 hex>, no tag")
        return v

    @field_validator("entrypoint")
    @classmethod
    def _entry(cls, v: list[str]) -> list[str]:
        if any(not s or len(s) > 200 for s in v):
            raise ValueError("entrypoint items must be 1..200 characters")
        return v

    @field_validator("params")
    @classmethod
    def _params(cls, v: dict[str, Any]) -> dict[str, Any]:
        return _check_json(v)

    # -- M3-CONTRACTS §2 names (read-only views)
    @property
    def id(self) -> str:
        return self.name

    @property
    def tolerance_class(self) -> Literal["exact", "tolerance"]:
        return "exact" if self.tolerance.kind == "exact" else "tolerance"

    @property
    def rtol(self) -> float | None:
        return self.tolerance.value if self.tolerance.kind == "rel" else None

    @property
    def atol(self) -> float | None:
        return self.tolerance.value if self.tolerance.kind == "abs" else None

    def to_document(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name}
        if self.step is not None:
            d["step"] = self.step
        d.update(
            image=self.image,
            entrypoint=list(self.entrypoint),
            params=dict(self.params),
            tolerance=self.tolerance.to_document(),
        )
        return d


class Meta(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str
    version: str
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        if not NAME_RE.match(v):
            raise ValueError("pipeline name must match ^[a-z0-9][a-z0-9._-]{0,99}$")
        return v

    @field_validator("version")
    @classmethod
    def _version(cls, v: str) -> str:
        if len(v) > 100 or not SEMVER_RE.match(v):
            raise ValueError("version must be a semantic version (semver.org 2.0.0)")
        return v


class PipelineSpec(BaseModel):
    """A PipelineVersion document. ``name``/``version`` are read from ``meta``."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)
    schema_: Literal["nf.pipeline-version/v1"] = Field(alias="schema")
    meta: Meta
    steps: list[StepSpec] = Field(min_length=1, max_length=200)
    seed: int = Field(ge=0, le=cj.MAX_SAFE_INT)

    @field_validator("steps")
    @classmethod
    def _unique(cls, v: list[StepSpec]) -> list[StepSpec]:
        names = [s.name for s in v]
        if len(set(names)) != len(names):
            raise ValueError("step names must be unique")
        return v

    @property
    def name(self) -> str:
        return self.meta.name

    @property
    def version(self) -> str:
        return self.meta.version

    @property
    def ref(self) -> str:
        return f"{self.meta.name}@{self.meta.version}"

    def to_document(self) -> dict[str, Any]:
        meta: dict[str, Any] = {"name": self.meta.name, "version": self.meta.version}
        if self.meta.description is not None:
            meta["description"] = self.meta.description
        return {
            "schema": SCHEMA,
            "meta": meta,
            "steps": [s.to_document() for s in self.steps],
            "seed": self.seed,
        }


def parse_spec(doc: Mapping[str, Any]) -> PipelineSpec:
    """Validate a document (raises :class:`PipelineError`)."""
    from pydantic import ValidationError  # noqa: PLC0415

    try:
        return PipelineSpec.model_validate(dict(doc))
    except ValidationError as e:
        msgs = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors()
        )
        raise PipelineError(msgs) from e


def id_payload(spec: PipelineSpec | Mapping[str, Any]) -> bytes:
    """Canonical JSON of the document without ``meta`` (hashing.md §5.1)."""
    doc = spec.to_document() if isinstance(spec, PipelineSpec) else dict(spec)
    doc.pop("meta", None)
    return cj.canonicalize(doc)


def pipeline_version_id(spec: PipelineSpec | Mapping[str, Any]) -> str:
    """``pv:sha256:`` + SHA-256(``nf.pipeline-version.v1`` 0x00 payload)."""
    return f"{KIND}:sha256:" + cj.sha256_hex(cj.tagged_preimage(TAG, id_payload(spec)))


# ---------------------------------------------------------------- step catalog (defaults)
class StepCatalog(Protocol):
    def defaults(self, step_ref: str) -> Mapping[str, Any] | None:
        """Every parameter of ``step_ref`` with its default, or ``None`` if the step is unknown."""
        ...


_catalog: StepCatalog | None = None


def register_catalog(catalog: StepCatalog | None) -> None:
    """Register the step library (3.4) used by :func:`publish` to fill defaults."""
    global _catalog
    _catalog = catalog


def fill_defaults(spec: PipelineSpec, catalog: StepCatalog | None) -> PipelineSpec:
    """Return ``spec`` with every library default written explicitly into ``params``.

    Steps with a ``step`` reference must be known to the catalog and may only set parameters it
    declares. Without a catalog the params are taken as given (they must already be explicit).
    """
    if catalog is None:
        return spec
    steps = []
    for s in spec.steps:
        if s.step is None:
            steps.append(s)
            continue
        defaults = catalog.defaults(s.step)
        if defaults is None:
            raise PipelineError(f"step {s.name}: unknown step library reference {s.step}")
        unknown = sorted(set(s.params) - set(defaults))
        if unknown:
            raise PipelineError(f"step {s.name}: unknown parameters {unknown}")
        steps.append(s.model_copy(update={"params": _check_json({**defaults, **s.params})}))
    return spec.model_copy(update={"steps": steps})


# ---------------------------------------------------------------- persistence
@dataclass(frozen=True)
class PipelineVersionRow:
    tenant_id: str
    name: str
    version: str
    pv_id: str
    document: dict[str, Any]
    created_by: str
    created_at: datetime
    created: bool = False  # True when this call inserted it (False: identical re-publish / read)

    @property
    def spec(self) -> PipelineSpec:
        return parse_spec(self.document)

    @property
    def ref(self) -> str:
        return f"{self.name}@{self.version}"


def _row(r: m.PipelineVersion, created: bool = False) -> PipelineVersionRow:
    return PipelineVersionRow(
        tenant_id=str(r.tenant_id),
        name=r.name,
        version=r.version,
        pv_id=r.pv_id,
        document=r.spec,
        created_by=r.created_by,
        created_at=r.created_at,
        created=created,
    )


def publish(
    session: Session,
    principal: Principal,
    spec: PipelineSpec | Mapping[str, Any],
    *,
    catalog: StepCatalog | None = None,
) -> PipelineVersionRow:
    """Publish ``spec`` in the principal's tenant (inside the caller's tenant session).

    Immutable: an identical re-publish of ``name@version`` returns the existing row (idempotent);
    any difference (steps, params, image, seed, or ``meta``) raises :class:`PipelineConflict`.
    The PipelineVersion also becomes a PROV agent node (``type='pipeline_version'``, ``ref_id`` =
    its ID) so runs can be ``wasAssociatedWith`` it.
    """
    if not isinstance(spec, PipelineSpec):
        spec = parse_spec(spec)
    spec = fill_defaults(spec, catalog or _catalog)
    doc = spec.to_document()
    pv_id = pipeline_version_id(doc)
    tid = uuid.UUID(principal.tenant_id)
    existing = session.scalar(
        select(m.PipelineVersion).where(
            m.PipelineVersion.tenant_id == tid,
            m.PipelineVersion.name == spec.name,
            m.PipelineVersion.version == spec.version,
        )
    )
    if existing is not None:
        if existing.pv_id == pv_id and cj.canonicalize(existing.spec) == cj.canonicalize(doc):
            return _row(existing)
        raise PipelineConflict(
            f"{spec.ref} is already published as {existing.pv_id}; publish a new version instead"
        )
    row = m.PipelineVersion(
        tenant_id=tid,
        name=spec.name,
        version=spec.version,
        pv_id=pv_id,
        spec=doc,
        created_by=principal.id,
    )
    session.add(row)
    session.flush()
    if prov.find_node(session, prov.ProvKind.AGENT, "pipeline_version", pv_id) is None:
        prov.record(
            session,
            principal,
            [
                prov.NodeSpec(
                    kind=prov.ProvKind.AGENT,
                    type="pipeline_version",
                    ref_id=pv_id,
                    content_hash=pv_id,
                    attrs={"steps": len(spec.steps)},
                )
            ],
            [],
        )
    session.refresh(row)
    return _row(row, created=True)


def resolve(session: Session, ref: str) -> PipelineVersionRow:
    """``name@semver`` or a ``pv:sha256:...`` ID → the published version (tenant session, RLS)."""
    if PV_ID_RE.match(ref):
        q = (
            select(m.PipelineVersion)
            .where(m.PipelineVersion.pv_id == ref)
            .order_by(m.PipelineVersion.created_at, m.PipelineVersion.name)
            .limit(1)
        )
    else:
        name, sep, version = ref.rpartition("@")
        if not sep or not NAME_RE.match(name) or not SEMVER_RE.match(version):
            raise PipelineError("reference must be name@semver or a pv:sha256:... ID")
        q = select(m.PipelineVersion).where(
            m.PipelineVersion.name == name, m.PipelineVersion.version == version
        )
    row = session.scalar(q)
    if row is None:
        raise PipelineNotFound(ref)
    return _row(row)
