from __future__ import annotations

from types import SimpleNamespace

from fleetshare_common.apps import internal_damage_service


def _settings():
    return SimpleNamespace(
        record_service_url="http://record-service:8000",
        maintenance_service_url="http://maintenance-service:8000",
        booking_service_url="http://booking-service:8000",
    )


def test_duplicate_fault_burst_is_suppressed_without_a_service_db(monkeypatch):
    published = []
    vehicle_updates = []
    record_ids = iter([501, 502])

    monkeypatch.setattr(internal_damage_service, "get_settings", _settings)
    monkeypatch.setattr(internal_damage_service, "build_context", lambda *_args, **_kwargs: (11, 21, "user-1"))
    monkeypatch.setattr(internal_damage_service, "post_json", lambda *_args, **_kwargs: {"recordId": next(record_ids)})
    monkeypatch.setattr(internal_damage_service, "has_open_ticket", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        internal_damage_service,
        "publish_event",
        lambda event_type, payload, *, event_id=None: published.append((event_type, payload, event_id)),
    )
    monkeypatch.setattr(
        internal_damage_service,
        "update_vehicle_status",
        lambda vehicle_id, status: vehicle_updates.append((vehicle_id, status)),
    )
    internal_damage_service._recent_fault_cache.clear()

    payload = internal_damage_service.InternalDamagePayload(
        bookingId=11,
        tripId=21,
        vehicleId=7,
        userId="user-1",
        faultCode="BATTERY_WARN",
        notes="battery warning light",
    )
    snapshot = {"batteryLevel": 10, "createdAt": "2026-04-07T01:00:00Z"}

    first = internal_damage_service.process_internal_damage(payload, snapshot=snapshot)
    second = internal_damage_service.process_internal_damage(payload, snapshot=snapshot)

    assert first["incidentPublished"] is True
    assert first["duplicateSuppressed"] is False
    assert second["incidentPublished"] is False
    assert second["duplicateSuppressed"] is True
    assert vehicle_updates == [(7, "MAINTENANCE_REQUIRED"), (7, "MAINTENANCE_REQUIRED")]
    assert [event_type for event_type, _payload, _event_id in published] == [
        "incident.internal_fault_detected",
        "booking.disruption_notification",
    ]


def test_open_ticket_suppresses_duplicate_fault_without_publish(monkeypatch):
    published = []

    monkeypatch.setattr(internal_damage_service, "get_settings", _settings)
    monkeypatch.setattr(internal_damage_service, "build_context", lambda *_args, **_kwargs: (11, 21, "user-1"))
    monkeypatch.setattr(internal_damage_service, "post_json", lambda *_args, **_kwargs: {"recordId": 777})
    monkeypatch.setattr(internal_damage_service, "has_open_ticket", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        internal_damage_service,
        "publish_event",
        lambda event_type, payload, *, event_id=None: published.append((event_type, payload, event_id)),
    )
    monkeypatch.setattr(internal_damage_service, "update_vehicle_status", lambda *_args, **_kwargs: None)
    internal_damage_service._recent_fault_cache.clear()

    result = internal_damage_service.process_internal_damage(
        internal_damage_service.InternalDamagePayload(
            bookingId=11,
            tripId=21,
            vehicleId=7,
            userId="user-1",
            faultCode="BATTERY_WARN",
            notes="battery warning light",
        ),
        snapshot={"batteryLevel": 10, "createdAt": "2026-04-07T01:00:00Z"},
    )

    assert result["blocked"] is True
    assert result["duplicateSuppressed"] is True
    assert result["incidentPublished"] is False
    assert published == []
