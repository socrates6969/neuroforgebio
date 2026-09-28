"""Multiverse sweeps: grid expansion, run creation and the comparison report (BUILD-GUIDE 3.6).

A sweep is ``{pipeline: name@semver | pv:sha256:..., recording_ids: [...], grid: {"<step>.<param>":
[values...]}, metric: {step, key}}``. The grid's cartesian product (factor order as given, values in
the order given) gives the variants; each variant runs on every recording, so a sweep creates
``n_variants x n_recordings`` runs on the 3.3 queue, in ONE transaction with the sweep rows and the
sweep's provenance activity.

**Design decision: every variant is a published PipelineVersion, not a run-level override.**
The alternative (one base PipelineVersion + per-run parameter overrides recorded in provenance)
would make a run's ``pipeline_version_id`` describe something that did not run, and anyone
re-running "pv X on recording R" would get a different result. Here each grid point is its own
immutable, content-addressed document (``pv:sha256:`` over steps + params + seed, hashing.md §5.1),
so:

- a run is still fully described by (PipelineVersion ID, input content, image digests, seed), the
  BLUEPRINT §3.5 definition of reproducible; the worker needs no special path;
- the PROV graph links each run to the exact PipelineVersion agent that produced it, and the
  sweep activity to the base and to every variant (``wasAssociatedWith``) and to every input
  recording (``used``);
- identical grid points dedupe to the same ID (re-running a sweep re-uses the published variants;
  a grid value equal to the base value yields the base's ID).

Variant labels are deterministic: ``<base name>.mv-<12 hex>`` at the base's version, where the hex
is SHA-256 over the base ID and the overrides, so the label cannot collide with another variant.

The report reads one number per run: ``info[metric.key]`` of step ``metric.step`` in the run record
(the worker writes each step's ``info`` there), and cites the step's ``signal.json`` artifact
(content hash + provenance node) that carries the same number. Aggregates (variant means, marginal
means per factor level, the factor's range) list the run IDs they are computed from, so every
number in the report links to runs.
"""

from __future__ import annotations

import copy
import itertools
import math
import re
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from nf_platform.audit import _canonical as cj
from nf_platform.db import models as m
from nf_platform.db.context import Principal
from nf_platform.jobs import queue, runs
from nf_platform.pipelines import spec as pipelines
from nf_platform.provenance import api as prov

MAX_FACTORS = 4
MAX_LEVELS = 16
MAX_VARIANTS = 64
MAX_RECORDINGS = 32
MAX_RUNS = 256
VARIANT_TAG = "nf.sweep-variant.v1"
METRIC_FILE = "signal.json"
FACTOR_RE = re.compile(
    r"^(?P<step>[a-z0-9][a-z0-9._-]{0,99})\.(?P<param>[A-Za-z_][A-Za-z0-9_]{0,99})$"
)
_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]{0,99}$")


class SweepError(Exception):
    """The sweep cannot be created (mapped to 404/409/422 by the API)."""

    def __init__(self, status: int, code: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------- request
class MetricSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    step: str = Field(min_length=1, max_length=100, description="pipeline step whose info holds it")
    key: str = Field(default="accuracy", description="key in that step's run-record info")
    higher_is_better: bool = True

    @field_validator("key")
    @classmethod
    def _key(cls, v: str) -> str:
        if not _KEY_RE.match(v):
            raise ValueError("metric key must match ^[A-Za-z_][A-Za-z0-9_.-]{0,99}$")
        return v


class SweepRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=200)
    pipeline: str = Field(
        min_length=1, max_length=300, description="base PipelineVersion: name@semver or pv ID"
    )
    recording_ids: list[uuid.UUID] = Field(min_length=1, max_length=MAX_RECORDINGS)
    grid: dict[str, list[Any]] = Field(
        min_length=1,
        max_length=MAX_FACTORS,
        description='{"<step>.<param>": [value, ...]}; the cartesian product gives the variants',
    )
    metric: MetricSpec

    @field_validator("recording_ids")
    @classmethod
    def _unique(cls, v: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(set(v)) != len(v):
            raise ValueError("recording_ids must be unique")
        return v


@dataclass(frozen=True)
class Factor:
    name: str  # "<step>.<param>"
    step: str
    param: str
    values: tuple[Any, ...]


@dataclass(frozen=True)
class Variant:
    index: int
    params: dict[str, Any]  # factor name -> value
    document: dict[str, Any]


def _canon(v: Any) -> bytes:
    try:
        return cj.canonicalize(v)
    except cj.CanonicalError as e:
        raise SweepError(422, "invalid-grid", f"grid value is not canonical JSON: {e}") from e


def parse_grid(grid: dict[str, list[Any]], base_doc: dict[str, Any]) -> list[Factor]:
    """Validate the grid against the base document: every factor names an existing step and one of
    its (explicit) parameters; values are canonical JSON, 1..MAX_LEVELS, without duplicates."""
    steps = {s["name"]: s for s in base_doc["steps"]}
    out = []
    for name, values in grid.items():
        mt = FACTOR_RE.match(name)
        if not mt:
            raise SweepError(422, "invalid-grid", f"factor {name!r} must be '<step>.<param>'")
        step, param = mt["step"], mt["param"]
        if step not in steps:
            raise SweepError(422, "invalid-grid", f"factor {name!r}: no step {step!r} in pipeline")
        if param not in (steps[step].get("params") or {}):
            raise SweepError(
                422, "invalid-grid", f"factor {name!r}: step {step!r} has no parameter {param!r}"
            )
        if not 1 <= len(values) <= MAX_LEVELS:
            raise SweepError(422, "invalid-grid", f"factor {name!r}: 1..{MAX_LEVELS} values")
        seen = [_canon(v) for v in values]
        if len(set(seen)) != len(seen):
            raise SweepError(422, "invalid-grid", f"factor {name!r}: duplicate values")
        out.append(Factor(name, step, param, tuple(values)))
    return out


def variant_label(base_pv_id: str, params: dict[str, Any]) -> str:
    """12 hex of SHA-256(tag 0x00 canonical({base, params})) -- deterministic per grid point."""
    payload = cj.canonicalize({"base": base_pv_id, "params": params})
    return cj.sha256_hex(cj.tagged_preimage(VARIANT_TAG, payload))[:12]


def variant_document(
    base: pipelines.PipelineVersionRow, factors: list[Factor], params: dict[str, Any]
) -> dict[str, Any]:
    doc = copy.deepcopy(base.document)
    by_name = {s["name"]: s for s in doc["steps"]}
    for f in factors:
        by_name[f.step]["params"][f.param] = copy.deepcopy(params[f.name])
    overrides = ", ".join(f"{k}={cj.canonical_text(v)}" for k, v in params.items())
    doc["meta"] = {
        "name": f"{base.name[:84]}.mv-{variant_label(base.pv_id, params)}",
        "version": base.version,
        "description": f"Multiverse variant of {base.ref} ({base.pv_id}): {overrides}"[:2000],
    }
    return doc


def expand(base: pipelines.PipelineVersionRow, factors: list[Factor]) -> list[Variant]:
    """Cartesian product in factor order (the last factor varies fastest)."""
    out = []
    for i, combo in enumerate(itertools.product(*(f.values for f in factors))):
        params = {f.name: v for f, v in zip(factors, combo, strict=True)}
        out.append(Variant(i, params, variant_document(base, factors, params)))
    return out


# ---------------------------------------------------------------- create
def _prov_ref(session: Session, nodes: list[prov.NodeSpec], kind, type_: str, ref_id: str):
    found = prov.find_node(session, kind, type_, ref_id)
    if found is not None:
        return found
    nodes.append(
        prov.NodeSpec(kind, type_, ref_id, ref_id if type_ == "pipeline_version" else None)
    )
    return len(nodes) - 1


def create_sweep(session: Session, principal: Principal, req: SweepRequest) -> m.Sweep:
    """Publish the variants, queue every run, write the sweep + its provenance (one transaction:
    the caller's tenant session)."""
    try:
        base = pipelines.resolve(session, req.pipeline)
    except pipelines.PipelineNotFound as e:
        raise SweepError(404, "not-found", "pipeline not found") from e
    except pipelines.PipelineError as e:
        raise SweepError(422, "invalid-pipeline-ref", str(e)) from e
    if req.metric.step not in {s["name"] for s in base.document["steps"]}:
        raise SweepError(422, "invalid-metric", f"no step {req.metric.step!r} in the pipeline")
    factors = parse_grid(req.grid, base.document)
    n_variants = math.prod(len(f.values) for f in factors)
    n_runs = n_variants * len(req.recording_ids)
    if n_variants > MAX_VARIANTS or n_runs > MAX_RUNS:
        raise SweepError(
            422,
            "too-large",
            f"{n_variants} variants x {len(req.recording_ids)} recordings = {n_runs} runs; "
            f"limits {MAX_VARIANTS} variants, {MAX_RUNS} runs",
        )
    variants = expand(base, factors)
    published = []
    for v in variants:
        try:
            published.append(pipelines.publish(session, principal, v.document))
        except pipelines.PipelineConflict as e:
            raise SweepError(409, "variant-conflict", str(e)) from e
        except pipelines.PipelineError as e:
            raise SweepError(422, "invalid-variant", f"variant {v.index}: {e}") from e

    sweep = m.Sweep(
        id=uuid.uuid4(),
        tenant_id=uuid.UUID(principal.tenant_id),
        name=req.name or f"sweep of {base.ref}",
        pipeline_ref=base.ref,
        pipeline_version_id=base.pv_id,
        spec={
            "pipeline": {"ref": base.ref, "id": base.pv_id},
            "recording_ids": [str(r) for r in req.recording_ids],
            "grid": [{"factor": f.name, "values": list(f.values)} for f in factors],
            "metric": req.metric.model_dump(),
        },
        metric_step=req.metric.step,
        metric_key=req.metric.key,
        n_variants=n_variants,
        n_runs=n_runs,
        created_by=principal.id,
    )
    session.add(sweep)
    session.flush()
    for v, pv in zip(variants, published, strict=True):
        for rec in req.recording_ids:
            try:
                run = runs.create_run(session, principal, pv.ref, rec)
            except runs.RunError as e:
                raise SweepError(e.status, e.code, f"recording {rec}: {e.detail}") from e
            session.add(
                m.SweepRun(
                    tenant_id=sweep.tenant_id,
                    sweep_id=sweep.id,
                    variant=v.index,
                    recording_id=rec,
                    run_id=run.id,
                    params=v.params,
                    pipeline_ref=pv.ref,
                    pipeline_version_id=pv.pv_id,
                )
            )
    session.flush()

    # provenance: sweep activity -> base + variant PipelineVersions, and the input recordings.
    # New endpoint nodes come first (an edge's dst must precede its src in one batch).
    E, A, G = prov.ProvKind.ENTITY, prov.ProvKind.ACTIVITY, prov.ProvKind.AGENT
    nodes: list[prov.NodeSpec] = []
    targets: list[tuple[prov.EdgeType, prov.NodeRef]] = []
    seen: set[str] = set()
    for pv_id in [base.pv_id, *[p.pv_id for p in published]]:
        if pv_id not in seen:
            seen.add(pv_id)
            ref = _prov_ref(session, nodes, G, "pipeline_version", pv_id)
            targets.append((prov.EdgeType.WAS_ASSOCIATED_WITH, ref))
    for rec in req.recording_ids:
        targets.append((prov.EdgeType.USED, _prov_ref(session, nodes, E, "recording", str(rec))))
    act = len(nodes)
    nodes.append(
        prov.NodeSpec(
            A,
            "sweep",
            str(sweep.id),
            None,
            {
                "base_pipeline_version_id": base.pv_id,
                "grid": sweep.spec["grid"],
                "metric": sweep.spec["metric"],
                "n_variants": n_variants,
                "n_runs": n_runs,
            },
        )
    )
    commit = prov.record(session, principal, nodes, [(act, rel, dst) for rel, dst in targets])
    sweep.prov_node_id = commit.node_ids[act]
    session.flush()
    return sweep


# ---------------------------------------------------------------- read + report
def get_sweep(session: Session, sweep_id: uuid.UUID) -> m.Sweep | None:
    return session.scalar(select(m.Sweep).where(m.Sweep.id == sweep_id))


def _cells(session: Session, sweep: m.Sweep) -> list[tuple[m.SweepRun, m.Run]]:
    q = (
        select(m.SweepRun, m.Run)
        .join(m.Run, (m.Run.id == m.SweepRun.run_id) & (m.Run.tenant_id == m.SweepRun.tenant_id))
        .where(m.SweepRun.sweep_id == sweep.id)
        .order_by(m.SweepRun.variant, m.SweepRun.recording_id)
    )
    return [(sr, r) for sr, r in session.execute(q).all()]


def sweep_state(states: list[str]) -> str:
    if all(s == "queued" for s in states):
        return "queued"
    if any(s not in queue.TERMINAL for s in states):
        return "running"
    if all(s == "succeeded" for s in states):
        return "succeeded"
    return "partial" if "succeeded" in states else "failed"


def _counts(states: list[str]) -> dict[str, int]:
    return {s: states.count(s) for s in sorted(set(states))}


def sweep_summary(session: Session, sweep: m.Sweep) -> dict[str, Any]:
    cells = _cells(session, sweep)
    states = [r.state for _, r in cells]
    variants: dict[int, dict[str, Any]] = {}
    for sr, _ in cells:
        variants.setdefault(
            sr.variant,
            {
                "variant": sr.variant,
                "params": sr.params,
                "pipeline_ref": sr.pipeline_ref,
                "pipeline_version_id": sr.pipeline_version_id,
            },
        )
    return {
        "id": str(sweep.id),
        "name": sweep.name,
        "state": sweep_state(states),
        "run_states": _counts(states),
        "pipeline": sweep.pipeline_ref,
        "pipeline_version_id": sweep.pipeline_version_id,
        "recording_ids": sweep.spec["recording_ids"],
        "grid": {g["factor"]: g["values"] for g in sweep.spec["grid"]},
        "metric": sweep.spec["metric"],
        "variants": [variants[k] for k in sorted(variants)],
        "run_ids": [str(r.id) for _, r in cells],
        "prov_node_id": None if sweep.prov_node_id is None else str(sweep.prov_node_id),
        "created_by": sweep.created_by,
        "created_at": sweep.created_at.isoformat(),
    }


def metric_value(record: dict[str, Any], step: str, key: str) -> float | None:
    """``info[key]`` of step ``step`` in the run record's execution, if it is a finite number."""
    for s in (record.get("execution") or {}).get("steps") or []:
        if s.get("name") == step:
            v = (s.get("info") or {}).get(key)
            if isinstance(v, bool) or not isinstance(v, int | float) or not math.isfinite(v):
                return None
            return float(v)
    return None


def _str(v: Any) -> str | None:
    return None if v is None else str(v)


def _mean(values: list[float]) -> float | None:
    return math.fsum(values) / len(values) if values else None


def report(session: Session, sweep: m.Sweep) -> dict[str, Any]:
    """How the metric varies across the grid. Every number carries the run IDs it comes from."""
    cells_db = _cells(session, sweep)
    run_ids = [r.id for _, r in cells_db]
    arts = {
        a.run_id: a
        for a in session.scalars(
            select(m.RunArtifact).where(
                m.RunArtifact.run_id.in_(run_ids),
                m.RunArtifact.step == sweep.metric_step,
                m.RunArtifact.name == METRIC_FILE,
                m.RunArtifact.visible_at.is_not(None),
            )
        )
    }
    factors = [g["factor"] for g in sweep.spec["grid"]]
    cells = []
    for sr, run in cells_db:
        value = None
        if run.state == "succeeded":
            value = metric_value(run.record, sweep.metric_step, sweep.metric_key)
        art = arts.get(run.id)
        cells.append(
            {
                "run_id": str(run.id),
                "recording_id": str(sr.recording_id),
                "variant": sr.variant,
                "params": sr.params,
                "pipeline_ref": sr.pipeline_ref,
                "pipeline_version_id": sr.pipeline_version_id,
                "state": run.state,
                "value": value,
                "prov_activity_id": _str(run.prov_activity_id),
                "prov_node_id": None if art is None else str(art.prov_node_id),
                "artifact": None
                if art is None
                else {"id": str(art.id), "step": art.step, "name": art.name, "sha256": art.sha256},
            }
        )

    def agg(group: list[dict[str, Any]]) -> dict[str, Any]:
        vals = [c for c in group if c["value"] is not None]
        return {
            "mean": _mean([c["value"] for c in vals]),
            "n": len(vals),
            "run_ids": [c["run_id"] for c in vals],
        }

    by_variant: dict[int, list[dict[str, Any]]] = {}
    for c in cells:
        by_variant.setdefault(c["variant"], []).append(c)
    variants = [
        {
            "variant": k,
            "params": g[0]["params"],
            "pipeline_ref": g[0]["pipeline_ref"],
            "pipeline_version_id": g[0]["pipeline_version_id"],
            **agg(g),
        }
        for k, g in sorted(by_variant.items())
    ]
    sensitivity = []
    for f, grid in zip(factors, sweep.spec["grid"], strict=True):
        levels = []
        for value in grid["values"]:
            key = _canon(value)
            group = [c for c in cells if _canon(c["params"][f]) == key]
            levels.append({"value": value, **agg(group)})
        means = [lv["mean"] for lv in levels if lv["mean"] is not None]
        sensitivity.append(
            {
                "factor": f,
                "levels": levels,
                "range": (max(means) - min(means)) if len(means) >= 2 else None,
            }
        )
    scored = [v for v in variants if v["mean"] is not None]
    best = None
    if scored:
        sign = 1.0 if sweep.spec["metric"].get("higher_is_better", True) else -1.0
        top = max(scored, key=lambda v: (sign * v["mean"], -v["variant"]))
        best = {k: top[k] for k in ("variant", "params", "mean", "run_ids")}
    states = [c["state"] for c in cells]
    metric = sweep.spec["metric"]
    return {
        "sweep_id": str(sweep.id),
        "state": sweep_state(states),
        "complete": all(s in queue.TERMINAL for s in states),
        "pipeline": sweep.pipeline_ref,
        "pipeline_version_id": sweep.pipeline_version_id,
        "metric": {
            "name": f"{metric['step']}.{metric['key']}",
            "step": metric["step"],
            "key": metric["key"],
            "higher_is_better": metric.get("higher_is_better", True),
        },
        "factors": [{"name": g["factor"], "values": g["values"]} for g in sweep.spec["grid"]],
        "cells": cells,
        "variants": variants,
        "sensitivity": sensitivity,
        "best": best,
        "prov_node_id": None if sweep.prov_node_id is None else str(sweep.prov_node_id),
    }
