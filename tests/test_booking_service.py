import os
from datetime import datetime, timezone
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from fleetshare_common.apps import booking_service
from fleetshare_common.contracts import BookingStatus
from fleetshare_common.timeutils import as_utc_naive


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


def test_seed_demo_bookings_is_idempotent_and_within_lookahead(monkeypatch):
    fixed_now = datetime(2026, 4, 6, 9, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(booking_service, "utcnow", lambda: fixed_now)
    booking_service.initialize_schema_with_retry(booking_service.Base.metadata)

    with booking_service.SessionLocal() as db:
        db.query(booking_service.Booking).delete()
        db.query(booking_service.VehicleReservationLock).delete()
        db.commit()

    booking_service.seed_demo_bookings()
    booking_service.seed_demo_bookings()

    with booking_service.SessionLocal() as db:
        bookings = (
            db.query(booking_service.Booking)
            .filter(booking_service.Booking.status == BookingStatus.CONFIRMED.value)
            .order_by(booking_service.Booking.id.asc())
            .all()
        )

    assert len(bookings) == 3
    markers = [(booking.metadata_json or {}).get("seedMarker") for booking in bookings]
    assert len(set(markers)) == 3
    assert all((booking.metadata_json or {}).get("seedCategory") == booking_service.DEMO_FUTURE_BOOKING_SEED_CATEGORY for booking in bookings)
    assert all(booking.cancellation_reason is None for booking in bookings)
    assert all(booking.start_time > as_utc_naive(fixed_now) for booking in bookings)
    assert all((booking.start_time - as_utc_naive(fixed_now)).total_seconds() <= 336 * 60 * 60 for booking in bookings)
