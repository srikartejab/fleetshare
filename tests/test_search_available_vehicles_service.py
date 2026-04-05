import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient

from fleetshare_common.apps import search_available_vehicles_service


def test_search_available_vehicles_returns_station_aggregation(monkeypatch):
    stations = [
        {
            "stationId": "PASIR_RIS_BLK_152",
            "stationName": "Block 152 Pasir Ris St 13",
            "stationAddress": "Block 152 Pasir Ris St 13",
            "area": "Pasir Ris",
            "latitude": 1.3725,
            "longitude": 103.9622,
            "totalVehicleCount": 2,
            "operationalAvailableCount": 2,
            "nextAvailableTiming": "19 Mar, 18:00 - 19 Mar, 19:00",
        },
        {
            "stationId": "LOYANG_AVE",
            "stationName": "Loyang Avenue",
            "stationAddress": "Loyang Avenue",
            "area": "Loyang",
            "latitude": 1.3705,
            "longitude": 103.9687,
            "totalVehicleCount": 1,
            "operationalAvailableCount": 1,
            "nextAvailableTiming": "19 Mar, 19:30 - 19 Mar, 20:30",
        },
    ]
    vehicles = [
        {
            "vehicleId": 101,
            "id": 101,
            "plateNumber": "EVA1101K",
            "model": "MG 4 EV",
            "zone": "PASIR_RIS_BLK_152",
            "vehicleType": "SEDAN",
            "status": "AVAILABLE",
            "stationId": "PASIR_RIS_BLK_152",
            "stationName": "Block 152 Pasir Ris St 13",
            "stationAddress": "Block 152 Pasir Ris St 13",
            "area": "Pasir Ris",
            "latitude": 1.3725,
            "longitude": 103.9622,
        },
        {
            "vehicleId": 202,
            "id": 202,
            "plateNumber": "EVA2202L",
            "model": "BYD Seal",
            "zone": "LOYANG_AVE",
            "vehicleType": "SEDAN",
            "status": "AVAILABLE",
            "stationId": "LOYANG_AVE",
            "stationName": "Loyang Avenue",
            "stationAddress": "Loyang Avenue",
            "area": "Loyang",
            "latitude": 1.3705,
            "longitude": 103.9687,
        },
    ]

    def fake_get_json(url, params=None):
        if url.endswith("/vehicles/stations"):
            return stations
        if url.endswith("/vehicles/availability"):
            return vehicles
        if url.endswith("/bookings/availability"):
            return {"availableVehicleIds": [101]}
        if url.endswith("/pricing/quote"):
            vehicle_id = params["vehicleId"]
            return {
                "estimatedPrice": 13.08 if vehicle_id == 101 else 15.90,
                "allowanceStatus": "WITHIN_ALLOWANCE",
                "crossCycleBooking": False,
                "hourlyRate": 9.5,
                "totalHours": 1.0,
                "currentCycleHours": 1.0,
                "includedHoursApplied": 1.0,
                "includedHoursRemainingBefore": 9.0,
                "includedHoursRemainingAfter": 8.0,
                "billableHours": 0.0,
                "provisionalPostMidnightHours": 0.0,
                "provisionalCharge": 0.0,
                "renewalDate": "2026-03-20T00:00:00Z",
            }
        raise AssertionError(f"Unexpected URL {url}")

    monkeypatch.setattr(search_available_vehicles_service, "get_json", fake_get_json)
    monkeypatch.setattr(search_available_vehicles_service, "check_availability", lambda vehicle_id: {"available": True})

    with TestClient(search_available_vehicles_service.app) as client:
        response = client.get(
            "/search-vehicles/search",
            params={
                "userId": "user-1001",
                "pickupLocation": "PASIR_RIS_BLK_152",
                "vehicleType": "SEDAN",
                "startTime": "2026-03-19T10:00:00Z",
                "endTime": "2026-03-19T11:00:00Z",
                "subscriptionPlanId": "STANDARD_MONTHLY",
            },
        )

    assert response.status_code == 200
    payload = response.json()

    assert payload["selectedStationId"] == "PASIR_RIS_BLK_152"
    assert payload["availabilitySummary"] == "1 vehicle(s) available"
    assert payload["vehicleList"][0]["vehicleId"] == 101
    assert payload["stationList"][0]["stationId"] == "PASIR_RIS_BLK_152"
    assert payload["stationList"][0]["availableVehicleCount"] == 1
    assert payload["stationList"][0]["featuredVehicle"]["vehicleId"] == 101
    assert payload["stationList"][1]["stationId"] == "LOYANG_AVE"
    assert payload["stationList"][1]["availableVehicleCount"] == 0
