from __future__ import annotations

from datetime import date, datetime

from dateutil.relativedelta import relativedelta
from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, Session, mapped_column

from fleetshare_common.app import create_app
from fleetshare_common.database import Base, engine, get_db
from fleetshare_common.pricing import APOLOGY_CREDIT, BASE_HOURLY_RATE, booking_quote, rerate_after_renewal, trip_adjustment
from fleetshare_common.timeutils import as_utc_naive, utcnow

app = create_app("Pricing Service", "Atomic pricing and re-rating service.")


class CustomerProfile(Base):
    __tablename__ = "customer_profiles"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(32), default="CUSTOMER")
    demo_badge: Mapped[str | None] = mapped_column(String(128), nullable=True)
    plan_name: Mapped[str] = mapped_column(String(64), default="STANDARD_MONTHLY")
    monthly_included_hours: Mapped[float] = mapped_column(Float, default=6.0)
    hours_used_this_cycle: Mapped[float] = mapped_column(Float, default=0.0)
    renewal_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class UsageLedger(Base):
    __tablename__ = "pricing_usage_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    booking_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    trip_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime] = mapped_column(DateTime)
    total_hours: Mapped[float] = mapped_column(Float, default=0.0)
    current_cycle_hours: Mapped[float] = mapped_column(Float, default=0.0)
    included_hours_applied: Mapped[float] = mapped_column(Float, default=0.0)
    included_hours_after_renewal: Mapped[float] = mapped_column(Float, default=0.0)
    billable_hours: Mapped[float] = mapped_column(Float, default=0.0)
    provisional_post_renewal_hours: Mapped[float] = mapped_column(Float, default=0.0)
    provisional_charge: Mapped[float] = mapped_column(Float, default=0.0)
    base_charge: Mapped[float] = mapped_column(Float, default=0.0)
    final_charge: Mapped[float] = mapped_column(Float, default=0.0)
    refund_amount: Mapped[float] = mapped_column(Float, default=0.0)
    discount_amount: Mapped[float] = mapped_column(Float, default=0.0)
    renewal_pending: Mapped[bool] = mapped_column(Boolean, default=False)
    reconciliation_status: Mapped[str] = mapped_column(String(64), default="NONE")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class ReRatePayload(BaseModel):
    bookingId: int
    tripId: int
    userId: str
    newBillingCycleId: str
    actualPostMidnightHours: float


class RenewalPayload(BaseModel):
    newBillingCycleId: str = "next"


class FinalizeTripPayload(BaseModel):
    bookingId: int
    tripId: int
    userId: str
    startedAt: datetime
    endedAt: datetime
    disrupted: bool = False


class DisruptionCompensationPayload(BaseModel):
    affectedBookings: list[dict]
    reason: str = "VEHICLE_UNAVAILABLE"


def seed_customers():
    today = utcnow().date()
    with Session(engine) as db:
        if db.query(CustomerProfile).count():
            return
        db.add_all(
            [
                CustomerProfile(
                    user_id="user-1001",
                    display_name="Alicia Tan",
                    role="CUSTOMER",
                    demo_badge="Renews tonight",
                    plan_name="STANDARD_MONTHLY",
                    monthly_included_hours=6.0,
                    hours_used_this_cycle=5.0,
                    renewal_date=today,
                ),
                CustomerProfile(
                    user_id="user-1002",
                    display_name="Marcus Lee",
                    role="CUSTOMER",
                    demo_badge="Active commuter",
                    plan_name="STANDARD_MONTHLY",
                    monthly_included_hours=6.0,
                    hours_used_this_cycle=2.0,
                    renewal_date=today + relativedelta(days=8),
                ),
                CustomerProfile(
                    user_id="user-1003",
                    display_name="Priya Nair",
                    role="CUSTOMER",
                    demo_badge="Allowance almost used",
                    plan_name="STANDARD_MONTHLY",
                    monthly_included_hours=6.0,
                    hours_used_this_cycle=5.5,
                    renewal_date=today + relativedelta(days=14),
                ),
                CustomerProfile(
                    user_id="ops-maint-1",
                    display_name="Maintenance Ops",
                    role="OPS",
                    demo_badge="Ops notification demo",
                    plan_name="OPERATIONS",
                    monthly_included_hours=0.0,
                    hours_used_this_cycle=0.0,
                    renewal_date=today + relativedelta(months=1),
                ),
            ]
        )
        db.commit()


@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)
    seed_customers()


def get_profile_or_404(db: Session, user_id: str) -> CustomerProfile:
    profile = db.get(CustomerProfile, user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Customer profile not found")
    return profile


def summary_from_profile(profile: CustomerProfile) -> dict:
    remaining = max(profile.monthly_included_hours - profile.hours_used_this_cycle, 0.0)
    return {
        "userId": profile.user_id,
        "displayName": profile.display_name,
        "role": profile.role,
        "demoBadge": profile.demo_badge,
        "planName": profile.plan_name,
        "monthlyIncludedHours": round(profile.monthly_included_hours, 2),
        "hoursUsedThisCycle": round(profile.hours_used_this_cycle, 2),
        "remainingHoursThisCycle": round(remaining, 2),
        "renewalDate": profile.renewal_date.isoformat(),
        "hourlyRate": BASE_HOURLY_RATE,
    }


def quote_to_dict(user_id: str, quote, profile: CustomerProfile) -> dict:
    current_cycle_id = profile.renewal_date.strftime("%Y-%m")
    next_cycle_id = (profile.renewal_date + relativedelta(months=1)).strftime("%Y-%m")
    return {
        "userId": user_id,
        "estimatedPrice": quote.estimated_price,
        "allowanceStatus": quote.allowance_status,
        "crossCycleBooking": quote.cross_cycle_booking,
        "hourlyRate": quote.hourly_rate,
        "totalHours": quote.total_hours,
        "currentCycleHours": quote.current_cycle_hours,
        "includedHoursRemainingBefore": quote.included_hours_remaining_before,
        "includedHoursApplied": quote.included_hours_applied,
        "includedHoursRemainingAfter": quote.included_hours_remaining_after,
        "billableHours": quote.billable_hours,
        "provisionalPostMidnightHours": quote.provisional_post_midnight_hours,
        "provisionalCharge": quote.provisional_charge,
        "currentBillingCycleId": current_cycle_id,
        "nextBillingCycleId": next_cycle_id,
    }


def response_from_ledger(ledger: UsageLedger, profile: CustomerProfile, *, idempotent: bool) -> dict:
    return {
        "bookingId": ledger.booking_id,
        "tripId": ledger.trip_id,
        "userId": ledger.user_id,
        "baseCharge": round(ledger.base_charge, 2),
        "finalPrice": round(ledger.final_charge, 2),
        "refundAmount": round(ledger.refund_amount, 2),
        "discountAmount": round(ledger.discount_amount, 2),
        "renewalPending": ledger.renewal_pending,
        "reconciliationStatus": ledger.reconciliation_status,
        "allowanceHoursApplied": round(ledger.included_hours_applied, 2),
        "postRenewalIncludedHoursApplied": round(ledger.included_hours_after_renewal, 2),
        "provisionalPostMidnightHours": round(ledger.provisional_post_renewal_hours, 2),
        "customerSummary": summary_from_profile(profile),
        "idempotent": idempotent,
    }


@app.get("/pricing/customers")
def list_customers(db: Session = Depends(get_db)):
    return [summary_from_profile(profile) for profile in db.query(CustomerProfile).order_by(CustomerProfile.user_id).all()]


@app.get("/pricing/customers/{user_id}/summary")
def get_customer_summary(user_id: str, db: Session = Depends(get_db)):
    return summary_from_profile(get_profile_or_404(db, user_id))


@app.post("/pricing/customers/{user_id}/renewal")
def apply_customer_renewal(user_id: str, payload: RenewalPayload, db: Session = Depends(get_db)):
    profile = get_profile_or_404(db, user_id)
    profile.hours_used_this_cycle = 0.0
    profile.renewal_date = profile.renewal_date + relativedelta(months=1)
    db.commit()
    return {
        **summary_from_profile(profile),
        "billingCycleId": payload.newBillingCycleId,
    }


@app.get("/pricing/quote")
def get_quote(
    userId: str,
    vehicleId: int,
    startTime: datetime = Query(...),
    endTime: datetime = Query(...),
    subscriptionPlanId: str = "STANDARD_MONTHLY",
    db: Session = Depends(get_db),
):
    profile = get_profile_or_404(db, userId)
    quote = booking_quote(
        startTime,
        endTime,
        monthly_included_hours=profile.monthly_included_hours,
        hours_used_this_cycle=profile.hours_used_this_cycle,
        renewal_date=profile.renewal_date,
    )
    return {
        "vehicleId": vehicleId,
        "subscriptionPlanId": subscriptionPlanId,
        **quote_to_dict(userId, quote, profile),
        "renewalDate": profile.renewal_date.isoformat(),
        "customerSummary": summary_from_profile(profile),
    }


@app.post("/pricing/finalize-trip")
def finalize_trip_pricing(payload: FinalizeTripPayload, db: Session = Depends(get_db)):
    profile = get_profile_or_404(db, payload.userId)
    existing = db.query(UsageLedger).filter(UsageLedger.booking_id == payload.bookingId).first()
    if existing and existing.trip_id == payload.tripId:
        return response_from_ledger(existing, profile, idempotent=True)

    normalized_start = as_utc_naive(payload.startedAt)
    normalized_end = as_utc_naive(payload.endedAt)
    quote = booking_quote(
        normalized_start,
        normalized_end,
        monthly_included_hours=profile.monthly_included_hours,
        hours_used_this_cycle=profile.hours_used_this_cycle,
        renewal_date=profile.renewal_date,
    )
    adjustment = trip_adjustment(payload.disrupted, quote.total_hours, quote.estimated_price)
    profile.hours_used_this_cycle = round(profile.hours_used_this_cycle + quote.included_hours_applied, 2)

    if not existing:
        existing = UsageLedger(
            booking_id=payload.bookingId,
            trip_id=payload.tripId,
            user_id=payload.userId,
            start_time=normalized_start,
            end_time=normalized_end,
        )
        db.add(existing)

    existing.trip_id = payload.tripId
    existing.user_id = payload.userId
    existing.start_time = normalized_start
    existing.end_time = normalized_end
    existing.total_hours = quote.total_hours
    existing.current_cycle_hours = quote.current_cycle_hours
    existing.included_hours_applied = quote.included_hours_applied
    existing.billable_hours = quote.billable_hours
    existing.provisional_post_renewal_hours = quote.provisional_post_midnight_hours
    existing.provisional_charge = quote.provisional_charge
    existing.base_charge = quote.estimated_price
    existing.final_charge = float(adjustment["adjustedFare"])
    existing.refund_amount = float(adjustment["refundAmount"])
    existing.discount_amount = float(adjustment["discountAmount"])
    existing.renewal_pending = quote.provisional_post_midnight_hours > 0
    existing.reconciliation_status = "PENDING" if existing.renewal_pending else "NONE"
    db.commit()

    return response_from_ledger(existing, profile, idempotent=False)


@app.get("/pricing/trip-adjustment")
def get_trip_adjustment(tripId: int, durationHours: float = 0.0, disrupted: bool = False, baseFare: float | None = None):
    return {"tripId": tripId, **trip_adjustment(disrupted, durationHours, baseFare)}


@app.post("/pricing/disruption-compensation")
def disruption_compensation(payload: DisruptionCompensationPayload):
    adjustments = []
    for booking in payload.affectedBookings:
        base_amount = float(booking.get("finalPrice") or booking.get("displayedPrice") or 0.0)
        adjustments.append(
            {
                "bookingId": booking["bookingId"],
                "tripId": booking.get("tripId"),
                "userId": booking["userId"],
                "refundAmount": round(base_amount, 2),
                "discountAmount": APOLOGY_CREDIT,
                "reason": payload.reason,
            }
        )
    return {
        "adjustments": adjustments,
        "affectedUsers": sorted({item["userId"] for item in adjustments}),
        "totalRefundAmount": round(sum(item["refundAmount"] for item in adjustments), 2),
        "totalDiscountAmount": round(sum(item["discountAmount"] for item in adjustments), 2),
    }


@app.post("/pricing/re-rate-renewed-booking")
def rerate(payload: ReRatePayload, db: Session = Depends(get_db)):
    profile = get_profile_or_404(db, payload.userId)
    rerate_result = rerate_after_renewal(
        payload.actualPostMidnightHours,
        monthly_included_hours=profile.monthly_included_hours,
        hours_used_this_cycle=profile.hours_used_this_cycle,
    )
    profile.hours_used_this_cycle = rerate_result["updatedEntitlementUsage"]

    ledger = db.query(UsageLedger).filter(UsageLedger.booking_id == payload.bookingId).first()
    if not ledger:
        ledger = UsageLedger(
            booking_id=payload.bookingId,
            trip_id=payload.tripId,
            user_id=payload.userId,
            start_time=as_utc_naive(utcnow()),
            end_time=as_utc_naive(utcnow()),
        )
        db.add(ledger)

    ledger.trip_id = payload.tripId
    ledger.user_id = payload.userId
    ledger.provisional_post_renewal_hours = payload.actualPostMidnightHours
    ledger.included_hours_after_renewal = rerate_result["eligibleIncludedHours"]
    ledger.refund_amount = rerate_result["refundAmount"]
    ledger.renewal_pending = False
    ledger.reconciliation_status = "COMPLETED"
    ledger.final_charge = max(ledger.final_charge - rerate_result["refundAmount"], 0.0)
    db.commit()

    return {
        "bookingId": payload.bookingId,
        "tripId": payload.tripId,
        **rerate_result,
        "finalPrice": round(ledger.final_charge, 2),
        "customerSummary": summary_from_profile(profile),
    }
