from __future__ import annotations

from datetime import datetime

from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, Session, mapped_column

from fleetshare_common.app import create_app
from fleetshare_common.database import Base, engine, get_db, session_scope
from fleetshare_common.http import get_json, patch_json, post_json
from fleetshare_common.messaging import publish_event, start_consumer
from fleetshare_common.settings import get_settings

app = create_app("Renewal Reconciliation Service", "Event-driven renewal refund reconciliation.")


class ProcessedRenewal(Base):
    __tablename__ = "processed_renewals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RenewalPayload(BaseModel):
    userId: str
    subscriptionPlanId: str = "STANDARD_MONTHLY"
    newBillingCycleId: str = "2026-04"
    renewalStatus: str = "SUCCESS"


@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)
    start_consumer("renewal-reconciliation-service", ["subscription.renewed"], handle_renewal_event)


@app.get("/renewal-reconciliation/events")
def list_processed(db: Session = Depends(get_db)):
    return [
        {"eventId": item.event_id, "userId": item.user_id, "createdAt": item.created_at.isoformat()}
        for item in db.query(ProcessedRenewal).order_by(ProcessedRenewal.id.desc()).all()
    ]


@app.post("/renewal-reconciliation/simulate")
def simulate_renewal(payload: RenewalPayload):
    publish_event("subscription.renewed", payload.model_dump())
    return {"published": True}


def handle_renewal_event(event: dict):
    settings = get_settings()
    payload = event["payload"]
    with session_scope() as db:
        if db.query(ProcessedRenewal).filter(ProcessedRenewal.event_id == event["event_id"]).first():
            return
        db.add(ProcessedRenewal(event_id=event["event_id"], user_id=payload["userId"]))

    pending = get_json(
        f"{settings.booking_service_url}/bookings/reconciliation-pending",
        {"userId": payload["userId"], "billingCycleId": payload.get("newBillingCycleId", "next")},
    )
    for candidate in pending["reconciliationCandidates"]:
        trip_id = candidate.get("tripId")
        if not trip_id:
            continue
        usage = get_json(f"{settings.trip_service_url}/trips/{trip_id}/post-midnight-usage")
        rerate = post_json(
            f"{settings.pricing_service_url}/pricing/re-rate-renewed-booking",
            {
                "bookingId": candidate["bookingId"],
                "tripId": trip_id,
                "userId": payload["userId"],
                "newBillingCycleId": payload.get("newBillingCycleId", "next"),
                "actualPostMidnightHours": usage["actualPostMidnightHours"],
            },
        )
        if rerate["refundAmount"] > 0:
            publish_event(
                "payment.refund_required",
                {
                    "bookingId": candidate["bookingId"],
                    "tripId": trip_id,
                    "userId": payload["userId"],
                    "refundAmount": rerate["refundAmount"],
                    "reason": "RENEWAL_RECONCILIATION",
                },
            )
        patch_json(
            f"{settings.booking_service_url}/booking/{candidate['bookingId']}/reconciliation-status",
            {
                "refund_pending_on_renewal": False,
                "reconciliationStatus": "COMPLETED",
            },
        )
        publish_event(
            "billing.refund_adjustment_completed",
            {
                "bookingId": candidate["bookingId"],
                "tripId": trip_id,
                "userId": payload["userId"],
                "subject": "Billing adjustment completed",
                "message": f"Booking {candidate['bookingId']} was re-rated after renewal. Refund: SGD {rerate['refundAmount']:.2f}",
            },
        )
