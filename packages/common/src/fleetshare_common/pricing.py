from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from fleetshare_common.timeutils import as_billing_time, billing_timezone


BASE_HOURLY_RATE = 20.0
SUBSCRIPTION_INCLUDED_HOURS = 6.0
APOLOGY_CREDIT = 8.0


@dataclass
class QuoteResult:
    estimated_price: float
    allowance_status: str
    cross_cycle_booking: bool
    provisional_post_midnight_hours: float
    hourly_rate: float
    total_hours: float
    current_cycle_hours: float
    included_hours_remaining_before: float
    included_hours_applied: float
    included_hours_remaining_after: float
    billable_hours: float
    provisional_charge: float


def hours_between(start: datetime, end: datetime) -> float:
    return max((end - start).total_seconds() / 3600.0, 0.0)


def post_midnight_hours(start: datetime, end: datetime) -> float:
    local_start = as_billing_time(start)
    local_end = as_billing_time(end)
    midnight = datetime.combine(local_end.date(), time.min, tzinfo=billing_timezone())
    if local_start >= midnight:
        return hours_between(local_start, local_end)
    if local_end <= midnight:
        return 0.0
    return hours_between(midnight, local_end)


def hours_after_subscription_end_boundary(start: datetime, end: datetime, subscription_end_date: date | None = None) -> float:
    if subscription_end_date is None:
        return post_midnight_hours(start, end)

    local_start = as_billing_time(start)
    local_end = as_billing_time(end)
    boundary = datetime.combine(subscription_end_date + timedelta(days=1), time.min, tzinfo=billing_timezone())
    if local_end <= boundary:
        return 0.0
    if local_start >= boundary:
        return hours_between(local_start, local_end)
    return hours_between(boundary, local_end)


def booking_quote(
    start: datetime,
    end: datetime,
    monthly_included_hours: float = SUBSCRIPTION_INCLUDED_HOURS,
    hours_used_this_cycle: float = 0.0,
    subscription_end_date: date | None = None,
) -> QuoteResult:
    total_hours = hours_between(start, end)
    provisional_post_midnight = hours_after_subscription_end_boundary(start, end, subscription_end_date)
    current_cycle_hours = max(total_hours - provisional_post_midnight, 0.0)
    included_remaining_before = max(monthly_included_hours - hours_used_this_cycle, 0.0)
    included_hours_applied = min(current_cycle_hours, included_remaining_before)
    included_remaining_after = max(included_remaining_before - included_hours_applied, 0.0)
    billable_hours = max(current_cycle_hours - included_hours_applied, 0.0)
    provisional_charge = provisional_post_midnight * BASE_HOURLY_RATE
    estimated = (billable_hours * BASE_HOURLY_RATE) + provisional_charge
    cross_cycle = provisional_post_midnight > 0

    if provisional_post_midnight > 0 and billable_hours > 0:
        allowance_status = "EXCESS_USAGE_AND_RENEWAL_PENDING"
    elif provisional_post_midnight > 0:
        allowance_status = "RENEWAL_PENDING"
    elif billable_hours > 0:
        allowance_status = "EXCESS_USAGE_ESTIMATED"
    else:
        allowance_status = "WITHIN_ALLOWANCE"

    return QuoteResult(
        estimated_price=round(estimated, 2),
        allowance_status=allowance_status,
        cross_cycle_booking=cross_cycle,
        provisional_post_midnight_hours=round(provisional_post_midnight, 2),
        hourly_rate=BASE_HOURLY_RATE,
        total_hours=round(total_hours, 2),
        current_cycle_hours=round(current_cycle_hours, 2),
        included_hours_remaining_before=round(included_remaining_before, 2),
        included_hours_applied=round(included_hours_applied, 2),
        included_hours_remaining_after=round(included_remaining_after, 2),
        billable_hours=round(billable_hours, 2),
        provisional_charge=round(provisional_charge, 2),
    )


def trip_adjustment(
    disrupted: bool,
    duration_hours: float,
    base_fare: float | None = None,
    end_reason: str | None = None,
) -> dict[str, float | bool]:
    if not disrupted:
        adjusted_fare = round(base_fare if base_fare is not None else max(duration_hours - SUBSCRIPTION_INCLUDED_HOURS, 0) * BASE_HOURLY_RATE, 2)
        return {
            "compensationRequired": False,
            "adjustedFare": adjusted_fare,
            "refundAmount": 0.0,
            "discountAmount": 0.0,
        }

    baseline = round(base_fare if base_fare is not None else max(duration_hours, 0) * BASE_HOURLY_RATE, 2)
    normalized_reason = (end_reason or "").upper()
    if "INTERNAL" in normalized_reason and "FAULT" in normalized_reason:
        return {
            "compensationRequired": True,
            "adjustedFare": 0.0,
            "refundAmount": baseline,
            "discountAmount": APOLOGY_CREDIT,
        }

    refund = round(min(baseline, min(duration_hours, 2.0) * BASE_HOURLY_RATE), 2)
    return {
        "compensationRequired": True,
        "adjustedFare": round(max(baseline - refund, 0.0), 2),
        "refundAmount": refund,
        "discountAmount": APOLOGY_CREDIT,
    }


def refunded_included_hours(
    disrupted: bool,
    duration_hours: float,
    included_hours_applied: float,
    end_reason: str | None = None,
) -> float:
    if not disrupted or included_hours_applied <= 0:
        return 0.0

    normalized_reason = (end_reason or "").upper()
    if "INTERNAL" in normalized_reason and "FAULT" in normalized_reason:
        return round(included_hours_applied, 2)

    compensated_hours = min(max(duration_hours, 0.0), 2.0)
    return round(min(included_hours_applied, compensated_hours), 2)


def rerate_after_renewal(
    actual_post_midnight_hours: float,
    monthly_included_hours: float = SUBSCRIPTION_INCLUDED_HOURS,
    hours_used_this_cycle: float = 0.0,
    original_provisional_charge: float | None = None,
) -> dict[str, float]:
    remaining_hours = max(monthly_included_hours - hours_used_this_cycle, 0.0)
    eligible_hours = min(actual_post_midnight_hours, remaining_hours)
    revised_charge = round(max(actual_post_midnight_hours - eligible_hours, 0.0) * BASE_HOURLY_RATE, 2)
    provisional_charge = round(
        original_provisional_charge if original_provisional_charge is not None else actual_post_midnight_hours * BASE_HOURLY_RATE,
        2,
    )
    refund = round(max(provisional_charge - revised_charge, 0.0), 2)
    updated_usage = round(hours_used_this_cycle + eligible_hours, 2)
    return {
        "revisedCharge": revised_charge,
        "eligibleIncludedHours": round(eligible_hours, 2),
        "refundAmount": refund,
        "updatedEntitlementUsage": updated_usage,
    }
