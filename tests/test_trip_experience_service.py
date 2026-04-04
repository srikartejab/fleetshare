import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient

from fleetshare_common.apps import trip_experience_service


def test_trip_experience_status_filters_records_to_customer_bookings_and_trips(monkeypatch):
    def fake_get_json(url, params=None):
        if url.endswith("/bookings"):
            return [{"bookingId": 101, "userId": "user-1001", "vehicleId": 7}]
        if url.endswith("/trips"):
            return [{"tripId": 201, "bookingId": 101, "userId": "user-1001"}]
        if url.endswith("/vehicles"):
            return [{"vehicleId": 7, "model": "Tesla Model 3"}]
        if url.endswith("/records"):
            return [
                {"recordId": 1, "bookingId": 101, "tripId": None, "vehicleId": 7},
                {"recordId": 2, "bookingId": None, "tripId": 201, "vehicleId": 7},
                {"recordId": 3, "bookingId": 999, "tripId": 999, "vehicleId": 8},
            ]
        if url.endswith("/notifications"):
            return []
        raise AssertionError(f"Unexpected URL {url}")

    monkeypatch.setattr(trip_experience_service, "get_json", fake_get_json)

    with TestClient(trip_experience_service.app) as client:
        response = client.get("/trip-experience/customers/user-1001/status")

    assert response.status_code == 200
    assert response.json() == {
        "bookings": [{"bookingId": 101, "userId": "user-1001", "vehicleId": 7}],
        "trips": [{"tripId": 201, "bookingId": 101, "userId": "user-1001"}],
        "vehicles": [{"vehicleId": 7, "model": "Tesla Model 3"}],
        "records": [
            {"recordId": 1, "bookingId": 101, "tripId": None, "vehicleId": 7},
            {"recordId": 2, "bookingId": None, "tripId": 201, "vehicleId": 7},
        ],
        "notifications": [],
        "liveTripAdvisory": None,
    }


def test_trip_experience_status_builds_live_trip_advisory(monkeypatch):
    def fake_get_json(url, params=None):
        if url.endswith("/bookings"):
            return [{"bookingId": 101, "userId": "user-1001", "vehicleId": 7}]
        if url.endswith("/trips"):
            return [{"tripId": 201, "bookingId": 101, "userId": "user-1001", "vehicleId": 7, "status": "STARTED"}]
        if url.endswith("/vehicles"):
            return [{"vehicleId": 7, "model": "Tesla Model 3"}]
        if url.endswith("/records"):
            return [{"recordId": 1, "bookingId": 101, "tripId": 201, "vehicleId": 7, "severity": "CRITICAL"}]
        if url.endswith("/notifications"):
            return [
                {
                    "notificationId": 88,
                    "userId": "user-1001",
                    "bookingId": 101,
                    "tripId": 201,
                    "subject": "Vehicle issue detected",
                    "message": "Stop the trip and complete the end-trip inspection.",
                    "createdAt": "2026-04-04T10:00:00Z",
                    "payload": {"severity": "CRITICAL"},
                }
            ]
        raise AssertionError(f"Unexpected URL {url}")

    monkeypatch.setattr(trip_experience_service, "get_json", fake_get_json)

    with TestClient(trip_experience_service.app) as client:
        response = client.get("/trip-experience/customers/user-1001/status")

    assert response.status_code == 200
    assert response.json()["liveTripAdvisory"] == {
        "notificationId": 88,
        "createdAt": "2026-04-04T10:00:00Z",
        "bookingId": 101,
        "tripId": 201,
        "vehicleId": 7,
        "vehicleName": "Tesla Model 3",
        "severity": "CRITICAL",
        "subject": "Vehicle issue detected",
        "message": "Stop the trip and complete the end-trip inspection.",
        "requiresImmediateEndTrip": True,
        "endReason": "SEVERE_INTERNAL_FAULT",
    }


def test_pre_trip_inspection_resolves_severe_damage_synchronously(monkeypatch):
    async def fake_post_multipart(_url, _fields, _photos):
        return {
            "recordId": 88,
            "bookingId": 101,
            "vehicleId": 7,
            "assessmentResult": {
                "severity": "SEVERE",
                "confidence": 0.94,
                "detectedDamage": ["major exterior damage"],
            },
            "tripStatus": "BLOCKED",
            "warningMessage": "Severe damage detected. Vehicle blocked.",
            "manualReview": False,
            "reviewState": "EXTERNAL_BLOCKED",
        }

    def fake_get_json(url, params=None):
        if "/booking/" in url:
            return {
                "bookingId": 101,
                "userId": "user-1001",
                "vehicleId": 7,
                "status": "CONFIRMED",
                "pickupLocation": "SMU",
                "startTime": "2026-04-04T23:00:00Z",
                "endTime": "2026-04-05T01:00:00Z",
            }
        if "/vehicles/" in url:
            return {"id": 7, "vehicleId": 7, "model": "Tesla Model 3"}
        raise AssertionError(f"Unexpected GET {url} {params}")

    def fake_post_json(url, payload):
        assert url.endswith("/handle-damage/external/pre-trip-resolution")
        assert payload["bookingId"] == 101
        return {
            "maintenanceTicketId": 33,
            "booking": {
                "bookingId": 101,
                "userId": "user-1001",
                "vehicleId": 7,
                "status": "CANCELLED",
                "pickupLocation": "SMU",
                "startTime": "2026-04-04T23:00:00Z",
                "endTime": "2026-04-05T01:00:00Z",
            },
            "walletSettlement": {
                "cashRefundAmount": 24.0,
                "restoredIncludedHours": 1.0,
                "discountAmount": 8.0,
                "reconciliationStatus": "RESTORED",
            },
        }

    monkeypatch.setattr(trip_experience_service, "_post_multipart", fake_post_multipart)
    monkeypatch.setattr(trip_experience_service, "get_json", fake_get_json)
    monkeypatch.setattr(trip_experience_service, "post_json", fake_post_json)

    with TestClient(trip_experience_service.app) as client:
        response = client.post(
            "/trip-experience/pre-trip-inspection",
            data={"bookingId": "101", "vehicleId": "7", "userId": "user-1001", "notes": "broken bumper"},
        )

    assert response.status_code == 200
    assert response.json()["bookingCancelled"] is True
    assert response.json()["bookingStatus"] == "CANCELLED"
    assert response.json()["resolutionCompleted"] is True
    assert response.json()["maintenanceTicketId"] == 33
    assert response.json()["walletSettlement"] == {
        "cashRefundAmount": 24.0,
        "restoredIncludedHours": 1.0,
        "discountAmount": 8.0,
        "reconciliationStatus": "RESTORED",
    }


def test_pre_trip_cancel_returns_completed_resolution(monkeypatch):
    def fake_post_json(url, payload):
        if url.endswith("/damage-assessment/external/customer-cancel"):
            return {
                "recordId": 77,
                "bookingId": 202,
                "vehicleId": 9,
                "status": "CANCELLATION_REQUESTED",
                "message": "Cancellation requested. FleetShare is finalizing the cancellation and compensation now.",
                "warningMessage": "Moderate damage escalated. The booking will be cancelled and compensation processed.",
                "severity": "MODERATE",
                "reviewState": "EXTERNAL_BLOCKED",
                "detectedDamage": ["possible body damage"],
            }
        if url.endswith("/handle-damage/external/pre-trip-resolution"):
            return {
                "maintenanceTicketId": 44,
                "booking": {
                    "bookingId": 202,
                    "userId": "user-1002",
                    "vehicleId": 9,
                    "status": "CANCELLED",
                    "pickupLocation": "CHANGI",
                    "startTime": "2026-04-04T23:00:00Z",
                    "endTime": "2026-04-05T01:00:00Z",
                },
                "walletSettlement": {
                    "cashRefundAmount": 0.0,
                    "restoredIncludedHours": 2.0,
                    "discountAmount": 8.0,
                    "reconciliationStatus": "RESTORED",
                },
            }
        raise AssertionError(f"Unexpected POST {url} {payload}")

    def fake_get_json(url, params=None):
        if "/booking/" in url:
            return {"bookingId": 202, "status": "CANCELLED"}
        if "/vehicles/" in url:
            return {"id": 9, "vehicleId": 9, "model": "BYD Atto 3"}
        raise AssertionError(f"Unexpected GET {url} {params}")

    monkeypatch.setattr(trip_experience_service, "post_json", fake_post_json)
    monkeypatch.setattr(trip_experience_service, "get_json", fake_get_json)

    with TestClient(trip_experience_service.app) as client:
        response = client.post(
            "/trip-experience/pre-trip/cancel",
            json={"bookingId": 202, "vehicleId": 9, "userId": "user-1002"},
        )

    assert response.status_code == 200
    assert response.json()["bookingCancelled"] is True
    assert response.json()["resolutionCompleted"] is True
    assert response.json()["maintenanceTicketId"] == 44
    assert response.json()["walletSettlement"]["restoredIncludedHours"] == 2.0
