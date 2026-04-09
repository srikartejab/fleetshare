from __future__ import annotations

import os
from datetime import datetime
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

TestClient = pytest.importorskip("fastapi.testclient").TestClient

from fleetshare_common.apps import maintenance_service


@pytest.fixture(autouse=True)
def reset_local_backend():
    maintenance_service._local_engine = None
    maintenance_service._local_session_factory = None
    yield
    maintenance_service._local_engine = None
    maintenance_service._local_session_factory = None


def test_local_mode_keeps_source_event_id_idempotency(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    maintenance_service._local_engine = engine
    maintenance_service._local_session_factory = session_local
    maintenance_service.LocalBase.metadata.create_all(bind=engine)
    maintenance_service.ensure_source_event_id_column()

    monkeypatch.setattr(maintenance_service, "_backend_mode", lambda: "local")

    payload = {
        "vehicleId": 7,
        "damageSeverity": "SEVERE",
        "damageType": "low_battery",
        "recommendedAction": "Recover vehicle",
        "estimatedDurationHours": 48,
        "recordId": 101,
        "bookingId": 202,
        "tripId": 303,
        "openedByEventType": "incident.internal_fault_detected",
        "sourceEventId": "evt-source-1",
    }

    with TestClient(maintenance_service.app) as client:
        first = client.post("/maintenance/tickets", json=payload)
        second = client.post("/maintenance/tickets", json=payload)
        tickets = client.get("/maintenance/tickets")

    assert first.status_code == 200
    assert second.status_code == 200
    assert tickets.status_code == 200
    assert first.headers["X-Maintenance-Backend"] == "local"
    assert first.json()["ticketId"] == second.json()["ticketId"]
    assert first.json()["sourceEventId"] == "evt-source-1"
    assert len(tickets.json()) == 1


def test_local_ticket_detail_serializes_created_at_as_utc_z(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    maintenance_service._local_engine = engine
    maintenance_service._local_session_factory = session_local
    maintenance_service.LocalBase.metadata.create_all(bind=engine)
    maintenance_service.ensure_source_event_id_column()

    with session_local() as db:
        ticket = maintenance_service.MaintenanceTicket(
            vehicle_id=11,
            damage_severity="SEVERE",
            damage_type="BATTERY",
            recommended_action="Tow to depot",
            created_at=datetime(2026, 4, 7, 10, 42),
        )
        db.add(ticket)
        db.commit()
        ticket_id = ticket.id

    monkeypatch.setattr(maintenance_service, "_backend_mode", lambda: "local")

    with TestClient(maintenance_service.app) as client:
        response = client.get(f"/maintenance/tickets/{ticket_id}")

    assert response.status_code == 200
    assert response.json()["createdAt"] == "2026-04-07T10:42:00Z"


def test_outsystems_list_normalizes_fields_and_sets_backend_header(monkeypatch):
    monkeypatch.setattr(maintenance_service, "_backend_mode", lambda: "outsystems")
    monkeypatch.setattr(
        maintenance_service,
        "_outsystems_request",
        lambda method, path, payload=None: [
            {
                "Id": 8,
                "vehicle_id": 1,
                "damage_severity": "HIGH",
                "damage_type": "ENGINE",
                "recommended_action": "Replace engine components",
                "estimated_duration_hours": 24,
                "status": "OPEN",
                "created_at": "2026-04-06T19:19:46Z",
                "record_id": 101,
                "booking_id": 1001,
                "trip_id": 2001,
                "opened_by_event_type": "SYSTEM",
            }
        ],
    )

    with TestClient(maintenance_service.app) as client:
        response = client.get("/maintenance/tickets")

    assert response.status_code == 200
    assert response.headers["X-Maintenance-Backend"] == "outsystems"
    assert response.json() == [
        {
            "ticketId": 8,
            "vehicleId": 1,
            "damageSeverity": "HIGH",
            "damageType": "ENGINE",
            "recommendedAction": "Replace engine components",
            "estimatedDurationHours": 24,
            "recordId": 101,
            "bookingId": 1001,
            "tripId": 2001,
            "openedByEventType": "SYSTEM",
            "sourceEventId": None,
            "status": "OPEN",
            "createdAt": "2026-04-06T19:19:46Z",
        }
    ]


def test_outsystems_list_returns_empty_for_known_empty_400(monkeypatch):
    monkeypatch.setattr(maintenance_service, "_backend_mode", lambda: "outsystems")

    def fake_request(method, url, json=None, timeout=None):
        return httpx.Response(
            400,
            text='{"detail":"{\\"detail\\": \\"No maintenance tickets\\"}"}',
            headers={"content-type": "application/json"},
            request=httpx.Request(method, url),
        )

    monkeypatch.setattr(maintenance_service.httpx, "request", fake_request)

    with TestClient(maintenance_service.app) as client:
        response = client.get("/maintenance/tickets")

    assert response.status_code == 200
    assert response.headers["X-Maintenance-Backend"] == "outsystems"
    assert response.json() == []


def test_outsystems_list_keeps_non_empty_400_errors(monkeypatch):
    monkeypatch.setattr(maintenance_service, "_backend_mode", lambda: "outsystems")

    def fake_request(method, url, json=None, timeout=None):
        return httpx.Response(
            400,
            json={"detail": "Validation failed"},
            request=httpx.Request(method, url),
        )

    monkeypatch.setattr(maintenance_service.httpx, "request", fake_request)

    with TestClient(maintenance_service.app) as client:
        response = client.get("/maintenance/tickets")

    assert response.status_code == 400
    assert response.json() == {"detail": "Validation failed"}


def test_outsystems_create_maps_request_and_ignores_source_event_id(monkeypatch):
    monkeypatch.setattr(maintenance_service, "_backend_mode", lambda: "outsystems")
    captured = {}

    def fake_request(method: str, path: str, payload=None):
        captured["method"] = method
        captured["path"] = path
        captured["payload"] = payload
        return {
            "Id": 9,
            "vehicle_id": 1,
            "damage_severity": "HIGH",
            "damage_type": "WRAPPER_TEST_ENGINE",
            "recommended_action": "Wrapper test replacement",
            "estimated_duration_hours": 24,
            "status": "OPEN",
            "created_at": "2026-04-06T19:21:14Z",
            "record_id": 9901,
            "booking_id": 9902,
            "trip_id": 9903,
            "opened_by_event_type": "WRAPPER_TEST",
        }

    monkeypatch.setattr(maintenance_service, "_outsystems_request", fake_request)

    with TestClient(maintenance_service.app) as client:
        response = client.post(
            "/maintenance/tickets",
            json={
                "vehicleId": 1,
                "damageSeverity": "HIGH",
                "damageType": "WRAPPER_TEST_ENGINE",
                "recommendedAction": "Wrapper test replacement",
                "estimatedDurationHours": 24,
                "recordId": 9901,
                "bookingId": 9902,
                "tripId": 9903,
                "openedByEventType": "WRAPPER_TEST",
                "sourceEventId": "evt-wrapper-test",
            },
        )

    assert response.status_code == 200
    assert response.headers["X-Maintenance-Backend"] == "outsystems"
    assert captured == {
        "method": "POST",
        "path": "/tickets",
        "payload": {
            "vehicle_id": 1,
            "damage_severity": "HIGH",
            "damage_type": "WRAPPER_TEST_ENGINE",
            "recommended_action": "Wrapper test replacement",
            "estimated_duration_hours": 24,
            "status": "OPEN",
            "record_id": 9901,
            "booking_id": 9902,
            "trip_id": 9903,
            "opened_by_event_type": "WRAPPER_TEST",
        },
    }
    assert response.json() == {
        "ticketId": 9,
        "vehicleId": 1,
        "damageSeverity": "HIGH",
        "damageType": "WRAPPER_TEST_ENGINE",
        "recommendedAction": "Wrapper test replacement",
        "estimatedDurationHours": 24,
        "recordId": 9901,
        "bookingId": 9902,
        "tripId": 9903,
        "openedByEventType": "WRAPPER_TEST",
        "sourceEventId": None,
        "status": "OPEN",
        "createdAt": "2026-04-06T19:21:14Z",
    }


def test_outsystems_detail_normalizes_fields(monkeypatch):
    monkeypatch.setattr(maintenance_service, "_backend_mode", lambda: "outsystems")
    monkeypatch.setattr(
        maintenance_service,
        "_outsystems_request",
        lambda method, path, payload=None: {
            "Id": 6,
            "vehicle_id": 101,
            "damage_severity": "LOW",
            "damage_type": "SCRATCH",
            "recommended_action": "Buffing and polishing",
            "estimated_duration_hours": 6,
            "status": "OPEN",
            "created_at": "2026-04-06T16:00:33.28Z",
            "record_id": 1002,
            "booking_id": 2002,
            "trip_id": 3002,
            "opened_by_event_type": "SYSTEM_ALERT",
        },
    )

    with TestClient(maintenance_service.app) as client:
        response = client.get("/maintenance/tickets/6")

    assert response.status_code == 200
    assert response.headers["X-Maintenance-Backend"] == "outsystems"
    assert response.json() == {
        "ticketId": 6,
        "vehicleId": 101,
        "damageSeverity": "LOW",
        "damageType": "SCRATCH",
        "recommendedAction": "Buffing and polishing",
        "estimatedDurationHours": 6,
        "recordId": 1002,
        "bookingId": 2002,
        "tripId": 3002,
        "openedByEventType": "SYSTEM_ALERT",
        "sourceEventId": None,
        "status": "OPEN",
        "createdAt": "2026-04-06T16:00:33.28Z",
    }


def test_backend_info_reports_outsystems_mode(monkeypatch):
    monkeypatch.setattr(maintenance_service, "_backend_mode", lambda: "outsystems")
    monkeypatch.setattr(
        maintenance_service,
        "get_settings",
        lambda: SimpleNamespace(
            maintenance_backend_mode="outsystems",
            outsystems_maintenance_base_url="https://example.outsystems/rest/maintenance",
            outsystems_maintenance_timeout_seconds=20,
        ),
    )

    with TestClient(maintenance_service.app) as client:
        response = client.get("/maintenance/backend-info")

    assert response.status_code == 200
    assert response.headers["X-Maintenance-Backend"] == "outsystems"
    assert response.json() == {
        "backendMode": "outsystems",
        "backend": "outsystems",
        "outsystemsBaseUrl": "https://example.outsystems/rest/maintenance",
    }
