from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, Query
from pydantic import BaseModel

from fleetshare_common.app import create_app
from fleetshare_common.http import get_json, patch_json, post_json
from fleetshare_common.settings import get_settings
from fleetshare_common.vehicle_grpc import check_availability

app = create_app("Process Booking Service", "Composite booking and payment orchestration.")


def validate_booking_window(start_time: datetime, end_time: datetime) -> None:
    if end_time <= start_time:
        raise HTTPException(status_code=400, detail="endTime must be later than startTime")


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


class PaymentPayload(BaseModel):
    bookingId: int
    userId: str
    amount: float | None = None
    paymentMethod: str = "SIMULATED_CARD"


@app.get("/process-booking/search")
def search_booking_options(
    userId: str = Query(...),
    startTime: datetime = Query(...),
    endTime: datetime = Query(...),
    pickupLocation: str = Query(...),
    vehicleType: str | None = None,
    subscriptionPlanId: str = "STANDARD_MONTHLY",
):
    validate_booking_window(startTime, endTime)
    settings = get_settings()
    params = {
        "userId": userId,
        "startTime": startTime.isoformat(),
        "endTime": endTime.isoformat(),
        "pickupLocation": pickupLocation,
        "subscriptionPlanId": subscriptionPlanId,
    }
    if vehicleType:
        params["vehicleType"] = vehicleType
    return get_json(f"{settings.search_service_url}/search-vehicles/search", params)


@app.post("/process-booking/reserve")
def process_booking(payload: ReservePayload):
    validate_booking_window(payload.startTime, payload.endTime)
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
            "displayedPrice": quote["estimatedPrice"],
            "crossCycleBooking": quote["crossCycleBooking"],
            "refundPendingOnRenewal": quote["crossCycleBooking"],
            "pricingSnapshot": quote,
        },
    )
    return {
        "bookingId": booking["bookingId"],
        "status": "PAYMENT_PENDING",
        "paymentStatus": "REQUIRED",
        "pricing": quote,
        "customerSummary": quote["customerSummary"],
    }


@app.post("/process-booking/pay")
def pay_for_booking(payload: PaymentPayload):
    settings = get_settings()
    booking = get_json(f"{settings.booking_service_url}/booking/{payload.bookingId}")
    amount = payload.amount if payload.amount is not None else float(booking["displayedPrice"])
    payment = post_json(
        f"{settings.payment_service_url}/payments",
        {
            "bookingId": payload.bookingId,
            "userId": payload.userId,
            "amount": amount,
            "reason": "BOOKING_PROVISIONAL_CHARGE",
        },
    )
    result = payment_result(
        PaymentResultPayload(bookingId=payload.bookingId, paymentId=payment["paymentId"], status=payment["status"])
    )
    return {
        "bookingId": payload.bookingId,
        "paymentId": payment["paymentId"],
        "paymentMethod": payload.paymentMethod,
        **result,
    }


@app.post("/process-booking/payment-result")
def payment_result(payload: PaymentResultPayload):
    settings = get_settings()
    if payload.status.upper() == "SUCCESS":
        booking = patch_json(
            f"{settings.booking_service_url}/booking/{payload.bookingId}/status",
            {"status": "CONFIRMED"},
        )
        return {"status": booking["status"], "paymentStatus": "SUCCESS"}
    booking = patch_json(
        f"{settings.booking_service_url}/booking/{payload.bookingId}/status",
        {"status": "CANCELLED", "cancellationReason": "PAYMENT_FAILED"},
    )
    return {"status": booking["status"], "paymentStatus": "FAILED"}
