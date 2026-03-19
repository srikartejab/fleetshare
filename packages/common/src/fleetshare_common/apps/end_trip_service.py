from __future__ import annotations

from fastapi import HTTPException
from pydantic import BaseModel

from fleetshare_common.app import create_app
from fleetshare_common.http import get_json, patch_json, post_json
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
    booking = get_json(f"{settings.booking_service_url}/booking/{payload.bookingId}")
    trip = get_json(f"{settings.trip_service_url}/trips/{payload.tripId}")
    if trip["status"] == "ENDED":
        lock_success = True
        trip_result = {"status": "ENDED", "idempotent": True}
        updated_trip = trip
    else:
        lock = lock_vehicle(payload.vehicleId, str(payload.bookingId), payload.userId)
        lock_success = lock["success"]
        if not lock_success:
            raise HTTPException(status_code=409, detail=lock["message"])
        effective_end = booking["endTime"]
        trip_result = patch_json(
            f"{settings.trip_service_url}/trips/{payload.tripId}/status",
            {
                "status": "ENDED",
                "endedAt": effective_end,
                "endReason": payload.endReason,
                "disruptionReason": payload.endReason if "FAULT" in payload.endReason else None,
            },
        )
        updated_trip = get_json(f"{settings.trip_service_url}/trips/{payload.tripId}")
    disrupted = "FAULT" in payload.endReason or "DISRUPTION" in payload.endReason
    pricing_result = post_json(
        f"{settings.pricing_service_url}/pricing/finalize-trip",
        {
            "bookingId": payload.bookingId,
            "tripId": payload.tripId,
            "userId": payload.userId,
            "startedAt": updated_trip["startedAt"],
            "endedAt": updated_trip["endedAt"],
            "disrupted": disrupted,
        },
    )
    patch_json(
        f"{settings.booking_service_url}/booking/{payload.bookingId}/financials",
        {"finalPrice": pricing_result["finalPrice"]},
    )
    patch_json(
        f"{settings.booking_service_url}/booking/{payload.bookingId}/status",
        {"status": "COMPLETED"},
    )
    if pricing_result["refundAmount"] > 0 or pricing_result["discountAmount"] > 0:
        publish_event(
            "payment.adjustment_required",
            {
                "bookingId": payload.bookingId,
                "tripId": payload.tripId,
                "userId": payload.userId,
                "refundAmount": pricing_result["refundAmount"],
                "discountAmount": pricing_result["discountAmount"],
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
        "vehicleLocked": lock_success,
        "adjustedFare": pricing_result["finalPrice"],
        "refundPending": pricing_result["renewalPending"] or pricing_result["refundAmount"] > 0,
        "discountAmount": pricing_result["discountAmount"],
        "allowanceHoursApplied": pricing_result["allowanceHoursApplied"],
        "customerSummary": pricing_result["customerSummary"],
    }


@app.post("/end-trip/request")
def end_trip_request(payload: EndTripPayload):
    return process_end_trip(payload)


@app.post("/end-trip/process")
def end_trip_process(payload: EndTripPayload):
    return process_end_trip(payload)
