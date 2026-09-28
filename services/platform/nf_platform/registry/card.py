"""The model card (``nf.model-card/v1``; JSON Schema: ``docs/spec/model-card.schema.json``,
generated from :class:`ModelCard` and kept in sync by a test).

- SEC-145: ``robustness`` is required: measured results on perturbed inputs (additive noise,
  channel dropout and a documented adversarial method). The card records measurements; it is not
  a robustness claim.
- SEC-143: ``privacy_risk`` (a membership-inference test on a held-out split, method recorded) is
  optional for tenant-private models and required before publication.
- ``inferences`` drives the EU AI Act restrictions (``registry.vocab``): ``emotion`` or
  ``cognitive_state`` adds ``eu_ai_act_5_1_f``; ``sensitive_trait`` adds ``eu_ai_act_5_1_g``.
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CARD_SCHEMA = "nf.model-card/v1"
SCHEMA_ID = "https://neuroforge.invalid/spec/model-card.schema.json"
ROBUSTNESS_NOTE = "Measured on perturbed inputs; not a robustness claim."

Task = Literal["decoding", "classification", "regression", "detection", "representation", "other"]
Inference = Literal[
    "emotion",
    "cognitive_state",
    "motor_intent",
    "sleep_stage",
    "seizure_risk",
    "artifact_detection",
    "sensitive_trait",
    "other",
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Measurement(_Strict):
    method: str = Field(min_length=1, max_length=500, description="how it was measured")
    metric: str = Field(min_length=1, max_length=100)
    value: float = Field(allow_inf_nan=False)
    split: str | None = Field(default=None, max_length=100, description="evaluation split")
    notes: str | None = Field(default=None, max_length=2000)


class Robustness(_Strict):
    """SEC-145: evaluation on perturbed inputs (recorded, not claimed)."""

    noise: Measurement
    channel_dropout: Measurement
    adversarial: Measurement = Field(description="a documented adversarial method (``method``)")


class PrivacyRisk(_Strict):
    """SEC-143: membership inference on a held-out split; required for publication."""

    membership_inference: Measurement
    held_out_split: str = Field(min_length=1, max_length=100)


class ModelCard(_Strict):
    card_schema: Literal["nf.model-card/v1"] = CARD_SCHEMA
    summary: str = Field(min_length=1, max_length=4000)
    task: Task
    inferences: list[Inference] = Field(min_length=1, max_length=16)
    modalities: list[str] = Field(min_length=1, max_length=16)
    limitations: str = Field(min_length=1, max_length=4000)
    evaluation: list[Measurement] = Field(default_factory=list, max_length=64)
    robustness: Robustness
    privacy_risk: PrivacyRisk | None = None
    contact: str | None = Field(default=None, max_length=200)


def json_schema() -> dict:
    """The committed JSON Schema document (draft 2020-12)."""
    doc = ModelCard.model_json_schema()
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_ID,
        **doc,
    }


def json_schema_text() -> str:
    return json.dumps(json_schema(), indent=2, sort_keys=True) + "\n"
