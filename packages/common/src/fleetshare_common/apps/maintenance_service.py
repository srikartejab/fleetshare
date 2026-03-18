from __future__ import annotations

from datetime import datetime

from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, Session, mapped_column

from fleetshare_common.app import create_app
from fleetshare_common.database import Base, engine, get_db

app = create_app("Maintenance Service", "Atomic maintenance ticket service.")


class MaintenanceTicket(Base):
    __tablename__ = "maintenance_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vehicle_id: Mapped[int] = mapped_column(Integer, index=True)
    damage_severity: Mapped[str] = mapped_column(String(32))
    damage_type: Mapped[str] = mapped_column(String(128))
    recommended_action: Mapped[str] = mapped_column(String(255))
    estimated_duration_hours: Mapped[int] = mapped_column(Integer, default=24)
    status: Mapped[str] = mapped_column(String(64), default="OPEN")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TicketPayload(BaseModel):
    vehicleId: int
    damageSeverity: str
    damageType: str
    recommendedAction: str
    estimatedDurationHours: int = 24


@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)


@app.get("/maintenance/tickets")
def list_tickets(db: Session = Depends(get_db)):
    return [
        {
            "ticketId": ticket.id,
            "vehicleId": ticket.vehicle_id,
            "damageSeverity": ticket.damage_severity,
            "damageType": ticket.damage_type,
            "recommendedAction": ticket.recommended_action,
            "estimatedDurationHours": ticket.estimated_duration_hours,
            "status": ticket.status,
        }
        for ticket in db.query(MaintenanceTicket).order_by(MaintenanceTicket.id.desc()).all()
    ]


@app.post("/maintenance/tickets")
def create_ticket(payload: TicketPayload, db: Session = Depends(get_db)):
    ticket = MaintenanceTicket(
        vehicle_id=payload.vehicleId,
        damage_severity=payload.damageSeverity,
        damage_type=payload.damageType,
        recommended_action=payload.recommendedAction,
        estimated_duration_hours=payload.estimatedDurationHours,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return {"ticketId": ticket.id, "estimatedDuration": ticket.estimated_duration_hours}


@app.get("/maintenance/tickets/{ticket_id}")
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.get(MaintenanceTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {
        "ticketId": ticket.id,
        "vehicleId": ticket.vehicle_id,
        "damageSeverity": ticket.damage_severity,
        "damageType": ticket.damage_type,
        "recommendedAction": ticket.recommended_action,
        "estimatedDurationHours": ticket.estimated_duration_hours,
        "status": ticket.status,
    }

