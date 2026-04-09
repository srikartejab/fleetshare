import os
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from fleetshare_common.apps import renewal_reconciliation_service


def _settings():
    return SimpleNamespace(
        booking_service_url="http://booking-service:8000",
        trip_service_url="http://trip-service:8000",
        pricing_service_url="http://pricing-service:8000",
    )


def test_handle_renewal_event_processes_candidates_without_redundant_booking_or_usage_reads(monkeypatch):
    get_calls = []
    post_calls = []
    patch_calls = []
    published = []

    def fake_get_json(url, params=None):
        get_calls.append((url, params))
        if url.endswith("/bookings/reconciliation-pending"):
            assert params == {"userId": "user-1001", "billingCycleId": "2026-05"}
            return {
                "reconciliationCandidates": [
                    {
                        "bookingId": 11,
                        "userId": "user-1001",
                        "tripId": 21,
                        "refundPendingOnRenewal": True,
                        "startTime": "2026-04-01T23:00:00Z",
                    }
                ]
            }
        if url.endswith("/trips/21"):
            return {
                "tripId": 21,
                "status": "ENDED",
                "endedAt": "2026-04-02T02:00:00Z",
                "actualPostMidnightHours": 2.0,
            }
        raise AssertionError(f"Unexpected GET {url} {params}")

    def fake_post_json(url, payload):
        post_calls.append((url, payload))
        if url.endswith("/pricing/customers/user-1001/renewal"):
            return {"billingCycleId": "2026-05", "idempotent": False}
        if url.endswith("/pricing/re-rate-renewed-booking"):
            return {"finalPrice": 0.0, "refundAmount": 24.0, "eligibleIncludedHours": 1.0}
        raise AssertionError(f"Unexpected POST {url} {payload}")

    monkeypatch.setattr(renewal_reconciliation_service, "get_settings", _settings)
    monkeypatch.setattr(renewal_reconciliation_service, "get_json", fake_get_json)
    monkeypatch.setattr(renewal_reconciliation_service, "post_json", fake_post_json)
    monkeypatch.setattr(renewal_reconciliation_service, "patch_json", lambda url, payload: patch_calls.append((url, payload)))
    monkeypatch.setattr(
        renewal_reconciliation_service,
        "publish_event",
        lambda event_type, payload, *, event_id=None: published.append((event_type, payload, event_id)),
    )

    renewal_reconciliation_service.handle_renewal_event(
        {
            "event_id": "evt-1",
            "event_type": "subscription.renewed",
            "payload": {"userId": "user-1001", "newBillingCycleId": "2026-05"},
        }
    )

    assert not any("/booking/11" in url for url, _params in get_calls)
    assert not any("/post-midnight-usage" in url for url, _params in get_calls)
    assert patch_calls == [
        (
            "http://booking-service:8000/booking/11/reconciliation-state",
            {"finalPrice": 0.0, "refund_pending_on_renewal": True, "reconciliationStatus": "REFUND_PENDING"},
        )
    ]
    assert (
        "payment.refund_required",
        {
            "bookingId": 11,
            "tripId": 21,
            "userId": "user-1001",
            "refundAmount": 24.0,
            "reason": "RENEWAL_RECONCILIATION",
            "billingCycleId": "2026-05",
            "eligibleIncludedHours": 1.0,
            "finalPrice": 0.0,
            "sourceEventId": renewal_reconciliation_service._reconciliation_event_id(
                "refund", booking_id=11, trip_id=21, billing_cycle_id="2026-05"
            ),
        },
        renewal_reconciliation_service._reconciliation_event_id(
            "refund", booking_id=11, trip_id=21, billing_cycle_id="2026-05"
        ),
    ) in published
    assert not any(event_type == "billing.refund_adjustment_completed" for event_type, _payload, _event_id in published)


def test_handle_trip_ended_event_targets_only_the_ended_booking(monkeypatch):
    captured = []

    def fake_get_json(url, params=None):
        if url.endswith("/booking/33"):
            return {
                "bookingId": 33,
                "refundPendingOnRenewal": True,
                "pricingSnapshot": {"nextBillingCycleId": "2026-05"},
            }
        if url.endswith("/pricing/customers/user-1001/summary"):
            return {"subscriptionEndDate": "2026-05-01"}
        raise AssertionError(f"Unexpected GET {url} {params}")

    monkeypatch.setattr(renewal_reconciliation_service, "get_settings", _settings)
    monkeypatch.setattr(renewal_reconciliation_service, "get_json", fake_get_json)
    monkeypatch.setattr(
        renewal_reconciliation_service,
        "process_pending_reconciliations",
        lambda settings, user_id, active_billing_cycle_id, booking_id=None: captured.append(
            (user_id, active_billing_cycle_id, booking_id)
        ),
    )

    renewal_reconciliation_service.handle_trip_ended_event(
        {
            "event_id": "evt-trip",
            "event_type": "trip.ended",
            "payload": {"bookingId": 33, "userId": "user-1001"},
        }
    )

    assert captured == [("user-1001", "2026-05", 33)]


def test_process_pending_reconciliations_skips_ineligible_candidates(monkeypatch):
    rerates = []
    completions = []

    def fake_get_json(url, params=None):
        if url.endswith("/bookings/reconciliation-pending"):
            return {
                "reconciliationCandidates": [
                    {"bookingId": 1, "tripId": 10, "refundPendingOnRenewal": False, "startTime": "2026-04-01T23:00:00Z"},
                    {"bookingId": 2, "tripId": None, "refundPendingOnRenewal": True, "startTime": "2026-04-01T23:05:00Z"},
                    {"bookingId": 3, "tripId": 30, "refundPendingOnRenewal": True, "startTime": "2026-04-01T23:10:00Z"},
                    {"bookingId": 4, "tripId": 40, "refundPendingOnRenewal": True, "startTime": "2026-04-01T23:15:00Z"},
                ]
            }
        if url.endswith("/trips/30"):
            return {"tripId": 30, "status": "STARTED", "endedAt": None, "actualPostMidnightHours": None}
        if url.endswith("/trips/40"):
            return {"tripId": 40, "status": "ENDED", "endedAt": "2026-04-02T02:00:00Z", "actualPostMidnightHours": 2.0}
        raise AssertionError(f"Unexpected GET {url} {params}")

    def fake_post_json(url, payload):
        assert url.endswith("/pricing/re-rate-renewed-booking")
        rerates.append(payload)
        return {"finalPrice": 8.0, "refundAmount": 0.0, "eligibleIncludedHours": 0.0}

    monkeypatch.setattr(renewal_reconciliation_service, "get_json", fake_get_json)
    monkeypatch.setattr(renewal_reconciliation_service, "post_json", fake_post_json)
    monkeypatch.setattr(renewal_reconciliation_service, "patch_json", lambda url, payload: completions.append((url, payload)))
    monkeypatch.setattr(renewal_reconciliation_service, "publish_event", lambda *_args, **_kwargs: None)

    processed = renewal_reconciliation_service.process_pending_reconciliations(_settings(), "user-1001", "2026-05")

    assert processed == 1
    assert rerates == [
        {
            "bookingId": 4,
            "tripId": 40,
            "userId": "user-1001",
            "newBillingCycleId": "2026-05",
            "actualPostMidnightHours": 2.0,
        }
    ]
    assert completions == [
        (
            "http://booking-service:8000/booking/4/reconciliation-state",
            {"finalPrice": 8.0, "refund_pending_on_renewal": False, "reconciliationStatus": "COMPLETED"},
        )
    ]


def test_handle_refund_completed_event_marks_reconciliation_complete_and_publishes_notification(monkeypatch):
    patch_calls = []
    published = []

    monkeypatch.setattr(renewal_reconciliation_service, "get_settings", _settings)
    monkeypatch.setattr(renewal_reconciliation_service, "patch_json", lambda url, payload: patch_calls.append((url, payload)))
    monkeypatch.setattr(
        renewal_reconciliation_service,
        "publish_event",
        lambda event_type, payload, *, event_id=None: published.append((event_type, payload, event_id)),
    )

    renewal_reconciliation_service.handle_refund_completed_event(
        {
            "event_id": "evt-refund-completed",
            "event_type": "payment.refund_completed",
            "payload": {
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
        }
    )

    assert patch_calls == [
        (
            "http://booking-service:8000/booking/11/reconciliation-state",
            {"finalPrice": 0.0, "refund_pending_on_renewal": False, "reconciliationStatus": "COMPLETED"},
        ),
        (
            "http://pricing-service:8000/pricing/bookings/11/reconciliation-state",
            {"reconciliationStatus": "COMPLETED"},
        ),
    ]
    assert published == [
        (
            "billing.refund_adjustment_completed",
            {
                "bookingId": 11,
                "tripId": 21,
                "userId": "user-1001",
                "subject": "Billing adjustment completed",
                "message": "Booking 11 was re-rated after renewal. 1.0h moved into the new cycle allowance; SGD 24.00 refunded.",
            },
            renewal_reconciliation_service._reconciliation_event_id(
                "notification", booking_id=11, trip_id=21, billing_cycle_id="2026-05"
            ),
        )
    ]
