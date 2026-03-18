from datetime import datetime

from fleetshare_common.ai import assess_damage
from fleetshare_common.pricing import booking_quote, rerate_after_renewal, trip_adjustment


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


def test_mock_ai_detects_severe_damage_keywords():
    result = assess_damage("deep dent and broken panel", ["front.jpg"])
    assert result["severity"] == "SEVERE"
