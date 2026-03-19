from __future__ import annotations

import pytest

from fleetshare_common.ai import assess_damage

fastapi = pytest.importorskip("fastapi")
TestClient = pytest.importorskip("fastapi.testclient").TestClient
from fleetshare_common.apps import external_damage_service


def test_mock_assessment_ignores_uploaded_filename_keywords():
    result = assess_damage("Vehicle exterior looks clean.", ["dent-fix-cost-estimate.jpg"])

    assert result["severity"] == "MINOR"
    assert result["confidence"] >= 0.7
    assert result["detectedDamage"] == ["no visible exterior damage"]


def test_mock_assessment_routes_ambiguous_damage_to_moderate():
    result = assess_damage("Rear door dent visible.", ["clean.jpg"])

    assert result["severity"] == "MODERATE"
    assert result["confidence"] < 0.7
    assert result["detectedDamage"] == ["possible body damage"]


def test_external_damage_service_keeps_clean_inspection_cleared(monkeypatch):
    record_updates: list[dict] = []
    published_events: list[tuple[str, dict]] = []
    vehicle_updates: list[tuple[int, str]] = []

    monkeypatch.setattr(external_damage_service, "ensure_bucket", lambda: None)
    monkeypatch.setattr(
        external_damage_service,
        "upload_bytes",
        lambda key, raw, content_type="application/octet-stream": f"minio://{key}",
    )
    monkeypatch.setattr(external_damage_service, "post_json", lambda url, payload: {"recordId": 123})
    monkeypatch.setattr(external_damage_service, "patch_json", lambda url, payload: record_updates.append(payload))
    monkeypatch.setattr(
        external_damage_service,
        "publish_event",
        lambda event_type, payload: published_events.append((event_type, payload)),
    )
    monkeypatch.setattr(
        external_damage_service,
        "update_vehicle_status",
        lambda vehicle_id, status: vehicle_updates.append((vehicle_id, status)),
    )

    with TestClient(external_damage_service.app) as client:
        response = client.post(
            "/damage-assessment/external",
            data={"bookingId": 101, "vehicleId": 7, "userId": "user-1", "notes": "Vehicle exterior looks clean."},
            files=[("photos", ("dent-fix-cost-estimate.jpg", b"fake-image", "image/jpeg"))],
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tripStatus"] == "CLEARED"
    assert payload["warningMessage"] == "Inspection passed"
    assert payload["assessmentResult"]["severity"] == "MINOR"
    assert record_updates == [
        {
            "severity": "MINOR",
            "reviewState": "EXTERNAL_ASSESSED",
            "confidence": 0.98,
            "detectedDamage": ["no visible exterior damage"],
        }
    ]
    assert published_events == []
    assert vehicle_updates == []


def test_external_damage_service_blocks_severe_damage_and_publishes_incident(monkeypatch):
    record_updates: list[dict] = []
    published_events: list[tuple[str, dict]] = []
    vehicle_updates: list[tuple[int, str]] = []

    monkeypatch.setattr(external_damage_service, "ensure_bucket", lambda: None)
    monkeypatch.setattr(
        external_damage_service,
        "upload_bytes",
        lambda key, raw, content_type="application/octet-stream": f"minio://{key}",
    )
    monkeypatch.setattr(external_damage_service, "post_json", lambda url, payload: {"recordId": 456})
    monkeypatch.setattr(external_damage_service, "patch_json", lambda url, payload: record_updates.append(payload))
    monkeypatch.setattr(
        external_damage_service,
        "publish_event",
        lambda event_type, payload: published_events.append((event_type, payload)),
    )
    monkeypatch.setattr(
        external_damage_service,
        "update_vehicle_status",
        lambda vehicle_id, status: vehicle_updates.append((vehicle_id, status)),
    )

    with TestClient(external_damage_service.app) as client:
        response = client.post(
            "/damage-assessment/external",
            data={"bookingId": 202, "vehicleId": 9, "userId": "user-2", "notes": "Broken mirror and cracked bumper."},
            files=[("photos", ("walkaround.jpg", b"fake-image", "image/jpeg"))],
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tripStatus"] == "BLOCKED"
    assert payload["warningMessage"] == "Severe damage detected. Vehicle blocked."
    assert payload["assessmentResult"]["severity"] == "SEVERE"
    assert record_updates == [
        {
            "severity": "SEVERE",
            "reviewState": "EXTERNAL_BLOCKED",
            "confidence": 0.92,
            "detectedDamage": ["major exterior damage"],
        }
    ]
    assert vehicle_updates == [(9, "UNDER_INSPECTION")]
    assert published_events == [
        (
            "incident.external_damage_detected",
            {
                "recordId": 456,
                "bookingId": 202,
                "vehicleId": 9,
                "userId": "user-2",
                "severity": "SEVERE",
                "damageType": "major exterior damage",
                "recommendedAction": "Immediate inspection and customer refund",
            },
        )
    ]


def test_external_damage_service_allows_trip_start_for_moderate_damage(monkeypatch):
    record_updates: list[dict] = []
    published_events: list[tuple[str, dict]] = []
    vehicle_updates: list[tuple[int, str]] = []

    monkeypatch.setattr(external_damage_service, "ensure_bucket", lambda: None)
    monkeypatch.setattr(
        external_damage_service,
        "upload_bytes",
        lambda key, raw, content_type="application/octet-stream": f"minio://{key}",
    )
    monkeypatch.setattr(external_damage_service, "post_json", lambda url, payload: {"recordId": 789})
    monkeypatch.setattr(external_damage_service, "patch_json", lambda url, payload: record_updates.append(payload))
    monkeypatch.setattr(
        external_damage_service,
        "publish_event",
        lambda event_type, payload: published_events.append((event_type, payload)),
    )
    monkeypatch.setattr(
        external_damage_service,
        "update_vehicle_status",
        lambda vehicle_id, status: vehicle_updates.append((vehicle_id, status)),
    )

    with TestClient(external_damage_service.app) as client:
        response = client.post(
            "/damage-assessment/external",
            data={"bookingId": 303, "vehicleId": 11, "userId": "user-3", "notes": "Rear door dent visible."},
            files=[("photos", ("walkaround.jpg", b"fake-image", "image/jpeg"))],
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tripStatus"] == "CLEARED"
    assert payload["warningMessage"] == "Moderate damage noted. You can still unlock the vehicle or cancel the booking to escalate it to ops."
    assert payload["assessmentResult"]["severity"] == "MODERATE"
    assert payload["manualReview"] is False
    assert record_updates == [
        {
            "severity": "MODERATE",
            "reviewState": "EXTERNAL_ASSESSED",
            "confidence": 0.61,
            "detectedDamage": ["possible body damage"],
        }
    ]
    assert published_events == []
    assert vehicle_updates == []


def test_customer_cancel_for_moderate_damage_publishes_incident(monkeypatch):
    record_updates: list[dict] = []
    published_events: list[tuple[str, dict]] = []
    vehicle_updates: list[tuple[int, str]] = []

    def fake_get_json(url: str, params: dict | None = None):
        if "/booking/" in url:
            return {"bookingId": 303, "userId": "user-3", "status": "CONFIRMED"}
        return [
            {
                "recordId": 789,
                "bookingId": 303,
                "vehicleId": 11,
                "recordType": "EXTERNAL_DAMAGE",
                "severity": "MODERATE",
                "reviewState": "EXTERNAL_ASSESSED",
                "detectedDamage": ["possible body damage"],
            }
        ]

    monkeypatch.setattr(external_damage_service, "get_json", fake_get_json)
    monkeypatch.setattr(external_damage_service, "patch_json", lambda url, payload: record_updates.append(payload))
    monkeypatch.setattr(
        external_damage_service,
        "publish_event",
        lambda event_type, payload: published_events.append((event_type, payload)),
    )
    monkeypatch.setattr(
        external_damage_service,
        "update_vehicle_status",
        lambda vehicle_id, status: vehicle_updates.append((vehicle_id, status)),
    )

    with TestClient(external_damage_service.app) as client:
        response = client.post(
            "/damage-assessment/external/customer-cancel",
            json={"bookingId": 303, "vehicleId": 11, "userId": "user-3"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "CANCELLATION_REQUESTED"
    assert record_updates == [{"reviewState": "EXTERNAL_BLOCKED"}]
    assert vehicle_updates == [(11, "UNDER_INSPECTION")]
    assert published_events == [
        (
            "incident.external_damage_detected",
            {
                "recordId": 789,
                "bookingId": 303,
                "vehicleId": 11,
                "userId": "user-3",
                "severity": "MODERATE",
                "damageType": "possible body damage",
                "recommendedAction": "Customer requested cancellation after moderate external damage finding",
            },
        )
    ]


def test_post_trip_damage_service_records_follow_up_without_blocking_end_trip(monkeypatch):
    record_updates: list[dict] = []
    published_events: list[tuple[str, dict]] = []
    vehicle_updates: list[tuple[int, str]] = []

    monkeypatch.setattr(external_damage_service, "ensure_bucket", lambda: None)
    monkeypatch.setattr(
        external_damage_service,
        "upload_bytes",
        lambda key, raw, content_type="application/octet-stream": f"minio://{key}",
    )
    monkeypatch.setattr(external_damage_service, "post_json", lambda url, payload: {"recordId": 880})
    monkeypatch.setattr(external_damage_service, "patch_json", lambda url, payload: record_updates.append(payload))
    monkeypatch.setattr(
        external_damage_service,
        "publish_event",
        lambda event_type, payload: published_events.append((event_type, payload)),
    )
    monkeypatch.setattr(
        external_damage_service,
        "update_vehicle_status",
        lambda vehicle_id, status: vehicle_updates.append((vehicle_id, status)),
    )

    with TestClient(external_damage_service.app) as client:
        response = client.post(
            "/damage-assessment/post-trip",
            data={"bookingId": 404, "tripId": 12, "vehicleId": 22, "userId": "user-4", "notes": "Rear door dent visible."},
            files=[("photos", ("return.jpg", b"fake-image", "image/jpeg"))],
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["followUpRequired"] is False
    assert payload["warningMessage"] == "Moderate post-trip issue noted. The report is saved for ops follow-up."
    assert record_updates == [
        {
            "severity": "MODERATE",
            "reviewState": "EXTERNAL_ASSESSED",
            "confidence": 0.61,
            "detectedDamage": ["possible body damage"],
        }
    ]
    assert published_events == []
    assert vehicle_updates == []


def test_post_trip_damage_service_escalates_severe_damage(monkeypatch):
    record_updates: list[dict] = []
    published_events: list[tuple[str, dict]] = []
    vehicle_updates: list[tuple[int, str]] = []

    monkeypatch.setattr(external_damage_service, "ensure_bucket", lambda: None)
    monkeypatch.setattr(
        external_damage_service,
        "upload_bytes",
        lambda key, raw, content_type="application/octet-stream": f"minio://{key}",
    )
    monkeypatch.setattr(external_damage_service, "post_json", lambda url, payload: {"recordId": 990})
    monkeypatch.setattr(external_damage_service, "patch_json", lambda url, payload: record_updates.append(payload))
    monkeypatch.setattr(
        external_damage_service,
        "publish_event",
        lambda event_type, payload: published_events.append((event_type, payload)),
    )
    monkeypatch.setattr(
        external_damage_service,
        "update_vehicle_status",
        lambda vehicle_id, status: vehicle_updates.append((vehicle_id, status)),
    )

    with TestClient(external_damage_service.app) as client:
        response = client.post(
            "/damage-assessment/post-trip",
            data={"bookingId": 505, "tripId": 14, "vehicleId": 23, "userId": "user-5", "notes": "Broken mirror and cracked bumper."},
            files=[("photos", ("return.jpg", b"fake-image", "image/jpeg"))],
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["followUpRequired"] is True
    assert payload["warningMessage"] == "Severe post-trip damage recorded. Ops review and downstream recovery have been triggered."
    assert record_updates == [
        {
            "severity": "SEVERE",
            "reviewState": "EXTERNAL_BLOCKED",
            "confidence": 0.92,
            "detectedDamage": ["major exterior damage"],
        }
    ]
    assert vehicle_updates == [(23, "UNDER_INSPECTION")]
    assert published_events == [
        (
            "incident.external_damage_detected",
            {
                "recordId": 990,
                "bookingId": 505,
                "tripId": 14,
                "vehicleId": 23,
                "userId": "user-5",
                "severity": "SEVERE",
                "damageType": "major exterior damage",
                "recommendedAction": "Inspect vehicle before next rental and compensate affected bookings if needed",
            },
        )
    ]
