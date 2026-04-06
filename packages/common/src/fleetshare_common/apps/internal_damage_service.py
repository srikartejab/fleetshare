from __future__ import annotations

import re
import threading
from datetime import datetime, timedelta

from fastapi import HTTPException
from pydantic import BaseModel

from fleetshare_common.app import create_app
from fleetshare_common.http import get_json, post_json
from fleetshare_common.messaging import publish_event, stable_event_id, start_consumer
from fleetshare_common.settings import get_settings
from fleetshare_common.timeutils import as_utc_naive, utcnow
from fleetshare_common.vehicle_grpc import update_vehicle_status

app = create_app("Internal Damage Service", "Composite telemetry-backed internal fault workflow.")

OPS_USER_ID = "ops-maint-1"
RECENT_WINDOW_MINUTES = 15
_recent_fault_cache: dict[tuple[int, str], datetime] = {}
_recent_fault_lock = threading.Lock()


class InternalDamagePayload(BaseModel):
    bookingId: int | None = None
    vehicleId: int
    userId: str | None = None
    tripId: int | None = None
    faultCode: str = ""
    sensorType: str = "TELEMETRY"
    notes: str = ""


@app.on_event("startup")
def startup_event():
    start_consumer("internal-damage-telemetry", ["vehicle.telemetry_alert"], handle_telemetry_event)


def normalize_fault_family(snapshot: dict, payload: InternalDamagePayload) -> str:
    tokens = f"{snapshot.get('faultCode', '')} {payload.faultCode} {payload.notes}".lower()
    if snapshot.get("batteryLevel", 100) < 20 or "battery" in tokens:
        return "low_battery"
    if not snapshot.get("tirePressureOk", True) or "tire" in tokens or "flat" in tokens:
        return "tire_pressure"
    source = payload.faultCode or snapshot.get("faultCode") or payload.notes or "general_fault"
    normalized = re.sub(r"[^a-z0-9]+", "_", source.lower()).strip("_")
    return normalized or "general_fault"


def assess_fault(snapshot: dict, payload: InternalDamagePayload) -> tuple[str, str]:
    tokens = f"{snapshot.get('faultCode', '')} {payload.faultCode} {payload.notes}".lower()
    battery_low = snapshot.get("batteryLevel", 100) < 20
    tire_issue = not snapshot.get("tirePressureOk", True)
    explicit = any(token in tokens for token in ("critical", "flat", "fault", "hazard", "battery", "warning light"))
    if snapshot.get("severity") == "CRITICAL" or battery_low or tire_issue or explicit:
        return "SEVERE", "Severe issue detected. Stop at the nearest safe carpark and proceed to end the trip."
    if snapshot.get("severity") == "WARNING":
        return "MODERATE", "Warning captured; continue only if safe and monitor the vehicle closely."
    return "MINOR", "No critical issue detected."


def get_latest_snapshot(settings, vehicle_id: int) -> dict:
    try:
        return get_json(f"{settings.vehicle_service_url}/vehicles/{vehicle_id}/telemetry/latest")
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=502, detail=f"Unable to retrieve telemetry: {exc}") from exc


def resolve_active_trip_context(settings, vehicle_id: int) -> dict | None:
    try:
        return get_json(f"{settings.booking_service_url}/bookings/vehicle/{vehicle_id}/active")
    except Exception:
        return None


def has_open_ticket(settings, vehicle_id: int, fault_fingerprint: str) -> bool:
    tickets = get_json(f"{settings.maintenance_service_url}/maintenance/tickets")
    if not isinstance(tickets, list):
        return False
    for ticket in tickets:
        if ticket["vehicleId"] != vehicle_id:
            continue
        if ticket["status"] in {"RESOLVED", "CLOSED"}:
            continue
        normalized_type = re.sub(r"[^a-z0-9]+", "_", str(ticket.get("damageType", "")).lower()).strip("_")
        if normalized_type == fault_fingerprint:
            return True
    return False


def processed_recently(vehicle_id: int, fault_fingerprint: str) -> bool:
    cutoff = as_utc_naive(utcnow() - timedelta(minutes=RECENT_WINDOW_MINUTES))
    cache_key = (vehicle_id, fault_fingerprint)
    with _recent_fault_lock:
        stale_keys = [key for key, created_at in _recent_fault_cache.items() if created_at < cutoff]
        for key in stale_keys:
            _recent_fault_cache.pop(key, None)
        existing = _recent_fault_cache.get(cache_key)
        return existing is not None and existing >= cutoff


def remember_processed(vehicle_id: int, fault_fingerprint: str):
    with _recent_fault_lock:
        _recent_fault_cache[(vehicle_id, fault_fingerprint)] = as_utc_naive(utcnow())


def build_context(settings, payload: InternalDamagePayload) -> tuple[int | None, int | None, str | None]:
    booking_id = payload.bookingId
    trip_id = payload.tripId
    user_id = payload.userId

    if trip_id is not None and booking_id is not None and user_id:
        return booking_id, trip_id, user_id

    if booking_id is not None:
        booking = get_json(f"{settings.booking_service_url}/booking/{booking_id}")
        trip_id = trip_id or booking.get("tripId")
        user_id = user_id or booking.get("userId")
        return booking_id, trip_id, user_id

    active_booking = resolve_active_trip_context(settings, payload.vehicleId)
    if not active_booking:
        return None, None, None
    return active_booking["bookingId"], active_booking.get("tripId"), active_booking["userId"]


def _incident_source_event_id(
    payload: InternalDamagePayload,
    *,
    snapshot: dict,
    booking_id: int | None,
    trip_id: int | None,
    fault_fingerprint: str,
    source_event_id: str | None,
) -> str:
    if source_event_id:
        return source_event_id
    return stable_event_id(
        "internal-damage",
        payload.vehicleId,
        booking_id,
        trip_id,
        fault_fingerprint,
        snapshot.get("createdAt"),
        payload.faultCode,
        payload.notes,
    )


def process_internal_damage(payload: InternalDamagePayload, *, snapshot: dict | None = None, source_event_id: str | None = None) -> dict:
    settings = get_settings()
    booking_id, trip_id, user_id = build_context(settings, payload)
    snapshot = snapshot or get_latest_snapshot(settings, payload.vehicleId)
    severity, message = assess_fault(snapshot, payload)
    fault_fingerprint = normalize_fault_family(snapshot, payload)
    resolved_source_event_id = _incident_source_event_id(
        payload,
        snapshot=snapshot,
        booking_id=booking_id,
        trip_id=trip_id,
        fault_fingerprint=fault_fingerprint,
        source_event_id=source_event_id,
    )

    record = post_json(
        f"{settings.record_service_url}/records",
        {
            "bookingId": booking_id,
            "tripId": trip_id,
            "vehicleId": payload.vehicleId,
            "recordType": "INTERNAL_FAULT",
            "notes": payload.notes or payload.faultCode or snapshot.get("faultCode"),
            "severity": severity,
            "reviewState": "EXTERNAL_ASSESSED",
            "confidence": 0.9 if severity == "SEVERE" else 0.72,
            "detectedDamage": [fault_fingerprint],
        },
    )

    blocked = severity == "SEVERE"
    duplicate_suppressed = False
    incident_published = False

    if blocked:
        update_vehicle_status(payload.vehicleId, "MAINTENANCE_REQUIRED")
        duplicate_suppressed = has_open_ticket(settings, payload.vehicleId, fault_fingerprint) or processed_recently(
            payload.vehicleId, fault_fingerprint
        )
        if not duplicate_suppressed:
            publish_event(
                "incident.internal_fault_detected",
                {
                    "recordId": record["recordId"],
                    "bookingId": booking_id,
                    "tripId": trip_id,
                    "vehicleId": payload.vehicleId,
                    "userId": user_id or payload.userId or OPS_USER_ID,
                    "severity": severity,
                    "damageType": fault_fingerprint,
                    "recommendedAction": "Open maintenance ticket, cancel affected bookings, and guide customer to end trip safely.",
                    "incidentAt": snapshot.get("createdAt"),
                },
                event_id=resolved_source_event_id,
            )
            if trip_id and booking_id and user_id:
                publish_event(
                    "booking.disruption_notification",
                    {
                        "bookingId": booking_id,
                        "tripId": trip_id,
                        "userIds": [user_id, OPS_USER_ID],
                        "subject": "Vehicle issue detected during trip",
                        "message": "A severe vehicle issue was detected. Stop at the nearest safe carpark and begin the end-trip flow.",
                    },
                    event_id=stable_event_id("internal-damage", "trip-notification", resolved_source_event_id, booking_id, trip_id),
                )
            remember_processed(payload.vehicleId, fault_fingerprint)
            incident_published = True

    return {
        "recordId": record["recordId"],
        "assessmentResult": {"severity": severity, "faultType": payload.faultCode or snapshot.get("faultCode", "")},
        "severity": severity,
        "recommendedAction": message,
        "blocked": blocked,
        "duplicateSuppressed": duplicate_suppressed,
        "incidentPublished": incident_published,
        "bookingId": booking_id,
        "tripId": trip_id,
        "userId": user_id,
    }


def handle_telemetry_event(event: dict):
    payload = event["payload"]
    active_booking = resolve_active_trip_context(get_settings(), payload["vehicleId"])
    if not active_booking:
        return
    process_internal_damage(
        InternalDamagePayload(
            bookingId=active_booking["bookingId"],
            tripId=active_booking.get("tripId"),
            vehicleId=payload["vehicleId"],
            userId=active_booking["userId"],
            faultCode=payload.get("faultCode", ""),
            sensorType="TELEMETRY",
            notes=payload.get("faultCode", ""),
        ),
        snapshot=payload,
        source_event_id=event["event_id"],
    )


@app.post("/internal-damage/validate")
def validate_internal_damage(payload: InternalDamagePayload):
    return process_internal_damage(payload)


@app.post("/internal-damage/fault-alert")
def fault_alert(payload: InternalDamagePayload):
    return process_internal_damage(payload)
