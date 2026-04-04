from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, Query
from pydantic import BaseModel

from fleetshare_common.app import create_app
from fleetshare_common.http import get_json, patch_json, post_json
from fleetshare_common.settings import get_settings
from fleetshare_common.vehicle_grpc import check_availability

app = create_app("Process Booking Service", "Public booking and billing composite service.")


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


def customer_summary(user_id: str) -> dict:
    settings = get_settings()
    return get_json(f"{settings.pricing_service_url}/pricing/customers/{user_id}/summary")


def customer_bookings(user_id: str) -> list[dict]:
    settings = get_settings()
    result = get_json(f"{settings.booking_service_url}/bookings", {"userId": user_id})
    return result if isinstance(result, list) else []


def customer_notifications(user_id: str) -> list[dict]:
    settings = get_settings()
    result = get_json(f"{settings.notification_service_url}/notifications", {"userId": user_id})
    return result if isinstance(result, list) else []


@app.get("/process-booking/customer-profiles")
def list_customer_profiles():
    settings = get_settings()
    result = get_json(f"{settings.pricing_service_url}/pricing/customers")
    return result if isinstance(result, list) else []


@app.get("/process-booking/discovery-metadata")
def discovery_metadata():
    settings = get_settings()
    vehicles = get_json(f"{settings.vehicle_service_url}/vehicles")
    filters = get_json(f"{settings.vehicle_service_url}/vehicles/filters")
    return {
        "vehicles": vehicles if isinstance(vehicles, list) else [],
        "filters": filters,
    }


@app.get("/process-booking/customers/{user_id}/home")
def get_customer_home(user_id: str):
    return {
        "customerSummary": customer_summary(user_id),
        "bookings": customer_bookings(user_id),
        "notifications": customer_notifications(user_id),
    }


@app.get("/process-booking/customers/{user_id}/bookings")
def get_customer_booking_list(user_id: str):
    return {
        "customerSummary": customer_summary(user_id),
        "bookings": customer_bookings(user_id),
    }


@app.get("/process-booking/bookings/{booking_id}")
def get_booking_detail(booking_id: int):
    settings = get_settings()
    booking = get_json(f"{settings.booking_service_url}/booking/{booking_id}")
    vehicle = get_json(f"{settings.vehicle_service_url}/vehicles/{booking['vehicleId']}")
    return {
        "booking": booking,
        "vehicle": vehicle,
        "customerSummary": customer_summary(booking["userId"]),
    }


@app.get("/process-booking/customers/{user_id}/wallet")
def get_customer_wallet(user_id: str):
    settings = get_settings()
    payments = get_json(f"{settings.payment_service_url}/payments", {"userId": user_id})
    ledger_entries = get_json(f"{settings.pricing_service_url}/pricing/customers/{user_id}/ledger")
    return {
        "customerSummary": customer_summary(user_id),
        "bookings": customer_bookings(user_id),
        "payments": payments if isinstance(payments, list) else [],
        "ledgerEntries": ledger_entries if isinstance(ledger_entries, list) else [],
    }


@app.get("/process-booking/customers/{user_id}/account")
def get_customer_account(user_id: str):
    return {
        "customerSummary": customer_summary(user_id),
        "notifications": customer_notifications(user_id),
    }


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
