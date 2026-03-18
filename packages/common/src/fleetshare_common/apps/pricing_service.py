from __future__ import annotations

from datetime import datetime

from fastapi import Query
from pydantic import BaseModel

from fleetshare_common.app import create_app
from fleetshare_common.pricing import booking_quote, rerate_after_renewal, trip_adjustment

app = create_app("Pricing Service", "Atomic pricing and re-rating service.")


class ReRatePayload(BaseModel):
    bookingId: int
    tripId: int
    userId: str
    newBillingCycleId: str
    actualPostMidnightHours: float


@app.get("/pricing/quote")
def get_quote(
    vehicleId: int,
    startTime: datetime = Query(...),
    endTime: datetime = Query(...),
    subscriptionPlanId: str = "STANDARD_MONTHLY",
):
    quote = booking_quote(startTime, endTime)
    return {
        "vehicleId": vehicleId,
        "subscriptionPlanId": subscriptionPlanId,
        "estimatedPrice": quote.estimated_price,
        "allowanceStatus": quote.allowance_status,
        "crossCycleBooking": quote.cross_cycle_booking,
        "provisionalPostMidnightHours": quote.provisional_post_midnight_hours,
    }


@app.get("/pricing/trip-adjustment")
def get_trip_adjustment(tripId: int, durationHours: float = 0.0, disrupted: bool = False):
    return {"tripId": tripId, **trip_adjustment(disrupted, durationHours)}


@app.post("/pricing/re-rate-renewed-booking")
def rerate(payload: ReRatePayload):
    return {"bookingId": payload.bookingId, "tripId": payload.tripId, **rerate_after_renewal(payload.actualPostMidnightHours)}
