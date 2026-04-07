import os
from datetime import datetime

import pytest

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./test_record_service.db"

TestClient = pytest.importorskip("fastapi.testclient").TestClient

from fleetshare_common.apps import record_service
from fleetshare_common.database import SessionLocal


def test_record_ingest_stores_uploaded_evidence_in_record_service(monkeypatch):
    uploaded_keys: list[str] = []
    monkeypatch.setattr(
        record_service,
        "upload_bytes",
        lambda key, raw, content_type="application/octet-stream": uploaded_keys.append(key) or key,
    )
    record_service.initialize_schema_with_retry(record_service.Base.metadata)
    with SessionLocal() as db:
        db.query(record_service.Record).delete()
        db.commit()

    with TestClient(record_service.app) as client:
        response = client.post(
            "/records/ingest",
            data={
                "bookingId": "12",
                "vehicleId": "9",
                "recordType": "EXTERNAL_DAMAGE",
                "notes": "Rear bumper dent",
                "severity": "PENDING",
                "reviewState": "PENDING_EXTERNAL",
            },
            files=[("photos", ("rear.jpg", b"image-bytes", "image/jpeg"))],
        )
        record_id = response.json()["recordId"]
        records = client.get("/records", params={"bookingId": 12}).json()

    assert response.status_code == 200
    assert len(uploaded_keys) == 1
    assert uploaded_keys[0].startswith("records/external_damage/booking-12/")
    assert records[0]["recordId"] == record_id
    assert records[0]["evidenceUrls"] == uploaded_keys


def test_record_ingest_accepts_pre_trip_form_without_trip_id(monkeypatch):
    uploaded_keys: list[str] = []
    monkeypatch.setattr(
        record_service,
        "upload_bytes",
        lambda key, raw, content_type="application/octet-stream": uploaded_keys.append(key) or key,
    )
    record_service.initialize_schema_with_retry(record_service.Base.metadata)
    with SessionLocal() as db:
        db.query(record_service.Record).delete()
        db.commit()

    with TestClient(record_service.app) as client:
        response = client.post(
            "/records/ingest",
            data={
                "bookingId": "14",
                "vehicleId": "4",
                "recordType": "EXTERNAL_DAMAGE",
                "notes": "Vehicle looks clean",
                "severity": "PENDING",
                "reviewState": "PENDING_EXTERNAL",
            },
        )
        record_id = response.json()["recordId"]
        records = client.get("/records", params={"bookingId": 14}).json()

    assert response.status_code == 200
    assert len(records) == 1
    assert records[0]["recordId"] == record_id
    assert records[0]["tripId"] is None
    assert records[0]["evidenceUrls"] == []


def test_record_evidence_download_returns_binary_payload(monkeypatch):
    monkeypatch.setattr(record_service, "download_bytes", lambda key: (b"evidence-image", "image/jpeg"))
    record_service.initialize_schema_with_retry(record_service.Base.metadata)
    with SessionLocal() as db:
        db.query(record_service.Record).delete()
        db.commit()

    with TestClient(record_service.app) as client:
        created = client.post(
            "/records",
            json={
                "bookingId": 10,
                "vehicleId": 7,
                "recordType": "EXTERNAL_DAMAGE",
                "notes": "Front bumper dent",
                "evidenceUrls": ["damage/10/front.jpg"],
            },
        )
        record_id = created.json()["recordId"]
        response = client.get(f"/records/{record_id}/evidence/0")

    assert response.status_code == 200
    assert response.content == b"evidence-image"
    assert response.headers["content-type"].startswith("image/jpeg")
    assert response.headers["content-disposition"] == 'inline; filename="front.jpg"'


def test_record_evidence_download_rejects_missing_evidence_index(monkeypatch):
    monkeypatch.setattr(record_service, "download_bytes", lambda key: (b"unused", "image/jpeg"))
    record_service.initialize_schema_with_retry(record_service.Base.metadata)
    with SessionLocal() as db:
        db.query(record_service.Record).delete()
        db.commit()

    with TestClient(record_service.app) as client:
        created = client.post(
            "/records",
            json={
                "bookingId": 11,
                "vehicleId": 8,
                "recordType": "EXTERNAL_DAMAGE",
                "notes": "No evidence uploaded",
                "evidenceUrls": [],
            },
        )
        record_id = created.json()["recordId"]
        response = client.get(f"/records/{record_id}/evidence/0")

    assert response.status_code == 404
    assert response.json()["detail"] == "Evidence item not found"


def test_record_list_serializes_created_and_updated_at_as_utc_z():
    record_service.initialize_schema_with_retry(record_service.Base.metadata)
    with SessionLocal() as db:
        db.query(record_service.Record).delete()
        db.add(
            record_service.Record(
                booking_id=21,
                vehicle_id=8,
                record_type="EXTERNAL_DAMAGE",
                created_at=datetime(2026, 4, 7, 10, 42),
                updated_at=datetime(2026, 4, 7, 10, 43),
            )
        )
        db.commit()

    with TestClient(record_service.app) as client:
        response = client.get("/records", params={"bookingId": 21})

    assert response.status_code == 200
    assert response.json()[0]["createdAt"] == "2026-04-07T10:42:00Z"
    assert response.json()[0]["updatedAt"] == "2026-04-07T10:43:00Z"
