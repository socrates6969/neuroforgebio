"""Consent-policy hook for new recordings (2.6; BLUEPRINT §3.3 step 4, §8.3).

Until the consent ledger and policy engine exist (M5, steps 5.3/5.4) the default policy answers
``"quarantine"`` for every new recording: nothing is processed or exported before a data steward
(or M5's engine) releases it. A quarantined recording is readable only by ``QUARANTINE_READERS``
(``auth.authorize``) and is hidden from everyone else's lists.
"""

from __future__ import annotations

from typing import Literal, Protocol

Decision = Literal["allow", "quarantine"]
RECORDING_STATE: dict[str, str] = {"allow": "active", "quarantine": "quarantined"}


class Quarantined(Exception):
    """Processing or export was attempted on a quarantined recording."""


class ConsentPolicy(Protocol):
    def decide(self, tenant_id: str, subject_id: str, recording_id: str) -> Decision: ...


class StubConsentPolicy:
    """M2 stub: every new recording is quarantined until M5's policy engine allows it."""

    def decide(self, tenant_id: str, subject_id: str, recording_id: str) -> Decision:
        return "quarantine"


class AllowAllPolicy:
    """For tests and synthetic-only demos where no consent rule applies."""

    def decide(self, tenant_id: str, subject_id: str, recording_id: str) -> Decision:
        return "allow"


def initial_state(policy: ConsentPolicy, tenant_id: str, subject_id: str, recording_id: str) -> str:
    decision = policy.decide(str(tenant_id), str(subject_id), str(recording_id))
    if decision not in RECORDING_STATE:
        return "quarantined"  # fail closed on an unknown answer
    return RECORDING_STATE[decision]


def assert_processable(state: str) -> None:
    """Gate for every processing/export path (pipelines M3, exports M4/M5): quarantine blocks."""
    if state != "active":
        raise Quarantined("recording is quarantined; processing and export are blocked")
