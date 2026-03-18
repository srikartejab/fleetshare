from __future__ import annotations

from fastapi import HTTPException
from pydantic import BaseModel

from fleetshare_common.app import create_app
from fleetshare_common.http import get_json, patch_json, post_json
from fleetshare_common.settings import get_settings
from fleetshare_common.timeutils import iso, utcnow
from fleetshare_common.vehicle_grpc import unlock_vehicle

app = create_app("Start Trip Service", "Composite trip start workflow.")


class StartTripPayload(BaseModel):
    bookingId: int
    vehicleId: int
    userId: str
    notes: str = ""


@app.post("/trips/start")
def start_trip(payload: StartTripPayload):
    settings = get_settings()
    records = get_json(
        f"{settings.record_service_url}/records",
        {"bookingId": payload.bookingId, "recordType": "EXTERNAL_DAMAGE"},
    )
    latest_inspection = records[0] if isinstance(records, list) and records else None
    if not latest_inspection:
        raise HTTPException(status_code=409, detail="Complete the pre-trip inspection before starting the trip.")
    if latest_inspection["reviewState"] in {"PENDING_EXTERNAL", "MANUAL_REVIEW", "EXTERNAL_BLOCKED"}:
        raise HTTPException(status_code=409, detail="Pre-trip inspection has not been cleared yet.")
    if latest_inspection["severity"] == "SEVERE":
        raise HTTPException(status_code=409, detail="Vehicle inspection found severe damage. Trip start is blocked.")

    validation = post_json(
        f"{settings.internal_damage_service_url}/internal-damage/validate",
        {
            "bookingId": payload.bookingId,
            "vehicleId": payload.vehicleId,
            "userId": payload.userId,
            "notes": payload.notes,
        },
    )
    if validation["blocked"]:
        raise HTTPException(status_code=409, detail=validation["recommendedAction"])

    unlock = unlock_vehicle(payload.vehicleId, str(payload.bookingId), payload.userId)
    if not unlock["success"]:
        raise HTTPException(status_code=409, detail=unlock["message"])

    trip = post_json(
        f"{settings.trip_service_url}/trips/start",
        {
            "bookingId": payload.bookingId,
            "vehicleId": payload.vehicleId,
            "userId": payload.userId,
            "startedAt": iso(utcnow()),
            "subscriptionSnapshot": {"renewalStatus": "PENDING", "billingCycleId": "2026-03"},
        },
    )
    patch_json(
        f"{settings.booking_service_url}/booking/{payload.bookingId}/status",
        {"status": "CONFIRMED", "tripId": trip["tripId"]},
    )
    return {"tripId": trip["tripId"], "status": "STARTED", "unlockCommandSent": True}
