from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import HTTPException
from pydantic import BaseModel

from fleetshare_common.app import create_app
from fleetshare_common.http import get_json, post_json, put_json
from fleetshare_common.messaging import publish_event, stable_event_id, start_consumer
from fleetshare_common.settings import get_settings
from fleetshare_common.timeutils import as_utc_naive, iso, utcnow

app = create_app("Handle Damage Service", "Event-driven recovery orchestration for damage and faults.")
OPS_USER_ID = "ops-maint-1"


class PreTripResolutionPayload(BaseModel):
    recordId: int
    bookingId: int
    vehicleId: int
    userId: str
    severity: str = "SEVERE"
    damageType: str = "unknown"
    recommendedAction: str = "Inspect vehicle"
    reason: str = "PRE_TRIP_EXTERNAL_DAMAGE"
    incidentAt: str | None = None
    sourceEventId: str | None = None


@app.on_event("startup")
def startup_event():
    start_consumer(
        "handle-damage-service",
        ["incident.external_damage_detected", "incident.internal_fault_detected"],
        handle_incident,
    )


def _captured_cash_amount(settings, booking_id: int) -> float:
    payments = get_json(
        f"{settings.payment_service_url}/payments",
        {"bookingId": booking_id, "status": "SUCCESS", "reason": "BOOKING_PROVISIONAL_CHARGE"},
    )
    if not isinstance(payments, list):
        return 0.0
    payment = next((item for item in payments if item.get("bookingId") == booking_id), None)
    return round(float(payment.get("amount", 0.0)), 2) if payment else 0.0


def _compensation_payload(affected_bookings: list[dict], settings, *, reason: str) -> dict:
    compensation_bookings = []
    for booking in affected_bookings:
        snapshot = booking.get("pricingSnapshot") or {}
        compensation_bookings.append(
            {
                "bookingId": booking["bookingId"],
                "userId": booking["userId"],
                "startTime": booking["startTime"],
                "endTime": booking["endTime"],
                "displayedPrice": booking.get("displayedPrice", 0.0),
                "capturedCashAmount": _captured_cash_amount(settings, booking["bookingId"]),
                "includedHoursApplied": snapshot.get("includedHoursApplied", 0.0),
                "provisionalPostMidnightHours": snapshot.get("provisionalPostMidnightHours", 0.0),
            }
        )
    return {
        "affectedBookings": compensation_bookings,
        "reason": reason,
    }


def _resolve_incident_time(payload: dict) -> datetime:
    raw_incident_time = payload.get("incidentAt")
    if not raw_incident_time:
        return as_utc_naive(utcnow())
    if isinstance(raw_incident_time, datetime):
        return as_utc_naive(raw_incident_time)
    normalized = str(raw_incident_time).replace("Z", "+00:00")
    return as_utc_naive(datetime.fromisoformat(normalized))


def _cancellation_breakdown(primary_booking_id: int | None, affected_bookings: list[dict]) -> dict:
    cancelled_booking_ids = [item["bookingId"] for item in affected_bookings]
    primary_booking_cancelled = primary_booking_id in cancelled_booking_ids if primary_booking_id is not None else False
    future_bookings_cancelled_count = len(
        [booking_id for booking_id in cancelled_booking_ids if primary_booking_id is None or booking_id != primary_booking_id]
    )
    return {
        "primaryBookingCancelled": primary_booking_cancelled,
        "futureBookingsCancelledCount": future_bookings_cancelled_count,
        "cancelledBookingIds": cancelled_booking_ids,
    }


def _resolve_source_event_id(payload: dict, *, reason: str, source_event_id: str | None) -> str:
    if source_event_id:
        return source_event_id
    if payload.get("sourceEventId"):
        return str(payload["sourceEventId"])
    return stable_event_id(
        "handle-damage",
        reason,
        payload.get("recordId"),
        payload.get("bookingId"),
        payload.get("tripId"),
        payload.get("vehicleId"),
    )


def resolve_damage_recovery(payload: dict, *, reason: str, source_event_id: str | None = None) -> dict:
    settings = get_settings()
    incident_time = _resolve_incident_time(payload)
    resolved_source_event_id = _resolve_source_event_id(payload, reason=reason, source_event_id=source_event_id)
    estimated_duration_hours = 24 if payload.get("severity") == "MODERATE" else 48
    maintenance_start = incident_time
    maintenance_end = maintenance_start + timedelta(hours=settings.damage_booking_lookahead_hours)
    ticket = post_json(
        f"{settings.maintenance_service_url}/maintenance/tickets",
        {
            "vehicleId": payload["vehicleId"],
            "damageSeverity": payload.get("severity", "SEVERE"),
            "damageType": payload.get("damageType", "unknown"),
            "recommendedAction": payload.get("recommendedAction", "Inspect vehicle"),
            "estimatedDurationHours": estimated_duration_hours,
            "recordId": payload.get("recordId"),
            "bookingId": payload.get("bookingId"),
            "tripId": payload.get("tripId"),
            "openedByEventType": reason,
            "sourceEventId": resolved_source_event_id,
        },
    )
    if not ticket.get("ticketId"):
        raise HTTPException(status_code=502, detail="Maintenance ticket service did not return a ticketId")
    affected = put_json(
        f"{settings.booking_service_url}/bookings/cancel-affected",
        {
            "vehicleId": payload["vehicleId"],
            "maintenanceStart": iso(maintenance_start),
            "maintenanceEnd": iso(maintenance_end),
            "reason": reason,
        },
    )

    compensation = {
        "settlements": [],
        "ledgerEntries": [],
        "affectedUsers": [],
        "totalRefundAmount": 0.0,
        "totalDiscountAmount": 0.0,
        "totalRestoredIncludedHours": 0.0,
    }
    if affected["affectedBookings"]:
        compensation = post_json(
            f"{settings.pricing_service_url}/pricing/pre-trip-cancellation-compensation",
            _compensation_payload(affected["affectedBookings"], settings, reason=reason),
        )
    cancellation_breakdown = _cancellation_breakdown(payload.get("bookingId"), affected["affectedBookings"])

    settlements_by_booking_id = {
        item["bookingId"]: item
        for item in compensation.get("settlements", [])
    }

    for booking in affected["affectedBookings"]:
        settlement = settlements_by_booking_id.get(
            booking["bookingId"],
            {
                "cashRefundAmount": 0.0,
                "restoredIncludedHours": 0.0,
                "discountAmount": 0.0,
            },
        )
        if settlement["cashRefundAmount"] > 0:
            publish_event(
                "payment.refund_required",
                {
                    "bookingId": booking["bookingId"],
                    "tripId": booking.get("tripId"),
                    "userId": booking["userId"],
                    "refundAmount": settlement["cashRefundAmount"],
                    "reason": reason,
                },
                event_id=stable_event_id("handle-damage", "refund", resolved_source_event_id, booking["bookingId"], reason),
            )
        if settlement["discountAmount"] > 0:
            publish_event(
                "payment.adjustment_required",
                {
                    "bookingId": booking["bookingId"],
                    "tripId": booking.get("tripId"),
                    "userId": booking["userId"],
                    "discountAmount": settlement["discountAmount"],
                    "reason": reason,
                },
                event_id=stable_event_id("handle-damage", "adjustment", resolved_source_event_id, booking["bookingId"], reason),
            )
        publish_event(
            "booking.disruption_notification",
            {
                "bookingId": booking["bookingId"],
                "tripId": booking.get("tripId"),
                "userIds": [booking["userId"]],
                "subject": "Vehicle disruption detected",
                "message": (
                    f"Vehicle {payload['vehicleId']} is unavailable. "
                    f"Booking {booking['bookingId']} was cancelled and compensation has been queued."
                ),
                "primaryBookingCancelled": booking["bookingId"] == payload.get("bookingId"),
                "futureBookingsCancelledCount": cancellation_breakdown["futureBookingsCancelledCount"] if booking["bookingId"] == payload.get("bookingId") else 0,
                "cancelledBookingIds": cancellation_breakdown["cancelledBookingIds"],
            },
            event_id=stable_event_id("handle-damage", "customer-notification", resolved_source_event_id, booking["bookingId"]),
        )

    publish_event(
        "booking.disruption_notification",
        {
            "bookingId": payload.get("bookingId"),
            "tripId": payload.get("tripId"),
            "userIds": [OPS_USER_ID],
            "subject": "Ops action required",
            "message": (
                f"Vehicle {payload['vehicleId']} is unavailable. "
                f"Ticket {ticket['ticketId']} opened."
            ),
            **cancellation_breakdown,
        },
        event_id=stable_event_id("handle-damage", "ops-notification", resolved_source_event_id, ticket["ticketId"]),
    )

    primary_booking = next(
        (item for item in affected["affectedBookings"] if item["bookingId"] == payload.get("bookingId")),
        None,
    )
    if primary_booking is None and payload.get("bookingId"):
        primary_booking = get_json(f"{settings.booking_service_url}/booking/{payload['bookingId']}")

    primary_settlement = settlements_by_booking_id.get(
        payload.get("bookingId"),
        {
            "cashRefundAmount": 0.0,
            "restoredIncludedHours": 0.0,
            "discountAmount": 0.0,
            "reconciliationStatus": "NONE",
        },
    )

    return {
        "maintenanceTicketId": ticket["ticketId"],
        "ticket": ticket,
        "booking": primary_booking,
        "walletSettlement": primary_settlement,
        "cancelledCount": affected["cancelledCount"],
        "primaryBookingCancelled": cancellation_breakdown["primaryBookingCancelled"],
        "futureBookingsCancelledCount": cancellation_breakdown["futureBookingsCancelledCount"],
        "cancelledBookingIds": cancellation_breakdown["cancelledBookingIds"],
        "affectedBookings": affected["affectedBookings"],
        "compensation": compensation,
    }


@app.post("/handle-damage/external/pre-trip-resolution")
def resolve_external_pre_trip_damage(payload: PreTripResolutionPayload):
    return resolve_damage_recovery(
        payload.model_dump(mode="json"),
        reason=payload.reason,
        source_event_id=payload.sourceEventId,
    )


def handle_incident(event: dict):
    payload = event["payload"]
    resolve_damage_recovery(payload, reason=event["event_type"], source_event_id=event["event_id"])

