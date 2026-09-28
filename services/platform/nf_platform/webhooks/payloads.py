"""Outbound webhook payload schemas (the webhook half of the public surface).

Every event is one JSON object: an envelope (``id``, ``type``, ``created_at``, ``tenant_id``,
``api_version``) plus ``data``. The OpenAPI document publishes these under ``webhooks``
(OpenAPI 3.1). SEC-090: events only *report* what happened on the platform; nothing here addresses
or configures a device. hw-guard's surface scan covers this module's schemas.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

API_VERSION = "v1"


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RunFinishedData(_Frozen):
    run_id: uuid.UUID
    pipeline_ref: str
    pipeline_version_id: str
    recording_id: uuid.UUID
    state: Literal["succeeded", "failed", "cancelled"]
    finished_at: datetime | None
    prov_activity_id: uuid.UUID | None = Field(
        default=None, description="PROV activity node of the run (succeeded runs)."
    )


class RunFinishedEvent(_Frozen):
    """Sent when a pipeline run reaches a terminal state."""

    id: uuid.UUID = Field(description="Event ID; the same on every retry (deduplicate on it).")
    type: Literal["run.finished"]
    api_version: Literal["v1"] = API_VERSION
    created_at: datetime
    tenant_id: uuid.UUID
    data: RunFinishedData


# event type -> (OpenAPI webhook name, model)
EVENTS: dict[str, tuple[str, type[BaseModel]]] = {
    "run.finished": ("runFinished", RunFinishedEvent),
}
