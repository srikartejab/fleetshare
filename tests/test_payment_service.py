import os
from datetime import datetime
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from fleetshare_common.apps import payment_service


class _FakeQuery:
    def __init__(self, items=None):
        self.items = items or []

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.items[0] if self.items else None

    def all(self):
        return self.items


class _FakeDb:
    def __init__(self, items=None):
        self.items = items or []

    def query(self, _model):
        return _FakeQuery(self.items)


def test_list_payments_returns_utc_iso_timestamps():
    payment = SimpleNamespace(
        id=5,
        booking_id=11,
        trip_id=21,
        user_id="user-1001",
        amount=51.33,
        reason="SEVERE_INTERNAL_FAULT",
        status="ADJUSTED",
        created_at=datetime(2026, 4, 1, 10, 19),
    )

    result = payment_service.list_payments(db=_FakeDb([payment]))

    assert result == [
        {
            "paymentId": 5,
            "bookingId": 11,
            "tripId": 21,
            "userId": "user-1001",
            "amount": 51.33,
            "reason": "SEVERE_INTERNAL_FAULT",
            "status": "ADJUSTED",
            "createdAt": "2026-04-01T10:19:00Z",
        }
    ]


def test_handle_payment_event_records_refund_amount_only(monkeypatch):
    added = []
    published = []

    class _FakeSessionScope:
        def __enter__(self):
            class _Session:
                def query(self, _model):
                    return _FakeQuery([])

                def add(self, item):
                    added.append(item)

            return _Session()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(payment_service, "session_scope", lambda: _FakeSessionScope())
    monkeypatch.setattr(
        payment_service,
        "publish_event",
        lambda event_type, payload, *, event_id=None: published.append((event_type, payload, event_id)),
    )

    payment_service.handle_payment_event(
        {
            "event_id": "evt-refund",
            "event_type": "payment.refund_required",
            "payload": {"bookingId": 11, "userId": "user-1001", "refundAmount": 24.0, "discountAmount": 8.0, "reason": "SEVERE_EXTERNAL_DAMAGE"},
        }
    )

    assert len(added) == 1
    assert added[0].amount == 24.0
    assert added[0].status == "REFUNDED"
    assert published == [
        (
            "payment.refund_completed",
            {
                "bookingId": 11,
                "tripId": None,
                "userId": "user-1001",
                "refundAmount": 24.0,
                "reason": "SEVERE_EXTERNAL_DAMAGE",
                "sourceEventId": "evt-refund",
                "billingCycleId": None,
                "eligibleIncludedHours": 0.0,
                "finalPrice": 0.0,
            },
            payment_service.stable_event_id("payment", "refund-completed", "evt-refund"),
        )
    ]


def test_handle_payment_event_records_adjustment_amount_only(monkeypatch):
    added = []
    published = []

    class _FakeSessionScope:
        def __enter__(self):
            class _Session:
                def query(self, _model):
                    return _FakeQuery([])

                def add(self, item):
                    added.append(item)

            return _Session()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(payment_service, "session_scope", lambda: _FakeSessionScope())
    monkeypatch.setattr(
        payment_service,
        "publish_event",
        lambda event_type, payload, *, event_id=None: published.append((event_type, payload, event_id)),
    )

    payment_service.handle_payment_event(
        {
            "event_id": "evt-adjust",
            "event_type": "payment.adjustment_required",
            "payload": {"bookingId": 11, "userId": "user-1001", "refundAmount": 24.0, "discountAmount": 8.0, "reason": "SEVERE_EXTERNAL_DAMAGE"},
        }
    )

    assert len(added) == 1
    assert added[0].amount == 8.0
    assert added[0].status == "ADJUSTED"
    assert published == []


def test_handle_payment_event_reemits_refund_completed_when_refund_record_already_exists(monkeypatch):
    published = []
    existing = SimpleNamespace(event_id="evt-refund")

    class _FakeSessionScope:
        def __enter__(self):
            class _Session:
                def query(self, _model):
                    return _FakeQuery([existing])

                def add(self, _item):
                    raise AssertionError("Should not insert a duplicate refund record")

            return _Session()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(payment_service, "session_scope", lambda: _FakeSessionScope())
    monkeypatch.setattr(
        payment_service,
        "publish_event",
        lambda event_type, payload, *, event_id=None: published.append((event_type, payload, event_id)),
    )

    payment_service.handle_payment_event(
        {
            "event_id": "evt-refund",
            "event_type": "payment.refund_required",
            "payload": {
                "bookingId": 11,
                "tripId": 21,
                "userId": "user-1001",
                "refundAmount": 24.0,
                "reason": "RENEWAL_RECONCILIATION",
                "billingCycleId": "2026-05",
                "eligibleIncludedHours": 1.0,
                "finalPrice": 0.0,
            },
        }
    )

    assert published == [
        (
            "payment.refund_completed",
            {
                "bookingId": 11,
                "tripId": 21,
                "userId": "user-1001",
                "refundAmount": 24.0,
                "reason": "RENEWAL_RECONCILIATION",
                "sourceEventId": "evt-refund",
                "billingCycleId": "2026-05",
                "eligibleIncludedHours": 1.0,
                "finalPrice": 0.0,
            },
            payment_service.stable_event_id("payment", "refund-completed", "evt-refund"),
        )
    ]
