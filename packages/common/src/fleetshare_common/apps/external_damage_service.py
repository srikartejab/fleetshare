from __future__ import annotations

from uuid import uuid4

from fastapi import File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from fleetshare_common.ai import assess_damage
from fleetshare_common.app import create_app
from fleetshare_common.http import get_json, patch_json, post_json
from fleetshare_common.messaging import publish_event
from fleetshare_common.object_store import ensure_bucket, upload_bytes
from fleetshare_common.settings import get_settings
from fleetshare_common.vehicle_grpc import update_vehicle_status

app = create_app("External Damage Service", "Composite pre-trip external damage workflow.")


class ExternalDamageCancellationPayload(BaseModel):
    bookingId: int
    vehicleId: int
    userId: str


@app.on_event("startup")
def startup_event():
    try:
        ensure_bucket()
    except Exception:
        # MinIO may still be starting when the service boots; uploads re-check lazily.
        pass


@app.post("/damage-assessment/external")
async def assess_external_damage(
    bookingId: int = Form(...),
    vehicleId: int = Form(...),
    userId: str = Form(...),
    notes: str = Form(""),
    photos: list[UploadFile] = File(default_factory=list),
):
    settings = get_settings()
    uploaded_keys = []
    filenames = []
    for photo in photos:
        data = await photo.read()
        key = upload_bytes(f"damage/{bookingId}/{uuid4()}-{photo.filename}", data, photo.content_type or "image/jpeg")
        uploaded_keys.append(key)
        filenames.append(photo.filename)

    record = post_json(
        f"{settings.record_service_url}/records",
        {
            "bookingId": bookingId,
            "vehicleId": vehicleId,
            "recordType": "EXTERNAL_DAMAGE",
            "notes": notes,
            "reviewState": "PENDING_EXTERNAL",
            "evidenceUrls": uploaded_keys,
        },
    )
    assessment = assess_damage(notes, filenames, mode=settings.azure_vision_mode)
    review_state = "EXTERNAL_ASSESSED"
    blocked = False
    warning = "Inspection passed"
    if assessment["severity"] == "SEVERE":
        review_state = "EXTERNAL_BLOCKED"
        blocked = True
        warning = "Severe damage detected. Vehicle blocked."
        update_vehicle_status(vehicleId, "UNDER_INSPECTION")
        publish_event(
            "incident.external_damage_detected",
            {
                "recordId": record["recordId"],
                "bookingId": bookingId,
                "vehicleId": vehicleId,
                "userId": userId,
                "severity": assessment["severity"],
                "damageType": ",".join(assessment["detectedDamage"]),
                "recommendedAction": "Immediate inspection and customer refund",
            },
        )
    elif assessment["severity"] == "MODERATE":
        warning = "Moderate damage noted. You can still unlock the vehicle or cancel the booking to escalate it to ops."
    elif assessment["confidence"] < 0.55:
        review_state = "MANUAL_REVIEW"
        blocked = True
        warning = "Inspection details are incomplete. Add more evidence or request manual review."
    patch_json(
        f"{settings.record_service_url}/records/{record['recordId']}",
        {
            "severity": assessment["severity"],
            "reviewState": review_state,
            "confidence": assessment["confidence"],
            "detectedDamage": assessment["detectedDamage"],
        },
    )
    return {
        "recordId": record["recordId"],
        "bookingId": bookingId,
        "vehicleId": vehicleId,
        "assessmentResult": assessment,
        "tripStatus": "BLOCKED" if blocked else "CLEARED",
        "warningMessage": warning,
        "manualReview": review_state == "MANUAL_REVIEW",
    }


@app.post("/damage-assessment/post-trip")
async def assess_post_trip_damage(
    bookingId: int = Form(...),
    tripId: int = Form(...),
    vehicleId: int = Form(...),
    userId: str = Form(...),
    notes: str = Form(""),
    photos: list[UploadFile] = File(default_factory=list),
):
    settings = get_settings()
    uploaded_keys = []
    filenames = []
    for photo in photos:
        data = await photo.read()
        key = upload_bytes(
            f"damage/post-trip/{bookingId}/{uuid4()}-{photo.filename}",
            data,
            photo.content_type or "image/jpeg",
        )
        uploaded_keys.append(key)
        filenames.append(photo.filename)

    record = post_json(
        f"{settings.record_service_url}/records",
        {
            "bookingId": bookingId,
            "tripId": tripId,
            "vehicleId": vehicleId,
            "recordType": "POST_TRIP_EXTERNAL_DAMAGE",
            "notes": notes,
            "reviewState": "PENDING_EXTERNAL",
            "evidenceUrls": uploaded_keys,
        },
    )
    assessment = assess_damage(notes, filenames, mode=settings.azure_vision_mode)
    review_state = "EXTERNAL_ASSESSED"
    follow_up_required = False
    warning = "Post-trip inspection recorded. You can now review and lock the car."
    if assessment["severity"] == "SEVERE":
        review_state = "EXTERNAL_BLOCKED"
        follow_up_required = True
        warning = "Severe post-trip damage recorded. Ops review and downstream recovery have been triggered."
        update_vehicle_status(vehicleId, "UNDER_INSPECTION")
        publish_event(
            "incident.external_damage_detected",
            {
                "recordId": record["recordId"],
                "bookingId": bookingId,
                "tripId": tripId,
                "vehicleId": vehicleId,
                "userId": userId,
                "severity": assessment["severity"],
                "damageType": ",".join(assessment["detectedDamage"]),
                "recommendedAction": "Inspect vehicle before next rental and compensate affected bookings if needed",
            },
        )
    elif assessment["confidence"] < 0.55:
        review_state = "MANUAL_REVIEW"
        follow_up_required = True
        warning = "Post-trip inspection needs manual review. The report is saved and ops will follow up."
    elif assessment["severity"] == "MODERATE":
        warning = "Moderate post-trip issue noted. The report is saved for ops follow-up."
    patch_json(
        f"{settings.record_service_url}/records/{record['recordId']}",
        {
            "severity": assessment["severity"],
            "reviewState": review_state,
            "confidence": assessment["confidence"],
            "detectedDamage": assessment["detectedDamage"],
        },
    )
    return {
        "recordId": record["recordId"],
        "bookingId": bookingId,
        "tripId": tripId,
        "vehicleId": vehicleId,
        "assessmentResult": assessment,
        "followUpRequired": follow_up_required,
        "warningMessage": warning,
        "manualReview": review_state == "MANUAL_REVIEW",
    }


@app.post("/damage-assessment/external/customer-cancel")
def cancel_booking_for_external_damage(payload: ExternalDamageCancellationPayload):
    settings = get_settings()
    booking = get_json(f"{settings.booking_service_url}/booking/{payload.bookingId}")
    if booking["userId"] != payload.userId:
        raise HTTPException(status_code=403, detail="Booking does not belong to the requesting user.")
    if booking["status"] in {"CANCELLED", "COMPLETED", "RECONCILED"}:
        raise HTTPException(status_code=409, detail=f"Booking can no longer be cancelled. Current status: {booking['status']}")

    records = get_json(
        f"{settings.record_service_url}/records",
        {"bookingId": payload.bookingId, "recordType": "EXTERNAL_DAMAGE"},
    )
    latest_inspection = records[0] if isinstance(records, list) and records else None
    if not latest_inspection:
        raise HTTPException(status_code=409, detail="External inspection record not found for this booking.")
    if latest_inspection["severity"] != "MODERATE":
        raise HTTPException(status_code=409, detail="Customer escalation is only available for moderate external damage findings.")

    patch_json(
        f"{settings.record_service_url}/records/{latest_inspection['recordId']}",
        {
            "reviewState": "EXTERNAL_BLOCKED",
        },
    )
    update_vehicle_status(payload.vehicleId, "UNDER_INSPECTION")
    publish_event(
        "incident.external_damage_detected",
        {
            "recordId": latest_inspection["recordId"],
            "bookingId": payload.bookingId,
            "vehicleId": payload.vehicleId,
            "userId": payload.userId,
            "severity": latest_inspection["severity"],
            "damageType": ",".join(latest_inspection.get("detectedDamage") or ["possible body damage"]),
            "recommendedAction": "Customer requested cancellation after moderate external damage finding",
        },
    )
    return {
        "bookingId": payload.bookingId,
        "vehicleId": payload.vehicleId,
        "recordId": latest_inspection["recordId"],
        "status": "CANCELLATION_REQUESTED",
        "message": "Cancellation requested. Ops review, compensation, and notifications will follow through the incident workflow.",
    }
