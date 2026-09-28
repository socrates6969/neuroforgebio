"""Training-set manifests (``nf.training-manifest/v1``) and subject hashing.

The registry never trusts a client's list of training subjects: it resolves every subject that
contributed to the training inputs through the provenance lineage (inputs -> source recordings ->
subjects) and hashes each one:

- subject hash = hex SHA-256(``nf.training-subject.v1`` 0x00 tenant-uuid 0x00 subject-uuid), UUIDs
  in lower-case canonical form. Pseudonymous: it links a version to a subject inside the tenant
  without naming the subject (SEC-046).
- manifest digest = hex SHA-256(``nf.training-manifest.v1`` 0x00 NF-CJSON(manifest)).
- ``weights_source`` (AppSec M3; hashing spec v2 §9.7 amendment): ``platform`` when the weights
  are the output of a platform training job (the inputs are then bound to what the weights were
  derived from), ``upload`` when the bytes were uploaded and ``inputs`` are the uploader's own
  declaration. Written by every registration since the amendment; absent in older manifests.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterable, Mapping
from typing import Any

from sqlalchemy.orm import Session

from nf_platform.audit import _canonical as cj
from nf_platform.governance import policy

SCHEMA = "nf.training-manifest/v1"
SUBJECT_TAG = b"nf.training-subject.v1"
MANIFEST_TAG = b"nf.training-manifest.v1"
WEIGHTS_SOURCES = ("platform", "upload")


def subject_hash(tenant_id: str | uuid.UUID, subject_id: str | uuid.UUID) -> str:
    t = str(uuid.UUID(str(tenant_id))).encode()
    s = str(uuid.UUID(str(subject_id))).encode()
    return hashlib.sha256(SUBJECT_TAG + b"\x00" + t + b"\x00" + s).hexdigest()


def training_subjects(
    session: Session, input_node_ids: Iterable[uuid.UUID]
) -> tuple[set[uuid.UUID], set[uuid.UUID]]:
    """(subject ids, source recording ids) behind the inputs, through the lineage."""
    recs = policy.source_recordings(session, list(input_node_ids))
    return policy.subjects_of_recordings(session, recs), recs


def build(
    *,
    tenant_id: str,
    input_node_ids: Iterable[uuid.UUID],
    subject_hashes: Iterable[str],
    n_source_recordings: int,
    shards: Mapping[str, int] | None,
    excluded_subject_hashes: Iterable[str],
    pipeline_version_ids: Iterable[str],
    code_commit: str,
    recipe: str | None,
    parent_version_id: uuid.UUID | None,
    weights_source: str | None = None,
) -> tuple[dict[str, Any], str]:
    doc: dict[str, Any] = {
        "schema": SCHEMA,
        "tenant": str(uuid.UUID(str(tenant_id))),
        # §9.7: de-duplicated and sorted, canonical lowercase UUIDs (BUG-HUNT M5)
        "inputs": sorted({str(uuid.UUID(str(i))) for i in input_node_ids}),
        "subjects": sorted(set(subject_hashes)),
        "n_subjects": len(set(subject_hashes)),
        "n_source_recordings": n_source_recordings,
        "excluded_subjects": sorted(set(excluded_subject_hashes)),
        "pipeline_version_ids": sorted(set(pipeline_version_ids)),
        "code_commit": code_commit,
        "recipe": recipe,
        "parent_version": None if parent_version_id is None else str(parent_version_id),
    }
    if shards:
        doc["shards"] = {k: int(v) for k, v in sorted(shards.items())}
    if weights_source is not None:
        if weights_source not in WEIGHTS_SOURCES:
            raise ValueError(f"weights_source must be one of {WEIGHTS_SOURCES}")
        doc["weights_source"] = weights_source
    return doc, digest(doc)


def digest(doc: Mapping[str, Any]) -> str:
    return hashlib.sha256(MANIFEST_TAG + b"\x00" + cj.canonicalize(dict(doc))).hexdigest()
