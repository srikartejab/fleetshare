from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from botocore.exceptions import ClientError
from fastapi import Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import JSON, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, Session, mapped_column

from fleetshare_common.app import create_app
from fleetshare_common.database import Base, get_db, initialize_schema_with_retry
from fleetshare_common.object_store import download_bytes, upload_bytes
from fleetshare_common.timeutils import iso, utcnow_naive

app = create_app("Record Service", "Atomic evidence and record management service.")


class Record(Base):
    __tablename__ = "records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    booking_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trip_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vehicle_id: Mapped[int] = mapped_column(Integer, index=True)
    record_type: Mapped[str] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    severity: Mapped[str] = mapped_column(String(32), default="MODERATE")
    review_state: Mapped[str] = mapped_column(String(64), default="PENDING_EXTERNAL")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_urls: Mapped[list] = mapped_column(JSON, default=list)
    detected_damage: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)


class RecordPayload(BaseModel):
    bookingId: int | None = None
    tripId: int | None = None
    vehicleId: int
    recordType: str
    notes: str | None = None
    severity: str = "MODERATE"
    reviewState: str = "PENDING_EXTERNAL"
    confidence: float = 0.0
    evidenceUrls: list[str] = Field(default_factory=list)
    detectedDamage: list[str] = Field(default_factory=list)


class RecordPatchPayload(BaseModel):
    severity: str | None = None
    reviewState: str | None = None
    confidence: float | None = None
    detectedDamage: list[str] | None = None


@app.on_event("startup")
def startup_event():
    initialize_schema_with_retry(Base.metadata)


def record_to_dict(record: Record) -> dict:
    return {
        "recordId": record.id,
        "bookingId": record.booking_id,
        "tripId": record.trip_id,
        "vehicleId": record.vehicle_id,
        "recordType": record.record_type,
        "notes": record.notes,
        "severity": record.severity,
        "reviewState": record.review_state,
        "confidence": record.confidence,
        "evidenceUrls": record.evidence_urls,
        "detectedDamage": record.detected_damage,
        "createdAt": iso(record.created_at),
        "updatedAt": iso(record.updated_at),
    }


def _build_record(
    *,
    booking_id: int | None,
    trip_id: int | None,
    vehicle_id: int,
    record_type: str,
    notes: str | None,
    severity: str,
    review_state: str,
    confidence: float,
    evidence_urls: list[str],
    detected_damage: list[str],
) -> Record:
    return Record(
        booking_id=booking_id,
        trip_id=trip_id,
        vehicle_id=vehicle_id,
        record_type=record_type,
        notes=notes,
        severity=severity,
        review_state=review_state,
        confidence=confidence,
        evidence_urls=evidence_urls,
        detected_damage=detected_damage,
    )


async def _store_uploaded_evidence(
    *,
    booking_id: int | None,
    trip_id: int | None,
    record_type: str,
    photos: list[UploadFile],
) -> list[str]:
    uploaded_keys: list[str] = []
    if not photos:
        return uploaded_keys
    prefix_parts = ["records", record_type.lower()]
    if booking_id is not None:
        prefix_parts.append(f"booking-{booking_id}")
    if trip_id is not None:
        prefix_parts.append(f"trip-{trip_id}")
    prefix = "/".join(prefix_parts)
    for photo in photos:
        raw = await photo.read()
        filename = photo.filename or "upload.bin"
        key = f"{prefix}/{uuid4()}-{filename}"
        uploaded_keys.append(upload_bytes(key, raw, content_type=photo.content_type or "application/octet-stream"))
    return uploaded_keys


@app.get("/records")
def list_records(
    bookingId: int | None = None,
    tripId: int | None = None,
    vehicleId: int | None = None,
    recordType: str | None = None,
    reviewState: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Record)
    if bookingId is not None:
        query = query.filter(Record.booking_id == bookingId)
    if tripId is not None:
        query = query.filter(Record.trip_id == tripId)
    if vehicleId is not None:
        query = query.filter(Record.vehicle_id == vehicleId)
    if recordType is not None:
        query = query.filter(Record.record_type == recordType)
    if reviewState is not None:
        query = query.filter(Record.review_state == reviewState)
    return [record_to_dict(record) for record in query.order_by(Record.id.desc()).all()]


@app.post("/records")
def create_record(payload: RecordPayload, db: Session = Depends(get_db)):
    record = _build_record(
        booking_id=payload.bookingId,
        trip_id=payload.tripId,
        vehicle_id=payload.vehicleId,
        record_type=payload.recordType,
        notes=payload.notes,
        severity=payload.severity,
        review_state=payload.reviewState,
        confidence=payload.confidence,
        evidence_urls=payload.evidenceUrls,
        detected_damage=payload.detectedDamage,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"recordId": record.id, "status": record.review_state}


@app.post("/records/ingest")
async def create_record_with_evidence(
    vehicleId: int = Form(...),
    recordType: str = Form(...),
    bookingId: int | None = Form(None),
    tripId: int | None = Form(None),
    notes: str | None = Form(None),
    severity: str = Form("PENDING"),
    reviewState: str = Form("PENDING_EXTERNAL"),
    confidence: float = Form(0.0),
    photos: list[UploadFile] = File(default_factory=list),
    db: Session = Depends(get_db),
):
    evidence_urls = await _store_uploaded_evidence(
        booking_id=bookingId,
        trip_id=tripId,
        record_type=recordType,
        photos=photos,
    )
    record = _build_record(
        booking_id=bookingId,
        trip_id=tripId,
        vehicle_id=vehicleId,
        record_type=recordType,
        notes=notes,
        severity=severity,
        review_state=reviewState,
        confidence=confidence,
        evidence_urls=evidence_urls,
        detected_damage=[],
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"recordId": record.id, "status": record.review_state}


@app.get("/records/{record_id}/evidence/{index}")
def get_record_evidence(record_id: int, index: int, db: Session = Depends(get_db)):
    record = db.get(Record, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    evidence_urls = record.evidence_urls or []
    if index < 0 or index >= len(evidence_urls):
        raise HTTPException(status_code=404, detail="Evidence item not found")

    object_key = evidence_urls[index]
    try:
        raw, content_type = download_bytes(object_key)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code in {"NoSuchKey", "404"}:
            raise HTTPException(status_code=404, detail="Evidence object not found") from exc
        raise HTTPException(status_code=502, detail="Evidence storage is unavailable") from exc
    filename = Path(object_key).name or f"record-{record_id}-evidence-{index + 1}"
    return Response(
        content=raw,
        media_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@app.patch("/records/{record_id}")
def patch_record(record_id: int, payload: RecordPatchPayload, db: Session = Depends(get_db)):
    record = db.get(Record, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    if payload.severity is not None:
        record.severity = payload.severity
    if payload.reviewState is not None:
        record.review_state = payload.reviewState
    if payload.confidence is not None:
        record.confidence = payload.confidence
    if payload.detectedDamage is not None:
        record.detected_damage = payload.detectedDamage
    db.commit()
    return {"recordId": record.id, "status": record.review_state}


@app.get("/records/manual-review-queue")
def manual_review_queue(db: Session = Depends(get_db)):
    records = db.query(Record).filter(Record.review_state == "MANUAL_REVIEW").order_by(Record.id.desc()).all()
    return [record_to_dict(record) for record in records]
