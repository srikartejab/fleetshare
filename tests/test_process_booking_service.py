import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient

from fleetshare_common.apps import process_booking_service


def test_process_booking_home_and_wallet_routes_aggregate_customer_views(monkeypatch):
    def fake_get_json(url, params=None):
        if url.endswith("/pricing/customers/user-1001/summary"):
            return {"userId": "user-1001", "displayName": "Alicia Tan", "role": "CUSTOMER"}
        if url.endswith("/bookings"):
            return [{"bookingId": 10, "userId": "user-1001"}]
        if url.endswith("/notifications"):
            return [{"notificationId": 20, "userId": "user-1001", "subject": "Ready", "message": "Hi", "audience": "CUSTOMER"}]
        if url.endswith("/payments"):
            return [{"paymentId": 30, "userId": "user-1001", "amount": 12.5, "reason": "BOOKING", "status": "SUCCESS"}]
        if url.endswith("/pricing/customers/user-1001/ledger"):
            return [{"ledgerId": 40, "bookingId": 10, "userId": "user-1001"}]
        raise AssertionError(f"Unexpected URL {url}")

    monkeypatch.setattr(process_booking_service, "get_json", fake_get_json)

    with TestClient(process_booking_service.app) as client:
        home = client.get("/process-booking/customers/user-1001/home")
        wallet = client.get("/process-booking/customers/user-1001/wallet")

    assert home.status_code == 200
    assert wallet.status_code == 200
    assert home.json() == {
        "customerSummary": {"userId": "user-1001", "displayName": "Alicia Tan", "role": "CUSTOMER"},
        "bookings": [{"bookingId": 10, "userId": "user-1001"}],
        "notifications": [{"notificationId": 20, "userId": "user-1001", "subject": "Ready", "message": "Hi", "audience": "CUSTOMER"}],
    }
    assert wallet.json() == {
        "customerSummary": {"userId": "user-1001", "displayName": "Alicia Tan", "role": "CUSTOMER"},
        "bookings": [{"bookingId": 10, "userId": "user-1001"}],
        "payments": [{"paymentId": 30, "userId": "user-1001", "amount": 12.5, "reason": "BOOKING", "status": "SUCCESS"}],
        "ledgerEntries": [{"ledgerId": 40, "bookingId": 10, "userId": "user-1001"}],
    }


def test_process_booking_detail_aggregates_booking_vehicle_and_customer(monkeypatch):
    def fake_get_json(url, params=None):
        if "/booking/" in url:
            return {"bookingId": 11, "vehicleId": 5, "userId": "user-1002"}
        if url.endswith("/vehicles/5"):
            return {"vehicleId": 5, "model": "BYD Atto 3"}
        if url.endswith("/pricing/customers/user-1002/summary"):
            return {"userId": "user-1002", "displayName": "Marcus Lee", "role": "CUSTOMER"}
        raise AssertionError(f"Unexpected URL {url}")

    monkeypatch.setattr(process_booking_service, "get_json", fake_get_json)

    with TestClient(process_booking_service.app) as client:
        response = client.get("/process-booking/bookings/11")

    assert response.status_code == 200
    assert response.json() == {
        "booking": {"bookingId": 11, "vehicleId": 5, "userId": "user-1002"},
        "vehicle": {"vehicleId": 5, "model": "BYD Atto 3"},
        "customerSummary": {"userId": "user-1002", "displayName": "Marcus Lee", "role": "CUSTOMER"},
    }


def test_process_booking_search_rejects_start_time_after_end_time():
    with TestClient(process_booking_service.app) as client:
        response = client.get(
            "/process-booking/search",
            params={
                "userId": "user-1001",
                "pickupLocation": "SMU",
                "startTime": "2026-04-09T12:00:00Z",
                "endTime": "2026-04-09T11:00:00Z",
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "endTime must be later than startTime"


def test_process_booking_reserve_allows_future_slot_for_vehicle_currently_in_use(monkeypatch):
    def fake_get_json(url, params=None):
        if url.endswith("/vehicles/7"):
            return {"vehicleId": 7, "status": "IN_USE"}
        if url.endswith("/bookings/availability"):
            return {"slotAvailable": True}
        if url.endswith("/pricing/quote"):
            return {
                "estimatedPrice": 12.5,
                "crossCycleBooking": False,
                "customerSummary": {"userId": "user-1001"},
            }
        raise AssertionError(f"Unexpected GET {url}")

    def fake_post_json(url, payload):
        assert url.endswith("/booking")
        return {"bookingId": 44}

    monkeypatch.setattr(process_booking_service, "get_json", fake_get_json)
    monkeypatch.setattr(process_booking_service, "post_json", fake_post_json)
    monkeypatch.setattr(
        process_booking_service,
        "check_operational_eligibility",
        lambda vehicle_id: {"available": True, "status": "IN_USE", "message": "Vehicle is operationally eligible"},
    )

    with TestClient(process_booking_service.app) as client:
        response = client.post(
            "/process-booking/reserve",
            json={
                "userId": "user-1001",
                "vehicleId": 7,
                "pickupLocation": "SMU",
                "startTime": "2026-04-10T12:00:00Z",
                "endTime": "2026-04-10T14:00:00Z",
                "displayedPrice": 0,
                "subscriptionPlanId": "STANDARD_MONTHLY",
            },
        )

    assert response.status_code == 200
    assert response.json()["bookingId"] == 44


def test_process_booking_reserve_rejects_overlapping_booking(monkeypatch):
    def fake_get_json(url, params=None):
        if url.endswith("/vehicles/7"):
            return {"vehicleId": 7, "status": "AVAILABLE"}
        if url.endswith("/bookings/availability"):
            return {"slotAvailable": False}
        raise AssertionError(f"Unexpected GET {url}")

    monkeypatch.setattr(process_booking_service, "get_json", fake_get_json)
    monkeypatch.setattr(
        process_booking_service,
        "check_operational_eligibility",
        lambda vehicle_id: {"available": True, "status": "AVAILABLE", "message": "Vehicle is operationally eligible"},
    )

    with TestClient(process_booking_service.app) as client:
        response = client.post(
            "/process-booking/reserve",
            json={
                "userId": "user-1001",
                "vehicleId": 7,
                "pickupLocation": "SMU",
                "startTime": "2026-04-10T12:00:00Z",
                "endTime": "2026-04-10T14:00:00Z",
                "displayedPrice": 0,
                "subscriptionPlanId": "STANDARD_MONTHLY",
            },
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "Vehicle is already reserved for that slot"


@pytest.mark.parametrize("blocked_status", ["MAINTENANCE_REQUIRED", "UNDER_INSPECTION"])
def test_process_booking_reserve_rejects_operationally_blocked_vehicle(monkeypatch, blocked_status):
    monkeypatch.setattr(process_booking_service, "get_json", lambda url, params=None: {"vehicleId": 7, "status": blocked_status})
    monkeypatch.setattr(
        process_booking_service,
        "check_operational_eligibility",
        lambda vehicle_id: {"available": False, "status": blocked_status, "message": "Vehicle is operationally blocked"},
    )

    with TestClient(process_booking_service.app) as client:
        response = client.post(
            "/process-booking/reserve",
            json={
                "userId": "user-1001",
                "vehicleId": 7,
                "pickupLocation": "SMU",
                "startTime": "2026-04-10T12:00:00Z",
                "endTime": "2026-04-10T14:00:00Z",
                "displayedPrice": 0,
                "subscriptionPlanId": "STANDARD_MONTHLY",
            },
        )

    assert response.status_code == 409
    assert blocked_status in response.json()["detail"]
