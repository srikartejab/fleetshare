from __future__ import annotations

from datetime import datetime

from fastapi import Depends
from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, Session, mapped_column

from fleetshare_common.app import create_app
from fleetshare_common.database import Base, engine, get_db, session_scope
from fleetshare_common.http import post_json, put_json
from fleetshare_common.messaging import publish_event, start_consumer
from fleetshare_common.settings import get_settings

app = create_app("Handle Damage Service", "Event-driven recovery orchestration for damage and faults.")


class ProcessedIncident(Base):
    __tablename__ = "processed_incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True)
    event_type: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)
    start_consumer(
        "handle-damage-service",
        ["incident.external_damage_detected", "incident.internal_fault_detected"],
        handle_incident,
    )


@app.get("/handle-damage/incidents")
def list_processed(db: Session = Depends(get_db)):
    return [
        {"eventId": item.event_id, "eventType": item.event_type, "createdAt": item.created_at.isoformat()}
        for item in db.query(ProcessedIncident).order_by(ProcessedIncident.id.desc()).all()
    ]


def handle_incident(event: dict):
    settings = get_settings()
    payload = event["payload"]
    with session_scope() as db:
        if db.query(ProcessedIncident).filter(ProcessedIncident.event_id == event["event_id"]).first():
            return
        db.add(ProcessedIncident(event_id=event["event_id"], event_type=event["event_type"]))

    ticket = post_json(
        f"{settings.maintenance_service_url}/maintenance/tickets",
        {
            "vehicleId": payload["vehicleId"],
            "damageSeverity": payload.get("severity", "SEVERE"),
            "damageType": payload.get("damageType", "unknown"),
            "recommendedAction": payload.get("recommendedAction", "Inspect vehicle"),
            "estimatedDurationHours": 48,
        },
    )
    affected = put_json(
        f"{settings.booking_service_url}/bookings/cancel-affected",
        {
            "vehicleId": payload["vehicleId"],
            "estimatedDurationHours": 48,
            "reason": event["event_type"],
        },
    )
    publish_event(
        "payment.adjustment_required",
        {
            "affectedBookingIds": affected["affectedBookingIds"],
            "userId": payload.get("userId", "ops"),
            "refundAmount": 18.0 * max(1, affected["cancelledCount"]),
            "discountAmount": 8.0 if affected["cancelledCount"] else 0.0,
            "reason": event["event_type"],
        },
    )
    publish_event(
        "booking.disruption_notification",
        {
            "bookingId": payload.get("bookingId"),
            "tripId": payload.get("tripId"),
            "userIds": [payload.get("userId", "ops"), "ops"],
            "subject": "Vehicle disruption detected",
            "message": f"Vehicle {payload['vehicleId']} is unavailable. Ticket {ticket['ticketId']} opened.",
        },
    )

