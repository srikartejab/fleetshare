from __future__ import annotations

from datetime import datetime

from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, Session, mapped_column

from fleetshare_common.app import create_app
from fleetshare_common.database import Base, get_db, initialize_schema_with_retry

app = create_app("Maintenance Service", "Atomic maintenance ticket service.")


class MaintenanceTicket(Base):
    __tablename__ = "maintenance_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vehicle_id: Mapped[int] = mapped_column(Integer, index=True)
    damage_severity: Mapped[str] = mapped_column(String(32))
    damage_type: Mapped[str] = mapped_column(String(128))
    recommended_action: Mapped[str] = mapped_column(String(255))
    estimated_duration_hours: Mapped[int] = mapped_column(Integer, default=24)
    record_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    booking_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trip_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    opened_by_event_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="OPEN")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TicketPayload(BaseModel):
    vehicleId: int
    damageSeverity: str
    damageType: str
    recommendedAction: str
    estimatedDurationHours: int = 24
    recordId: int | None = None
    bookingId: int | None = None
    tripId: int | None = None
    openedByEventType: str | None = None


def ticket_to_dict(ticket: MaintenanceTicket) -> dict:
    return {
        "ticketId": ticket.id,
        "vehicleId": ticket.vehicle_id,
        "damageSeverity": ticket.damage_severity,
        "damageType": ticket.damage_type,
        "recommendedAction": ticket.recommended_action,
        "estimatedDurationHours": ticket.estimated_duration_hours,
        "recordId": ticket.record_id,
        "bookingId": ticket.booking_id,
        "tripId": ticket.trip_id,
        "openedByEventType": ticket.opened_by_event_type,
        "status": ticket.status,
        "createdAt": ticket.created_at.isoformat() if ticket.created_at else None,
    }


@app.on_event("startup")
def startup_event():
    initialize_schema_with_retry(Base.metadata)


@app.get("/maintenance/tickets")
def list_tickets(db: Session = Depends(get_db)):
    return [ticket_to_dict(ticket) for ticket in db.query(MaintenanceTicket).order_by(MaintenanceTicket.id.desc()).all()]


@app.post("/maintenance/tickets")
def create_ticket(payload: TicketPayload, db: Session = Depends(get_db)):
    ticket = MaintenanceTicket(
        vehicle_id=payload.vehicleId,
        damage_severity=payload.damageSeverity,
        damage_type=payload.damageType,
        recommended_action=payload.recommendedAction,
        estimated_duration_hours=payload.estimatedDurationHours,
        record_id=payload.recordId,
        booking_id=payload.bookingId,
        trip_id=payload.tripId,
        opened_by_event_type=payload.openedByEventType,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket_to_dict(ticket)


@app.get("/maintenance/tickets/{ticket_id}")
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.get(MaintenanceTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket_to_dict(ticket)
