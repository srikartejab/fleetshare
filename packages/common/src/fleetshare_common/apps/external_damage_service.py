from __future__ import annotations

from uuid import uuid4

from fastapi import File, Form, UploadFile

from fleetshare_common.ai import assess_damage
from fleetshare_common.app import create_app
from fleetshare_common.http import patch_json, post_json
from fleetshare_common.messaging import publish_event
from fleetshare_common.object_store import ensure_bucket, upload_bytes
from fleetshare_common.settings import get_settings
from fleetshare_common.vehicle_grpc import update_vehicle_status

app = create_app("External Damage Service", "Composite pre-trip external damage workflow.")


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
    assessment = assess_damage(notes, filenames)
    review_state = "EXTERNAL_ASSESSED"
    blocked = False
    warning = "Inspection passed"
    if assessment["confidence"] < 0.7:
        review_state = "MANUAL_REVIEW"
        blocked = True
        warning = "Low confidence evidence requires manual review."
    elif assessment["severity"] == "SEVERE":
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
        "assessmentResult": assessment,
        "tripStatus": "BLOCKED" if blocked else "CLEARED",
        "warningMessage": warning,
        "manualReview": review_state == "MANUAL_REVIEW",
    }
