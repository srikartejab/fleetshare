from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from pydantic import BaseModel

from fleetshare_common.app import create_app
from fleetshare_common.http import patch_json, post_json
from fleetshare_common.settings import get_settings
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
            "startedAt": datetime.utcnow().isoformat(),
            "subscriptionSnapshot": {"renewalStatus": "PENDING", "billingCycleId": "2026-03"},
        },
    )
    patch_json(
        f"{settings.booking_service_url}/booking/{payload.bookingId}/status",
        {"status": "CONFIRMED", "tripId": trip["tripId"]},
    )
    return {"tripId": trip["tripId"], "status": "STARTED", "unlockCommandSent": True}

