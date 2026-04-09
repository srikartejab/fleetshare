from __future__ import annotations

import logging
from datetime import date, datetime

from dateutil.relativedelta import relativedelta
from fastapi import HTTPException
from pydantic import BaseModel

from fleetshare_common.app import create_app
from fleetshare_common.http import get_json, patch_json, post_json
from fleetshare_common.messaging import publish_event, stable_event_id, start_consumer
from fleetshare_common.settings import get_settings

app = create_app("Renewal Reconciliation Service", "Event-driven renewal refund reconciliation.")
logger = logging.getLogger("fleetshare.renewal_reconciliation")


class RenewalPayload(BaseModel):
    userId: str
    subscriptionPlanId: str = "STANDARD_MONTHLY"
    newBillingCycleId: str = "next"
    renewalStatus: str = "SUCCESS"


@app.on_event("startup")
def startup_event():
    start_consumer(
        "renewal-reconciliation-service",
        ["subscription.renewed", "trip.ended", "payment.refund_completed"],
        handle_event,
    )


@app.post("/renewal-reconciliation/simulate")
def simulate_renewal(payload: RenewalPayload):
    settings = get_settings()
    summary = get_json(f"{settings.pricing_service_url}/pricing/customers/{payload.userId}/summary")
    concrete_cycle_id = (
        payload.newBillingCycleId
        if payload.newBillingCycleId not in {"", "next"}
        else billing_cycle_id_for_date(date.fromisoformat(summary["subscriptionEndDate"]) + relativedelta(months=1))
    )
    publish_event(
        "subscription.renewed",
        {**payload.model_dump(), "newBillingCycleId": concrete_cycle_id},
        event_id=stable_event_id("renewal-simulate", payload.userId, concrete_cycle_id),
    )
    return {"published": True, "newBillingCycleId": concrete_cycle_id}


def billing_cycle_id_for_date(value: date) -> str:
    return value.strftime("%Y-%m")


def active_billing_cycle_id_from_summary(summary: dict) -> str:
    return billing_cycle_id_for_date(date.fromisoformat(summary["subscriptionEndDate"]))


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


def build_completion_message(booking_id: int, rerate: dict) -> str:
    message_parts = []
    if float(rerate.get("eligibleIncludedHours", 0)) > 0:
        message_parts.append(
            f"{float(rerate['eligibleIncludedHours']):.1f}h moved into the new cycle allowance"
        )
    if float(rerate.get("refundAmount", 0)) > 0:
        message_parts.append(f"SGD {float(rerate['refundAmount']):.2f} refunded")
    if not message_parts:
        message_parts.append("No additional refund was required after re-rating")
    return f"Booking {booking_id} was re-rated after renewal. {'; '.join(message_parts)}."


def _reconciliation_event_id(kind: str, *, booking_id: int, trip_id: int, billing_cycle_id: str) -> str:
    return stable_event_id("renewal-reconciliation", kind, booking_id, trip_id, billing_cycle_id)


def patch_booking_reconciliation_state(
    settings,
    *,
    booking_id: int,
    final_price: float,
    refund_pending_on_renewal: bool,
    reconciliation_status: str,
):
    patch_json(
        f"{settings.booking_service_url}/booking/{booking_id}/reconciliation-state",
        {
            "finalPrice": final_price,
            "refund_pending_on_renewal": refund_pending_on_renewal,
            "reconciliationStatus": reconciliation_status,
        },
    )


def patch_pricing_reconciliation_state(settings, *, booking_id: int, reconciliation_status: str):
    patch_json(
        f"{settings.pricing_service_url}/pricing/bookings/{booking_id}/reconciliation-state",
        {"reconciliationStatus": reconciliation_status},
    )


def is_renewal_refund_event(payload: dict) -> bool:
    return (
        payload.get("reason") == "RENEWAL_RECONCILIATION"
        and bool(payload.get("billingCycleId"))
        and payload.get("bookingId") is not None
        and payload.get("tripId") is not None
    )


def publish_completion_notification(
    *,
    booking_id: int,
    trip_id: int,
    user_id: str,
    billing_cycle_id: str,
    rerate: dict,
):
    if float(rerate.get("refundAmount", 0)) <= 0 and float(rerate.get("eligibleIncludedHours", 0)) <= 0:
        return
    publish_event(
        "billing.refund_adjustment_completed",
        {
            "bookingId": booking_id,
            "tripId": trip_id,
            "userId": user_id,
            "subject": "Billing adjustment completed",
            "message": build_completion_message(booking_id, rerate),
        },
        event_id=_reconciliation_event_id(
            "notification",
            booking_id=booking_id,
            trip_id=trip_id,
            billing_cycle_id=billing_cycle_id,
        ),
    )


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
            refund_event_id = _reconciliation_event_id(
                "refund",
                booking_id=candidate["bookingId"],
                trip_id=trip_id,
                billing_cycle_id=active_billing_cycle_id,
            )
            publish_event(
                "payment.refund_required",
                {
                    "bookingId": candidate["bookingId"],
                    "tripId": trip_id,
                    "userId": user_id,
                    "refundAmount": rerate["refundAmount"],
                    "reason": "RENEWAL_RECONCILIATION",
                    "billingCycleId": active_billing_cycle_id,
                    "eligibleIncludedHours": rerate.get("eligibleIncludedHours", 0),
                    "finalPrice": rerate["finalPrice"],
                    "sourceEventId": refund_event_id,
                },
                event_id=refund_event_id,
            )
            patch_booking_reconciliation_state(
                settings,
                booking_id=candidate["bookingId"],
                final_price=rerate["finalPrice"],
                refund_pending_on_renewal=True,
                reconciliation_status="REFUND_PENDING",
            )
        else:
            patch_booking_reconciliation_state(
                settings,
                booking_id=candidate["bookingId"],
                final_price=rerate["finalPrice"],
                refund_pending_on_renewal=False,
                reconciliation_status="COMPLETED",
            )
            publish_completion_notification(
                booking_id=candidate["bookingId"],
                trip_id=trip_id,
                user_id=user_id,
                billing_cycle_id=active_billing_cycle_id,
                rerate=rerate,
            )
        processed += 1
    return processed


def handle_renewal_event(event: dict):
    settings = get_settings()
    payload = event["payload"]

    renewal_result = post_json(
        f"{settings.pricing_service_url}/pricing/customers/{payload['userId']}/renewal",
        {"newBillingCycleId": payload.get("newBillingCycleId", "next")},
    )
    active_billing_cycle_id = renewal_result.get("billingCycleId")
    if not active_billing_cycle_id:
        raise HTTPException(status_code=502, detail="Pricing renewal response did not include billingCycleId")
    process_pending_reconciliations(settings, payload["userId"], active_billing_cycle_id)


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


def handle_refund_completed_event(event: dict):
    settings = get_settings()
    payload = event["payload"]
    if not is_renewal_refund_event(payload):
        return

    booking_id = payload["bookingId"]
    trip_id = payload["tripId"]
    billing_cycle_id = payload["billingCycleId"]
    rerate = {
        "refundAmount": payload.get("refundAmount", 0),
        "eligibleIncludedHours": payload.get("eligibleIncludedHours", 0),
    }

    patch_booking_reconciliation_state(
        settings,
        booking_id=booking_id,
        final_price=float(payload.get("finalPrice", 0)),
        refund_pending_on_renewal=False,
        reconciliation_status="COMPLETED",
    )
    try:
        patch_pricing_reconciliation_state(
            settings,
            booking_id=booking_id,
            reconciliation_status="COMPLETED",
        )
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        logger.warning(
            "pricing reconciliation ledger missing during renewal refund completion; continuing",
            extra={"booking_id": booking_id, "trip_id": trip_id, "billing_cycle_id": billing_cycle_id},
        )
    publish_completion_notification(
        booking_id=booking_id,
        trip_id=trip_id,
        user_id=payload["userId"],
        billing_cycle_id=billing_cycle_id,
        rerate=rerate,
    )


def handle_event(event: dict):
    if event.get("event_type") == "subscription.renewed":
        handle_renewal_event(event)
        return
    if event.get("event_type") == "trip.ended":
        handle_trip_ended_event(event)
        return
    if event.get("event_type") == "payment.refund_completed":
        handle_refund_completed_event(event)
