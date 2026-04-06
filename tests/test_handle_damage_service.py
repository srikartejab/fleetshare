import os

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

TestClient = pytest.importorskip("fastapi.testclient").TestClient

from fleetshare_common.apps import handle_damage_service


def test_sync_pre_trip_resolution_splits_refund_and_credit(monkeypatch):
    published_events = []
    maintenance_payloads = []

    def fake_post_json(url, payload):
        if url.endswith("/maintenance/tickets"):
            maintenance_payloads.append(payload)
            assert payload["recordId"] == 1
            assert payload["bookingId"] == 101
            assert payload["tripId"] is None
            assert payload["openedByEventType"] == "SEVERE_EXTERNAL_DAMAGE"
            assert payload["sourceEventId"]
            return {"ticketId": 91, "vehicleId": payload["vehicleId"]}
        if url.endswith("/pricing/pre-trip-cancellation-compensation"):
            return {
                "settlements": [
                    {
                        "bookingId": 101,
                        "userId": "user-1001",
                        "cashRefundAmount": 24.0,
                        "restoredIncludedHours": 1.0,
                        "discountAmount": 8.0,
                        "reconciliationStatus": "RESTORED",
                        "ledgerCreated": True,
                    }
                ],
                "ledgerEntries": [],
                "affectedUsers": ["user-1001"],
                "totalRefundAmount": 24.0,
                "totalDiscountAmount": 8.0,
                "totalRestoredIncludedHours": 1.0,
            }
        raise AssertionError(f"Unexpected POST {url} {payload}")

    def fake_put_json(url, payload):
        assert url.endswith("/bookings/cancel-affected")
        maintenance_start = handle_damage_service.datetime.fromisoformat(payload["maintenanceStart"].replace("Z", "+00:00"))
        maintenance_end = handle_damage_service.datetime.fromisoformat(payload["maintenanceEnd"].replace("Z", "+00:00"))
        assert (maintenance_end - maintenance_start).total_seconds() == 336 * 60 * 60
        return {
            "affectedBookings": [
                {
                    "bookingId": 101,
                    "userId": "user-1001",
                    "vehicleId": 7,
                    "status": "CANCELLED",
                    "displayedPrice": 24.0,
                    "finalPrice": 24.0,
                    "tripId": None,
                    "pickupLocation": "SMU",
                    "startTime": "2026-04-04T23:00:00Z",
                    "endTime": "2026-04-05T01:00:00Z",
                    "pricingSnapshot": {"includedHoursApplied": 1.0, "provisionalPostMidnightHours": 0.0},
                }
            ],
            "cancelledCount": 1,
        }

    def fake_get_json(url, params=None):
        if url.endswith("/payments"):
            return [{"bookingId": 101, "amount": 24.0, "status": "SUCCESS", "reason": "BOOKING_PROVISIONAL_CHARGE"}]
        if "/booking/" in url:
            return {"bookingId": 101, "status": "CANCELLED", "userId": "user-1001", "vehicleId": 7}
        raise AssertionError(f"Unexpected GET {url} {params}")

    monkeypatch.setattr(handle_damage_service, "post_json", fake_post_json)
    monkeypatch.setattr(handle_damage_service, "put_json", fake_put_json)
    monkeypatch.setattr(handle_damage_service, "get_json", fake_get_json)
    monkeypatch.setattr(
        handle_damage_service,
        "publish_event",
        lambda event_type, payload, *, event_id=None: published_events.append((event_type, payload, event_id)),
    )
    monkeypatch.setattr(handle_damage_service, "utcnow", lambda: handle_damage_service.datetime(2026, 4, 4, 10, 0))
    monkeypatch.setattr(handle_damage_service.get_settings(), "damage_booking_lookahead_hours", 336, raising=False)

    with TestClient(handle_damage_service.app) as client:
        response = client.post(
            "/handle-damage/external/pre-trip-resolution",
            json={
                "recordId": 1,
                "bookingId": 101,
                "vehicleId": 7,
                "userId": "user-1001",
                "severity": "SEVERE",
                "damageType": "major exterior damage",
                "recommendedAction": "Severe damage detected. Vehicle blocked.",
                "reason": "SEVERE_EXTERNAL_DAMAGE",
                "incidentAt": "2026-04-04T10:15:00Z",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["maintenanceTicketId"] == 91
    assert payload["booking"]["status"] == "CANCELLED"
    assert payload["walletSettlement"]["cashRefundAmount"] == 24.0
    assert payload["walletSettlement"]["restoredIncludedHours"] == 1.0
    assert payload["primaryBookingCancelled"] is True
    assert payload["futureBookingsCancelledCount"] == 0
    assert payload["cancelledBookingIds"] == [101]
    assert maintenance_payloads[0]["sourceEventId"] == handle_damage_service.stable_event_id(
        "handle-damage", "SEVERE_EXTERNAL_DAMAGE", 1, 101, None, 7
    )
    assert (
        "payment.refund_required",
        {"bookingId": 101, "tripId": None, "userId": "user-1001", "refundAmount": 24.0, "reason": "SEVERE_EXTERNAL_DAMAGE"},
        handle_damage_service.stable_event_id(
            "handle-damage", "refund", maintenance_payloads[0]["sourceEventId"], 101, "SEVERE_EXTERNAL_DAMAGE"
        ),
    ) in published_events
    assert (
        "payment.adjustment_required",
        {"bookingId": 101, "tripId": None, "userId": "user-1001", "discountAmount": 8.0, "reason": "SEVERE_EXTERNAL_DAMAGE"},
        handle_damage_service.stable_event_id(
            "handle-damage", "adjustment", maintenance_payloads[0]["sourceEventId"], 101, "SEVERE_EXTERNAL_DAMAGE"
        ),
    ) in published_events
    ops_event = next(payload for event_type, payload, _event_id in published_events if event_type == "booking.disruption_notification" and payload["userIds"] == ["ops-maint-1"])
    assert ops_event["primaryBookingCancelled"] is True
    assert ops_event["futureBookingsCancelledCount"] == 0
    assert ops_event["cancelledBookingIds"] == [101]


def test_sync_pre_trip_resolution_counts_future_bookings_separately(monkeypatch):
    published_events = []

    def fake_post_json(url, payload):
        if url.endswith("/maintenance/tickets"):
            return {"ticketId": 92, "vehicleId": payload["vehicleId"]}
        if url.endswith("/pricing/pre-trip-cancellation-compensation"):
            return {
                "settlements": [
                    {
                        "bookingId": 101,
                        "userId": "user-1001",
                        "cashRefundAmount": 24.0,
                        "restoredIncludedHours": 0.0,
                        "discountAmount": 8.0,
                        "reconciliationStatus": "RESTORED",
                    },
                    {
                        "bookingId": 202,
                        "userId": "user-1002",
                        "cashRefundAmount": 12.0,
                        "restoredIncludedHours": 0.0,
                        "discountAmount": 4.0,
                        "reconciliationStatus": "RESTORED",
                    },
                ],
                "ledgerEntries": [],
                "affectedUsers": ["user-1001", "user-1002"],
                "totalRefundAmount": 36.0,
                "totalDiscountAmount": 12.0,
                "totalRestoredIncludedHours": 0.0,
            }
        raise AssertionError(f"Unexpected POST {url} {payload}")

    def fake_put_json(url, payload):
        assert url.endswith("/bookings/cancel-affected")
        return {
            "affectedBookings": [
                {
                    "bookingId": 101,
                    "userId": "user-1001",
                    "vehicleId": 7,
                    "status": "CANCELLED",
                    "displayedPrice": 24.0,
                    "finalPrice": 24.0,
                    "tripId": None,
                    "pickupLocation": "SMU",
                    "startTime": "2026-04-04T23:00:00Z",
                    "endTime": "2026-04-05T01:00:00Z",
                    "pricingSnapshot": {},
                },
                {
                    "bookingId": 202,
                    "userId": "user-1002",
                    "vehicleId": 7,
                    "status": "CANCELLED",
                    "displayedPrice": 12.0,
                    "finalPrice": 12.0,
                    "tripId": None,
                    "pickupLocation": "SMU",
                    "startTime": "2026-04-05T03:00:00Z",
                    "endTime": "2026-04-05T04:00:00Z",
                    "pricingSnapshot": {},
                },
            ],
            "cancelledCount": 2,
        }

    def fake_get_json(url, params=None):
        if url.endswith("/payments"):
            return [
                {"bookingId": 101, "amount": 24.0, "status": "SUCCESS", "reason": "BOOKING_PROVISIONAL_CHARGE"},
                {"bookingId": 202, "amount": 12.0, "status": "SUCCESS", "reason": "BOOKING_PROVISIONAL_CHARGE"},
            ]
        if "/booking/" in url:
            return {"bookingId": 101, "status": "CANCELLED", "userId": "user-1001", "vehicleId": 7}
        raise AssertionError(f"Unexpected GET {url} {params}")

    monkeypatch.setattr(handle_damage_service, "post_json", fake_post_json)
    monkeypatch.setattr(handle_damage_service, "put_json", fake_put_json)
    monkeypatch.setattr(handle_damage_service, "get_json", fake_get_json)
    monkeypatch.setattr(
        handle_damage_service,
        "publish_event",
        lambda event_type, payload, *, event_id=None: published_events.append((event_type, payload, event_id)),
    )

    result = handle_damage_service.resolve_damage_recovery(
        {
            "recordId": 1,
            "bookingId": 101,
            "vehicleId": 7,
            "userId": "user-1001",
            "severity": "SEVERE",
            "damageType": "major exterior damage",
            "recommendedAction": "Severe damage detected. Vehicle blocked.",
            "incidentAt": "2026-04-04T10:15:00Z",
        },
        reason="SEVERE_EXTERNAL_DAMAGE",
    )

    assert result["cancelledCount"] == 2
    assert result["primaryBookingCancelled"] is True
    assert result["futureBookingsCancelledCount"] == 1
    assert result["cancelledBookingIds"] == [101, 202]
    ops_event = next(payload for event_type, payload, _event_id in published_events if event_type == "booking.disruption_notification" and payload["userIds"] == ["ops-maint-1"])
    assert ops_event["primaryBookingCancelled"] is True
    assert ops_event["futureBookingsCancelledCount"] == 1
    assert ops_event["cancelledBookingIds"] == [101, 202]
