from __future__ import annotations

from fastapi import File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from fleetshare_common.ai import assess_damage
from fleetshare_common.app import create_app
from fleetshare_common.http import get_json, patch_json, post_form_json
from fleetshare_common.messaging import publish_event
from fleetshare_common.settings import get_settings
from fleetshare_common.vehicle_grpc import update_vehicle_status

app = create_app("External Damage Service", "Composite pre-trip external damage workflow.")


class ExternalDamageCancellationPayload(BaseModel):
    bookingId: int
    vehicleId: int
    userId: str


async def _extract_uploaded_photos(photos: list[UploadFile]) -> tuple[list[tuple[str, bytes, str]], list[bytes]]:
    photo_payloads: list[tuple[str, bytes, str]] = []
    image_bytes_list: list[bytes] = []
    if not photos:
        return photo_payloads, image_bytes_list

    for photo in photos:
        data = await photo.read()
        image_bytes_list.append(data)
        filename = photo.filename or "upload.bin"
        photo_payloads.append((filename, data, photo.content_type or "application/octet-stream"))
    return photo_payloads, image_bytes_list


def _create_record_with_evidence(
    settings,
    *,
    booking_id: int,
    trip_id: int | None,
    vehicle_id: int,
    notes: str,
    photo_payloads: list[tuple[str, bytes, str]],
) -> dict:
    data = {
        "bookingId": booking_id,
        "vehicleId": vehicle_id,
        "recordType": "EXTERNAL_DAMAGE",
        "notes": notes,
        "severity": "PENDING",
        "reviewState": "PENDING_EXTERNAL",
        "confidence": 0.0,
    }
    if trip_id is not None:
        data["tripId"] = trip_id
    return post_form_json(
        f"{settings.record_service_url}/records/ingest",
        data=data,
        files=[("photos", file_tuple) for file_tuple in photo_payloads],
    )


@app.post("/damage-assessment/external")
async def assess_external_damage(
    bookingId: int = Form(...),
    vehicleId: int = Form(...),
    userId: str = Form(...),
    notes: str = Form(""),
    photos: list[UploadFile] = File(default_factory=list),
):
    settings = get_settings()
    photo_payloads, image_bytes_list = await _extract_uploaded_photos(photos)
    record = _create_record_with_evidence(
        settings,
        booking_id=bookingId,
        trip_id=None,
        vehicle_id=vehicleId,
        notes=notes,
        photo_payloads=photo_payloads,
    )
    assessment = assess_damage(notes, image_bytes_list=image_bytes_list, mode=settings.azure_vision_mode)
    review_state = "EXTERNAL_ASSESSED"
    blocked = False
    warning = "Inspection passed"
    if assessment["severity"] == "SEVERE":
        review_state = "EXTERNAL_BLOCKED"
        blocked = True
        warning = "Severe damage detected. Vehicle blocked."
        update_vehicle_status(vehicleId, "UNDER_INSPECTION")
    elif assessment["confidence"] < 0.55:
        review_state = "MANUAL_REVIEW"
        blocked = True
        warning = "Inspection details are incomplete. Add more evidence or request manual review."
    elif assessment["severity"] == "MODERATE":
        warning = "Moderate damage noted. You can still unlock the vehicle or cancel the booking to escalate it to ops."
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
        "reviewState": review_state,
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
    photo_payloads, image_bytes_list = await _extract_uploaded_photos(photos)
    record = _create_record_with_evidence(
        settings,
        booking_id=bookingId,
        trip_id=tripId,
        vehicle_id=vehicleId,
        notes=notes,
        photo_payloads=photo_payloads,
    )
    assessment = assess_damage(notes, image_bytes_list=image_bytes_list, mode=settings.azure_vision_mode)
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
    return {
        "bookingId": payload.bookingId,
        "vehicleId": payload.vehicleId,
        "recordId": latest_inspection["recordId"],
        "status": "CANCELLATION_REQUESTED",
        "message": "Cancellation requested. FleetShare is finalizing the cancellation and compensation now.",
        "warningMessage": "Moderate damage escalated. The booking will be cancelled and compensation processed.",
        "severity": latest_inspection["severity"],
        "reviewState": "EXTERNAL_BLOCKED",
        "detectedDamage": latest_inspection.get("detectedDamage") or ["possible body damage"],
    }
