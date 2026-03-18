from __future__ import annotations

from fastapi import HTTPException
from pydantic import BaseModel

from fleetshare_common.app import create_app
from fleetshare_common.http import get_json, post_json
from fleetshare_common.messaging import publish_event
from fleetshare_common.settings import get_settings
from fleetshare_common.vehicle_grpc import update_vehicle_status

app = create_app("Internal Damage Service", "Composite telemetry-backed internal fault workflow.")


class InternalDamagePayload(BaseModel):
    bookingId: int
    vehicleId: int
    userId: str
    tripId: int | None = None
    faultCode: str = ""
    sensorType: str = "TELEMETRY"
    notes: str = ""


def assess_fault(snapshot: dict, payload: InternalDamagePayload) -> tuple[str, str]:
    tokens = f"{snapshot.get('faultCode', '')} {payload.faultCode} {payload.notes}".lower()
    battery_low = snapshot.get("batteryLevel", 100) < 20
    tire_issue = not snapshot.get("tirePressureOk", True)
    explicit = any(token in tokens for token in ("critical", "flat", "fault", "hazard", "battery"))
    if snapshot.get("severity") == "CRITICAL" or battery_low or tire_issue or explicit:
        return "SEVERE", "Trip blocked. Vehicle requires maintenance review."
    if snapshot.get("severity") == "WARNING":
        return "MODERATE", "Warning captured; operations follow-up recommended."
    return "MINOR", "No critical issue detected."


@app.post("/internal-damage/validate")
def validate_internal_damage(payload: InternalDamagePayload):
    settings = get_settings()
    try:
        snapshot = get_json(f"{settings.vehicle_service_url}/vehicles/{payload.vehicleId}/telemetry/latest")
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=502, detail=f"Unable to retrieve telemetry: {exc}") from exc

    severity, message = assess_fault(snapshot, payload)
    record = post_json(
        f"{settings.record_service_url}/records",
        {
            "bookingId": payload.bookingId,
            "tripId": payload.tripId,
            "vehicleId": payload.vehicleId,
            "recordType": "INTERNAL_FAULT",
            "notes": payload.notes or payload.faultCode,
            "severity": severity,
            "reviewState": "EXTERNAL_ASSESSED",
            "confidence": 0.9 if severity == "SEVERE" else 0.72,
            "detectedDamage": [snapshot.get("faultCode", "") or payload.faultCode or "telemetry-warning"],
        },
    )
    blocked = severity == "SEVERE"
    if blocked:
        update_vehicle_status(payload.vehicleId, "MAINTENANCE_REQUIRED")
        publish_event(
            "incident.internal_fault_detected",
            {
                "recordId": record["recordId"],
                "bookingId": payload.bookingId,
                "tripId": payload.tripId,
                "vehicleId": payload.vehicleId,
                "userId": payload.userId,
                "severity": severity,
                "damageType": payload.faultCode or snapshot.get("faultCode") or "critical-fault",
                "recommendedAction": "Cancel affected bookings and open maintenance ticket",
            },
        )
    return {
        "recordId": record["recordId"],
        "assessmentResult": {"severity": severity, "faultType": payload.faultCode or snapshot.get("faultCode", "")},
        "severity": severity,
        "recommendedAction": message,
        "blocked": blocked,
    }


@app.post("/internal-damage/fault-alert")
def fault_alert(payload: InternalDamagePayload):
    return validate_internal_damage(payload)
