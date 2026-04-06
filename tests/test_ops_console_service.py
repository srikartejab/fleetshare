import pytest
import httpx

TestClient = pytest.importorskip("fastapi.testclient").TestClient

from fleetshare_common.apps import ops_console_service


def test_ops_console_dashboard_enriches_operational_views(monkeypatch):
    responses = {
        "/vehicles": [
            {
                "id": 1,
                "vehicleId": 1,
                "model": "Hyundai Kona Electric",
                "stationName": "Pasir Ris Hub",
                "stationAddress": "Blk 149A Pasir Ris",
                "zone": "EAST",
            }
        ],
        "/pricing/customers": [{"userId": "user-1001", "displayName": "Alicia Tan"}],
        "/bookings": [{"bookingId": 10, "userId": "user-1001", "vehicleId": 1, "pickupLocation": "Pasir Ris Hub"}],
        "/trips": [{"tripId": 20, "bookingId": 10, "vehicleId": 1}],
        "/maintenance/tickets": [{"ticketId": 30, "vehicleId": 1, "bookingId": 10, "recordId": 40}],
        "/records": [{"recordId": 40, "vehicleId": 1, "bookingId": 10, "notes": "Front bumper dent", "evidenceUrls": ["damage/40/front.jpg"]}],
        "/records/manual-review-queue": [{"recordId": 50, "vehicleId": 1, "bookingId": 10, "evidenceUrls": []}],
        "/payments": [{"paymentId": 60}],
        "/notifications": [{"notificationId": 70, "bookingId": 10, "tripId": 20, "payload": {"severity": "CRITICAL"}}],
    }

    def fake_get_json(url, params=None):
        for suffix, payload in responses.items():
            if url.endswith(suffix):
                return payload
        raise AssertionError(f"Unexpected URL {url}")

    monkeypatch.setattr(ops_console_service, "get_json", fake_get_json)

    with TestClient(ops_console_service.app) as client:
        response = client.get("/ops-console/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["vehicles"][0]["model"] == "Hyundai Kona Electric"
    assert payload["bookings"][0]["bookingCode"] == "B-000010"
    assert payload["bookings"][0]["customerName"] == "Alicia Tan"
    assert payload["tickets"][0]["vehicleName"] == "Hyundai Kona Electric"
    assert payload["tickets"][0]["recordSummary"] == "Front bumper dent"
    assert payload["tickets"][0]["hasEvidence"] is True
    assert payload["records"][0]["customerName"] == "Alicia Tan"
    assert payload["reviewQueue"][0]["bookingCode"] == "B-000010"
    assert payload["notifications"][0]["vehicleName"] == "Hyundai Kona Electric"
    assert payload["notifications"][0]["severity"] == "CRITICAL"


def test_ops_console_ticket_detail_returns_linked_entities(monkeypatch):
    responses = {
        "/vehicles": [{"id": 1, "vehicleId": 1, "model": "Hyundai Kona Electric", "stationName": "Pasir Ris Hub", "zone": "EAST"}],
        "/pricing/customers": [{"userId": "user-1001", "displayName": "Alicia Tan"}],
        "/bookings": [{"bookingId": 10, "userId": "user-1001", "vehicleId": 1, "pickupLocation": "Pasir Ris Hub"}],
        "/trips": [{"tripId": 20, "bookingId": 10, "vehicleId": 1}],
        "/maintenance/tickets": [{"ticketId": 30, "vehicleId": 1, "bookingId": 10, "tripId": 20, "recordId": 40}],
        "/records": [{"recordId": 40, "vehicleId": 1, "bookingId": 10, "notes": "Front bumper dent", "evidenceUrls": ["damage/40/front.jpg"]}],
        "/records/manual-review-queue": [],
        "/payments": [],
        "/notifications": [],
    }

    def fake_get_json(url, params=None):
        if url.endswith("/maintenance/tickets/30"):
            return {
                "ticketId": 30,
                "vehicleId": 1,
                "bookingId": 10,
                "tripId": 20,
                "recordId": 40,
                "damageSeverity": "SEVERE",
                "damageType": "LOW_BATTERY",
                "recommendedAction": "Recover vehicle",
                "estimatedDurationHours": 24,
                "status": "OPEN",
            }
        for suffix, payload in responses.items():
            if url.endswith(suffix):
                return payload
        raise AssertionError(f"Unexpected URL {url}")

    monkeypatch.setattr(ops_console_service, "get_json", fake_get_json)

    with TestClient(ops_console_service.app) as client:
        response = client.get("/ops-console/tickets/30")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticket"]["vehicleName"] == "Hyundai Kona Electric"
    assert payload["ticket"]["customerName"] == "Alicia Tan"
    assert payload["booking"]["bookingCode"] == "B-000010"
    assert payload["record"]["notes"] == "Front bumper dent"
    assert payload["evidenceUrls"] == ["/ops-console/tickets/30/evidence/0"]


def test_ops_console_ticket_evidence_proxies_record_service_bytes(monkeypatch):
    responses = {
        "/vehicles": [],
        "/pricing/customers": [],
        "/bookings": [],
        "/trips": [],
        "/maintenance/tickets": [{"ticketId": 30, "vehicleId": 1, "recordId": 40}],
        "/records": [{"recordId": 40, "vehicleId": 1, "evidenceUrls": ["damage/40/front.jpg"]}],
        "/records/manual-review-queue": [],
        "/payments": [],
        "/notifications": [],
    }

    def fake_get_json(url, params=None):
        if url.endswith("/maintenance/tickets/30"):
            return {"ticketId": 30, "vehicleId": 1, "recordId": 40}
        for suffix, payload in responses.items():
            if url.endswith(suffix):
                return payload
        raise AssertionError(f"Unexpected URL {url}")

    def fake_httpx_get(url, timeout):
        assert url.endswith("/records/40/evidence/0")
        return httpx.Response(
            200,
            content=b"image-bytes",
            headers={"content-type": "image/jpeg", "content-disposition": 'inline; filename="front.jpg"'},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(ops_console_service, "get_json", fake_get_json)
    monkeypatch.setattr(ops_console_service.httpx, "get", fake_httpx_get)

    with TestClient(ops_console_service.app) as client:
        response = client.get("/ops-console/tickets/30/evidence/0")

    assert response.status_code == 200
    assert response.content == b"image-bytes"
    assert response.headers["content-type"].startswith("image/jpeg")
    assert response.headers["content-disposition"] == 'inline; filename="front.jpg"'
