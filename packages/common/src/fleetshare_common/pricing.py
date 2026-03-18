from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import ceil


BASE_HOURLY_RATE = 18.0
SUBSCRIPTION_INCLUDED_HOURS = 6
APOLOGY_CREDIT = 8.0


@dataclass
class QuoteResult:
    estimated_price: float
    allowance_status: str
    cross_cycle_booking: bool
    provisional_post_midnight_hours: float


def hours_between(start: datetime, end: datetime) -> float:
    return max((end - start).total_seconds() / 3600.0, 0.0)


def post_midnight_hours(start: datetime, end: datetime) -> float:
    midnight = datetime.combine(end.date(), datetime.min.time(), tzinfo=end.tzinfo)
    if start >= midnight:
        return hours_between(start, end)
    if end <= midnight:
        return 0.0
    return hours_between(midnight, end)


def booking_quote(start: datetime, end: datetime) -> QuoteResult:
    total_hours = hours_between(start, end)
    post_midnight = post_midnight_hours(start, end)
    cross_cycle = start.date() != end.date()
    billable_hours = max(total_hours - SUBSCRIPTION_INCLUDED_HOURS, 0.0)
    provisional_post_midnight = post_midnight if cross_cycle else 0.0
    estimated = max(billable_hours, provisional_post_midnight) * BASE_HOURLY_RATE
    allowance_status = "WITHIN_ALLOWANCE" if billable_hours == 0 else "EXCESS_USAGE_ESTIMATED"
    return QuoteResult(
        estimated_price=round(estimated, 2),
        allowance_status=allowance_status,
        cross_cycle_booking=cross_cycle,
        provisional_post_midnight_hours=round(provisional_post_midnight, 2),
    )


def trip_adjustment(disrupted: bool, duration_hours: float) -> dict[str, float | bool]:
    if not disrupted:
        adjusted_fare = round(max(duration_hours - SUBSCRIPTION_INCLUDED_HOURS, 0) * BASE_HOURLY_RATE, 2)
        return {
            "compensationRequired": False,
            "adjustedFare": adjusted_fare,
            "refundAmount": 0.0,
            "discountAmount": 0.0,
        }
    refund = round(min(duration_hours, 2.0) * BASE_HOURLY_RATE, 2)
    return {
        "compensationRequired": True,
        "adjustedFare": round(max(duration_hours - 2.0, 0) * BASE_HOURLY_RATE, 2),
        "refundAmount": refund,
        "discountAmount": APOLOGY_CREDIT,
    }


def rerate_after_renewal(actual_post_midnight_hours: float) -> dict[str, float | int]:
    eligible_hours = min(actual_post_midnight_hours, SUBSCRIPTION_INCLUDED_HOURS)
    revised_charge = round(max(actual_post_midnight_hours - eligible_hours, 0) * BASE_HOURLY_RATE, 2)
    provisional_charge = round(actual_post_midnight_hours * BASE_HOURLY_RATE, 2)
    refund = round(max(provisional_charge - revised_charge, 0), 2)
    return {
        "revisedCharge": revised_charge,
        "eligibleIncludedHours": int(ceil(eligible_hours)),
        "refundAmount": refund,
        "updatedEntitlementUsage": int(ceil(eligible_hours)),
    }

