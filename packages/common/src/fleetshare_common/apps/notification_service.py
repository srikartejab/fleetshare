from __future__ import annotations

from datetime import datetime

from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, Session, mapped_column

from fleetshare_common.app import create_app
from fleetshare_common.database import Base, get_db, initialize_schema_with_retry, session_scope
from fleetshare_common.messaging import start_consumer

app = create_app("Notification Service", "Atomic in-app notification service.")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    booking_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trip_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    audience: Mapped[str] = mapped_column(String(32), default="CUSTOMER")
    subject: Mapped[str] = mapped_column(String(128))
    message: Mapped[str] = mapped_column(String(500))
    event_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DirectNotificationPayload(BaseModel):
    userId: str
    bookingId: int | None = None
    tripId: int | None = None
    subject: str
    message: str


@app.on_event("startup")
def startup_event():
    initialize_schema_with_retry(Base.metadata)
    start_consumer(
        "notification-service",
        ["booking.disruption_notification", "billing.refund_adjustment_completed"],
        handle_notification_event,
    )


@app.get("/notifications")
def list_notifications(userId: str | None = None, audience: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Notification)
    if userId:
        query = query.filter(Notification.user_id == userId)
    if audience:
        query = query.filter(Notification.audience == audience.upper())
    return [
        {
            "notificationId": item.id,
            "userId": item.user_id,
            "bookingId": item.booking_id,
            "tripId": item.trip_id,
            "audience": item.audience,
            "subject": item.subject,
            "message": item.message,
            "payload": item.payload_json,
            "createdAt": item.created_at.isoformat() if item.created_at else None,
        }
        for item in query.order_by(Notification.id.desc()).all()
    ]


@app.post("/notifications/send-customer")
def send_customer(payload: DirectNotificationPayload, db: Session = Depends(get_db)):
    db.add(
        Notification(
            user_id=payload.userId,
            booking_id=payload.bookingId,
            trip_id=payload.tripId,
            audience="CUSTOMER",
            subject=payload.subject,
            message=payload.message,
            payload_json=payload.model_dump(),
        )
    )
    db.commit()
    return {"notificationReady": True}


@app.post("/notifications/send-ops")
def send_ops(payload: DirectNotificationPayload, db: Session = Depends(get_db)):
    db.add(
        Notification(
            user_id=payload.userId,
            booking_id=payload.bookingId,
            trip_id=payload.tripId,
            audience="OPS",
            subject=payload.subject,
            message=payload.message,
            payload_json=payload.model_dump(),
        )
    )
    db.commit()
    return {"opsNotified": True}


def handle_notification_event(event: dict):
    payload = event["payload"]
    targets = payload.get("userIds") or [payload.get("userId", "ops")]
    with session_scope() as db:
        if db.query(Notification).filter(Notification.event_id == event["event_id"]).first():
            return
        for index, target in enumerate(targets):
            db.add(
                Notification(
                    user_id=str(target),
                    booking_id=payload.get("bookingId"),
                    trip_id=payload.get("tripId"),
                    audience="OPS" if str(target).lower().startswith("ops") else "CUSTOMER",
                    subject=payload.get("subject", event["event_type"]),
                    message=payload.get("message", "A FleetShare event requires attention."),
                    event_id=event["event_id"] if index == 0 else None,
                    payload_json=payload,
                )
            )

