from __future__ import annotations

from fleetshare_common.apps import end_trip_service


def test_end_trip_service_separates_renewal_reconciliation_from_refund_queue(monkeypatch):
    booking_updates: list[tuple[str, dict]] = []

    def fake_get_json(url: str, params: dict | None = None):
        if "/booking/" in url:
            return {
                "bookingId": 101,
                "endTime": "2026-04-02T02:10:00Z",
                "pricingSnapshot": {"renewalDate": "2026-04-01"},
            }
        return {
            "tripId": 201,
            "status": "STARTED",
            "startedAt": "2026-04-01T15:10:00Z",
            "endedAt": None,
        }

    def fake_patch_json(url: str, payload: dict):
        booking_updates.append((url, payload))
        if "/trips/" in url:
            return {"status": "ENDED"}
        return {"ok": True}

    def fake_post_json(url: str, payload: dict):
        return {
            "finalPrice": 43.33,
            "renewalPending": True,
            "refundAmount": 0.0,
            "discountAmount": 0.0,
            "allowanceHoursApplied": 1.0,
            "customerSummary": {"userId": "user-1001"},
        }

    monkeypatch.setattr(end_trip_service, "get_json", fake_get_json)
    monkeypatch.setattr(end_trip_service, "patch_json", fake_patch_json)
    monkeypatch.setattr(end_trip_service, "post_json", fake_post_json)
    monkeypatch.setattr(end_trip_service, "lock_vehicle", lambda vehicle_id, booking_ref, user_id: {"success": True})
    monkeypatch.setattr(end_trip_service, "publish_event", lambda *_args, **_kwargs: None)

    payload = end_trip_service.EndTripPayload(
        tripId=201,
        bookingId=101,
        vehicleId=9,
        userId="user-1001",
        endReason="USER_COMPLETED",
    )

    result = end_trip_service.process_end_trip(payload)

    assert result["refundPending"] is False
    assert result["renewalReconciliationPending"] is True
    assert any(
        url.endswith("/booking/101/reconciliation-status")
        and update["refund_pending_on_renewal"] is True
        and update["reconciliationStatus"] == "PENDING"
        for url, update in booking_updates
    )


def test_end_trip_service_marks_cash_refund_as_pending_when_adjustment_is_queued(monkeypatch):
    monkeypatch.setattr(
        end_trip_service,
        "get_json",
        lambda url, params=None: {
            "bookingId": 102,
            "endTime": "2026-04-01T12:00:00Z",
            "pricingSnapshot": {},
        }
        if "/booking/" in url
        else {
            "tripId": 202,
            "status": "ENDED",
            "startedAt": "2026-04-01T10:00:00Z",
            "endedAt": "2026-04-01T12:00:00Z",
        },
    )
    monkeypatch.setattr(end_trip_service, "patch_json", lambda url, payload: {"ok": True})
    monkeypatch.setattr(
        end_trip_service,
        "post_json",
        lambda url, payload: {
            "finalPrice": 0.0,
            "renewalPending": False,
            "refundAmount": 30.0,
            "discountAmount": 8.0,
            "allowanceHoursApplied": 1.5,
            "customerSummary": {"userId": "user-1002"},
        },
    )
    monkeypatch.setattr(end_trip_service, "lock_vehicle", lambda vehicle_id, booking_ref, user_id: {"success": True})
    monkeypatch.setattr(end_trip_service, "publish_event", lambda *_args, **_kwargs: None)

    payload = end_trip_service.EndTripPayload(
        tripId=202,
        bookingId=102,
        vehicleId=10,
        userId="user-1002",
        endReason="SEVERE_INTERNAL_FAULT",
    )

    result = end_trip_service.process_end_trip(payload)

    assert result["refundPending"] is True
    assert result["renewalReconciliationPending"] is False
