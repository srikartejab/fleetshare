from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from pydantic import BaseModel

from fleetshare_common.app import create_app
from fleetshare_common.http import get_json, patch_json, post_json
from fleetshare_common.settings import get_settings
from fleetshare_common.vehicle_grpc import check_availability, update_vehicle_status

app = create_app("Process Booking Service", "Composite booking and payment orchestration.")


class ReservePayload(BaseModel):
    userId: str
    vehicleId: int
    pickupLocation: str
    startTime: datetime
    endTime: datetime
    displayedPrice: float
    subscriptionPlanId: str = "STANDARD_MONTHLY"


class PaymentResultPayload(BaseModel):
    bookingId: int
    paymentId: int
    status: str


@app.post("/process-booking/reserve")
def process_booking(payload: ReservePayload):
    settings = get_settings()
    grpc_status = check_availability(payload.vehicleId)
    if not grpc_status["available"]:
        raise HTTPException(status_code=409, detail="Vehicle is not operationally available")

    availability = get_json(
        f"{settings.booking_service_url}/bookings/availability",
        {
            "vehicleId": payload.vehicleId,
            "startTime": payload.startTime.isoformat(),
            "endTime": payload.endTime.isoformat(),
        },
    )
    if not availability["slotAvailable"]:
        raise HTTPException(status_code=409, detail="Vehicle is already reserved for that slot")

    quote = get_json(
        f"{settings.pricing_service_url}/pricing/quote",
        {
            "userId": payload.userId,
            "vehicleId": payload.vehicleId,
            "startTime": payload.startTime.isoformat(),
            "endTime": payload.endTime.isoformat(),
            "subscriptionPlanId": payload.subscriptionPlanId,
        },
    )
    booking = post_json(
        f"{settings.booking_service_url}/booking",
        {
            **payload.model_dump(mode="json"),
            "displayedPrice": quote["estimatedPrice"] or payload.displayedPrice,
            "crossCycleBooking": quote["crossCycleBooking"],
            "refundPendingOnRenewal": quote["crossCycleBooking"],
            "pricingSnapshot": quote,
        },
    )
    payment = post_json(
        f"{settings.payment_service_url}/payments",
        {
            "bookingId": booking["bookingId"],
            "userId": payload.userId,
            "amount": quote["estimatedPrice"] or payload.displayedPrice,
            "reason": "BOOKING_PROVISIONAL_CHARGE",
        },
    )
    patch_json(
        f"{settings.booking_service_url}/booking/{booking['bookingId']}/status",
        {"status": "CONFIRMED"},
    )
    update_vehicle_status(payload.vehicleId, "BOOKED")
    return {
        "bookingId": booking["bookingId"],
        "status": "CONFIRMED",
        "paymentStatus": "SUCCESS",
        "paymentId": payment["paymentId"],
        "pricing": quote,
        "customerSummary": quote["customerSummary"],
    }


@app.post("/process-booking/payment-result")
def payment_result(payload: PaymentResultPayload):
    settings = get_settings()
    if payload.status.upper() == "SUCCESS":
        return patch_json(
            f"{settings.booking_service_url}/booking/{payload.bookingId}/status",
            {"status": "CONFIRMED"},
        )
    return patch_json(
        f"{settings.booking_service_url}/booking/{payload.bookingId}/status",
        {"status": "CANCELLED", "cancellationReason": "PAYMENT_FAILED"},
    )
