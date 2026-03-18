from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from fleetshare_common.app import create_app
from fleetshare_common.http import get_json, patch_json
from fleetshare_common.messaging import publish_event
from fleetshare_common.settings import get_settings
from fleetshare_common.vehicle_grpc import lock_vehicle

app = create_app("End Trip Service", "Composite trip end workflow.")


class EndTripPayload(BaseModel):
    tripId: int
    bookingId: int
    vehicleId: int
    userId: str
    endReason: str = "USER_COMPLETED"


def process_end_trip(payload: EndTripPayload):
    settings = get_settings()
    trip = get_json(f"{settings.trip_service_url}/trips/{payload.tripId}")
    if trip["status"] == "ENDED":
        return {"tripStatus": "ENDED", "vehicleLocked": True, "idempotent": True}

    lock = lock_vehicle(payload.vehicleId, str(payload.bookingId), payload.userId)
    trip_result = patch_json(
        f"{settings.trip_service_url}/trips/{payload.tripId}/status",
        {
            "status": "ENDED",
            "endedAt": datetime.utcnow().isoformat(),
            "endReason": payload.endReason,
            "disruptionReason": payload.endReason if "FAULT" in payload.endReason else None,
        },
    )
    updated_trip = get_json(f"{settings.trip_service_url}/trips/{payload.tripId}")
    disrupted = "FAULT" in payload.endReason or "DISRUPTION" in payload.endReason
    adjustment = get_json(
        f"{settings.pricing_service_url}/pricing/trip-adjustment",
        {
            "tripId": payload.tripId,
            "durationHours": updated_trip["durationHours"],
            "disrupted": str(disrupted).lower(),
        },
    )
    if adjustment["compensationRequired"]:
        publish_event(
            "payment.adjustment_required",
            {
                "bookingId": payload.bookingId,
                "tripId": payload.tripId,
                "userId": payload.userId,
                "refundAmount": adjustment["refundAmount"],
                "discountAmount": adjustment["discountAmount"],
                "reason": payload.endReason,
            },
        )
        publish_event(
            "booking.disruption_notification",
            {
                "bookingId": payload.bookingId,
                "tripId": payload.tripId,
                "userIds": [payload.userId, "ops"],
                "subject": "Trip ended with adjustment",
                "message": f"Trip {payload.tripId} ended early and compensation has been queued.",
            },
        )
    return {
        "tripStatus": trip_result["status"],
        "vehicleLocked": lock["success"],
        "adjustedFare": adjustment["adjustedFare"],
        "refundPending": adjustment["refundAmount"] > 0,
        "discountAmount": adjustment["discountAmount"],
    }


@app.post("/end-trip/request")
def end_trip_request(payload: EndTripPayload):
    return process_end_trip(payload)


@app.post("/end-trip/process")
def end_trip_process(payload: EndTripPayload):
    return process_end_trip(payload)

