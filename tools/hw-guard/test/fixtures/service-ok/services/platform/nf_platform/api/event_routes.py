from fastapi import APIRouter

router = APIRouter()


# Recorded markers ("Stimulus", "Response") travel as neutral fields: event_label, event_onset_s.
@router.get("/v1/recordings/{id}/events", operation_id="listRecordingEvents")
def list_events(id: str) -> list[dict]:
    return [{"event_label": "Stimulus/S  1", "event_onset_s": 1.5}]
