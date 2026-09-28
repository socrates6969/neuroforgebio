"""Runs and their provenance handles."""

from __future__ import annotations

import time
from typing import Any

from .client import Client, get_client

__all__ = ["Provenance", "Run", "RunFailed"]

TERMINAL = ("succeeded", "failed", "cancelled")


class RunFailed(Exception):
    def __init__(self, run: Run) -> None:
        super().__init__(f"run {run.id} {run.state}: {run.error}")
        self.run = run


class Run:
    """A run of one PipelineVersion on one recording."""

    def __init__(self, doc: dict[str, Any], *, client: Client | None = None) -> None:
        self._client = client
        self._update(doc)

    def _update(self, doc: dict[str, Any]) -> None:
        self.doc = doc
        self.id: str = doc["id"]
        self.state: str = doc["state"]
        self.error: str | None = doc.get("error")
        self.pipeline_version_id: str = doc["pipeline_version_id"]
        self.recording_id: str = doc["recording_id"]

    def __repr__(self) -> str:
        return f"Run({self.id!r}, state={self.state!r})"

    @property
    def done(self) -> bool:
        return self.state in TERMINAL

    def refresh(self) -> Run:
        self._update(get_client(self._client).get(f"/v1/runs/{self.id}"))
        return self

    def wait(self, timeout: float = 3600.0) -> Run:
        """Poll until the run ends; raise ``RunFailed`` unless it succeeded."""
        c = get_client(self._client)
        deadline = time.monotonic() + timeout
        delay = c.poll_interval
        while not self.done:
            if time.monotonic() > deadline:
                raise TimeoutError(f"run {self.id} still {self.state} after {timeout} s")
            time.sleep(delay)
            delay = min(delay * 1.5, 10.0)
            self.refresh()
        if self.state != "succeeded":
            raise RunFailed(self)
        return self

    @property
    def record(self) -> dict[str, Any]:
        """The run record: every resolved parameter (defaults included), seed, environment."""
        return self.doc.get("record", {})

    @property
    def artifacts(self) -> list[dict[str, Any]]:
        return self.doc.get("artifacts", [])

    @property
    def provenance(self) -> Provenance:
        """The run's provenance handle. Waits for the run to finish: provenance is committed
        together with the outputs (step 3.3), never before."""
        self.wait()
        pid = self.doc.get("prov_activity_id")
        if not pid:
            raise RunFailed(self)
        return Provenance(
            pid, batch_id=self.doc.get("prov_batch_id"), run=self, client=self._client
        )


class Provenance:
    """A provenance node on the platform (a run's activity, a recording, an artifact)."""

    def __init__(
        self,
        node_id: str,
        *,
        batch_id: str | None = None,
        run: Run | None = None,
        client: Client | None = None,
    ) -> None:
        self.id = str(node_id)
        self.batch_id = batch_id
        self.run = run
        self._client = client

    def __repr__(self) -> str:
        return f"Provenance({self.id!r})"

    def __str__(self) -> str:
        return self.id

    def node(self) -> dict[str, Any]:
        return get_client(self._client).get(f"/v1/provenance/{self.id}")

    def lineage(self, direction: str = "up", depth: int | None = None) -> dict[str, Any]:
        """Ancestors (``up``) or descendants (``down``) of this node."""
        return get_client(self._client).get(
            f"/v1/provenance/{self.id}/lineage", direction=direction, depth=depth
        )

    def export(
        self, fmt: str = "prov-json", direction: str = "up", depth: int | None = None
    ) -> dict[str, Any]:
        """Lineage export: W3C ``prov-json`` or ``openlineage`` (the formats the API offers)."""
        return get_client(self._client).get(
            f"/v1/provenance/{self.id}/export", format=fmt, direction=direction, depth=depth
        )
