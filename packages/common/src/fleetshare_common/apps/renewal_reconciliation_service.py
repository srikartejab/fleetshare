from __future__ import annotations

from datetime import date, datetime

from dateutil.relativedelta import relativedelta
from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, Session, mapped_column

from fleetshare_common.app import create_app
from fleetshare_common.database import Base, get_db, initialize_schema_with_retry, session_scope
from fleetshare_common.http import get_json, patch_json, post_json
from fleetshare_common.messaging import publish_event, start_consumer
from fleetshare_common.settings import get_settings

app = create_app("Renewal Reconciliation Service", "Event-driven renewal refund reconciliation.")


class ProcessedRenewal(Base):
    __tablename__ = "processed_renewals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="PROCESSING")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RenewalPayload(BaseModel):
    userId: str
    subscriptionPlanId: str = "STANDARD_MONTHLY"
    newBillingCycleId: str = "next"
    renewalStatus: str = "SUCCESS"


@app.on_event("startup")
def startup_event():
    initialize_schema_with_retry(Base.metadata)
    start_consumer("renewal-reconciliation-service", ["subscription.renewed", "trip.ended"], handle_event)


@app.get("/renewal-reconciliation/events")
def list_processed(db: Session = Depends(get_db)):
    return [
        {
            "eventId": item.event_id,
            "userId": item.user_id,
            "status": item.status,
            "lastError": item.last_error,
            "createdAt": item.created_at.isoformat(),
        }
        for item in db.query(ProcessedRenewal).order_by(ProcessedRenewal.id.desc()).all()
    ]


@app.post("/renewal-reconciliation/simulate")
def simulate_renewal(payload: RenewalPayload):
    settings = get_settings()
    summary = get_json(f"{settings.pricing_service_url}/pricing/customers/{payload.userId}/summary")
    concrete_cycle_id = (
        payload.newBillingCycleId
        if payload.newBillingCycleId not in {"", "next"}
        else billing_cycle_id_for_date(date.fromisoformat(summary["renewalDate"]) + relativedelta(months=1))
    )
    publish_event("subscription.renewed", {**payload.model_dump(), "newBillingCycleId": concrete_cycle_id})
    return {"published": True, "newBillingCycleId": concrete_cycle_id}


def mark_renewal_processing(event: dict):
    payload = event["payload"]
    with session_scope() as db:
        existing = db.query(ProcessedRenewal).filter(ProcessedRenewal.event_id == event["event_id"]).first()
        if existing and existing.status == "COMPLETED":
            return False
        if existing:
            existing.status = "PROCESSING"
            existing.last_error = None
        else:
            db.add(
                ProcessedRenewal(
                    event_id=event["event_id"],
                    user_id=payload["userId"],
                    status="PROCESSING",
                )
            )
    return True


def mark_renewal_outcome(event_id: str, *, status: str, last_error: str | None = None):
    with session_scope() as db:
        existing = db.query(ProcessedRenewal).filter(ProcessedRenewal.event_id == event_id).first()
        if not existing:
            return
        existing.status = status
        existing.last_error = last_error


def billing_cycle_id_for_date(value: date) -> str:
    return value.strftime("%Y-%m")


def active_billing_cycle_id_from_summary(summary: dict) -> str:
    return billing_cycle_id_for_date(date.fromisoformat(summary["renewalDate"]))


def fetch_customer_summary(settings, user_id: str) -> dict:
    return get_json(f"{settings.pricing_service_url}/pricing/customers/{user_id}/summary")


def sorted_candidates(candidates: list[dict]) -> list[dict]:
    return sorted(
        candidates,
        key=lambda candidate: (
            candidate.get("startTime") or "",
            candidate.get("bookingId") or 0,
        ),
    )


def pending_reconciliation_candidates(settings, user_id: str, active_billing_cycle_id: str, booking_id: int | None = None) -> list[dict]:
    params = {"userId": user_id, "billingCycleId": active_billing_cycle_id}
    if booking_id is not None:
        params["bookingId"] = booking_id
    pending = get_json(
        f"{settings.booking_service_url}/bookings/reconciliation-pending",
        params,
    )
    return sorted_candidates(pending.get("reconciliationCandidates", []))


def build_completion_message(candidate: dict, rerate: dict) -> str:
    message_parts = []
    if float(rerate.get("eligibleIncludedHours", 0)) > 0:
        message_parts.append(
            f"{float(rerate['eligibleIncludedHours']):.1f}h moved into the new cycle allowance"
        )
    if float(rerate.get("refundAmount", 0)) > 0:
        message_parts.append(f"SGD {float(rerate['refundAmount']):.2f} refunded")
    if not message_parts:
        message_parts.append("No additional refund was required after re-rating")
    return f"Booking {candidate['bookingId']} was re-rated after renewal. {'; '.join(message_parts)}."


def process_pending_reconciliations(
    settings,
    user_id: str,
    active_billing_cycle_id: str,
    booking_id: int | None = None,
) -> int:
    processed = 0
    for candidate in pending_reconciliation_candidates(settings, user_id, active_billing_cycle_id, booking_id):
        if not candidate.get("refundPendingOnRenewal"):
            continue

        trip_id = candidate.get("tripId")
        if not trip_id:
            continue

        trip = get_json(f"{settings.trip_service_url}/trips/{trip_id}")
        if trip.get("status") != "ENDED" or not trip.get("endedAt"):
            continue

        rerate = post_json(
            f"{settings.pricing_service_url}/pricing/re-rate-renewed-booking",
            {
                "bookingId": candidate["bookingId"],
                "tripId": trip_id,
                "userId": user_id,
                "newBillingCycleId": active_billing_cycle_id,
                "actualPostMidnightHours": trip.get("actualPostMidnightHours") or 0.0,
            },
        )

        if float(rerate.get("refundAmount", 0)) > 0:
            publish_event(
                "payment.refund_required",
                {
                    "bookingId": candidate["bookingId"],
                    "tripId": trip_id,
                    "userId": user_id,
                    "refundAmount": rerate["refundAmount"],
                    "reason": "RENEWAL_RECONCILIATION",
                },
            )

        patch_json(
            f"{settings.booking_service_url}/booking/{candidate['bookingId']}/reconciliation-complete",
            {
                "finalPrice": rerate["finalPrice"],
                "refund_pending_on_renewal": False,
                "reconciliationStatus": "COMPLETED",
            },
        )

        if float(rerate.get("refundAmount", 0)) > 0 or float(rerate.get("eligibleIncludedHours", 0)) > 0:
            publish_event(
                "billing.refund_adjustment_completed",
                {
                    "bookingId": candidate["bookingId"],
                    "tripId": trip_id,
                    "userId": user_id,
                    "subject": "Billing adjustment completed",
                    "message": build_completion_message(candidate, rerate),
                },
            )
        processed += 1
    return processed


def handle_renewal_event(event: dict):
    settings = get_settings()
    payload = event["payload"]
    if not mark_renewal_processing(event):
        return

    try:
        renewal_result = post_json(
            f"{settings.pricing_service_url}/pricing/customers/{payload['userId']}/renewal",
            {"newBillingCycleId": payload.get("newBillingCycleId", "next")},
        )
        active_billing_cycle_id = renewal_result.get("billingCycleId")
        if not active_billing_cycle_id:
            raise RuntimeError("Pricing renewal response did not include billingCycleId")
        process_pending_reconciliations(settings, payload["userId"], active_billing_cycle_id)
    except Exception as exc:
        mark_renewal_outcome(event["event_id"], status="FAILED", last_error=str(exc))
        raise
    mark_renewal_outcome(event["event_id"], status="COMPLETED")


def handle_trip_ended_event(event: dict):
    settings = get_settings()
    payload = event["payload"]
    booking = get_json(f"{settings.booking_service_url}/booking/{payload['bookingId']}")
    if not booking.get("refundPendingOnRenewal"):
        return

    current_summary = fetch_customer_summary(settings, payload["userId"])
    active_billing_cycle_id = active_billing_cycle_id_from_summary(current_summary)
    if booking.get("pricingSnapshot", {}).get("nextBillingCycleId") != active_billing_cycle_id:
        return

    process_pending_reconciliations(settings, payload["userId"], active_billing_cycle_id, booking_id=payload["bookingId"])


def handle_event(event: dict):
    if event.get("event_type") == "subscription.renewed":
        handle_renewal_event(event)
        return
    if event.get("event_type") == "trip.ended":
        handle_trip_ended_event(event)
