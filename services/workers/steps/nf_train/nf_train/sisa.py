"""SISA sharded training for the toy decoder (BUILD-GUIDE 6.4).

After Bourtoule et al., "Machine Unlearning" (arXiv:1912.03817): the training subjects are split
into ``S`` disjoint **shards**; one constituent model is trained per shard; each shard is split
into ``R`` **slices** that are added one at a time, with a checkpoint saved after each slice;
predictions aggregate the constituents. Removing a subject then only needs its own shard to be
retrained, and only from the last checkpoint saved *before* the slice that first contains it.

**This is not certified unlearning.** The retrained shard has provably never seen the withdrawn
subject's samples (the retrain starts from a checkpoint trained without them and never loads them
again), but nothing here bounds or certifies what the *other* artefacts (earlier model versions,
exported predictions, logs, backups outside the crypto-shred scope) still reveal. See
``docs/features/sisa.md``.

Our choices (not the paper's):

- the unit is a **subject** (all of a subject's epochs go to one shard and one slice), because a
  consent withdrawal removes a subject, not a sample;
- assignment is by hash: ``shard = H("shard") mod S``, ``slice = H("slice") mod R`` with
  ``H(tag) = SHA-256("nf.sisa-assign/v1|<seed>|<hashed subject id>|<tag>")``, so a subject's place
  never depends on the other subjects (removing one moves nobody else); shards are therefore only
  balanced in expectation;
- stage ``r`` of shard ``k`` trains on the *cumulative* data of slices ``0..r``, warm-started from
  checkpoint ``(k, r-1)``, for a fixed number of iterations (``decoder.fit``). A retrain replays
  exactly these stages without the withdrawn subject, so its result equals training that shard
  from scratch without the subject (bit-identical; tested);
- aggregation: the mean of the constituents' class-1 probabilities (soft vote); empty shards
  have no constituent.

The core only ever sees *hashed* subject IDs. Checkpoints go through a :class:`CheckpointStore`
(in memory here; encrypted derived objects in ``nf_train.platform``); :class:`AuditedStore`
records every checkpoint read and write, which is the acceptance evidence ("retraining after a
withdrawal touches only one shard").
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np

from nf_train import decoder

MANIFEST_SCHEMA = "nf.sisa-manifest/v1"
CHECKPOINT_SCHEMA = "nf.sisa-checkpoint/v1"
ENSEMBLE_SCHEMA = "nf.sisa-ensemble/v1"
ASSIGN_TAG = "nf.sisa-assign/v1"
AGGREGATION = "mean-probability"
MAX_SHARDS = 64
MAX_SLICES = 64

# hashed subject id -> (x (n, p), y (n,))
SubjectData = Mapping[str, tuple[np.ndarray, np.ndarray]]
Loader = Callable[[list[str]], SubjectData]


class SisaError(ValueError):
    pass


@dataclass(frozen=True)
class SisaConfig:
    shards: int = 4
    slices: int = 3
    seed: int = 0
    fit: decoder.FitParams = field(default_factory=decoder.FitParams)

    def __post_init__(self) -> None:
        if not 1 <= self.shards <= MAX_SHARDS or not 1 <= self.slices <= MAX_SLICES:
            raise SisaError(f"shards must be 1..{MAX_SHARDS} and slices 1..{MAX_SLICES}")

    def doc(self) -> dict[str, Any]:
        return {
            "shards": self.shards,
            "slices": self.slices,
            "seed": self.seed,
            "fit": self.fit.doc(),
        }

    @classmethod
    def from_doc(cls, d: Mapping[str, Any]) -> SisaConfig:
        return cls(
            shards=int(d["shards"]),
            slices=int(d["slices"]),
            seed=int(d["seed"]),
            fit=decoder.FitParams(**d["fit"]),
        )


def canonical(doc: Any) -> bytes:
    """Deterministic JSON bytes (sorted keys, no whitespace; floats as shortest round-trip repr)."""
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _h(seed: int, hid: str, tag: str) -> int:
    d = hashlib.sha256(f"{ASSIGN_TAG}|{seed}|{hid}|{tag}".encode()).digest()
    return int.from_bytes(d[:8], "big")


def assign(hid: str, cfg: SisaConfig) -> tuple[int, int]:
    """(shard, slice) of one hashed subject id; independent of every other subject."""
    if not hid:
        raise SisaError("empty subject id")
    return _h(cfg.seed, hid, "shard") % cfg.shards, _h(cfg.seed, hid, "slice") % cfg.slices


# ---------------------------------------------------------------- checkpoint stores
class CheckpointStore(Protocol):
    def put(self, shard: int, slice_: int, data: bytes, subjects: list[str]) -> str:
        """Store one checkpoint; returns its reference."""
        ...

    def get(self, ref: str) -> bytes: ...

    def discard(self, ref: str) -> None:
        """The checkpoint is superseded (it contains a withdrawn subject): destroy it."""
        ...


class MemoryStore:
    """In-memory store keyed by the SHA-256 of the checkpoint bytes (tests, evaluation)."""

    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}
        self.discarded: set[str] = set()

    def put(self, shard: int, slice_: int, data: bytes, subjects: list[str]) -> str:
        ref = f"sha256:{hashlib.sha256(data).hexdigest()}"
        self.blobs[ref] = data
        return ref

    def get(self, ref: str) -> bytes:
        if ref in self.discarded or ref not in self.blobs:
            raise SisaError(f"checkpoint {ref} is not available")
        return self.blobs[ref]

    def discard(self, ref: str) -> None:
        self.discarded.add(ref)


@dataclass
class AuditEntry:
    op: str  # "read" | "write" | "discard" | "load"
    shard: int | None
    slice: int | None
    ref: str | None = None
    subjects: int | None = None

    def doc(self) -> dict[str, Any]:
        return {
            "op": self.op,
            "shard": self.shard,
            "slice": self.slice,
            "ref": self.ref,
            "subjects": self.subjects,
        }


class AuditedStore:
    """Wraps a store and records every checkpoint read / write / discard."""

    def __init__(self, inner: CheckpointStore) -> None:
        self.inner = inner
        self.log: list[AuditEntry] = []
        self._where: dict[str, tuple[int, int]] = {}

    def put(self, shard: int, slice_: int, data: bytes, subjects: list[str]) -> str:
        ref = self.inner.put(shard, slice_, data, subjects)
        self._where[ref] = (shard, slice_)
        self.log.append(AuditEntry("write", shard, slice_, ref))
        return ref

    def get(self, ref: str) -> bytes:
        data = self.inner.get(ref)
        doc = json.loads(data)
        self.log.append(AuditEntry("read", int(doc["shard"]), int(doc["slice"]), ref))
        return data

    def discard(self, ref: str) -> None:
        self.inner.discard(ref)
        sh, sl = self._where.get(ref, (None, None))
        self.log.append(AuditEntry("discard", sh, sl, ref))

    def note(self, where: tuple[int, int] | None, ref: str) -> None:
        if where is not None:
            self._where[ref] = where

    def shards(self, op: str) -> set[int]:
        return {e.shard for e in self.log if e.op == op and e.shard is not None}


# ---------------------------------------------------------------- the model
@dataclass(frozen=True)
class SisaModel:
    members: tuple[decoder.LogReg | None, ...]  # one per shard; None = empty shard

    def proba(self, x: np.ndarray) -> np.ndarray:
        ps = [m.proba(x) for m in self.members if m is not None]
        if not ps:
            raise SisaError("every shard is empty")
        return np.mean(np.stack(ps), axis=0)

    def predict(self, x: np.ndarray) -> np.ndarray:
        return (self.proba(x) >= 0.5).astype(np.int64)

    def doc(self) -> dict[str, Any]:
        return {
            "schema": ENSEMBLE_SCHEMA,
            "aggregation": AGGREGATION,
            "members": [
                {"shard": k, "model": m.doc() if m is not None else None}
                for k, m in enumerate(self.members)
            ],
        }

    def to_bytes(self) -> bytes:
        return canonical(self.doc())

    @classmethod
    def from_doc(cls, d: Mapping[str, Any]) -> SisaModel:
        if d.get("schema") != ENSEMBLE_SCHEMA:
            raise SisaError(f"not a {ENSEMBLE_SCHEMA} document")
        members = sorted(d["members"], key=lambda e: e["shard"])
        return cls(
            tuple(decoder.LogReg.from_doc(e["model"]) if e["model"] else None for e in members)
        )


@dataclass(frozen=True)
class TrainResult:
    model: SisaModel
    manifest: dict[str, Any]
    audit: list[AuditEntry]
    loaded_subjects: list[str]
    retrained_shards: list[int]


def _checkpoint_doc(
    shard: int, slice_: int, model: decoder.LogReg | None, subjects: list[str]
) -> dict[str, Any]:
    return {
        "schema": CHECKPOINT_SCHEMA,
        "shard": shard,
        "slice": slice_,
        "model": model.doc() if model is not None else None,
        "subjects": sorted(subjects),
    }


def _stack(data: SubjectData, hids: list[str]) -> tuple[np.ndarray, np.ndarray]:
    xs = [np.asarray(data[h][0], dtype=np.float64) for h in hids]
    ys = [np.asarray(data[h][1], dtype=np.float64) for h in hids]
    return np.concatenate(xs), np.concatenate(ys)


def _train_shard(
    cfg: SisaConfig,
    shard: int,
    by_slice: dict[int, list[str]],
    data: SubjectData,
    store: CheckpointStore,
    *,
    from_slice: int,
    start: decoder.LogReg | None,
) -> tuple[decoder.LogReg | None, dict[int, str]]:
    """Stages ``from_slice..R-1`` of one shard; returns (final model, {slice: checkpoint ref})."""
    model = start
    refs: dict[int, str] = {}
    cumulative = sorted(h for r in range(from_slice) for h in by_slice.get(r, ()))
    for r in range(from_slice, cfg.slices):
        cumulative = sorted(cumulative + by_slice.get(r, []))
        if cumulative:
            x, y = _stack(data, cumulative)
            model = decoder.fit(x, y, cfg.fit, start=model)
        refs[r] = store.put(
            shard, r, canonical(_checkpoint_doc(shard, r, model, cumulative)), cumulative
        )
    return model, refs


def _layout(cfg: SisaConfig, hids: Iterable[str]) -> dict[int, dict[int, list[str]]]:
    out: dict[int, dict[int, list[str]]] = {k: {} for k in range(cfg.shards)}
    for h in sorted(set(hids)):
        k, r = assign(h, cfg)
        out[k].setdefault(r, []).append(h)
    return out


def _manifest(
    cfg: SisaConfig, layout: dict[int, dict[int, list[str]]], refs: dict[tuple[int, int], str]
) -> dict[str, Any]:
    assignment = {h: [k, r] for k, slices in layout.items() for r, hs in slices.items() for h in hs}
    return {
        "schema": MANIFEST_SCHEMA,
        "config": cfg.doc(),
        "aggregation": AGGREGATION,
        "assignment": dict(sorted(assignment.items())),
        "checkpoints": {f"{k}/{r}": refs[(k, r)] for k, r in sorted(refs)},
        "withdrawn": [],
    }


def train(cfg: SisaConfig, data: SubjectData, store: CheckpointStore) -> TrainResult:
    """Full SISA training: every shard, every slice, one checkpoint per (shard, slice)."""
    if not data:
        raise SisaError("no training subjects")
    layout = _layout(cfg, data.keys())
    audited = store if isinstance(store, AuditedStore) else AuditedStore(store)
    refs: dict[tuple[int, int], str] = {}
    members: list[decoder.LogReg | None] = []
    for k in range(cfg.shards):
        final, shard_refs = _train_shard(cfg, k, layout[k], data, audited, from_slice=0, start=None)
        members.append(final)
        refs.update({(k, r): ref for r, ref in shard_refs.items()})
    return TrainResult(
        model=SisaModel(tuple(members)),
        manifest=_manifest(cfg, layout, refs),
        audit=list(audited.log),
        loaded_subjects=sorted(data.keys()),
        retrained_shards=list(range(cfg.shards)),
    )


def _load_checkpoint(store: CheckpointStore, ref: str) -> decoder.LogReg | None:
    doc = json.loads(store.get(ref))
    if doc.get("schema") != CHECKPOINT_SCHEMA:
        raise SisaError("not a SISA checkpoint")
    return decoder.LogReg.from_doc(doc["model"]) if doc["model"] else None


def retrain_without(
    manifest: Mapping[str, Any],
    withdrawn: Iterable[str],
    load: Loader,
    store: CheckpointStore,
    previous: SisaModel,
) -> TrainResult:
    """Retrain only the shards that contain a withdrawn (hashed) subject, each from the last
    checkpoint before the subject's first slice. ``load`` is asked only for the remaining
    subjects of those shards, in slices at or after that point; other shards keep their model
    from ``previous`` untouched. Superseded checkpoints are discarded (in the platform: their
    data keys are destroyed)."""
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise SisaError(f"not a {MANIFEST_SCHEMA} document")
    cfg = SisaConfig.from_doc(manifest["config"])
    assignment: dict[str, list[int]] = dict(manifest["assignment"])
    gone = sorted(set(withdrawn))
    unknown = [h for h in gone if h not in assignment]
    if unknown:
        raise SisaError(f"{len(unknown)} withdrawn subject(s) are not in the training manifest")
    first: dict[int, int] = {}
    for h in gone:
        k, r = assignment[h]
        first[k] = min(first.get(k, r), r)
    remaining = {h: kr for h, kr in assignment.items() if h not in set(gone)}
    layout: dict[int, dict[int, list[str]]] = {k: {} for k in range(cfg.shards)}
    for h, (k, r) in sorted(remaining.items()):
        layout[k].setdefault(r, []).append(h)
    audited = store if isinstance(store, AuditedStore) else AuditedStore(store)
    refs = {
        (int(k), int(r)): ref
        for key, ref in manifest["checkpoints"].items()
        for k, r in [key.split("/")]
    }
    for (k, r), ref in refs.items():
        audited.note((k, r), ref)
    members = list(previous.members)
    if len(members) != cfg.shards:
        raise SisaError("previous model does not match the manifest's shard count")
    loaded: list[str] = []
    for k in sorted(first):
        r0 = first[k]
        start = _load_checkpoint(audited, refs[(k, r0 - 1)]) if r0 > 0 else None
        # Stages r0..R-1 are replayed; each stage refits on the cumulative slices 0..r, so the
        # remaining subjects of THIS shard are loaded (never another shard's, never the withdrawn).
        need = sorted(h for r in range(cfg.slices) for h in layout[k].get(r, ()))
        data = load(need) if need else {}
        loaded += need
        final, new_refs = _train_shard(cfg, k, layout[k], data, audited, from_slice=r0, start=start)
        members[k] = final
        for r, ref in new_refs.items():
            old = refs.get((k, r))
            refs[(k, r)] = ref
            if old is not None and old != ref:
                audited.discard(old)
    new_manifest = {
        **dict(manifest),
        "assignment": dict(sorted((h, list(kr)) for h, kr in remaining.items())),
        "checkpoints": {f"{k}/{r}": refs[(k, r)] for k, r in sorted(refs)},
        "withdrawn": sorted(set(manifest.get("withdrawn") or []) | set(gone)),
    }
    return TrainResult(
        model=SisaModel(tuple(members)),
        manifest=new_manifest,
        audit=list(audited.log),
        loaded_subjects=sorted(set(loaded)),
        retrained_shards=sorted(first),
    )


def train_monolithic(fit: decoder.FitParams, data: SubjectData) -> decoder.LogReg:
    """The non-sharded baseline ("full retraining"): one model on every subject."""
    hids = sorted(data)
    x, y = _stack(data, hids)
    return decoder.fit(x, y, fit)
