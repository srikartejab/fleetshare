from __future__ import annotations

from typing import Any

import httpx
from fastapi import File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from fleetshare_common.app import create_app
from fleetshare_common.http import get_json, post_json
from fleetshare_common.settings import get_settings

app = create_app("Rental Execution Service", "Public rental execution composite service.")


class PreTripCancellationPayload(BaseModel):
    bookingId: int
    vehicleId: int
    userId: str


class TripStartPayload(BaseModel):
    bookingId: int
    vehicleId: int
    userId: str
    notes: str = ""


class FaultReportPayload(BaseModel):
    bookingId: int | None = None
    vehicleId: int
    userId: str | None = None
    tripId: int | None = None
    faultCode: str = ""
    sensorType: str = "USER_REPORT"
    notes: str = ""


class EndTripPayload(BaseModel):
    tripId: int
    bookingId: int
    vehicleId: int
    userId: str
    endReason: str = "USER_COMPLETED"


def _default_wallet_settlement() -> dict:
    return {
        "cashRefundAmount": 0.0,
        "restoredIncludedHours": 0.0,
        "discountAmount": 0.0,
        "reconciliationStatus": "NONE",
    }


def _vehicle_key(vehicle: dict) -> int | None:
    value = vehicle.get("vehicleId", vehicle.get("id"))
    return int(value) if value is not None else None


def _vehicle_label(vehicle: dict | None, fallback_vehicle_id: int | None = None) -> str:
    if not vehicle:
        return f"Vehicle {fallback_vehicle_id}" if fallback_vehicle_id is not None else "Vehicle"
    return vehicle.get("model") or vehicle.get("plateNumber") or f"Vehicle {_vehicle_key(vehicle) or fallback_vehicle_id}"


def _build_live_trip_advisory(
    *,
    active_trip: dict | None,
    booking_rows: list[dict],
    vehicle_by_id: dict[int, dict],
    related_records: list[dict],
    related_notifications: list[dict],
) -> dict | None:
    if not active_trip:
        return None

    active_booking = next((booking for booking in booking_rows if booking.get("bookingId") == active_trip.get("bookingId")), None)
    candidates = [
        notification
        for notification in related_notifications
        if notification.get("tripId") == active_trip.get("tripId")
        or notification.get("bookingId") == active_trip.get("bookingId")
    ]
    if not candidates:
        return None

    advisory_notification = next(
        (
            notification
            for notification in candidates
            if "issue" in str(notification.get("subject", "")).lower()
            or "stop" in str(notification.get("message", "")).lower()
            or "end trip" in str(notification.get("message", "")).lower()
        ),
        candidates[0],
    )
    relevant_record = next(
        (
            record
            for record in related_records
            if record.get("tripId") == active_trip.get("tripId")
            or record.get("bookingId") == active_trip.get("bookingId")
        ),
        None,
    )
    vehicle_id = active_trip.get("vehicleId")
    if vehicle_id is None and active_booking:
        vehicle_id = active_booking.get("vehicleId")
    vehicle = vehicle_by_id.get(int(vehicle_id)) if vehicle_id is not None else None
    severity = relevant_record.get("severity", "SEVERE") if relevant_record else advisory_notification.get("payload", {}).get("severity", "SEVERE")
    return {
        "notificationId": advisory_notification["notificationId"],
        "createdAt": advisory_notification.get("createdAt"),
        "bookingId": active_trip.get("bookingId"),
        "tripId": active_trip.get("tripId"),
        "vehicleId": vehicle_id,
        "vehicleName": _vehicle_label(vehicle, vehicle_id),
        "severity": severity,
        "subject": advisory_notification.get("subject", "Vehicle issue detected"),
        "message": advisory_notification.get("message", "A vehicle issue was detected during the current trip."),
        "requiresImmediateEndTrip": True,
        "endReason": "SEVERE_INTERNAL_FAULT",
    }


def _inspection_response(
    *,
    inspection: dict,
    booking: dict | None,
    vehicle: dict | None,
    resolution: dict | None = None,
) -> dict:
    booking_snapshot = resolution.get("booking") if resolution else booking
    wallet_settlement = resolution.get("walletSettlement") if resolution else _default_wallet_settlement()
    booking_status = booking_snapshot.get("status") if booking_snapshot else booking.get("status") if booking else None
    return {
        "recordId": inspection["recordId"],
        "bookingId": inspection["bookingId"],
        "vehicleId": inspection["vehicleId"],
        "assessmentResult": inspection["assessmentResult"],
        "tripStatus": inspection["tripStatus"],
        "warningMessage": inspection["warningMessage"],
        "manualReview": inspection["manualReview"],
        "reviewState": inspection.get("reviewState", "PENDING"),
        "bookingStatus": booking_status,
        "bookingCancelled": booking_status == "CANCELLED",
        "resolutionCompleted": resolution is not None,
        "booking": booking_snapshot,
        "vehicle": vehicle,
        "walletSettlement": wallet_settlement,
        "maintenanceTicketId": resolution.get("maintenanceTicketId") if resolution else None,
    }


def _resolve_pre_trip_damage(*, inspection: dict, reason: str) -> dict:
    settings = get_settings()
    return post_json(
        f"{settings.handle_damage_service_url}/handle-damage/external/pre-trip-resolution",
        {
            "recordId": inspection["recordId"],
            "bookingId": inspection["bookingId"],
            "vehicleId": inspection["vehicleId"],
            "userId": inspection.get("userId"),
            "severity": inspection["assessmentResult"]["severity"],
            "damageType": ",".join(inspection["assessmentResult"].get("detectedDamage") or ["possible body damage"]),
            "recommendedAction": inspection["warningMessage"],
            "reason": reason,
        },
    )


def _raise_http_error(response: httpx.Response):
    detail = response.text.strip() or response.reason_phrase
    raise HTTPException(status_code=response.status_code, detail=detail)


async def _post_multipart(url: str, fields: dict[str, Any], photos: list[UploadFile]) -> dict:
    multipart: list[tuple[str, tuple[Any, ...]]] = []
    for key, value in fields.items():
        multipart.append((key, (None, str(value))))
    for photo in photos:
        raw = await photo.read()
        multipart.append(
            (
                "photos",
                (
                    photo.filename or "upload.bin",
                    raw,
                    photo.content_type or "application/octet-stream",
                ),
            )
        )
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, files=multipart)
    if not response.is_success:
        _raise_http_error(response)
    return response.json()


@app.get("/rental-execution/customers/{user_id}/status")
def get_trip_status(user_id: str):
    settings = get_settings()
    bookings = get_json(f"{settings.booking_service_url}/bookings", {"userId": user_id})
    trips = get_json(f"{settings.trip_service_url}/trips", {"userId": user_id})
    vehicles = get_json(f"{settings.vehicle_service_url}/vehicles")
    records = get_json(f"{settings.record_service_url}/records")
    notifications = get_json(f"{settings.notification_service_url}/notifications", {"userId": user_id})

    booking_rows = bookings if isinstance(bookings, list) else []
    trip_rows = trips if isinstance(trips, list) else []
    vehicle_rows = vehicles if isinstance(vehicles, list) else []
    record_rows = records if isinstance(records, list) else []
    notification_rows = notifications if isinstance(notifications, list) else []

    booking_ids = {item["bookingId"] for item in booking_rows if item.get("bookingId") is not None}
    trip_ids = {item["tripId"] for item in trip_rows if item.get("tripId") is not None}
    related_records = [
        record
        for record in record_rows
        if record.get("bookingId") in booking_ids or record.get("tripId") in trip_ids
    ]
    related_notifications = [
        notification
        for notification in notification_rows
        if notification.get("bookingId") in booking_ids or notification.get("tripId") in trip_ids or notification.get("bookingId") is None and notification.get("tripId") is None
    ]
    vehicle_by_id = {
        key: vehicle
        for vehicle in vehicle_rows
        for key in [_vehicle_key(vehicle)]
        if key is not None
    }
    active_trip = next((trip for trip in trip_rows if trip.get("status") == "STARTED"), None)

    return {
        "bookings": booking_rows,
        "trips": trip_rows,
        "vehicles": vehicle_rows,
        "records": related_records,
        "notifications": related_notifications,
        "liveTripAdvisory": _build_live_trip_advisory(
            active_trip=active_trip,
            booking_rows=booking_rows,
            vehicle_by_id=vehicle_by_id,
            related_records=related_records,
            related_notifications=related_notifications,
        ),
    }


@app.post("/rental-execution/pre-trip-inspection")
async def pre_trip_inspection(
    bookingId: int = Form(...),
    vehicleId: int = Form(...),
    userId: str = Form(...),
    notes: str = Form(""),
    photos: list[UploadFile] = File(default_factory=list),
):
    settings = get_settings()
    inspection = await _post_multipart(
        f"{settings.external_damage_service_url}/damage-assessment/external",
        {
            "bookingId": bookingId,
            "vehicleId": vehicleId,
            "userId": userId,
            "notes": notes,
        },
        photos,
    )
    inspection["userId"] = userId
    booking = get_json(f"{settings.booking_service_url}/booking/{bookingId}")
    vehicle = get_json(f"{settings.vehicle_service_url}/vehicles/{vehicleId}")
    if inspection["tripStatus"] == "BLOCKED" and inspection["assessmentResult"]["severity"] == "SEVERE" and not inspection["manualReview"]:
        resolution = _resolve_pre_trip_damage(inspection=inspection, reason="SEVERE_EXTERNAL_DAMAGE")
        booking = resolution.get("booking") or booking
        return _inspection_response(inspection=inspection, booking=booking, vehicle=vehicle, resolution=resolution)
    return _inspection_response(inspection=inspection, booking=booking, vehicle=vehicle)


@app.post("/rental-execution/pre-trip/cancel")
def cancel_pre_trip_booking(payload: PreTripCancellationPayload):
    settings = get_settings()
    cancellation = post_json(
        f"{settings.external_damage_service_url}/damage-assessment/external/customer-cancel",
        payload.model_dump(),
    )
    resolution = post_json(
        f"{settings.handle_damage_service_url}/handle-damage/external/pre-trip-resolution",
        {
            "recordId": cancellation["recordId"],
            "bookingId": payload.bookingId,
            "vehicleId": payload.vehicleId,
            "userId": payload.userId,
            "severity": cancellation["severity"],
            "damageType": ",".join(cancellation.get("detectedDamage") or ["possible body damage"]),
            "recommendedAction": cancellation["message"],
            "reason": "MODERATE_EXTERNAL_DAMAGE_CANCELLED",
        },
    )
    booking = resolution.get("booking") or get_json(f"{settings.booking_service_url}/booking/{payload.bookingId}")
    vehicle = get_json(f"{settings.vehicle_service_url}/vehicles/{payload.vehicleId}")
    return {
        "recordId": cancellation["recordId"],
        "bookingId": payload.bookingId,
        "vehicleId": payload.vehicleId,
        "assessmentResult": {
            "severity": cancellation["severity"],
            "confidence": 0.0,
            "detectedDamage": cancellation.get("detectedDamage") or ["possible body damage"],
        },
        "tripStatus": "BLOCKED",
        "warningMessage": cancellation["warningMessage"],
        "manualReview": False,
        "reviewState": cancellation["reviewState"],
        "status": cancellation["status"],
        "message": cancellation["message"],
        "bookingStatus": booking.get("status"),
        "bookingCancelled": booking.get("status") == "CANCELLED",
        "resolutionCompleted": True,
        "booking": booking,
        "vehicle": vehicle,
        "walletSettlement": resolution.get("walletSettlement", _default_wallet_settlement()),
        "maintenanceTicketId": resolution.get("maintenanceTicketId"),
    }


@app.post("/rental-execution/start")
def start_trip(payload: TripStartPayload):
    settings = get_settings()
    return post_json(
        f"{settings.start_trip_service_url}/trips/start",
        payload.model_dump(mode="json"),
    )


@app.post("/rental-execution/report-fault")
def report_fault(payload: FaultReportPayload):
    settings = get_settings()
    return post_json(
        f"{settings.internal_damage_service_url}/internal-damage/fault-alert",
        payload.model_dump(mode="json"),
    )


@app.post("/rental-execution/post-trip-inspection")
async def post_trip_inspection(
    bookingId: int = Form(...),
    tripId: int = Form(...),
    vehicleId: int = Form(...),
    userId: str = Form(...),
    notes: str = Form(""),
    photos: list[UploadFile] = File(default_factory=list),
):
    settings = get_settings()
    return await _post_multipart(
        f"{settings.external_damage_service_url}/damage-assessment/post-trip",
        {
            "bookingId": bookingId,
            "tripId": tripId,
            "vehicleId": vehicleId,
            "userId": userId,
            "notes": notes,
        },
        photos,
    )


@app.post("/rental-execution/end")
def end_trip(payload: EndTripPayload):
    settings = get_settings()
    return post_json(
        f"{settings.end_trip_service_url}/end-trip/request",
        payload.model_dump(mode="json"),
    )
