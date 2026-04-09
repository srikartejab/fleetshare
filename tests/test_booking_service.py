import os
from datetime import datetime
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

import pytest

from fleetshare_common.apps import booking_service


class _FakeQuery:
    def __init__(self, items=None):
        self.items = items or []

    def filter(self, *_args, **_kwargs):
        return self

    def all(self):
        return self.items


class _FakeDb:
    def __init__(self, bookings=None):
        self.bookings = {booking.id: booking for booking in bookings or []}
        self.committed = False

    def query(self, _model):
        return _FakeQuery(list(self.bookings.values()))

    def get(self, _model, booking_id):
        return self.bookings.get(booking_id)

    def commit(self):
        self.committed = True


def test_reconciliation_pending_filters_by_booking_id_and_sorts():
    first = SimpleNamespace(
        id=8,
        user_id="user-1001",
        vehicle_id=3,
        pickup_location="SMU",
        start_time=datetime(2026, 4, 2, 22, 0),
        end_time=datetime(2026, 4, 3, 1, 0),
        status="COMPLETED",
        displayed_price=20.0,
        final_price=20.0,
        cross_cycle_booking=True,
        refund_pending_on_renewal=True,
        reconciliation_status="PENDING",
        trip_id=88,
        booking_note=None,
        cancellation_reason=None,
        metadata_json={"nextBillingCycleId": "2026-04"},
    )
    second = SimpleNamespace(
        id=4,
        user_id="user-1001",
        vehicle_id=2,
        pickup_location="SMU",
        start_time=datetime(2026, 4, 1, 22, 0),
        end_time=datetime(2026, 4, 2, 1, 0),
        status="COMPLETED",
        displayed_price=15.0,
        final_price=15.0,
        cross_cycle_booking=True,
        refund_pending_on_renewal=True,
        reconciliation_status="PENDING",
        trip_id=44,
        booking_note=None,
        cancellation_reason=None,
        metadata_json={"nextBillingCycleId": "2026-04"},
    )

    result = booking_service.reconciliation_pending(
        "user-1001",
        billingCycleId="2026-04",
        bookingId=4,
        db=_FakeDb([first, second]),
    )

    assert result["bookingIds"] == [4]
    assert result["tripIds"] == [44]
    assert [item["bookingId"] for item in result["reconciliationCandidates"]] == [4]


def test_patch_reconciliation_complete_updates_booking_atomically():
    booking = SimpleNamespace(
        id=11,
        final_price=32.0,
        refund_pending_on_renewal=True,
        reconciliation_status="PENDING",
        status="COMPLETED",
    )
    db = _FakeDb([booking])

    result = booking_service.patch_reconciliation_complete(
        11,
        booking_service.ReconciliationCompletePayload(finalPrice=12.5),
        db,
    )

    assert db.committed is True
    assert booking.final_price == 12.5
    assert booking.refund_pending_on_renewal is False
    assert booking.reconciliation_status == "COMPLETED"
    assert booking.status == "RECONCILED"
    assert result["idempotent"] is False


def test_patch_reconciliation_complete_is_idempotent():
    booking = SimpleNamespace(
        id=11,
        final_price=12.5,
        refund_pending_on_renewal=False,
        reconciliation_status="COMPLETED",
        status="RECONCILED",
    )
    db = _FakeDb([booking])

    result = booking_service.patch_reconciliation_complete(
        11,
        booking_service.ReconciliationCompletePayload(finalPrice=12.5),
        db,
    )

    assert db.committed is False
    assert result["idempotent"] is True
    assert result["status"] == "RECONCILED"


def test_validate_booking_window_rejects_start_time_after_end_time():
    with pytest.raises(booking_service.HTTPException) as exc_info:
        booking_service.validate_booking_window(
            datetime(2026, 4, 9, 12, 0),
            datetime(2026, 4, 9, 11, 0),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "endTime must be later than startTime"
