from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import Depends
from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, Session, mapped_column

from fleetshare_common.app import create_app
from fleetshare_common.database import Base, get_db, initialize_schema_with_retry, session_scope
from fleetshare_common.http import post_json, put_json
from fleetshare_common.messaging import publish_event, start_consumer
from fleetshare_common.settings import get_settings
from fleetshare_common.timeutils import iso, utcnow

app = create_app("Handle Damage Service", "Event-driven recovery orchestration for damage and faults.")
OPS_USER_ID = "ops-maint-1"


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


def handle_incident(event: dict):
    settings = get_settings()
    payload = event["payload"]
    if not mark_incident_processing(event):
        return

    try:
        estimated_duration_hours = 24 if payload.get("severity") == "MODERATE" else 48
        maintenance_start = utcnow()
        maintenance_end = maintenance_start + timedelta(hours=estimated_duration_hours)
        ticket = post_json(
            f"{settings.maintenance_service_url}/maintenance/tickets",
            {
                "vehicleId": payload["vehicleId"],
                "damageSeverity": payload.get("severity", "SEVERE"),
                "damageType": payload.get("damageType", "unknown"),
                "recommendedAction": payload.get("recommendedAction", "Inspect vehicle"),
                "estimatedDurationHours": estimated_duration_hours,
            },
        )
        affected = put_json(
            f"{settings.booking_service_url}/bookings/cancel-affected",
            {
                "vehicleId": payload["vehicleId"],
                "maintenanceStart": iso(maintenance_start),
                "maintenanceEnd": iso(maintenance_end),
                "reason": event["event_type"],
            },
        )
        compensation = post_json(
            f"{settings.pricing_service_url}/pricing/disruption-compensation",
            {
                "affectedBookings": affected["affectedBookings"],
                "reason": event["event_type"],
            },
        )
        for adjustment in compensation["adjustments"]:
            publish_event("payment.adjustment_required", adjustment)
            publish_event(
                "booking.disruption_notification",
                {
                    "bookingId": adjustment["bookingId"],
                    "tripId": adjustment.get("tripId"),
                    "userIds": [adjustment["userId"]],
                    "subject": "Vehicle disruption detected",
                    "message": (
                        f"Vehicle {payload['vehicleId']} is unavailable. "
                        f"Booking {adjustment['bookingId']} was cancelled and compensation has been queued."
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
    except Exception as exc:
        mark_incident_outcome(event["event_id"], status="FAILED", last_error=str(exc))
        raise
    mark_incident_outcome(event["event_id"], status="COMPLETED")

