import os
from datetime import date, datetime
from types import SimpleNamespace

from fleetshare_common.ai import assess_damage
from fleetshare_common.pricing import booking_quote, refunded_included_hours, rerate_after_renewal, trip_adjustment

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from fleetshare_common.apps import pricing_service


def test_booking_quote_detects_cross_cycle():
    quote = booking_quote(datetime(2026, 3, 31, 23, 0), datetime(2026, 4, 1, 2, 0))
    assert quote.cross_cycle_booking is True
    assert quote.provisional_post_midnight_hours == 2.0


def test_rerate_after_renewal_refunds_provisional_charge():
    rerate = rerate_after_renewal(2.0)
    assert rerate["refundAmount"] > 0
    assert rerate["revisedCharge"] == 0


def test_trip_adjustment_uses_compensation_for_disruption():
    result = trip_adjustment(True, 1.5)
    assert result["compensationRequired"] is True
    assert result["refundAmount"] > 0


def test_trip_adjustment_fully_refunds_internal_fault_endings():
    result = trip_adjustment(True, 1.5, 30.0, "SEVERE_INTERNAL_FAULT")
    assert result["compensationRequired"] is True
    assert result["adjustedFare"] == 0.0
    assert result["refundAmount"] == 30.0


def test_refunded_included_hours_matches_partial_disruption_policy():
    refunded_hours = refunded_included_hours(True, 3.5, 3.0, "USER_REPORTED_DISRUPTION")
    assert refunded_hours == 2.0


def test_refunded_included_hours_fully_restores_internal_fault_allowance():
    refunded_hours = refunded_included_hours(True, 4.0, 4.0, "SEVERE_INTERNAL_FAULT")
    assert refunded_hours == 4.0


class _FakeQuery:
    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return None


class _FakeDb:
    def __init__(self):
        self.added = []
        self.committed = False

    def query(self, _model):
        return _FakeQuery()

    def add(self, item):
        self.added.append(item)

    def commit(self):
        self.committed = True


def test_finalize_trip_pricing_returns_used_allowance_on_internal_fault(monkeypatch):
    profile = SimpleNamespace(
        user_id="user-1001",
        display_name="Alicia Tan",
        role="CUSTOMER",
        demo_badge="Renews tonight",
        plan_name="STANDARD_MONTHLY",
        monthly_included_hours=6.0,
        hours_used_this_cycle=5.0,
        renewal_date=date(2026, 3, 19),
    )
    payload = pricing_service.FinalizeTripPayload(
        bookingId=11,
        tripId=21,
        userId="user-1001",
        startedAt=datetime(2026, 3, 19, 10, 0),
        endedAt=datetime(2026, 3, 19, 11, 30),
        disrupted=True,
        endReason="SEVERE_INTERNAL_FAULT",
    )
    db = _FakeDb()

    monkeypatch.setattr(pricing_service, "get_profile_or_404", lambda _db, _user_id: profile)

    result = pricing_service.finalize_trip_pricing(payload, db)

    assert db.committed is True
    assert profile.hours_used_this_cycle == 5.0
    assert result["customerSummary"]["remainingHoursThisCycle"] == 1.0
    assert result["allowanceHoursApplied"] == 1.0
    assert result["refundAmount"] == 10.0


def test_finalize_trip_pricing_only_keeps_uncompensated_allowance_usage(monkeypatch):
    profile = SimpleNamespace(
        user_id="user-1002",
        display_name="Marcus Lee",
        role="CUSTOMER",
        demo_badge="Active commuter",
        plan_name="STANDARD_MONTHLY",
        monthly_included_hours=6.0,
        hours_used_this_cycle=0.0,
        renewal_date=date(2026, 3, 27),
    )
    payload = pricing_service.FinalizeTripPayload(
        bookingId=12,
        tripId=22,
        userId="user-1002",
        startedAt=datetime(2026, 3, 19, 10, 0),
        endedAt=datetime(2026, 3, 19, 13, 0),
        disrupted=True,
        endReason="USER_REPORTED_DISRUPTION",
    )
    db = _FakeDb()

    monkeypatch.setattr(pricing_service, "get_profile_or_404", lambda _db, _user_id: profile)

    result = pricing_service.finalize_trip_pricing(payload, db)

    assert db.committed is True
    assert profile.hours_used_this_cycle == 1.0
    assert result["customerSummary"]["hoursUsedThisCycle"] == 1.0
    assert result["customerSummary"]["remainingHoursThisCycle"] == 5.0
    assert result["allowanceHoursApplied"] == 3.0


def test_mock_ai_detects_severe_damage_keywords():
    result = assess_damage("deep dent and broken panel", ["front.jpg"])
    assert result["severity"] == "SEVERE"
