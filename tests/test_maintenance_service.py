from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

TestClient = pytest.importorskip("fastapi.testclient").TestClient

from fleetshare_common.apps import maintenance_service
from fleetshare_common import database


@pytest.fixture(autouse=True)
def reset_maintenance_db(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", session_local)
    monkeypatch.setattr(maintenance_service, "engine", engine)

    maintenance_service.Base.metadata.drop_all(bind=engine)
    maintenance_service.Base.metadata.create_all(bind=engine)
    maintenance_service.ensure_source_event_id_column()
    yield


def test_create_ticket_is_idempotent_for_source_event_id():
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
    assert first.json()["ticketId"] == second.json()["ticketId"]
    assert first.json()["sourceEventId"] == "evt-source-1"
    assert len(tickets.json()) == 1
