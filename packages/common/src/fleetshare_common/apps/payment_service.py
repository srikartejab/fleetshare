from __future__ import annotations

from datetime import datetime

from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy import JSON, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, Session, mapped_column

from fleetshare_common.app import create_app
from fleetshare_common.database import Base, get_db, initialize_schema_with_retry, session_scope
from fleetshare_common.messaging import start_consumer

app = create_app("Payment Service", "Atomic simulated payment execution service.")


class PaymentRecord(Base):
    __tablename__ = "payment_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    booking_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trip_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    amount: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(64), default="SUCCESS")
    event_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PaymentPayload(BaseModel):
    bookingId: int
    userId: str
    amount: float
    reason: str
    currency: str = "SGD"


@app.on_event("startup")
def startup_event():
    initialize_schema_with_retry(Base.metadata)
    start_consumer("payment-adjustment-service", ["payment.refund_required", "payment.adjustment_required"], handle_payment_event)


@app.get("/payments")
def list_payments(userId: str | None = None, db: Session = Depends(get_db)):
    query = db.query(PaymentRecord)
    if userId:
        query = query.filter(PaymentRecord.user_id == userId)
    return [
        {
            "paymentId": payment.id,
            "bookingId": payment.booking_id,
            "tripId": payment.trip_id,
            "userId": payment.user_id,
            "amount": payment.amount,
            "reason": payment.reason,
            "status": payment.status,
            "createdAt": payment.created_at.isoformat() if payment.created_at else None,
        }
        for payment in query.order_by(PaymentRecord.id.desc()).all()
    ]


@app.post("/payments")
def make_payment(payload: PaymentPayload, db: Session = Depends(get_db)):
    payment = PaymentRecord(
        booking_id=payload.bookingId,
        user_id=payload.userId,
        amount=payload.amount,
        reason=payload.reason,
        status="SUCCESS",
        payload_json=payload.model_dump(),
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return {"paymentId": payment.id, "status": "SUCCESS"}


def handle_payment_event(event: dict):
    payload = event["payload"]
    with session_scope() as db:
        existing = db.query(PaymentRecord).filter(PaymentRecord.event_id == event["event_id"]).first()
        if existing:
            return
        booking_ids = payload.get("affectedBookingIds")
        db.add(
            PaymentRecord(
                booking_id=payload.get("bookingId") or (booking_ids[0] if booking_ids else None),
                trip_id=payload.get("tripId"),
                user_id=payload.get("userId", "ops"),
                amount=float(payload.get("refundAmount", 0)) + float(payload.get("discountAmount", 0)),
                reason=payload.get("reason", event["event_type"]),
                status="ADJUSTED" if event["event_type"] == "payment.adjustment_required" else "REFUNDED",
                event_id=event["event_id"],
                payload_json=payload,
            )
        )
