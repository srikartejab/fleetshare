import os
from datetime import datetime
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from fleetshare_common.apps import trip_service


class _FakeDb:
    def __init__(self, trip):
        self.trip = trip

    def get(self, _model, trip_id):
        return self.trip if self.trip and self.trip.id == trip_id else None


def test_get_trip_includes_post_midnight_usage_for_ended_trip():
    trip = SimpleNamespace(
        id=21,
        booking_id=11,
        vehicle_id=5,
        user_id="user-1001",
        status="ENDED",
        started_at=datetime(2026, 4, 1, 15, 0),
        ended_at=datetime(2026, 4, 1, 17, 30),
        end_reason="USER_COMPLETED",
        disruption_reason=None,
        subscription_snapshot={},
        duration_hours=2.5,
    )

    result = trip_service.get_trip(21, _FakeDb(trip))

    assert result["actualPostMidnightHours"] == 1.5
    assert result["tripUsageSummary"] == "1.5 hours after midnight"


def test_get_trip_leaves_post_midnight_usage_empty_for_active_trip():
    trip = SimpleNamespace(
        id=22,
        booking_id=12,
        vehicle_id=6,
        user_id="user-1002",
        status="STARTED",
        started_at=datetime(2026, 4, 1, 10, 0),
        ended_at=None,
        end_reason=None,
        disruption_reason=None,
        subscription_snapshot={},
        duration_hours=0.0,
    )

    result = trip_service.get_trip(22, _FakeDb(trip))

    assert result["actualPostMidnightHours"] is None
    assert result["tripUsageSummary"] is None
