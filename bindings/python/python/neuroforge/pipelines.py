"""Pinned pipeline versions: ``nf.pipelines.get("eeg-basic@1.0.0").run(rec)``.

A reference is ``name@semver`` or a content ID ``pv:sha256:<hex>``; the platform resolves it to
one immutable PipelineVersion (BLUEPRINT §3.5). ``Pipeline.id`` is recomputed locally by nf-core
from the returned spec and must equal the server's ID, so a pipeline cannot be swapped silently.
"""

from __future__ import annotations

import uuid
from typing import Any
from urllib.parse import quote

from . import canonical
from .client import Client, get_client
from .recordings import LocalFile, RemoteRecording
from .runs import Run

__all__ = ["Pipeline", "get", "publish"]


class IntegrityError(Exception):
    """The server's pipeline ID does not match the ID nf-core computes from its spec."""


class Pipeline:
    def __init__(self, doc: dict[str, Any], *, client: Client | None = None) -> None:
        self._doc = doc
        self._client = client
        self.id: str = doc["id"]
        self.ref: str = doc.get("ref") or f"{doc.get('name')}@{doc.get('version')}"
        self.spec: dict[str, Any] = doc["spec"]
        local = canonical.pipeline_version_id(self.spec)
        if local != self.id:
            raise IntegrityError(f"pipeline {self.ref}: server id {self.id} != local {local}")

    def __repr__(self) -> str:
        return f"Pipeline({self.ref!r}, id={self.id!r})"

    @property
    def steps(self) -> list[dict[str, Any]]:
        return list(self.spec.get("steps", []))

    def run(
        self,
        recording: LocalFile | RemoteRecording | str,
        *,
        session: str | None = None,
        synthetic: bool | None = None,
    ) -> Run:
        """Queue a run on ``recording`` (a local file is uploaded first). Returns at once; the
        run's ``provenance``, ``wait()`` and ``refresh()`` follow it."""
        c = get_client(self._client)
        if isinstance(recording, LocalFile):
            recording = recording.upload(session, synthetic=synthetic, client=c)
        rid = recording.id if isinstance(recording, RemoteRecording) else str(recording)
        out = c.post(
            "/v1/runs",
            {"pipeline": self.id, "recording_id": rid},
            idempotency_key=str(uuid.uuid4()),
        )
        return Run(out, client=c)


def get(ref: str, *, client: Client | None = None) -> Pipeline:
    c = get_client(client)
    return Pipeline(c.get(f"/v1/pipelines/{quote(ref, safe='@:.')}"), client=c)


def publish(spec: dict[str, Any], *, client: Client | None = None) -> Pipeline:
    """Publish a PipelineVersion document (immutable once published)."""
    c = get_client(client)
    return Pipeline(c.post("/v1/pipelines", spec), client=c)
