from fastapi import APIRouter

router = APIRouter()


@router.post("/v1/devices/{id}/stimulate", operation_id="stimulateDevice")
def create_event(id: str) -> dict:
    return {"id": id}
