"""Use-restriction vocabulary and the deployment rules (BUILD-GUIDE 6.2; BLUEPRINT §3.7;
``market/regulation.md`` §5; SEC-092, SEC-144).

Facts used (``market/regulation.md`` §5, EU AI Act Art. 5 prohibitions, applicable from
2 Feb 2025):

- 5(1)(f) bans AI "to infer emotions of a natural person in the areas of workplace and education
  institutions, except ... for medical or safety reasons". A "cognitive state" or emotion model in
  EU workplace or education settings is refused unless a documented medical or safety exception
  record exists.
- 5(1)(g) bans biometric categorisation that infers sensitive traits (no exception is recorded in
  our source, so none is offered).
- 5(1)(a) bans subliminal or manipulative techniques: a context that declares behaviour influence
  is refused in the EU for a model carrying ``eu_ai_act_5_1_a``.

These are machine checks of the registry, not legal advice; nothing here is counsel-reviewed.

SEC-092 (non-negotiable, §G): the platform never controls stimulation or any actuator. The control
settings below are always refused and audited, whatever the model, restriction or exception.
Every version carries ``no_realtime_control`` and its ``intended_use`` states that it is not
intended for real-time or safety-critical control.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

CONTROL_STATEMENT = "Not intended for real-time or safety-critical control."

RESTRICTIONS: dict[str, str] = {
    "eu_ai_act_5_1_f": (
        "EU AI Act Art. 5(1)(f): no emotion or cognitive-state inference in workplace or "
        "education settings in the EU, except for medical or safety reasons (a documented "
        "exception record is required)"
    ),
    "eu_ai_act_5_1_g": (
        "EU AI Act Art. 5(1)(g): no biometric categorisation that infers sensitive traits in the EU"
    ),
    "eu_ai_act_5_1_a": (
        "EU AI Act Art. 5(1)(a): no subliminal or manipulative techniques in the EU (a context "
        "that declares behaviour influence is refused)"
    ),
    "no_realtime_control": (
        "SEC-092: not intended for real-time or safety-critical control; stimulation, "
        "neuromodulation and actuator-control contexts are always refused"
    ),
    "research_only": "deployments only in research or clinical_research settings",
    "no_clinical_care": "no deployment in clinical_care settings",
}
ALWAYS = ("no_realtime_control",)

# Deployment settings. The control settings are part of the vocabulary so that a request naming
# them is recognised, refused and audited (SEC-092); they never appear as an OpenAPI enum.
CONTROL_SETTINGS = frozenset(
    {"closed_loop_stimulation", "neuromodulation_control", "actuator_control"}
)
SETTINGS = (
    frozenset(
        {
            "research",
            "clinical_research",
            "clinical_care",
            "workplace",
            "education",
            "consumer_wellness",
            "safety_monitoring",
            "other",
        }
    )
    | CONTROL_SETTINGS
)
ART_5_1_F_SETTINGS = frozenset({"workplace", "education"})
EMOTION_INFERENCES = frozenset({"emotion", "cognitive_state"})
SENSITIVE_INFERENCES = frozenset({"sensitive_trait"})
RESEARCH_SETTINGS = frozenset({"research", "clinical_research"})

# SEC-144: inference outputs are labels or coarse scores by default; full logits or embeddings
# are refused (no inference API is offered in M6; the deployment records what one may return).
OUTPUTS = ("labels", "coarse_scores", "logits", "embeddings")
ALLOWED_OUTPUTS = frozenset({"labels", "coarse_scores"})
RATE_LIMIT_MAX = 600

# EU member states (ISO 3166-1 alpha-2; Greece is "GR") and the Union as a whole.
EU_CODES = frozenset(
    [
        "AT",
        "BE",
        "BG",
        "HR",
        "CY",
        "CZ",
        "DK",
        "EE",
        "FI",
        "FR",
        "DE",
        "GR",
        "HU",
        "IE",
        "IT",
        "LV",
        "LT",
        "LU",
        "MT",
        "NL",
        "PL",
        "PT",
        "RO",
        "SK",
        "SI",
        "ES",
        "SE",
    ]
) | {"EU"}
JURISDICTION_RE = re.compile(r"^[A-Z]{2}(-[A-Z0-9]{1,3})?$")

# Refusal reason codes (stable; the console and the audit events use them).
R_CONTROL = "sec_092_control_context"
R_5_1_F = "eu_ai_act_5_1_f"
R_5_1_G = "eu_ai_act_5_1_g"
R_5_1_A = "eu_ai_act_5_1_a"
R_RESEARCH_ONLY = "research_only"
R_NO_CLINICAL = "no_clinical_care"
R_OUTPUTS = "sec_144_outputs"
R_RETRAIN = "retrain_required"
R_EXCEPTION = "exception_not_applicable"
# AppSec M3: an upload-sourced version needs an approver other than the uploader (four-eyes)
R_UPLOAD_APPROVAL = "upload_approval_required"


def in_eu(jurisdiction: str) -> bool:
    return jurisdiction.split("-", 1)[0] in EU_CODES


def derived_restrictions(inferences: Iterable[str]) -> set[str]:
    """Restrictions a card's declared inferences impose (a floor; tenants may add more)."""
    inf = set(inferences)
    out = set(ALWAYS)
    if inf & EMOTION_INFERENCES:
        out.add("eu_ai_act_5_1_f")
    if inf & SENSITIVE_INFERENCES:
        out.add("eu_ai_act_5_1_g")
    return out


def unknown_restrictions(values: Iterable[str]) -> list[str]:
    return sorted(set(values) - set(RESTRICTIONS))


@dataclass(frozen=True)
class ExceptionView:
    """The parts of a ``model_use_exception`` row the rules need."""

    model_id: str
    basis: str
    jurisdiction: str
    setting: str
    evidence_ref: str


def exception_covers(exc: ExceptionView, model_id: str, jurisdiction: str, setting: str) -> bool:
    if exc.model_id != model_id or exc.basis not in ("medical", "safety"):
        return False
    if not exc.evidence_ref.strip() or exc.setting != setting:
        return False
    if exc.jurisdiction == jurisdiction:
        return True
    return exc.jurisdiction == "EU" and in_eu(jurisdiction)


def evaluate(
    restrictions: Iterable[str],
    *,
    model_id: str,
    jurisdiction: str,
    setting: str,
    outputs: str,
    influences_behaviour: bool,
    exception: ExceptionView | None,
) -> list[str]:
    """Refusal reasons for a deployment context (empty = allowed by the restrictions)."""
    r = set(restrictions) | set(ALWAYS)
    reasons: list[str] = []
    if setting in CONTROL_SETTINGS:
        reasons.append(R_CONTROL)  # SEC-092: always, no exception can lift it
    eu = in_eu(jurisdiction)
    if "eu_ai_act_5_1_f" in r and eu and setting in ART_5_1_F_SETTINGS:
        if exception is None:
            reasons.append(R_5_1_F)
        elif not exception_covers(exception, model_id, jurisdiction, setting):
            reasons += [R_5_1_F, R_EXCEPTION]
    if "eu_ai_act_5_1_g" in r and eu:
        reasons.append(R_5_1_G)
    if "eu_ai_act_5_1_a" in r and eu and influences_behaviour:
        reasons.append(R_5_1_A)
    if "research_only" in r and setting not in RESEARCH_SETTINGS:
        reasons.append(R_RESEARCH_ONLY)
    if "no_clinical_care" in r and setting == "clinical_care":
        reasons.append(R_NO_CLINICAL)
    if outputs not in ALLOWED_OUTPUTS:
        reasons.append(R_OUTPUTS)
    return reasons


def with_control_statement(intended_use: str) -> str:
    text = intended_use.strip()
    if CONTROL_STATEMENT.lower() in text.lower():
        return text
    return f"{text} {CONTROL_STATEMENT}".strip()
