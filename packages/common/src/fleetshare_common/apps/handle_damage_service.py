from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, Session, mapped_column

from fleetshare_common.app import create_app
from fleetshare_common.database import Base, get_db, initialize_schema_with_retry, session_scope
from fleetshare_common.http import get_json, post_json, put_json
from fleetshare_common.messaging import publish_event, start_consumer
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


class ProcessedIncident(Base):
    __tablename__ = "processed_incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True)
    event_type: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="PROCESSING")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


@app.on_event("startup")
def startup_event():
    initialize_schema_with_retry(Base.metadata)
    start_consumer(
        "handle-damage-service",
        ["incident.external_damage_detected", "incident.internal_fault_detected"],
        handle_incident,
    )


@app.get("/handle-damage/incidents")
def list_processed(db: Session = Depends(get_db)):
    return [
        {
            "eventId": item.event_id,
            "eventType": item.event_type,
            "status": item.status,
            "lastError": item.last_error,
            "createdAt": item.created_at.isoformat(),
        }
        for item in db.query(ProcessedIncident).order_by(ProcessedIncident.id.desc()).all()
    ]


def mark_incident_processing(event: dict):
    with session_scope() as db:
        existing = db.query(ProcessedIncident).filter(ProcessedIncident.event_id == event["event_id"]).first()
        if existing and existing.status == "COMPLETED":
            return False
        if existing:
            existing.status = "PROCESSING"
            existing.last_error = None
        else:
            db.add(
                ProcessedIncident(
                    event_id=event["event_id"],
                    event_type=event["event_type"],
                    status="PROCESSING",
                )
            )
    return True


def mark_incident_outcome(event_id: str, *, status: str, last_error: str | None = None):
    with session_scope() as db:
        existing = db.query(ProcessedIncident).filter(ProcessedIncident.event_id == event_id).first()
        if not existing:
            return
        existing.status = status
        existing.last_error = last_error


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


def resolve_damage_recovery(payload: dict, *, reason: str) -> dict:
    settings = get_settings()
    incident_time = _resolve_incident_time(payload)
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
        },
    )
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
            },
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
                f"Ticket {ticket['ticketId']} opened and {affected['cancelledCount']} booking(s) were cancelled."
            ),
        },
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
        "affectedBookings": affected["affectedBookings"],
        "compensation": compensation,
    }


@app.post("/handle-damage/external/pre-trip-resolution")
def resolve_external_pre_trip_damage(payload: PreTripResolutionPayload):
    return resolve_damage_recovery(
        payload.model_dump(mode="json"),
        reason=payload.reason,
    )


def handle_incident(event: dict):
    payload = event["payload"]
    if not mark_incident_processing(event):
        return

    try:
        resolve_damage_recovery(payload, reason=event["event_type"])
    except Exception as exc:
        mark_incident_outcome(event["event_id"], status="FAILED", last_error=str(exc))
        raise
    mark_incident_outcome(event["event_id"], status="COMPLETED")

