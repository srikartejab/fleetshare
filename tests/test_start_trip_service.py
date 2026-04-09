import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient

from fleetshare_common.apps import start_trip_service


def test_start_trip_rejects_when_booking_has_not_started(monkeypatch):
    def fake_get_json(url, params=None):
        if "/booking/" in url:
            return {
                "bookingId": 101,
                "userId": "user-1001",
                "vehicleId": 7,
                "status": "CONFIRMED",
                "startTime": "2099-04-10T12:00:00Z",
                "endTime": "2099-04-10T14:00:00Z",
                "refundPendingOnRenewal": False,
                "pricingSnapshot": {},
            }
        if url.endswith("/records"):
            return [{"recordId": 1, "reviewState": "EXTERNAL_ASSESSED", "severity": "MINOR"}]
        raise AssertionError(f"Unexpected GET {url}")

    monkeypatch.setattr(start_trip_service, "get_json", fake_get_json)

    with TestClient(start_trip_service.app) as client:
        response = client.post(
            "/trips/start",
            json={"bookingId": 101, "vehicleId": 7, "userId": "user-1001", "notes": ""},
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "Trip cannot start before the booked start time."


def test_start_trip_starts_when_booking_window_is_open(monkeypatch):
    def fake_get_json(url, params=None):
        if "/booking/" in url:
            return {
                "bookingId": 101,
                "userId": "user-1001",
                "vehicleId": 7,
                "status": "CONFIRMED",
                "startTime": "2020-04-10T10:00:00Z",
                "endTime": "2099-04-10T14:00:00Z",
                "refundPendingOnRenewal": False,
                "pricingSnapshot": {},
            }
        if url.endswith("/records"):
            return [{"recordId": 1, "reviewState": "EXTERNAL_ASSESSED", "severity": "MINOR"}]
        raise AssertionError(f"Unexpected GET {url}")

    monkeypatch.setattr(start_trip_service, "get_json", fake_get_json)
    monkeypatch.setattr(start_trip_service, "post_json", lambda url, payload: {"blocked": False} if "internal-damage/validate" in url else {"tripId": 333})
    monkeypatch.setattr(start_trip_service, "patch_json", lambda url, payload: {"status": "IN_PROGRESS"})
    monkeypatch.setattr(start_trip_service, "unlock_vehicle", lambda vehicle_id, booking_ref, user_id: {"success": True, "status": "IN_USE", "message": "Vehicle unlocked"})

    with TestClient(start_trip_service.app) as client:
        response = client.post(
            "/trips/start",
            json={"bookingId": 101, "vehicleId": 7, "userId": "user-1001", "notes": ""},
        )

    assert response.status_code == 200
    assert response.json()["tripId"] == 333
